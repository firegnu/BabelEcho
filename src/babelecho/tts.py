import math
import subprocess
import wave
from pathlib import Path
from typing import Any

from .jsonio import write_json


def write_silent_wav(
    path: Path,
    duration_seconds: float = 0.2,
    sample_rate: int = 16_000,
) -> None:
    frames = int(duration_seconds * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)


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
        for config_key, flag in [
            ("cosyvoice_repo", "--cosyvoice-repo"),
            ("model_dir", "--model-dir"),
            ("mode", "--mode"),
            ("prompt_text", "--prompt-text"),
            ("prompt_wav", "--prompt-wav"),
            ("speed", "--speed"),
        ]:
            value = tts_config.get(config_key)
            if value is not None:
                command.extend([flag, str(value)])
        subprocess.run(command, check=True)
        return
    raise ValueError(f"Unsupported tts.provider: {provider}")


def _normalize_item(item: tuple[str, Path] | dict[str, Any]) -> tuple[str, Path, dict[str, str]]:
    if isinstance(item, dict):
        text = item["text"]
        output_path = Path(item["output_path"])
        metadata = {}
        if item.get("voice_role"):
            metadata["voice_role"] = str(item["voice_role"])
        return text, output_path, metadata
    text, output_path = item
    return text, output_path, {}


def synthesize_many_to_wav(
    items: list[tuple[str, Path] | dict[str, Any]],
    batch_path: Path,
    tts_config: dict,
) -> None:
    provider = tts_config.get("provider")
    if provider == "fixture":
        for item in items:
            text, output_path, _metadata = _normalize_item(item)
            seconds = max(0.2, min(1.0, math.ceil(len(text) / 20) * 0.2))
            write_silent_wav(output_path, seconds)
        return
    if provider == "local_cli":
        batch_items = []
        for item in items:
            text, output_path, metadata = _normalize_item(item)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            text_file = output_path.with_suffix(".txt")
            text_file.write_text(text, encoding="utf-8")
            batch_item = {
                "text_file": str(text_file),
                "output": str(output_path),
            }
            batch_item.update(metadata)
            batch_items.append(batch_item)
        write_json(batch_path, {"items": batch_items})
        command = [
            tts_config["command"],
            "--batch-file",
            str(batch_path),
            "--voice",
            tts_config.get("voice", "default-zh"),
        ]
        for config_key, flag in [
            ("cosyvoice_repo", "--cosyvoice-repo"),
            ("model_dir", "--model-dir"),
            ("mode", "--mode"),
            ("prompt_text", "--prompt-text"),
            ("prompt_wav", "--prompt-wav"),
            ("speed", "--speed"),
        ]:
            value = tts_config.get(config_key)
            if value is not None:
                command.extend([flag, str(value)])
        subprocess.run(command, check=True)
        return
    raise ValueError(f"Unsupported tts.provider: {provider}")
