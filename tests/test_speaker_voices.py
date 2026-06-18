from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.speaker_voices import infer_speaker_voices


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
