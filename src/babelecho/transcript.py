import re
from pathlib import Path

from .jsonio import write_json
from .paths import RunPaths

TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)
SPEAKER_LABEL_RE = re.compile(
    r"(?P<prefix>^|(?<=[.!?])\s+)"
    r"(?P<speaker>"
    r"[A-Z][A-Za-z0-9'.-]*(?:\s+\([^)]+\))?"
    r"(?:\s+[A-Z][A-Za-z0-9'.-]*){0,4}"
    r"):\s+"
)


def parse_timestamp_ms(value: str) -> int:
    normalized = value.replace(",", ".")
    hours, minutes, seconds = normalized.split(":")
    whole_seconds, millis = seconds.split(".")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(whole_seconds) * 1_000
        + int(millis)
    )


def _segment(
    segment_id: int,
    text: str,
    start_ms: int | None,
    end_ms: int | None,
    speaker: str | None = None,
) -> dict:
    return {
        "id": f"{segment_id:04d}",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "speaker": speaker,
        "text": " ".join(text.split()),
        "source": "transcript",
    }


def _split_speaker_turns(text: str) -> list[tuple[str | None, str]]:
    normalized = " ".join(text.split())
    matches = list(SPEAKER_LABEL_RE.finditer(normalized))
    if not matches:
        return [(None, normalized)]

    turns: list[tuple[str | None, str]] = []
    current_speaker: str | None = None
    current_start = 0
    for match in matches:
        previous_text = normalized[current_start : match.start()].strip()
        if previous_text:
            turns.append((current_speaker, previous_text))
        current_speaker = match.group("speaker").strip()
        current_start = match.end()

    remaining_text = normalized[current_start:].strip()
    if remaining_text:
        turns.append((current_speaker, remaining_text))
    return turns


def _segments_from_text(
    first_segment_id: int,
    text: str,
    start_ms: int | None,
    end_ms: int | None,
) -> list[dict]:
    segments = []
    for offset, (speaker, segment_text) in enumerate(_split_speaker_turns(text)):
        segments.append(
            _segment(
                first_segment_id + offset,
                segment_text,
                start_ms,
                end_ms,
                speaker,
            )
        )
    return segments


def parse_plain_text(content: str) -> list[dict]:
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()
    ]
    segments: list[dict] = []
    for paragraph in paragraphs:
        segments.extend(_segments_from_text(len(segments) + 1, paragraph, None, None))
    return segments


def parse_timed_text(content: str) -> list[dict]:
    blocks = re.split(r"\n\s*\n", content.strip())
    segments: list[dict] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines == ["WEBVTT"]:
            continue
        time_index = next(
            (index for index, line in enumerate(lines) if TIME_RE.search(line)),
            None,
        )
        if time_index is None:
            continue
        match = TIME_RE.search(lines[time_index])
        assert match is not None
        text_lines = lines[time_index + 1 :]
        if not text_lines:
            continue
        segments.extend(
            _segments_from_text(
                len(segments) + 1,
                " ".join(text_lines),
                parse_timestamp_ms(match.group("start")),
                parse_timestamp_ms(match.group("end")),
            )
        )
    return segments


def normalize_transcript(run_paths: RunPaths, raw_path: str | Path) -> Path:
    source = Path(raw_path)
    content = source.read_text(encoding="utf-8")
    suffix = source.suffix.lower()
    if suffix in {".vtt", ".srt"}:
        segments = parse_timed_text(content)
    else:
        segments = parse_plain_text(content)
    if not segments:
        raise ValueError(f"No transcript segments parsed from {source}")
    output = {
        "episode_id": run_paths.run_id,
        "language": "en",
        "segments": segments,
    }
    write_json(run_paths.normalized_transcript_json, output)
    return run_paths.normalized_transcript_json
