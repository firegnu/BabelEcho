import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .adapt import adapt_to_chinese
from .article_pipeline import ARTICLE_PIPELINE_STAGES, run_article_pipeline
from .audio import assemble_audio
from .audio_pipeline import AUDIO_PIPELINE_STAGES, run_audio_pipeline
from .checks import CheckError, check_run_artifacts
from .config import load_yaml, require_keys
from .episode_convert import build_on_demand_source_config
from .ingest import ingest_transcript_source
from .itunes import (
    build_podcast_rss_source_config,
    fetch_itunes_podcast_lookup,
    fetch_itunes_podcast_search,
)
from .jsonio import read_json, write_json
from .overrides import apply_script_overrides
from .paths import create_run
from .podcast import build_podcast_rss_episode_source_config, fetch_podcast_episodes
from .podcast_index_api import (
    build_episode_source_config,
    fetch_podcast_index_episodes,
    fetch_podcast_search,
)
from .publish import publish_episode
from .script import preview_chinese_script
from .speaker_similarity import (
    DEFAULT_POSSIBLE_THRESHOLD,
    DEFAULT_SAME_THRESHOLD,
    compare_speaker_profiles,
    format_speaker_similarity_summary,
)
from .speaker_voices import infer_speaker_voices, infer_speaker_voices_if_enabled
from .status import (
    init_run_status,
    mark_run_succeeded,
    mark_stage_failed,
    mark_stage_running,
    mark_stage_succeeded,
)
from .synthesize import synthesize_segments
from .transcript import normalize_transcript

PIPELINE_STAGES = ("ingest", "normalize", "adapt", "synthesize", "assemble", "publish")
CHECK_NAMES = ("script", "segments", "output")
APPLE_PODCAST_HOSTS = {"podcasts.apple.com", "itunes.apple.com"}


