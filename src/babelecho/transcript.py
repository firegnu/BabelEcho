import re
from pathlib import Path

from .jsonio import read_json, write_json
from .paths import RunPaths
from .transcript_quality import write_transcript_quality

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
STAGE_MARKER_RE = re.compile(r"(?:\[[^\]]+\]\s*)+[.!?。！？]*")
TRANSCRIPT_BOILERPLATE_PHRASES = (
    "transcripts are created",
    "may not be in their final form",
    "may be updated or revised",
    "authoritative record is the audio record",
    "authoritative record of",
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


def _split_speaker_turns(
    text: str,
    *,
    infer_speaker_labels: bool = True,
) -> list[tuple[str | None, str]]:
    normalized = " ".join(text.split())
    if not infer_speaker_labels:
        return [(None, normalized)]
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
    *,
    infer_speaker_labels: bool = True,
) -> list[dict]:
    segments = []
    for offset, (speaker, segment_text) in enumerate(
        _split_speaker_turns(text, infer_speaker_labels=infer_speaker_labels)
    ):
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


def _is_stage_marker(text: str) -> bool:
    return bool(STAGE_MARKER_RE.fullmatch(" ".join(text.split())))


def _is_transcript_boilerplate(text: str) -> bool:
    normalized = " ".join(text.split()).casefold()
    if (
        ("copyright" in normalized or "©" in text)
        and ("all rights reserved" in normalized or "terms of use" in normalized)
    ):
        return True
    return any(phrase in normalized for phrase in TRANSCRIPT_BOILERPLATE_PHRASES)


def parse_plain_text(content: str, *, infer_speaker_labels: bool = True) -> list[dict]:
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()
    ]
    segments: list[dict] = []
    last_speaker: str | None = None
    can_inherit_speaker = False
    for paragraph in paragraphs:
        turns = _split_speaker_turns(
            paragraph,
            infer_speaker_labels=infer_speaker_labels,
        )
        if (
            len(turns) == 1
            and turns[0][0] is None
            and last_speaker
            and can_inherit_speaker
            and not _is_stage_marker(turns[0][1])
        ):
            turns = [(last_speaker, turns[0][1])]

        for speaker, segment_text in turns:
            segments.append(
                _segment(
                    len(segments) + 1,
                    segment_text,
                    None,
                    None,
                    speaker,
                )
            )

        paragraph_speakers = [speaker for speaker, _text in turns if speaker]
        if len(turns) == 1 and paragraph_speakers:
            last_speaker = paragraph_speakers[0]
            can_inherit_speaker = True
        elif paragraph_speakers:
            last_speaker = paragraph_speakers[-1]
            can_inherit_speaker = False
        else:
            last_speaker = None
            can_inherit_speaker = False
    return segments


def parse_timed_text(content: str, *, infer_speaker_labels: bool = True) -> list[dict]:
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
                infer_speaker_labels=infer_speaker_labels,
            )
        )
    return segments


def _infer_speaker_labels_for_run(run_paths: RunPaths) -> bool:
    if not run_paths.source_json.exists():
        return True
    source = read_json(run_paths.source_json)
    return source.get("source_type") != "youtube_captions"


def _youtube_start_ms_for_run(run_paths: RunPaths) -> int | None:
    if not run_paths.source_json.exists():
        return None
    source = read_json(run_paths.source_json)
    if source.get("source_type") != "youtube_captions":
        return None
    value = source.get("youtube_start_ms")
    if value is None:
        return None
    return int(value)


def _renumber_segments(segments: list[dict]) -> list[dict]:
    return [
        {
            **segment,
            "id": f"{index:04d}",
        }
        for index, segment in enumerate(segments, start=1)
    ]


def _filter_non_spoken_segments(segments: list[dict]) -> list[dict]:
    kept = [
        segment
        for segment in segments
        if not _is_stage_marker(str(segment.get("text", "")))
        and not _is_transcript_boilerplate(str(segment.get("text", "")))
    ]
    return _renumber_segments(kept)


def _apply_youtube_start_offset(run_paths: RunPaths, segments: list[dict]) -> list[dict]:
    youtube_start_ms = _youtube_start_ms_for_run(run_paths)
    if youtube_start_ms is None:
        return segments
    kept = [
        segment
        for segment in segments
        if segment.get("end_ms") is None or int(segment["end_ms"]) > youtube_start_ms
    ]
    return _renumber_segments(kept)


def normalize_transcript(run_paths: RunPaths, raw_path: str | Path) -> Path:
    source = Path(raw_path)
    content = source.read_text(encoding="utf-8")
    suffix = source.suffix.lower()
    infer_speaker_labels = _infer_speaker_labels_for_run(run_paths)
    if suffix in {".vtt", ".srt"}:
        segments = parse_timed_text(content, infer_speaker_labels=infer_speaker_labels)
    else:
        segments = parse_plain_text(content, infer_speaker_labels=infer_speaker_labels)
    segments = _apply_youtube_start_offset(run_paths, segments)
    segments = _filter_non_spoken_segments(segments)
    if not segments:
        raise ValueError(f"No transcript segments parsed from {source}")
    output = {
        "episode_id": run_paths.run_id,
        "language": "en",
        "segments": segments,
    }
    write_json(run_paths.normalized_transcript_json, output)
    write_transcript_quality(run_paths, run_paths.normalized_transcript_json)
    return run_paths.normalized_transcript_json
