import os
import subprocess
import sys
from pathlib import Path

import pytest

from babelecho.jsonio import read_json, write_json
from babelecho.speaker_alias_review import build_speaker_alias_review
from babelecho.speaker_aliases import build_speaker_aliases


def _worktree_python_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def _speaker(
    run_index: int,
    run_id: str,
    speaker_id: str,
    sample_duration_ms: int,
) -> dict:
    return {
        "run_index": run_index,
        "run_id": run_id,
        "speaker_id": speaker_id,
        "sample_count": 4,
        "sample_duration_ms": sample_duration_ms,
        "embedding_dimension": 192,
        "embedding_artifact": f"asr/voice-profiles/{speaker_id}.json",
    }


def _pair(
    left: tuple[int, str, str],
    right: tuple[int, str, str],
    cosine: float,
) -> dict:
    return {
        "left": {"run_index": left[0], "run_id": left[1], "speaker_id": left[2]},
        "right": {"run_index": right[0], "run_id": right[1], "speaker_id": right[2]},
        "same_run": False,
        "cosine": cosine,
        "classification": "likely_same" if cosine >= 0.85 else "different",
    }


def test_build_speaker_aliases_filters_short_intro_like_speakers():
    report = {
        "schema_version": "1.0",
        "speakers": [
            _speaker(0, "episode-a", "speaker_1", 32000),
            _speaker(1, "episode-b", "speaker_1", 32100),
            _speaker(0, "episode-a", "speaker_2", 120000),
            _speaker(1, "episode-b", "speaker_2", 110000),
            _speaker(2, "episode-c", "speaker_2", 90000),
        ],
        "pairs": [
            _pair((0, "episode-a", "speaker_1"), (1, "episode-b", "speaker_1"), 0.999),
            _pair((0, "episode-a", "speaker_2"), (1, "episode-b", "speaker_2"), 0.93),
            _pair((0, "episode-a", "speaker_2"), (2, "episode-c", "speaker_2"), 0.88),
            _pair((1, "episode-b", "speaker_2"), (2, "episode-c", "speaker_2"), 0.86),
        ],
    }

    aliases = build_speaker_aliases(
        report,
        same_threshold=0.85,
        min_sample_duration_ms=60000,
    )

    assert aliases["alias_count"] == 1
    assert aliases["aliases"] == [
        {
            "alias_id": "speaker_alias_001",
            "member_count": 3,
            "pair_count": 3,
            "min_cosine": pytest.approx(0.86),
            "max_cosine": pytest.approx(0.93),
            "average_cosine": pytest.approx(0.89),
            "members": [
                {
                    "run_index": 0,
                    "run_id": "episode-a",
                    "speaker_id": "speaker_2",
                    "sample_count": 4,
                    "sample_duration_ms": 120000,
                },
                {
                    "run_index": 1,
                    "run_id": "episode-b",
                    "speaker_id": "speaker_2",
                    "sample_count": 4,
                    "sample_duration_ms": 110000,
                },
                {
                    "run_index": 2,
                    "run_id": "episode-c",
                    "speaker_id": "speaker_2",
                    "sample_count": 4,
                    "sample_duration_ms": 90000,
                },
            ],
        }
    ]
    assert aliases["skipped_speakers"] == [
        {
            "run_index": 0,
            "run_id": "episode-a",
            "speaker_id": "speaker_1",
            "sample_duration_ms": 32000,
            "reason": "sample_duration_below_minimum",
        },
        {
            "run_index": 1,
            "run_id": "episode-b",
            "speaker_id": "speaker_1",
            "sample_duration_ms": 32100,
            "reason": "sample_duration_below_minimum",
        },
    ]


