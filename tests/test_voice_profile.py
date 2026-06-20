from pathlib import Path

import pytest

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.voice_profile import apply_voice_profile_config


def _write_profiles(run_paths):
    write_json(
        run_paths.run_dir / "asr" / "speaker-profiles.json",
        {
            "schema_version": "1.0",
            "provider": "diarization_stats",
            "source": "diarization",
            "diarization_provider": "fixture",
            "diarization_model": "fixture",
            "speaker_count": 2,
            "speakers": [
                {
                    "id": "speaker_1",
                    "label": "speaker_1",
                    "turn_count": 1,
                    "total_ms": 4200,
                    "first_start_ms": 0,
                    "last_end_ms": 4200,
                    "avg_turn_ms": 4200.0,
                    "sample_count": 0,
                    "sample_duration_ms": 0,
                    "profile_kind": "diarization_stats",
                    "embedding_status": "not_computed",
                    "embedding_artifact": None,
                },
                {
                    "id": "speaker_2",
                    "label": "speaker_2",
                    "turn_count": 1,
                    "total_ms": 4900,
                    "first_start_ms": 4300,
                    "last_end_ms": 9200,
                    "avg_turn_ms": 4900.0,
                    "sample_count": 0,
                    "sample_duration_ms": 0,
                    "profile_kind": "diarization_stats",
                    "embedding_status": "not_computed",
                    "embedding_artifact": None,
                },
            ],
        },
    )


def test_fixture_voice_profile_merges_known_speaker_metadata(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-fixture")
    _write_profiles(run_paths)
    fixture = tmp_path / "voice-profile-fixture.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "speakers": [
                {
                    "id": "speaker_1",
                    "sample_count": 2,
                    "sample_duration_ms": 12000,
                    "embedding_status": "fixture",
                    "profile_kind": "voice_profile_fixture",
                    "embedding_artifact": "asr/voice-profiles/speaker_1.json",
                }
            ],
        },
    )

    profiles_path = apply_voice_profile_config(
        {"provider": "fixture", "fixture_path": str(fixture)},
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    assert profiles_path == run_paths.run_dir / "asr" / "speaker-profiles.json"
    profiles = read_json(profiles_path)
    speaker_1, speaker_2 = profiles["speakers"]
    assert speaker_1["sample_count"] == 2
    assert speaker_1["sample_duration_ms"] == 12000
    assert speaker_1["embedding_status"] == "fixture"
    assert speaker_1["profile_kind"] == "voice_profile_fixture"
    assert speaker_1["embedding_artifact"] == "asr/voice-profiles/speaker_1.json"
    assert speaker_2["embedding_status"] == "not_computed"


def test_none_voice_profile_preserves_existing_profiles(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-none")
    _write_profiles(run_paths)
    before = read_json(run_paths.run_dir / "asr" / "speaker-profiles.json")

    profiles_path = apply_voice_profile_config(
        {"provider": "none"},
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    assert profiles_path == run_paths.run_dir / "asr" / "speaker-profiles.json"
    assert read_json(profiles_path) == before


def test_voice_profile_rejects_unknown_provider(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-unknown")
    _write_profiles(run_paths)

    with pytest.raises(ValueError, match="voice_profile.provider"):
        apply_voice_profile_config(
            {"provider": "unknown"},
            run_paths,
            config_path=tmp_path / "local-audio.yaml",
        )


def test_voice_profile_rejects_non_mapping_config(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-non-mapping")
    _write_profiles(run_paths)

    with pytest.raises(ValueError, match="voice_profile must be a mapping"):
        apply_voice_profile_config(
            "fixture",
            run_paths,
            config_path=tmp_path / "local-audio.yaml",
        )


def test_fixture_voice_profile_requires_fixture_path(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-missing-fixture")
    _write_profiles(run_paths)

    with pytest.raises(ValueError, match="voice_profile.fixture_path is required"):
        apply_voice_profile_config(
            {"provider": "fixture"},
            run_paths,
            config_path=tmp_path / "local-audio.yaml",
        )


def test_fixture_voice_profile_allows_not_computed_status(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-not-computed")
    _write_profiles(run_paths)
    fixture = tmp_path / "voice-profile-fixture.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "speakers": [
                {
                    "id": "speaker_1",
                    "embedding_status": "not_computed",
                }
            ],
        },
    )

    apply_voice_profile_config(
        {"provider": "fixture", "fixture_path": str(fixture)},
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    profiles = read_json(run_paths.run_dir / "asr" / "speaker-profiles.json")
    assert profiles["speakers"][0]["embedding_status"] == "not_computed"


def test_fixture_voice_profile_rejects_unknown_speaker(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-unknown-speaker")
    _write_profiles(run_paths)
    fixture = tmp_path / "voice-profile-fixture.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "speakers": [
                {
                    "id": "speaker_3",
                    "embedding_status": "fixture",
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="unknown speaker"):
        apply_voice_profile_config(
            {"provider": "fixture", "fixture_path": str(fixture)},
            run_paths,
            config_path=tmp_path / "local-audio.yaml",
        )


def test_fixture_voice_profile_rejects_embedding_artifact_outside_run(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-bad-artifact")
    _write_profiles(run_paths)
    fixture = tmp_path / "voice-profile-fixture.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "speakers": [
                {
                    "id": "speaker_1",
                    "embedding_status": "fixture",
                    "embedding_artifact": "../speaker_1.json",
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="embedding_artifact"):
        apply_voice_profile_config(
            {"provider": "fixture", "fixture_path": str(fixture)},
            run_paths,
            config_path=tmp_path / "local-audio.yaml",
        )
