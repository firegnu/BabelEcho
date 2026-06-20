import re
from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json
from .paths import RunPaths


LOW_CONFIDENCE_THRESHOLD = 0.75
SHORT_SPEAKER_TURN_MS = 1_000
MANY_SHORT_SPEAKER_TURNS = 20
MERGE_MAX_GAP_MS = 1_500
MERGE_MAX_CHARS = 280
MERGE_MAX_DURATION_MS = 45_000
AMBIGUOUS_PRIMARY_OVERLAP_RATIO = 0.60
AMBIGUOUS_SEGMENT_COUNT_INSPECT_THRESHOLD = 3
AMBIGUOUS_SEGMENT_RATIO_INSPECT_THRESHOLD = 0.05
BOUNDARY_CONTENT_WINDOW_MS = 120_000
BOUNDARY_CONTENT_MAX_SEGMENTS = 8

HIGH_CONFIDENCE_BOUNDARY_CONTENT_PATTERNS = (
    re.compile(r"\bsupported by (?:ads|advertising)\b", re.IGNORECASE),
    re.compile(r"\b(?:advertisement|advertising|sponsored by|brought to you by)\b", re.IGNORECASE),
    re.compile(r"\bthis tv broadcast\b.*\bwebsite\b", re.IGNORECASE),
    re.compile(r"\bbbc\s+(?:nl|sounds|iplayer)\b.*\b(?:drama|series|comedy|watch|listen|download)\b", re.IGNORECASE),
    re.compile(r"\bbest of brits\b", re.IGNORECASE),
)
POSSIBLE_BOUNDARY_CONTENT_PATTERNS = (
    re.compile(r"\bfor more information\b", re.IGNORECASE),
    re.compile(r"\bvisit (?:our|the) website\b", re.IGNORECASE),
    re.compile(r"\bdownload (?:the )?(?:bbc )?(?:sounds )?app\b", re.IGNORECASE),
    re.compile(r"\bsubscribe\b|\bfollow us\b|\brate and review\b", re.IGNORECASE),
)
MAIN_INTRO_PATTERNS = (
    re.compile(r"^(?:hello|hi|welcome)\b.*\b(?:this is|to)\b", re.IGNORECASE),
    re.compile(r"\bthis is\b.{0,80}\b(?:podcast|show|episode|programme|program|english)\b", re.IGNORECASE),
    re.compile(r"\bin this (?:episode|programme|program)\b", re.IGNORECASE),
)
FAREWELL_PATTERNS = (
    re.compile(r"\bgoodbye\b|\bbye for now\b|\bsee you again soon\b", re.IGNORECASE),
    re.compile(r"\bour .* time .* up\b|\bonce again,? our .* minutes are up\b", re.IGNORECASE),
)


def _asr_raw_path(run_paths: RunPaths) -> Path:
    return run_paths.run_dir / "asr" / "raw.json"