def _add_podcast_index_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-base-url")
    parser.add_argument("--credentials-file")
    parser.add_argument("--api-key-env", default="PODCASTINDEX_API_KEY")
    parser.add_argument("--api-secret-env", default="PODCASTINDEX_API_SECRET")
    parser.add_argument("--user-agent")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="babelecho",
        description="BabelEcho backend pipeline",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    ingest = subparsers.add_parser("ingest", help="Fetch transcript input.")
    ingest.add_argument("--workspace", required=True)
    ingest.add_argument("--run-id", required=True)
    ingest.add_argument("--source-config", required=True)

    normalize = subparsers.add_parser("normalize", help="Normalize raw transcript.")
    normalize.add_argument("--workspace", required=True)
    normalize.add_argument("--run-id", required=True)
    normalize.add_argument("--raw-transcript", required=True)

    adapt = subparsers.add_parser("adapt", help="Adapt transcript to Chinese script.")
    adapt.add_argument("--workspace", required=True)
    adapt.add_argument("--run-id", required=True)
    adapt.add_argument("--local-config", required=True)

    synthesize = subparsers.add_parser("synthesize", help="Generate audio segments.")
    synthesize.add_argument("--workspace", required=True)
    synthesize.add_argument("--run-id", required=True)
    synthesize.add_argument("--local-config", required=True)

    assemble = subparsers.add_parser("assemble", help="Assemble final episode audio.")
    assemble.add_argument("--workspace", required=True)
    assemble.add_argument("--run-id", required=True)

    publish = subparsers.add_parser("publish", help="Publish static podcast artifacts.")
    publish.add_argument("--workspace", required=True)
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--local-config", required=True)

    script = subparsers.add_parser("script", help="Preview the Chinese script before TTS.")
    script.add_argument("--workspace", required=True)
    script.add_argument("--run-id", required=True)

    overrides = subparsers.add_parser("overrides", help="Apply local script overrides.")
    overrides.add_argument("--workspace", required=True)
    overrides.add_argument("--run-id", required=True)
    overrides.add_argument("--local-config", required=True)

    speaker_voices = subparsers.add_parser("speaker-voices", help="Infer speaker voice roles once.")
    speaker_voices.add_argument("--workspace", required=True)
    speaker_voices.add_argument("--run-id", required=True)
    speaker_voices.add_argument("--local-config", required=True)

    speaker_profiles = subparsers.add_parser(
        "speaker-profiles",
        help="Inspect speaker profile artifacts.",
    )
    speaker_profiles_subparsers = speaker_profiles.add_subparsers(
        dest="speaker_profiles_command",
        required=True,
    )
    speaker_profiles_compare = speaker_profiles_subparsers.add_parser(
        "compare",
        help="Compare run-local speaker embeddings.",
    )
    speaker_profiles_compare.add_argument(
        "--run-dir",
        action="append",
        required=True,
        help="Run directory containing asr/speaker-profiles.json. Repeat for multiple runs.",
    )
    speaker_profiles_compare.add_argument("--output-json")
    speaker_profiles_compare.add_argument(
        "--same-threshold",
        type=float,
        default=DEFAULT_SAME_THRESHOLD,
    )
    speaker_profiles_compare.add_argument(
        "--possible-threshold",
        type=float,
        default=DEFAULT_POSSIBLE_THRESHOLD,
    )

    podcast_index = subparsers.add_parser(
        "podcast-index",
        help="Search PodcastIndex and create source configs.",
    )
    podcast_index_subparsers = podcast_index.add_subparsers(
        dest="podcast_index_command",
        required=True,
    )

    podcast_index_search = podcast_index_subparsers.add_parser(
        "search",
        help="Search podcasts by term or title.",
    )
    podcast_index_search.add_argument("--query", required=True)
    podcast_index_search.add_argument("--by-title", action="store_true")
    podcast_index_search.add_argument("--max", type=int, default=10)
    podcast_index_search.add_argument("--clean", action="store_true")
    _add_podcast_index_auth_args(podcast_index_search)

    podcast_index_episodes = podcast_index_subparsers.add_parser(
        "episodes",
        help="List episodes for a PodcastIndex feed.",
    )
    podcast_index_episodes.add_argument("--feed-id", required=True, type=int)
    podcast_index_episodes.add_argument("--max", type=int, default=10)
    podcast_index_episodes.add_argument("--select-index", type=int)
    podcast_index_episodes.add_argument("--source-config-out")
    _add_podcast_index_auth_args(podcast_index_episodes)

    itunes = subparsers.add_parser(
        "itunes",
        help="Search iTunes podcasts and create RSS source configs.",
    )
    itunes_subparsers = itunes.add_subparsers(
        dest="itunes_command",
        required=True,
    )
    itunes_search = itunes_subparsers.add_parser(
        "search",
        help="Search iTunes podcast shows.",
    )
    itunes_search.add_argument("--query", required=True)
    itunes_search.add_argument("--country", default="US")
    itunes_search.add_argument("--max", type=int, default=10)
    itunes_search.add_argument("--api-base-url")
    itunes_search.add_argument("--select-index", type=int)
    itunes_search.add_argument("--source-config-out")
    itunes_episodes = itunes_subparsers.add_parser(
        "episodes",
        help="List RSS episodes from an Apple Podcasts URL.",
    )
    itunes_episodes.add_argument("--url", required=True)
    itunes_episodes.add_argument("--country", default="US")
    itunes_episodes.add_argument("--api-base-url")
    itunes_episodes.add_argument("--select-index", type=int)
    itunes_episodes.add_argument("--source-config-out")

    rss = subparsers.add_parser(
        "rss",
        help="List RSS feed episodes and create episode source configs.",
    )
    rss_subparsers = rss.add_subparsers(
        dest="rss_command",
        required=True,
    )
    rss_episodes = rss_subparsers.add_parser(
        "episodes",
        help="List episodes in an RSS feed.",
    )
    rss_episodes.add_argument("--feed-url", required=True)
    rss_episodes.add_argument("--select-index", type=int)
    rss_episodes.add_argument("--source-config-out")

    episode = subparsers.add_parser(
        "episode",
        help="Convert one requested episode.",
    )
    episode_subparsers = episode.add_subparsers(
        dest="episode_command",
        required=True,
    )
    episode_convert = episode_subparsers.add_parser(
        "convert",
        help="Convert one exact episode input.",
    )
    episode_convert.add_argument("--workspace", required=True)
    episode_convert.add_argument("--run-id", required=True)
    episode_input = episode_convert.add_mutually_exclusive_group(required=True)
    episode_input.add_argument("--url")
    episode_input.add_argument("--source-config")
    episode_input.add_argument("--transcript-file")
    episode_convert.add_argument("--local-config", required=True)
    episode_convert.add_argument("--title")
    episode_convert.add_argument("--language", default="en")
    episode_convert.add_argument("--select-index", type=int)
    episode_convert.add_argument("--itunes-country", default="US")
    episode_convert.add_argument("--itunes-api-base-url")
    episode_convert.add_argument("--source-config-out")
    episode_convert.add_argument(
        "--from-stage",
        choices=PIPELINE_STAGES,
        default="ingest",
    )
    episode_convert.add_argument(
        "--to-stage",
        choices=PIPELINE_STAGES,
        default="publish",
    )

    article = subparsers.add_parser(
        "article",
        help="Convert one requested article.",
    )
    article_subparsers = article.add_subparsers(
        dest="article_command",
        required=True,
    )
    article_convert = article_subparsers.add_parser(
        "convert",
        help="Convert one article URL or local article file.",
    )
    article_convert.add_argument("--workspace", required=True)
    article_convert.add_argument("--run-id", required=True)
    article_input = article_convert.add_mutually_exclusive_group(required=True)
    article_input.add_argument("--url")
    article_input.add_argument("--file")
    article_convert.add_argument("--local-config", required=True)
    article_convert.add_argument("--title")
    article_convert.add_argument(
        "--from-stage",
        choices=ARTICLE_PIPELINE_STAGES,
        default="ingest",
    )
    article_convert.add_argument(
        "--to-stage",
        choices=ARTICLE_PIPELINE_STAGES,
        default="publish",
    )

    audio = subparsers.add_parser(
        "audio",
        help="Convert one local audio file.",
    )
    audio_subparsers = audio.add_subparsers(
        dest="audio_command",
        required=True,
    )
    audio_convert = audio_subparsers.add_parser(
        "convert",
        help="Convert one local audio file through the audio-first pipeline.",
    )
    audio_convert.add_argument("--workspace", required=True)
    audio_convert.add_argument("--run-id", required=True)
    audio_convert.add_argument("--audio-file", required=True)
    audio_convert.add_argument("--local-config", required=True)
    audio_convert.add_argument("--title")
    audio_convert.add_argument(
        "--from-stage",
        choices=AUDIO_PIPELINE_STAGES,
        default="ingest_audio",
    )
    audio_convert.add_argument(
        "--to-stage",
        choices=AUDIO_PIPELINE_STAGES,
        default="ingest_audio",
    )

    run = subparsers.add_parser("run", help="Run the transcript-to-podcast pipeline.")
    run.add_argument("--workspace", required=True)
    run.add_argument("--run-id", required=True)
    run_input = run.add_mutually_exclusive_group(required=True)
    run_input.add_argument("--source-config")
    run_input.add_argument("--transcript-file")
    run_input.add_argument("--podcast-feed")
    run.add_argument("--episode-url")
    run.add_argument("--title")
    run.add_argument("--original-url")
    run.add_argument("--local-config", required=True)
    run.add_argument(
        "--from-stage",
        choices=PIPELINE_STAGES,
        default="ingest",
        help="Resume from this stage.",
    )
    run.add_argument(
        "--to-stage",
        choices=PIPELINE_STAGES,
        default="publish",
        help="Stop after this stage.",
    )

    check = subparsers.add_parser("check", help="Validate generated run artifacts.")
    check.add_argument("--workspace", required=True)
    check.add_argument("--run-id", required=True)
    check.add_argument(
        "--checks",
        nargs="+",
        choices=CHECK_NAMES,
        default=CHECK_NAMES,
        help="Artifact checks to run.",
    )
    check.add_argument(
        "--max-script-chars",
        type=int,
        default=1200,
        help="Maximum allowed characters per script segment.",
    )

    return parser


