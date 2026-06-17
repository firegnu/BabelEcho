import argparse
import sys
from pathlib import Path

from .adapt import adapt_to_chinese
from .audio import assemble_audio
from .checks import CheckError, check_run_artifacts
from .config import load_yaml, require_keys
from .ingest import ingest_transcript_source
from .jsonio import read_json
from .overrides import apply_script_overrides
from .paths import create_run
from .publish import publish_episode
from .script import preview_chinese_script
from .status import (
    init_run_status,
    mark_run_succeeded,
    mark_stage_failed,
    mark_stage_running,
    mark_stage_succeeded,
)
from .synthesize import synthesize_segments
from .transcript import normalize_transcript

PIPELINE_STAGES = ("ingest", "normalize", "adapt", "synthesize", "assemble", "publish")
CHECK_NAMES = ("script", "segments", "output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="babelecho",
        description="BabelEcho backend pipeline",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    ingest = subparsers.add_parser("ingest", help="Fetch transcript input.")
    ingest.add_argument("--workspace", required=True)
    ingest.add_argument("--run-id", required=True)
    ingest.add_argument("--source-config", required=True)

    normalize = subparsers.add_parser("normalize", help="Normalize raw transcript.")
    normalize.add_argument("--workspace", required=True)
    normalize.add_argument("--run-id", required=True)
    normalize.add_argument("--raw-transcript", required=True)

    adapt = subparsers.add_parser("adapt", help="Adapt transcript to Chinese script.")
    adapt.add_argument("--workspace", required=True)
    adapt.add_argument("--run-id", required=True)
    adapt.add_argument("--local-config", required=True)

    synthesize = subparsers.add_parser("synthesize", help="Generate audio segments.")
    synthesize.add_argument("--workspace", required=True)
    synthesize.add_argument("--run-id", required=True)
    synthesize.add_argument("--local-config", required=True)

    assemble = subparsers.add_parser("assemble", help="Assemble final episode audio.")
    assemble.add_argument("--workspace", required=True)
    assemble.add_argument("--run-id", required=True)

    publish = subparsers.add_parser("publish", help="Publish static podcast artifacts.")
    publish.add_argument("--workspace", required=True)
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--local-config", required=True)

    script = subparsers.add_parser("script", help="Preview the Chinese script before TTS.")
    script.add_argument("--workspace", required=True)
    script.add_argument("--run-id", required=True)

    overrides = subparsers.add_parser("overrides", help="Apply local script overrides.")
    overrides.add_argument("--workspace", required=True)
    overrides.add_argument("--run-id", required=True)
    overrides.add_argument("--local-config", required=True)

    run = subparsers.add_parser("run", help="Run the transcript-to-podcast pipeline.")
    run.add_argument("--workspace", required=True)
    run.add_argument("--run-id", required=True)
    run_input = run.add_mutually_exclusive_group(required=True)
    run_input.add_argument("--source-config")
    run_input.add_argument("--transcript-file")
    run.add_argument("--title")
    run.add_argument("--original-url")
    run.add_argument("--local-config", required=True)
    run.add_argument(
        "--from-stage",
        choices=PIPELINE_STAGES,
        default="ingest",
        help="Resume from this stage.",
    )

    check = subparsers.add_parser("check", help="Validate generated run artifacts.")
    check.add_argument("--workspace", required=True)
    check.add_argument("--run-id", required=True)
    check.add_argument(
        "--checks",
        nargs="+",
        choices=CHECK_NAMES,
        default=CHECK_NAMES,
        help="Artifact checks to run.",
    )
    check.add_argument(
        "--max-script-chars",
        type=int,
        default=1200,
        help="Maximum allowed characters per script segment.",
    )

    return parser


def _raw_transcript_path(run_paths) -> Path:
    source = read_json(run_paths.source_json)
    raw_transcript = source.get("raw_transcript")
    if not raw_transcript:
        raise ValueError(f"Missing raw_transcript in {run_paths.source_json}")
    return run_paths.run_dir / raw_transcript


def _source_config_and_input(
    source_config_path: str | None,
    transcript_file: str | None,
    title: str | None,
    original_url: str | None,
) -> tuple[dict, dict]:
    if source_config_path:
        source_config = load_yaml(Path(source_config_path))
        require_keys(source_config, ["source"])
        return source_config, {"source_config": str(Path(source_config_path))}

    if not transcript_file:
        raise ValueError("Either source_config_path or transcript_file is required")

    transcript_path = Path(transcript_file)
    episode_title = title or transcript_path.stem
    source = {
        "type": "transcript_file",
        "transcript_file": str(transcript_path),
        "title": episode_title,
    }
    input_info = {
        "transcript_file": str(transcript_path),
        "title": episode_title,
    }
    if original_url:
        source["original_url"] = original_url
        input_info["original_url"] = original_url
    return {"source": source}, input_info


def _run_stage(status: dict, run_paths, stage_name: str, action):
    mark_stage_running(status, run_paths, stage_name)
    try:
        result = action()
    except Exception as error:
        mark_stage_failed(status, run_paths, stage_name, error)
        raise
    mark_stage_succeeded(status, run_paths, stage_name)
    return result


def run_pipeline(
    workspace: str,
    run_id: str,
    source_config_path: str | None,
    local_config_path: str,
    from_stage: str,
    transcript_file: str | None = None,
    title: str | None = None,
    original_url: str | None = None,
) -> str:
    source_config, input_info = _source_config_and_input(
        source_config_path,
        transcript_file,
        title,
        original_url,
    )
    local_config = load_yaml(Path(local_config_path))
    require_keys(local_config, ["llm", "tts", "publish"])

    run_paths = create_run(workspace, run_id)
    status = init_run_status(
        run_paths,
        from_stage=from_stage,
        input_info=input_info,
        stages=PIPELINE_STAGES,
    )
    stage_index = PIPELINE_STAGES.index(from_stage)
    raw_path: Path | None = None
    outputs: list[str] = []

    if stage_index <= PIPELINE_STAGES.index("ingest"):
        raw_path = _run_stage(
            status,
            run_paths,
            "ingest",
            lambda: ingest_transcript_source(source_config["source"], run_paths),
        )
        outputs.append(f"ingest: {raw_path}")

    if stage_index <= PIPELINE_STAGES.index("normalize"):
        def normalize_stage() -> Path:
            nonlocal raw_path
            if raw_path is None:
                raw_path = _raw_transcript_path(run_paths)
            return normalize_transcript(run_paths, raw_path)

        normalized_path = _run_stage(status, run_paths, "normalize", normalize_stage)
        outputs.append(f"normalize: {normalized_path}")

    if stage_index <= PIPELINE_STAGES.index("adapt"):
        def adapt_stage() -> tuple[str, dict]:
            script_path = adapt_to_chinese(run_paths, local_config["llm"])
            script_check = check_run_artifacts(run_paths, checks=("script",))
            return script_path, script_check

        script_path, script_check = _run_stage(status, run_paths, "adapt", adapt_stage)
        outputs.append(f"adapt: {script_path}")
        outputs.append(f"check script: {script_check['script_segments']} segments")

    if stage_index <= PIPELINE_STAGES.index("synthesize"):
        def synthesize_stage() -> tuple[dict, str, dict]:
            override_result = apply_script_overrides(run_paths, local_config.get("overrides"))
            manifest_path = synthesize_segments(run_paths, local_config["tts"])
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

    if stage_index <= PIPELINE_STAGES.index("assemble"):
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

    if stage_index <= PIPELINE_STAGES.index("publish"):
        feed_path = _run_stage(
            status,
            run_paths,
            "publish",
            lambda: publish_episode(run_paths, local_config["publish"]),
        )
        outputs.append(f"publish: {feed_path}")

    mark_run_succeeded(status, run_paths)
    outputs.append(f"audio: {run_paths.output_audio}")
    outputs.append(f"feed: {run_paths.publish_dir / 'feed.xml'}")
    outputs.append(f"stable feed: {run_paths.stable_feed}")
    return "\n".join(outputs)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from . import __version__

        print(__version__)
        return 0

    if args.command == "ingest":
        config = load_yaml(Path(args.source_config))
        require_keys(config, ["source"])
        run_paths = create_run(args.workspace, args.run_id)
        raw_path = ingest_transcript_source(config["source"], run_paths)
        print(raw_path)
        return 0

    if args.command == "normalize":
        run_paths = create_run(args.workspace, args.run_id)
        output = normalize_transcript(run_paths, Path(args.raw_transcript))
        print(output)
        return 0

    if args.command == "publish":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["publish"])
        run_paths = create_run(args.workspace, args.run_id)
        output = publish_episode(run_paths, config["publish"])
        print(output)
        return 0

    if args.command == "script":
        run_paths = create_run(args.workspace, args.run_id)
        try:
            output = preview_chinese_script(run_paths)
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        print(output)
        return 0

    if args.command == "overrides":
        config = load_yaml(Path(args.local_config))
        run_paths = create_run(args.workspace, args.run_id)
        try:
            result = apply_script_overrides(run_paths, config.get("overrides"))
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"overrides: {result['replacements']} replacements from {result['rules']} rules")
        print(f"script: {result['script']}")
        return 0

    if args.command == "assemble":
        run_paths = create_run(args.workspace, args.run_id)
        output = assemble_audio(run_paths)
        print(output)
        return 0

    if args.command == "synthesize":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["tts"])
        run_paths = create_run(args.workspace, args.run_id)
        output = synthesize_segments(run_paths, config["tts"])
        print(output)
        return 0

    if args.command == "adapt":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["llm"])
        run_paths = create_run(args.workspace, args.run_id)
        output = adapt_to_chinese(run_paths, config["llm"])
        print(output)
        return 0

    if args.command == "run":
        try:
            output = run_pipeline(
                args.workspace,
                args.run_id,
                args.source_config,
                args.local_config,
                args.from_stage,
                args.transcript_file,
                args.title,
                args.original_url,
            )
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        print(output)
        return 0

    if args.command == "check":
        run_paths = create_run(args.workspace, args.run_id)
        try:
            result = check_run_artifacts(
                run_paths,
                checks=tuple(args.checks),
                max_script_chars=args.max_script_chars,
            )
        except CheckError as error:
            print(str(error), file=sys.stderr)
            return 1
        for key, value in result.items():
            print(f"{key}={value}")
        return 0

    parser.print_help()
    return 0
