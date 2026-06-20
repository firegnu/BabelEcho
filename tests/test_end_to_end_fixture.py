from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

import yaml

from babelecho.jsonio import read_json, write_json
from babelecho.cli import run_pipeline


def worktree_python_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    return env


def run_podcast_index_api_server(response_body: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
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


def run_podcast_index_route_server(routes: dict[str, str]):
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


def write_fake_yt_dlp(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake-yt-dlp"
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return script


def test_end_to_end_fixture_pipeline(tmp_path: Path):
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    source_config.write_text(
        f"""
source:
  type: transcript_url
  transcript_url: "{transcript}"
  title: "Sample Episode"
  original_url: "https://example.com/sample"
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    commands = [
        ["ingest", "--source-config", str(source_config)],
        [
            "normalize",
            "--raw-transcript",
            str(workspace / "runs" / "demo" / "transcript" / "raw.vtt"),
        ],
        ["adapt", "--local-config", str(local_config)],
        ["synthesize", "--local-config", str(local_config)],
    ]
    for command in commands:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                command[0],
                "--workspace",
                str(workspace),
                "--run-id",
                "demo",
                *command[1:],
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        if command[0] == "normalize":
            assert "transcript quality:" in result.stdout
            assert "quality metrics:" in result.stdout

    assert (workspace / "runs" / "demo" / "script" / "zh.json").exists()
    assert (workspace / "runs" / "demo" / "segments" / "0001.wav").exists()


def test_run_pipeline_uses_cleaned_youtube_transcript_for_normalize(tmp_path: Path):
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "youtube-source.yaml"
    local_config = tmp_path / "local.yaml"
    fake_yt_dlp = write_fake_yt_dlp(
        tmp_path,
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
file="${out%\\.%(ext)s}.en.vtt"
cat > "$file" <<'VTT'
WEBVTT

00:00:00.000 --> 00:00:01.000
AI agents

00:00:01.200 --> 00:00:02.000
can call tools.
VTT
""",
    )
    source_config.write_text(
        f"""
source:
  type: youtube_captions
  url: "https://www.youtube.com/watch?v=abc123&t=1s"
  language: "en"
  yt_dlp_command: "{fake_yt_dlp}"
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    output = run_pipeline(
        str(workspace),
        "youtube-normalize",
        str(source_config),
        str(local_config),
        "ingest",
        "normalize",
    )

    run_dir = workspace / "runs" / "youtube-normalize"
    source = read_json(run_dir / "source.json")
    normalized = read_json(run_dir / "transcript" / "normalized.json")
    assert source["raw_transcript"] == "transcript/raw.vtt"
    assert source["normalized_transcript_source"] == "transcript/cleaned.vtt"
    assert source["youtube_start_ms"] == 1_000
    assert len(normalized["segments"]) == 1
    assert normalized["segments"][0]["text"] == "AI agents can call tools."
    assert "transcript candidates: 1" in output
    assert "start offset: 1s" in output
    assert "selected transcript: youtube_captions/en/vtt score=" in output
    assert "warnings: short transcript" in output
    assert "cleaned transcript:" in output
    assert "transcript/cleaned.vtt" in output
    assert "transcript quality:" in output
    assert "quality metrics:" in output


def test_run_command_executes_fixture_pipeline(tmp_path: Path):
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    source_config.write_text(
        f"""
source:
  type: transcript_url
  transcript_url: "{transcript}"
  title: "Sample Episode"
  original_url: "https://example.com/sample"
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "demo",
            "--source-config",
            str(source_config),
            "--local-config",
            str(local_config),
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "output/audio.mp3" in result.stdout
    assert "publish/feed.xml" in result.stdout
    assert "published/feed.xml" in result.stdout
    assert (workspace / "runs" / "demo" / "output" / "audio.mp3").exists()
    assert (workspace / "runs" / "demo" / "publish" / "feed.xml").exists()
    assert (workspace / "published" / "feed.xml").exists()
    assert (workspace / "published" / "episodes" / "demo" / "audio.mp3").exists()
    assert (
        workspace
        / "runs"
        / "demo"
        / "publish"
        / "episodes"
        / "demo"
        / "transcript.zh.json"
    ).exists()
    zh_transcript = read_json(
        workspace
        / "runs"
        / "demo"
        / "publish"
        / "episodes"
        / "demo"
        / "transcript.zh.json"
    )
    first_zh = zh_transcript["segments"][0]
    assert first_zh["start_ms"] == 0
    assert first_zh["end_ms"] == 200
    assert first_zh["duration_ms"] == 200

    check_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "check",
            "--workspace",
            str(workspace),
            "--run-id",
            "demo",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert check_result.returncode == 0, check_result.stderr
    assert "script_segments=1" in check_result.stdout
    assert "audio_segments=1" in check_result.stdout
    assert "output_duration_seconds=" in check_result.stdout

    script_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "script",
            "--workspace",
            str(workspace),
            "--run-id",
            "demo",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert script_result.returncode == 0, script_result.stderr
    assert "script:" in script_result.stdout
    assert "workspace/runs/demo/script/zh.json" in script_result.stdout
    assert "0001" in script_result.stdout
    assert "中文口播：Welcome to the sample episode." in script_result.stdout
    assert "--from-stage synthesize" in script_result.stdout


def test_run_command_accepts_transcript_file_and_writes_status(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "manual-demo",
            "--transcript-file",
            str(transcript),
            "--title",
            "Manual Episode",
            "--local-config",
            str(local_config),
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    run_dir = workspace / "runs" / "manual-demo"
    assert result.returncode == 0, result.stderr
    assert (run_dir / "output" / "audio.mp3").exists()
    assert (run_dir / "publish" / "feed.xml").exists()

    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "transcript_file"
    assert source["title"] == "Manual Episode"
    assert source["transcript_file"] == str(transcript)

    status = read_json(run_dir / "run.json")
    assert status["status"] == "succeeded"
    assert status["from_stage"] == "ingest"
    assert status["input"]["transcript_file"] == str(transcript)
    assert status["outputs"]["audio"] == "output/audio.mp3"
    assert status["outputs"]["feed"] == "publish/feed.xml"
    assert status["outputs"]["stable_feed"] == "published/feed.xml"
    assert [stage["status"] for stage in status["stages"]] == [
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
    ]


def test_run_pipeline_infers_speaker_voices_once_before_synthesize(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    transcript = tmp_path / "conversation.txt"
    transcript.write_text(
        """
MaleHost: Welcome to the show.

FemaleGuest: Happy to be here.

NeutralGuest: I have a question.
""".strip(),
        encoding="utf-8",
    )
    local_config.write_text(
        """
llm:
  provider: fixture
speaker_voices:
  mode: infer_once
tts:
  provider: fixture
publish:
  base_url: "https://example.com/babelecho"
""",
        encoding="utf-8",
    )

    output = run_pipeline(
        workspace=str(workspace),
        run_id="speaker-voice-demo",
        source_config_path=None,
        local_config_path=str(local_config),
        from_stage="ingest",
        to_stage="synthesize",
        transcript_file=str(transcript),
    )

    run_dir = workspace / "runs" / "speaker-voice-demo"
    speaker_voices = read_json(run_dir / "script" / "speaker-voices.json")
    manifest = read_json(run_dir / "segments" / "manifest.json")
    assert "speaker voices: created" in output
    assert speaker_voices["speaker_voices"] == {
        "MaleHost": "male_a",
        "FemaleGuest": "female_a",
        "NeutralGuest": "female_b",
    }
    assert [segment["voice_role"] for segment in manifest["segments"]] == [
        "male_a",
        "female_a",
        "female_b",
    ]


def test_run_command_accepts_podcast_feed_and_stops_at_adapt(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    feed = tmp_path / "feed.xml"
    feed.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Fixture Podcast</title>
    <item>
      <title>Feed Episode</title>
      <link>https://example.com/feed-episode</link>
      <podcast:transcript url="{transcript}" type="text/vtt" language="en" />
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "feed-demo",
            "--podcast-feed",
            str(feed),
            "--episode-url",
            "https://example.com/feed-episode",
            "--local-config",
            str(local_config),
            "--to-stage",
            "adapt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    run_dir = workspace / "runs" / "feed-demo"
    assert result.returncode == 0, result.stderr
    assert "adapt:" in result.stdout
    assert (run_dir / "transcript" / "raw.vtt").exists()
    assert (run_dir / "script" / "zh.json").exists()

    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "podcast_rss"
    assert source["feed_url"] == str(feed)
    assert source["episode_url"] == "https://example.com/feed-episode"
    assert source["title"] == "Feed Episode"
    assert source["transcript_url"] == str(transcript)

    status = read_json(run_dir / "run.json")
    assert status["input"]["podcast_feed"] == str(feed)
    assert status["input"]["episode_url"] == "https://example.com/feed-episode"


def test_run_command_accepts_podcast_index_episode_source_config(tmp_path: Path):
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    episode_json = tmp_path / "episode.json"
    episode_json.write_text(
        f"""{{
  "episode": {{
    "title": "PodcastIndex Feed Episode",
    "link": "https://example.com/pi-episode",
    "transcripts": [
      {{
        "url": "{transcript}",
        "type": "text/vtt"
      }}
    ]
  }}
}}
""",
        encoding="utf-8",
    )
    source_config.write_text(
        f"""
source:
  type: podcast_index_episode
  episode_json: "{episode_json}"
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "pi-feed-demo",
            "--source-config",
            str(source_config),
            "--local-config",
            str(local_config),
            "--to-stage",
            "adapt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    run_dir = workspace / "runs" / "pi-feed-demo"
    assert result.returncode == 0, result.stderr
    assert "adapt:" in result.stdout
    assert (run_dir / "transcript" / "raw.vtt").exists()
    assert (run_dir / "script" / "zh.json").exists()

    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "podcast_index_episode"
    assert source["episode_json"] == str(episode_json)
    assert source["title"] == "PodcastIndex Feed Episode"
    assert source["original_url"] == "https://example.com/pi-episode"
    assert source["transcript_url"] == str(transcript)

    status = read_json(run_dir / "run.json")
    assert status["input"]["source_config"] == str(source_config)


def test_run_command_accepts_podcast_index_api_source_config(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("PODCASTINDEX_API_KEY", "api-key")
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "api-secret")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    server = run_podcast_index_api_server(
        f"""{{
  "episode": {{
    "title": "PodcastIndex API Episode",
    "link": "https://example.com/pi-api-episode",
    "transcripts": [
      {{
        "url": "{transcript}",
        "type": "text/vtt"
      }}
    ]
  }}
}}
"""
    )
    source_config.write_text(
        f"""
source:
  type: podcast_index_api
  api_base_url: "http://127.0.0.1:{server.server_port}/api/1.0"
  endpoint: episodes/byid
  episode_id: 123
  api_key_env: PODCASTINDEX_API_KEY
  api_secret_env: PODCASTINDEX_API_SECRET
  user_agent: "BabelEchoTest/0.1"
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "run",
                "--workspace",
                str(workspace),
                "--run-id",
                "pi-api-flow",
                "--source-config",
                str(source_config),
                "--local-config",
                str(local_config),
                "--to-stage",
                "adapt",
            ],
            text=True,
            capture_output=True,
            env=worktree_python_env(),
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()

    run_dir = workspace / "runs" / "pi-api-flow"
    assert result.returncode == 0, result.stderr
    assert "ingest:" in result.stdout
    assert "normalize:" in result.stdout
    assert "adapt:" in result.stdout
    assert (run_dir / "transcript" / "raw.vtt").exists()
    assert (run_dir / "script" / "zh.json").exists()

    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "podcast_index_api"
    assert source["podcast_index_endpoint"] == "episodes/byid"
    assert source["podcast_index_episode_id"] == 123
    assert source["title"] == "PodcastIndex API Episode"
    assert source["original_url"] == "https://example.com/pi-api-episode"
    assert source["transcript_url"] == str(transcript)

    status = read_json(run_dir / "run.json")
    assert status["input"]["source_config"] == str(source_config)


def test_podcast_index_cli_searches_episodes_and_writes_source_config(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    credentials_file = tmp_path / "podcastindex.env"
    source_config_out = tmp_path / "selected-source.yaml"
    credentials_file.write_text(
        """
PODCASTINDEX_API_KEY=file-key
PODCASTINDEX_API_SECRET=file-secret
PODCASTINDEX_USER_AGENT=BabelEchoTest/0.1
""",
        encoding="utf-8",
    )
    server = run_podcast_index_route_server(
        {
            "/api/1.0/search/byterm": json.dumps(
                {
                    "feeds": [
                        {
                            "id": 75075,
                            "title": "99% Invisible",
                            "author": "Roman Mars",
                            "url": "https://feeds.example.com/99pi.xml",
                            "link": "https://99percentinvisible.org",
                        }
                    ]
                }
            ),
            "/api/1.0/episodes/byfeedid": json.dumps(
                {
                    "items": [
                        {
                            "title": "Older Episode",
                            "guid": "older-guid",
                            "link": "https://example.com/older",
                        },
                        {
                            "title": "Selected Episode",
                            "guid": "selected-guid",
                            "link": "https://example.com/selected",
                            "transcripts": [
                                {"url": "https://example.com/transcript.txt"}
                            ],
                        },
                    ]
                }
            ),
        }
    )

    try:
        search_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "podcast-index",
                "search",
                "--query",
                "99 percent invisible",
                "--api-base-url",
                f"http://127.0.0.1:{server.server_port}/api/1.0",
                "--credentials-file",
                str(credentials_file),
                "--max",
                "5",
            ],
            text=True,
            capture_output=True,
            env=worktree_python_env(),
            check=False,
        )

        assert search_result.returncode == 0, search_result.stderr
        assert "1. 99% Invisible" in search_result.stdout
        assert "feed_id=75075" in search_result.stdout

        episodes_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "podcast-index",
                "episodes",
                "--feed-id",
                "75075",
                "--api-base-url",
                f"http://127.0.0.1:{server.server_port}/api/1.0",
                "--credentials-file",
                str(credentials_file),
                "--max",
                "2",
                "--select-index",
                "2",
                "--source-config-out",
                str(source_config_out),
            ],
            text=True,
            capture_output=True,
            env=worktree_python_env(),
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert episodes_result.returncode == 0, episodes_result.stderr
    assert "2. Selected Episode" in episodes_result.stdout
    assert f"source config: {source_config_out}" in episodes_result.stdout
    source_config = yaml.safe_load(source_config_out.read_text(encoding="utf-8"))
    assert source_config == {
        "source": {
            "type": "podcast_index_api",
            "api_base_url": f"http://127.0.0.1:{server.server_port}/api/1.0",
            "endpoint": "episodes/byfeedid",
            "feed_id": 75075,
            "max_episodes": 2,
            "episode_url": "selected-guid",
            "credentials_file": str(credentials_file),
        }
    }


def test_itunes_cli_searches_and_writes_podcast_rss_source_config(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    source_config_out = tmp_path / "itunes-source.yaml"
    server = run_route_server(
        {
            "/search": json.dumps(
                {
                    "results": [
                        {
                            "wrapperType": "track",
                            "kind": "podcast",
                            "collectionName": "99% Invisible",
                            "artistName": "Roman Mars",
                            "feedUrl": "https://feeds.example.com/99pi.xml",
                            "collectionViewUrl": "https://podcasts.apple.com/us/podcast/99pi",
                        }
                    ]
                }
            )
        }
    )

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "itunes",
                "search",
                "--query",
                "99 percent invisible",
                "--api-base-url",
                f"http://127.0.0.1:{server.server_port}/search",
                "--max",
                "5",
                "--select-index",
                "1",
                "--source-config-out",
                str(source_config_out),
            ],
            text=True,
            capture_output=True,
            env=worktree_python_env(),
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.returncode == 0, result.stderr
    assert "1. 99% Invisible" in result.stdout
    assert "feed_url=https://feeds.example.com/99pi.xml" in result.stdout
    assert f"source config: {source_config_out}" in result.stdout
    source_config = yaml.safe_load(source_config_out.read_text(encoding="utf-8"))
    assert source_config == {
        "source": {
            "type": "podcast_rss",
            "feed_url": "https://feeds.example.com/99pi.xml",
            "title": "99% Invisible",
            "original_url": "https://podcasts.apple.com/us/podcast/99pi",
        }
    }


def test_itunes_cli_lists_episodes_from_apple_url_and_writes_source_config(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    source_config_out = tmp_path / "itunes-episode-source.yaml"
    transcript = tmp_path / "episode.vtt"
    local_config.write_text(
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
    transcript.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello.\n",
        encoding="utf-8",
    )
    routes: dict[str, str] = {}
    server = run_route_server(routes)
    feed_url = f"http://127.0.0.1:{server.server_port}/feed.xml"
    routes["/lookup"] = json.dumps(
        {
            "results": [
                {
                    "wrapperType": "track",
                    "kind": "podcast",
                    "collectionName": "99% Invisible",
                    "artistName": "Roman Mars",
                    "feedUrl": feed_url,
                    "collectionViewUrl": "https://podcasts.apple.com/us/podcast/99pi/id394775318",
                }
            ]
        }
    )
    routes["/feed.xml"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>Panel Episode</title>
      <link>https://example.com/panel</link>
      <guid>panel-guid</guid>
      <podcast:transcript url="{transcript}" type="text/vtt" language="en" />
    </item>
  </channel>
</rss>
"""

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "itunes",
                "episodes",
                "--url",
                "https://podcasts.apple.com/us/podcast/99pi/id394775318?i=1000651234567",
                "--api-base-url",
                f"http://127.0.0.1:{server.server_port}/lookup",
                "--select-index",
                "1",
                "--source-config-out",
                str(source_config_out),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        convert_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "episode",
                "convert",
                "--workspace",
                str(workspace),
                "--run-id",
                "itunes-url-flow",
                "--source-config",
                str(source_config_out),
                "--local-config",
                str(local_config),
                "--to-stage",
                "normalize",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.returncode == 0, result.stderr
    assert convert_result.returncode == 0, convert_result.stderr
    assert f"feed_url={feed_url}" in result.stdout
    assert "1. Panel Episode (transcript=yes)" in result.stdout
    assert f"source config: {source_config_out}" in result.stdout
    source_config = yaml.safe_load(source_config_out.read_text(encoding="utf-8"))
    assert source_config == {
        "source": {
            "type": "podcast_rss",
            "feed_url": feed_url,
            "episode_url": "https://example.com/panel",
            "title": "Panel Episode",
            "original_url": "https://example.com/panel",
        }
    }
    run_dir = workspace / "runs" / "itunes-url-flow"
    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "podcast_rss"
    assert source["feed_url"] == feed_url
    assert (run_dir / "transcript" / "normalized.json").exists()


def test_rss_cli_lists_episodes_and_writes_source_config(tmp_path: Path):
    feed = tmp_path / "feed.xml"
    transcript = tmp_path / "episode.vtt"
    source_config_out = tmp_path / "rss-source.yaml"
    transcript.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello.\n",
        encoding="utf-8",
    )
    feed.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>Older Episode</title>
      <link>https://example.com/older</link>
    </item>
    <item>
      <title>Selected Episode</title>
      <link>https://example.com/selected</link>
      <guid>selected-guid</guid>
      <podcast:transcript url="{transcript}" type="text/vtt" language="en" />
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "rss",
            "episodes",
            "--feed-url",
            str(feed),
            "--select-index",
            "2",
            "--source-config-out",
            str(source_config_out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "1. Older Episode (transcript=no)" in result.stdout
    assert "2. Selected Episode (transcript=yes)" in result.stdout
    assert f"source config: {source_config_out}" in result.stdout
    source_config = yaml.safe_load(source_config_out.read_text(encoding="utf-8"))
    assert source_config == {
        "source": {
            "type": "podcast_rss",
            "feed_url": str(feed),
            "episode_url": "https://example.com/selected",
            "title": "Selected Episode",
            "original_url": "https://example.com/selected",
        }
    }


def test_run_command_accepts_youtube_captions_source_config(tmp_path: Path):
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
file="${out%\\.%(ext)s}.en.vtt"
cat > "$file" <<'VTT'
WEBVTT

00:00:00.000 --> 00:00:03.000
Welcome to the YouTube episode.
VTT
""",
        encoding="utf-8",
    )
    fake_yt_dlp.chmod(0o755)
    source_config.write_text(
        f"""
source:
  type: youtube_captions
  url: "https://www.youtube.com/watch?v=fixture"
  title: "YouTube Fixture Episode"
  language: en
  yt_dlp_command: "{fake_yt_dlp}"
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "youtube-demo",
            "--source-config",
            str(source_config),
            "--local-config",
            str(local_config),
            "--to-stage",
            "adapt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    run_dir = workspace / "runs" / "youtube-demo"
    assert result.returncode == 0, result.stderr
    assert "adapt:" in result.stdout
    assert (run_dir / "transcript" / "raw.vtt").exists()
    assert (run_dir / "script" / "zh.json").exists()

    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "youtube_captions"
    assert source["youtube_url"] == "https://www.youtube.com/watch?v=fixture"
    assert source["youtube_language"] == "en"
    assert source["youtube_subtitle_file"] == "raw.vtt"
    assert source["title"] == "YouTube Fixture Episode"
    assert source["raw_transcript"] == "transcript/raw.vtt"


def test_run_command_accepts_episode_page_source_config(tmp_path: Path):
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    episode_page = tmp_path / "episode.html"
    transcript_page = tmp_path / "transcript.html"
    episode_page.write_text(
        """<!doctype html>
<html>
  <body>
    <article>
      <h1>Episode Page Flow</h1>
      <a href="transcript.html">Transcript</a>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )
    transcript_page.write_text(
        """<!doctype html>
<html>
  <body>
    <nav>Navigation text</nav>
    <div class="transcript-content">
      <p>Host: Welcome to the episode page flow.</p>
      <p>Guest: The transcript should be clean.</p>
    </div>
  </body>
</html>
""",
        encoding="utf-8",
    )
    source_config.write_text(
        f"""
source:
  type: episode_page
  page_url: "{episode_page}"
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "episode-page-flow",
            "--source-config",
            str(source_config),
            "--local-config",
            str(local_config),
            "--to-stage",
            "adapt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    run_dir = workspace / "runs" / "episode-page-flow"
    raw_text = (run_dir / "transcript" / "raw.txt").read_text(encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "ingest:" in result.stdout
    assert "normalize:" in result.stdout
    assert "adapt:" in result.stdout
    assert "<p>" not in raw_text
    assert "<div>" not in raw_text
    assert "Navigation text" not in raw_text
    assert (run_dir / "script" / "zh.json").exists()

    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "episode_page"
    assert source["page_url"] == str(episode_page)
    assert source["transcript_page_url"] == str(transcript_page)
    assert source["title"] == "Episode Page Flow"

    status = read_json(run_dir / "run.json")
    assert status["input"]["source_config"] == str(source_config)


def test_episode_convert_command_accepts_exact_episode_page_url(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    episode_page = tmp_path / "episode.html"
    transcript_page = tmp_path / "transcript.html"
    episode_page.write_text(
        f"""
        <html>
          <head><title>On Demand Episode</title></head>
          <body><a href="{transcript_page}">Transcript</a></body>
        </html>
        """,
        encoding="utf-8",
    )
    transcript_page.write_text(
        """
        <html>
          <body>
            <main>
              <h1>On Demand Episode Transcript</h1>
              <p>HOST: Hello from the on demand episode.</p>
            </main>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "episode",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "on-demand-page",
            "--url",
            str(episode_page),
            "--local-config",
            str(local_config),
            "--to-stage",
            "adapt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "source config:" in result.stdout
    assert "adapt:" in result.stdout
    run_dir = workspace / "runs" / "on-demand-page"
    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "episode_page"
    assert source["page_url"] == str(episode_page)
    status = read_json(run_dir / "run.json")
    assert status["input"]["episode_url"] == str(episode_page)


def test_episode_convert_command_accepts_rss_feed_url_with_select_index(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    feed = tmp_path / "feed.xml"
    transcript = tmp_path / "episode.vtt"
    source_config_out = tmp_path / "rss-on-demand-source.yaml"
    transcript.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello from RSS.\n",
        encoding="utf-8",
    )
    feed.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>On Demand RSS Feed</title>
    <item>
      <title>Older Episode</title>
      <link>https://example.com/older</link>
    </item>
    <item>
      <title>Selected RSS Episode</title>
      <link>https://example.com/rss-selected</link>
      <guid>rss-selected-guid</guid>
      <podcast:transcript url="{transcript}" type="text/vtt" language="en" />
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "episode",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "on-demand-rss",
            "--url",
            str(feed),
            "--select-index",
            "2",
            "--source-config-out",
            str(source_config_out),
            "--local-config",
            str(local_config),
            "--to-stage",
            "normalize",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"source config: {source_config_out}" in result.stdout
    assert "feed_url=" in result.stdout
    assert "normalize:" in result.stdout
    source_config = yaml.safe_load(source_config_out.read_text(encoding="utf-8"))
    assert source_config == {
        "source": {
            "type": "podcast_rss",
            "feed_url": str(feed),
            "episode_url": "https://example.com/rss-selected",
            "title": "Selected RSS Episode",
            "original_url": "https://example.com/rss-selected",
        }
    }
    run_dir = workspace / "runs" / "on-demand-rss"
    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "podcast_rss"
    assert source["feed_url"] == str(feed)
    assert source["episode_url"] == "https://example.com/rss-selected"
    assert (run_dir / "transcript" / "normalized.json").exists()


def test_episode_convert_command_accepts_apple_url_with_select_index(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    transcript = tmp_path / "episode.vtt"
    source_config_out = tmp_path / "apple-on-demand-source.yaml"
    transcript.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello from Apple.\n",
        encoding="utf-8",
    )
    local_config.write_text(
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
    routes: dict[str, str] = {}
    server = run_route_server(routes)
    feed_url = f"http://127.0.0.1:{server.server_port}/feed.xml"
    routes["/lookup"] = json.dumps(
        {
            "results": [
                {
                    "wrapperType": "track",
                    "kind": "podcast",
                    "collectionName": "On Demand Apple Show",
                    "artistName": "Fixture Host",
                    "feedUrl": feed_url,
                    "collectionViewUrl": (
                        "https://podcasts.apple.com/us/podcast/show/id123456"
                    ),
                }
            ]
        }
    )
    routes["/feed.xml"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>On Demand Apple Feed</title>
    <item>
      <title>Selected Apple Episode</title>
      <link>https://example.com/apple-selected</link>
      <guid>apple-selected-guid</guid>
      <podcast:transcript url="{transcript}" type="text/vtt" language="en" />
    </item>
  </channel>
</rss>
"""

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "episode",
                "convert",
                "--workspace",
                str(workspace),
                "--run-id",
                "on-demand-apple",
                "--url",
                "https://podcasts.apple.com/us/podcast/show/id123456",
                "--itunes-api-base-url",
                f"http://127.0.0.1:{server.server_port}/lookup",
                "--select-index",
                "1",
                "--source-config-out",
                str(source_config_out),
                "--local-config",
                str(local_config),
                "--to-stage",
                "normalize",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.returncode == 0, result.stderr
    assert f"feed_url={feed_url}" in result.stdout
    assert f"source config: {source_config_out}" in result.stdout
    source_config = yaml.safe_load(source_config_out.read_text(encoding="utf-8"))
    assert source_config == {
        "source": {
            "type": "podcast_rss",
            "feed_url": feed_url,
            "episode_url": "https://example.com/apple-selected",
            "title": "Selected Apple Episode",
            "original_url": "https://example.com/apple-selected",
        }
    }
    run_dir = workspace / "runs" / "on-demand-apple"
    source = read_json(run_dir / "source.json")
    assert source["source_type"] == "podcast_rss"
    assert source["feed_url"] == feed_url
    assert source["episode_url"] == "https://example.com/apple-selected"
    assert (run_dir / "transcript" / "normalized.json").exists()


def test_episode_convert_command_rejects_unknown_episode_input(tmp_path: Path):
    local_config = tmp_path / "local.yaml"
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "episode",
            "convert",
            "--workspace",
            str(tmp_path / "workspace"),
            "--run-id",
            "bad-on-demand",
            "--url",
            "not a url",
            "--local-config",
            str(local_config),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Unsupported episode input: not a url" in result.stderr


def test_article_convert_command_accepts_article_file_without_speaker_inference(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    article = tmp_path / "article.md"
    article.write_text(
        "# 测试文章\n\n" + "\n\n".join(["这是用于测试的文章段落，内容会被直接转换为固定女声朗读。"] * 30),
        encoding="utf-8",
    )
    local_config = tmp_path / "local.yaml"
    local_config.write_text(
        """
llm:
  provider: fixture
tts:
  provider: fixture
publish:
  base_url: "https://example.com/babelecho"
speaker_voices:
  mode: infer_once
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "article",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "article-file-cli",
            "--file",
            str(article),
            "--title",
            "测试文章",
            "--local-config",
            str(local_config),
            "--to-stage",
            "synthesize",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "speaker voices:" not in result.stdout
    run_dir = workspace / "runs" / "article-file-cli"
    source = read_json(run_dir / "source.json")
    normalized = read_json(run_dir / "transcript" / "normalized.json")
    manifest = read_json(run_dir / "segments" / "manifest.json")
    assert source["source_type"] == "article_file"
    assert all(segment.get("speaker") is None for segment in normalized["segments"])
    assert not (run_dir / "script" / "speaker-voices.json").exists()
    assert {segment.get("voice_role") for segment in manifest["segments"]} == {"female_a"}


def test_article_convert_command_accepts_web_article_url_to_normalize(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    local_config.write_text(
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
    routes = {
        "/article": """
        <html>
          <head><title>Public Web Article</title></head>
          <body>
            <nav>Navigation</nav>
            <article>
              <h1>Public Web Article</h1>
              <p>Important: this is article text, not a speaker.</p>
              <p>The second paragraph remains plain article content.</p>
            </article>
          </body>
        </html>
        """,
    }
    server = run_route_server(routes)
    try:
        url = f"http://127.0.0.1:{server.server_port}/article"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                "article",
                "convert",
                "--workspace",
                str(workspace),
                "--run-id",
                "web-article-cli",
                "--url",
                url,
                "--local-config",
                str(local_config),
                "--to-stage",
                "normalize",
            ],
            text=True,
            capture_output=True,
            env=worktree_python_env(),
            check=False,
        )
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stderr
    run_dir = workspace / "runs" / "web-article-cli"
    source = read_json(run_dir / "source.json")
    normalized = read_json(run_dir / "transcript" / "normalized.json")
    assert source["source_type"] == "web_article"
    assert source["provider"] == "trafilatura"
    assert source["title"] == "Public Web Article"
    assert source["input_url"].startswith("http://127.0.0.1:")
    assert normalized["segments"][0]["speaker"] is None
    assert normalized["segments"][0]["text"] == "Public Web Article"
    assert normalized["segments"][1]["text"] == "Important: this is article text, not a speaker."


def test_run_command_stops_at_requested_stage(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "preview-demo",
            "--transcript-file",
            str(transcript),
            "--title",
            "Preview Episode",
            "--local-config",
            str(local_config),
            "--to-stage",
            "adapt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    run_dir = workspace / "runs" / "preview-demo"
    assert result.returncode == 0, result.stderr
    assert "adapt:" in result.stdout
    assert "synthesize:" not in result.stdout
    assert (run_dir / "script" / "zh.json").exists()
    assert not (run_dir / "output" / "audio.mp3").exists()

    status = read_json(run_dir / "run.json")
    assert status["status"] == "succeeded"
    assert status["from_stage"] == "ingest"
    assert status["to_stage"] == "adapt"
    assert [stage["status"] for stage in status["stages"]] == [
        "succeeded",
        "succeeded",
        "succeeded",
        "skipped",
        "skipped",
        "skipped",
    ]


def test_run_command_records_failed_stage_in_status(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    missing_transcript = tmp_path / "missing.vtt"
    local_config.write_text(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "failed-demo",
            "--transcript-file",
            str(missing_transcript),
            "--local-config",
            str(local_config),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    status = read_json(workspace / "runs" / "failed-demo" / "run.json")
    assert result.returncode == 1
    assert status["status"] == "failed"
    assert status["failed_stage"] == "ingest"
    assert "missing.vtt" in status["error"]
    assert status["stages"][0]["status"] == "failed"
    assert status["stages"][1]["status"] == "pending"


def test_run_command_resumes_from_synthesize(tmp_path: Path):
    workspace = tmp_path / "workspace"
    run_dir = workspace / "runs" / "resume-demo"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    overrides = tmp_path / "overrides.yaml"
    source_config.write_text(
        """
source:
  type: transcript_url
  transcript_url: "tests/fixtures/sample.vtt"
  title: "Resume Episode"
  original_url: "https://example.com/resume"
""",
        encoding="utf-8",
    )
    overrides.write_text(
        """
replacements:
  - from: "NASA"
    to: "美国国家航空航天局"
  - from: "Crew-9"
    to: "Crew Nine"
""",
        encoding="utf-8",
    )
    local_config.write_text(
        """
llm:
  provider: fixture
tts:
  provider: fixture
publish:
  base_url: "https://example.com/babelecho"
overrides:
  path: "{overrides_path}"
""",
        encoding="utf-8",
    )
    (run_dir / "transcript").mkdir(parents=True)
    (run_dir / "script").mkdir()
    write_json(
        run_dir / "source.json",
        {
            "run_id": "resume-demo",
            "title": "Resume Episode",
            "original_url": "https://example.com/resume",
            "transcript_url": "tests/fixtures/sample.vtt",
        },
    )
    write_json(
        run_dir / "transcript" / "normalized.json",
        {
            "episode_id": "resume-demo",
            "language": "en",
            "segments": [
                {
                    "id": "0001",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": None,
                    "text": "This should not be adapted again.",
                    "source": "transcript",
                }
            ],
        },
    )
    write_json(
        run_dir / "script" / "zh.json",
        {
            "episode_id": "resume-demo",
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "source_segment_ids": ["0001"],
                    "speaker": None,
                    "text": "人工编辑后的 NASA Crew-9 中文稿。",
                }
            ],
        },
    )
    local_config.write_text(
        local_config.read_text(encoding="utf-8").format(overrides_path=overrides),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "resume-demo",
            "--source-config",
            str(source_config),
            "--local-config",
            str(local_config),
            "--from-stage",
            "synthesize",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "overrides: 2 replacements from 2 rules" in result.stdout
    manifest = read_json(run_dir / "segments" / "manifest.json")
    assert manifest["segments"][0]["text"] == "人工编辑后的 美国国家航空航天局 Crew Nine 中文稿。"
    assert (run_dir / "output" / "audio.mp3").exists()
    assert (run_dir / "publish" / "feed.xml").exists()


def test_check_command_reports_script_failures(tmp_path: Path):
    workspace = tmp_path / "workspace"
    run_dir = workspace / "runs" / "bad-script"
    (run_dir / "script").mkdir(parents=True)
    write_json(
        run_dir / "script" / "zh.json",
        {
            "episode_id": "bad-script",
            "language": "zh-CN",
            "segments": [{"id": "0001", "text": ""}],
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "check",
            "--workspace",
            str(workspace),
            "--run-id",
            "bad-script",
            "--checks",
            "script",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "empty text" in result.stderr


def test_adapt_command_blocks_real_llm_when_quality_rejects(tmp_path: Path):
    workspace = tmp_path / "workspace"
    run_dir = workspace / "runs" / "bad-quality-adapt"
    local_config = tmp_path / "local.yaml"
    (run_dir / "transcript").mkdir(parents=True)
    write_json(
        run_dir / "transcript" / "normalized.json",
        {
            "episode_id": "bad-quality-adapt",
            "language": "en",
            "segments": [
                {
                    "id": "0001",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": None,
                    "text": "Too short.",
                    "source": "transcript",
                }
            ],
        },
    )
    write_json(
        run_dir / "transcript" / "quality.json",
        {
            "recommendation": "reject",
            "reasons": ["too_short"],
            "warnings": [],
            "metrics": {"segment_count": 1, "total_chars": 10},
        },
    )
    local_config.write_text(
        """
llm:
  provider: openai_compatible
  base_url: "http://127.0.0.1:9/v1"
  model: "deepseek-chat"
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "adapt",
            "--workspace",
            str(workspace),
            "--run-id",
            "bad-quality-adapt",
            "--local-config",
            str(local_config),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Transcript quality gate failed before adapt" in result.stderr
    assert "recommendation=reject" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_command_stops_before_real_llm_when_quality_rejects(tmp_path: Path):
    workspace = tmp_path / "workspace"
    local_config = tmp_path / "local.yaml"
    transcript = tmp_path / "short.txt"
    transcript.write_text("Too short for a real LLM request.", encoding="utf-8")
    local_config.write_text(
        """
llm:
  provider: openai_compatible
  base_url: "http://127.0.0.1:9/v1"
  model: "deepseek-chat"
tts:
  provider: fixture
publish:
  base_url: "https://example.com/babelecho"
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "run",
            "--workspace",
            str(workspace),
            "--run-id",
            "quality-gated-run",
            "--transcript-file",
            str(transcript),
            "--local-config",
            str(local_config),
            "--to-stage",
            "adapt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    run_dir = workspace / "runs" / "quality-gated-run"
    status = read_json(run_dir / "run.json")
    quality = read_json(run_dir / "transcript" / "quality.json")
    assert result.returncode == 1
    assert "Transcript quality gate failed before adapt" in result.stderr
    assert quality["recommendation"] == "reject"
    assert status["status"] == "failed"
    assert status["failed_stage"] == "adapt"
    assert [stage["status"] for stage in status["stages"][:3]] == [
        "succeeded",
        "succeeded",
        "failed",
    ]
    assert not (run_dir / "script" / "zh.json").exists()
