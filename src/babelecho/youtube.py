from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import parse_qs, urlparse


DEFAULT_YT_DLP_COMMAND = "yt-dlp"
SUPPORTED_SUBTITLE_SUFFIXES = (".vtt", ".srt", ".txt")
YOUTUBE_TIME_RE = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s?)?$"
)


@dataclass(frozen=True)
class YouTubeCaptions:
    path: Path
    language: str
    title: str | None = None


def parse_youtube_start_ms(url: str) -> int | None:
    query = parse_qs(urlparse(url).query)
    values = query.get("t") or query.get("start")
    if not values:
        return None
    return _parse_youtube_time_ms(values[0])


def _parse_youtube_time_ms(value: str) -> int | None:
    raw = value.strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw) * 1000
    match = YOUTUBE_TIME_RE.fullmatch(raw)
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds * 1000 if total_seconds else None


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
    title = _fetch_youtube_title(command, url, output_template)
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
        title=title,
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


def _fetch_youtube_title(command: str, url: str, output_template: Path) -> str | None:
    result = subprocess.run(
        [
            command,
            "--skip-download",
            "--no-playlist",
            "--print",
            "title",
            "-o",
            str(output_template),
            url,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return _title_from_stdout(result.stdout)


def _subtitle_language(path: Path) -> str | None:
    parts = path.name.split(".")
    if len(parts) >= 3 and parts[0] == "captions":
        return parts[-2]
    return None


def _title_from_stdout(stdout: str) -> str | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[-1]