def _diarization_path(run_paths: RunPaths) -> Path:
    return run_paths.run_dir / "asr" / "diarization.json"


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _require_int(value: Any, context: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{context} must be an integer")
    return value


def _source_type(run_paths: RunPaths) -> str | None:
    if not run_paths.source_json.exists():
        return None
    source = read_json(run_paths.source_json)
    return source.get("source_type")


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _speaker_for_segment(
    segment: dict[str, Any],
    diarization: dict[str, Any],
    warnings: list[str],
    cross_speaker_stats: dict[str, Any],
) -> str | None:
    turns = diarization.get("segments") or []
    if diarization.get("provider") == "none" or not turns:
        return "speaker_1"

    overlaps = [
        (
            _overlap_ms(
                segment["start_ms"],
                segment["end_ms"],
                turn["start_ms"],
                turn["end_ms"],
            ),
            turn.get("speaker"),
        )
        for turn in turns
    ]
    matches = [(overlap, speaker) for overlap, speaker in overlaps if overlap > 0]
    if not matches:
        _add_warning(warnings, "missing_diarization_overlap")
        return None
    if len(matches) > 1:
        _add_warning(warnings, "asr_segment_crosses_speaker_turns")
        primary_overlap = max(overlap for overlap, _speaker in matches)
        total_overlap = sum(overlap for overlap, _speaker in matches)
        if total_overlap > 0:
            primary_overlap_ratio = primary_overlap / total_overlap
            cross_speaker_stats["primary_overlap_ratios"].append(primary_overlap_ratio)
            if primary_overlap_ratio < AMBIGUOUS_PRIMARY_OVERLAP_RATIO:
                cross_speaker_stats["ambiguous_count"] += 1
        cross_speaker_stats["count"] += 1
    return max(matches, key=lambda item: item[0])[1]


def _add_warning(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def _normalized_asr_segments(
    raw_asr: dict[str, Any],
    diarization: dict[str, Any],
    warnings: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_segments = raw_asr.get("segments")
    if not isinstance(raw_segments, list):
        raise ValueError("ASR raw segments must be a list")

    segments: list[dict[str, Any]] = []
    timestamp_error_count = 0
    empty_segment_count = 0
    previous_end: int | None = None
    confidences: list[float] = []
    low_confidence_count = 0
    cross_speaker_stats: dict[str, Any] = {
        "count": 0,
        "ambiguous_count": 0,
        "primary_overlap_ratios": [],
    }

    for raw_index, raw_segment in enumerate(raw_segments, start=1):
        item = _require_mapping(raw_segment, f"ASR segment {raw_index}")
        start_ms = _require_int(item.get("start_ms"), f"ASR segment {raw_index} start_ms")
        end_ms = _require_int(item.get("end_ms"), f"ASR segment {raw_index} end_ms")
        if end_ms <= start_ms:
            raise ValueError(f"ASR segment {raw_index} end_ms must be after start_ms")
        if previous_end is not None and start_ms < previous_end:
            timestamp_error_count += 1
            _add_warning(warnings, "timestamp_errors")
        previous_end = end_ms

        confidence = item.get("confidence")
        if isinstance(confidence, int | float):
            confidences.append(float(confidence))
            if float(confidence) < LOW_CONFIDENCE_THRESHOLD:
                low_confidence_count += 1
                _add_warning(warnings, "low_confidence_segments")

        text = str(item.get("text") or "").strip()
        if not text:
            empty_segment_count += 1
            _add_warning(warnings, "empty_asr_segments")
            continue

        segment = {
            "id": f"{len(segments) + 1:04d}",
            "start_ms": start_ms,
            "end_ms": end_ms,
            "speaker": None,
            "text": " ".join(text.split()),
            "source": "asr",
        }
        segment["speaker"] = _speaker_for_segment(
            segment,
            diarization,
            warnings,
            cross_speaker_stats,
        )
        segments.append(segment)

    cross_speaker_count = int(cross_speaker_stats["count"])
    ambiguous_speaker_count = int(cross_speaker_stats["ambiguous_count"])
    cross_speaker_ratios = cross_speaker_stats["primary_overlap_ratios"]
    metrics = {
        "avg_confidence": (
            round(sum(confidences) / len(confidences), 3) if confidences else None
        ),
        "low_confidence_segment_count": low_confidence_count,
        "timestamp_error_count": timestamp_error_count,
        "empty_segment_count": empty_segment_count,
        "cross_speaker_segment_count": cross_speaker_count,
        "cross_speaker_segment_ratio": (
            round(cross_speaker_count / len(raw_segments), 3) if raw_segments else 0
        ),
        "ambiguous_speaker_segment_count": ambiguous_speaker_count,
        "ambiguous_speaker_segment_ratio": (
            round(ambiguous_speaker_count / len(raw_segments), 3)
            if raw_segments
            else 0
        ),
        "min_primary_speaker_overlap_ratio": (
            round(min(cross_speaker_ratios), 3) if cross_speaker_ratios else None
        ),
        "avg_primary_speaker_overlap_ratio": (
            round(sum(cross_speaker_ratios) / len(cross_speaker_ratios), 3)
            if cross_speaker_ratios
            else None
        ),
    }
    return _merge_adjacent_same_speaker_segments(segments), metrics


def _can_merge(current: dict[str, Any], next_segment: dict[str, Any]) -> bool:
    if current.get("speaker") != next_segment.get("speaker"):
        return False
    if current.get("speaker") is None:
        return False
    gap_ms = int(next_segment["start_ms"]) - int(current["end_ms"])
    if gap_ms < 0 or gap_ms > MERGE_MAX_GAP_MS:
        return False
    merged_text = " ".join([current["text"], next_segment["text"]]).strip()
    if len(merged_text) > MERGE_MAX_CHARS:
        return False
    if int(next_segment["end_ms"]) - int(current["start_ms"]) > MERGE_MAX_DURATION_MS:
        return False
    return True


def _merge_adjacent_same_speaker_segments(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for segment in segments:
        if merged and _can_merge(merged[-1], segment):
            previous = merged[-1]
            merged[-1] = {
                **previous,
                "end_ms": segment["end_ms"],
                "text": " ".join([previous["text"], segment["text"]]).strip(),
            }
        else:
            merged.append({**segment})
    return [
        {
            **segment,
            "id": f"{index:04d}",
        }
        for index, segment in enumerate(merged, start=1)
    ]


def _matches_any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _is_high_confidence_boundary_content(segment: dict[str, Any]) -> bool:
    text = str(segment.get("text") or "")
    return _matches_any(HIGH_CONFIDENCE_BOUNDARY_CONTENT_PATTERNS, text)


def _is_possible_boundary_content(segment: dict[str, Any]) -> bool:
    text = str(segment.get("text") or "")
    return _matches_any(POSSIBLE_BOUNDARY_CONTENT_PATTERNS, text)


def _is_main_intro(segment: dict[str, Any]) -> bool:
    text = str(segment.get("text") or "")
    return _matches_any(MAIN_INTRO_PATTERNS, text)


def _is_farewell(segment: dict[str, Any]) -> bool:
    text = str(segment.get("text") or "")
    return _matches_any(FAREWELL_PATTERNS, text)


def _leading_boundary_indices(segments: list[dict[str, Any]]) -> list[int]:
    if not segments:
        return []
    first_start = int(segments[0]["start_ms"])
    indices = []
    for index, segment in enumerate(segments[:BOUNDARY_CONTENT_MAX_SEGMENTS]):
        if int(segment["start_ms"]) - first_start > BOUNDARY_CONTENT_WINDOW_MS:
            break
        indices.append(index)
    return indices


def _trailing_boundary_indices(segments: list[dict[str, Any]]) -> list[int]:
    if not segments:
        return []
    last_end = int(segments[-1]["end_ms"])
    start_index = max(0, len(segments) - BOUNDARY_CONTENT_MAX_SEGMENTS)
    indices = []
    for index in range(start_index, len(segments)):
        if last_end - int(segments[index]["end_ms"]) <= BOUNDARY_CONTENT_WINDOW_MS:
            indices.append(index)
    return indices


def _renumber_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **segment,
            "id": f"{index:04d}",
        }
        for index, segment in enumerate(segments, start=1)
    ]


def _boundary_content_cleanup(
    segments: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dropped_indices: set[int] = set()
    leading_indices = _leading_boundary_indices(segments)
    intro_index = next(
        (index for index in leading_indices if _is_main_intro(segments[index])),
        None,
    )
    if intro_index is not None and any(
        _is_high_confidence_boundary_content(segments[index])
        for index in leading_indices
        if index < intro_index
    ):
        dropped_indices.update(range(0, intro_index))
    else:
        for index in leading_indices:
            if _is_high_confidence_boundary_content(segments[index]):
                dropped_indices.add(index)

    trailing_indices = _trailing_boundary_indices(segments)
    farewell_index = next(
        (
            index
            for index in reversed(trailing_indices)
            if _is_farewell(segments[index])
        ),
        None,
    )
    if farewell_index is not None and any(
        _is_high_confidence_boundary_content(segments[index])
        for index in trailing_indices
        if index > farewell_index
    ):
        dropped_indices.update(range(farewell_index + 1, len(segments)))
    else:
        for index in trailing_indices:
            if _is_high_confidence_boundary_content(segments[index]):
                dropped_indices.add(index)

    cleaned = [
        segment for index, segment in enumerate(segments) if index not in dropped_indices
    ]
    possible_count = sum(
        1
        for index in set(_leading_boundary_indices(cleaned) + _trailing_boundary_indices(cleaned))
        if _is_possible_boundary_content(cleaned[index])
        and not _is_high_confidence_boundary_content(cleaned[index])
    )

    if dropped_indices:
        _add_warning(warnings, "dropped_boundary_content_segments")
    if possible_count:
        _add_warning(warnings, "possible_boundary_content_segments")

    return _renumber_segments(cleaned), {
        "dropped_boundary_content_segment_count": len(dropped_indices),
        "possible_boundary_content_segment_count": possible_count,
    }


def _speaker_turn_metrics(diarization: dict[str, Any]) -> dict[str, Any]:
    turns = diarization.get("segments") or []
    durations = [
        int(turn["end_ms"]) - int(turn["start_ms"])
        for turn in turns
        if isinstance(turn.get("start_ms"), int)
        and isinstance(turn.get("end_ms"), int)
        and int(turn["end_ms"]) > int(turn["start_ms"])
    ]
    short_count = sum(1 for duration in durations if duration < SHORT_SPEAKER_TURN_MS)
    return {
        "speaker_turn_count": len(turns),
        "avg_speaker_turn_ms": (
            round(sum(durations) / len(durations), 1) if durations else None
        ),
        "short_speaker_turn_count": short_count,
    }


def _quality_report(
    *,
    run_paths: RunPaths,
    segments: list[dict[str, Any]],
    diarization: dict[str, Any],
    segment_metrics: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    if diarization.get("provider") == "none":
        for warning in diarization.get("warnings") or ["diarization_disabled"]:
            _add_warning(warnings, str(warning))

    speaker_turn_metrics = _speaker_turn_metrics(diarization)
    if (
        speaker_turn_metrics["short_speaker_turn_count"] >= MANY_SHORT_SPEAKER_TURNS
    ):
        _add_warning(warnings, "too_many_short_speaker_turns")
    ambiguous_count = int(segment_metrics.get("ambiguous_speaker_segment_count") or 0)
    ambiguous_ratio = float(segment_metrics.get("ambiguous_speaker_segment_ratio") or 0)
    if ambiguous_count and (
        ambiguous_count >= AMBIGUOUS_SEGMENT_COUNT_INSPECT_THRESHOLD
        or ambiguous_ratio >= AMBIGUOUS_SEGMENT_RATIO_INSPECT_THRESHOLD
    ):
        _add_warning(warnings, "ambiguous_speaker_assignments")

    texts = [str(segment.get("text") or "") for segment in segments]
    speakers = {
        str(segment.get("speaker")).strip()
        for segment in segments
        if segment.get("speaker")
    }
    reasons = []
    if not segments:
        reasons.append("empty_transcript")

    inspect_warnings = {
        "low_confidence_segments",
        "missing_diarization_overlap",
        "ambiguous_speaker_assignments",
        "timestamp_errors",
        "too_many_short_speaker_turns",
    }
    if reasons:
        recommendation = "reject"
    elif any(warning in inspect_warnings for warning in warnings):
        recommendation = "inspect_first"
    else:
        recommendation = "safe_to_adapt"

    return {
        "recommendation": recommendation,
        "metrics": {
            "segment_count": len(segments),
            "speaker_count": len(speakers),
            "total_chars": sum(len(text) for text in texts),
            **segment_metrics,
            **speaker_turn_metrics,
            "source_type": _source_type(run_paths),
            "extractor": "asr",
        },
        "warnings": warnings,
        "reasons": reasons,
    }


def normalize_audio_transcript(run_paths: RunPaths) -> Path:
    raw_asr = _require_mapping(read_json(_asr_raw_path(run_paths)), "ASR raw")
    diarization_path = _diarization_path(run_paths)
    if diarization_path.exists():
        diarization = _require_mapping(read_json(diarization_path), "Diarization")
    else:
        diarization = {
            "provider": "none",
            "model": None,
            "speaker_count": 1,
            "segments": [],
            "warnings": ["diarization_disabled"],
        }

    warnings: list[str] = []
    segments, segment_metrics = _normalized_asr_segments(
        raw_asr,
        diarization,
        warnings,
    )
    segments, cleanup_metrics = _boundary_content_cleanup(segments, warnings)
    segment_metrics.update(cleanup_metrics)
    normalized = {
        "episode_id": run_paths.run_id,
        "language": raw_asr.get("language") or "en",
        "segments": segments,
    }
    write_json(run_paths.normalized_transcript_json, normalized)
    write_json(
        run_paths.transcript_quality_json,
        _quality_report(
            run_paths=run_paths,
            segments=segments,
            diarization=diarization,
            segment_metrics=segment_metrics,
            warnings=warnings,
        ),
    )
    return run_paths.normalized_transcript_json
