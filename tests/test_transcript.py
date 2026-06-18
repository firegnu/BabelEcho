from pathlib import Path

from babelecho.jsonio import read_json, write_json
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


def test_normalize_plain_text_extracts_speaker_labels(tmp_path: Path):
    run_paths = create_run(tmp_path, "speaker-run")
    raw = run_paths.transcript_dir / "raw.txt"
    raw.write_text(
        "\n\n".join(
            [
                "Host (Dane Turner): Houston, we have a podcast!",
                (
                    "This is setup. Nick Hague: Pleasure to be here. "
                    "Host: So, can you tell us more?"
                ),
                "This note keeps an ordinary ratio: 2 to 1.",
            ]
        ),
        encoding="utf-8",
    )

    data = read_json(normalize_transcript(run_paths, raw))

    assert [segment["id"] for segment in data["segments"]] == [
        "0001",
        "0002",
        "0003",
        "0004",
        "0005",
    ]
    assert [
        (segment["speaker"], segment["text"]) for segment in data["segments"]
    ] == [
        ("Host (Dane Turner)", "Houston, we have a podcast!"),
        (None, "This is setup."),
        ("Nick Hague", "Pleasure to be here."),
        ("Host", "So, can you tell us more?"),
        (None, "This note keeps an ordinary ratio: 2 to 1."),
    ]


def test_normalize_plain_text_inherits_single_speaker_continuations(tmp_path: Path):
    run_paths = create_run(tmp_path, "speaker-continuation-run")
    raw = run_paths.transcript_dir / "raw.txt"
    raw.write_text(
        "\n\n".join(
            [
                "ROMAN MARS: This is 99% Invisible.",
                "This year marks the 15th anniversary of the show.",
                "[AD BREAK]",
                "VIVIAN LE: Happy birthday!",
            ]
        ),
        encoding="utf-8",
    )

    data = read_json(normalize_transcript(run_paths, raw))

    assert [
        (segment["speaker"], segment["text"]) for segment in data["segments"]
    ] == [
        ("ROMAN MARS", "This is 99% Invisible."),
        ("ROMAN MARS", "This year marks the 15th anniversary of the show."),
        (None, "[AD BREAK]"),
        ("VIVIAN LE", "Happy birthday!"),
    ]


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
    quality = read_json(run_paths.transcript_quality_json)
    assert quality["metrics"]["segment_count"] == len(data["segments"])
    assert quality["recommendation"] in {
        "safe_to_adapt",
        "inspect_first",
        "reject",
    }


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


def test_normalize_youtube_captions_keeps_technical_colons_in_text(tmp_path: Path):
    run_paths = create_run(tmp_path, "youtube-caption-run")
    write_json(
        run_paths.source_json,
        {
            "source_type": "youtube_captions",
            "raw_transcript": "transcript/raw.vtt",
        },
    )
    raw = run_paths.transcript_dir / "raw.vtt"
    raw.write_text(
        """WEBVTT

00:00:00.000 --> 00:00:03.000
AI: problem definition matters when API: calls are involved.
""",
        encoding="utf-8",
    )

    data = read_json(normalize_transcript(run_paths, raw))

    assert len(data["segments"]) == 1
    assert data["segments"][0]["speaker"] is None
    assert data["segments"][0]["text"] == (
        "AI: problem definition matters when API: calls are involved."
    )


def test_normalize_youtube_captions_applies_start_offset(tmp_path: Path):
    run_paths = create_run(tmp_path, "youtube-start-run")
    write_json(
        run_paths.source_json,
        {
            "source_type": "youtube_captions",
            "raw_transcript": "transcript/raw.vtt",
            "youtube_start_ms": 3_000,
        },
    )
    raw = run_paths.transcript_dir / "raw.vtt"
    raw.write_text(
        """WEBVTT

00:00:00.000 --> 00:00:02.000
Before the shared start time.

00:00:02.500 --> 00:00:04.000
This overlaps the requested start time.

00:00:04.500 --> 00:00:06.000
This is after the requested start time.
""",
        encoding="utf-8",
    )

    data = read_json(normalize_transcript(run_paths, raw))

    assert [segment["id"] for segment in data["segments"]] == ["0001", "0002"]
    assert [segment["text"] for segment in data["segments"]] == [
        "This overlaps the requested start time.",
        "This is after the requested start time.",
    ]
