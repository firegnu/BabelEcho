#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROMPT_TEXT = "希望你以后能够做的比我还好呦。"
DEFAULT_VOICE = "sft_builtin_4role"
MALE_A_COSYVOICE2_SPEED = 1.1
SUPPORTED_VOICES = {"default-zh", "sft_builtin_4role"}
SUPPORTED_SFT_BUILTIN_4ROLE_ROLES = {
    "female_a",
    "male_a",
    "female_b",
    "male_b",
}
SFT_ROLE_SPEAKERS = {
    "female_a": "中文女",
    "female_b": "英文女",
    "male_b": "英文男",
}
SFT_ROLE_FILTERS = {
    "female_a": "highpass=f=70,loudnorm=I=-19:TP=-1.5:LRA=8:linear=false",
    "female_b": "highpass=f=70,loudnorm=I=-19:TP=-1.5:LRA=8:linear=false",
    "male_b": "highpass=f=70,loudnorm=I=-19:TP=-1.5:LRA=8:linear=false",
}
MALE_A_COSYVOICE2_FILTER = "loudnorm=I=-18.5:TP=-1.2:LRA=8:linear=false"


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
    male_a_model_dir: Path | None = None
    male_a_prompt_wav: Path | None = None
    male_a_speed: float = MALE_A_COSYVOICE2_SPEED


@dataclass(frozen=True)
class SynthesisItem:
    text_file: Path
    output: Path
    voice_role: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a wav with CosyVoice.")
    parser.add_argument("--text-file")
    parser.add_argument("--output")
    parser.add_argument("--batch-file")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
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
    if args.voice not in SUPPORTED_VOICES:
        raise ValueError(f"Unsupported voice: {args.voice}")
    if args.batch_file and (args.text_file or args.output):
        raise ValueError("Configure either --batch-file or --text-file with --output")
    if not args.batch_file and (not args.text_file or not args.output):
        raise ValueError("--text-file and --output are required unless --batch-file is used")

    cosyvoice_repo = _required_path(
        "COSYVOICE_REPO or --cosyvoice-repo",
        args.cosyvoice_repo or os.environ.get("COSYVOICE_REPO"),
    )
    if args.voice == "sft_builtin_4role":
        model_dir_value = args.model_dir
    else:
        model_dir_value = args.model_dir or os.environ.get("COSYVOICE_MODEL_DIR")
    if not model_dir_value and args.voice == "sft_builtin_4role":
        model_dir_value = str(cosyvoice_repo / "pretrained_models" / "CosyVoice-300M-SFT")
    model_dir = _required_path("COSYVOICE_MODEL_DIR or --model-dir", model_dir_value)
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
    male_a_speed = float(
        os.environ.get("COSYVOICE_MALE_A_SPEED", str(MALE_A_COSYVOICE2_SPEED))
    )
    if male_a_speed <= 0:
        raise ValueError("COSYVOICE_MALE_A_SPEED must be greater than 0")
    male_a_model_dir = Path(
        os.environ.get("COSYVOICE_MALE_A_MODEL_DIR")
        or cosyvoice_repo / "pretrained_models" / "CosyVoice2-0.5B"
    )
    male_a_prompt_wav = Path(
        os.environ.get("COSYVOICE_MALE_A_PROMPT_WAV")
        or cosyvoice_repo / "asset" / "cross_lingual_prompt.wav"
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
        male_a_model_dir=male_a_model_dir,
        male_a_prompt_wav=male_a_prompt_wav,
        male_a_speed=male_a_speed,
    )


def _raw_output_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.raw{output.suffix}")


def _cosyvoice2_raw_output_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.cosyvoice2.raw{output.suffix}")


def _postprocess_wav(raw_output: Path, output: Path, audio_filter: str) -> None:
    full_filter = f"{audio_filter},aresample=22050,asetpts=N/SR/TB"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(raw_output),
            "-af",
            full_filter,
            "-ar",
            "22050",
            "-ac",
            "1",
            str(output),
        ],
        check=True,
    )


def _postprocess_sft_role(raw_output: Path, output: Path, voice_role: str) -> None:
    _postprocess_wav(raw_output, output, SFT_ROLE_FILTERS[voice_role])


def _postprocess_male_a_cosyvoice2(raw_output: Path, output: Path) -> None:
    _postprocess_wav(raw_output, output, MALE_A_COSYVOICE2_FILTER)


