from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json
from .paths import RunPaths


ALLOWED_EMBEDDING_STATUS = {"not_computed", "fixture", "unavailable"}


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _resolve_fixture_path(fixture_path: str, config_path: Path) -> Path:
    source = Path(fixture_path)
    if source.is_absolute():
        return source
    return config_path.parent / source


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
    if provider != "fixture":
        raise ValueError("voice_profile.provider must be none or fixture")

    fixture = _load_fixture_config(config, config_path)
    profiles = _require_mapping(read_json(profiles_path), "speaker profiles")
    merged = _merge_fixture_profiles(profiles, fixture, run_paths)
    write_json(profiles_path, merged)
    return profiles_path
