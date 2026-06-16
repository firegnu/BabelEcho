# Backend MVP-0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a transcript-first backend pipeline that turns one configured English transcript into a Chinese podcast audio artifact and a minimal RSS feed.

**Architecture:** The implementation is a Python package with stage-oriented CLI commands. Each stage reads and writes files under `workspace/runs/<run-id>/`, so stages can be inspected and rerun independently. Local model integrations are behind thin adapters: vLLM HTTP for LLM adaptation, TTS CLI for speech generation, and `ffmpeg` CLI for final audio assembly.

**Tech Stack:** Python 3.11+, stdlib `argparse` CLI, `PyYAML`, `pytest`, local vLLM OpenAI-compatible API, local TTS wrapper command, `ffmpeg`.

**Current update:** The first real LLM adaptation validation now uses DeepSeek API as a temporary quality baseline, while keeping TTS on the 5090D locally. The final direction remains local-first; use `docs/plans/01-backend-mvp0/01-local-llm-adapt.md` as the active plan.

---

## Scope Check

This plan implements the narrow MVP-0 path:

```text
transcript_url or local transcript file
  -> transcript/raw.*
  -> transcript/normalized.json
  -> script/zh.json
  -> segments/*.wav
  -> output/audio.mp3
  -> publish/feed.xml
```

This plan does not implement RSS search, PodcastIndex search, Apple/Spotify/YouTube link expansion, ASR, voice clone, Web UI, background workers, or macOS App code.

## File Structure

Create:

- `pyproject.toml` - Python package metadata and dependencies.
- `src/babelecho/__init__.py` - Package marker and version.
- `src/babelecho/__main__.py` - Enables `python -m babelecho`.
- `src/babelecho/cli.py` - CLI entrypoint and stage subcommands.
- `src/babelecho/config.py` - YAML loading and config validation helpers.
- `src/babelecho/paths.py` - Workspace and run path helpers.
- `src/babelecho/jsonio.py` - Atomic JSON read/write helpers.
- `src/babelecho/ingest.py` - `01_ingest` implementation for transcript URL/local file.
- `src/babelecho/transcript.py` - Transcript normalization for text, VTT, and SRT.
- `src/babelecho/llm.py` - Local vLLM client and fixture adapter.
- `src/babelecho/adapt.py` - `03_adapt_to_chinese` implementation.
- `src/babelecho/tts.py` - TTS CLI adapter and fixture adapter.
- `src/babelecho/synthesize.py` - `04_synthesize` implementation.
- `src/babelecho/audio.py` - `ffmpeg` assembly wrapper.
- `src/babelecho/publish.py` - RSS and static artifact publishing.
- `workspace/sources/hardcoded.example.yaml` - Safe example source config with no secrets.
- `workspace/config/local.example.yaml` - Safe example local runtime config with no private hostnames.

Create tests:

- `tests/fixtures/sample.txt`
- `tests/fixtures/sample.vtt`
- `tests/fixtures/sample.srt`
- `tests/test_config.py`
- `tests/test_ingest.py`
- `tests/test_transcript.py`
- `tests/test_adapt.py`
- `tests/test_synthesize.py`
- `tests/test_audio.py`
- `tests/test_publish.py`
- `tests/test_cli_smoke.py`

## Task 1: Python Package Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/babelecho/__init__.py`
- Create: `src/babelecho/__main__.py`
- Create: `src/babelecho/cli.py`
- Create: `tests/test_cli_smoke.py`

- [ ] **Step 1: Create failing CLI smoke test**

Create `tests/test_cli_smoke.py`:

```python
import subprocess
import sys


def test_module_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "babelecho", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "BabelEcho backend pipeline" in result.stdout
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/test_cli_smoke.py -v
```

Expected: fails because the `babelecho` module does not exist.

