from html import unescape
import re
from dataclasses import dataclass
from pathlib import Path

from .transcript import parse_timestamp_ms


TIME_LINE_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)
INLINE_TIMING_RE = re.compile(r"<\d{2}:\d{2}:\d{2}[,.]\d{3}>")
CAPTION_TAG_RE = re.compile(r"</?c(?:\.[^>]*)?>")
SPEAKER_ARROW_RE = re.compile(r"(^|\s)>>\s*")
SPEAKER_PREFIX_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9'. -]{0,60}):\s+")
SENTENCE_ENDINGS = (".", "?", "!")
METADATA_PREFIXES = ("NOTE", "STYLE", "REGION")


@dataclass(frozen=True)
class CaptionCue:
    start: str
    end: str
    start_ms: int
    end_ms: int
    text: str


def _blocks(content: str) -> list[list[str]]:
    return [
        [line.strip() for line in block.splitlines() if line.strip()]
        for block in re.split(r"\n\s*\n", content.strip())
        if block.strip()
    ]


def _dedupe_lines(lines: list[str]) -> list[str]:
    deduped = []
    previous = None
    for line in lines:
        if line == previous:
            continue
        deduped.append(line)
        previous = line
    return deduped


def _clean_caption_text(text: str) -> str:
    decoded = unescape(text)
    without_timing = INLINE_TIMING_RE.sub("", decoded)
    without_tags = CAPTION_TAG_RE.sub("", without_timing)
    without_arrows = SPEAKER_ARROW_RE.sub(" ", without_tags)
    return " ".join(without_arrows.split())


def _words(value: str) -> list[str]:
    return value.split()


def _remove_previous_overlap(previous_text: str, current_text: str) -> str:
    previous_words = _words(previous_text)
    current_words = _words(current_text)
    max_overlap = min(len(previous_words), len(current_words))
    for overlap in range(max_overlap, 1, -1):
        if previous_words[-overlap:] == current_words[:overlap]:
            return " ".join(current_words[overlap:])
    return current_text


def _remove_rolling_overlaps(cues: list[CaptionCue]) -> list[CaptionCue]:
    cleaned: list[CaptionCue] = []
    previous_full_text = ""
    previous_end_ms: int | None = None
    for cue in cues:
        text = cue.text
        if previous_end_ms is not None and cue.start_ms - previous_end_ms <= 1_000:
            text = _remove_previous_overlap(previous_full_text, text)
        previous_full_text = cue.text
        previous_end_ms = cue.end_ms
        if not text:
            continue
        cleaned.append(
            CaptionCue(
                start=cue.start,
                end=cue.end,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                text=text,
            )
        )
    return cleaned


def _parse_cues(content: str) -> list[CaptionCue]:
    cues = []
    for block in _blocks(content):
        if block == ["WEBVTT"]:
            continue
        if block[0].startswith(METADATA_PREFIXES):
            continue
        time_index = next(
            (index for index, line in enumerate(block) if TIME_LINE_RE.search(line)),
            None,
        )
        if time_index is None:
            continue
        match = TIME_LINE_RE.search(block[time_index])
        assert match is not None
        text_lines = _dedupe_lines(block[time_index + 1 :])
        text = _clean_caption_text(" ".join(text_lines))
        if not text:
            continue
        cues.append(
            CaptionCue(
                start=match.group("start"),
                end=match.group("end"),
                start_ms=parse_timestamp_ms(match.group("start")),
                end_ms=parse_timestamp_ms(match.group("end")),
                text=text,
            )
        )
    return _remove_rolling_overlaps(cues)


def _speaker_prefix(text: str) -> str | None:
    match = SPEAKER_PREFIX_RE.match(text)
    return match.group(1) if match else None


def _can_merge(current: CaptionCue, next_cue: CaptionCue) -> bool:
    gap_ms = next_cue.start_ms - current.end_ms
    if gap_ms < 0 or gap_ms > 900:
        return False
    if current.text.endswith(SENTENCE_ENDINGS):
        return False
    current_speaker = _speaker_prefix(current.text)
    next_speaker = _speaker_prefix(next_cue.text)
    if current_speaker or next_speaker:
        return current_speaker is not None and current_speaker == next_speaker
    merged_text = f"{current.text} {next_cue.text}"
    if len(merged_text) > 450:
        return False
    if next_cue.end_ms - current.start_ms > 45_000:
        return False
    return True


def _merge_cues(cues: list[CaptionCue]) -> list[CaptionCue]:
    merged: list[CaptionCue] = []
    for cue in cues:
        if merged and _can_merge(merged[-1], cue):
            previous = merged[-1]
            merged[-1] = CaptionCue(
                start=previous.start,
                end=cue.end,
                start_ms=previous.start_ms,
                end_ms=cue.end_ms,
                text=f"{previous.text} {cue.text}",
            )
        else:
            merged.append(cue)
    return merged


def clean_timed_transcript_text(
    content: str,
    transcript_format: str,
    *,
    merge_short_cues: bool = True,
) -> str:
    cues = _parse_cues(content)
    if merge_short_cues:
        cues = _merge_cues(cues)
    prefix = "WEBVTT\n\n" if transcript_format == "vtt" else ""
    body = "\n\n".join(f"{cue.start} --> {cue.end}\n{cue.text}" for cue in cues)
    return f"{prefix}{body}\n" if body else prefix.rstrip() + "\n"


def clean_timed_transcript_file(raw_path: Path, output_path: Path) -> Path:
    transcript_format = raw_path.suffix.lower().lstrip(".")
    cleaned = clean_timed_transcript_text(
        raw_path.read_text(encoding="utf-8", errors="replace"),
        transcript_format,
    )
    output_path.write_text(cleaned, encoding="utf-8")
    return output_path
