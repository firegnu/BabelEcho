import subprocess
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
    profiles = read_json(run_paths.run_dir / "asr" / "speaker-profiles.json")
    assert profiles == {
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
    }


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
    profiles = read_json(run_paths.run_dir / "asr" / "speaker-profiles.json")
    assert profiles == {
        "schema_version": "1.0",
        "provider": "diarization_stats",
        "source": "diarization",
        "diarization_provider": "none",
        "diarization_model": None,
        "speaker_count": 1,
        "speakers": [
            {
                "id": "speaker_1",
                "label": "speaker_1",
                "turn_count": 0,
                "total_ms": 0,
                "first_start_ms": None,
                "last_end_ms": None,
                "avg_turn_ms": None,
                "sample_count": 0,
                "sample_duration_ms": 0,
                "profile_kind": "diarization_stats",
                "embedding_status": "not_computed",
                "embedding_artifact": None,
            }
        ],
    }


def test_fixture_diarization_profiles_preserve_custom_speaker_labels(tmp_path: Path):
    fixture = tmp_path / "custom-speaker-diarization.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "model": "fixture",
            "speaker_count": 1,
            "segments": [
                {
                    "start_ms": 1000,
                    "end_ms": 2500,
                    "speaker": "host",
                }
            ],
        },
    )
    run_paths = create_run(tmp_path / "workspace", "custom-speaker-diarization")

    run_diarization(
        {
            "provider": "fixture",
            "fixture_path": str(fixture),
        },
        run_paths,
        config_path=fixture,
    )

    profiles = read_json(run_paths.run_dir / "asr" / "speaker-profiles.json")
    assert profiles["speaker_count"] == 1
    assert profiles["speakers"] == [
        {
            "id": "host",
            "label": "host",
            "turn_count": 1,
            "total_ms": 1500,
            "first_start_ms": 1000,
            "last_end_ms": 2500,
            "avg_turn_ms": 1500.0,
            "sample_count": 0,
            "sample_duration_ms": 0,
            "profile_kind": "diarization_stats",
            "embedding_status": "not_computed",
            "embedding_artifact": None,
        }
    ]


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


def test_local_cli_diarization_canonicalizes_compressed_audio_before_wrapper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "local-cli-compressed-diarization")
    audio_dir = run_paths.run_dir / "audio"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / "input.mp3"
    audio_path.write_bytes(b"fake mp3 bytes")
    write_json(
        run_paths.source_json,
        {
            "source_type": "audio_url",
            "audio_input": "audio/input.mp3",
        },
    )

    ffmpeg_commands = []
    wrapper_audio_files = []

    def fake_run(command, check, text, capture_output):
        if command[0] == "ffmpeg":
            ffmpeg_commands.append(command)
            Path(command[-1]).write_bytes(b"canonical wav bytes")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        audio = Path(command[command.index("--audio-file") + 1])
        wrapper_audio_files.append(audio)
        output_json = Path(command[command.index("--output-json") + 1])
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            """
{
  "provider": "fake_diarization",
  "model": "fake-model",
  "speaker_count": 1,
  "segments": [
    {"start_ms": 0, "end_ms": 1500, "speaker": "speaker_1"}
  ],
  "metadata": {
    "audio_name": "%s"
  }
}
"""
            % audio.name,
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("babelecho.diarization.subprocess.run", fake_run)

    diarization_path = run_diarization(
        {
            "provider": "local_cli",
            "command": f"{sys.executable} fake_diarization_wrapper.py",
            "model": "fake-model",
        },
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    canonical_audio = run_paths.run_dir / "audio" / "diarization-input.wav"
    assert ffmpeg_commands == [
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(audio_path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(canonical_audio),
        ]
    ]
    assert canonical_audio.exists()
    assert wrapper_audio_files == [canonical_audio]
    assert (
        read_json(diarization_path)["metadata"]["audio_name"]
        == "diarization-input.wav"
    )


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