- [ ] **Step 3: Add package skeleton**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "babelecho"
version = "0.1.0"
description = "Local transcript-first podcast translation pipeline"
requires-python = ">=3.11"
dependencies = [
  "PyYAML>=6.0.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `src/babelecho/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/babelecho/__main__.py`:

```python
from .cli import main


if __name__ == "__main__":
    main()
```

Create `src/babelecho/cli.py`:

```python
import argparse


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from . import __version__

        print(__version__)
    return 0
```

- [ ] **Step 4: Run smoke test and verify it passes**

Run:

```bash
python -m pytest tests/test_cli_smoke.py -v
```

Expected: one passing test.

- [ ] **Step 5: Commit skeleton**

Run:

```bash
git add pyproject.toml src/babelecho tests/test_cli_smoke.py
git commit -m "chore: add backend package skeleton"
```

## Task 2: Config and Run Path Helpers

**Files:**
- Create: `src/babelecho/config.py`
- Create: `src/babelecho/paths.py`
- Create: `src/babelecho/jsonio.py`
- Create: `workspace/sources/hardcoded.example.yaml`
- Create: `workspace/config/local.example.yaml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create config tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

import pytest

from babelecho.config import load_yaml, require_keys
from babelecho.paths import RunPaths, create_run
from babelecho.jsonio import read_json, write_json


def test_load_yaml_reads_mapping(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("source:\n  type: transcript_url\n", encoding="utf-8")

    assert load_yaml(config_path) == {"source": {"type": "transcript_url"}}


def test_require_keys_reports_missing_key():
    with pytest.raises(ValueError, match="Missing required key: source"):
        require_keys({}, ["source"])


def test_create_run_builds_expected_directories(tmp_path: Path):
    run_paths = create_run(tmp_path, "demo-run")

    assert isinstance(run_paths, RunPaths)
    assert run_paths.run_dir == tmp_path / "runs" / "demo-run"
    assert run_paths.transcript_dir.is_dir()
    assert run_paths.script_dir.is_dir()
    assert run_paths.segments_dir.is_dir()
    assert run_paths.output_dir.is_dir()
    assert run_paths.publish_dir.is_dir()


def test_json_round_trip(tmp_path: Path):
    path = tmp_path / "data.json"

    write_json(path, {"hello": "world"})

    assert read_json(path) == {"hello": "world"}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected: fails because helper modules do not exist.

- [ ] **Step 3: Implement config, path, and JSON helpers**

Create `src/babelecho/config.py`:

```python
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be a mapping: {source}")
    return value


def require_keys(mapping: dict[str, Any], keys: list[str]) -> None:
    for key in keys:
        if key not in mapping:
            raise ValueError(f"Missing required key: {key}")
```

Create `src/babelecho/paths.py`:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    workspace: Path
    run_id: str
    run_dir: Path
    transcript_dir: Path
    script_dir: Path
    segments_dir: Path
    output_dir: Path
    publish_dir: Path

    @property
    def source_json(self) -> Path:
        return self.run_dir / "source.json"

    @property
    def normalized_transcript_json(self) -> Path:
        return self.transcript_dir / "normalized.json"

    @property
    def chinese_script_json(self) -> Path:
        return self.script_dir / "zh.json"

    @property
    def output_audio(self) -> Path:
        return self.output_dir / "audio.mp3"


def create_run(workspace: str | Path, run_id: str) -> RunPaths:
    root = Path(workspace)
    run_dir = root / "runs" / run_id
    paths = RunPaths(
        workspace=root,
        run_id=run_id,
        run_dir=run_dir,
        transcript_dir=run_dir / "transcript",
        script_dir=run_dir / "script",
        segments_dir=run_dir / "segments",
        output_dir=run_dir / "output",
        publish_dir=run_dir / "publish",
    )
    for directory in [
        paths.transcript_dir,
        paths.script_dir,
        paths.segments_dir,
        paths.output_dir,
        paths.publish_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    return paths
```

Create `src/babelecho/jsonio.py`:

```python
import json
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp.replace(target)
```

Create `workspace/sources/hardcoded.example.yaml`:

```yaml
source:
  type: transcript_url
  transcript_url: "https://example.com/episode.vtt"
  title: "Example Episode"
  original_url: "https://example.com/episode"
```

Create `workspace/config/local.example.yaml`:

```yaml
llm:
  provider: local_vllm
  base_url: "http://127.0.0.1:8000/v1"
  model: "Qwen/Qwen3-30B-A3B-Instruct-2507"
  temperature: 0.3
  max_tokens: 4096

tts:
  provider: local_cli
  command: "tts-wrapper"
  voice: "default-zh"
  output_format: "wav"

publish:
  base_url: "https://example.com/babelecho"
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected: four passing tests.

- [ ] **Step 5: Commit config foundation**

Run:

```bash
git add src/babelecho/config.py src/babelecho/paths.py src/babelecho/jsonio.py workspace tests/test_config.py
git commit -m "chore: add backend config and run helpers"
```

## Task 3: Transcript Ingestion

**Files:**
- Create: `src/babelecho/ingest.py`
- Modify: `src/babelecho/cli.py`
- Create: `tests/fixtures/sample.vtt`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: Create ingest fixture and tests**

Create `tests/fixtures/sample.vtt`:

```text
WEBVTT

00:00:00.000 --> 00:00:03.000
Welcome to the sample episode.
```

Create `tests/test_ingest.py`:

```python
from pathlib import Path

from babelecho.ingest import ingest_transcript_source
from babelecho.jsonio import read_json
from babelecho.paths import create_run


def test_ingest_copies_local_transcript(tmp_path: Path):
    fixture = Path("tests/fixtures/sample.vtt")
    run_paths = create_run(tmp_path, "demo-run")
    source_config = {
        "type": "transcript_url",
        "transcript_url": str(fixture),
        "title": "Sample Episode",
        "original_url": "https://example.com/sample",
    }

    raw_path = ingest_transcript_source(source_config, run_paths)

    assert raw_path == run_paths.transcript_dir / "raw.vtt"
    assert raw_path.read_text(encoding="utf-8").startswith("WEBVTT")
    assert read_json(run_paths.source_json)["title"] == "Sample Episode"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/test_ingest.py -v
```

Expected: fails because `babelecho.ingest` does not exist.

- [ ] **Step 3: Implement transcript ingestion**

Create `src/babelecho/ingest.py`:

```python
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from .jsonio import write_json
from .paths import RunPaths


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
        with urlopen(transcript_url, timeout=30) as response:
            return response.read()
    return Path(transcript_url).read_bytes()


def ingest_transcript_source(source_config: dict, run_paths: RunPaths) -> Path:
    if source_config.get("type") != "transcript_url":
        raise ValueError("MVP-0 supports only source.type=transcript_url")
    transcript_url = source_config.get("transcript_url")
    if not transcript_url:
        raise ValueError("source.transcript_url is required")

    raw_path = run_paths.transcript_dir / _target_name(transcript_url)
    raw_path.write_bytes(_read_source(transcript_url))

    write_json(
        run_paths.source_json,
        {
            "run_id": run_paths.run_id,
            "source_type": "transcript_url",
            "title": source_config.get("title", "Untitled Episode"),
            "original_url": source_config.get("original_url"),
            "transcript_url": transcript_url,
            "raw_transcript": str(raw_path.relative_to(run_paths.run_dir)),
        },
    )
    return raw_path
```

- [ ] **Step 4: Add ingest CLI command**

Modify `src/babelecho/cli.py` so it contains:

```python
import argparse
from pathlib import Path

from .config import load_yaml, require_keys
from .ingest import ingest_transcript_source
from .paths import create_run


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

    return parser


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

    parser.print_help()
    return 0
```

- [ ] **Step 5: Run ingest tests**

Run:

```bash
python -m pytest tests/test_ingest.py tests/test_cli_smoke.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit ingest stage**

Run:

```bash
git add src/babelecho/ingest.py src/babelecho/cli.py tests/fixtures/sample.vtt tests/test_ingest.py
git commit -m "feat: ingest transcript source"
```

## Task 4: Transcript Normalization

**Files:**
- Create: `src/babelecho/transcript.py`
- Modify: `src/babelecho/cli.py`
- Create: `tests/fixtures/sample.txt`
- Create: `tests/fixtures/sample.srt`
- Create: `tests/test_transcript.py`

- [ ] **Step 1: Create transcript fixtures and tests**

Create `tests/fixtures/sample.txt`:

```text
Welcome to the sample episode.

This is the second paragraph.
```

Create `tests/fixtures/sample.srt`:

```text
1
00:00:00,000 --> 00:00:03,000
Welcome to the sample episode.

2
00:00:03,500 --> 00:00:07,000
This is the second subtitle.
```

Create `tests/test_transcript.py`:

```python
from pathlib import Path

from babelecho.jsonio import read_json
from babelecho.paths import create_run
from babelecho.transcript import normalize_transcript


def test_normalize_plain_text(tmp_path: Path):
    run_paths = create_run(tmp_path, "text-run")
    raw = run_paths.transcript_dir / "raw.txt"
    raw.write_text(Path("tests/fixtures/sample.txt").read_text(encoding="utf-8"), encoding="utf-8")

    output = normalize_transcript(run_paths, raw)
    data = read_json(output)

    assert data["language"] == "en"
    assert [segment["id"] for segment in data["segments"]] == ["0001", "0002"]
    assert data["segments"][0]["start_ms"] is None
    assert data["segments"][0]["text"] == "Welcome to the sample episode."


def test_normalize_vtt(tmp_path: Path):
    run_paths = create_run(tmp_path, "vtt-run")
    raw = run_paths.transcript_dir / "raw.vtt"
    raw.write_text(Path("tests/fixtures/sample.vtt").read_text(encoding="utf-8"), encoding="utf-8")

    data = read_json(normalize_transcript(run_paths, raw))

    assert data["segments"][0]["start_ms"] == 0
    assert data["segments"][0]["end_ms"] == 3000


def test_normalize_srt(tmp_path: Path):
    run_paths = create_run(tmp_path, "srt-run")
    raw = run_paths.transcript_dir / "raw.srt"
    raw.write_text(Path("tests/fixtures/sample.srt").read_text(encoding="utf-8"), encoding="utf-8")

    data = read_json(normalize_transcript(run_paths, raw))

    assert len(data["segments"]) == 2
    assert data["segments"][1]["start_ms"] == 3500
    assert data["segments"][1]["text"] == "This is the second subtitle."
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest tests/test_transcript.py -v
```

Expected: fails because `babelecho.transcript` does not exist.

- [ ] **Step 3: Implement transcript normalization**

Create `src/babelecho/transcript.py`:

```python
import re
from pathlib import Path

from .jsonio import write_json
from .paths import RunPaths

TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


def parse_timestamp_ms(value: str) -> int:
    normalized = value.replace(",", ".")
    hours, minutes, seconds = normalized.split(":")
    whole_seconds, millis = seconds.split(".")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(whole_seconds) * 1_000
        + int(millis)
    )


def _segment(segment_id: int, text: str, start_ms: int | None, end_ms: int | None) -> dict:
    return {
        "id": f"{segment_id:04d}",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "speaker": None,
        "text": " ".join(text.split()),
        "source": "transcript",
    }


def parse_plain_text(content: str) -> list[dict]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    return [_segment(index + 1, paragraph, None, None) for index, paragraph in enumerate(paragraphs)]


def parse_timed_text(content: str) -> list[dict]:
    blocks = re.split(r"\n\s*\n", content.strip())
    segments: list[dict] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines == ["WEBVTT"]:
            continue
        time_index = next((index for index, line in enumerate(lines) if TIME_RE.search(line)), None)
        if time_index is None:
            continue
        match = TIME_RE.search(lines[time_index])
        assert match is not None
        text_lines = lines[time_index + 1 :]
        if not text_lines:
            continue
        segments.append(
            _segment(
                len(segments) + 1,
                " ".join(text_lines),
                parse_timestamp_ms(match.group("start")),
                parse_timestamp_ms(match.group("end")),
            )
        )
    return segments


def normalize_transcript(run_paths: RunPaths, raw_path: str | Path) -> Path:
    source = Path(raw_path)
    content = source.read_text(encoding="utf-8")
    suffix = source.suffix.lower()
    if suffix in {".vtt", ".srt"}:
        segments = parse_timed_text(content)
    else:
        segments = parse_plain_text(content)
    if not segments:
        raise ValueError(f"No transcript segments parsed from {source}")
    output = {
        "episode_id": run_paths.run_id,
        "language": "en",
        "segments": segments,
    }
    write_json(run_paths.normalized_transcript_json, output)
    return run_paths.normalized_transcript_json
```

- [ ] **Step 4: Add normalize CLI command**

Modify `src/babelecho/cli.py`:

```python
from .transcript import normalize_transcript
```

Add parser setup:

```python
    normalize = subparsers.add_parser("normalize", help="Normalize raw transcript.")
    normalize.add_argument("--workspace", required=True)
    normalize.add_argument("--run-id", required=True)
    normalize.add_argument("--raw-transcript", required=True)
```

Add command handling before the final `parser.print_help()`:

```python
    if args.command == "normalize":
        run_paths = create_run(args.workspace, args.run_id)
        output = normalize_transcript(run_paths, Path(args.raw_transcript))
        print(output)
        return 0
```

- [ ] **Step 5: Run transcript tests**

Run:

```bash
python -m pytest tests/test_transcript.py tests/test_cli_smoke.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit transcript stage**

Run:

```bash
git add src/babelecho/transcript.py src/babelecho/cli.py tests/fixtures tests/test_transcript.py
git commit -m "feat: normalize transcripts"
```

## Task 5: Chinese Adaptation via Local LLM Adapter

**Files:**
- Create: `src/babelecho/llm.py`
- Create: `src/babelecho/adapt.py`
- Modify: `src/babelecho/cli.py`
- Create: `tests/test_adapt.py`

- [ ] **Step 1: Create adaptation tests**

Create `tests/test_adapt.py`:

```python
from pathlib import Path

from babelecho.adapt import adapt_to_chinese
from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run


def test_adapt_to_chinese_with_fixture_llm(tmp_path: Path):
    run_paths = create_run(tmp_path, "adapt-run")
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": "adapt-run",
            "language": "en",
            "segments": [
                {
                    "id": "0001",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": None,
                    "text": "Welcome to the sample episode.",
                    "source": "transcript",
                }
            ],
        },
    )

    output = adapt_to_chinese(run_paths, {"provider": "fixture"})
    data = read_json(output)

    assert data["language"] == "zh-CN"
    assert data["segments"][0]["source_segment_ids"] == ["0001"]
    assert "中文口播" in data["segments"][0]["text"]
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/test_adapt.py -v
```

Expected: fails because adaptation modules do not exist.

- [ ] **Step 3: Implement LLM adapters**

Create `src/babelecho/llm.py`:

```python
import json
from typing import Protocol
from urllib.request import Request, urlopen


