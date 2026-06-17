import importlib.util
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
