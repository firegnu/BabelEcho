import json
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from .jsonio import write_json
from .paths import RunPaths

DOWNLOAD_TIMEOUT_SECONDS = 60
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
KNOWN_AUDIO_SUFFIXES = {".aac", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}


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


def _write_audio_metadata(
    *,
    run_paths: RunPaths,
    audio_path: Path,
    metadata: dict,
) -> None:
    probed, warnings = _probe_audio(audio_path)
    metadata.update(
        {
            "audio_path": _relative_to_run(run_paths, audio_path),
            "duration_seconds": probed["duration_seconds"],
            "sample_rate": probed["sample_rate"],
            "channels": probed["channels"],
            "file_size_bytes": audio_path.stat().st_size,
            "warnings": warnings,
        }
    )
    write_json(_audio_dir(run_paths) / "metadata.json", metadata)


def _audio_url_parts(audio_url: str):
    parsed = urlparse(audio_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source.audio_url must be an http or https URL")
    return parsed


def _audio_suffix_from_url(path: str) -> str:
    suffix = Path(unquote(path)).suffix.lower()
    return suffix if suffix in KNOWN_AUDIO_SUFFIXES else ".audio"


def _audio_filename_from_url(path: str) -> str:
    name = Path(unquote(path)).name
    return name or "audio"


def _download_audio_url(audio_url: str, audio_path: Path) -> None:
    request = Request(audio_url, headers={"User-Agent": "BabelEcho/0.1"})
    try:
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            with audio_path.open("wb") as handle:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise ValueError(f"Failed to download audio URL: {error}") from error


def _ingest_audio_file(source_config: dict, run_paths: RunPaths) -> Path:
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

    metadata_path = audio_dir / "metadata.json"
    _write_audio_metadata(
        run_paths=run_paths,
        audio_path=audio_path,
        metadata={
            "input_kind": "audio_file",
            "original_filename": source.name,
        },
    )
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


def _ingest_audio_url(source_config: dict, run_paths: RunPaths) -> Path:
    audio_url = source_config.get("audio_url")
    if not isinstance(audio_url, str) or not audio_url.strip():
        raise ValueError("source.audio_url is required")
    parsed = _audio_url_parts(audio_url)
    audio_dir = _audio_dir(run_paths)
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"input{_audio_suffix_from_url(parsed.path)}"
    _download_audio_url(audio_url, audio_path)
    _validate_audio_file(audio_path)

    metadata_path = audio_dir / "metadata.json"
    source_path = parsed.path or "/"
    _write_audio_metadata(
        run_paths=run_paths,
        audio_path=audio_path,
        metadata={
            "input_kind": "audio_url",
            "source_host": parsed.netloc,
            "source_path": source_path,
            "original_filename": _audio_filename_from_url(source_path),
        },
    )
    write_json(
        run_paths.source_json,
        {
            "run_id": run_paths.run_id,
            "source_type": "audio_url",
            "provider": "remote_url",
            "title": source_config.get("title")
            or Path(_audio_filename_from_url(source_path)).stem
            or parsed.netloc,
            "source_host": parsed.netloc,
            "source_path": source_path,
            "audio_input": _relative_to_run(run_paths, audio_path),
            "audio_metadata": _relative_to_run(run_paths, metadata_path),
        },
    )
    return audio_path


def ingest_audio_source(source_config: dict, run_paths: RunPaths) -> Path:
    source_type = source_config.get("type")
    if source_type == "audio_file":
        return _ingest_audio_file(source_config, run_paths)
    if source_type == "audio_url":
        return _ingest_audio_url(source_config, run_paths)
    raise ValueError("audio pipeline supports source.type=audio_file or audio_url")