class LLMClient(Protocol):
    def adapt_segment(self, text: str) -> str:
        raise NotImplementedError


class FixtureLLMClient:
    def adapt_segment(self, text: str) -> str:
        return f"中文口播：{text}"


class VLLMClient:
    def __init__(self, base_url: str, model: str, temperature: float, max_tokens: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def adapt_segment(self, text: str) -> str:
        prompt = (
            "请把下面英文播客片段改写成自然、适合口播的简体中文。"
            "只输出中文正文，不要解释。\n\n"
            f"{text}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()


def build_llm_client(config: dict) -> LLMClient:
    provider = config.get("provider")
    if provider == "fixture":
        return FixtureLLMClient()
    if provider == "local_vllm":
        return VLLMClient(
            base_url=config["base_url"],
            model=config["model"],
            temperature=float(config.get("temperature", 0.3)),
            max_tokens=int(config.get("max_tokens", 4096)),
        )
    raise ValueError(f"Unsupported llm.provider: {provider}")
```

- [ ] **Step 4: Implement adaptation stage**

Create `src/babelecho/adapt.py`:

```python
from .jsonio import read_json, write_json
from .llm import build_llm_client
from .paths import RunPaths


def adapt_to_chinese(run_paths: RunPaths, llm_config: dict) -> str:
    transcript = read_json(run_paths.normalized_transcript_json)
    client = build_llm_client(llm_config)
    segments = []
    for segment in transcript["segments"]:
        text = client.adapt_segment(segment["text"])
        segments.append(
            {
                "id": segment["id"],
                "source_segment_ids": [segment["id"]],
                "speaker": segment.get("speaker"),
                "text": text,
            }
        )
    script = {
        "episode_id": transcript["episode_id"],
        "language": "zh-CN",
        "segments": segments,
    }
    write_json(run_paths.chinese_script_json, script)
    return str(run_paths.chinese_script_json)
```

- [ ] **Step 5: Add adapt CLI command**

Modify `src/babelecho/cli.py`:

```python
from .adapt import adapt_to_chinese
```

Add parser setup:

```python
    adapt = subparsers.add_parser("adapt", help="Adapt transcript to Chinese script.")
    adapt.add_argument("--workspace", required=True)
    adapt.add_argument("--run-id", required=True)
    adapt.add_argument("--local-config", required=True)
```

Add command handling:

```python
    if args.command == "adapt":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["llm"])
        run_paths = create_run(args.workspace, args.run_id)
        output = adapt_to_chinese(run_paths, config["llm"])
        print(output)
        return 0
```

- [ ] **Step 6: Run adaptation tests**

Run:

```bash
python -m pytest tests/test_adapt.py tests/test_cli_smoke.py -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit adaptation stage**

Run:

```bash
git add src/babelecho/llm.py src/babelecho/adapt.py src/babelecho/cli.py tests/test_adapt.py
git commit -m "feat: adapt transcripts with local llm adapter"
```

## Task 6: TTS Synthesis via CLI Adapter

**Files:**
- Create: `src/babelecho/tts.py`
- Create: `src/babelecho/synthesize.py`
- Modify: `src/babelecho/cli.py`
- Create: `tests/test_synthesize.py`

- [ ] **Step 1: Create synthesis tests**

Create `tests/test_synthesize.py`:

```python
from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.synthesize import synthesize_segments


def test_synthesize_segments_with_fixture_tts(tmp_path: Path):
    run_paths = create_run(tmp_path, "tts-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "tts-run",
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "source_segment_ids": ["0001"],
                    "speaker": None,
                    "text": "中文口播：欢迎。",
                }
            ],
        },
    )

    manifest_path = synthesize_segments(run_paths, {"provider": "fixture"})
    manifest = read_json(manifest_path)

    audio_path = run_paths.run_dir / manifest["segments"][0]["audio_path"]
    assert audio_path.exists()
    assert audio_path.suffix == ".wav"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/test_synthesize.py -v
```

Expected: fails because synthesis modules do not exist.

- [ ] **Step 3: Implement TTS adapters**

Create `src/babelecho/tts.py`:

```python
import math
import subprocess
import wave
from pathlib import Path


def write_silent_wav(path: Path, duration_seconds: float = 0.2, sample_rate: int = 16_000) -> None:
    frames = int(duration_seconds * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        silence = b"".join((0).to_bytes(2, "little", signed=True) for _ in range(frames))
        handle.writeframes(silence)


def synthesize_text_to_wav(text: str, output_path: Path, tts_config: dict) -> None:
    provider = tts_config.get("provider")
    if provider == "fixture":
        seconds = max(0.2, min(1.0, math.ceil(len(text) / 20) * 0.2))
        write_silent_wav(output_path, seconds)
        return
    if provider == "local_cli":
        text_file = output_path.with_suffix(".txt")
        text_file.write_text(text, encoding="utf-8")
        command = [
            tts_config["command"],
            "--text-file",
            str(text_file),
            "--output",
            str(output_path),
            "--voice",
            tts_config.get("voice", "default-zh"),
        ]
        subprocess.run(command, check=True)
        return
    raise ValueError(f"Unsupported tts.provider: {provider}")
```

- [ ] **Step 4: Implement synthesize stage**

Create `src/babelecho/synthesize.py`:

```python
from .jsonio import read_json, write_json
from .paths import RunPaths
from .tts import synthesize_text_to_wav


def synthesize_segments(run_paths: RunPaths, tts_config: dict) -> str:
    script = read_json(run_paths.chinese_script_json)
    manifest_segments = []
    for segment in script["segments"]:
        audio_path = run_paths.segments_dir / f"{segment['id']}.wav"
        synthesize_text_to_wav(segment["text"], audio_path, tts_config)
        manifest_segments.append(
            {
                "id": segment["id"],
                "audio_path": str(audio_path.relative_to(run_paths.run_dir)),
                "text": segment["text"],
            }
        )
    manifest = {
        "episode_id": script["episode_id"],
        "segments": manifest_segments,
    }
    manifest_path = run_paths.segments_dir / "manifest.json"
    write_json(manifest_path, manifest)
    return str(manifest_path)
```

- [ ] **Step 5: Add synthesize CLI command**

Modify `src/babelecho/cli.py`:

```python
from .synthesize import synthesize_segments
```

Add parser setup:

```python
    synthesize = subparsers.add_parser("synthesize", help="Generate audio segments.")
    synthesize.add_argument("--workspace", required=True)
    synthesize.add_argument("--run-id", required=True)
    synthesize.add_argument("--local-config", required=True)
```

Add command handling:

```python
    if args.command == "synthesize":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["tts"])
        run_paths = create_run(args.workspace, args.run_id)
        output = synthesize_segments(run_paths, config["tts"])
        print(output)
        return 0
```

- [ ] **Step 6: Run synthesis tests**

Run:

```bash
python -m pytest tests/test_synthesize.py tests/test_cli_smoke.py -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit synthesis stage**

Run:

```bash
git add src/babelecho/tts.py src/babelecho/synthesize.py src/babelecho/cli.py tests/test_synthesize.py
git commit -m "feat: synthesize audio segments via tts adapter"
```

## Task 7: Audio Assembly

**Files:**
- Create: `src/babelecho/audio.py`
- Modify: `src/babelecho/cli.py`
- Create: `tests/test_audio.py`

- [ ] **Step 1: Create audio assembly tests**

Create `tests/test_audio.py`:

```python
from pathlib import Path
from unittest.mock import patch

from babelecho.audio import assemble_audio
from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.tts import write_silent_wav


def test_assemble_audio_writes_concat_list_and_invokes_ffmpeg(tmp_path: Path):
    run_paths = create_run(tmp_path, "audio-run")
    first = run_paths.segments_dir / "0001.wav"
    second = run_paths.segments_dir / "0002.wav"
    write_silent_wav(first)
    write_silent_wav(second)
    write_json(
        run_paths.segments_dir / "manifest.json",
        {
            "episode_id": "audio-run",
            "segments": [
                {"id": "0001", "audio_path": "segments/0001.wav", "text": "一"},
                {"id": "0002", "audio_path": "segments/0002.wav", "text": "二"},
            ],
        },
    )

    with patch("subprocess.run") as run:
        output = assemble_audio(run_paths, {"format": "mp3"})

    concat_list = run_paths.output_dir / "concat.txt"
    assert concat_list.exists()
    assert "segments/0001.wav" in concat_list.read_text(encoding="utf-8")
    assert output == str(run_paths.output_audio)
    run.assert_called_once()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/test_audio.py -v
```

Expected: fails because `babelecho.audio` does not exist.

- [ ] **Step 3: Implement ffmpeg assembly wrapper**

Create `src/babelecho/audio.py`:

```python
import subprocess
from pathlib import Path

from .jsonio import read_json
from .paths import RunPaths


def _ffmpeg_concat_line(path: Path) -> str:
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'"


def assemble_audio(run_paths: RunPaths, audio_config: dict | None = None) -> str:
    manifest = read_json(run_paths.segments_dir / "manifest.json")
    concat_path = run_paths.output_dir / "concat.txt"
    lines = []
    for segment in manifest["segments"]:
        audio_path = run_paths.run_dir / segment["audio_path"]
        lines.append(_ffmpeg_concat_line(audio_path))
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    output = run_paths.output_audio
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(output),
    ]
    subprocess.run(command, check=True)
    return str(output)
