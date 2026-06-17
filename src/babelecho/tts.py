import math
import subprocess
import wave
from pathlib import Path


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
