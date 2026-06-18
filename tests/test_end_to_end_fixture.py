import subprocess
import sys
from pathlib import Path

from babelecho.jsonio import read_json, write_json


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

    assert (workspace / "runs" / "demo" / "script" / "zh.json").exists()
    assert (workspace / "runs" / "demo" / "segments" / "0001.wav").exists()


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