```

- [ ] **Step 4: Add assemble CLI command**

Modify `src/babelecho/cli.py`:

```python
from .audio import assemble_audio
```

Add parser setup:

```python
    assemble = subparsers.add_parser("assemble", help="Assemble final episode audio.")
    assemble.add_argument("--workspace", required=True)
    assemble.add_argument("--run-id", required=True)
```

Add command handling:

```python
    if args.command == "assemble":
        run_paths = create_run(args.workspace, args.run_id)
        output = assemble_audio(run_paths)
        print(output)
        return 0
```

- [ ] **Step 5: Run audio tests**

Run:

```bash
python -m pytest tests/test_audio.py tests/test_cli_smoke.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit audio assembly**

Run:

```bash
git add src/babelecho/audio.py src/babelecho/cli.py tests/test_audio.py
git commit -m "feat: assemble final podcast audio"
```

## Task 8: Publish Static Podcast Feed

**Files:**
- Create: `src/babelecho/publish.py`
- Modify: `src/babelecho/cli.py`
- Create: `tests/test_publish.py`

- [ ] **Step 1: Create publish tests**

Create `tests/test_publish.py`:

```python
from pathlib import Path
from xml.etree import ElementTree

from babelecho.jsonio import write_json
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
    write_json(run_paths.normalized_transcript_json, {"episode_id": "publish-run", "segments": []})
    write_json(run_paths.chinese_script_json, {"episode_id": "publish-run", "segments": []})

    feed_path = publish_episode(run_paths, {"base_url": "https://example.com/babelecho"})

    assert Path(feed_path).exists()
    assert (run_paths.publish_dir / "episodes" / "publish-run" / "audio.mp3").exists()
    root = ElementTree.parse(feed_path).getroot()
    assert root.tag == "rss"
    assert root.find("./channel/item/title").text == "Sample Episode"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/test_publish.py -v
```

