from pathlib import Path

from babelecho.jsonio import read_json
from babelecho.paths import create_run
from babelecho.transcript import normalize_transcript


def test_normalize_plain_text(tmp_path: Path):
    run_paths = create_run(tmp_path, "text-run")
    raw = run_paths.transcript_dir / "raw.txt"
    raw.write_text(
        Path("tests/fixtures/sample.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    output = normalize_transcript(run_paths, raw)
    data = read_json(output)

    assert data["language"] == "en"
    assert [segment["id"] for segment in data["segments"]] == ["0001", "0002"]
    assert data["segments"][0]["start_ms"] is None
    assert data["segments"][0]["text"] == "Welcome to the sample episode."


def test_normalize_vtt(tmp_path: Path):
    run_paths = create_run(tmp_path, "vtt-run")
    raw = run_paths.transcript_dir / "raw.vtt"
    raw.write_text(
        Path("tests/fixtures/sample.vtt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    data = read_json(normalize_transcript(run_paths, raw))

    assert data["segments"][0]["start_ms"] == 0
    assert data["segments"][0]["end_ms"] == 3000


def test_normalize_srt(tmp_path: Path):
    run_paths = create_run(tmp_path, "srt-run")
    raw = run_paths.transcript_dir / "raw.srt"
    raw.write_text(
        Path("tests/fixtures/sample.srt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    data = read_json(normalize_transcript(run_paths, raw))

    assert len(data["segments"]) == 2
    assert data["segments"][1]["start_ms"] == 3500
    assert data["segments"][1]["text"] == "This is the second subtitle."
