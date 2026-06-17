import argparse
from pathlib import Path

from .adapt import adapt_to_chinese
from .audio import assemble_audio
from .config import load_yaml, require_keys
from .ingest import ingest_transcript_source
from .jsonio import read_json
from .paths import create_run
from .publish import publish_episode
from .synthesize import synthesize_segments
from .transcript import normalize_transcript

PIPELINE_STAGES = ("ingest", "normalize", "adapt", "synthesize", "assemble", "publish")


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

    run = subparsers.add_parser("run", help="Run the transcript-to-podcast pipeline.")
    run.add_argument("--workspace", required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--source-config", required=True)
    run.add_argument("--local-config", required=True)
    run.add_argument(
        "--from-stage",
        choices=PIPELINE_STAGES,
        default="ingest",
        help="Resume from this stage.",
    )

    return parser


def _raw_transcript_path(run_paths) -> Path:
    source = read_json(run_paths.source_json)
    raw_transcript = source.get("raw_transcript")
    if not raw_transcript:
        raise ValueError(f"Missing raw_transcript in {run_paths.source_json}")
    return run_paths.run_dir / raw_transcript


def run_pipeline(
    workspace: str,
    run_id: str,
    source_config_path: str,
    local_config_path: str,
    from_stage: str,
) -> str:
    source_config = load_yaml(Path(source_config_path))
    local_config = load_yaml(Path(local_config_path))
    require_keys(source_config, ["source"])
    require_keys(local_config, ["llm", "tts", "publish"])

    run_paths = create_run(workspace, run_id)
    stage_index = PIPELINE_STAGES.index(from_stage)
    raw_path: Path | None = None
    outputs: list[str] = []

    if stage_index <= PIPELINE_STAGES.index("ingest"):
        raw_path = ingest_transcript_source(source_config["source"], run_paths)
        outputs.append(f"ingest: {raw_path}")

    if stage_index <= PIPELINE_STAGES.index("normalize"):
        if raw_path is None:
            raw_path = _raw_transcript_path(run_paths)
        normalized_path = normalize_transcript(run_paths, raw_path)
        outputs.append(f"normalize: {normalized_path}")

    if stage_index <= PIPELINE_STAGES.index("adapt"):
        script_path = adapt_to_chinese(run_paths, local_config["llm"])
        outputs.append(f"adapt: {script_path}")

    if stage_index <= PIPELINE_STAGES.index("synthesize"):
        manifest_path = synthesize_segments(run_paths, local_config["tts"])
        outputs.append(f"synthesize: {manifest_path}")

    if stage_index <= PIPELINE_STAGES.index("assemble"):
        audio_path = assemble_audio(run_paths)
        outputs.append(f"assemble: {audio_path}")

    if stage_index <= PIPELINE_STAGES.index("publish"):
        feed_path = publish_episode(run_paths, local_config["publish"])
        outputs.append(f"publish: {feed_path}")

    outputs.append(f"audio: {run_paths.output_audio}")
    outputs.append(f"feed: {run_paths.publish_dir / 'feed.xml'}")
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
        output = run_pipeline(
            args.workspace,
            args.run_id,
            args.source_config,
            args.local_config,
            args.from_stage,
        )
        print(output)
        return 0

    parser.print_help()
    return 0
