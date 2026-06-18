from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.synthesize import synthesize_segments
from babelecho.tts import synthesize_many_to_wav, synthesize_text_to_wav


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


def test_local_cli_tts_batches_segments_in_one_wrapper_call(monkeypatch, tmp_path: Path):
    calls = []
    first_output = tmp_path / "segments" / "0001.wav"
    second_output = tmp_path / "segments" / "0002.wav"
    batch_path = tmp_path / "segments" / "tts-batch.json"

    def fake_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr("babelecho.tts.subprocess.run", fake_run)

    synthesize_many_to_wav(
        [
            ("第一段中文。", first_output),
            ("第二段中文。", second_output),
        ],
        batch_path,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "default-zh",
            "mode": "cross_lingual",
            "prompt_wav": "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
            "speed": 1.0,
        },
    )

    assert calls == [
        (
            [
                "tts-wrapper",
                "--batch-file",
                str(batch_path),
                "--voice",
                "default-zh",
                "--mode",
                "cross_lingual",
                "--prompt-wav",
                "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
                "--speed",
                "1.0",
            ],
            True,
        )
    ]
    assert first_output.with_suffix(".txt").read_text(encoding="utf-8") == "第一段中文。"
    assert second_output.with_suffix(".txt").read_text(encoding="utf-8") == "第二段中文。"
    assert read_json(batch_path) == {
        "items": [
            {"text_file": str(first_output.with_suffix(".txt")), "output": str(first_output)},
            {"text_file": str(second_output.with_suffix(".txt")), "output": str(second_output)},
        ]
    }


def test_local_cli_tts_defaults_batch_to_sft_builtin_4role(monkeypatch, tmp_path: Path):
    calls = []
    output_path = tmp_path / "segments" / "0001.wav"
    batch_path = tmp_path / "segments" / "tts-batch.json"

    def fake_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr("babelecho.tts.subprocess.run", fake_run)

    synthesize_many_to_wav(
        [("第一段中文。", output_path)],
        batch_path,
        {"provider": "local_cli", "command": "tts-wrapper"},
    )

    assert calls == [
        (
            [
                "tts-wrapper",
                "--batch-file",
                str(batch_path),
                "--voice",
                "sft_builtin_4role",
            ],
            True,
        )
    ]


def test_sft_builtin_4role_profile_assigns_stable_roles(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "multi-speaker-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "multi-speaker-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": "Alice", "text": "第一位。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": "Bob", "text": "第二位。"},
                {"id": "0003", "source_segment_ids": ["0003"], "speaker": "Carol", "text": "第三位。"},
                {"id": "0004", "source_segment_ids": ["0004"], "speaker": "Dave", "text": "第四位。"},
                {"id": "0005", "source_segment_ids": ["0005"], "speaker": "Alice", "text": "第一位回来。"},
            ],
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        captured["batch_path"] = batch_path
        captured["tts_config"] = tts_config
        for item in items:
            item["output_path"].parent.mkdir(parents=True, exist_ok=True)
            item["output_path"].write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    manifest_path = synthesize_segments(run_paths, {"provider": "local_cli", "voice": "sft_builtin_4role"})

    assert [item["voice_role"] for item in captured["items"]] == [
        "female_a",
        "male_a",
        "female_b",
        "male_b",
        "female_a",
    ]
    manifest = read_json(manifest_path)
    assert [segment["speaker"] for segment in manifest["segments"]] == [
        "Alice",
        "Bob",
        "Carol",
        "Dave",
        "Alice",
    ]
    assert [segment["voice_role"] for segment in manifest["segments"]] == [
        "female_a",
        "male_a",
        "female_b",
        "male_b",
        "female_a",
    ]


