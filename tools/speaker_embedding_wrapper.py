#!/usr/bin/env python3
import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract speaker embeddings and write BabelEcho voice profile JSON."
    )
    parser.add_argument("--audio-file", required=True)
    parser.add_argument("--diarization-json", required=True)
    parser.add_argument("--speaker-profiles-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--min-sample-ms", type=int, default=1500)
    parser.add_argument("--max-samples-per-speaker", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    parse_args(argv)
    raise SystemExit(
        "speaker_embedding_wrapper.py is a contract stub; "
        "run a model-specific wrapper after the 5090D model probe."
    )


if __name__ == "__main__":
    raise SystemExit(main())
