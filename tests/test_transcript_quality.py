from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.transcript_quality import write_transcript_quality


def _segments(texts: list[str]) -> list[dict]:
    return [
        {
            "id": f"{index:04d}",
            "start_ms": None,
            "end_ms": None,
            "speaker": None,
            "text": text,
            "source": "transcript",
        }
        for index, text in enumerate(texts, start=1)
    ]


def _write_normalized(run_paths, texts: list[str]) -> Path:
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": run_paths.run_id,
            "language": "en",
            "segments": _segments(texts),
        },
    )
    return run_paths.normalized_transcript_json


def test_quality_report_marks_usable_transcript_safe(tmp_path: Path):
    run_paths = create_run(tmp_path, "safe-quality")
    paragraphs = [
        (
            "This discussion explains how agents plan tool calls, recover from "
            "errors, and keep a transcript usable before the adaptation stage."
        ),
        (
            "The host compares deterministic checks with model judgment and "
            "keeps the risky decisions outside the caption download step."
        ),
        (
            "A clean source gives the Chinese script pass enough context to "
            "summarize ideas without inventing speaker names or identities."
        ),
        (
            "The episode also covers why local preprocessing should catch "
            "caption markup before the transcript reaches the language model."
        ),
        (
            "Later sections explain how metrics such as segment length and "
            "repetition can expose broken subtitle exports early."
        ),
        (
            "The workflow stays focused on one submitted URL so subscription "
            "scanning and feed discovery remain outside the current milestone."
        ),
        (
            "For YouTube podcasts, the same transcript contract can be reused "
            "as long as the source resolves to a single video episode."
        ),
        (
            "The final recommendation is advisory, giving the operator a clear "
            "signal before spending an LLM request on adaptation."
        ),
    ]
    _write_normalized(run_paths, paragraphs)

    output = write_transcript_quality(run_paths)
    report = read_json(output)

    assert output == run_paths.transcript_quality_json
    assert report["recommendation"] == "safe_to_adapt"
    assert report["metrics"]["segment_count"] == 8
    assert report["metrics"]["speaker_count"] == 0
    assert report["metrics"]["dirty_markup_count"] == 0
    assert report["metrics"]["html_entity_count"] == 0
    assert report["flags"]["too_short"] is False


def test_quality_report_rejects_short_or_dirty_transcript(tmp_path: Path):
    run_paths = create_run(tmp_path, "dirty-quality")
    dirty_text = (
        "Useful transcript text still contains <c>caption tags</c>, "
        "<00:00:03.000> inline timing, and &nbsp; HTML entities. "
    )
    _write_normalized(run_paths, [dirty_text] * 6)

    report = read_json(write_transcript_quality(run_paths))

    assert report["recommendation"] == "reject"
    assert report["metrics"]["dirty_markup_count"] >= 3
    assert report["metrics"]["html_entity_count"] >= 3
    assert "dirty_markup" in report["reasons"]


def test_quality_report_flags_fragmented_or_repetitive_transcript_for_inspection(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path, "inspect-quality")
    repeated = ["AI agents can call tools."] * 24
    _write_normalized(run_paths, repeated)

    report = read_json(write_transcript_quality(run_paths))

    assert report["recommendation"] == "inspect_first"
    assert report["flags"]["too_fragmented"] is True
    assert report["flags"]["too_repetitive"] is True
    assert report["metrics"]["repeated_line_score"] > 0.5
