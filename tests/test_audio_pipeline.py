import os
import subprocess
import sys
from pathlib import Path

from babelecho.jsonio import read_json


def worktree_python_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def test_audio_convert_ingest_audio_stage_creates_isolated_run_artifacts(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"fixture audio bytes")
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text(
        """
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
            "audio",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "audio-cli",
            "--audio-file",
            str(audio),
            "--title",
            "Audio CLI",
            "--local-config",
            str(local_config),
            "--to-stage",
            "ingest_audio",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ingest_audio:" in result.stdout
    assert "audio metadata:" in result.stdout
    run_dir = workspace / "runs" / "audio-cli"
    source = read_json(run_dir / "source.json")
    status = read_json(run_dir / "run.json")
    metadata = read_json(run_dir / "audio" / "metadata.json")
    assert source["source_type"] == "audio_file"
    assert source["audio_input"] == "audio/input.mp3"
    assert metadata["audio_path"] == "audio/input.mp3"
    assert status["status"] == "succeeded"
    assert status["from_stage"] == "ingest_audio"
    assert status["to_stage"] == "ingest_audio"
    assert status["outputs"]["source"] == "source.json"
    assert status["outputs"]["audio_metadata"] == "audio/metadata.json"
    assert str(audio) not in (run_dir / "source.json").read_text(encoding="utf-8")


def test_audio_convert_asr_stage_writes_fixture_asr_artifact(tmp_path: Path):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"fixture audio bytes")
    fixture = Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-asr.json"
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text(
        f"""
asr:
  provider: fixture
  fixture_path: "{fixture}"
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
            "audio",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "audio-asr-cli",
            "--audio-file",
            str(audio),
            "--local-config",
            str(local_config),
            "--to-stage",
            "asr",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ingest_audio:" in result.stdout
    assert "asr:" in result.stdout
    run_dir = workspace / "runs" / "audio-asr-cli"
    raw_asr = read_json(run_dir / "asr" / "raw.json")
    status = read_json(run_dir / "run.json")
    assert raw_asr == read_json(fixture)
    assert status["status"] == "succeeded"
    assert status["to_stage"] == "asr"
    assert status["outputs"]["asr_raw"] == "asr/raw.json"


def test_audio_convert_asr_stage_supports_local_cli_provider(tmp_path: Path):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fixture audio bytes")
    wrapper = tmp_path / "fake_asr_wrapper.py"
    wrapper.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--audio-file", required=True)
parser.add_argument("--output-json", required=True)
parser.add_argument("--model")
parser.add_argument("--language")
parser.add_argument("--device")
args = parser.parse_args()

source = Path(args.audio_file)
Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
Path(args.output_json).write_text(json.dumps({
    "provider": "fake_asr",
    "model": args.model,
    "language": args.language,
    "duration_seconds": 1.5,
    "segments": [
        {
            "start_ms": 0,
            "end_ms": 1500,
            "text": f"local cli saw {source.name}",
        }
    ],
}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text(
        f"""
asr:
  provider: local_cli
  command: "{sys.executable} {wrapper}"
  model: tiny.en
  language: en
  device: cpu
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
            "audio",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "audio-local-cli-asr",
            "--audio-file",
            str(audio),
            "--local-config",
            str(local_config),
            "--to-stage",
            "asr",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "asr:" in result.stdout
    run_dir = workspace / "runs" / "audio-local-cli-asr"
    raw_asr = read_json(run_dir / "asr" / "raw.json")
    status = read_json(run_dir / "run.json")
    assert raw_asr["provider"] == "fake_asr"
    assert raw_asr["model"] == "tiny.en"
    assert raw_asr["language"] == "en"
    assert raw_asr["segments"] == [
        {
            "id": "asr_0001",
            "start_ms": 0,
            "end_ms": 1500,
            "text": "local cli saw input.wav",
        }
    ]
    assert status["status"] == "succeeded"
    assert status["to_stage"] == "asr"
    assert status["outputs"]["asr_raw"] == "asr/raw.json"


def test_audio_convert_diarize_stage_writes_fixture_diarization_artifact(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"fixture audio bytes")
    asr_fixture = Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-asr.json"
    diarization_fixture = (
        Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-diarization.json"
    )
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text(
        f"""
asr:
  provider: fixture
  fixture_path: "{asr_fixture}"
diarization:
  provider: fixture
  fixture_path: "{diarization_fixture}"
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
            "audio",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "audio-diarize-cli",
            "--audio-file",
            str(audio),
            "--local-config",
            str(local_config),
            "--to-stage",
            "diarize",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "diarize:" in result.stdout
    run_dir = workspace / "runs" / "audio-diarize-cli"
    diarization = read_json(run_dir / "asr" / "diarization.json")
    status = read_json(run_dir / "run.json")
    assert diarization == read_json(diarization_fixture)
    assert status["status"] == "succeeded"
    assert status["to_stage"] == "diarize"
    assert status["outputs"]["asr_diarization"] == "asr/diarization.json"


def test_audio_convert_normalize_stage_writes_transcript_artifacts(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"fixture audio bytes")
    asr_fixture = Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-asr.json"
    diarization_fixture = (
        Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-diarization.json"
    )
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text(
        f"""
asr:
  provider: fixture
  fixture_path: "{asr_fixture}"
diarization:
  provider: fixture
  fixture_path: "{diarization_fixture}"
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
            "audio",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "audio-normalize-cli",
            "--audio-file",
            str(audio),
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

    assert result.returncode == 0, result.stderr
    assert "normalize:" in result.stdout
    run_dir = workspace / "runs" / "audio-normalize-cli"
    normalized = read_json(run_dir / "transcript" / "normalized.json")
    quality = read_json(run_dir / "transcript" / "quality.json")
    status = read_json(run_dir / "run.json")
    assert [segment["speaker"] for segment in normalized["segments"]] == [
        "speaker_1",
        "speaker_2",
    ]
    assert quality["recommendation"] == "safe_to_adapt"
    assert status["status"] == "succeeded"
    assert status["to_stage"] == "normalize"
    assert status["outputs"]["normalized"] == "transcript/normalized.json"
    assert status["outputs"]["transcript_quality"] == "transcript/quality.json"


def test_audio_convert_publish_stage_runs_fixture_full_chain(tmp_path: Path):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"fixture audio bytes")
    asr_fixture = Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-asr.json"
    diarization_fixture = (
        Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-diarization.json"
    )
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text(
        f"""
asr:
  provider: fixture
  fixture_path: "{asr_fixture}"
diarization:
  provider: fixture
  fixture_path: "{diarization_fixture}"
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
            "audio",
            "convert",
            "--workspace",
            str(workspace),
            "--run-id",
            "audio-fixture-full-chain",
            "--audio-file",
            str(audio),
            "--title",
            "Audio Fixture Full Chain",
            "--local-config",
            str(local_config),
            "--to-stage",
            "publish",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "adapt:" in result.stdout
    assert "synthesize:" in result.stdout
    assert "assemble:" in result.stdout
    assert "publish:" in result.stdout
    assert "published/feed.xml" in result.stdout

    run_dir = workspace / "runs" / "audio-fixture-full-chain"
    assert (run_dir / "source.json").exists()
    assert (run_dir / "audio" / "metadata.json").exists()
    assert (run_dir / "asr" / "raw.json").exists()
    assert (run_dir / "asr" / "diarization.json").exists()
    assert (run_dir / "transcript" / "normalized.json").exists()
    assert (run_dir / "script" / "zh.json").exists()
    assert (run_dir / "segments" / "manifest.json").exists()
    assert (run_dir / "output" / "audio.mp3").exists()
    assert (run_dir / "publish" / "feed.xml").exists()
    artifact_path = (
        workspace
        / "published"
        / "episodes"
        / "audio-fixture-full-chain"
        / "artifact.json"
    )
    artifact = read_json(artifact_path)
    status = read_json(run_dir / "run.json")
    assert artifact["route"] == "audio_first"
    assert artifact["source"]["type"] == "audio_file"
    assert artifact["asr"]["provider"] == "fixture"
    assert artifact["asr"]["model"] == "fixture"
    assert artifact["asr"]["segment_count"] == 2
    assert artifact["asr"]["speaker_count"] == 2
    assert artifact["asr"]["quality"]["recommendation"] == "safe_to_adapt"
    assert status["status"] == "succeeded"
    assert status["to_stage"] == "publish"
    assert status["outputs"]["audio"] == "output/audio.mp3"
    assert status["outputs"]["feed"] == "publish/feed.xml"
    assert status["outputs"]["stable_feed"] == "published/feed.xml"


def test_audio_convert_rejects_missing_audio_file(tmp_path: Path):
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text("publish:\n  base_url: https://example.com/babelecho\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "audio",
            "convert",
            "--workspace",
            str(tmp_path / "workspace"),
            "--run-id",
            "missing-audio",
            "--audio-file",
            str(tmp_path / "missing.mp3"),
            "--local-config",
            str(local_config),
            "--to-stage",
            "ingest_audio",
        ],
        text=True,
        capture_output=True,
        env=worktree_python_env(),
        check=False,
    )

    assert result.returncode == 1
    assert "Audio file does not exist" in result.stderr
