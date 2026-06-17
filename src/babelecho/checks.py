import subprocess

from .jsonio import read_json
from .paths import RunPaths


class CheckError(ValueError):
    pass


def _check_script(run_paths: RunPaths, max_script_chars: int) -> dict:
    if not run_paths.chinese_script_json.exists():
        raise CheckError(f"Missing script: {run_paths.chinese_script_json}")
    script = read_json(run_paths.chinese_script_json)
    segments = script.get("segments", [])
    if not segments:
        raise CheckError(f"No script segments in {run_paths.chinese_script_json}")
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        segment_id = segment.get("id", "<unknown>")
        if not text:
            raise CheckError(f"Script segment {segment_id} has empty text")
        if len(text) > max_script_chars:
            raise CheckError(
                f"Script segment {segment_id} is too long: "
                f"{len(text)} > {max_script_chars}"
            )
    return {"script_segments": len(segments)}


def _check_segments(run_paths: RunPaths) -> dict:
    manifest_path = run_paths.segments_dir / "manifest.json"
    if not manifest_path.exists():
        raise CheckError(f"Missing segment manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    segments = manifest.get("segments", [])
    if not segments:
        raise CheckError(f"No audio segments in {run_paths.segments_dir / 'manifest.json'}")
    for segment in segments:
        audio_path = run_paths.run_dir / segment["audio_path"]
        if not audio_path.exists():
            raise CheckError(f"Missing audio segment: {audio_path}")
        if audio_path.stat().st_size == 0:
            raise CheckError(f"Empty audio segment: {audio_path}")
    return {"audio_segments": len(segments)}


def _check_output(run_paths: RunPaths) -> dict:
    if not run_paths.output_audio.exists():
        raise CheckError(f"Missing output audio: {run_paths.output_audio}")
    if run_paths.output_audio.stat().st_size == 0:
        raise CheckError(f"Empty output audio: {run_paths.output_audio}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_name,sample_rate,channels",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(run_paths.output_audio),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise CheckError(f"ffprobe failed for {run_paths.output_audio}: {error}") from error

    lines = completed.stdout.strip().splitlines()
    if len(lines) < 4:
        raise CheckError(f"Unexpected ffprobe output for {run_paths.output_audio}")
    codec, sample_rate, channels, duration = lines[:4]
    if codec != "mp3":
        raise CheckError(f"Unexpected output codec: {codec}")
    return {
        "output_sample_rate": int(sample_rate),
        "output_channels": int(channels),
        "output_duration_seconds": float(duration),
    }


def check_run_artifacts(
    run_paths: RunPaths,
    checks: tuple[str, ...] = ("script", "segments"),
    max_script_chars: int = 1200,
) -> dict:
    result: dict[str, int] = {}
    if "script" in checks:
        result.update(_check_script(run_paths, max_script_chars))
    if "segments" in checks:
        result.update(_check_segments(run_paths))
    if "output" in checks:
        result.update(_check_output(run_paths))
    return result