def _synthesize_one(
    config: WrapperConfig,
    model,
    torch,
    torchaudio,
    item: SynthesisItem,
) -> None:
    text_file = item.text_file
    output = item.output
    output.parent.mkdir(parents=True, exist_ok=True)
    text = text_file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Text file is empty: {text_file}")

    if config.voice == "sft_builtin_4role":
        voice_role = item.voice_role or "female_a"
        if voice_role not in SUPPORTED_SFT_BUILTIN_4ROLE_ROLES:
            raise ValueError(f"Unsupported sft_builtin_4role voice_role: {voice_role}")
        if voice_role == "male_a":
            if config.male_a_prompt_wav is None:
                raise ValueError("male_a_prompt_wav is required for male_a")
            outputs = model.inference_cross_lingual(
                text,
                str(config.male_a_prompt_wav),
                stream=False,
                speed=config.male_a_speed,
            )
            save_output = _cosyvoice2_raw_output_path(output)
            postprocess = "male_a_cosyvoice2"
        else:
            outputs = model.inference_sft(
                text,
                SFT_ROLE_SPEAKERS[voice_role],
                stream=False,
                speed=config.speed,
            )
            save_output = _raw_output_path(output)
            postprocess = "sft"
    elif config.mode == "zero_shot":
        outputs = model.inference_zero_shot(
            text,
            config.prompt_text,
            str(config.prompt_wav),
            stream=False,
            speed=config.speed,
        )
        postprocess = None
    elif config.mode == "cross_lingual":
        outputs = model.inference_cross_lingual(
            text,
            str(config.prompt_wav),
            stream=False,
            speed=config.speed,
        )
        postprocess = None
    else:
        raise ValueError(f"Unsupported mode: {config.mode}")

    chunks = [item["tts_speech"] for item in outputs]
    if not chunks:
        raise RuntimeError("CosyVoice generated no audio chunks")
    audio = torch.cat(chunks, dim=-1)
    audio_output = save_output if postprocess else output
    torchaudio.save(str(audio_output), audio.cpu(), model.sample_rate)
    if postprocess == "sft":
        _postprocess_sft_role(save_output, output, voice_role)
        save_output.unlink(missing_ok=True)
    elif postprocess == "male_a_cosyvoice2":
        _postprocess_male_a_cosyvoice2(save_output, output)
        save_output.unlink(missing_ok=True)


def _synthesis_items(config: WrapperConfig) -> list[SynthesisItem]:
    if config.batch_file:
        payload = json.loads(config.batch_file.read_text(encoding="utf-8"))
        items = [
            SynthesisItem(
                text_file=Path(item["text_file"]),
                output=Path(item["output"]),
                voice_role=item.get("voice_role"),
            )
            for item in payload.get("items", [])
        ]
        if not items:
            raise ValueError(f"Batch file contains no items: {config.batch_file}")
        return items
    assert config.text_file is not None
    assert config.output is not None
    return [SynthesisItem(config.text_file, config.output)]


def synthesize(config: WrapperConfig) -> None:
    sys.path.insert(0, str(config.cosyvoice_repo))
    sys.path.append(str(config.cosyvoice_repo / "third_party" / "Matcha-TTS"))

    import torch
    import torchaudio

    items = _synthesis_items(config)
    if config.voice == "sft_builtin_4role":
        from cosyvoice.cli.cosyvoice import AutoModel, CosyVoice

        sft_model = None
        male_a_model = None
        for item in items:
            voice_role = item.voice_role or "female_a"
            if voice_role not in SUPPORTED_SFT_BUILTIN_4ROLE_ROLES:
                raise ValueError(f"Unsupported sft_builtin_4role voice_role: {voice_role}")
            if voice_role == "male_a":
                if config.male_a_model_dir is None:
                    raise ValueError("male_a_model_dir is required for male_a")
                if male_a_model is None:
                    male_a_model = AutoModel(model_dir=str(config.male_a_model_dir))
                model = male_a_model
            else:
                if sft_model is None:
                    sft_model = CosyVoice(str(config.model_dir))
                model = sft_model
            _synthesize_one(config, model, torch, torchaudio, item)
        return

    from cosyvoice.cli.cosyvoice import AutoModel

    model = AutoModel(model_dir=str(config.model_dir))
    for item in items:
        _synthesize_one(config, model, torch, torchaudio, item)


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
