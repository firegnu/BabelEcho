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
            "title": "Sample Episode",
            "original_url": "https://example.com/sample",
            "transcript_url": "https://example.com/sample.vtt",
        },
    )
    write_json(
        run_paths.normalized_transcript_json,
        {"episode_id": "publish-run", "segments": []},
    )
    write_json(
        run_paths.chinese_script_json,
        {"episode_id": "publish-run", "segments": []},
    )

    feed_path = publish_episode(run_paths, {"base_url": "https://example.com/babelecho"})

    assert Path(feed_path).exists()
    assert (run_paths.publish_dir / "episodes" / "publish-run" / "audio.mp3").exists()
    assert (run_paths.workspace / "published" / "feed.xml").exists()
    assert (run_paths.workspace / "published" / "episodes" / "publish-run" / "audio.mp3").exists()
    metadata = read_json(run_paths.workspace / "published" / "episodes" / "publish-run" / "metadata.json")
    assert metadata["audio_url"] == "https://example.com/babelecho/episodes/publish-run/audio.mp3"
    root = ElementTree.parse(feed_path).getroot()
    assert root.tag == "rss"
    assert root.find("./channel/item/title").text == "Sample Episode"
