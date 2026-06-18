import re
from pathlib import Path

from .jsonio import read_json, write_json
from .paths import RunPaths

DIRTY_MARKUP_RE = re.compile(r"<[^>\n]{1,80}>")
HTML_ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);")
WORD_RE = re.compile(r"[A-Za-z0-9']+")
MIN_TOTAL_CHARS = 500
FRAGMENTED_SEGMENT_COUNT = 20
FRAGMENTED_AVG_CHARS = 80
HEAVY_MARKUP_COUNT = 3
REPEATED_LINE_SCORE = 0.25
REPEATED_PHRASE_SCORE = 0.35


def _segment_texts(segments: list[dict]) -> list[str]:
    return [str(segment.get("text") or "").strip() for segment in segments]


def _repeated_line_score(texts: list[str]) -> float:
    normalized = [" ".join(text.lower().split()) for text in texts if text.strip()]
    if not normalized:
        return 0.0
    seen: set[str] = set()
    repeated = 0
    for text in normalized:
        if text in seen:
            repeated += 1
        seen.add(text)
    return repeated / len(normalized)


def _repeated_phrase_score(texts: list[str], window_size: int = 5) -> float:
    shingles: list[tuple[str, ...]] = []
    for text in texts:
        tokens = [token.lower() for token in WORD_RE.findall(text)]
        if len(tokens) < window_size:
            continue
        shingles.extend(
            tuple(tokens[index : index + window_size])
            for index in range(len(tokens) - window_size + 1)
        )
    if not shingles:
        return 0.0

    seen: set[tuple[str, ...]] = set()
    repeated = 0
    for shingle in shingles:
        if shingle in seen:
            repeated += 1
        seen.add(shingle)
    return repeated / len(shingles)


def build_transcript_quality_report(normalized_transcript: dict) -> dict:
    segments = normalized_transcript.get("segments") or []
    texts = _segment_texts(segments)
    segment_count = len(segments)
    total_chars = sum(len(text) for text in texts)
    avg_chars = total_chars / segment_count if segment_count else 0.0
    max_chars = max((len(text) for text in texts), default=0)
    speaker_count = len(
        {
            str(segment.get("speaker")).strip()
            for segment in segments
            if segment.get("speaker")
        }
    )
    joined_text = "\n".join(texts)
    dirty_markup_count = len(DIRTY_MARKUP_RE.findall(joined_text))
    html_entity_count = len(HTML_ENTITY_RE.findall(joined_text))
    repeated_line_score = _repeated_line_score(texts)
    repeated_phrase_score = _repeated_phrase_score(texts)

    flags = {
        "empty_transcript": segment_count == 0,
        "too_short": total_chars < MIN_TOTAL_CHARS,
        "too_fragmented": (
            segment_count >= FRAGMENTED_SEGMENT_COUNT
            and avg_chars < FRAGMENTED_AVG_CHARS
        ),
        "too_repetitive": (
            repeated_line_score >= REPEATED_LINE_SCORE
            or repeated_phrase_score >= REPEATED_PHRASE_SCORE
        ),
        "dirty_markup": dirty_markup_count > 0,
        "html_entities": html_entity_count > 0,
    }
    dirty_markup_heavy = dirty_markup_count >= HEAVY_MARKUP_COUNT
    html_entities_heavy = html_entity_count >= HEAVY_MARKUP_COUNT

    reasons = []
    if flags["empty_transcript"]:
        reasons.append("empty_transcript")
    if flags["too_short"]:
        reasons.append("too_short")
    if dirty_markup_heavy:
        reasons.append("dirty_markup")
    if html_entities_heavy:
        reasons.append("html_entities")

    warnings = []
    if flags["too_fragmented"]:
        warnings.append("too_fragmented")
    if flags["too_repetitive"]:
        warnings.append("too_repetitive")
    if flags["dirty_markup"] and not dirty_markup_heavy:
        warnings.append("dirty_markup")
    if flags["html_entities"] and not html_entities_heavy:
        warnings.append("html_entities")

    if reasons:
        recommendation = "reject"
    elif warnings:
        recommendation = "inspect_first"
    else:
        recommendation = "safe_to_adapt"

    report = {
        "recommendation": recommendation,
        "metrics": {
            "segment_count": segment_count,
            "total_chars": total_chars,
            "avg_chars_per_segment": round(avg_chars, 1),
            "max_chars_per_segment": max_chars,
            "speaker_count": speaker_count,
            "dirty_markup_count": dirty_markup_count,
            "html_entity_count": html_entity_count,
            "repeated_line_score": round(repeated_line_score, 3),
            "repeated_phrase_score": round(repeated_phrase_score, 3),
        },
        "flags": flags,
        "reasons": reasons,
        "warnings": warnings,
    }
    return report


def write_transcript_quality(
    run_paths: RunPaths,
    normalized_path: str | Path | None = None,
) -> Path:
    source = Path(normalized_path) if normalized_path else run_paths.normalized_transcript_json
    report = build_transcript_quality_report(read_json(source))
    write_json(run_paths.transcript_quality_json, report)
    return run_paths.transcript_quality_json
