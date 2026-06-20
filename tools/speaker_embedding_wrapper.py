#!/usr/bin/env python3
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
from typing import Any


PROVIDER = "speechbrain_ecapa"
TARGET_SAMPLE_RATE = 16000


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def select_sample_windows(
    diarization: dict[str, Any],
    *,
    min_sample_ms: int,
    max_samples_per_speaker: int,
) -> dict[str, list[dict[str, int]]]:
    segments = diarization.get("segments") or []
    if not isinstance(segments, list):
        raise ValueError("diarization.segments must be a list")

    by_speaker: dict[str, list[tuple[int, int, dict[str, int]]]] = defaultdict(list)
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("diarization segment must be an object")
        speaker = segment.get("speaker")
        start_ms = segment.get("start_ms")
        end_ms = segment.get("end_ms")
        if not isinstance(speaker, str) or not speaker:
            raise ValueError("diarization segment speaker must be a non-empty string")
        if not isinstance(start_ms, int) or not isinstance(end_ms, int):
            raise ValueError("diarization segment start_ms and end_ms must be integers")
        duration_ms = end_ms - start_ms
        if duration_ms < min_sample_ms:
            continue
        by_speaker[speaker].append(
            (duration_ms, start_ms, {"start_ms": start_ms, "end_ms": end_ms})
        )

    selected = {}
    for speaker, windows in sorted(by_speaker.items()):
        ordered = sorted(windows, key=lambda item: (-item[0], item[1]))
        selected[speaker] = [
            window for _, _, window in ordered[:max_samples_per_speaker]
        ]
    return selected


def _embedding_artifact_path(output_dir: Path, speaker_id: str) -> tuple[Path, str]:
    artifact_path = output_dir / f"{speaker_id}.json"
    run_dir = output_dir.parent.parent
    return artifact_path, artifact_path.relative_to(run_dir).as_posix()


def _sample_duration_ms(windows: list[dict[str, int]]) -> int:
    return sum(window["end_ms"] - window["start_ms"] for window in windows)


def write_voice_profile_outputs(
    *,
    output_dir: Path,
    output_json: Path,
    provider: str,
    model: str,
    embeddings: dict[str, list[float]],
    sample_windows: dict[str, list[dict[str, int]]],
    embedding_dimension: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    speakers = []
    for speaker_id in sorted(sample_windows):
        windows = sample_windows[speaker_id]
        embedding = embeddings.get(speaker_id)
        embedding_artifact = None
        embedding_status = "unavailable"
        if embedding and windows:
            artifact_path, embedding_artifact = _embedding_artifact_path(
                output_dir,
                speaker_id,
            )
            _write_json(
                artifact_path,
                {
                    "schema_version": "1.0",
                    "speaker_id": speaker_id,
                    "provider": provider,
                    "model": model,
                    "embedding_format": "float32",
                    "embedding": embedding,
                    "sample_windows": windows,
                },
            )
            embedding_status = "computed"
        speakers.append(
            {
                "id": speaker_id,
                "sample_count": len(windows) if embedding_status == "computed" else 0,
                "sample_duration_ms": (
                    _sample_duration_ms(windows)
                    if embedding_status == "computed"
                    else 0
                ),
                "profile_kind": "speaker_embedding",
                "embedding_status": embedding_status,
                "embedding_artifact": embedding_artifact,
            }
        )

    _write_json(
        output_json,
        {
            "provider": provider,
            "model": model,
            "speakers": speakers,
            "metadata": {
                "wrapper": "tools/speaker_embedding_wrapper.py",
                "embedding_dimension": embedding_dimension,
                "target_sample_rate": TARGET_SAMPLE_RATE,
            },
        },
    )


def _speechbrain_model_cache(model: str) -> str:
    cache_root = Path(
        os.environ.get(
            "SPEECHBRAIN_MODEL_CACHE",
            Path.home() / ".cache" / "babelecho" / "speechbrain",
        )
    )
    return str(cache_root / model.replace("/", "__"))


def extract_speechbrain_embeddings(
    *,
    audio_file: Path,
    model: str,
    device: str,
    sample_windows: dict[str, list[dict[str, int]]],
) -> tuple[dict[str, list[float]], int]:
    try:
        import torch
        import torchaudio
        from speechbrain.inference.speaker import EncoderClassifier
    except ImportError as error:
        raise SystemExit(
            "SpeechBrain voice profile dependencies are missing. "
            "Install speechbrain in the ignored runtime environment."
        ) from error

    selected_device = device
    if device == "cuda" and not torch.cuda.is_available():
        selected_device = "cpu"
    classifier = EncoderClassifier.from_hparams(
        source=model,
        savedir=_speechbrain_model_cache(model),
        run_opts={"device": selected_device},
    )
    waveform, sample_rate = torchaudio.load(str(audio_file))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != TARGET_SAMPLE_RATE:
        waveform = torchaudio.transforms.Resample(
            sample_rate,
            TARGET_SAMPLE_RATE,
        )(waveform)
        sample_rate = TARGET_SAMPLE_RATE
    waveform = waveform.to(selected_device)

    embeddings = {}
    embedding_dimension = 0
    with torch.no_grad():
        for speaker_id, windows in sample_windows.items():
            vectors = []
            for window in windows:
                start = int(round(window["start_ms"] * sample_rate / 1000.0))
                end = int(round(window["end_ms"] * sample_rate / 1000.0))
                crop = waveform[:, start:end]
                if crop.numel() == 0:
                    continue
                vector = classifier.encode_batch(crop).detach().cpu().reshape(-1)
                vectors.append(vector)
            if not vectors:
                continue
            speaker_embedding = torch.stack(vectors).mean(dim=0).to(dtype=torch.float32)
            embedding_dimension = int(speaker_embedding.numel())
            embeddings[speaker_id] = [float(value) for value in speaker_embedding.tolist()]
    return embeddings, embedding_dimension


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
    args = parse_args(argv)
    diarization = _read_json(Path(args.diarization_json))
    sample_windows = select_sample_windows(
        diarization,
        min_sample_ms=args.min_sample_ms,
        max_samples_per_speaker=args.max_samples_per_speaker,
    )
    embeddings, embedding_dimension = extract_speechbrain_embeddings(
        audio_file=Path(args.audio_file),
        model=args.model,
        device=args.device,
        sample_windows=sample_windows,
    )
    write_voice_profile_outputs(
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        provider=PROVIDER,
        model=args.model,
        embeddings=embeddings,
        sample_windows=sample_windows,
        embedding_dimension=embedding_dimension,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
