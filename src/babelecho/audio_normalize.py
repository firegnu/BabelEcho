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
        segment["speaker"] = _speaker_for_segment(segment, diarization, warnings)
        segments.append(segment)

    metrics = {
        "avg_confidence": (
            round(sum(confidences) / len(confidences), 3) if confidences else None
        ),
        "low_confidence_segment_count": low_confidence_count,
        "timestamp_error_count": timestamp_error_count,
        "empty_segment_count": empty_segment_count,
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
        "asr_segment_crosses_speaker_turns",
        "low_confidence_segments",
        "missing_diarization_overlap",
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
