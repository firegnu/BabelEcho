import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .episode_page import discover_episode_page_transcript
from .jsonio import write_json
from .paths import RunPaths
from .podcast import discover_podcast_index_transcript, discover_podcast_transcript
from .podcast_index_api import fetch_podcast_index_episode
from .transcript_cleaning import clean_timed_transcript_file
from .transcript_candidates import build_youtube_candidate, write_candidates_json
from .youtube import fetch_youtube_captions, parse_youtube_start_ms


TRANSCRIPT_EXTENSIONS = {
    ".vtt": "raw.vtt",
    ".srt": "raw.srt",
    ".txt": "raw.txt",
    ".json": "raw.json",
    ".html": "raw.html",
    ".htm": "raw.html",
}


def _target_name(transcript_url: str) -> str:
    suffix = Path(urlparse(transcript_url).path).suffix.lower()
    return TRANSCRIPT_EXTENSIONS.get(suffix, "raw.txt")


def _read_source(transcript_url: str) -> bytes:
    parsed = urlparse(transcript_url)
    if parsed.scheme in {"http", "https"}:
        request = Request(transcript_url, headers={"User-Agent": "BabelEcho/0.1"})
        with urlopen(request, timeout=30) as response:
            return response.read()
    return Path(transcript_url).read_bytes()


