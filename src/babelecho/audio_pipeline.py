from pathlib import Path

from .adapt import adapt_to_chinese
from .audio import assemble_audio
from .audio_normalize import normalize_audio_transcript
from .asr import run_asr
from .audio_source import ingest_audio_source
from .checks import check_run_artifacts
from .config import load_yaml
from .diarization import run_diarization
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
from .voice_profile import apply_voice_profile_config


AUDIO_PIPELINE_STAGES = (
    "ingest_audio",
    "asr",
    "diarize",
    "normalize",
    "adapt",
    "synthesize",
    "assemble",
    "publish",
)


def _run_stage(status: dict, run_paths, stage_name: str, action):
    mark_stage_running(status, run_paths, stage_name)
    try:
        result = action()
    except Exception as error:
        mark_stage_failed(status, run_paths, stage_name, error)
        raise
    mark_stage_succeeded(status, run_paths, stage_name)
    return result


def run_audio_pipeline(
    *,
    workspace: str,
    run_id: str,
    local_config_path: str,
    audio_file: str | None = None,
    audio_url: str | None = None,
    from_stage: str = "ingest_audio",
    to_stage: str = "ingest_audio",
    title: str | None = None,
) -> str:
    if bool(audio_file) == bool(audio_url):
        raise ValueError("audio convert requires exactly one of --audio-file or --audio-url")
    stage_index = AUDIO_PIPELINE_STAGES.index(from_stage)
    stop_index = AUDIO_PIPELINE_STAGES.index(to_stage)
    if stop_index < stage_index:
        raise ValueError("--to-stage must be the same as or after --from-stage")

    local_config = load_yaml(Path(local_config_path))
    run_paths = create_run(workspace, run_id)
    status = init_run_status(
        run_paths,
        from_stage=from_stage,
        to_stage=to_stage,
        input_info={
            "audio_file": audio_file,
            "audio_url": audio_url,
            "local_config": local_config_path,
            "title": title,
        },
        stages=AUDIO_PIPELINE_STAGES,
    )
    outputs: list[str] = []

    if stage_index <= AUDIO_PIPELINE_STAGES.index("ingest_audio") <= stop_index:
        audio_path = _run_stage(
            status,
            run_paths,
            "ingest_audio",
            lambda: ingest_audio_source(
                {
                    "type": "audio_file" if audio_file else "audio_url",
                    "audio_file": audio_file,
                    "audio_url": audio_url,
                    "title": title,
                },
                run_paths,
            ),
        )
        metadata_path = run_paths.run_dir / "audio" / "metadata.json"
        outputs.extend(
            [
                f"ingest_audio: {audio_path}",
                f"audio metadata: {metadata_path}",
            ]
        )

    if stage_index <= AUDIO_PIPELINE_STAGES.index("asr") <= stop_index:
        asr_path = _run_stage(
            status,
            run_paths,
            "asr",
            lambda: run_asr(
                local_config.get("asr") or {},
                run_paths,
                config_path=Path(local_config_path),
            ),
        )
        outputs.append(f"asr: {asr_path}")

    if stage_index <= AUDIO_PIPELINE_STAGES.index("diarize") <= stop_index:
        def diarize_stage() -> str:
            diarization_path = run_diarization(
                local_config.get("diarization") or {"provider": "none"},
                run_paths,
                config_path=Path(local_config_path),
            )
            apply_voice_profile_config(
                local_config.get("voice_profile"),
                run_paths,
                config_path=Path(local_config_path),
            )
            return diarization_path

        diarization_path = _run_stage(
            status,
            run_paths,
            "diarize",
            diarize_stage,
        )
        outputs.append(f"diarize: {diarization_path}")

    if stage_index <= AUDIO_PIPELINE_STAGES.index("normalize") <= stop_index:
        normalized_path = _run_stage(
            status,
            run_paths,
            "normalize",
            lambda: normalize_audio_transcript(run_paths),
        )
        outputs.append(f"normalize: {normalized_path}")
        outputs.append(f"quality: {run_paths.transcript_quality_json}")

    if stage_index <= AUDIO_PIPELINE_STAGES.index("adapt") <= stop_index:
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

    if stage_index <= AUDIO_PIPELINE_STAGES.index("synthesize") <= stop_index:
        def synthesize_stage() -> tuple[dict, str, dict]:
            override_result = apply_script_overrides(run_paths, local_config.get("overrides"))
            manifest_path = synthesize_segments(
                run_paths,
                local_config["tts"],
                local_config.get("speaker_voices"),
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

    if stage_index <= AUDIO_PIPELINE_STAGES.index("assemble") <= stop_index:
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

    if stage_index <= AUDIO_PIPELINE_STAGES.index("publish") <= stop_index:
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
