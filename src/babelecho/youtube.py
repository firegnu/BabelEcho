from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any


DEFAULT_YT_DLP_COMMAND = "yt-dlp"
SUPPORTED_SUBTITLE_SUFFIXES = (".vtt", ".srt", ".txt")


@dataclass(frozen=True)
class YouTubeCaptions:
    path: Path
    language: str


def fetch_youtube_captions(
    source_config: dict[str, Any],
    output_dir: str | Path,
) -> YouTubeCaptions:
    url = _required_config_value(source_config, "url")
    language = str(source_config.get("language") or "en")
    command = str(source_config.get("yt_dlp_command") or DEFAULT_YT_DLP_COMMAND)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_template = target_dir / "captions.%(ext)s"
    args = [
        command,
        "--skip-download",
        "--no-playlist",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        language,
        "--sub-format",
        "vtt/srt/best",
        "-o",
        str(output_template),
        url,
    ]
    result = subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or str(result.returncode)
        raise ValueError(f"yt-dlp failed while fetching YouTube subtitles: {message}")

    subtitle_path = _select_subtitle_file(target_dir)
    return YouTubeCaptions(
        path=subtitle_path,
        language=_subtitle_language(subtitle_path) or language,
    )


def _required_config_value(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if value is None or value == "":
        raise ValueError(f"source.{key} is required")
    return str(value)


def _select_subtitle_file(output_dir: Path) -> Path:
    candidates = [
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUBTITLE_SUFFIXES
    ]
    if not candidates:
        raise ValueError("No YouTube subtitles downloaded")
    priority = {suffix: index for index, suffix in enumerate(SUPPORTED_SUBTITLE_SUFFIXES)}
    return sorted(candidates, key=lambda path: (priority[path.suffix.lower()], path.name))[0]


def _subtitle_language(path: Path) -> str | None:
    parts = path.name.split(".")
    if len(parts) >= 3 and parts[0] == "captions":
        return parts[-2]
    return None