def test_build_speaker_aliases_skips_components_with_duplicate_run_members():
    report = {
        "schema_version": "1.0",
        "speakers": [
            _speaker(0, "episode-a", "speaker_1", 120000),
            _speaker(0, "episode-a", "speaker_2", 120000),
            _speaker(1, "episode-b", "speaker_1", 120000),
        ],
        "pairs": [
            _pair((0, "episode-a", "speaker_1"), (1, "episode-b", "speaker_1"), 0.91),
            _pair((0, "episode-a", "speaker_2"), (1, "episode-b", "speaker_1"), 0.9),
        ],
    }

    aliases = build_speaker_aliases(report, same_threshold=0.85)

    assert aliases["alias_count"] == 0
    assert aliases["aliases"] == []
    assert aliases["skipped_components"] == [
        {
            "reason": "multiple_speakers_in_one_run",
            "members": [
                {"run_index": 0, "run_id": "episode-a", "speaker_id": "speaker_1"},
                {"run_index": 0, "run_id": "episode-a", "speaker_id": "speaker_2"},
                {"run_index": 1, "run_id": "episode-b", "speaker_id": "speaker_1"},
            ],
        }
    ]


def test_speaker_profiles_alias_cli_writes_private_alias_map(tmp_path: Path):
    report_path = tmp_path / "speaker-similarity.json"
    output_json = tmp_path / "speaker-aliases.json"
    write_json(
        report_path,
        {
            "schema_version": "1.0",
            "speakers": [
                _speaker(0, "episode-a", "speaker_1", 120000),
                _speaker(1, "episode-b", "speaker_2", 110000),
            ],
            "pairs": [
                _pair((0, "episode-a", "speaker_1"), (1, "episode-b", "speaker_2"), 0.92)
            ],
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "speaker-profiles",
            "alias",
            "--similarity-report",
            str(report_path),
            "--output-json",
            str(output_json),
            "--same-threshold",
            "0.85",
            "--min-sample-duration-ms",
            "60000",
        ],
        text=True,
        capture_output=True,
        env=_worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "speaker aliases: 1" in result.stdout
    aliases = read_json(output_json)
    assert aliases["aliases"][0]["members"][0]["speaker_id"] == "speaker_1"
    assert "embedding_artifact" not in aliases["aliases"][0]["members"][0]


def test_build_speaker_alias_review_defaults_candidates_and_keeps_safe_fields():
    alias_map = {
        "schema_version": "1.0",
        "source": "speaker_similarity_report",
        "alias_count": 1,
        "aliases": [
            {
                "alias_id": "speaker_alias_001",
                "member_count": 2,
                "pair_count": 1,
                "min_cosine": 0.92,
                "max_cosine": 0.92,
                "average_cosine": 0.92,
                "members": [
                    {
                        "run_index": 0,
                        "run_id": "episode-a",
                        "speaker_id": "speaker_1",
                        "sample_count": 4,
                        "sample_duration_ms": 120000,
                        "embedding_artifact": "asr/voice-profiles/speaker_1.json",
                    },
                    {
                        "run_index": 1,
                        "run_id": "episode-b",
                        "speaker_id": "speaker_2",
                        "sample_count": 4,
                        "sample_duration_ms": 110000,
                    },
                ],
            }
        ],
    }

    review = build_speaker_alias_review(alias_map)

    assert review["schema_version"] == "1.0"
    assert review["source"] == "speaker_alias_review"
    assert review["review_status_counts"] == {"candidate": 1}
    assert review["aliases"] == [
        {
            "alias_id": "speaker_alias_001",
            "candidate_alias_id": "speaker_alias_001",
            "review_status": "candidate",
            "reviewer": None,
            "reviewed_at": None,
            "review_note": None,
            "candidate": {
                "member_count": 2,
                "pair_count": 1,
                "min_cosine": 0.92,
                "max_cosine": 0.92,
                "average_cosine": 0.92,
            },
            "members": [
                {
                    "run_index": 0,
                    "run_id": "episode-a",
                    "speaker_id": "speaker_1",
                    "sample_count": 4,
                    "sample_duration_ms": 120000,
                },
                {
                    "run_index": 1,
                    "run_id": "episode-b",
                    "speaker_id": "speaker_2",
                    "sample_count": 4,
                    "sample_duration_ms": 110000,
                },
            ],
        }
    ]


def test_build_speaker_alias_review_preserves_existing_review_decisions():
    alias_map = {
        "schema_version": "1.0",
        "aliases": [
            {
                "alias_id": "speaker_alias_001",
                "member_count": 2,
                "pair_count": 1,
                "min_cosine": 0.91,
                "max_cosine": 0.91,
                "average_cosine": 0.91,
                "members": [
                    _speaker(0, "episode-a", "speaker_1", 120000),
                    _speaker(1, "episode-b", "speaker_2", 110000),
                ],
            }
        ],
    }
    existing_review = {
        "schema_version": "1.0",
        "source": "speaker_alias_review",
        "aliases": [
            {
                "alias_id": "speaker_alias_001",
                "review_status": "confirmed",
                "reviewer": "local",
                "reviewed_at": "2026-06-20T08:00:00Z",
                "review_note": "same host",
            }
        ],
    }

    review = build_speaker_alias_review(alias_map, existing_review=existing_review)

    assert review["review_status_counts"] == {"confirmed": 1}
    reviewed = review["aliases"][0]
    assert reviewed["review_status"] == "confirmed"
    assert reviewed["reviewer"] == "local"
    assert reviewed["reviewed_at"] == "2026-06-20T08:00:00Z"
    assert reviewed["review_note"] == "same host"


def test_speaker_profiles_review_cli_writes_private_review_contract(tmp_path: Path):
    alias_map_path = tmp_path / "speaker-aliases.json"
    output_json = tmp_path / "speaker-alias-review.json"
    write_json(
        alias_map_path,
        {
            "schema_version": "1.0",
            "aliases": [
                {
                    "alias_id": "speaker_alias_001",
                    "member_count": 2,
                    "pair_count": 1,
                    "min_cosine": 0.91,
                    "max_cosine": 0.91,
                    "average_cosine": 0.91,
                    "members": [
                        _speaker(0, "episode-a", "speaker_1", 120000),
                        _speaker(1, "episode-b", "speaker_2", 110000),
                    ],
                }
            ],
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "speaker-profiles",
            "review",
            "--alias-map",
            str(alias_map_path),
            "--output-json",
            str(output_json),
        ],
        text=True,
        capture_output=True,
        env=_worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "speaker alias review: 1 aliases" in result.stdout
    review = read_json(output_json)
    assert review["aliases"][0]["review_status"] == "candidate"


def test_speaker_profiles_review_cli_preserves_existing_review_contract(tmp_path: Path):
    alias_map_path = tmp_path / "speaker-aliases.json"
    existing_review_path = tmp_path / "speaker-alias-review-existing.json"
    output_json = tmp_path / "speaker-alias-review.json"
    write_json(
        alias_map_path,
        {
            "schema_version": "1.0",
            "aliases": [
                {
                    "alias_id": "speaker_alias_001",
                    "member_count": 2,
                    "pair_count": 1,
                    "min_cosine": 0.91,
                    "max_cosine": 0.91,
                    "average_cosine": 0.91,
                    "members": [
                        _speaker(0, "episode-a", "speaker_1", 120000),
                        _speaker(1, "episode-b", "speaker_2", 110000),
                    ],
                }
            ],
        },
    )
    write_json(
        existing_review_path,
        {
            "schema_version": "1.0",
            "source": "speaker_alias_review",
            "aliases": [
                {
                    "alias_id": "speaker_alias_001",
                    "review_status": "confirmed",
                    "reviewer": "local",
                    "reviewed_at": "2026-06-20T08:00:00Z",
                    "review_note": "same host",
                }
            ],
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "speaker-profiles",
            "review",
            "--alias-map",
            str(alias_map_path),
            "--existing-review",
            str(existing_review_path),
            "--output-json",
            str(output_json),
        ],
        text=True,
        capture_output=True,
        env=_worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    review = read_json(output_json)
    assert review["review_status_counts"] == {"confirmed": 1}
    assert review["aliases"][0]["review_status"] == "confirmed"
    assert review["aliases"][0]["review_note"] == "same host"
