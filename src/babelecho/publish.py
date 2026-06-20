import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from .jsonio import read_json, write_json
from .paths import RunPaths

AUDIO_FIRST_SOURCE_TYPES = {"audio_file", "audio_url"}


def _text(parent: ElementTree.Element, tag: str, value: str) -> ElementTree.Element:
    child = ElementTree.SubElement(parent, tag)
    child.text = value
    return child


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _read_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return read_json(path)


def _source_type(source: dict) -> str:
    return str(source.get("source_type") or source.get("type") or "unknown")


def _source_provider(source: dict) -> str:
    if source.get("provider"):
        return str(source["provider"])
    source_type = _source_type(source)
    providers = {
        "youtube_captions": "youtube",
        "episode_page": "episode_page",
        "podcast_rss": "rss",
        "transcript_file": "local_file",
        "audio_file": "local_file",
        "audio_url": "remote_url",
        "article_file": "local_file",
        "web_article": "trafilatura",
        "x_post": "x_api",
        "x_thread": "x_api",
    }
    return providers.get(source_type, source_type)


def _route_for_source(source: dict) -> str:
    source_type = _source_type(source)
    if source_type in AUDIO_FIRST_SOURCE_TYPES:
        return "audio_first"
    if source_type in {"article_file", "web_article", "x_post", "x_thread"}:
        return "article_reading"
    return "transcript_first"


def _public_source(source: dict) -> dict:
    public_source = {
        "type": _source_type(source),
        "provider": _source_provider(source),
        "input_url": (
            source.get("input_url")
            or source.get("url")
            or source.get("feed_url")
            or source.get("original_url")
        ),
        "episode_url": source.get("episode_url") or source.get("original_url"),
        "transcript_url": source.get("transcript_url"),
        "feed_url": source.get("feed_url"),
    }
    for key in ["site_name", "author", "published_time", "excerpt"]:
        if source.get(key) is not None:
            public_source[key] = source[key]
    for key in ["source_host", "source_path"]:
        if source.get(key) is not None:
            public_source[key] = source[key]
    return public_source


def _audio_probe(audio_path: Path) -> dict:
    media = {
        "audio_path": "audio.mp3",
        "mime_type": "audio/mpeg",
        "duration_seconds": None,
        "sample_rate": None,
        "channels": None,
        "file_size_bytes": audio_path.stat().st_size,
    }
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-show_entries",
        "stream=sample_rate,channels",
        "-of",
        "json",
        str(audio_path),
    ]
    try:
        completed = subprocess.run(command, check=True, text=True, capture_output=True)
        probed = json.loads(completed.stdout)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return media
    streams = probed.get("streams", [])
    if streams:
        stream = streams[0]
        if stream.get("sample_rate") is not None:
            media["sample_rate"] = int(stream["sample_rate"])
        if stream.get("channels") is not None:
            media["channels"] = int(stream["channels"])
    duration = probed.get("format", {}).get("duration")
    if duration is not None:
        media["duration_seconds"] = float(duration)
    return media


def _quality_summary(run_paths: RunPaths) -> dict:
    quality = _read_optional_json(run_paths.transcript_quality_json) or {}
    return {
        "recommendation": quality.get("recommendation", "unknown"),
        "warnings": quality.get("warnings", []),
        "reasons": quality.get("reasons", []),
        "metrics": quality.get("metrics", {}),
    }


def _speaker_inference_map(speaker_voices: dict | None) -> dict:
    if not speaker_voices:
        return {}
    return {
        item.get("speaker"): item
        for item in speaker_voices.get("inferences", [])
        if item.get("speaker")
    }


def _speaker_summaries(script: dict, speaker_voices: dict | None) -> list[dict]:
    ordered_speakers: list[str] = []
    segment_counts: dict[str, int] = {}
    for segment in script.get("segments", []):
        speaker = segment.get("speaker")
        if not speaker:
            continue
        speaker = str(speaker)
        if speaker not in segment_counts:
            ordered_speakers.append(speaker)
            segment_counts[speaker] = 0
        segment_counts[speaker] += 1

    voice_roles = (speaker_voices or {}).get("speaker_voices", {})
    inferences = _speaker_inference_map(speaker_voices)
    speakers = []
    for index, speaker in enumerate(ordered_speakers, start=1):
        summary = {
            "id": f"speaker_{index}",
            "display_name": speaker,
            "segment_count": segment_counts[speaker],
        }
        if speaker in voice_roles:
            summary["voice_role"] = voice_roles[speaker]
        inference = inferences.get(speaker)
        if inference and inference.get("gender"):
            summary["inferred_gender"] = inference["gender"]
        speakers.append(summary)
    return speakers


