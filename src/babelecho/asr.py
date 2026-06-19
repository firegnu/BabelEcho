from pathlib import Path
import shlex
import subprocess
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


def _normalize_raw_asr(
    raw: Any,
    *,
    default_provider: str,
    default_model: str,
    default_language: str,
) -> dict[str, Any]:
    item = _require_mapping(raw, "ASR raw output")
    segments = item.get("segments")
    if not isinstance(segments, list):
        raise ValueError("ASR raw output segments must be a list")

    normalized = {
        "provider": str(item.get("provider") or default_provider),
        "model": str(item.get("model") or default_model),
        "language": str(item.get("language") or default_language),
        "duration_seconds": item.get("duration_seconds"),
        "segments": [
            _normalize_segment(segment, index)
            for index, segment in enumerate(segments, start=1)
        ],
    }
    if "metadata" in item:
        normalized["metadata"] = item["metadata"]
    return normalized


def _resolve_audio_input(run_paths: RunPaths) -> Path:
    source = _require_mapping(read_json(run_paths.source_json), "audio source")
    audio_input = source.get("audio_input")
    if not isinstance(audio_input, str) or not audio_input.strip():
        raise ValueError("source.audio_input is required before ASR")
    audio_path = run_paths.run_dir / audio_input
    if not audio_path.exists():
        raise ValueError(f"ASR audio input does not exist: {audio_path}")
    return audio_path


def _command_parts(command: Any) -> list[str]:
    if isinstance(command, str):
        parts = shlex.split(command)
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        parts = list(command)
    else:
        raise ValueError("asr.command must be a string or list of strings")
    if not parts:
        raise ValueError("asr.command must not be empty")
    return parts


def _optional_string(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    if value is None:
        return None
    value = str(value)
    return value if value else None


def _run_local_cli_command(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, text=True, capture_output=True)
    except FileNotFoundError as error:
        raise ValueError(f"ASR local_cli command not found: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").strip()
        stdout = (error.stdout or "").strip()
        detail = stderr or stdout or "no output"
        raise RuntimeError(
            f"ASR local_cli command failed with exit code {error.returncode}: {detail}"
        ) from error


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

    raw = _normalize_raw_asr(
        fixture,
        default_provider="fixture",
        default_model="fixture",
        default_language=str(asr_config.get("language") or "en"),
    )

    asr_path = _asr_dir(run_paths) / "raw.json"
    write_json(asr_path, raw)
    return asr_path


def run_local_cli_asr(
    asr_config: dict[str, Any],
    run_paths: RunPaths,
    *,
    config_path: Path,
) -> Path:
    command_value = asr_config.get("command")
    if not command_value:
        raise ValueError("asr.command is required for local_cli ASR")

    audio_path = _resolve_audio_input(run_paths)
    asr_path = _asr_dir(run_paths) / "raw.json"
    command = _command_parts(command_value)
    command.extend(["--audio-file", str(audio_path), "--output-json", str(asr_path)])
    for key in ["model", "language", "device"]:
        value = _optional_string(asr_config, key)
        if value:
            command.extend([f"--{key}", value])
    extra_args = asr_config.get("extra_args") or []
    if not isinstance(extra_args, list) or not all(isinstance(item, str) for item in extra_args):
        raise ValueError("asr.extra_args must be a list of strings")
    command.extend(extra_args)

    _run_local_cli_command(command)
    if not asr_path.exists():
        raise ValueError(f"ASR local_cli command did not write output: {asr_path}")

    raw = _normalize_raw_asr(
        read_json(asr_path),
        default_provider="local_cli",
        default_model=str(asr_config.get("model") or "local_cli"),
        default_language=str(asr_config.get("language") or "en"),
    )
    write_json(asr_path, raw)
    return asr_path


def run_asr(
    asr_config: dict[str, Any],
    run_paths: RunPaths,
    *,
    config_path: Path,
) -> Path:
    provider = asr_config.get("provider")
    if provider == "fixture":
        return run_fixture_asr(asr_config, run_paths, config_path=config_path)
    if provider == "local_cli":
        return run_local_cli_asr(asr_config, run_paths, config_path=config_path)
    raise ValueError("audio ASR supports asr.provider=fixture or local_cli")
