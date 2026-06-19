import sys
from pathlib import Path

import pytest

from babelecho.diarization import run_diarization
from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run


def test_fixture_diarization_writes_canonical_json(tmp_path: Path):
    fixture = Path("tests/fixtures/asr/two-speaker-diarization.json")
    run_paths = create_run(tmp_path / "workspace", "fixture-diarization")

    diarization_path = run_diarization(
        {
            "provider": "fixture",
            "fixture_path": str(fixture),
        },
        run_paths,
        config_path=Path.cwd() / "local-audio.yaml",
    )

    assert diarization_path == run_paths.run_dir / "asr" / "diarization.json"
    diarization = read_json(diarization_path)
    assert diarization == read_json(fixture)
    assert [segment["speaker"] for segment in diarization["segments"]] == [
        "speaker_1",
        "speaker_2",
    ]


def test_disabled_diarization_writes_empty_single_speaker_artifact(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "disabled-diarization")

    diarization_path = run_diarization(
        {"provider": "none"},
        run_paths,
        config_path=Path.cwd() / "local-audio.yaml",
    )

    diarization = read_json(diarization_path)
    assert diarization == {
        "provider": "none",
        "model": None,
        "speaker_count": 1,
        "segments": [],
        "warnings": ["diarization_disabled"],
    }


def test_local_cli_diarization_invokes_wrapper_and_writes_canonical_json(
    tmp_path: Path,
):
    wrapper = tmp_path / "fake_diarization_wrapper.py"
    wrapper.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--audio-file", required=True)
parser.add_argument("--output-json", required=True)
parser.add_argument("--model")
parser.add_argument("--min-speakers")
parser.add_argument("--max-speakers")
args = parser.parse_args()

audio = Path(args.audio_file)
if not audio.exists():
    raise SystemExit(f"missing audio file: {audio}")

Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
Path(args.output_json).write_text(json.dumps({
    "provider": "fake_diarization",
    "model": args.model,
    "speaker_count": 2,
    "segments": [
        {"start_ms": 0, "end_ms": 1800, "speaker": "speaker_1"},
        {"start_ms": 1800, "end_ms": 3600, "speaker": "speaker_2"},
    ],
    "metadata": {
        "audio_name": audio.name,
        "speaker_bounds": [args.min_speakers, args.max_speakers],
    },
}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    run_paths = create_run(tmp_path / "workspace", "local-cli-diarization")
    audio_dir = run_paths.run_dir / "audio"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / "input.wav"
    audio_path.write_bytes(b"fake audio")
    write_json(
        run_paths.source_json,
        {
            "source_type": "audio_file",
            "audio_input": "audio/input.wav",
        },
    )

    diarization_path = run_diarization(
        {
            "provider": "local_cli",
            "command": f"{sys.executable} {wrapper}",
            "model": "fake-model",
            "min_speakers": 1,
            "max_speakers": 3,
        },
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    diarization = read_json(diarization_path)
    assert diarization == {
        "provider": "fake_diarization",
        "model": "fake-model",
        "speaker_count": 2,
        "segments": [
            {"start_ms": 0, "end_ms": 1800, "speaker": "speaker_1"},
            {"start_ms": 1800, "end_ms": 3600, "speaker": "speaker_2"},
        ],
        "metadata": {
            "audio_name": "input.wav",
            "speaker_bounds": ["1", "3"],
        },
    }


@pytest.mark.parametrize("missing_key", ["start_ms", "end_ms", "speaker"])
def test_fixture_diarization_rejects_segment_missing_required_fields(
    tmp_path: Path,
    missing_key: str,
):
    segment = {
        "start_ms": 0,
        "end_ms": 2000,
        "speaker": "speaker_1",
    }
    del segment[missing_key]
    fixture = tmp_path / "bad-diarization.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "model": "fixture",
            "speaker_count": 1,
            "segments": [segment],
        },
    )
    run_paths = create_run(tmp_path / "workspace", f"bad-diarization-{missing_key}")

    with pytest.raises(
        ValueError,
        match=f"Diarization segment 1 missing required key: {missing_key}",
    ):
        run_diarization(
            {
                "provider": "fixture",
                "fixture_path": str(fixture),
            },
            run_paths,
            config_path=fixture,
        )


def test_fixture_diarization_rejects_non_increasing_timestamps(tmp_path: Path):
    fixture = tmp_path / "bad-diarization.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "model": "fixture",
            "speaker_count": 1,
            "segments": [
                {
                    "start_ms": 2000,
                    "end_ms": 1000,
                    "speaker": "speaker_1",
                }
            ],
        },
    )
    run_paths = create_run(tmp_path / "workspace", "bad-diarization-time")

    with pytest.raises(
        ValueError,
        match="Diarization segment 1 end_ms must be after start_ms",
    ):
        run_diarization(
            {
                "provider": "fixture",
                "fixture_path": str(fixture),
            },
            run_paths,
            config_path=fixture,
        )