def _raw_transcript_path(run_paths) -> Path:
    source = read_json(run_paths.source_json)
    raw_transcript = source.get("normalized_transcript_source") or source.get("raw_transcript")
    if not raw_transcript:
        raise ValueError(f"Missing raw_transcript in {run_paths.source_json}")
    return run_paths.run_dir / raw_transcript


def _source_config_and_input(
    source_config_path: str | None,
    transcript_file: str | None,
    podcast_feed: str | None,
    episode_url: str | None,
    title: str | None,
    original_url: str | None,
) -> tuple[dict, dict]:
    if source_config_path:
        source_config = load_yaml(Path(source_config_path))
        require_keys(source_config, ["source"])
        return source_config, {"source_config": str(Path(source_config_path))}

    if podcast_feed:
        source = {
            "type": "podcast_rss",
            "feed_url": podcast_feed,
        }
        input_info = {"podcast_feed": podcast_feed}
        if episode_url:
            source["episode_url"] = episode_url
            input_info["episode_url"] = episode_url
        if title:
            source["title"] = title
            input_info["title"] = title
        if original_url:
            source["original_url"] = original_url
            input_info["original_url"] = original_url
        return {"source": source}, input_info

    if not transcript_file:
        raise ValueError("source_config_path, transcript_file, or podcast_feed is required")

    transcript_path = Path(transcript_file)
    episode_title = title or transcript_path.stem
    source = {
        "type": "transcript_file",
        "transcript_file": str(transcript_path),
        "title": episode_title,
    }
    input_info = {
        "transcript_file": str(transcript_path),
        "title": episode_title,
    }
    if original_url:
        source["original_url"] = original_url
        input_info["original_url"] = original_url
    return {"source": source}, input_info


