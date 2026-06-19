#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "pyannote/speaker-diarization-community-1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local pyannote speaker diarization and write BabelEcho JSON."
    )
    parser.add_argument("--audio-file", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--hf-token-env", default="HF_TOKEN")
    parser.add_argument("--num-speakers", type=int)
    parser.add_argument("--min-speakers", type=int)
    parser.add_argument("--max-speakers", type=int)
    return parser.parse_args(argv)


def _load_pipeline(model: str, token: str | None):
    from pyannote.audio import Pipeline

    if token:
        return Pipeline.from_pretrained(model, token=token)
    return Pipeline.from_pretrained(model)


def _move_to_device(pipeline, device: str):
    if not device:
        return pipeline
    import torch

    pipeline.to(torch.device(device))
    return pipeline


def _speaker_name(raw_speaker: str, mapping: dict[str, str]) -> str:
    if raw_speaker not in mapping:
        mapping[raw_speaker] = f"speaker_{len(mapping) + 1}"
    return mapping[raw_speaker]


def _iter_turns(diarization: Any):
    if hasattr(diarization, "itertracks"):
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            yield turn, speaker
        return
    for item in diarization:
        if len(item) == 2:
            turn, speaker = item
            yield turn, speaker
        elif len(item) == 3:
            turn, _, speaker = item
            yield turn, speaker


def _select_diarization(output: Any):
    exclusive = getattr(output, "exclusive_speaker_diarization", None)
    if exclusive is not None:
        return exclusive, "exclusive_speaker_diarization"
    speaker_diarization = getattr(output, "speaker_diarization", None)
    if speaker_diarization is not None:
        return speaker_diarization, "speaker_diarization"
    return output, "annotation"


def _pipeline_kwargs(args: argparse.Namespace) -> dict[str, int]:
    values = {
        "num_speakers": args.num_speakers,
        "min_speakers": args.min_speakers,
        "max_speakers": args.max_speakers,
    }
    return {key: value for key, value in values.items() if value is not None}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        raise ValueError(f"Audio file does not exist: {audio_path}")

    token = os.environ.get(args.hf_token_env) if args.hf_token_env else None
    pipeline = _load_pipeline(args.model, token)
    pipeline = _move_to_device(pipeline, args.device)
    output = pipeline(str(audio_path), **_pipeline_kwargs(args))
    diarization, diarization_kind = _select_diarization(output)

    speaker_mapping: dict[str, str] = {}
    segments = []
    for turn, raw_speaker in _iter_turns(diarization):
        start_ms = int(round(float(turn.start) * 1000))
        end_ms = int(round(float(turn.end) * 1000))
        if end_ms <= start_ms:
            continue
        segments.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "speaker": _speaker_name(str(raw_speaker), speaker_mapping),
            }
        )

    result = {
        "provider": "pyannote",
        "model": args.model,
        "speaker_count": len(set(segment["speaker"] for segment in segments)) or 1,
        "segments": segments,
        "metadata": {
            "diarization_kind": diarization_kind,
            "device": args.device,
            "wrapper": "tools/pyannote_diarization_wrapper.py",
            "raw_speaker_mapping": speaker_mapping,
        },
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
