import shlex
import subprocess
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


def _normalize_diarization(
    diarization: Any,
    *,
    default_provider: str,
    default_model: str | None,
) -> dict[str, Any]:
    item = _require_mapping(diarization, "Diarization output")
    segments = item.get("segments")
    if not isinstance(segments, list):
        raise ValueError("Diarization output segments must be a list")
    normalized_segments = [
        _normalize_segment(segment, index)
        for index, segment in enumerate(segments, start=1)
    ]
    speakers = {segment["speaker"] for segment in normalized_segments}
    output = {
        "provider": str(item.get("provider") or default_provider),
        "model": item.get("model") if item.get("model") is not None else default_model,
        "speaker_count": item.get("speaker_count") or len(speakers) or 1,
        "segments": normalized_segments,
    }
    if "warnings" in item:
        output["warnings"] = item["warnings"]
    if "metadata" in item:
        output["metadata"] = item["metadata"]
    return output


def _disabled_diarization() -> dict[str, Any]:
    return {
        "provider": "none",
        "model": None,
        "speaker_count": 1,
        "segments": [],
        "warnings": ["diarization_disabled"],
    }


def _speaker_profiles(diarization: dict[str, Any]) -> dict[str, Any]:
    speakers: dict[str, dict[str, Any]] = {}
    ordered_speakers: list[str] = []
    for turn in diarization.get("segments") or []:
        speaker = str(turn["speaker"])
        if speaker not in speakers:
            ordered_speakers.append(speaker)
            speakers[speaker] = {
                "id": speaker,
                "label": speaker,
                "turn_count": 0,
                "total_ms": 0,
                "first_start_ms": None,
                "last_end_ms": None,
                "profile_kind": "diarization_stats",
                "embedding_status": "not_computed",
            }
        profile = speakers[speaker]
        start_ms = int(turn["start_ms"])
        end_ms = int(turn["end_ms"])
        profile["turn_count"] += 1
        profile["total_ms"] += end_ms - start_ms
        if profile["first_start_ms"] is None or start_ms < profile["first_start_ms"]:
            profile["first_start_ms"] = start_ms
        if profile["last_end_ms"] is None or end_ms > profile["last_end_ms"]:
            profile["last_end_ms"] = end_ms

    speaker_count = int(diarization.get("speaker_count") or len(speakers) or 1)
    if not ordered_speakers:
        for index in range(1, speaker_count + 1):
            speaker = f"speaker_{index}"
            ordered_speakers.append(speaker)
            speakers[speaker] = {
                "id": speaker,
                "label": speaker,
                "turn_count": 0,
                "total_ms": 0,
                "first_start_ms": None,
                "last_end_ms": None,
                "profile_kind": "diarization_stats",
                "embedding_status": "not_computed",
            }

    profiles = []
    for speaker in ordered_speakers:
        profile = speakers[speaker]
        turn_count = int(profile["turn_count"])
        profile["avg_turn_ms"] = (
            round(int(profile["total_ms"]) / turn_count, 1)
            if turn_count
            else None
        )
        profiles.append(profile)

    return {
        "schema_version": "1.0",
        "provider": "diarization_stats",
        "source": "diarization",
        "diarization_provider": diarization.get("provider"),
        "diarization_model": diarization.get("model"),
        "speaker_count": speaker_count,
        "speakers": profiles,
    }


def _resolve_audio_input(run_paths: RunPaths) -> Path:
    source = _require_mapping(read_json(run_paths.source_json), "audio source")
    audio_input = source.get("audio_input")
    if not isinstance(audio_input, str) or not audio_input.strip():
        raise ValueError("source.audio_input is required before diarization")
    audio_path = run_paths.run_dir / audio_input
    if not audio_path.exists():
        raise ValueError(f"Diarization audio input does not exist: {audio_path}")
    return audio_path


def _command_parts(command: Any) -> list[str]:
    if isinstance(command, str):
        parts = shlex.split(command)
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        parts = list(command)
    else:
        raise ValueError("diarization.command must be a string or list of strings")
    if not parts:
        raise ValueError("diarization.command must not be empty")
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
        raise ValueError(f"Diarization local_cli command not found: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").strip()
        stdout = (error.stdout or "").strip()
        detail = stderr or stdout or "no output"
        raise RuntimeError(
            "Diarization local_cli command failed with exit code "
            f"{error.returncode}: {detail}"
        ) from error


def _run_local_cli_diarization(
    diarization_config: dict[str, Any],
    run_paths: RunPaths,
) -> dict[str, Any]:
    command_value = diarization_config.get("command")
    if not command_value:
        raise ValueError("diarization.command is required for local_cli diarization")

    audio_path = _resolve_audio_input(run_paths)
    diarization_path = _asr_dir(run_paths) / "diarization.json"
    command = _command_parts(command_value)
    command.extend(["--audio-file", str(audio_path), "--output-json", str(diarization_path)])
    for key, argument in [
        ("model", "--model"),
        ("min_speakers", "--min-speakers"),
        ("max_speakers", "--max-speakers"),
    ]:
        value = _optional_string(diarization_config, key)
        if value:
            command.extend([argument, value])
    extra_args = diarization_config.get("extra_args") or []
    if not isinstance(extra_args, list) or not all(isinstance(item, str) for item in extra_args):
        raise ValueError("diarization.extra_args must be a list of strings")
    command.extend(extra_args)

    _run_local_cli_command(command)
    if not diarization_path.exists():
        raise ValueError(
            f"Diarization local_cli command did not write output: {diarization_path}"
        )
    return _normalize_diarization(
        read_json(diarization_path),
        default_provider="local_cli",
        default_model=_optional_string(diarization_config, "model"),
    )


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
        diarization = _normalize_diarization(
            fixture,
            default_provider="fixture",
            default_model="fixture",
        )
    elif provider == "local_cli":
        diarization = _run_local_cli_diarization(diarization_config, run_paths)
    else:
        raise ValueError(
            "audio diarization supports diarization.provider=fixture, none, or local_cli"
        )

    diarization_path = _asr_dir(run_paths) / "diarization.json"
    write_json(diarization_path, diarization)
    write_json(_asr_dir(run_paths) / "speaker-profiles.json", _speaker_profiles(diarization))
    return diarization_path
