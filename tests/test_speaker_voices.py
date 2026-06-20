import os
import subprocess
import sys
from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.speaker_voices import apply_speaker_voice_role_map, infer_speaker_voices


def _worktree_python_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def _write_script(run_paths, segments: list[dict]) -> None:
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": run_paths.run_id,
            "language": "zh-CN",
            "segments": segments,
        },
    )


def test_infer_speaker_voices_writes_concrete_roles_and_reuses_existing_file(
    monkeypatch,
    tmp_path: Path,
):
    run_paths = create_run(tmp_path, "speaker-voice-run")
    _write_script(
        run_paths,
        [
            {"id": "0001", "source_segment_ids": ["0001"], "speaker": "ROMAN MARS", "text": "罗曼。"},
            {"id": "0002", "source_segment_ids": ["0002"], "speaker": "VIVIAN LE", "text": "薇薇安。"},
            {"id": "0003", "source_segment_ids": ["0003"], "speaker": "TAYA", "text": "泰雅。"},
        ],
    )
    calls = []

    class FakeClient:
        def infer_speaker_genders(self, speakers):
            calls.append(speakers)
            return [
                {
                    "speaker": "ROMAN MARS",
                    "gender": "male",
                    "confidence": 0.95,
                    "reason": "public host knowledge",
                },
                {
                    "speaker": "VIVIAN LE",
                    "gender": "female",
                    "confidence": 0.42,
                    "reason": "name and context",
                },
                {
                    "speaker": "TAYA",
                    "gender": "unknown",
                    "confidence": 0.2,
                    "reason": "insufficient evidence",
                },
            ]

    monkeypatch.setattr("babelecho.speaker_voices.build_llm_client", lambda _config: FakeClient())

    result = infer_speaker_voices(
        run_paths,
        {"provider": "fixture"},
        {"mode": "infer_once"},
    )

    assert result["status"] == "created"
    assert len(calls) == 1
    assert [speaker["speaker"] for speaker in calls[0]] == ["ROMAN MARS", "VIVIAN LE", "TAYA"]
    data = read_json(result["path"])
    assert data["speaker_voices"] == {
        "ROMAN MARS": "male_a",
        "VIVIAN LE": "female_a",
        "TAYA": "female_b",
    }
    assert data["inferences"][1]["confidence"] == 0.42
    assert data["inferences"][1]["voice_role"] == "female_a"
    assert data["inferences"][2]["gender"] == "unknown"
    assert data["inferences"][2]["voice_role"] == "female_b"

    reused = infer_speaker_voices(
        run_paths,
        {"provider": "fixture"},
        {"mode": "infer_once"},
    )

    assert reused["status"] == "reused"
    assert len(calls) == 1
    assert reused["path"] == result["path"]


def test_apply_speaker_voice_role_map_writes_only_target_run_speakers(tmp_path: Path):
    run_paths = create_run(tmp_path, "episode-a")
    role_map = {
        "schema_version": "1.0",
        "source": "speaker_voice_role_map",
        "aliases": [
            {
                "alias_id": "speaker_alias_001",
                "voice_role": "female_a",
                "review_status": "confirmed",
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
            },
            {
                "alias_id": "speaker_alias_002",
                "voice_role": "male_a",
                "review_status": "confirmed",
                "members": [
                    {
                        "run_index": 0,
                        "run_id": "episode-a",
                        "speaker_id": "speaker_3",
                        "sample_count": 3,
                        "sample_duration_ms": 90000,
                    }
                ],
            },
        ],
    }

    result = apply_speaker_voice_role_map(run_paths, role_map)

    assert result == {
        "status": "created",
        "path": str(run_paths.script_dir / "speaker-voices.json"),
        "speaker_count": 2,
        "alias_count": 2,
    }
    data = read_json(run_paths.script_dir / "speaker-voices.json")
    assert data["mode"] == "speaker_voice_role_map"
    assert data["source"] == "speaker_voice_role_map"
    assert data["speaker_voices"] == {
        "speaker_1": "female_a",
        "speaker_3": "male_a",
    }
    assert data["inferences"] == [
        {
            "speaker": "speaker_1",
            "gender": "unknown",
            "confidence": 1.0,
            "reason": "confirmed speaker alias speaker_alias_001",
            "voice_role": "female_a",
            "alias_id": "speaker_alias_001",
        },
        {
            "speaker": "speaker_3",
            "gender": "unknown",
            "confidence": 1.0,
            "reason": "confirmed speaker alias speaker_alias_002",
            "voice_role": "male_a",
            "alias_id": "speaker_alias_002",
        },
    ]


def test_apply_speaker_voice_role_map_reuses_existing_file_without_overwrite(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path, "episode-a")
    write_json(
        run_paths.script_dir / "speaker-voices.json",
        {
            "version": 1,
            "mode": "manual",
            "speaker_voices": {"speaker_1": "male_b"},
            "inferences": [],
        },
    )

    result = apply_speaker_voice_role_map(
        run_paths,
        {
            "schema_version": "1.0",
            "source": "speaker_voice_role_map",
            "aliases": [
                {
                    "alias_id": "speaker_alias_001",
                    "voice_role": "female_a",
                    "review_status": "confirmed",
                    "members": [
                        {
                            "run_index": 0,
                            "run_id": "episode-a",
                            "speaker_id": "speaker_1",
                            "sample_count": 4,
                            "sample_duration_ms": 120000,
                        }
                    ],
                }
            ],
        },
    )

    assert result["status"] == "reused"
    data = read_json(run_paths.script_dir / "speaker-voices.json")
    assert data["speaker_voices"] == {"speaker_1": "male_b"}


def test_speaker_profiles_apply_voice_roles_cli_writes_per_run_speaker_voices(
    tmp_path: Path,
):
    role_map_path = tmp_path / "speaker-voice-role-map.json"
    write_json(
        role_map_path,
        {
            "schema_version": "1.0",
            "source": "speaker_voice_role_map",
            "aliases": [
                {
                    "alias_id": "speaker_alias_001",
                    "voice_role": "female_a",
                    "review_status": "confirmed",
                    "members": [
                        {
                            "run_index": 0,
                            "run_id": "episode-a",
                            "speaker_id": "speaker_1",
                            "sample_count": 4,
                            "sample_duration_ms": 120000,
                        }
                    ],
                }
            ],
        },
    )
    create_run(tmp_path, "episode-a")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "speaker-profiles",
            "apply-voice-roles",
            "--workspace",
            str(tmp_path),
            "--run-id",
            "episode-a",
            "--voice-role-map",
            str(role_map_path),
        ],
        text=True,
        capture_output=True,
        env=_worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "speaker voice role map applied: created" in result.stdout
    data = read_json(tmp_path / "runs" / "episode-a" / "script" / "speaker-voices.json")
    assert data["speaker_voices"] == {"speaker_1": "female_a"}
