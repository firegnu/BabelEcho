import wave
from subprocess import CompletedProcess
from pathlib import Path

import pytest

from babelecho.checks import CheckError, check_run_artifacts
from babelecho.jsonio import write_json
from babelecho.paths import create_run


def _write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(b"\x00\x00" * 1600)


def _write_valid_run(tmp_path: Path):
    run_paths = create_run(tmp_path, "check-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "check-run",
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "source_segment_ids": ["0001"],
                    "speaker": None,
                    "text": "这是一段中文口播稿。",
                }
            ],
        },
    )
    _write_wav(run_paths.segments_dir / "0001.wav")
    write_json(
        run_paths.segments_dir / "manifest.json",
        {
            "episode_id": "check-run",
            "segments": [
                {
                    "id": "0001",
                    "audio_path": "segments/0001.wav",
                    "text": "这是一段中文口播稿。",
                }
            ],
        },
    )
    run_paths.output_audio.write_bytes(b"fake mp3")
    return run_paths


def test_check_run_artifacts_reports_ok_for_valid_script_and_wav(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)

    result = check_run_artifacts(run_paths, checks=("script", "segments"))

    assert result["script_segments"] == 1
    assert result["audio_segments"] == 1


def test_check_run_artifacts_rejects_empty_script_text(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "check-run",
            "language": "zh-CN",
            "segments": [{"id": "0001", "text": "  "}],
        },
    )

    with pytest.raises(CheckError, match="empty text"):
        check_run_artifacts(run_paths, checks=("script",))


def test_check_run_artifacts_rejects_missing_script(tmp_path: Path):
    run_paths = create_run(tmp_path, "missing-script")

    with pytest.raises(CheckError, match="Missing script"):
        check_run_artifacts(run_paths, checks=("script",))


def test_check_run_artifacts_rejects_long_script_segment(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "check-run",
            "language": "zh-CN",
            "segments": [{"id": "0001", "text": "长" * 121}],
        },
    )

    with pytest.raises(CheckError, match="too long"):
        check_run_artifacts(run_paths, checks=("script",), max_script_chars=120)


def test_check_run_artifacts_rejects_script_transcript_artifacts(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "check-run",
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "text": ">> 谢谢您，总统先生。WEBVTT",
                }
            ],
        },
    )

    with pytest.raises(CheckError, match="transcript artifact"):
        check_run_artifacts(run_paths, checks=("script",))


def test_check_run_artifacts_rejects_english_heavy_script_segment(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "check-run",
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "text": (
                        "This segment accidentally remained in English instead "
                        "of being adapted into Chinese spoken-script text."
                    ),
                }
            ],
        },
    )

    with pytest.raises(CheckError, match="English-heavy"):
        check_run_artifacts(run_paths, checks=("script",))


def test_check_run_artifacts_allows_chinese_script_with_repeated_urls(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "check-run",
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "text": (
                        "都会进入你的监控和告警系统。"
                        "我鼓励你去predictionguard.com/practicalai看看我们正在做的事情。"
                        "你可以预约我和团队的演示，我很想听听你对我们在做的事情的反馈。"
                        "所以请访问predictionguard.com/practicalai。"
                        "网址是predictionguard.com/practicalai。"
                    ),
                }
            ],
        },
    )

    result = check_run_artifacts(run_paths, checks=("script",))

    assert result["script_segments"] == 1


def test_check_run_artifacts_rejects_missing_audio_segment(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    (run_paths.segments_dir / "0001.wav").unlink()

    with pytest.raises(CheckError, match="Missing audio segment"):
        check_run_artifacts(run_paths, checks=("segments",))


def test_check_run_artifacts_rejects_missing_manifest(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    (run_paths.segments_dir / "manifest.json").unlink()

    with pytest.raises(CheckError, match="Missing segment manifest"):
        check_run_artifacts(run_paths, checks=("segments",))


def test_check_run_artifacts_reports_output_audio_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    run_paths = _write_valid_run(tmp_path)

    def fake_run(command, check, text, capture_output):
        assert command[:5] == [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_name,sample_rate,channels",
        ]
        assert command[-1] == str(run_paths.output_audio)
        return CompletedProcess(command, 0, stdout="mp3\n24000\n1\n3.5\n")

    monkeypatch.setattr("babelecho.checks.subprocess.run", fake_run)

    result = check_run_artifacts(run_paths, checks=("output",))

    assert result["output_duration_seconds"] == 3.5
    assert result["output_sample_rate"] == 24000
    assert result["output_channels"] == 1


def test_check_run_artifacts_rejects_missing_output_audio(tmp_path: Path):
    run_paths = _write_valid_run(tmp_path)
    run_paths.output_audio.unlink()

    with pytest.raises(CheckError, match="Missing output audio"):
        check_run_artifacts(run_paths, checks=("output",))