Expected: fails because `babelecho.publish` does not exist.

- [ ] **Step 3: Implement publisher**

Create `src/babelecho/publish.py`:

```python
import shutil
from pathlib import Path
from xml.etree import ElementTree

from .jsonio import read_json, write_json
from .paths import RunPaths


def _text(parent: ElementTree.Element, tag: str, value: str) -> ElementTree.Element:
    child = ElementTree.SubElement(parent, tag)
    child.text = value
    return child


def publish_episode(run_paths: RunPaths, publish_config: dict) -> str:
    base_url = publish_config["base_url"].rstrip("/")
    source = read_json(run_paths.source_json)
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
    shutil.copy2(run_paths.chinese_script_json, episode_dir / "transcript.zh.json")

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
    return str(feed_path)
```

- [ ] **Step 4: Add publish CLI command**

Modify `src/babelecho/cli.py`:

```python
from .publish import publish_episode
```

Add parser setup:

```python
    publish = subparsers.add_parser("publish", help="Publish static podcast artifacts.")
    publish.add_argument("--workspace", required=True)
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--local-config", required=True)
```

Add command handling:

```python
    if args.command == "publish":
        config = load_yaml(Path(args.local_config))
        require_keys(config, ["publish"])
        run_paths = create_run(args.workspace, args.run_id)
        output = publish_episode(run_paths, config["publish"])
        print(output)
        return 0
```

