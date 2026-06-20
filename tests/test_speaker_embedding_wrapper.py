import importlib.util
from pathlib import Path

from babelecho.jsonio import read_json


def _load_wrapper():
    module_path = Path.cwd() / "tools" / "speaker_embedding_wrapper.py"
    spec = importlib.util.spec_from_file_location("speaker_embedding_wrapper", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_select_sample_windows_uses_longest_segments_per_speaker():
    wrapper = _load_wrapper()
    diarization = {
        "segments": [
            {"speaker": "speaker_1", "start_ms": 0, "end_ms": 1000},
            {"speaker": "speaker_1", "start_ms": 1000, "end_ms": 5000},
            {"speaker": "speaker_1", "start_ms": 6000, "end_ms": 9000},
            {"speaker": "speaker_2", "start_ms": 0, "end_ms": 2500},
        ]
    }

    windows = wrapper.select_sample_windows(
        diarization,
        min_sample_ms=1500,
        max_samples_per_speaker=2,
    )

    assert windows == {
        "speaker_1": [
            {"start_ms": 1000, "end_ms": 5000},
            {"start_ms": 6000, "end_ms": 9000},
        ],
        "speaker_2": [{"start_ms": 0, "end_ms": 2500}],
    }


def test_write_voice_profile_outputs_writes_summary_and_artifacts(tmp_path: Path):
    wrapper = _load_wrapper()
    output_dir = tmp_path / "run" / "asr" / "voice-profiles"
    output_json = output_dir / "summary.json"
    sample_windows = {
        "speaker_1": [{"start_ms": 1000, "end_ms": 5000}],
        "speaker_2": [],
    }

    wrapper.write_voice_profile_outputs(
        output_dir=output_dir,
        output_json=output_json,
        provider="speechbrain_ecapa",
        model="speechbrain/spkrec-ecapa-voxceleb",
        embeddings={"speaker_1": [0.1, 0.2]},
        sample_windows=sample_windows,
        embedding_dimension=2,
    )

    summary = read_json(output_json)
    assert summary["provider"] == "speechbrain_ecapa"
    assert summary["model"] == "speechbrain/spkrec-ecapa-voxceleb"
    assert summary["speakers"] == [
        {
            "id": "speaker_1",
            "sample_count": 1,
            "sample_duration_ms": 4000,
            "profile_kind": "speaker_embedding",
            "embedding_status": "computed",
            "embedding_artifact": "asr/voice-profiles/speaker_1.json",
        },
        {
            "id": "speaker_2",
            "sample_count": 0,
            "sample_duration_ms": 0,
            "profile_kind": "speaker_embedding",
            "embedding_status": "unavailable",
            "embedding_artifact": None,
        },
    ]
    artifact = read_json(output_dir / "speaker_1.json")
    assert artifact["schema_version"] == "1.0"
    assert artifact["speaker_id"] == "speaker_1"
    assert artifact["provider"] == "speechbrain_ecapa"
    assert artifact["embedding"] == [0.1, 0.2]
    assert artifact["sample_windows"] == [{"start_ms": 1000, "end_ms": 5000}]
