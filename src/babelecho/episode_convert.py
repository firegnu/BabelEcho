from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .youtube import parse_youtube_start_ms


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _with_optional_title(source: dict, title: str | None) -> dict:
    if title:
        return {**source, "title": title}
    return source


def _is_youtube_url(parsed) -> bool:
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in YOUTUBE_HOSTS


def _is_single_youtube_episode_url(parsed) -> bool:
    path = parsed.path.rstrip("/")
    if parse_qs(parsed.query).get("list"):
        return False
    if path.startswith(("/playlist", "/channel", "/c/", "/@")):
        return False
    if parsed.netloc.lower() == "youtu.be":
        return bool(path.strip("/"))
    return path in {"", "/watch"} and bool(parse_qs(parsed.query).get("v"))


def build_on_demand_source_config(
    episode_input: str,
    *,
    title: str | None = None,
    language: str = "en",
) -> dict:
    parsed = urlparse(episode_input)
    if _is_youtube_url(parsed):
        if not _is_single_youtube_episode_url(parsed):
            raise ValueError("YouTube input must be a single YouTube episode/video URL")
        source = {
            "type": "youtube_captions",
            "url": episode_input,
            "language": language,
            "original_url": episode_input,
        }
        youtube_start_ms = parse_youtube_start_ms(episode_input)
        if youtube_start_ms is not None:
            source["youtube_start_ms"] = youtube_start_ms
        return {"source": _with_optional_title(source, title)}

    if parsed.scheme in {"http", "https"} and parsed.netloc:
        source = {
            "type": "episode_page",
            "page_url": episode_input,
            "original_url": episode_input,
        }
        return {"source": _with_optional_title(source, title)}

    local_path = Path(episode_input)
    if local_path.exists():
        source = {
            "type": "episode_page",
            "page_url": str(local_path),
            "original_url": str(local_path),
        }
        return {"source": _with_optional_title(source, title)}

    raise ValueError(f"Unsupported episode input: {episode_input}")
