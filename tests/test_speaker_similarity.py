import os
import subprocess
import sys
from pathlib import Path

import pytest

from babelecho.jsonio import read_json, write_json
from babelecho.speaker_similarity import compare_speaker_profiles


def _worktree_python_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def _write_run(
    run_dir: Path,
    speakers: list[dict],
    embeddings: dict[str, list[float]],
) -> None:
    profile_speakers = []
    voice_profile_dir = run_dir / "asr" / "voice-profiles"
    for speaker in speakers:
        speaker_id = speaker["id"]
        embedding = embeddings.get(speaker_id)
        artifact = None
        embedding_status = speaker.get("embedding_status", "not_computed")
        if embedding is not None:
            artifact = f"asr/voice-profiles/{speaker_id}.json"
            write_json(
                voice_profile_dir / f"{speaker_id}.json",
                {
                    "schema_version": "1.0",
                    "speaker_id": speaker_id,
                    "provider": "fixture",
                    "model": "fixture",
                    "embedding": embedding,
                },
            )
            embedding_status = "computed"
        profile_speakers.append(
            {
                "id": speaker_id,
                "label": speaker.get("label", speaker_id),
                "sample_count": 1 if embedding is not None else 0,
                "sample_duration_ms": 4200 if embedding is not None else 0,
                "profile_kind": "speaker_embedding" if embedding is not None else "diarization_stats",
                "embedding_status": embedding_status,
                "embedding_artifact": speaker.get("embedding_artifact", artifact),
            }
        )

    write_json(
        run_dir / "asr" / "speaker-profiles.json",
        {
            "schema_version": "1.0",
            "provider": "diarization_stats",
            "speaker_count": len(profile_speakers),
            "speakers": profile_speakers,
        },
    )


def test_compare_speaker_profiles_reports_cross_run_cosine_scores(tmp_path: Path):
    run_a = tmp_path / "runs" / "episode-a"
    run_b = tmp_path / "runs" / "episode-b"
    _write_run(
        run_a,
        [{"id": "speaker_1"}, {"id": "speaker_2"}],
        {"speaker_1": [1.0, 0.0], "speaker_2": [0.0, 1.0]},
    )
    _write_run(
        run_b,
        [{"id": "speaker_1"}, {"id": "speaker_2", "embedding_status": "unavailable"}],
        {"speaker_1": [0.99, 0.1]},
    )

    report = compare_speaker_profiles(
        [run_a, run_b],
        same_threshold=0.8,
        possible_threshold=0.65,
    )

    assert report["run_count"] == 2
    assert report["speaker_count"] == 3
    assert report["skipped_speaker_count"] == 1
    assert report["thresholds"] == {
        "same": 0.8,
        "possible": 0.65,
    }
    assert report["pairs"] == [
        {
            "left": {"run_index": 0, "run_id": "episode-a", "speaker_id": "speaker_1"},
            "right": {"run_index": 1, "run_id": "episode-b", "speaker_id": "speaker_1"},
            "same_run": False,
            "cosine": pytest.approx(0.994937),
            "classification": "likely_same",
        },
        {
            "left": {"run_index": 0, "run_id": "episode-a", "speaker_id": "speaker_2"},
            "right": {"run_index": 1, "run_id": "episode-b", "speaker_id": "speaker_1"},
            "same_run": False,
            "cosine": pytest.approx(0.100499),
            "classification": "different",
        },
    ]


def test_compare_speaker_profiles_rejects_artifacts_outside_run(tmp_path: Path):
    bad_run = tmp_path / "runs" / "bad-run"
    good_run = tmp_path / "runs" / "good-run"
    _write_run(
        bad_run,
        [
            {
                "id": "speaker_1",
                "embedding_status": "computed",
                "embedding_artifact": "../leaked.json",
            }
        ],
        {},
    )
    _write_run(good_run, [{"id": "speaker_1"}], {"speaker_1": [1.0, 0.0]})

    with pytest.raises(ValueError, match="embedding_artifact"):
        compare_speaker_profiles([bad_run, good_run])


def test_speaker_profiles_compare_cli_writes_json_report(tmp_path: Path):
    run_a = tmp_path / "runs" / "episode-a"
    run_b = tmp_path / "runs" / "episode-b"
    output_json = tmp_path / "speaker-similarity.json"
    _write_run(run_a, [{"id": "speaker_1"}], {"speaker_1": [1.0, 0.0]})
    _write_run(run_b, [{"id": "speaker_1"}], {"speaker_1": [0.99, 0.1]})

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "speaker-profiles",
            "compare",
            "--run-dir",
            str(run_a),
            "--run-dir",
            str(run_b),
            "--output-json",
            str(output_json),
        ],
        text=True,
        capture_output=True,
        env=_worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "speaker profile pairs: 1" in result.stdout
    assert output_json.exists()
    report = read_json(output_json)
    assert report["pairs"][0]["classification"] == "likely_same"