def _asr_summary(run_paths: RunPaths, source: dict) -> dict | None:
    if _source_type(source) not in AUDIO_FIRST_SOURCE_TYPES:
        return None
    raw_asr = _read_optional_json(run_paths.run_dir / "asr" / "raw.json") or {}
    if not raw_asr:
        return None
    diarization = _read_optional_json(run_paths.run_dir / "asr" / "diarization.json") or {}
    quality = _quality_summary(run_paths)
    summary = {
        "provider": raw_asr.get("provider"),
        "model": raw_asr.get("model"),
        "language": raw_asr.get("language"),
        "duration_seconds": raw_asr.get("duration_seconds"),
        "segment_count": len(raw_asr.get("segments") or []),
        "speaker_count": (
            diarization.get("speaker_count")
            or quality.get("metrics", {}).get("speaker_count")
            or 0
        ),
        "diarization_provider": diarization.get("provider"),
        "quality": {
            "recommendation": quality.get("recommendation", "unknown"),
            "warnings": quality.get("warnings", []),
            "reasons": quality.get("reasons", []),
        },
    }
    speaker_profiles = _read_optional_json(run_paths.run_dir / "asr" / "speaker-profiles.json")
    if speaker_profiles:
        speakers = speaker_profiles.get("speakers") or []
        summary["speaker_profiles"] = {
            "provider": speaker_profiles.get("provider"),
            "speaker_count": speaker_profiles.get("speaker_count") or len(speakers),
            "profile_kind": (
                speakers[0].get("profile_kind") if speakers else None
            ),
            "embedding_status": (
                speakers[0].get("embedding_status") if speakers else None
            ),
        }
    return summary


def _write_published_index(stable_publish_dir: Path, generated_at: str) -> None:
    episodes = []
    for artifact_path in sorted((stable_publish_dir / "episodes").glob("*/artifact.json")):
        artifact = read_json(artifact_path)
        episodes.append(
            {
                "run_id": artifact["run_id"],
                "title": artifact["title"],
                "route": artifact["route"],
                "status": artifact["status"],
                "source_type": artifact["source"]["type"],
                "quality_recommendation": artifact.get("quality", {}).get(
                    "recommendation", "unknown"
                ),
                "speaker_count": len(artifact.get("speakers", [])),
                "duration_seconds": artifact.get("media", {}).get("duration_seconds"),
                "published_at": artifact.get("published_at"),
                "audio_path": f"episodes/{artifact['run_id']}/audio.mp3",
                "artifact_path": f"episodes/{artifact['run_id']}/artifact.json",
            }
        )
    episodes.sort(
        key=lambda episode: (episode.get("published_at") or "", episode["run_id"]),
        reverse=True,
    )
    write_json(
        stable_publish_dir / "index.json",
        {
            "schema_version": "1.0",
            "generated_at": generated_at,
            "title": "BabelEcho",
            "description": "Locally generated Chinese podcast artifacts.",
            "episodes": episodes,
        },
    )


def _write_zh_transcript(run_paths: RunPaths, script: dict, target: Path) -> None:
    timings: dict = {}
    manifest_path = run_paths.segments_dir / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        for segment in manifest.get("segments", []):
            if "start_ms" in segment:
                timings[segment["id"]] = {
                    "start_ms": segment["start_ms"],
                    "end_ms": segment.get("end_ms"),
                    "duration_ms": segment.get("duration_ms"),
                }
    enriched = dict(script)
    enriched_segments = []
    for segment in script.get("segments", []):
        new_segment = dict(segment)
        timing = timings.get(segment.get("id"))
        if timing is not None:
            new_segment.update(timing)
        enriched_segments.append(new_segment)
    enriched["segments"] = enriched_segments
    write_json(target, enriched)


def publish_episode(run_paths: RunPaths, publish_config: dict) -> str:
    base_url = publish_config["base_url"].rstrip("/")
    source = read_json(run_paths.source_json)
    script = read_json(run_paths.chinese_script_json)
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
    _write_zh_transcript(run_paths, script, episode_dir / "transcript.zh.json")
    speaker_profiles_path = run_paths.run_dir / "asr" / "speaker-profiles.json"
    if speaker_profiles_path.exists():
        shutil.copy2(speaker_profiles_path, episode_dir / "speaker-profiles.json")
    published_at = _utc_timestamp()
    speaker_voices = _read_optional_json(run_paths.script_dir / "speaker-voices.json")
    artifact_paths = {
        "metadata": "metadata.json",
        "transcript_en": "transcript.en.json",
        "script_zh": "transcript.zh.json",
        "feed": "../../feed.xml",
    }
    if speaker_profiles_path.exists():
        artifact_paths["speaker_profiles"] = "speaker-profiles.json"
    artifact = {
        "schema_version": "1.0",
        "run_id": episode_id,
        "route": _route_for_source(source),
        "status": "succeeded",
        "title": metadata["title"],
        "summary": source.get("summary"),
        "created_at": None,
        "published_at": published_at,
        "source": _public_source(source),
        "quality": _quality_summary(run_paths),
        "media": _audio_probe(audio_target),
        "artifacts": artifact_paths,
        "speakers": _speaker_summaries(script, speaker_voices),
        "asr": _asr_summary(run_paths, source),
        "ui": {
            "default_tab": "script",
            "badges": [_route_for_source(source).replace("_", "-")],
        },
    }
    if artifact["quality"]["recommendation"] != "unknown":
        artifact["ui"]["badges"].append(
            artifact["quality"]["recommendation"].replace("_", "-")
        )
    write_json(episode_dir / "artifact.json", artifact)

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
    for name in [
        "audio.mp3",
        "metadata.json",
        "transcript.en.json",
        "transcript.zh.json",
        "artifact.json",
        "speaker-profiles.json",
    ]:
        source_path = episode_dir / name
        if source_path.exists():
            shutil.copy2(source_path, stable_episode_dir / name)
    shutil.copy2(feed_path, run_paths.stable_feed)
    _write_published_index(run_paths.stable_publish_dir, published_at)
    return str(feed_path)
