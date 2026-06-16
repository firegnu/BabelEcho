from pathlib import Path

from babelecho.ingest import ingest_transcript_source
from babelecho.jsonio import read_json
from babelecho.paths import create_run


def test_ingest_copies_local_transcript(tmp_path: Path):
    fixture = Path("tests/fixtures/sample.vtt")
    run_paths = create_run(tmp_path, "demo-run")
    source_config = {
        "type": "transcript_url",
        "transcript_url": str(fixture),
        "title": "Sample Episode",
        "original_url": "https://example.com/sample",
    }

    raw_path = ingest_transcript_source(source_config, run_paths)

    assert raw_path == run_paths.transcript_dir / "raw.vtt"
    assert raw_path.read_text(encoding="utf-8").startswith("WEBVTT")
    assert read_json(run_paths.source_json)["title"] == "Sample Episode"
