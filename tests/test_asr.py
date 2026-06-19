from pathlib import Path
import sys

import pytest

from babelecho.asr import run_asr, run_fixture_asr
from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run


def test_fixture_asr_writes_canonical_raw_json(tmp_path: Path):
    fixture = Path("tests/fixtures/asr/two-speaker-asr.json")
    run_paths = create_run(tmp_path / "workspace", "fixture-asr")

    asr_path = run_fixture_asr(
        {
            "provider": "fixture",
            "fixture_path": str(fixture),
        },
        run_paths,
        config_path=Path.cwd() / "local-audio.yaml",
    )

    assert asr_path == run_paths.run_dir / "asr" / "raw.json"
    raw = read_json(asr_path)
    assert raw == read_json(fixture)


def test_local_cli_asr_invokes_wrapper_and_writes_canonical_raw_json(tmp_path: Path):
    wrapper = tmp_path / "fake_asr_wrapper.py"
    wrapper.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--audio-file", required=True)
parser.add_argument("--output-json", required=True)
parser.add_argument("--model")
parser.add_argument("--language")
parser.add_argument("--device")
args = parser.parse_args()

audio = Path(args.audio_file)
if not audio.exists():
    raise SystemExit(f"missing audio file: {audio}")

Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
Path(args.output_json).write_text(json.dumps({
    "provider": "fake_asr",
    "model": args.model,
    "language": args.language,
    "duration_seconds": 2.4,
    "segments": [
        {
            "start_ms": 0,
            "end_ms": 2400,
            "text": f"transcribed {audio.name} on {args.device}",
            "confidence": 0.91,
        }
    ],
}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    run_paths = create_run(tmp_path / "workspace", "local-cli-asr")
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

    asr_path = run_asr(
        {
            "provider": "local_cli",
            "command": f"{sys.executable} {wrapper}",
            "model": "tiny.en",
            "language": "en",
            "device": "cpu",
        },
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    raw = read_json(asr_path)
    assert raw == {
        "provider": "fake_asr",
        "model": "tiny.en",
        "language": "en",
        "duration_seconds": 2.4,
        "segments": [
            {
                "id": "asr_0001",
                "start_ms": 0,
                "end_ms": 2400,
                "text": "transcribed input.wav on cpu",
                "confidence": 0.91,
            }
        ],
    }


@pytest.mark.parametrize("missing_key", ["start_ms", "end_ms", "text"])
def test_fixture_asr_rejects_segment_missing_required_fields(
    tmp_path: Path,
    missing_key: str,
):
    segment = {
        "id": "asr_0001",
        "start_ms": 0,
        "end_ms": 2000,
        "text": "Hello from the source audio.",
    }
    del segment[missing_key]
    fixture = tmp_path / "bad-asr.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "model": "fixture",
            "language": "en",
            "duration_seconds": 2.0,
            "segments": [segment],
        },
    )
    run_paths = create_run(tmp_path / "workspace", f"bad-asr-{missing_key}")

    with pytest.raises(ValueError, match=f"ASR segment 1 missing required key: {missing_key}"):
        run_fixture_asr(
            {
                "provider": "fixture",
                "fixture_path": str(fixture),
            },
            run_paths,
            config_path=fixture,
        )
