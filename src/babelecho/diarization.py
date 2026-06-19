from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json
from .paths import RunPaths


def _asr_dir(run_paths: RunPaths) -> Path:
    return run_paths.run_dir / "asr"


def _resolve_fixture_path(fixture_path: str, config_path: Path) -> Path:
    source = Path(fixture_path)
    if source.is_absolute():
        return source
    return config_path.parent / source


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _normalize_segment(segment: Any, index: int) -> dict[str, Any]:
    item = _require_mapping(segment, f"Diarization segment {index}")
    for key in ["start_ms", "end_ms", "speaker"]:
        if key not in item:
            raise ValueError(f"Diarization segment {index} missing required key: {key}")
    if not isinstance(item["start_ms"], int) or not isinstance(item["end_ms"], int):
        raise ValueError(
            f"Diarization segment {index} start_ms and end_ms must be integers"
        )
    if item["end_ms"] <= item["start_ms"]:
        raise ValueError(f"Diarization segment {index} end_ms must be after start_ms")
    speaker = item["speaker"]
    if not isinstance(speaker, str) or not speaker.strip():
        raise ValueError(f"Diarization segment {index} speaker must be a non-empty string")

    normalized = {
        "start_ms": item["start_ms"],
        "end_ms": item["end_ms"],
        "speaker": speaker,
    }
    if "confidence" in item:
        normalized["confidence"] = item["confidence"]
    return normalized


def _disabled_diarization() -> dict[str, Any]:
    return {
        "provider": "none",
        "model": None,
        "speaker_count": 1,
        "segments": [],
        "warnings": ["diarization_disabled"],
    }


def run_diarization(
    diarization_config: dict[str, Any],
    run_paths: RunPaths,
    *,
    config_path: Path,
) -> Path:
    provider = diarization_config.get("provider")
    if provider == "none":
        diarization = _disabled_diarization()
    elif provider == "fixture":
        fixture_path = diarization_config.get("fixture_path")
        if not fixture_path:
            raise ValueError("diarization.fixture_path is required for fixture diarization")
        fixture = read_json(_resolve_fixture_path(str(fixture_path), config_path))
        fixture = _require_mapping(fixture, "Diarization fixture")
        segments = fixture.get("segments")
        if not isinstance(segments, list):
            raise ValueError("Diarization fixture segments must be a list")
        normalized_segments = [
            _normalize_segment(segment, index)
            for index, segment in enumerate(segments, start=1)
        ]
        speakers = {segment["speaker"] for segment in normalized_segments}
        diarization = {
            "provider": "fixture",
            "model": fixture.get("model") or "fixture",
            "speaker_count": fixture.get("speaker_count") or len(speakers),
            "segments": normalized_segments,
        }
        if "metadata" in fixture:
            diarization["metadata"] = fixture["metadata"]
    else:
        raise ValueError(
            "audio diarization currently supports diarization.provider=fixture or none"
        )

    diarization_path = _asr_dir(run_paths) / "diarization.json"
    write_json(diarization_path, diarization)
    return diarization_path