def _run_stage(status: dict, run_paths, stage_name: str, action):
    mark_stage_running(status, run_paths, stage_name)
    try:
        result = action()
    except Exception as error:
        mark_stage_failed(status, run_paths, stage_name, error)
        raise
    mark_stage_succeeded(status, run_paths, stage_name)
    return result


def _format_speaker_voice_result(result: dict) -> str:
    message = f"speaker voices: {result['status']} {result['path']}"
    if result.get("error"):
        message += f" ({result['error']}; fallback automatic roles)"
    elif result.get("reason"):
        message += f" ({result['reason']})"
    return message


def _format_transcript_candidate_result(run_paths) -> list[str]:
    candidates_path = run_paths.transcript_dir / "candidates.json"
    if not candidates_path.exists():
        return []
    data = read_json(candidates_path)
    candidates = data.get("candidates") or []
    lines = [f"transcript candidates: {len(candidates)}"]
    selected = data.get("selected")
    if not selected:
        lines.append("No usable transcript candidate found.")
        for candidate in candidates:
            reason = candidate.get("rejection_reason") or "not selected"
            lines.append(f"- {candidate.get('source_type', 'unknown')}: {reason}")
        return lines

    source_type = selected.get("source_type", "unknown")
    language = selected.get("language") or "unknown"
    transcript_format = selected.get("format") or "unknown"
    lines.append(
        "selected transcript: "
        f"{source_type}/{language}/{transcript_format} "
        f"score={selected.get('score', 0)}"
    )
    warnings = selected.get("warnings") or []
    if warnings:
        lines.append(f"warnings: {', '.join(warnings)}")
    cleaned_path = selected.get("cleaned_path")
    if cleaned_path:
        lines.append(f"cleaned transcript: {run_paths.run_dir / cleaned_path}")
    return lines


def _format_youtube_start_offset_result(run_paths) -> list[str]:
    if not run_paths.source_json.exists():
        return []
    source = read_json(run_paths.source_json)
    youtube_start_ms = source.get("youtube_start_ms")
    if youtube_start_ms is None:
        return []
    return [f"start offset: {int(youtube_start_ms) // 1000}s"]


def _format_transcript_quality_result(run_paths) -> list[str]:
    quality_path = run_paths.transcript_quality_json
    if not quality_path.exists():
        return []
    data = read_json(quality_path)
    metrics = data.get("metrics") or {}
    lines = [f"transcript quality: {data.get('recommendation', 'unknown')}"]
    details = [
        f"segments={metrics.get('segment_count', 0)}",
        f"total_chars={metrics.get('total_chars', 0)}",
        f"avg_chars={metrics.get('avg_chars_per_segment', 0)}",
        f"max_chars={metrics.get('max_chars_per_segment', 0)}",
        f"speakers={metrics.get('speaker_count', 0)}",
        f"dirty_markup={metrics.get('dirty_markup_count', 0)}",
        f"html_entities={metrics.get('html_entity_count', 0)}",
        f"repeated_lines={metrics.get('repeated_line_score', 0)}",
        f"repeated_phrases={metrics.get('repeated_phrase_score', 0)}",
    ]
    lines.append(f"quality metrics: {' '.join(details)}")
    issues = data.get("reasons") or data.get("warnings") or []
    if issues:
        lines.append(f"quality issues: {', '.join(issues)}")
    return lines


def _podcast_index_api_config_from_args(args) -> dict:
    config = {}
    if args.api_base_url:
        config["api_base_url"] = args.api_base_url
    if args.credentials_file:
        config["credentials_file"] = args.credentials_file
    else:
        config["api_key_env"] = args.api_key_env
        config["api_secret_env"] = args.api_secret_env
    if args.user_agent:
        config["user_agent"] = args.user_agent
    return config


def _format_podcast_index_feeds(feeds: list[dict]) -> str:
    lines = []
    for index, feed in enumerate(feeds, start=1):
        title = feed.get("title") or "<untitled>"
        feed_id = feed.get("id") or "<missing>"
        lines.append(f"{index}. {title} (feed_id={feed_id})")
        if feed.get("author"):
            lines.append(f"   author={feed['author']}")
        if feed.get("url"):
            lines.append(f"   feed_url={feed['url']}")
        if feed.get("link"):
            lines.append(f"   link={feed['link']}")
    return "\n".join(lines)


