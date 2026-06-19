from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .jsonio import write_json
from .paths import RunPaths


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _relative(run_paths: RunPaths, path: Path) -> str:
    try:
        return str(path.relative_to(run_paths.run_dir))
    except ValueError:
        return str(path.relative_to(run_paths.workspace))


def _stage(status: dict[str, Any], name: str) -> dict[str, Any]:
    for stage in status["stages"]:
        if stage["name"] == name:
            return stage
    raise ValueError(f"Unknown pipeline stage: {name}")


def collect_outputs(run_paths: RunPaths) -> dict[str, str]:
    outputs: dict[str, str] = {}
    candidates = {
        "source": run_paths.source_json,
        "audio_metadata": run_paths.run_dir / "audio" / "metadata.json",
        "asr_raw": run_paths.run_dir / "asr" / "raw.json",
        "asr_diarization": run_paths.run_dir / "asr" / "diarization.json",
        "speaker_profiles": run_paths.run_dir / "asr" / "speaker-profiles.json",
        "normalized": run_paths.normalized_transcript_json,
        "transcript_quality": run_paths.transcript_quality_json,
        "script": run_paths.chinese_script_json,
        "segments_manifest": run_paths.segments_dir / "manifest.json",
        "audio": run_paths.output_audio,
        "feed": run_paths.publish_dir / "feed.xml",
        "stable_feed": run_paths.stable_feed,
    }
    for name, path in candidates.items():
        if path.exists():
            outputs[name] = _relative(run_paths, path)
    return outputs


def init_run_status(
    run_paths: RunPaths,
    *,
    from_stage: str,
    to_stage: str,
    input_info: dict[str, Any],
    stages: tuple[str, ...],
) -> dict[str, Any]:
    start_index = stages.index(from_stage)
    stop_index = stages.index(to_stage)
    status = {
        "run_id": run_paths.run_id,
        "status": "running",
        "from_stage": from_stage,
        "to_stage": to_stage,
        "input": input_info,
        "current_stage": None,
        "failed_stage": None,
        "error": None,
        "outputs": collect_outputs(run_paths),
        "started_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
        "stages": [
            {
                "name": stage,
                "status": "skipped" if index < start_index or index > stop_index else "pending",
            }
            for index, stage in enumerate(stages)
        ],
    }
    write_json(run_paths.run_json, status)
    return status


def mark_stage_running(status: dict[str, Any], run_paths: RunPaths, stage_name: str) -> None:
    stage = _stage(status, stage_name)
    stage["status"] = "running"
    stage["started_at"] = _now()
    status["status"] = "running"
    status["current_stage"] = stage_name
    status["updated_at"] = _now()
    status["outputs"] = collect_outputs(run_paths)
    write_json(run_paths.run_json, status)


def mark_stage_succeeded(status: dict[str, Any], run_paths: RunPaths, stage_name: str) -> None:
    stage = _stage(status, stage_name)
    stage["status"] = "succeeded"
    stage["completed_at"] = _now()
    status["updated_at"] = _now()
    status["outputs"] = collect_outputs(run_paths)
    write_json(run_paths.run_json, status)


def mark_stage_failed(
    status: dict[str, Any],
    run_paths: RunPaths,
    stage_name: str,
    error: Exception,
) -> None:
    stage = _stage(status, stage_name)
    stage["status"] = "failed"
    stage["completed_at"] = _now()
    status["status"] = "failed"
    status["current_stage"] = stage_name
    status["failed_stage"] = stage_name
    status["error"] = str(error)
    status["outputs"] = collect_outputs(run_paths)
    status["updated_at"] = _now()
    status["completed_at"] = _now()
    write_json(run_paths.run_json, status)


def mark_run_succeeded(status: dict[str, Any], run_paths: RunPaths) -> None:
    status["status"] = "succeeded"
    status["current_stage"] = None
    status["failed_stage"] = None
    status["error"] = None
    status["outputs"] = collect_outputs(run_paths)
    status["updated_at"] = _now()
    status["completed_at"] = _now()
    write_json(run_paths.run_json, status)
