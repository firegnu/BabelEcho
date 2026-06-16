import argparse
from pathlib import Path

from .config import load_yaml, require_keys
from .ingest import ingest_transcript_source
from .paths import create_run
from .transcript import normalize_transcript


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

    return parser


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

    parser.print_help()
    return 0
