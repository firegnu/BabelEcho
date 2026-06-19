from pathlib import Path

from .adapt import adapt_to_chinese
from .article import ingest_article_source, normalize_article
from .audio import assemble_audio
from .checks import check_run_artifacts
from .config import load_yaml, require_keys
from .jsonio import read_json
from .overrides import apply_script_overrides
from .paths import create_run
from .publish import publish_episode
from .status import (
    init_run_status,
    mark_run_succeeded,
    mark_stage_failed,
    mark_stage_running,
    mark_stage_succeeded,
)
from .synthesize import synthesize_segments


ARTICLE_PIPELINE_STAGES = ("ingest", "normalize", "adapt", "synthesize", "assemble", "publish")


def _run_stage(status: dict, run_paths, stage_name: str, action):
    mark_stage_running(status, run_paths, stage_name)
    try:
        result = action()
    except Exception as error:
        mark_stage_failed(status, run_paths, stage_name, error)
        raise
    mark_stage_succeeded(status, run_paths, stage_name)
    return result


def _raw_article_path(run_paths) -> Path:
    source = read_json(run_paths.source_json)
    raw_transcript = source.get("raw_transcript")
    if not raw_transcript:
        raise ValueError(f"Missing raw_transcript in {run_paths.source_json}")
    return run_paths.run_dir / raw_transcript


def _format_article_quality(run_paths) -> list[str]:
    if not run_paths.transcript_quality_json.exists():
        return []
    data = read_json(run_paths.transcript_quality_json)
    metrics = data.get("metrics") or {}
    lines = [f"article quality: {data.get('recommendation', 'unknown')}"]
    lines.append(
        "quality metrics: "
        f"segments={metrics.get('segment_count', 0)} "
        f"total_chars={metrics.get('total_chars', 0)} "
        f"source_type={metrics.get('source_type', 'unknown')} "
        f"extractor={metrics.get('extractor', 'unknown')}"
    )
    issues = data.get("reasons") or data.get("warnings") or []
    if issues:
        lines.append(f"quality issues: {', '.join(issues)}")
    return lines


def _source_config_from_input(
    *,
    url: str | None,
    article_file: str | None,
    title: str | None,
) -> tuple[dict, dict]:
    if url:
        source = {"type": "web_article", "url": url}
        if title:
            source["title"] = title
        return {"source": source}, {"article_url": url, "title": title}
    if not article_file:
        raise ValueError("article convert requires --url or --file")
    source = {"type": "article_file", "article_file": article_file}
    if title:
        source["title"] = title
    return {"source": source}, {"article_file": article_file, "title": title}


def run_article_pipeline(
    *,
    workspace: str,
    run_id: str,
    local_config_path: str,
    from_stage: str = "ingest",
    to_stage: str = "publish",
    url: str | None = None,
    article_file: str | None = None,
    title: str | None = None,
) -> str:
    source_config, input_info = _source_config_from_input(
        url=url,
        article_file=article_file,
        title=title,
    )
    local_config = load_yaml(Path(local_config_path))
    require_keys(local_config, ["llm", "tts", "publish"])
    run_paths = create_run(workspace, run_id)

    stage_index = ARTICLE_PIPELINE_STAGES.index(from_stage)
    stop_index = ARTICLE_PIPELINE_STAGES.index(to_stage)
    if stop_index < stage_index:
        raise ValueError("--to-stage must be the same as or after --from-stage")
    status = init_run_status(
        run_paths,
        from_stage=from_stage,
        to_stage=to_stage,
        input_info={key: value for key, value in input_info.items() if value is not None},
        stages=ARTICLE_PIPELINE_STAGES,
    )
    raw_path: Path | None = None
    outputs: list[str] = []

    if stage_index <= ARTICLE_PIPELINE_STAGES.index("ingest") <= stop_index:
        raw_path = _run_stage(
            status,
            run_paths,
            "ingest",
            lambda: ingest_article_source(source_config["source"], run_paths),
        )
        outputs.append(f"ingest: {raw_path}")

    if stage_index <= ARTICLE_PIPELINE_STAGES.index("normalize") <= stop_index:
        def normalize_stage() -> Path:
            nonlocal raw_path
            raw_path = _raw_article_path(run_paths)
            return normalize_article(run_paths, raw_path)

        normalized_path = _run_stage(status, run_paths, "normalize", normalize_stage)
        outputs.append(f"normalize: {normalized_path}")
        outputs.extend(_format_article_quality(run_paths))

    if stage_index <= ARTICLE_PIPELINE_STAGES.index("adapt") <= stop_index:
        def adapt_stage() -> tuple[str, dict]:
            script_path = adapt_to_chinese(
                run_paths,
                local_config["llm"],
                local_config.get("adapt"),
            )
            script_check = check_run_artifacts(run_paths, checks=("script",))
            return script_path, script_check

        script_path, script_check = _run_stage(status, run_paths, "adapt", adapt_stage)
        outputs.append(f"adapt: {script_path}")
        outputs.append(f"check script: {script_check['script_segments']} segments")

    if stage_index <= ARTICLE_PIPELINE_STAGES.index("synthesize") <= stop_index:
        def synthesize_stage() -> tuple[dict, str, dict]:
            override_result = apply_script_overrides(run_paths, local_config.get("overrides"))
            manifest_path = synthesize_segments(
                run_paths,
                local_config["tts"],
                None,
            )
            segment_check = check_run_artifacts(run_paths, checks=("segments",))
            return override_result, manifest_path, segment_check

        override_result, manifest_path, segment_check = _run_stage(
            status,
            run_paths,
            "synthesize",
            synthesize_stage,
        )
        if override_result["rules"]:
            outputs.append(
                "overrides: "
                f"{override_result['replacements']} replacements "
                f"from {override_result['rules']} rules"
            )
        outputs.append(f"synthesize: {manifest_path}")
        outputs.append(f"check segments: {segment_check['audio_segments']} files")

    if stage_index <= ARTICLE_PIPELINE_STAGES.index("assemble") <= stop_index:
        def assemble_stage() -> tuple[str, dict]:
            audio_path = assemble_audio(run_paths)
            output_check = check_run_artifacts(run_paths, checks=("output",))
            return audio_path, output_check

        audio_path, output_check = _run_stage(status, run_paths, "assemble", assemble_stage)
        outputs.append(f"assemble: {audio_path}")
        outputs.append(
            "check output: "
            f"{output_check['output_duration_seconds']:.3f}s, "
            f"{output_check['output_sample_rate']} Hz, "
            f"{output_check['output_channels']} ch"
        )

    if stage_index <= ARTICLE_PIPELINE_STAGES.index("publish") <= stop_index:
        feed_path = _run_stage(
            status,
            run_paths,
            "publish",
            lambda: publish_episode(run_paths, local_config["publish"]),
        )
        outputs.append(f"publish: {feed_path}")

    mark_run_succeeded(status, run_paths)
    if run_paths.output_audio.exists():
        outputs.append(f"audio: {run_paths.output_audio}")
    feed_path = run_paths.publish_dir / "feed.xml"
    if feed_path.exists():
        outputs.append(f"feed: {feed_path}")
    if run_paths.stable_feed.exists():
        outputs.append(f"stable feed: {run_paths.stable_feed}")
    return "\n".join(outputs)
