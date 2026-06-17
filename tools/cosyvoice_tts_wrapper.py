#!/usr/bin/env python3
import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROMPT_TEXT = "希望你以后能够做的比我还好呦。"


@dataclass(frozen=True)
class WrapperConfig:
    voice: str
    cosyvoice_repo: Path
    model_dir: Path
    prompt_text: str
    prompt_wav: Path
    mode: str
    speed: float
    text_file: Path | None = None
    output: Path | None = None
    batch_file: Path | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a wav with CosyVoice.")
    parser.add_argument("--text-file")
    parser.add_argument("--output")
    parser.add_argument("--batch-file")
    parser.add_argument("--voice", default="default-zh")
    parser.add_argument("--cosyvoice-repo")
    parser.add_argument("--model-dir")
    parser.add_argument("--prompt-text")
    parser.add_argument("--prompt-wav")
    parser.add_argument("--mode", choices=["zero_shot", "cross_lingual"])
    parser.add_argument("--speed", type=float)
    return parser.parse_args(argv)


def _required_path(name: str, value: str | None) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    return Path(value)


def resolve_config(args: argparse.Namespace) -> WrapperConfig:
    if args.voice != "default-zh":
        raise ValueError(f"Unsupported voice: {args.voice}")
    if args.batch_file and (args.text_file or args.output):
        raise ValueError("Configure either --batch-file or --text-file with --output")
    if not args.batch_file and (not args.text_file or not args.output):
        raise ValueError("--text-file and --output are required unless --batch-file is used")

    cosyvoice_repo = _required_path(
        "COSYVOICE_REPO or --cosyvoice-repo",
        args.cosyvoice_repo or os.environ.get("COSYVOICE_REPO"),
    )
    model_dir = _required_path(
        "COSYVOICE_MODEL_DIR or --model-dir",
        args.model_dir or os.environ.get("COSYVOICE_MODEL_DIR"),
    )
    prompt_text = (
        args.prompt_text
        or os.environ.get("COSYVOICE_PROMPT_TEXT")
        or DEFAULT_PROMPT_TEXT
    )
    mode = args.mode or os.environ.get("COSYVOICE_MODE") or "zero_shot"
    speed = args.speed
    if speed is None:
        speed = float(os.environ.get("COSYVOICE_SPEED", "1.0"))
    if speed <= 0:
        raise ValueError("speed must be greater than 0")
    default_prompt_wav = cosyvoice_repo / "asset" / (
        "cross_lingual_prompt.wav" if mode == "cross_lingual" else "zero_shot_prompt.wav"
    )
    prompt_wav = Path(
        args.prompt_wav
        or os.environ.get("COSYVOICE_PROMPT_WAV")
        or default_prompt_wav
    )
    return WrapperConfig(
        voice=args.voice,
        cosyvoice_repo=cosyvoice_repo,
        model_dir=model_dir,
        prompt_text=prompt_text,
        prompt_wav=prompt_wav,
        mode=mode,
        speed=speed,
        text_file=Path(args.text_file) if args.text_file else None,
        output=Path(args.output) if args.output else None,
        batch_file=Path(args.batch_file) if args.batch_file else None,
    )


def _synthesize_one(config: WrapperConfig, model, torch, torchaudio, text_file: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    text = text_file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Text file is empty: {text_file}")

    if config.mode == "zero_shot":
        outputs = model.inference_zero_shot(
            text,
            config.prompt_text,
            str(config.prompt_wav),
            stream=False,
            speed=config.speed,
        )
    elif config.mode == "cross_lingual":
        outputs = model.inference_cross_lingual(
            text,
            str(config.prompt_wav),
            stream=False,
            speed=config.speed,
        )
    else:
        raise ValueError(f"Unsupported mode: {config.mode}")

    chunks = [item["tts_speech"] for item in outputs]
    if not chunks:
        raise RuntimeError("CosyVoice generated no audio chunks")
    audio = torch.cat(chunks, dim=-1)
    torchaudio.save(str(output), audio.cpu(), model.sample_rate)


def _synthesis_items(config: WrapperConfig) -> list[tuple[Path, Path]]:
    if config.batch_file:
        payload = json.loads(config.batch_file.read_text(encoding="utf-8"))
        items = [
            (Path(item["text_file"]), Path(item["output"]))
            for item in payload.get("items", [])
        ]
        if not items:
            raise ValueError(f"Batch file contains no items: {config.batch_file}")
        return items
    assert config.text_file is not None
    assert config.output is not None
    return [(config.text_file, config.output)]


def synthesize(config: WrapperConfig) -> None:
    sys.path.insert(0, str(config.cosyvoice_repo))
    sys.path.append(str(config.cosyvoice_repo / "third_party" / "Matcha-TTS"))

    import torch
    import torchaudio
    from cosyvoice.cli.cosyvoice import AutoModel

    model = AutoModel(model_dir=str(config.model_dir))
    for text_file, output in _synthesis_items(config):
        _synthesize_one(config, model, torch, torchaudio, text_file, output)


def main(argv: list[str] | None = None) -> int:
    try:
        config = resolve_config(parse_args(argv))
        synthesize(config)
    except Exception as exc:
        print(f"tts-wrapper failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
