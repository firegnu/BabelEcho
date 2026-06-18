from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.podcastindex.org/api/1.0"
DEFAULT_USER_AGENT = "BabelEcho/0.1"
SUPPORTED_ENDPOINTS = {
    "episodes/byfeedid",
    "episodes/byfeedurl",
    "episodes/byid",
    "episodes/byitunesid",
}


@dataclass(frozen=True)
class PodcastIndexCredentials:
    api_key: str
    api_secret: str
    user_agent: str


def build_auth_headers(
    credentials: PodcastIndexCredentials,
    unix_time: int | None = None,
) -> dict[str, str]:
    auth_date = str(int(time.time() if unix_time is None else unix_time))
    token = hashlib.sha1(
        f"{credentials.api_key}{credentials.api_secret}{auth_date}".encode("utf-8")
    ).hexdigest()
    return {
        "User-Agent": credentials.user_agent,
        "X-Auth-Date": auth_date,
        "X-Auth-Key": credentials.api_key,
        "Authorization": token,
    }


def _read_env_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    source = Path(path)
    if not source.exists():
        raise ValueError(f"Configured credentials_file does not exist: {source}")
    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _required_file_value(values: dict[str, str], key: str, source: str | Path) -> str:
    value = values.get(key)
    if not value:
        raise ValueError(f"Configured credentials_file does not define {key}: {source}")
    return value


def load_podcast_index_credentials(source_config: dict) -> PodcastIndexCredentials:
    credentials_file = source_config.get("credentials_file")
    api_key_env = source_config.get("api_key_env")
    api_secret_env = source_config.get("api_secret_env")

    if credentials_file and (api_key_env or api_secret_env):
        raise ValueError("Configure either credentials_file or api_key_env/api_secret_env")

    if credentials_file:
        values = _read_env_file(credentials_file)
        return PodcastIndexCredentials(
            api_key=_required_file_value(
                values,
                "PODCASTINDEX_API_KEY",
                credentials_file,
            ),
            api_secret=_required_file_value(
                values,
                "PODCASTINDEX_API_SECRET",
                credentials_file,
            ),
            user_agent=values.get("PODCASTINDEX_USER_AGENT")
            or source_config.get("user_agent")
            or DEFAULT_USER_AGENT,
        )

    if not api_key_env or not api_secret_env:
        raise ValueError("source.api_key_env and source.api_secret_env are required")

    return PodcastIndexCredentials(
        api_key=_required_env(api_key_env),
        api_secret=_required_env(api_secret_env),
        user_agent=source_config.get("user_agent") or DEFAULT_USER_AGENT,
    )


def _required_config_value(source_config: dict, key: str) -> str:
    value = source_config.get(key)
    if value is None or value == "":
        raise ValueError(f"source.{key} is required")
    return str(value)


def build_podcast_index_url(source_config: dict) -> str:
    endpoint = source_config.get("endpoint")
    if endpoint not in SUPPORTED_ENDPOINTS:
        raise ValueError(
            "source.endpoint must be one of "
            "episodes/byfeedid, episodes/byfeedurl, episodes/byid, episodes/byitunesid"
        )

    query: dict[str, str] = {"fulltext": "true"}
    if endpoint == "episodes/byid":
        query["id"] = _required_config_value(source_config, "episode_id")
    elif endpoint == "episodes/byfeedid":
        query["id"] = _required_config_value(source_config, "feed_id")
        query["max"] = str(int(source_config.get("max_episodes", 10)))
    elif endpoint == "episodes/byfeedurl":
        query["url"] = _required_config_value(source_config, "feed_url")
    elif endpoint == "episodes/byitunesid":
        query["id"] = _required_config_value(source_config, "itunes_id")
        query["max"] = str(int(source_config.get("max_episodes", 10)))

    base_url = str(source_config.get("api_base_url") or DEFAULT_BASE_URL).rstrip("/")
    return f"{base_url}/{endpoint}?{urlencode(query)}"


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _episode_candidates(episode: dict[str, Any]) -> set[str | None]:
    return {
        _str_value(episode.get("link")),
        _str_value(episode.get("guid")),
        _str_value(episode.get("enclosureUrl")),
    }


def select_podcast_index_episode(
    payload: dict[str, Any],
    episode_url: str | None,
) -> dict[str, Any]:
    episode = payload.get("episode")
    if isinstance(episode, dict):
        return episode

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("No podcast episodes found in PodcastIndex API response")

    if not episode_url:
        first = items[0]
        if isinstance(first, dict):
            return first
        raise ValueError("No podcast episodes found in PodcastIndex API response")

    for item in items:
        if isinstance(item, dict) and episode_url in _episode_candidates(item):
            return item

    raise ValueError(f"Episode not found in PodcastIndex API response: {episode_url}")


def fetch_podcast_index_episode(source_config: dict) -> dict[str, Any]:
    credentials = load_podcast_index_credentials(source_config)
    request = Request(
        build_podcast_index_url(source_config),
        headers=build_auth_headers(credentials),
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    return select_podcast_index_episode(payload, source_config.get("episode_url"))
