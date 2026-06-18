from pathlib import Path

from babelecho.jsonio import read_json
from babelecho.paths import create_run
from babelecho.transcript_candidates import (
    build_youtube_candidate,
    write_candidates_json,
)


def test_writes_selected_youtube_candidate_json(tmp_path: Path):
    run_paths = create_run(tmp_path, "candidate-run")
    raw_path = run_paths.transcript_dir / "raw.vtt"
    raw_path.write_text(
        """WEBVTT

00:00:00.000 --> 00:00:03.000
Host: Welcome to this agent episode.
""",
        encoding="utf-8",
    )

    candidate = build_youtube_candidate(
        run_paths,
        source_url="https://www.youtube.com/watch?v=abc123",
        raw_path=raw_path,
        language="en",
        selected=True,
    )
    output = write_candidates_json(run_paths, [candidate])

    data = read_json(output)
    assert data["selected"]["source_type"] == "youtube_captions"
    assert data["selected"]["format"] == "vtt"
    assert data["selected"]["language"] == "en"
    assert data["selected"]["selected"] is True
    assert data["selected"]["raw_path"] == "transcript/raw.vtt"
    assert data["selected"]["has_timestamps"] is True
    assert data["selected"]["text_char_count"] > 0
    assert data["selected"]["segment_count_estimate"] == 1
    assert data["selected"]["speaker_count_estimate"] == 1
    assert data["selected"]["score"] > 0
    assert data["candidates"] == [data["selected"]]


def test_writes_rejected_youtube_candidate_json(tmp_path: Path):
    run_paths = create_run(tmp_path, "candidate-failure-run")

    candidate = build_youtube_candidate(
        run_paths,
        source_url="https://www.youtube.com/watch?v=missing",
        raw_path=None,
        language="en",
        selected=False,
        rejection_reason="No YouTube subtitles downloaded",
    )
    output = write_candidates_json(run_paths, [candidate])

    data = read_json(output)
    assert data["selected"] is None
    assert data["candidates"][0]["selected"] is False
    assert data["candidates"][0]["raw_path"] is None
    assert data["candidates"][0]["rejection_reason"] == "No YouTube subtitles downloaded"
