import shutil
from xml.etree import ElementTree

from .jsonio import read_json, write_json
from .paths import RunPaths


def _text(parent: ElementTree.Element, tag: str, value: str) -> ElementTree.Element:
    child = ElementTree.SubElement(parent, tag)
    child.text = value
    return child


def publish_episode(run_paths: RunPaths, publish_config: dict) -> str:
    base_url = publish_config["base_url"].rstrip("/")
    source = read_json(run_paths.source_json)
    episode_id = run_paths.run_id
    episode_dir = run_paths.publish_dir / "episodes" / episode_id
    episode_dir.mkdir(parents=True, exist_ok=True)

    audio_target = episode_dir / "audio.mp3"
    shutil.copy2(run_paths.output_audio, audio_target)

    metadata = {
        "episode_id": episode_id,
        "title": source.get("title", "Untitled Episode"),
        "original_url": source.get("original_url"),
        "transcript_url": source.get("transcript_url"),
        "audio_url": f"{base_url}/episodes/{episode_id}/audio.mp3",
    }
    write_json(episode_dir / "metadata.json", metadata)
    shutil.copy2(run_paths.normalized_transcript_json, episode_dir / "transcript.en.json")
    shutil.copy2(run_paths.chinese_script_json, episode_dir / "transcript.zh.json")

    rss = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(rss, "channel")
    _text(channel, "title", "BabelEcho MVP-0")
    _text(channel, "link", base_url)
    _text(channel, "description", "Locally generated Chinese podcast feed.")
    item = ElementTree.SubElement(channel, "item")
    _text(item, "title", metadata["title"])
    _text(item, "guid", episode_id)
    if metadata.get("original_url"):
        _text(item, "link", metadata["original_url"])
    enclosure = ElementTree.SubElement(
        item,
        "enclosure",
        {
            "url": metadata["audio_url"],
            "length": str(audio_target.stat().st_size),
            "type": "audio/mpeg",
        },
    )
    assert enclosure is not None

    feed_path = run_paths.publish_dir / "feed.xml"
    tree = ElementTree.ElementTree(rss)
    ElementTree.indent(tree, space="  ")
    tree.write(feed_path, encoding="utf-8", xml_declaration=True)

    stable_episode_dir = run_paths.stable_publish_dir / "episodes" / episode_id
    stable_episode_dir.mkdir(parents=True, exist_ok=True)
    for name in ["audio.mp3", "metadata.json", "transcript.en.json", "transcript.zh.json"]:
        shutil.copy2(episode_dir / name, stable_episode_dir / name)
    shutil.copy2(feed_path, run_paths.stable_feed)
    return str(feed_path)
