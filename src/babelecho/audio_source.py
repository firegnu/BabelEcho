import json
import shutil
import subprocess
from pathlib import Path

from .jsonio import write_json
from .paths import RunPaths


def _audio_dir(run_paths: RunPaths) -> Path:
    return run_paths.run_dir / "audio"


def _relative_to_run(run_paths: RunPaths, path: Path) -> str:
    return str(path.relative_to(run_paths.run_dir))


def _probe_audio(path: Path) -> tuple[dict, list[str]]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-show_entries",
        "stream=sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, text=True, capture_output=True)
        probed = json.loads(completed.stdout)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {
            "duration_seconds": None,
            "sample_rate": None,
            "channels": None,
        }, ["ffprobe_unavailable_or_failed"]

    stream = (probed.get("streams") or [{}])[0]
    duration = probed.get("format", {}).get("duration")
    return {
        "duration_seconds": float(duration) if duration is not None else None,
        "sample_rate": (
            int(stream["sample_rate"])
            if stream.get("sample_rate") is not None
            else None
        ),
        "channels": int(stream["channels"]) if stream.get("channels") is not None else None,
    }, []


def _validate_audio_file(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"Audio file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Audio input is not a file: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Audio file is empty: {path}")


def ingest_audio_source(source_config: dict, run_paths: RunPaths) -> Path:
    source_type = source_config.get("type")
    if source_type != "audio_file":
        raise ValueError("audio pipeline supports source.type=audio_file")
    audio_file = source_config.get("audio_file")
    if not audio_file:
        raise ValueError("source.audio_file is required")

    source = Path(audio_file)
    _validate_audio_file(source)

    audio_dir = _audio_dir(run_paths)
    audio_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".audio"
    audio_path = audio_dir / f"input{suffix}"
    shutil.copy2(source, audio_path)

    probed, warnings = _probe_audio(audio_path)
    metadata = {
        "input_kind": "audio_file",
        "original_filename": source.name,
        "audio_path": _relative_to_run(run_paths, audio_path),
        "duration_seconds": probed["duration_seconds"],
        "sample_rate": probed["sample_rate"],
        "channels": probed["channels"],
        "file_size_bytes": audio_path.stat().st_size,
        "warnings": warnings,
    }
    metadata_path = audio_dir / "metadata.json"
    write_json(metadata_path, metadata)

    write_json(
        run_paths.source_json,
        {
            "run_id": run_paths.run_id,
            "source_type": "audio_file",
            "provider": "local_file",
            "title": source_config.get("title") or source.stem,
            "audio_input": _relative_to_run(run_paths, audio_path),
            "audio_metadata": _relative_to_run(run_paths, metadata_path),
        },
    )
    return audio_path