def _episode_has_transcript(episode: dict) -> bool:
    transcripts = episode.get("transcripts")
    if isinstance(transcripts, list) and transcripts:
        return True
    return bool(episode.get("transcriptUrl"))


def _format_podcast_index_episodes(episodes: list[dict]) -> str:
    lines = []
    for index, episode in enumerate(episodes, start=1):
        title = episode.get("title") or "<untitled>"
        transcript = "yes" if _episode_has_transcript(episode) else "no"
        lines.append(f"{index}. {title} (transcript={transcript})")
        if episode.get("guid"):
            lines.append(f"   guid={episode['guid']}")
        if episode.get("link"):
            lines.append(f"   link={episode['link']}")
    return "\n".join(lines)


def _format_itunes_results(results: list[dict]) -> str:
    lines = []
    for index, result in enumerate(results, start=1):
        title = result.get("title") or "<untitled>"
        lines.append(f"{index}. {title}")
        if result.get("artist"):
            lines.append(f"   artist={result['artist']}")
        if result.get("feed_url"):
            lines.append(f"   feed_url={result['feed_url']}")
        if result.get("apple_url"):
            lines.append(f"   apple_url={result['apple_url']}")
    return "\n".join(lines)


def _format_rss_episodes(episodes: list) -> str:
    lines = []
    for index, episode in enumerate(episodes, start=1):
        transcript = "yes" if episode.transcript_url else "no"
        lines.append(f"{index}. {episode.title} (transcript={transcript})")
        if episode.episode_url:
            lines.append(f"   episode_url={episode.episode_url}")
        if episode.transcript_url:
            lines.append(f"   transcript_url={episode.transcript_url}")
        if episode.enclosure_url:
            lines.append(f"   enclosure_url={episode.enclosure_url}")
    return "\n".join(lines)


