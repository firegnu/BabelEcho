import subprocess
from pathlib import Path

from .jsonio import read_json
from .paths import RunPaths


def _ffmpeg_concat_line(path: Path) -> str:
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'"


def assemble_audio(run_paths: RunPaths, audio_config: dict | None = None) -> str:
    manifest = read_json(run_paths.segments_dir / "manifest.json")
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