def test_sft_builtin_4role_uses_speaker_voice_file_before_auto_order(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "speaker-voice-override-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "speaker-voice-override-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": "ROMAN MARS", "text": "罗曼。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": "VIVIAN LE", "text": "薇薇安。"},
                {"id": "0003", "source_segment_ids": ["0003"], "speaker": "TAYA", "text": "泰雅。"},
            ],
        },
    )
    write_json(
        run_paths.script_dir / "speaker-voices.json",
        {
            "speaker_voices": {
                "ROMAN MARS": "male_a",
                "VIVIAN LE": "female_a",
                "TAYA": "female_b",
            }
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        captured["batch_path"] = batch_path
        captured["tts_config"] = tts_config
        for item in items:
            item["output_path"].parent.mkdir(parents=True, exist_ok=True)
            item["output_path"].write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    manifest_path = synthesize_segments(
        run_paths,
        {"provider": "local_cli", "voice": "sft_builtin_4role"},
        {"mode": "infer_once"},
    )

    assert [item["voice_role"] for item in captured["items"]] == [
        "male_a",
        "female_a",
        "female_b",
    ]
    manifest = read_json(manifest_path)
    assert [segment["voice_role"] for segment in manifest["segments"]] == [
        "male_a",
        "female_a",
        "female_b",
    ]


def test_multi_speaker_script_auto_selects_sft_builtin_4role(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "auto-multi-speaker-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "auto-multi-speaker-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": "Host", "text": "主持人。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": "Guest", "text": "嘉宾。"},
            ],
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        captured["tts_config"] = tts_config
        for item in items:
            output_path = item["output_path"] if isinstance(item, dict) else item[1]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    synthesize_segments(
        run_paths,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "default-zh",
            "mode": "cross_lingual",
            "prompt_wav": "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
            "speed": 1.0,
        },
    )

    assert captured["tts_config"]["voice"] == "sft_builtin_4role"
    assert "mode" not in captured["tts_config"]
    assert "prompt_wav" not in captured["tts_config"]
    assert [item["voice_role"] for item in captured["items"]] == ["female_a", "male_a"]


def test_single_unspecified_speaker_auto_selects_sft_female_default(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "auto-single-speaker-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "auto-single-speaker-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": "Solo", "text": "第一段。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": "Solo", "text": "第二段。"},
            ],
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        captured["tts_config"] = tts_config
        for item in items:
            output_path = item["output_path"] if isinstance(item, dict) else item[1]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    synthesize_segments(
        run_paths,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "default-zh",
            "mode": "cross_lingual",
            "prompt_wav": "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
            "speed": 1.0,
        },
    )

    assert captured["tts_config"]["voice"] == "sft_builtin_4role"
    assert "mode" not in captured["tts_config"]
    assert "prompt_wav" not in captured["tts_config"]
    assert [item["voice_role"] for item in captured["items"]] == ["female_a", "female_a"]


def test_no_speaker_script_can_use_configured_default_voice_role(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "no-speaker-default-voice-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "no-speaker-default-voice-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": None, "text": "第一段。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": None, "text": "第二段。"},
            ],
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        for item in items:
            output_path = item["output_path"] if isinstance(item, dict) else item[1]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    manifest_path = synthesize_segments(
        run_paths,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "sft_builtin_4role",
        },
        {"default_voice_role": "male_a"},
    )

    assert [item["voice_role"] for item in captured["items"]] == ["male_a", "male_a"]
    manifest = read_json(manifest_path)
    assert [segment["voice_role"] for segment in manifest["segments"]] == ["male_a", "male_a"]


def test_default_voice_role_does_not_override_existing_speaker_rules(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "speaker-default-voice-ignore-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "speaker-default-voice-ignore-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": "Solo", "text": "第一段。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": "Solo", "text": "第二段。"},
            ],
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        for item in items:
            output_path = item["output_path"] if isinstance(item, dict) else item[1]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    manifest_path = synthesize_segments(
        run_paths,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "sft_builtin_4role",
        },
        {"default_voice_role": "male_a"},
    )

    assert [item["voice_role"] for item in captured["items"]] == ["female_a", "female_a"]
    manifest = read_json(manifest_path)
    assert [segment["voice_role"] for segment in manifest["segments"]] == ["female_a", "female_a"]