def ingest_transcript_source(source_config: dict, run_paths: RunPaths) -> Path:
    source_type = source_config.get("type")
    raw_content: bytes | None = None
    raw_filename: str | None = None
    youtube_candidate_language: str | None = None
    youtube_candidate_source_url: str | None = None
    youtube_start_ms: int | None = None
    normalized_transcript_source: str | None = None
    if source_type == "transcript_url":
        transcript_source = source_config.get("transcript_url")
        source_key = "transcript_url"
    elif source_type == "transcript_file":
        transcript_source = source_config.get("transcript_file")
        source_key = "transcript_file"
    elif source_type == "podcast_rss":
        feed_url = source_config.get("feed_url")
        if not feed_url:
            raise ValueError("source.feed_url is required")
        transcript = discover_podcast_transcript(
            _read_source(feed_url),
            source_config.get("episode_url"),
        )
        transcript_source = transcript.transcript_url
        source_key = "transcript_url"
        source_config = {
            **source_config,
            "title": source_config.get("title") or transcript.title,
            "original_url": source_config.get("original_url") or transcript.episode_url,
            "transcript_url": transcript.transcript_url,
        }
    elif source_type == "podcast_index_episode":
        episode_json = source_config.get("episode_json")
        if not episode_json:
            raise ValueError("source.episode_json is required")
        transcript = discover_podcast_index_transcript(json.loads(_read_source(episode_json)))
        transcript_source = transcript.transcript_url
        source_key = "transcript_url"
        source_config = {
            **source_config,
            "title": source_config.get("title") or transcript.title,
            "original_url": source_config.get("original_url") or transcript.episode_url,
            "transcript_url": transcript.transcript_url,
        }
    elif source_type == "podcast_index_api":
        episode = fetch_podcast_index_episode(source_config)
        transcript = discover_podcast_index_transcript(episode)
        transcript_source = transcript.transcript_url
        source_key = "transcript_url"
        source_config = {
            **source_config,
            "title": source_config.get("title") or transcript.title,
            "original_url": source_config.get("original_url") or transcript.episode_url,
            "transcript_url": transcript.transcript_url,
        }
    elif source_type == "episode_page":
        page_url = source_config.get("page_url")
        if not page_url:
            raise ValueError("source.page_url is required")
        transcript = discover_episode_page_transcript(page_url, _read_source)
        transcript_source = transcript.transcript_page_url
        source_key = "transcript_page_url"
        raw_content = transcript.text.encode("utf-8")
        raw_filename = "raw.txt"
        source_config = {
            **source_config,
            "title": source_config.get("title") or transcript.title,
            "original_url": source_config.get("original_url") or transcript.page_url,
            "page_url": transcript.page_url,
            "transcript_page_url": transcript.transcript_page_url,
        }
    elif source_type == "youtube_captions":
        youtube_candidate_source_url = source_config.get("url")
        try:
            captions = fetch_youtube_captions(
                source_config,
                run_paths.run_dir / "tmp" / "youtube-captions",
            )
        except ValueError as error:
            write_candidates_json(
                run_paths,
                [
                    build_youtube_candidate(
                        run_paths,
                        source_url=youtube_candidate_source_url,
                        raw_path=None,
                        language=str(source_config.get("language") or "en"),
                        selected=False,
                        rejection_reason=str(error),
                    )
                ],
            )
            raise
        transcript_source = str(captions.path)
        source_key = "youtube_subtitle_source"
        raw_content = captions.path.read_bytes()
        raw_filename = TRANSCRIPT_EXTENSIONS.get(captions.path.suffix.lower(), "raw.vtt")
        youtube_candidate_language = captions.language
        youtube_start_ms = source_config.get("youtube_start_ms")
        if youtube_start_ms is None and youtube_candidate_source_url:
            youtube_start_ms = parse_youtube_start_ms(str(youtube_candidate_source_url))
        source_config = {
            **source_config,
            "title": source_config.get("title") or captions.title,
            "original_url": source_config.get("original_url") or source_config.get("url"),
            "youtube_url": source_config.get("url"),
            "youtube_language": captions.language,
            "youtube_subtitle_file": raw_filename,
        }
        if youtube_start_ms is not None:
            source_config["youtube_start_ms"] = youtube_start_ms
    else:
        raise ValueError(
            "BabelEcho supports source.type=transcript_url, transcript_file, "
            "podcast_rss, podcast_index_episode, podcast_index_api, episode_page, "
            "or youtube_captions"
        )
    if not transcript_source:
        raise ValueError(f"source.{source_key} is required")

    raw_path = run_paths.transcript_dir / (raw_filename or _target_name(transcript_source))
    raw_path.write_bytes(raw_content if raw_content is not None else _read_source(transcript_source))
    if source_type == "youtube_captions":
        cleaned_path = run_paths.transcript_dir / f"cleaned{raw_path.suffix.lower()}"
        clean_timed_transcript_file(raw_path, cleaned_path)
        normalized_transcript_source = str(cleaned_path.relative_to(run_paths.run_dir))
        write_candidates_json(
            run_paths,
            [
                build_youtube_candidate(
                    run_paths,
                    source_url=youtube_candidate_source_url,
                    raw_path=raw_path,
                    language=youtube_candidate_language,
                    selected=True,
                    cleaned_path=cleaned_path,
                )
            ],
        )

    source_payload = {
        "run_id": run_paths.run_id,
        "source_type": source_type,
        "title": source_config.get("title") or "Untitled Episode",
        "original_url": source_config.get("original_url"),
        "feed_url": source_config.get("feed_url"),
        "episode_url": source_config.get("episode_url"),
        "episode_json": source_config.get("episode_json"),
        "podcast_index_endpoint": source_config.get("endpoint"),
        "podcast_index_episode_id": source_config.get("episode_id"),
        "feed_id": source_config.get("feed_id"),
        "itunes_id": source_config.get("itunes_id"),
        "raw_transcript": str(raw_path.relative_to(run_paths.run_dir)),
    }
    if source_config.get("youtube_url") is not None:
        source_payload["youtube_url"] = source_config.get("youtube_url")
    if source_config.get("youtube_language") is not None:
        source_payload["youtube_language"] = source_config.get("youtube_language")
    if source_config.get("youtube_subtitle_file") is not None:
        source_payload["youtube_subtitle_file"] = source_config.get("youtube_subtitle_file")
    if source_config.get("youtube_start_ms") is not None:
        source_payload["youtube_start_ms"] = source_config.get("youtube_start_ms")
    if source_config.get("page_url") is not None:
        source_payload["page_url"] = source_config.get("page_url")
    if source_config.get("transcript_page_url") is not None:
        source_payload["transcript_page_url"] = source_config.get("transcript_page_url")
    if normalized_transcript_source is not None:
        source_payload["normalized_transcript_source"] = normalized_transcript_source
    source_payload[source_key] = transcript_source
    write_json(run_paths.source_json, source_payload)
    return raw_path
