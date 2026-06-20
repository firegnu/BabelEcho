from pathlib import Path
import shlex
import subprocess
from typing import Any

from .jsonio import read_json, write_json
from .paths import RunPaths


ALLOWED_EMBEDDING_STATUS = {"not_computed", "fixture", "unavailable", "computed"}


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _resolve_fixture_path(fixture_path: str, config_path: Path) -> Path:
    source = Path(fixture_path)
    if source.is_absolute():
        return source
    return config_path.parent / source


def _command_parts(command: Any) -> list[str]:
    if isinstance(command, str):
        parts = shlex.split(command)
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        parts = list(command)
    else:
        raise ValueError("voice_profile.command must be a string or list of strings")
    if not parts:
        raise ValueError("voice_profile.command must not be empty")
    return parts


def _extra_args(config: dict[str, Any]) -> list[str]:
    extra_args = config.get("extra_args") or []
    if not isinstance(extra_args, list) or not all(
        isinstance(item, str) for item in extra_args
    ):
        raise ValueError("voice_profile.extra_args must be a list of strings")
    return extra_args


def _optional_string(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    if value is None:
        return None
    value = str(value)
    return value if value else None


def _load_fixture_config(
    config: dict[str, Any],
    config_path: Path,
) -> dict[str, Any]:
    fixture_path = config.get("fixture_path")
    if not isinstance(fixture_path, str) or not fixture_path.strip():
        raise ValueError("voice_profile.fixture_path is required")
    fixture = _require_mapping(
        read_json(_resolve_fixture_path(fixture_path, config_path)),
        "voice profile fixture",
    )
    speakers = fixture.get("speakers")
    if not isinstance(speakers, list):
        raise ValueError("voice profile fixture speakers must be a list")
    return fixture


def _load_summary_config(path: Path) -> dict[str, Any]:
    summary = _require_mapping(read_json(path), "voice profile summary")
    speakers = summary.get("speakers")
    if not isinstance(speakers, list):
        raise ValueError("voice profile summary speakers must be a list")
    return summary


def _resolve_audio_input(run_paths: RunPaths) -> Path:
    source = _require_mapping(read_json(run_paths.source_json), "audio source")
    audio_input = source.get("audio_input")
    if not isinstance(audio_input, str) or not audio_input.strip():
        raise ValueError("source.audio_input is required before voice profile extraction")
    audio_path = run_paths.run_dir / audio_input
    if not audio_path.exists():
        raise ValueError(f"Voice profile audio input does not exist: {audio_path}")
    return audio_path


def _validate_embedding_artifact(value: Any, run_paths: RunPaths) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("voice_profile.embedding_artifact must be a relative path")
    artifact = Path(value)
    if artifact.is_absolute():
        raise ValueError("voice_profile.embedding_artifact must be run-local")
    target = (run_paths.run_dir / artifact).resolve()
    if not target.is_relative_to(run_paths.run_dir.resolve()):
        raise ValueError("voice_profile.embedding_artifact must be run-local")
    return value


def _fixture_speaker_metadata(
    item: Any,
    known_speakers: set[str],
    run_paths: RunPaths,
) -> tuple[str, dict[str, Any]]:
    speaker = _require_mapping(item, "voice profile fixture speaker")
    speaker_id = speaker.get("id")
    if not isinstance(speaker_id, str) or not speaker_id.strip():
        raise ValueError("voice profile fixture speaker id is required")
    if speaker_id not in known_speakers:
        raise ValueError(f"voice profile fixture references unknown speaker: {speaker_id}")

    metadata: dict[str, Any] = {}
    for key in ["sample_count", "sample_duration_ms"]:
        if key in speaker:
            value = speaker[key]
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"voice_profile.{key} must be a non-negative integer")
            metadata[key] = value

    status = speaker.get("embedding_status")
    if status is not None:
        if status not in ALLOWED_EMBEDDING_STATUS:
            raise ValueError("voice_profile.embedding_status is invalid")
        metadata["embedding_status"] = status

    profile_kind = speaker.get("profile_kind")
    if profile_kind is not None:
        if not isinstance(profile_kind, str) or not profile_kind.strip():
            raise ValueError("voice_profile.profile_kind must be a non-empty string")
        metadata["profile_kind"] = profile_kind

    if "embedding_artifact" in speaker:
        metadata["embedding_artifact"] = _validate_embedding_artifact(
            speaker.get("embedding_artifact"),
            run_paths,
        )

    return speaker_id, metadata