def test_single_explicit_male_speaker_auto_selects_sft_male_voice(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "auto-single-male-speaker-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "auto-single-male-speaker-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": "MaleHost", "text": "第一段。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": "MaleHost", "text": "第二段。"},
            ],
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        captured["tts_config"] = tts_config
        for item in items:
            output_path = item["output_path"] if isinstance(item, dict) else item[1]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    manifest_path = synthesize_segments(
        run_paths,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "default-zh",
            "mode": "cross_lingual",
            "prompt_wav": "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
            "speed": 1.0,
        },
    )

    assert captured["tts_config"]["voice"] == "sft_builtin_4role"
    assert "mode" not in captured["tts_config"]
    assert "prompt_wav" not in captured["tts_config"]
    assert [item["voice_role"] for item in captured["items"]] == ["male_a", "male_a"]
    manifest = read_json(manifest_path)
    assert manifest["tts_voice"] == "sft_builtin_4role"
    assert [segment["voice_role"] for segment in manifest["segments"]] == ["male_a", "male_a"]


def test_single_explicit_female_speaker_auto_selects_sft_female_voice(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path, "auto-single-female-speaker-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "auto-single-female-speaker-run",
            "language": "zh-CN",
            "segments": [
                {"id": "0001", "source_segment_ids": ["0001"], "speaker": "FemaleHost", "text": "第一段。"},
                {"id": "0002", "source_segment_ids": ["0002"], "speaker": "FemaleHost", "text": "第二段。"},
            ],
        },
    )
    captured = {}

    def fake_synthesize_many_to_wav(items, batch_path, tts_config):
        captured["items"] = items
        captured["tts_config"] = tts_config
        for item in items:
            output_path = item["output_path"] if isinstance(item, dict) else item[1]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")

    monkeypatch.setattr("babelecho.synthesize.synthesize_many_to_wav", fake_synthesize_many_to_wav)

    manifest_path = synthesize_segments(
        run_paths,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "default-zh",
            "mode": "cross_lingual",
            "prompt_wav": "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
            "speed": 1.0,
        },
    )

    assert captured["tts_config"]["voice"] == "sft_builtin_4role"
    assert "mode" not in captured["tts_config"]
    assert "prompt_wav" not in captured["tts_config"]
    assert [item["voice_role"] for item in captured["items"]] == ["female_a", "female_a"]
    manifest = read_json(manifest_path)
    assert manifest["tts_voice"] == "sft_builtin_4role"
    assert [segment["voice_role"] for segment in manifest["segments"]] == ["female_a", "female_a"]


def test_local_cli_tts_batch_includes_voice_roles_and_model_options(monkeypatch, tmp_path: Path):
    calls = []
    first_output = tmp_path / "segments" / "0001.wav"
    second_output = tmp_path / "segments" / "0002.wav"
    batch_path = tmp_path / "segments" / "tts-batch.json"

    def fake_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr("babelecho.tts.subprocess.run", fake_run)

    synthesize_many_to_wav(
        [
            {"text": "第一段中文。", "output_path": first_output, "voice_role": "female_a"},
            {"text": "第二段中文。", "output_path": second_output, "voice_role": "male_a"},
        ],
        batch_path,
        {
            "provider": "local_cli",
            "command": "tts-wrapper",
            "voice": "sft_builtin_4role",
            "cosyvoice_repo": "/opt/CosyVoice",
            "model_dir": "/models/CosyVoice-300M-SFT",
        },
    )

    assert calls == [
        (
            [
                "tts-wrapper",
                "--batch-file",
                str(batch_path),
                "--voice",
                "sft_builtin_4role",
                "--cosyvoice-repo",
                "/opt/CosyVoice",
                "--model-dir",
                "/models/CosyVoice-300M-SFT",
            ],
            True,
        )
    ]
    assert read_json(batch_path) == {
        "items": [
            {
                "text_file": str(first_output.with_suffix(".txt")),
                "output": str(first_output),
                "voice_role": "female_a",
            },
            {
                "text_file": str(second_output.with_suffix(".txt")),
                "output": str(second_output),
                "voice_role": "male_a",
            },
        ]
    }