def _write_yaml(path: str | Path, data: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _is_apple_podcasts_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in APPLE_PODCAST_HOSTS


def _select_episode(episodes: list, select_index: int):
    if select_index < 1 or select_index > len(episodes):
        raise ValueError(f"--select-index out of range: {select_index}")
    return episodes[select_index - 1]


def _build_rss_episode_source_from_url(feed_url: str, select_index: int) -> dict:
    episodes = fetch_podcast_episodes(feed_url)
    episode = _select_episode(episodes, select_index)
    return build_podcast_rss_episode_source_config(
        feed_url=feed_url,
        episode=episode,
    )


def _build_apple_episode_source_from_url(
    apple_url: str,
    select_index: int,
    *,
    country: str,
    api_base_url: str | None,
) -> tuple[dict, str]:
    lookup_config = {
        "url": apple_url,
        "country": country,
    }
    if api_base_url:
        lookup_config["api_base_url"] = api_base_url
    result = fetch_itunes_podcast_lookup(lookup_config)
    feed_url = result["feed_url"]
    return _build_rss_episode_source_from_url(feed_url, select_index), feed_url


def run_pipeline(
    workspace: str,
    run_id: str,
    source_config_path: str | None,
    local_config_path: str,
    from_stage: str,
    to_stage: str,
    transcript_file: str | None = None,
    podcast_feed: str | None = None,
    episode_url: str | None = None,
    title: str | None = None,
    original_url: str | None = None,
    input_info_extra: dict | None = None,
) -> str:
    source_config, input_info = _source_config_and_input(
        source_config_path,
        transcript_file,
        podcast_feed,
        episode_url,
        title,
        original_url,
    )
    if input_info_extra:
        input_info.update(input_info_extra)
    local_config = load_yaml(Path(local_config_path))
    require_keys(local_config, ["llm", "tts", "publish"])

    run_paths = create_run(workspace, run_id)
    stage_index = PIPELINE_STAGES.index(from_stage)
    stop_index = PIPELINE_STAGES.index(to_stage)
    if stop_index < stage_index:
        raise ValueError("--to-stage must be the same as or after --from-stage")
    status = init_run_status(
        run_paths,
        from_stage=from_stage,
        to_stage=to_stage,
        input_info=input_info,
        stages=PIPELINE_STAGES,
    )
    raw_path: Path | None = None
    outputs: list[str] = []

    if stage_index <= PIPELINE_STAGES.index("ingest") <= stop_index:
        raw_path = _run_stage(
            status,
            run_paths,
            "ingest",
            lambda: ingest_transcript_source(source_config["source"], run_paths),
        )
        outputs.append(f"ingest: {raw_path}")
        outputs.extend(_format_transcript_candidate_result(run_paths))
        outputs.extend(_format_youtube_start_offset_result(run_paths))

    if stage_index <= PIPELINE_STAGES.index("normalize") <= stop_index:
        def normalize_stage() -> Path:
            nonlocal raw_path
            raw_path = _raw_transcript_path(run_paths)
            return normalize_transcript(run_paths, raw_path)

        normalized_path = _run_stage(status, run_paths, "normalize", normalize_stage)
        outputs.append(f"normalize: {normalized_path}")
        outputs.extend(_format_transcript_quality_result(run_paths))

    if stage_index <= PIPELINE_STAGES.index("adapt") <= stop_index:
        def adapt_stage() -> tuple[str, dict]:
            script_path = adapt_to_chinese(
                run_paths,
                local_config["llm"],
                local_config.get("adapt"),
            )
            script_check = check_run_artifacts(run_paths, checks=("script",))
            return script_path, script_check

        script_path, script_check = _run_stage(status, run_paths, "adapt", adapt_stage)
        outputs.append(f"adapt: {script_path}")
        outputs.append(f"check script: {script_check['script_segments']} segments")

    if stage_index <= PIPELINE_STAGES.index("synthesize") <= stop_index:
        def synthesize_stage() -> tuple[dict | None, dict, str, dict]:
            speaker_voice_result = infer_speaker_voices_if_enabled(run_paths, local_config)
            override_result = apply_script_overrides(run_paths, local_config.get("overrides"))
            manifest_path = synthesize_segments(
                run_paths,
                local_config["tts"],
                local_config.get("speaker_voices"),
            )
            segment_check = check_run_artifacts(run_paths, checks=("segments",))
            return speaker_voice_result, override_result, manifest_path, segment_check

        speaker_voice_result, override_result, manifest_path, segment_check = _run_stage(
            status,
            run_paths,
            "synthesize",
            synthesize_stage,
        )
        if speaker_voice_result:
            outputs.append(_format_speaker_voice_result(speaker_voice_result))
        if override_result["rules"]:
            outputs.append(
                "overrides: "
                f"{override_result['replacements']} replacements "
                f"from {override_result['rules']} rules"
            )
        outputs.append(f"synthesize: {manifest_path}")
        outputs.append(f"check segments: {segment_check['audio_segments']} files")

    if stage_index <= PIPELINE_STAGES.index("assemble") <= stop_index:
        def assemble_stage() -> tuple[str, dict]:
            audio_path = assemble_audio(run_paths)
            output_check = check_run_artifacts(run_paths, checks=("output",))
            return audio_path, output_check

        audio_path, output_check = _run_stage(status, run_paths, "assemble", assemble_stage)
        outputs.append(f"assemble: {audio_path}")
        outputs.append(
            "check output: "
            f"{output_check['output_duration_seconds']:.3f}s, "
            f"{output_check['output_sample_rate']} Hz, "
            f"{output_check['output_channels']} ch"
        )

    if stage_index <= PIPELINE_STAGES.index("publish") <= stop_index:
        feed_path = _run_stage(
            status,
            run_paths,
            "publish",
            lambda: publish_episode(run_paths, local_config["publish"]),
        )
        outputs.append(f"publish: {feed_path}")

    mark_run_succeeded(status, run_paths)
    if run_paths.output_audio.exists():
        outputs.append(f"audio: {run_paths.output_audio}")
    feed_path = run_paths.publish_dir / "feed.xml"
    if feed_path.exists():
        outputs.append(f"feed: {feed_path}")
    if run_paths.stable_feed.exists():
        outputs.append(f"stable feed: {run_paths.stable_feed}")
    return "\n".join(outputs)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from . import __version__

        print(__version__)
        return 0

    if args.command == "ingest":
        config = load_yaml(Path(args.source_config))
        require_keys(config, ["source"])
        run_paths = create_run(args.workspace, args.run_id)
        raw_path = ingest_transcript_source(config["source"], run_paths)
        print(raw_path)
        return 0

    if args.command == "normalize":
        run_paths = create_run(args.workspace, args.run_id)
        output = normalize_transcript(run_paths, Path(args.raw_transcript))
        print(output)
        for line in _format_youtube_start_offset_result(run_paths):
            print(line)
        for line in _format_transcript_quality_result(run_paths):
            print(line)
        return 0

    if args.command == "publish":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["publish"])
        run_paths = create_run(args.workspace, args.run_id)
        output = publish_episode(run_paths, config["publish"])
        print(output)
        return 0

    if args.command == "script":
        run_paths = create_run(args.workspace, args.run_id)
        try:
            output = preview_chinese_script(run_paths)
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        print(output)
        return 0

    if args.command == "overrides":
        config = load_yaml(Path(args.local_config))
        run_paths = create_run(args.workspace, args.run_id)
        try:
            result = apply_script_overrides(run_paths, config.get("overrides"))
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"overrides: {result['replacements']} replacements from {result['rules']} rules")
        print(f"script: {result['script']}")
        return 0

    if args.command == "assemble":
        run_paths = create_run(args.workspace, args.run_id)
        output = assemble_audio(run_paths)
        print(output)
        return 0

    if args.command == "synthesize":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["tts"])
        run_paths = create_run(args.workspace, args.run_id)
        speaker_voice_result = infer_speaker_voices_if_enabled(run_paths, config)
        if speaker_voice_result:
            print(_format_speaker_voice_result(speaker_voice_result))
        output = synthesize_segments(run_paths, config["tts"], config.get("speaker_voices"))
        print(output)
        return 0

    if args.command == "speaker-voices":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["llm"])
        run_paths = create_run(args.workspace, args.run_id)
        result = infer_speaker_voices(run_paths, config["llm"], config.get("speaker_voices"))
        print(_format_speaker_voice_result(result))
        return 0

    if args.command == "speaker-profiles":
        try:
            if args.speaker_profiles_command == "compare":
                report = compare_speaker_profiles(
                    [Path(value) for value in args.run_dir],
                    same_threshold=args.same_threshold,
                    possible_threshold=args.possible_threshold,
                )
                if args.output_json:
                    write_json(args.output_json, report)
                    print(f"speaker similarity report: {args.output_json}")
                print(format_speaker_similarity_summary(report))
                return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    if args.command == "podcast-index":
        try:
            api_config = _podcast_index_api_config_from_args(args)
            if args.podcast_index_command == "search":
                search_config = {
                    **api_config,
                    "endpoint": "search/bytitle" if args.by_title else "search/byterm",
                    "query": args.query,
                    "max": args.max,
                }
                if args.clean:
                    search_config["clean"] = True
                print(_format_podcast_index_feeds(fetch_podcast_search(search_config)))
                return 0

            if args.podcast_index_command == "episodes":
                episode_config = {
                    **api_config,
                    "endpoint": "episodes/byfeedid",
                    "feed_id": args.feed_id,
                    "max_episodes": args.max,
                }
                episodes = fetch_podcast_index_episodes(episode_config)
                print(_format_podcast_index_episodes(episodes))
                if args.select_index is not None:
                    if args.select_index < 1 or args.select_index > len(episodes):
                        raise ValueError(f"--select-index out of range: {args.select_index}")
                    source_config = build_episode_source_config(
                        feed_id=args.feed_id,
                        episode=episodes[args.select_index - 1],
                        credentials_config=api_config,
                        api_base_url=args.api_base_url,
                        max_episodes=args.max,
                    )
                    if args.source_config_out:
                        _write_yaml(args.source_config_out, source_config)
                        print(f"source config: {args.source_config_out}")
                    else:
                        print(yaml.safe_dump(source_config, allow_unicode=True, sort_keys=False))
                return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    if args.command == "itunes":
        try:
            if args.itunes_command == "search":
                search_config = {
                    "query": args.query,
                    "country": args.country,
                    "max": args.max,
                }
                if args.api_base_url:
                    search_config["api_base_url"] = args.api_base_url
                results = fetch_itunes_podcast_search(search_config)
                print(_format_itunes_results(results))
                if args.select_index is not None:
                    if args.select_index < 1 or args.select_index > len(results):
                        raise ValueError(f"--select-index out of range: {args.select_index}")
                    source_config = build_podcast_rss_source_config(
                        results[args.select_index - 1]
                    )
                    if args.source_config_out:
                        _write_yaml(args.source_config_out, source_config)
                        print(f"source config: {args.source_config_out}")
                    else:
                        print(yaml.safe_dump(source_config, allow_unicode=True, sort_keys=False))
                return 0
            if args.itunes_command == "episodes":
                lookup_config = {
                    "url": args.url,
                    "country": args.country,
                }
                if args.api_base_url:
                    lookup_config["api_base_url"] = args.api_base_url
                result = fetch_itunes_podcast_lookup(lookup_config)
                feed_url = result["feed_url"]
                episodes = fetch_podcast_episodes(feed_url)
                print(f"feed_url={feed_url}")
                print(_format_rss_episodes(episodes))
                if args.select_index is not None:
                    if args.select_index < 1 or args.select_index > len(episodes):
                        raise ValueError(f"--select-index out of range: {args.select_index}")
                    source_config = build_podcast_rss_episode_source_config(
                        feed_url=feed_url,
                        episode=episodes[args.select_index - 1],
                    )
                    if args.source_config_out:
                        _write_yaml(args.source_config_out, source_config)
                        print(f"source config: {args.source_config_out}")
                    else:
                        print(yaml.safe_dump(source_config, allow_unicode=True, sort_keys=False))
                return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    if args.command == "rss":
        try:
            if args.rss_command == "episodes":
                episodes = fetch_podcast_episodes(args.feed_url)
                print(_format_rss_episodes(episodes))
                if args.select_index is not None:
                    if args.select_index < 1 or args.select_index > len(episodes):
                        raise ValueError(f"--select-index out of range: {args.select_index}")
                    source_config = build_podcast_rss_episode_source_config(
                        feed_url=args.feed_url,
                        episode=episodes[args.select_index - 1],
                    )
                    if args.source_config_out:
                        _write_yaml(args.source_config_out, source_config)
                        print(f"source config: {args.source_config_out}")
                    else:
                        print(yaml.safe_dump(source_config, allow_unicode=True, sort_keys=False))
                return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    if args.command == "article":
        try:
            if args.article_command == "convert":
                output = run_article_pipeline(
                    workspace=args.workspace,
                    run_id=args.run_id,
                    local_config_path=args.local_config,
                    from_stage=args.from_stage,
                    to_stage=args.to_stage,
                    url=args.url,
                    article_file=args.file,
                    title=args.title,
                )
                print(output)
                return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    if args.command == "audio":
        try:
            if args.audio_command == "convert":
                output = run_audio_pipeline(
                    workspace=args.workspace,
                    run_id=args.run_id,
                    audio_file=args.audio_file,
                    local_config_path=args.local_config,
                    from_stage=args.from_stage,
                    to_stage=args.to_stage,
                    title=args.title,
                )
                print(output)
                return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    if args.command == "episode":
        try:
            if args.episode_command == "convert":
                source_config_path = args.source_config
                transcript_file = args.transcript_file
                input_info_line = None
                input_info_extra = None
                if args.url:
                    feed_url = None
                    if _is_apple_podcasts_url(args.url):
                        if args.select_index is None:
                            raise ValueError(
                                "Apple Podcasts URL input requires --select-index"
                            )
                        source_config, feed_url = _build_apple_episode_source_from_url(
                            args.url,
                            args.select_index,
                            country=args.itunes_country,
                            api_base_url=args.itunes_api_base_url,
                        )
                    elif args.select_index is not None:
                        source_config = _build_rss_episode_source_from_url(
                            args.url,
                            args.select_index,
                        )
                        feed_url = args.url
                    else:
                        source_config = build_on_demand_source_config(
                            args.url,
                            title=args.title,
                            language=args.language,
                        )
                    run_paths = create_run(args.workspace, args.run_id)
                    source_config_path = str(
                        Path(args.source_config_out)
                        if args.source_config_out
                        else run_paths.run_dir / "source.input.yaml"
                    )
                    _write_yaml(source_config_path, source_config)
                    input_info_line = f"source config: {source_config_path}"
                    if feed_url:
                        input_info_line = f"feed_url={feed_url}\n{input_info_line}"
                    input_info_extra = {"episode_url": args.url}
                    if feed_url:
                        input_info_extra["feed_url"] = feed_url
                        input_info_extra["selected_episode_index"] = args.select_index

                output = run_pipeline(
                    args.workspace,
                    args.run_id,
                    source_config_path,
                    args.local_config,
                    args.from_stage,
                    args.to_stage,
                    transcript_file,
                    None,
                    args.url,
                    args.title,
                    args.url,
                    input_info_extra,
                )
                if input_info_line:
                    print(input_info_line)
                print(output)
                return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    if args.command == "adapt":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["llm"])
        run_paths = create_run(args.workspace, args.run_id)
        try:
            output = adapt_to_chinese(run_paths, config["llm"], config.get("adapt"))
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        print(output)
        return 0

    if args.command == "run":
        try:
            output = run_pipeline(
                args.workspace,
                args.run_id,
                args.source_config,
                args.local_config,
                args.from_stage,
                args.to_stage,
                args.transcript_file,
                args.podcast_feed,
                args.episode_url,
                args.title,
                args.original_url,
            )
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        print(output)
        return 0

    if args.command == "check":
        run_paths = create_run(args.workspace, args.run_id)
        try:
            result = check_run_artifacts(
                run_paths,
                checks=tuple(args.checks),
                max_script_chars=args.max_script_chars,
            )
        except CheckError as error:
            print(str(error), file=sys.stderr)
            return 1
        for key, value in result.items():
            print(f"{key}={value}")
        return 0

    parser.print_help()
    return 0