def _merge_fixture_profiles(
    profiles: dict[str, Any],
    fixture: dict[str, Any],
    run_paths: RunPaths,
) -> dict[str, Any]:
    speakers = profiles.get("speakers")
    if not isinstance(speakers, list):
        raise ValueError("speaker profiles speakers must be a list")
    known_speakers = {
        speaker.get("id")
        for speaker in speakers
        if isinstance(speaker, dict) and isinstance(speaker.get("id"), str)
    }
    metadata_by_id = dict(
        _fixture_speaker_metadata(item, known_speakers, run_paths)
        for item in fixture["speakers"]
    )
    for speaker in speakers:
        if not isinstance(speaker, dict):
            raise ValueError("speaker profile entries must be mappings")
        metadata = metadata_by_id.get(speaker.get("id"))
        if metadata:
            speaker.update(metadata)
    return profiles


def _run_local_cli_command(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, text=True, capture_output=True)
    except FileNotFoundError as error:
        raise ValueError(f"Voice profile local_cli command not found: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").strip()
        stdout = (error.stdout or "").strip()
        detail = stderr or stdout or "no output"
        raise RuntimeError(
            "Voice profile local_cli command failed with exit code "
            f"{error.returncode}: {detail}"
        ) from error


def run_local_cli_voice_profile(
    voice_profile_config: dict[str, Any],
    run_paths: RunPaths,
    *,
    config_path: Path,
) -> Path:
    del config_path
    command_value = voice_profile_config.get("command")
    if not command_value:
        raise ValueError("voice_profile.command is required for local_cli voice profile")
    command = _command_parts(command_value)
    extra_args = _extra_args(voice_profile_config)
    audio_path = _resolve_audio_input(run_paths)
    diarization_path = run_paths.run_dir / "asr" / "diarization.json"
    profiles_path = run_paths.run_dir / "asr" / "speaker-profiles.json"
    if not diarization_path.exists():
        raise ValueError("asr/diarization.json is required before voice profile extraction")
    if not profiles_path.exists():
        raise ValueError("asr/speaker-profiles.json is required before voice profile extraction")

    output_dir = run_paths.run_dir / "asr" / "voice-profiles"
    summary_path = output_dir / "summary.json"
    command.extend(
        [
            "--audio-file",
            str(audio_path),
            "--diarization-json",
            str(diarization_path),
            "--speaker-profiles-json",
            str(profiles_path),
            "--output-dir",
            str(output_dir),
            "--output-json",
            str(summary_path),
        ]
    )
    for key, argument in [
        ("model", "--model"),
        ("device", "--device"),
        ("min_sample_ms", "--min-sample-ms"),
        ("max_samples_per_speaker", "--max-samples-per-speaker"),
    ]:
        value = _optional_string(voice_profile_config, key)
        if value:
            command.extend([argument, value])
    command.extend(extra_args)

    _run_local_cli_command(command)
    if not summary_path.exists():
        raise ValueError(f"Voice profile local_cli command did not write output: {summary_path}")

    profiles = _require_mapping(read_json(profiles_path), "speaker profiles")
    merged = _merge_fixture_profiles(
        profiles,
        _load_summary_config(summary_path),
        run_paths,
    )
    write_json(profiles_path, merged)
    return profiles_path


def apply_voice_profile_config(
    voice_profile_config: dict[str, Any] | None,
    run_paths: RunPaths,
    *,
    config_path: Path,
) -> Path:
    profiles_path = run_paths.run_dir / "asr" / "speaker-profiles.json"
    config = (
        _require_mapping(voice_profile_config, "voice_profile")
        if voice_profile_config is not None
        else {"provider": "none"}
    )
    provider = config.get("provider") or "none"
    if provider == "none":
        return profiles_path
    if provider == "local_cli":
        return run_local_cli_voice_profile(config, run_paths, config_path=config_path)
    if provider != "fixture":
        raise ValueError("voice_profile.provider must be none, fixture, or local_cli")

    fixture = _load_fixture_config(config, config_path)
    profiles = _require_mapping(read_json(profiles_path), "speaker profiles")
    merged = _merge_fixture_profiles(profiles, fixture, run_paths)
    write_json(profiles_path, merged)
    return profiles_path
