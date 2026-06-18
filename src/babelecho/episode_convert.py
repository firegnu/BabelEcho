from pathlib import Path
from urllib.parse import urlparse


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _with_optional_title(source: dict, title: str | None) -> dict:
    if title:
        return {**source, "title": title}
    return source


def _is_youtube_url(parsed) -> bool:
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in YOUTUBE_HOSTS


def build_on_demand_source_config(
    episode_input: str,
    *,
    title: str | None = None,
    language: str = "en",
) -> dict:
    parsed = urlparse(episode_input)
    if _is_youtube_url(parsed):
        source = {
            "type": "youtube_captions",
            "url": episode_input,
            "language": language,
            "original_url": episode_input,
        }
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
