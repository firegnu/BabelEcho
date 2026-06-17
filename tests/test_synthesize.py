from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.synthesize import synthesize_segments
from babelecho.tts import synthesize_text_to_wav


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


def test_local_cli_tts_forwards_voice_calibration_options(monkeypatch, tmp_path: Path):
    output_path = tmp_path / "segment.wav"
    calls = []

    def fake_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr("babelecho.tts.subprocess.run", fake_run)

    synthesize_text_to_wav(
        "中文口播：欢迎。",
        output_path,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "default-zh",
            "mode": "cross_lingual",
            "prompt_wav": "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
            "speed": 0.92,
        },
    )

    assert calls == [
        (
            [
                "tts-wrapper",
                "--text-file",
                str(output_path.with_suffix(".txt")),
                "--output",
                str(output_path),
                "--voice",
                "default-zh",
                "--mode",
                "cross_lingual",
                "--prompt-wav",
                "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
                "--speed",
                "0.92",
            ],
            True,
        )
    ]
    assert output_path.with_suffix(".txt").read_text(encoding="utf-8") == "中文口播：欢迎。"
