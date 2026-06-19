#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local OpenAI Whisper and write BabelEcho ASR raw JSON."
    )
    parser.add_argument("--audio-file", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--model", default="tiny.en")
    parser.add_argument("--language", default="en")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--task", choices=["transcribe", "translate"], default="transcribe")
    parser.add_argument("--fp16", default=None)
    return parser.parse_args(argv)


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _segment_to_raw(segment: dict[str, Any], index: int) -> dict[str, Any] | None:
    text = str(segment.get("text") or "").strip()
    if not text:
        return None
    return {
        "id": f"asr_{index:04d}",
        "start_ms": int(round(float(segment["start"]) * 1000)),
        "end_ms": int(round(float(segment["end"]) * 1000)),
        "text": text,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        raise ValueError(f"Audio file does not exist: {audio_path}")

    import whisper

    model = whisper.load_model(args.model, device=args.device)
    transcribe_kwargs: dict[str, Any] = {
        "language": args.language,
        "task": args.task,
        "verbose": False,
    }
    fp16 = _parse_bool(args.fp16)
    if fp16 is not None:
        transcribe_kwargs["fp16"] = fp16
    result = model.transcribe(str(audio_path), **transcribe_kwargs)

    segments: list[dict[str, Any]] = []
    for source_segment in result.get("segments") or []:
        segment = _segment_to_raw(source_segment, len(segments) + 1)
        if segment is not None:
            segments.append(segment)

    duration_seconds = None
    if segments:
        duration_seconds = segments[-1]["end_ms"] / 1000

    output = {
        "provider": "openai_whisper",
        "model": args.model,
        "language": result.get("language") or args.language,
        "duration_seconds": duration_seconds,
        "segments": segments,
        "metadata": {
            "task": args.task,
            "device": args.device,
            "wrapper": "tools/openai_whisper_asr_wrapper.py",
        },
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
