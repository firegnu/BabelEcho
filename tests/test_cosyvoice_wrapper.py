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
