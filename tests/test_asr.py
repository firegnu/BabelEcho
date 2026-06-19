from pathlib import Path

import pytest

from babelecho.asr import run_fixture_asr
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
