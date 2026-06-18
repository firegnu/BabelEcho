import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .jsonio import write_json
from .paths import RunPaths


TIMESTAMP_RE = re.compile(
    r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[,.]\d{3}"
)
SPEAKER_RE = re.compile(r"(?m)^\s*([A-Z][A-Za-z0-9'. -]{0,60}):\s+\S")


@dataclass(frozen=True)
class TranscriptCandidate:
    source_type: str
    source_url: str | None
    raw_path: str | None
    cleaned_path: str | None
    format: str
    language: str | None
    title: str | None
    score: int
    selected: bool
    warnings: list[str]
    rejection_reason: str | None
    text_char_count: int
    segment_count_estimate: int
    speaker_count_estimate: int
    has_timestamps: bool


def _relative_run_path(run_paths: RunPaths, path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(run_paths.run_dir))


def _format_for_path(path: Path | None) -> str:
    if path is None:
        return "unknown"
    return path.suffix.lower().lstrip(".") or "unknown"


def _text_lines(content: str) -> list[str]:
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "WEBVTT" or TIMESTAMP_RE.search(stripped):
            continue
        lines.append(stripped)
    return lines


def _score_candidate(
    *,
    transcript_format: str,
    language: str | None,
    has_timestamps: bool,
    speaker_count: int,
    rejection_reason: str | None,
) -> int:
    if rejection_reason:
        return 0
    score = 10
    if transcript_format in {"vtt", "srt", "txt"}:
        score += 20
    if language == "en":
        score += 10
    if has_timestamps:
        score += 10
    if speaker_count:
        score += 5
    return score


def build_youtube_candidate(
    run_paths: RunPaths,
    *,
    source_url: str | None,
    raw_path: Path | None,
    language: str | None,
    selected: bool,
    cleaned_path: Path | None = None,
    rejection_reason: str | None = None,
) -> TranscriptCandidate:
    transcript_format = _format_for_path(raw_path)
    content = raw_path.read_text(encoding="utf-8", errors="replace") if raw_path else ""
    text_lines = _text_lines(content)
    text_char_count = sum(len(line) for line in text_lines)
    timestamp_count = len(TIMESTAMP_RE.findall(content))
    segment_count = timestamp_count or len([line for line in text_lines if line])
    speaker_count = len(set(SPEAKER_RE.findall(content)))
    has_timestamps = timestamp_count > 0
    warnings = []
    if raw_path and text_char_count < 1000:
        warnings.append("short transcript")
    if raw_path and segment_count > 1000 and text_char_count / max(segment_count, 1) < 60:
        warnings.append("highly fragmented captions")

    return TranscriptCandidate(
        source_type="youtube_captions",
        source_url=source_url,
        raw_path=_relative_run_path(run_paths, raw_path),
        cleaned_path=_relative_run_path(run_paths, cleaned_path),
        format=transcript_format,
        language=language,
        title=None,
        score=_score_candidate(
            transcript_format=transcript_format,
            language=language,
            has_timestamps=has_timestamps,
            speaker_count=speaker_count,
            rejection_reason=rejection_reason,
        ),
        selected=selected,
        warnings=warnings,
        rejection_reason=rejection_reason,
        text_char_count=text_char_count,
        segment_count_estimate=segment_count,
        speaker_count_estimate=speaker_count,
        has_timestamps=has_timestamps,
    )


def write_candidates_json(
    run_paths: RunPaths,
    candidates: list[TranscriptCandidate],
) -> Path:
    selected = next((candidate for candidate in candidates if candidate.selected), None)
    output = run_paths.transcript_dir / "candidates.json"
    write_json(
        output,
        {
            "selected": asdict(selected) if selected else None,
            "candidates": [asdict(candidate) for candidate in candidates],
        },
    )
    return output