- [ ] **Step 5: Run publish tests**

Run:

```bash
python -m pytest tests/test_publish.py tests/test_cli_smoke.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit publisher**

Run:

```bash
git add src/babelecho/publish.py src/babelecho/cli.py tests/test_publish.py
git commit -m "feat: publish static podcast feed"
```

## Task 9: End-to-End Fixture Pipeline

**Files:**
- Create: `tests/test_end_to_end_fixture.py`
- Modify: `src/babelecho/cli.py`

- [ ] **Step 1: Create end-to-end test with fixture providers**

Create `tests/test_end_to_end_fixture.py`:

```python
import subprocess
import sys
from pathlib import Path


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
        ["normalize", "--raw-transcript", str(workspace / "runs" / "demo" / "transcript" / "raw.vtt")],
        ["adapt", "--local-config", str(local_config)],
        ["synthesize", "--local-config", str(local_config)],
    ]
    for command in commands:
        result = subprocess.run(
            [sys.executable, "-m", "babelecho", command[0], "--workspace", str(workspace), "--run-id", "demo", *command[1:]],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert (workspace / "runs" / "demo" / "script" / "zh.json").exists()
    assert (workspace / "runs" / "demo" / "segments" / "0001.wav").exists()
```

This test stops before `assemble` because it should not require a real `ffmpeg` binary in unit test environments.

- [ ] **Step 2: Run end-to-end fixture test**

Run:

```bash
python -m pytest tests/test_end_to_end_fixture.py -v
```

Expected: one passing test.

- [ ] **Step 3: Run full unit test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit fixture pipeline test**

Run:

```bash
git add tests/test_end_to_end_fixture.py
git commit -m "test: cover fixture backend pipeline"
```

## Task 10: Real Local Runtime Smoke Procedure

**Files:**
- Create: `docs/backend-mvp0-runbook.md`

- [ ] **Step 1: Create runbook**

Create `docs/backend-mvp0-runbook.md`:

````markdown
# Backend MVP-0 Runbook

## Purpose

Run one transcript-first episode through the local MVP-0 pipeline on the 5090D Ubuntu machine.

## Preconditions

- Python environment has `babelecho` installed with `pip install -e .[dev]`.
- vLLM is running locally and serving the configured Qwen Instruct model.
- TTS wrapper command from `workspace/config/local.yaml` is available in `PATH`.
- `ffmpeg` is installed.
- Source config points to a complete transcript.

## Commands

```bash
export WORKSPACE=/path/to/babelecho-workspace
export RUN_ID=first-episode
export SOURCE_CONFIG=$WORKSPACE/sources/hardcoded.yaml
export LOCAL_CONFIG=$WORKSPACE/config/local.yaml

python -m babelecho ingest --workspace "$WORKSPACE" --run-id "$RUN_ID" --source-config "$SOURCE_CONFIG"
python -m babelecho normalize --workspace "$WORKSPACE" --run-id "$RUN_ID" --raw-transcript "$WORKSPACE/runs/$RUN_ID/transcript/raw.vtt"
python -m babelecho adapt --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
python -m babelecho synthesize --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
python -m babelecho assemble --workspace "$WORKSPACE" --run-id "$RUN_ID"
python -m babelecho publish --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
```

## Expected Outputs

- `$WORKSPACE/runs/$RUN_ID/transcript/normalized.json`
- `$WORKSPACE/runs/$RUN_ID/script/zh.json`
- `$WORKSPACE/runs/$RUN_ID/segments/manifest.json`
- `$WORKSPACE/runs/$RUN_ID/output/audio.mp3`
- `$WORKSPACE/runs/$RUN_ID/publish/feed.xml`
- `$WORKSPACE/runs/$RUN_ID/publish/episodes/$RUN_ID/audio.mp3`
````

- [ ] **Step 2: Check runbook formatting**

Run:

```bash
sed -n '1,240p' docs/backend-mvp0-runbook.md
```

Expected: markdown renders as a clear command sequence with no private hostnames or secrets.

- [ ] **Step 3: Commit runbook**

Run:

```bash
git add docs/backend-mvp0-runbook.md
git commit -m "docs: add backend mvp0 runbook"
```

## Final Verification

- [ ] **Step 1: Run all tests**

Run:

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Check changed files**

Run:

```bash
git status --short
```

Expected: no unstaged implementation files except any intentionally edited local config files that are not tracked.

- [ ] **Step 3: Run secret scan before publishing**

Run:

```bash
/opt/homebrew/bin/gitleaks dir .
/opt/homebrew/bin/trufflehog filesystem .
```

Expected: no leaked API keys, private keys, server passwords, private hostnames, or tokens in tracked files.

If running on the 5090D Linux machine without Homebrew paths, use the locally installed `gitleaks` and `trufflehog` binaries from that machine.

## Self-Review Checklist

- Each task produces a working, testable slice.
- The initial implementation supports transcript URL/local file input only.
- The implementation does not introduce ASR, voice clone, queue workers, Web UI, or macOS App code.
- Model-specific dependencies stay out of the pipeline Python environment.
- The TTS integration stays CLI-first.
- The publish output is static files plus a single-episode RSS feed.
