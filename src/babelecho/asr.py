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
    item = _require_mapping(segment, f"ASR segment {index}")
    for key in ["start_ms", "end_ms", "text"]:
        if key not in item:
            raise ValueError(f"ASR segment {index} missing required key: {key}")
    if not isinstance(item["start_ms"], int) or not isinstance(item["end_ms"], int):
        raise ValueError(f"ASR segment {index} start_ms and end_ms must be integers")
    if item["end_ms"] <= item["start_ms"]:
        raise ValueError(f"ASR segment {index} end_ms must be after start_ms")
    text = item["text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"ASR segment {index} text must be a non-empty string")

    normalized = {
        "id": str(item.get("id") or f"asr_{index:04d}"),
        "start_ms": item["start_ms"],
        "end_ms": item["end_ms"],
        "text": text,
    }
    if "confidence" in item:
        normalized["confidence"] = item["confidence"]
    return normalized


def run_fixture_asr(
    asr_config: dict[str, Any],
    run_paths: RunPaths,
    *,
    config_path: Path,
) -> Path:
    provider = asr_config.get("provider")
    if provider != "fixture":
        raise ValueError("audio ASR currently supports asr.provider=fixture")
    fixture_path = asr_config.get("fixture_path")
    if not fixture_path:
        raise ValueError("asr.fixture_path is required for fixture ASR")

    fixture = read_json(_resolve_fixture_path(str(fixture_path), config_path))
    fixture = _require_mapping(fixture, "ASR fixture")
    segments = fixture.get("segments")
    if not isinstance(segments, list):
        raise ValueError("ASR fixture segments must be a list")

    raw = {
        "provider": "fixture",
        "model": fixture.get("model") or "fixture",
        "language": fixture.get("language") or asr_config.get("language") or "en",
        "duration_seconds": fixture.get("duration_seconds"),
        "segments": [
            _normalize_segment(segment, index)
            for index, segment in enumerate(segments, start=1)
        ],
    }
    if "metadata" in fixture:
        raw["metadata"] = fixture["metadata"]

    asr_path = _asr_dir(run_paths) / "raw.json"
    write_json(asr_path, raw)
    return asr_path
