from dataclasses import dataclass
import xml.etree.ElementTree as ET


PODCAST_NAMESPACE = "{https://podcastindex.org/namespace/1.0}"


@dataclass(frozen=True)
class PodcastTranscript:
    title: str
    episode_url: str | None
    transcript_url: str


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
