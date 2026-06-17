from pathlib import Path

import pytest

from babelecho.ingest import ingest_transcript_source
from babelecho.jsonio import read_json
from babelecho.paths import create_run


def write_feed(path: Path, transcript_url: str | None) -> None:
    transcript_tag = (
        f'<podcast:transcript url="{transcript_url}" type="text/vtt" language="en" />'
        if transcript_url
        else ""
    )
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Example Podcast</title>
    <item>
      <title>Public Transcript Episode</title>
      <link>https://example.com/episodes/public-transcript</link>
      <guid>episode-guid-1</guid>
      <enclosure url="https://cdn.example.com/episode.mp3" type="audio/mpeg" />
      {transcript_tag}
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )


def test_ingest_podcast_rss_uses_episode_transcript(tmp_path: Path):
    transcript = tmp_path / "episode.vtt"
    transcript.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello.\n", encoding="utf-8")
    feed = tmp_path / "feed.xml"
    write_feed(feed, str(transcript))
    run_paths = create_run(tmp_path / "workspace", "rss-demo")

    raw_path = ingest_transcript_source(
        {
            "type": "podcast_rss",
            "feed_url": str(feed),
            "episode_url": "https://example.com/episodes/public-transcript",
        },
        run_paths,
    )

    source = read_json(run_paths.source_json)
    assert raw_path == run_paths.transcript_dir / "raw.vtt"
    assert raw_path.read_text(encoding="utf-8").startswith("WEBVTT")
    assert source["source_type"] == "podcast_rss"
    assert source["feed_url"] == str(feed)
    assert source["episode_url"] == "https://example.com/episodes/public-transcript"
    assert source["transcript_url"] == str(transcript)
    assert source["title"] == "Public Transcript Episode"
    assert source["original_url"] == "https://example.com/episodes/public-transcript"


def test_ingest_podcast_rss_fails_when_episode_has_no_transcript(tmp_path: Path):
    feed = tmp_path / "feed.xml"
    write_feed(feed, None)
    run_paths = create_run(tmp_path / "workspace", "rss-missing")

    with pytest.raises(ValueError, match="No transcript found"):
        ingest_transcript_source(
            {
                "type": "podcast_rss",
                "feed_url": str(feed),
                "episode_url": "https://example.com/episodes/public-transcript",
            },
            run_paths,
        )
