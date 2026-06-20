import subprocess
import wave
from pathlib import Path

from .jsonio import read_json, write_json
from .paths import RunPaths


def _ffmpeg_concat_line(path: Path) -> str:
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'"


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
    if rate <= 0:
        return 0
    return round(frames / rate * 1000)


def _annotate_segment_timings(run_paths: RunPaths, manifest: dict) -> None:
    cursor_ms = 0
    for segment in manifest["segments"]:
        audio_path = (run_paths.run_dir / segment["audio_path"]).resolve()
        duration_ms = _wav_duration_ms(audio_path)
        segment["start_ms"] = cursor_ms
        segment["end_ms"] = cursor_ms + duration_ms
        segment["duration_ms"] = duration_ms
        cursor_ms += duration_ms
    write_json(run_paths.segments_dir / "manifest.json", manifest)


def assemble_audio(run_paths: RunPaths, audio_config: dict | None = None) -> str:
    manifest = read_json(run_paths.segments_dir / "manifest.json")
    _annotate_segment_timings(run_paths, manifest)
    concat_path = run_paths.output_dir / "concat.txt"
    lines = []
    for segment in manifest["segments"]:
        audio_path = (run_paths.run_dir / segment["audio_path"]).resolve()
        lines.append(_ffmpeg_concat_line(audio_path))
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    output = run_paths.output_audio
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(output),
    ]
    subprocess.run(command, check=True)
    return str(output)
