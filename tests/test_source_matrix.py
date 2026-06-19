from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import subprocess
import sys
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

import yaml

from babelecho.episode_convert import build_on_demand_source_config
from babelecho.jsonio import read_json


def run_route_server(routes: dict[str, str]):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            response_body = routes.get(urlparse(self.path).path)
            if response_body is None:
                self.send_response(404)
                self.end_headers()
                return
            encoded = response_body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def write_local_config(path: Path) -> None:
    path.write_text(
        """
llm:
  provider: fixture
tts:
  provider: fixture
publish:
  base_url: "https://example.com/babelecho"
""",
        encoding="utf-8",
    )


def write_transcript(path: Path) -> None:
    path.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHost: Hello from the matrix.\n",
        encoding="utf-8",
    )


def rss_feed_xml(transcript: Path, selected_link: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Matrix Feed</title>
    <item>
      <title>Skipped Episode</title>
      <link>https://example.com/skipped</link>
    </item>
    <item>
      <title>Selected Matrix Episode</title>
      <link>{selected_link}</link>
      <guid>selected-matrix-guid</guid>
      <podcast:transcript url="{transcript}" type="text/vtt" language="en" />
    </item>
  </channel>
</rss>
"""


def run_convert_to_normalize(
    workspace: Path,
    local_config: Path,
    source_config: Path,
    run_id: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "episode",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            run_id,
            "--source-config",
            str(source_config),
            "--local-config",
            str(local_config),
            "--to-stage",
            "normalize",
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_source_entry_matrix_preserves_youtube_rss_and_itunes_routes(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    transcript = tmp_path / "episode.vtt"
    write_local_config(local_config)
    write_transcript(transcript)

    youtube_source = build_on_demand_source_config(
        "https://www.youtube.com/watch?v=matrix123&t=5s",
        title="Matrix YouTube",
        language="en",
    )
    assert youtube_source["source"]["type"] == "youtube_captions"
    assert youtube_source["source"]["url"] == (
        "https://www.youtube.com/watch?v=matrix123&t=5s"
    )
    assert youtube_source["source"]["youtube_start_ms"] == 5_000

    rss_feed = tmp_path / "feed.xml"
    rss_source_config = tmp_path / "rss-source.yaml"
    rss_feed.write_text(
        rss_feed_xml(transcript, "https://example.com/rss-selected"),
        encoding="utf-8",
    )
    rss_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "rss",
            "episodes",
            "--feed-url",
            str(rss_feed),
            "--select-index",
            "2",
            "--source-config-out",
            str(rss_source_config),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert rss_result.returncode == 0, rss_result.stderr
    assert "2. Selected Matrix Episode (transcript=yes)" in rss_result.stdout
    rss_config = yaml.safe_load(rss_source_config.read_text(encoding="utf-8"))
    assert rss_config["source"]["type"] == "podcast_rss"
    assert rss_config["source"]["feed_url"] == str(rss_feed)
    assert rss_config["source"]["episode_url"] == "https://example.com/rss-selected"

    rss_convert = run_convert_to_normalize(
        workspace,
        local_config,
        rss_source_config,
        "matrix-rss",
    )
    assert rss_convert.returncode == 0, rss_convert.stderr
    rss_source = read_json(workspace / "runs" / "matrix-rss" / "source.json")
    assert rss_source["source_type"] == "podcast_rss"
    assert rss_source["feed_url"] == str(rss_feed)
    assert rss_source["episode_url"] == "https://example.com/rss-selected"

    rss_direct_convert = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "episode",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "matrix-rss-direct",
            "--url",
            str(rss_feed),
            "--select-index",
            "2",
            "--local-config",
            str(local_config),
            "--to-stage",
            "normalize",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert rss_direct_convert.returncode == 0, rss_direct_convert.stderr
    rss_direct_source = read_json(
        workspace / "runs" / "matrix-rss-direct" / "source.json"
    )
    assert rss_direct_source["source_type"] == "podcast_rss"
    assert rss_direct_source["feed_url"] == str(rss_feed)
    assert rss_direct_source["episode_url"] == "https://example.com/rss-selected"

    routes: dict[str, str] = {}
    server = run_route_server(routes)
    itunes_source_config = tmp_path / "itunes-source.yaml"
    feed_url = f"http://127.0.0.1:{server.server_port}/feed.xml"
    routes["/lookup"] = json.dumps(
        {
            "results": [
                {
                    "wrapperType": "track",
                    "kind": "podcast",
                    "collectionName": "Matrix Podcast",
                    "artistName": "Fixture Host",
                    "feedUrl": feed_url,
                    "collectionViewUrl": (
                        "https://podcasts.apple.com/us/podcast/matrix/id123456"
                    ),
                }
            ]
        }
    )
    routes["/feed.xml"] = rss_feed_xml(transcript, "https://example.com/itunes-selected")
    try:
        itunes_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "itunes",
                "episodes",
                "--url",
                "https://podcasts.apple.com/us/podcast/matrix/id123456",
                "--api-base-url",
                f"http://127.0.0.1:{server.server_port}/lookup",
                "--select-index",
                "2",
                "--source-config-out",
                str(itunes_source_config),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        assert itunes_result.returncode == 0, itunes_result.stderr
        assert f"feed_url={feed_url}" in itunes_result.stdout
        assert "2. Selected Matrix Episode (transcript=yes)" in itunes_result.stdout
        itunes_config = yaml.safe_load(itunes_source_config.read_text(encoding="utf-8"))
        assert itunes_config["source"]["type"] == "podcast_rss"
        assert itunes_config["source"]["feed_url"] == feed_url
        assert (
            itunes_config["source"]["episode_url"]
            == "https://example.com/itunes-selected"
        )

        itunes_convert = run_convert_to_normalize(
            workspace,
            local_config,
            itunes_source_config,
            "matrix-itunes",
        )
        assert itunes_convert.returncode == 0, itunes_convert.stderr
        itunes_source = read_json(workspace / "runs" / "matrix-itunes" / "source.json")
        assert itunes_source["source_type"] == "podcast_rss"
        assert itunes_source["feed_url"] == feed_url
        assert itunes_source["episode_url"] == "https://example.com/itunes-selected"

        itunes_direct_convert = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "episode",
                "convert",
                "--workspace",
                str(workspace),
                "--run-id",
                "matrix-itunes-direct",
                "--url",
                "https://podcasts.apple.com/us/podcast/matrix/id123456",
                "--itunes-api-base-url",
                f"http://127.0.0.1:{server.server_port}/lookup",
                "--select-index",
                "2",
                "--local-config",
                str(local_config),
                "--to-stage",
                "normalize",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert itunes_direct_convert.returncode == 0, itunes_direct_convert.stderr
        itunes_direct_source = read_json(
            workspace / "runs" / "matrix-itunes-direct" / "source.json"
        )
        assert itunes_direct_source["source_type"] == "podcast_rss"
        assert itunes_direct_source["feed_url"] == feed_url
        assert (
            itunes_direct_source["episode_url"]
            == "https://example.com/itunes-selected"
        )
    finally:
        server.shutdown()
        server.server_close()
