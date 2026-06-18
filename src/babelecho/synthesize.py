from .jsonio import read_json, write_json
from .paths import RunPaths
from .speaker_voices import load_speaker_voice_roles
from .tts import synthesize_many_to_wav


SFT_BUILTIN_4ROLE_SEQUENCE = ["female_a", "male_a", "female_b", "male_b"]
SINGLE_SPEAKER_KEYS = {"mode", "prompt_text", "prompt_wav"}
FEMALE_SPEAKER_MARKERS = ("female", "woman", "女")
MALE_SPEAKER_MARKERS = ("male", "man", "男")


def _speaker_count(segments: list[dict]) -> int:
    speakers = {
        segment["speaker"]
        for segment in segments
        if segment.get("speaker")
    }
    return len(speakers)


def _single_speaker(segments: list[dict]) -> str | None:
    speakers = {
        segment["speaker"]
        for segment in segments
        if segment.get("speaker")
    }
    if len(speakers) != 1:
        return None
    return next(iter(speakers))


def _single_speaker_role(segments: list[dict]) -> str:
    speaker = _single_speaker(segments)
    if speaker is None:
        return "female_a"
    speaker_key = str(speaker).casefold()
    if any(marker in speaker_key for marker in FEMALE_SPEAKER_MARKERS):
        return "female_a"
    if any(marker in speaker_key for marker in MALE_SPEAKER_MARKERS):
        return "male_a"
    return "female_a"


def _select_sft_voice(effective_config: dict) -> dict:
    effective_config["voice"] = "sft_builtin_4role"
    for key in SINGLE_SPEAKER_KEYS:
        effective_config.pop(key, None)
    return effective_config


def _effective_tts_config(segments: list[dict], tts_config: dict) -> dict:
    effective_config = dict(tts_config)
    return _select_sft_voice(effective_config)


def _auto_voice_roles_for_segments(segments: list[dict], tts_config: dict) -> list[str | None]:
    if tts_config.get("voice") != "sft_builtin_4role":
        return [None] * len(segments)

    if _speaker_count(segments) <= 1:
        return [_single_speaker_role(segments)] * len(segments)

    speaker_to_role: dict[str, str] = {}
    roles = []
    for segment in segments:
        speaker_key = segment.get("speaker") or "__default__"
        if speaker_key not in speaker_to_role:
            role_index = len(speaker_to_role) % len(SFT_BUILTIN_4ROLE_SEQUENCE)
            speaker_to_role[speaker_key] = SFT_BUILTIN_4ROLE_SEQUENCE[role_index]
        roles.append(speaker_to_role[speaker_key])
    return roles


def _voice_roles_for_segments(
    segments: list[dict],
    tts_config: dict,
    speaker_voice_roles: dict[str, str] | None = None,
) -> list[str | None]:
    roles = _auto_voice_roles_for_segments(segments, tts_config)
    if tts_config.get("voice") != "sft_builtin_4role" or not speaker_voice_roles:
        return roles
    return [
        speaker_voice_roles.get(str(segment.get("speaker")), role)
        if segment.get("speaker") is not None
        else role
        for segment, role in zip(segments, roles, strict=True)
    ]


def synthesize_segments(
    run_paths: RunPaths,
    tts_config: dict,
    speaker_voice_config: dict | None = None,
) -> str:
    script = read_json(run_paths.chinese_script_json)
    effective_tts_config = _effective_tts_config(script["segments"], tts_config)
    manifest_segments = []
    tts_items = []
    speaker_voice_roles = load_speaker_voice_roles(run_paths, speaker_voice_config)
    voice_roles = _voice_roles_for_segments(
        script["segments"],
        effective_tts_config,
        speaker_voice_roles,
    )
    for segment, voice_role in zip(script["segments"], voice_roles, strict=True):
        audio_path = run_paths.segments_dir / f"{segment['id']}.wav"
        manifest_segment = {
            "id": segment["id"],
            "audio_path": str(audio_path.relative_to(run_paths.run_dir)),
            "text": segment["text"],
        }
        if segment.get("speaker") is not None:
            manifest_segment["speaker"] = segment["speaker"]
        if voice_role is not None:
            manifest_segment["voice_role"] = voice_role
            tts_items.append(
                {
                    "text": segment["text"],
                    "output_path": audio_path,
                    "voice_role": voice_role,
                }
            )
        else:
            tts_items.append((segment["text"], audio_path))
        manifest_segments.append(manifest_segment)
    synthesize_many_to_wav(
        tts_items,
        run_paths.segments_dir / "tts-batch.json",
        effective_tts_config,
    )
    manifest = {
        "episode_id": script["episode_id"],
        "tts_voice": effective_tts_config.get("voice", "default-zh"),
        "segments": manifest_segments,
    }
    manifest_path = run_paths.segments_dir / "manifest.json"
    write_json(manifest_path, manifest)
    return str(manifest_path)
