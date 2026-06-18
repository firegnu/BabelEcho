import importlib.util
import json
from pathlib import Path

import pytest


def load_wrapper():
    path = Path("tools/cosyvoice_tts_wrapper.py")
    spec = importlib.util.spec_from_file_location("cosyvoice_tts_wrapper", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_config_uses_env_defaults(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    text_file = tmp_path / "segment.txt"
    output = tmp_path / "segment.wav"
    monkeypatch.setenv("COSYVOICE_REPO", "/opt/CosyVoice")
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", "/models/CosyVoice2-0.5B")

    args = wrapper.parse_args(
        [
            "--text-file",
            str(text_file),
            "--output",
            str(output),
            "--voice",
            "default-zh",
        ]
    )

    config = wrapper.resolve_config(args)

    assert config.cosyvoice_repo == Path("/opt/CosyVoice")
    assert config.model_dir == Path("/models/CosyVoice2-0.5B")
    assert config.prompt_text == "希望你以后能够做的比我还好呦。"
    assert config.prompt_wav == Path("/opt/CosyVoice/asset/zero_shot_prompt.wav")
    assert config.mode == "zero_shot"
    assert config.speed == 1.0


def test_resolve_config_defaults_to_sft_builtin_4role(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    monkeypatch.setenv("COSYVOICE_REPO", "/opt/CosyVoice")
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", "/models/CosyVoice2-0.5B")
    args = wrapper.parse_args(
        [
            "--batch-file",
            str(tmp_path / "tts-batch.json"),
        ]
    )

    config = wrapper.resolve_config(args)

    assert config.voice == "sft_builtin_4role"
    assert config.model_dir == Path("/opt/CosyVoice/pretrained_models/CosyVoice-300M-SFT")


def test_resolve_config_accepts_cross_lingual_voice_options(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    monkeypatch.setenv("COSYVOICE_REPO", "/opt/CosyVoice")
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", "/models/CosyVoice2-0.5B")
    args = wrapper.parse_args(
        [
            "--text-file",
            str(tmp_path / "segment.txt"),
            "--output",
            str(tmp_path / "segment.wav"),
            "--voice",
            "default-zh",
            "--mode",
            "cross_lingual",
            "--prompt-wav",
            "/opt/CosyVoice/asset/cross_lingual_prompt.wav",
            "--speed",
            "0.92",
        ]
    )

    config = wrapper.resolve_config(args)

    assert config.mode == "cross_lingual"
    assert config.prompt_wav == Path("/opt/CosyVoice/asset/cross_lingual_prompt.wav")
    assert config.speed == 0.92


def test_resolve_config_rejects_unsupported_voice(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    monkeypatch.setenv("COSYVOICE_REPO", "/opt/CosyVoice")
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", "/models/CosyVoice2-0.5B")
    args = wrapper.parse_args(
        [
            "--text-file",
            str(tmp_path / "segment.txt"),
            "--output",
            str(tmp_path / "segment.wav"),
            "--voice",
            "unknown",
        ]
    )

    with pytest.raises(ValueError, match="Unsupported voice"):
        wrapper.resolve_config(args)


def test_resolve_config_accepts_sft_builtin_4role_voice(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    monkeypatch.setenv("COSYVOICE_REPO", "/opt/CosyVoice")
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", "/models/CosyVoice2-0.5B")
    args = wrapper.parse_args(
        [
            "--batch-file",
            str(tmp_path / "tts-batch.json"),
            "--voice",
            "sft_builtin_4role",
            "--model-dir",
            "/models/CosyVoice-300M-SFT",
        ]
    )

    config = wrapper.resolve_config(args)

    assert config.voice == "sft_builtin_4role"
    assert config.model_dir == Path("/models/CosyVoice-300M-SFT")


def test_resolve_config_defaults_sft_model_dir_from_repo(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    monkeypatch.setenv("COSYVOICE_REPO", "/opt/CosyVoice")
    monkeypatch.delenv("COSYVOICE_MODEL_DIR", raising=False)
    args = wrapper.parse_args(
        [
            "--batch-file",
            str(tmp_path / "tts-batch.json"),
            "--voice",
            "sft_builtin_4role",
        ]
    )

    config = wrapper.resolve_config(args)

    assert config.model_dir == Path("/opt/CosyVoice/pretrained_models/CosyVoice-300M-SFT")


def test_resolve_config_ignores_default_model_env_for_sft_voice(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    monkeypatch.setenv("COSYVOICE_REPO", "/opt/CosyVoice")
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", "/models/CosyVoice2-0.5B")
    args = wrapper.parse_args(
        [
            "--batch-file",
            str(tmp_path / "tts-batch.json"),
            "--voice",
            "sft_builtin_4role",
        ]
    )

    config = wrapper.resolve_config(args)

    assert config.model_dir == Path("/opt/CosyVoice/pretrained_models/CosyVoice-300M-SFT")


def test_synthesize_uses_cross_lingual_mode(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    text_file = tmp_path / "segment.txt"
    text_file.write_text("中文口播：欢迎。", encoding="utf-8")
    output = tmp_path / "segment.wav"
    calls = []

    class FakeModel:
        sample_rate = 24_000

        def __init__(self, model_dir):
            self.model_dir = model_dir

        def inference_cross_lingual(self, text, prompt_wav, stream, speed):
            calls.append((text, prompt_wav, stream, speed))
            return [{"tts_speech": FakeTensor()}]

    class FakeTensor:
        def cpu(self):
            return self

    fake_torch = type(
        "FakeTorch",
        (),
        {"cat": staticmethod(lambda chunks, dim: chunks[0])},
    )

    saved = []
    fake_torchaudio = type(
        "FakeTorchaudio",
        (),
        {"save": staticmethod(lambda path, audio, sample_rate: saved.append((path, audio, sample_rate)))},
    )

    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    monkeypatch.setitem(__import__("sys").modules, "torchaudio", fake_torchaudio)
    monkeypatch.setitem(
        __import__("sys").modules,
        "cosyvoice.cli.cosyvoice",
        type("FakeCosyVoiceModule", (), {"AutoModel": FakeModel}),
    )

    config = wrapper.WrapperConfig(
        text_file=text_file,
        output=output,
        voice="default-zh",
        cosyvoice_repo=tmp_path / "CosyVoice",
        model_dir=tmp_path / "model",
        prompt_text=wrapper.DEFAULT_PROMPT_TEXT,
        prompt_wav=tmp_path / "cross_lingual_prompt.wav",
        mode="cross_lingual",
        speed=0.92,
    )

    wrapper.synthesize(config)

    assert calls == [("中文口播：欢迎。", str(tmp_path / "cross_lingual_prompt.wav"), False, 0.92)]
    assert saved == [(str(output), saved[0][1], 24_000)]


def test_synthesize_batch_reuses_model_for_multiple_outputs(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    first_text = tmp_path / "0001.txt"
    second_text = tmp_path / "0002.txt"
    first_output = tmp_path / "0001.wav"
    second_output = tmp_path / "0002.wav"
    batch_file = tmp_path / "tts-batch.json"
    first_text.write_text("第一段中文。", encoding="utf-8")
    second_text.write_text("第二段中文。", encoding="utf-8")
    batch_file.write_text(
        json.dumps(
            {
                "items": [
                    {"text_file": str(first_text), "output": str(first_output)},
                    {"text_file": str(second_text), "output": str(second_output)},
                ]
            }
        ),
        encoding="utf-8",
    )
    init_count = 0
    calls = []

    class FakeModel:
        sample_rate = 24_000

        def __init__(self, model_dir):
            nonlocal init_count
            init_count += 1
            self.model_dir = model_dir

        def inference_cross_lingual(self, text, prompt_wav, stream, speed):
            calls.append((text, prompt_wav, stream, speed))
            return [{"tts_speech": FakeTensor()}]

    class FakeTensor:
        def cpu(self):
            return self

    fake_torch = type(
        "FakeTorch",
        (),
        {"cat": staticmethod(lambda chunks, dim: chunks[0])},
    )

    saved = []
    fake_torchaudio = type(
        "FakeTorchaudio",
        (),
        {"save": staticmethod(lambda path, audio, sample_rate: saved.append((path, audio, sample_rate)))},
    )

    monkeypatch.setenv("COSYVOICE_REPO", str(tmp_path / "CosyVoice"))
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", str(tmp_path / "model"))
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    monkeypatch.setitem(__import__("sys").modules, "torchaudio", fake_torchaudio)
    monkeypatch.setitem(
        __import__("sys").modules,
        "cosyvoice.cli.cosyvoice",
        type("FakeCosyVoiceModule", (), {"AutoModel": FakeModel}),
    )

    args = wrapper.parse_args(
        [
            "--batch-file",
            str(batch_file),
            "--voice",
            "default-zh",
            "--mode",
            "cross_lingual",
            "--prompt-wav",
            str(tmp_path / "cross_lingual_prompt.wav"),
            "--speed",
            "1.0",
        ]
    )
    config = wrapper.resolve_config(args)

    wrapper.synthesize(config)

    assert init_count == 1
    assert calls == [
        ("第一段中文。", str(tmp_path / "cross_lingual_prompt.wav"), False, 1.0),
        ("第二段中文。", str(tmp_path / "cross_lingual_prompt.wav"), False, 1.0),
    ]
    assert saved == [
        (str(first_output), saved[0][1], 24_000),
        (str(second_output), saved[1][1], 24_000),
    ]


def test_synthesize_sft_builtin_4role_uses_item_voice_roles(monkeypatch, tmp_path: Path):
    wrapper = load_wrapper()
    text_file = tmp_path / "0001.txt"
    output = tmp_path / "0001.wav"
    batch_file = tmp_path / "tts-batch.json"
    text_file.write_text("第一段中文。", encoding="utf-8")
    batch_file.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "text_file": str(text_file),
                        "output": str(output),
                        "voice_role": "male_a",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    sft_calls = []

    class FakeAutoModel:
        def __init__(self, model_dir):
            raise AssertionError("AutoModel should not be used for sft_builtin_4role")

    class FakeCosyVoice:
        sample_rate = 22_050

        def __init__(self, model_dir):
            self.model_dir = model_dir

        def inference_sft(self, text, speaker, stream, speed):
            sft_calls.append((text, speaker, stream, speed))
            return [{"tts_speech": FakeTensor()}]

    class FakeTensor:
        def cpu(self):
            return self

    fake_torch = type(
        "FakeTorch",
        (),
        {"cat": staticmethod(lambda chunks, dim: chunks[0])},
    )

    saved = []
    fake_torchaudio = type(
        "FakeTorchaudio",
        (),
        {"save": staticmethod(lambda path, audio, sample_rate: saved.append((path, audio, sample_rate)))},
    )
    ffmpeg_calls = []

    def fake_run(command, check):
        ffmpeg_calls.append((command, check))

    monkeypatch.setenv("COSYVOICE_REPO", str(tmp_path / "CosyVoice"))
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", str(tmp_path / "CosyVoice-300M-SFT"))
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    monkeypatch.setitem(__import__("sys").modules, "torchaudio", fake_torchaudio)
    monkeypatch.setitem(
        __import__("sys").modules,
        "cosyvoice.cli.cosyvoice",
        type(
            "FakeCosyVoiceModule",
            (),
            {"AutoModel": FakeAutoModel, "CosyVoice": FakeCosyVoice},
        ),
    )
    monkeypatch.setattr(wrapper.subprocess, "run", fake_run)

    config = wrapper.resolve_config(
        wrapper.parse_args(
            [
                "--batch-file",
                str(batch_file),
                "--voice",
                "sft_builtin_4role",
                "--speed",
                "1.0",
            ]
        )
    )

    wrapper.synthesize(config)

    assert sft_calls == [("第一段中文。", "中文男", False, 1.0)]
    assert saved == [(str(tmp_path / "0001.raw.wav"), saved[0][1], 22_050)]
    assert ffmpeg_calls
    assert ffmpeg_calls[0][0][:6] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
    ]
    assert str(tmp_path / "0001.raw.wav") in ffmpeg_calls[0][0]
    filter_index = ffmpeg_calls[0][0].index("-af") + 1
    assert ffmpeg_calls[0][0][filter_index] == (
        "volume=-4dB,"
        "highpass=f=150,"
        "equalizer=f=180:t=q:w=1.0:g=-4,"
        "equalizer=f=340:t=q:w=1.0:g=-3.2,"
        "equalizer=f=650:t=q:w=1.1:g=-2.2,"
        "equalizer=f=3000:t=q:w=1.0:g=3.2,"
        "equalizer=f=4500:t=q:w=1.0:g=4.0,"
        "equalizer=f=6500:t=q:w=1.0:g=2.2,"
        "equalizer=f=9000:t=q:w=1.0:g=1.4,"
        "loudnorm=I=-18.5:TP=-1.2:LRA=8:linear=false,"
        "aresample=22050,"
        "asetpts=N/SR/TB"
    )
    assert str(output) == ffmpeg_calls[0][0][-1]
