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
    profiles = read_json(run_dir / "asr" / "speaker-profiles.json")
    status = read_json(run_dir / "run.json")
    assert diarization == read_json(diarization_fixture)
    assert profiles["provider"] == "diarization_stats"
    assert profiles["speaker_count"] == 2
    assert [speaker["id"] for speaker in profiles["speakers"]] == [
        "speaker_1",
        "speaker_2",
    ]
    assert status["status"] == "succeeded"
    assert status["to_stage"] == "diarize"
    assert status["outputs"]["asr_diarization"] == "asr/diarization.json"
    assert status["outputs"]["speaker_profiles"] == "asr/speaker-profiles.json"


def test_audio_convert_diarize_stage_applies_fixture_voice_profile(tmp_path: Path):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"fixture audio bytes")
    asr_fixture = Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-asr.json"
    diarization_fixture = (
        Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-diarization.json"
    )
    voice_profile_fixture = (
        Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-voice-profile.json"
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
voice_profile:
  provider: fixture
  fixture_path: "{voice_profile_fixture}"
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
            "audio-voice-profile-cli",
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
    run_dir = workspace / "runs" / "audio-voice-profile-cli"
    profiles = read_json(run_dir / "asr" / "speaker-profiles.json")
    status = read_json(run_dir / "run.json")
    assert profiles["speakers"][0]["embedding_status"] == "fixture"
    assert profiles["speakers"][0]["sample_count"] == 2
    assert profiles["speakers"][0]["sample_duration_ms"] == 12000
    assert profiles["speakers"][0]["embedding_artifact"] == (
        "asr/voice-profiles/speaker_1.json"
    )
    assert status["outputs"]["speaker_profiles"] == "asr/speaker-profiles.json"


def test_audio_convert_diarize_stage_applies_local_cli_voice_profile(tmp_path: Path):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"fixture audio bytes")
    asr_fixture = Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-asr.json"
    diarization_fixture = (
        Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-diarization.json"
    )
    wrapper = tmp_path / "fake_voice_profile_wrapper.py"
    wrapper.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--audio-file", required=True)
parser.add_argument("--diarization-json", required=True)
parser.add_argument("--speaker-profiles-json", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--output-json", required=True)
parser.add_argument("--model")
parser.add_argument("--device")
parser.add_argument("--min-sample-ms")
parser.add_argument("--max-samples-per-speaker")
args = parser.parse_args()

output_dir = Path(args.output_dir)
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / "speaker_1.json").write_text(
    json.dumps({"speaker_id": "speaker_1", "embedding": [0.1, 0.2]}),
    encoding="utf-8",
)
Path(args.output_json).write_text(json.dumps({
    "provider": "fake_embedding",
    "model": args.model,
    "speakers": [
        {
            "id": "speaker_1",
            "sample_count": 1,
            "sample_duration_ms": 4200,
            "profile_kind": "speaker_embedding",
            "embedding_status": "computed",
            "embedding_artifact": "asr/voice-profiles/speaker_1.json"
        }
    ]
}), encoding="utf-8")
""",
        encoding="utf-8",
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
voice_profile:
  provider: local_cli
  command: "{sys.executable} {wrapper}"
  model: fake-model
  device: cpu
  min_sample_ms: 1500
  max_samples_per_speaker: 5
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
            "audio-local-cli-voice-profile",
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
    run_dir = workspace / "runs" / "audio-local-cli-voice-profile"
    profiles = read_json(run_dir / "asr" / "speaker-profiles.json")
    status = read_json(run_dir / "run.json")
    assert profiles["speakers"][0]["profile_kind"] == "speaker_embedding"
    assert profiles["speakers"][0]["embedding_status"] == "computed"
    assert profiles["speakers"][0]["embedding_artifact"] == (
        "asr/voice-profiles/speaker_1.json"
    )
    assert (run_dir / "asr" / "voice-profiles" / "speaker_1.json").exists()
    assert status["outputs"]["speaker_profiles"] == "asr/speaker-profiles.json"


def test_audio_convert_diarize_stage_supports_local_cli_provider(tmp_path: Path):
    workspace = tmp_path / "workspace"
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fixture audio bytes")
    asr_fixture = Path.cwd() / "tests" / "fixtures" / "asr" / "two-speaker-asr.json"
    wrapper = tmp_path / "fake_diarization_wrapper.py"
    wrapper.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--audio-file", required=True)
parser.add_argument("--output-json", required=True)
parser.add_argument("--model")
parser.add_argument("--min-speakers")
parser.add_argument("--max-speakers")
args = parser.parse_args()

source = Path(args.audio_file)
Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
Path(args.output_json).write_text(json.dumps({
    "provider": "fake_diarization",
    "model": args.model,
    "speaker_count": 2,
    "segments": [
        {"start_ms": 0, "end_ms": 4200, "speaker": "speaker_1"},
        {"start_ms": 4300, "end_ms": 9200, "speaker": "speaker_2"},
    ],
    "metadata": {"audio_name": source.name},
}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    local_config = tmp_path / "local-audio.yaml"
    local_config.write_text(
        f"""
asr:
  provider: fixture
  fixture_path: "{asr_fixture}"
diarization:
  provider: local_cli
  command: "{sys.executable} {wrapper}"
  model: fake-diarizer
  min_speakers: 1
  max_speakers: 3
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
            "audio-local-cli-diarization",
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
    run_dir = workspace / "runs" / "audio-local-cli-diarization"
    diarization = read_json(run_dir / "asr" / "diarization.json")
    status = read_json(run_dir / "run.json")
    assert diarization["provider"] == "fake_diarization"
    assert diarization["model"] == "fake-diarizer"
    assert diarization["speaker_count"] == 2
    assert diarization["segments"] == [
        {"start_ms": 0, "end_ms": 4200, "speaker": "speaker_1"},
        {"start_ms": 4300, "end_ms": 9200, "speaker": "speaker_2"},
    ]
    assert diarization["metadata"]["audio_name"] == "input.wav"
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
    assert (run_dir / "asr" / "speaker-profiles.json").exists()
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
    assert artifact["asr"]["speaker_profiles"] == {
        "provider": "diarization_stats",
        "speaker_count": 2,
        "profile_kind": "diarization_stats",
        "embedding_status": "not_computed",
    }
    assert artifact["asr"]["quality"]["recommendation"] == "safe_to_adapt"
    assert artifact["artifacts"]["speaker_profiles"] == "speaker-profiles.json"
    assert (
        workspace
        / "published"
        / "episodes"
        / "audio-fixture-full-chain"
        / "speaker-profiles.json"
    ).exists()
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
