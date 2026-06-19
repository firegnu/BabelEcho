from pathlib import Path
from xml.etree import ElementTree

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.publish import publish_episode


def test_publish_episode_writes_feed_and_artifacts(tmp_path: Path):
    run_paths = create_run(tmp_path, "publish-run")
    run_paths.output_audio.write_bytes(b"fake mp3")
    write_json(
        run_paths.source_json,
        {
            "run_id": "publish-run",
            "source_type": "podcast_rss",
            "title": "Sample Episode",
            "original_url": "https://example.com/sample",
            "feed_url": "https://example.com/feed.xml",
            "episode_url": "https://example.com/sample",
            "transcript_url": "https://example.com/sample.vtt",
        },
    )
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": "publish-run",
            "segments": [
                {"id": "1", "speaker": "Alice", "text": "Hello."},
                {"id": "2", "speaker": "Bob", "text": "Hi."},
            ],
        },
    )
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "publish-run",
            "segments": [
                {"id": "1", "speaker": "Alice", "text": "你好。"},
                {"id": "2", "speaker": "Bob", "text": "嗨。"},
            ],
        },
    )
    write_json(
        run_paths.transcript_quality_json,
        {
            "recommendation": "safe_to_adapt",
            "metrics": {"segment_count": 2, "speaker_count": 2},
            "warnings": [],
            "reasons": [],
        },
    )
    write_json(
        run_paths.script_dir / "speaker-voices.json",
        {
            "speaker_voices": {"Alice": "female_a", "Bob": "male_a"},
            "inferences": [
                {"speaker": "Alice", "gender": "female", "confidence": 0.9},
                {"speaker": "Bob", "gender": "male", "confidence": 0.8},
            ],
        },
    )

    feed_path = publish_episode(run_paths, {"base_url": "https://example.com/babelecho"})

    assert Path(feed_path).exists()
    assert (run_paths.publish_dir / "episodes" / "publish-run" / "audio.mp3").exists()
    assert (run_paths.publish_dir / "episodes" / "publish-run" / "artifact.json").exists()
    assert (run_paths.workspace / "published" / "feed.xml").exists()
    assert (run_paths.workspace / "published" / "index.json").exists()
    assert (run_paths.workspace / "published" / "episodes" / "publish-run" / "audio.mp3").exists()
    assert (run_paths.workspace / "published" / "episodes" / "publish-run" / "artifact.json").exists()
    metadata = read_json(run_paths.workspace / "published" / "episodes" / "publish-run" / "metadata.json")
    assert metadata["audio_url"] == "https://example.com/babelecho/episodes/publish-run/audio.mp3"
    artifact = read_json(run_paths.workspace / "published" / "episodes" / "publish-run" / "artifact.json")
    assert artifact["schema_version"] == "1.0"
    assert artifact["run_id"] == "publish-run"
    assert artifact["route"] == "transcript_first"
    assert artifact["status"] == "succeeded"
    assert artifact["source"]["type"] == "podcast_rss"
    assert artifact["source"]["provider"] == "rss"
    assert artifact["quality"]["recommendation"] == "safe_to_adapt"
    assert artifact["media"]["audio_path"] == "audio.mp3"
    assert artifact["media"]["file_size_bytes"] == len(b"fake mp3")
    assert artifact["artifacts"]["script_zh"] == "transcript.zh.json"
    assert artifact["speakers"] == [
        {
            "id": "speaker_1",
            "display_name": "Alice",
            "voice_role": "female_a",
            "inferred_gender": "female",
            "segment_count": 1,
        },
        {
            "id": "speaker_2",
            "display_name": "Bob",
            "voice_role": "male_a",
            "inferred_gender": "male",
            "segment_count": 1,
        },
    ]
    index = read_json(run_paths.workspace / "published" / "index.json")
    assert index["schema_version"] == "1.0"
    assert index["episodes"] == [
        {
            "run_id": "publish-run",
            "title": "Sample Episode",
            "route": "transcript_first",
            "status": "succeeded",
            "source_type": "podcast_rss",
            "quality_recommendation": "safe_to_adapt",
            "speaker_count": 2,
            "duration_seconds": None,
            "published_at": artifact["published_at"],
            "audio_path": "episodes/publish-run/audio.mp3",
            "artifact_path": "episodes/publish-run/artifact.json",
        }
    ]
    root = ElementTree.parse(feed_path).getroot()
    assert root.tag == "rss"
    assert root.find("./channel/item/title").text == "Sample Episode"


def test_publish_episode_maps_article_route_and_public_source_metadata(tmp_path: Path):
    run_paths = create_run(tmp_path, "article-publish-run")
    run_paths.output_audio.write_bytes(b"fake mp3")
    write_json(
        run_paths.source_json,
        {
            "run_id": "article-publish-run",
            "source_type": "web_article",
            "provider": "trafilatura",
            "title": "AI Agent Article",
            "original_url": "https://example.com/agents",
            "input_url": "https://example.com/agents",
            "site_name": "Example Research",
            "author": "Jane Author",
            "published_time": "2026-06-18",
            "excerpt": "A practical article about agent systems.",
        },
    )
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": "article-publish-run",
            "segments": [
                {
                    "id": "article-0001",
                    "speaker": None,
                    "text": "This is an article paragraph.",
                    "source": "article",
                }
            ],
        },
    )
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "article-publish-run",
            "segments": [
                {
                    "id": "article-0001",
                    "speaker": None,
                    "text": "这是一段文章内容。",
                }
            ],
        },
    )
    write_json(
        run_paths.transcript_quality_json,
        {
            "recommendation": "safe_to_adapt",
            "metrics": {"segment_count": 1, "speaker_count": 0, "source_type": "web_article"},
            "warnings": [],
            "reasons": [],
        },
    )

    publish_episode(run_paths, {"base_url": "https://example.com/babelecho"})

    artifact = read_json(
        run_paths.workspace
        / "published"
        / "episodes"
        / "article-publish-run"
        / "artifact.json"
    )
    assert artifact["route"] == "article_reading"
    assert artifact["source"] == {
        "type": "web_article",
        "provider": "trafilatura",
        "input_url": "https://example.com/agents",
        "episode_url": "https://example.com/agents",
        "transcript_url": None,
        "feed_url": None,
        "site_name": "Example Research",
        "author": "Jane Author",
        "published_time": "2026-06-18",
        "excerpt": "A practical article about agent systems.",
    }
    assert artifact["speakers"] == []
    assert artifact["ui"]["badges"][0] == "article-reading"
    index = read_json(run_paths.workspace / "published" / "index.json")
    assert index["episodes"][0]["route"] == "article_reading"
    assert index["episodes"][0]["source_type"] == "web_article"
    assert index["episodes"][0]["speaker_count"] == 0
