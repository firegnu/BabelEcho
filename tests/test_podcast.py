from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

import pytest

from babelecho.ingest import ingest_transcript_source
from babelecho.jsonio import read_json
from babelecho.paths import create_run
from babelecho.podcast import (
    build_podcast_rss_episode_source_config,
    list_podcast_episodes,
)


def run_podcast_index_api_server(response_body: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.requests.append(
                {
                    "path": self.path,
                    "headers": dict(self.headers),
                }
            )
            encoded = response_body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.requests = []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


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


def test_list_podcast_episodes_reports_transcript_availability(tmp_path: Path):
    transcript = tmp_path / "episode.vtt"
    transcript.write_text("WEBVTT\n", encoding="utf-8")
    feed = tmp_path / "feed.xml"
    feed.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Example Podcast</title>
    <item>
      <title>First Episode</title>
      <link>https://example.com/first</link>
      <guid>first-guid</guid>
      <enclosure url="https://cdn.example.com/first.mp3" type="audio/mpeg" />
      <podcast:transcript url="{transcript}" type="text/vtt" language="en" />
    </item>
    <item>
      <title>Second Episode</title>
      <guid>second-guid</guid>
      <enclosure url="https://cdn.example.com/second.mp3" type="audio/mpeg" />
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    episodes = list_podcast_episodes(feed.read_bytes())

    assert [episode.title for episode in episodes] == ["First Episode", "Second Episode"]
    assert episodes[0].episode_url == "https://example.com/first"
    assert episodes[0].transcript_url == str(transcript)
    assert episodes[0].enclosure_url == "https://cdn.example.com/first.mp3"
    assert episodes[1].episode_url == "second-guid"
    assert episodes[1].transcript_url is None


def test_build_podcast_rss_episode_source_config_uses_episode_url():
    episodes = list_podcast_episodes(
        b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <item>
      <title>Selected Episode</title>
      <link>https://example.com/selected</link>
      <podcast:transcript url="https://example.com/selected.vtt" type="text/vtt" />
    </item>
  </channel>
</rss>
"""
    )

    source_config = build_podcast_rss_episode_source_config(
        feed_url="https://feeds.example.com/show.xml",
        episode=episodes[0],
    )

    assert source_config == {
        "source": {
            "type": "podcast_rss",
            "feed_url": "https://feeds.example.com/show.xml",
            "episode_url": "https://example.com/selected",
            "title": "Selected Episode",
            "original_url": "https://example.com/selected",
        }
    }


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


def test_ingest_podcast_index_episode_prefers_transcripts_list(tmp_path: Path):
    transcript = tmp_path / "episode.srt"
    transcript.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello.\n", encoding="utf-8")
    fallback = tmp_path / "fallback.txt"
    fallback.write_text("Fallback transcript", encoding="utf-8")
    episode_json = tmp_path / "episode.json"
    episode_json.write_text(
        f"""{{
  "episode": {{
    "title": "PodcastIndex Episode",
    "link": "https://example.com/episodes/pi",
    "enclosureUrl": "https://cdn.example.com/pi.mp3",
    "transcriptUrl": "{fallback}",
    "transcripts": [
      {{
        "url": "{transcript}",
        "type": "application/srt"
      }}
    ]
  }}
}}
""",
        encoding="utf-8",
    )
    run_paths = create_run(tmp_path / "workspace", "pi-demo")

    raw_path = ingest_transcript_source(
        {
            "type": "podcast_index_episode",
            "episode_json": str(episode_json),
        },
        run_paths,
    )

    source = read_json(run_paths.source_json)
    assert raw_path == run_paths.transcript_dir / "raw.srt"
    assert raw_path.read_text(encoding="utf-8").startswith("1\n")
    assert source["source_type"] == "podcast_index_episode"
    assert source["episode_json"] == str(episode_json)
    assert source["transcript_url"] == str(transcript)
    assert source["title"] == "PodcastIndex Episode"
    assert source["original_url"] == "https://example.com/episodes/pi"


def test_ingest_podcast_index_episode_falls_back_to_transcript_url(tmp_path: Path):
    transcript = tmp_path / "episode.txt"
    transcript.write_text("Plain transcript", encoding="utf-8")
    episode_json = tmp_path / "episode.json"
    episode_json.write_text(
        f"""{{
  "title": "PodcastIndex Fallback Episode",
  "guid": "episode-guid-2",
  "transcriptUrl": "{transcript}",
  "transcripts": []
}}
""",
        encoding="utf-8",
    )
    run_paths = create_run(tmp_path / "workspace", "pi-fallback")

    raw_path = ingest_transcript_source(
        {
            "type": "podcast_index_episode",
            "episode_json": str(episode_json),
        },
        run_paths,
    )

    source = read_json(run_paths.source_json)
    assert raw_path == run_paths.transcript_dir / "raw.txt"
    assert raw_path.read_text(encoding="utf-8") == "Plain transcript"
    assert source["transcript_url"] == str(transcript)
    assert source["title"] == "PodcastIndex Fallback Episode"
    assert source["original_url"] == "episode-guid-2"


def test_ingest_podcast_index_api_episode_by_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PODCASTINDEX_API_KEY", "api-key")
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "api-secret")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    transcript = tmp_path / "episode.txt"
    transcript.write_text("API transcript", encoding="utf-8")
    server = run_podcast_index_api_server(
        f"""{{
  "episode": {{
    "title": "API Episode",
    "link": "https://example.com/api-episode",
    "transcripts": [
      {{
        "url": "{transcript}",
        "type": "text/plain"
      }}
    ]
  }}
}}
"""
    )
    try:
        run_paths = create_run(tmp_path / "workspace", "pi-api-demo")

        raw_path = ingest_transcript_source(
            {
                "type": "podcast_index_api",
                "api_base_url": f"http://127.0.0.1:{server.server_port}/api/1.0",
                "endpoint": "episodes/byid",
                "episode_id": 123,
                "api_key_env": "PODCASTINDEX_API_KEY",
                "api_secret_env": "PODCASTINDEX_API_SECRET",
                "user_agent": "BabelEchoTest/0.1",
            },
            run_paths,
        )
    finally:
        server.shutdown()
        server.server_close()

    request = server.requests[0]
    parsed = urlparse(request["path"])
    source = read_json(run_paths.source_json)
    assert parse_qs(parsed.query) == {"id": ["123"], "fulltext": ["true"]}
    assert request["headers"]["User-Agent"] == "BabelEchoTest/0.1"
    assert request["headers"]["X-Auth-Key"] == "api-key"
    assert request["headers"]["X-Auth-Date"]
    assert request["headers"]["Authorization"]
    assert raw_path == run_paths.transcript_dir / "raw.txt"
    assert raw_path.read_text(encoding="utf-8") == "API transcript"
    assert source["source_type"] == "podcast_index_api"
    assert source["podcast_index_endpoint"] == "episodes/byid"
    assert source["podcast_index_episode_id"] == 123
    assert source["transcript_url"] == str(transcript)
    assert source["title"] == "API Episode"
    assert source["original_url"] == "https://example.com/api-episode"
