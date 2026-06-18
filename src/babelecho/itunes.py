import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_SEARCH_URL = "https://itunes.apple.com/search"
DEFAULT_USER_AGENT = "BabelEcho/0.1"


def build_itunes_search_url(config: dict[str, Any]) -> str:
    query = {
        "term": _required_config_value(config, "query"),
        "country": str(config.get("country") or "US"),
        "media": "podcast",
        "entity": "podcast",
        "limit": str(int(config.get("max", 10))),
    }
    base_url = str(config.get("api_base_url") or DEFAULT_SEARCH_URL)
    return f"{base_url}?{urlencode(query)}"


def _required_config_value(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if value is None or value == "":
        raise ValueError(f"itunes.{key} is required")
    return str(value)


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def parse_itunes_podcast_results(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("No podcast feeds found in iTunes response")

    results: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "podcast":
            continue
        feed_url = _str_value(item.get("feedUrl"))
        if not feed_url:
            continue
        title = (
            _str_value(item.get("collectionName"))
            or _str_value(item.get("trackName"))
            or "Untitled Podcast"
        )
        result = {
            "title": title,
            "artist": _str_value(item.get("artistName")) or "",
            "feed_url": feed_url,
            "apple_url": _str_value(item.get("collectionViewUrl")) or "",
        }
        results.append(result)

    if not results:
        raise ValueError("No podcast feeds found in iTunes response")
    return results


def fetch_itunes_podcast_search(config: dict[str, Any]) -> list[dict[str, str]]:
    url = build_itunes_search_url(config)
    request = Request(
        url,
        headers={"User-Agent": config.get("user_agent") or DEFAULT_USER_AGENT},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    return parse_itunes_podcast_results(payload)


def build_podcast_rss_source_config(result: dict[str, str]) -> dict[str, dict[str, str]]:
    feed_url = _str_value(result.get("feed_url"))
    if not feed_url:
        raise ValueError("Selected iTunes result has no feed_url")
    source = {
        "type": "podcast_rss",
        "feed_url": feed_url,
        "title": result.get("title") or "Untitled Podcast",
    }
    apple_url = _str_value(result.get("apple_url"))
    if apple_url:
        source["original_url"] = apple_url
    return {"source": source}
