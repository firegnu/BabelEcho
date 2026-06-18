from dataclasses import dataclass
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PODCAST_NAMESPACE = "{https://podcastindex.org/namespace/1.0}"


@dataclass(frozen=True)
class PodcastTranscript:
    title: str
    episode_url: str | None
    transcript_url: str


@dataclass(frozen=True)
class PodcastEpisode:
    title: str
    episode_url: str | None
    transcript_url: str | None
    enclosure_url: str | None
    guid: str | None


def _text(parent: ET.Element, name: str) -> str | None:
    value = parent.findtext(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _enclosure_url(item: ET.Element) -> str | None:
    enclosure = item.find("enclosure")
    if enclosure is None:
        return None
    return enclosure.attrib.get("url")


def _item_url(item: ET.Element) -> str | None:
    return _text(item, "link") or _text(item, "guid") or _enclosure_url(item)


def _read_feed_source(feed_url: str) -> bytes:
    parsed = urlparse(feed_url)
    if parsed.scheme in {"http", "https"}:
        request = Request(feed_url, headers={"User-Agent": "BabelEcho/0.1"})
        with urlopen(request, timeout=30) as response:
            return response.read()
    return Path(feed_url).read_bytes()


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _matches_episode(item: ET.Element, episode_url: str | None) -> bool:
    if not episode_url:
        return True
    candidates = {
        _text(item, "link"),
        _text(item, "guid"),
        _enclosure_url(item),
    }
    return episode_url in candidates


def _transcript_url(item: ET.Element) -> str | None:
    transcript = item.find(f"{PODCAST_NAMESPACE}transcript")
    if transcript is None:
        transcript = item.find("transcript")
    if transcript is None:
        return None
    return transcript.attrib.get("url")


def discover_podcast_transcript(feed_bytes: bytes, episode_url: str | None = None) -> PodcastTranscript:
    root = ET.fromstring(feed_bytes)
    items = root.findall("./channel/item")
    if not items:
        raise ValueError("No podcast episodes found in RSS feed")

    matched_episode = False
    for item in items:
        if not _matches_episode(item, episode_url):
            continue
        matched_episode = True
        transcript_url = _transcript_url(item)
        if not transcript_url:
            continue
        title = _text(item, "title") or "Untitled Episode"
        return PodcastTranscript(
            title=title,
            episode_url=_item_url(item),
            transcript_url=transcript_url,
        )

    if episode_url and not matched_episode:
        raise ValueError(f"Episode not found in RSS feed: {episode_url}")
    raise ValueError("No transcript found in RSS feed episode")


def list_podcast_episodes(feed_bytes: bytes) -> list[PodcastEpisode]:
    root = ET.fromstring(feed_bytes)
    items = root.findall("./channel/item")
    if not items:
        raise ValueError("No podcast episodes found in RSS feed")

    episodes = []
    for item in items:
        episodes.append(
            PodcastEpisode(
                title=_text(item, "title") or "Untitled Episode",
                episode_url=_item_url(item),
                transcript_url=_transcript_url(item),
                enclosure_url=_enclosure_url(item),
                guid=_text(item, "guid"),
            )
        )
    return episodes


def fetch_podcast_episodes(feed_url: str) -> list[PodcastEpisode]:
    return list_podcast_episodes(_read_feed_source(feed_url))


def build_podcast_rss_episode_source_config(
    feed_url: str,
    episode: PodcastEpisode,
) -> dict[str, dict[str, str]]:
    if not episode.episode_url:
        raise ValueError("Selected RSS episode has no link, guid, or enclosure URL")
    return {
        "source": {
            "type": "podcast_rss",
            "feed_url": feed_url,
            "episode_url": episode.episode_url,
            "title": episode.title,
            "original_url": episode.episode_url,
        }
    }


def _podcast_index_episode(payload: dict[str, Any]) -> dict[str, Any]:
    episode = payload.get("episode")
    if isinstance(episode, dict):
        return episode
    return payload


def _podcast_index_transcript_url(episode: dict[str, Any]) -> str | None:
    transcripts = episode.get("transcripts")
    if isinstance(transcripts, list):
        for transcript in transcripts:
            if isinstance(transcript, dict):
                url = _str_value(transcript.get("url"))
                if url:
                    return url

    return _str_value(episode.get("transcriptUrl"))


def _podcast_index_episode_url(episode: dict[str, Any]) -> str | None:
    return (
        _str_value(episode.get("link"))
        or _str_value(episode.get("guid"))
        or _str_value(episode.get("enclosureUrl"))
    )


def discover_podcast_index_transcript(payload: dict[str, Any]) -> PodcastTranscript:
    episode = _podcast_index_episode(payload)
    transcript_url = _podcast_index_transcript_url(episode)
    if not transcript_url:
        raise ValueError("No transcript found in PodcastIndex episode")

    return PodcastTranscript(
        title=_str_value(episode.get("title")) or "Untitled Episode",
        episode_url=_podcast_index_episode_url(episode),
        transcript_url=transcript_url,
    )
