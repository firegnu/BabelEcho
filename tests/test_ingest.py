from pathlib import Path

from babelecho.ingest import ingest_transcript_source
from babelecho.jsonio import read_json
from babelecho.paths import create_run


def write_fake_yt_dlp(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake-yt-dlp"
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return script


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


def test_ingest_youtube_captions_writes_candidate_json(tmp_path: Path):
    fake_yt_dlp = write_fake_yt_dlp(
        tmp_path,
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
file="${out%\\.%(ext)s}.en.vtt"
cat > "$file" <<'VTT'
WEBVTT

00:00:00.000 --> 00:00:02.000
Host: Welcome to this agent episode.
VTT
printf '%s\\n' 'Fixture YouTube Episode'
""",
    )
    run_paths = create_run(tmp_path / "workspace", "youtube-candidate-run")

    raw_path = ingest_transcript_source(
        {
            "type": "youtube_captions",
            "url": "https://www.youtube.com/watch?v=abc123",
            "language": "en",
            "yt_dlp_command": str(fake_yt_dlp),
        },
        run_paths,
    )

    candidates = read_json(run_paths.transcript_dir / "candidates.json")
    source = read_json(run_paths.source_json)
    assert raw_path == run_paths.transcript_dir / "raw.vtt"
    assert (run_paths.transcript_dir / "cleaned.vtt").exists()
    assert source["raw_transcript"] == "transcript/raw.vtt"
    assert source["normalized_transcript_source"] == "transcript/cleaned.vtt"
    assert source["title"] == "Fixture YouTube Episode"
    assert candidates["selected"]["source_type"] == "youtube_captions"
    assert candidates["selected"]["source_url"] == "https://www.youtube.com/watch?v=abc123"
    assert candidates["selected"]["raw_path"] == "transcript/raw.vtt"
    assert candidates["selected"]["cleaned_path"] == "transcript/cleaned.vtt"
    assert candidates["selected"]["language"] == "en"
