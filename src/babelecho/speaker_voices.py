from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json
from .llm import build_llm_client
from .paths import RunPaths


VOICE_ROLES = ("female_a", "male_a", "female_b", "male_b")
FEMALE_VOICE_ROLES = ("female_a", "female_b")
MALE_VOICE_ROLES = ("male_a", "male_b")
VALID_GENDERS = {"male", "female", "unknown"}


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return value


def _require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} is required")
    return value


def speaker_voice_path(run_paths: RunPaths, config: dict[str, Any] | None = None) -> Path:
    configured_path = (config or {}).get("path")
    if configured_path:
        return Path(str(configured_path).format(workspace=run_paths.workspace, run_id=run_paths.run_id))
    return run_paths.script_dir / "speaker-voices.json"


def collect_speaker_samples(
    run_paths: RunPaths,
    max_samples_per_speaker: int = 3,
    max_sample_chars: int = 220,
) -> list[dict[str, Any]]:
    script = read_json(run_paths.chinese_script_json)
    speakers: dict[str, dict[str, Any]] = {}
    for segment in script.get("segments", []):
        speaker = segment.get("speaker")
        if not speaker:
            continue
        speaker_name = str(speaker)
        entry = speakers.setdefault(
            speaker_name,
            {
                "speaker": speaker_name,
                "segment_count": 0,
                "samples": [],
            },
        )
        entry["segment_count"] += 1
        samples = entry["samples"]
        text = str(segment.get("text", "")).strip()
        if text and len(samples) < max_samples_per_speaker:
            samples.append(text[:max_sample_chars])
    return list(speakers.values())


def _normalize_gender(value: Any) -> str:
    gender = str(value or "unknown").casefold()
    return gender if gender in VALID_GENDERS else "unknown"


def _normalize_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _next_role(
    sequence: tuple[str, ...],
    role_offsets: dict[tuple[str, ...], int],
    used_roles: set[str],
) -> str:
    start = role_offsets.get(sequence, 0)
    for offset in range(len(sequence)):
        index = (start + offset) % len(sequence)
        role = sequence[index]
        if role not in used_roles:
            role_offsets[sequence] = index + 1
            used_roles.add(role)
            return role
    role = sequence[start % len(sequence)]
    role_offsets[sequence] = start + 1
    return role


def assign_voice_roles(
    speakers: list[dict[str, Any]],
    inferences: list[dict[str, Any]],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    inference_by_speaker = {
        str(item.get("speaker")): item
        for item in inferences
        if item.get("speaker") is not None
    }
    speaker_voices: dict[str, str] = {}
    inference_records = []
    role_offsets: dict[tuple[str, ...], int] = {}
    used_roles: set[str] = set()
    for speaker in speakers:
        speaker_name = str(speaker["speaker"])
        inference = inference_by_speaker.get(speaker_name, {})
        gender = _normalize_gender(inference.get("gender"))
        if gender == "male":
            role = _next_role(MALE_VOICE_ROLES, role_offsets, used_roles)
        elif gender == "female":
            role = _next_role(FEMALE_VOICE_ROLES, role_offsets, used_roles)
        else:
            role = _next_role(VOICE_ROLES, role_offsets, used_roles)
        speaker_voices[speaker_name] = role
        inference_records.append(
            {
                "speaker": speaker_name,
                "gender": gender,
                "confidence": _normalize_confidence(inference.get("confidence")),
                "reason": str(inference.get("reason", "")),
                "voice_role": role,
            }
        )
    return speaker_voices, inference_records


def infer_speaker_voices(
    run_paths: RunPaths,
    llm_config: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_path = speaker_voice_path(run_paths, config)
    if output_path.exists():
        return {"status": "reused", "path": str(output_path)}
    speakers = collect_speaker_samples(run_paths)
    if not speakers:
        return {"status": "skipped", "path": str(output_path), "reason": "no speakers"}
    client = build_llm_client(llm_config)
    inferences = client.infer_speaker_genders(speakers)
    speaker_voices, inference_records = assign_voice_roles(speakers, inferences)
    write_json(
        output_path,
        {
            "version": 1,
            "mode": (config or {}).get("mode", "infer_once"),
            "speaker_voices": speaker_voices,
            "inferences": inference_records,
        },
    )
    return {"status": "created", "path": str(output_path)}


def infer_speaker_voices_if_enabled(
    run_paths: RunPaths,
    local_config: dict[str, Any],
) -> dict[str, Any] | None:
    config = local_config.get("speaker_voices")
    if not isinstance(config, dict):
        return None
    mode = config.get("mode")
    try:
        if mode == "infer_once":
            return infer_speaker_voices(run_paths, local_config["llm"], config)
        if mode == "apply_voice_role_map":
            role_map = read_json(_speaker_voice_role_map_path(run_paths, config))
            return apply_speaker_voice_role_map(
                run_paths,
                role_map,
                overwrite=bool(config.get("overwrite")),
            )
        return None
    except Exception as error:
        return {
            "status": "failed",
            "path": str(speaker_voice_path(run_paths, config)),
            "error": str(error),
        }


def _speaker_voice_role_map_path(run_paths: RunPaths, config: dict[str, Any]) -> Path:
    configured_path = config.get("voice_role_map")
    if not configured_path:
        raise ValueError("speaker_voices.voice_role_map is required")
    return Path(
        str(configured_path).format(
            workspace=run_paths.workspace,
            run_id=run_paths.run_id,
        )
    )


def _speaker_voices_from_role_map(
    role_map: dict[str, Any],
    run_id: str,
) -> tuple[dict[str, str], list[dict[str, Any]], set[str]]:
    data = _require_mapping(role_map, "speaker voice role map")
    speaker_voices: dict[str, str] = {}
    inferences = []
    matched_aliases: set[str] = set()

    for item in _require_list(data.get("aliases"), "speaker voice role map aliases"):
        alias = _require_mapping(item, "speaker voice role map alias")
        alias_id = _require_string(alias.get("alias_id"), "speaker voice role alias_id")
        voice_role = _require_string(alias.get("voice_role"), "speaker voice role")
        if voice_role not in VOICE_ROLES:
            raise ValueError("speaker voice role must be one of: " + ", ".join(VOICE_ROLES))
        if alias.get("review_status") != "confirmed":
            continue
        for member_item in _require_list(alias.get("members"), "speaker voice role members"):
            member = _require_mapping(member_item, "speaker voice role member")
            if member.get("run_id") != run_id:
                continue
            speaker_id = _require_string(
                member.get("speaker_id"), "speaker voice role member speaker_id"
            )
            previous = speaker_voices.get(speaker_id)
            if previous is not None and previous != voice_role:
                raise ValueError(
                    f"speaker {speaker_id} maps to multiple voice roles: "
                    f"{previous}, {voice_role}"
                )
            if previous == voice_role:
                continue
            matched_aliases.add(alias_id)
            speaker_voices[speaker_id] = voice_role
            inferences.append(
                {
                    "speaker": speaker_id,
                    "gender": "unknown",
                    "confidence": 1.0,
                    "reason": f"confirmed speaker alias {alias_id}",
                    "voice_role": voice_role,
                    "alias_id": alias_id,
                }
            )
    return speaker_voices, inferences, matched_aliases


def apply_speaker_voice_role_map(
    run_paths: RunPaths,
    role_map: dict[str, Any],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    output_path = speaker_voice_path(run_paths)
    if output_path.exists() and not overwrite:
        return {"status": "reused", "path": str(output_path)}

    speaker_voices, inferences, matched_aliases = _speaker_voices_from_role_map(
        role_map,
        run_paths.run_id,
    )
    if not speaker_voices:
        return {
            "status": "skipped",
            "path": str(output_path),
            "reason": "no matching speakers",
            "speaker_count": 0,
            "alias_count": 0,
        }

    write_json(
        output_path,
        {
            "version": 1,
            "mode": "speaker_voice_role_map",
            "source": "speaker_voice_role_map",
            "speaker_voices": speaker_voices,
            "inferences": inferences,
        },
    )
    return {
        "status": "created",
        "path": str(output_path),
        "speaker_count": len(speaker_voices),
        "alias_count": len(matched_aliases),
    }


def load_speaker_voice_roles(
    run_paths: RunPaths,
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    if not isinstance(config, dict):
        return {}
    roles: dict[str, str] = {}
    configured_roles = config.get("voices")
    if isinstance(configured_roles, dict):
        roles.update(
            {
                str(speaker): str(role)
                for speaker, role in configured_roles.items()
                if str(role) in VOICE_ROLES
            }
        )
    path = speaker_voice_path(run_paths, config)
    if not path.exists():
        return roles
    try:
        data = read_json(path)
    except Exception:
        return roles
    file_roles = data.get("speaker_voices")
    if isinstance(file_roles, dict):
        roles.update(
            {
                str(speaker): str(role)
                for speaker, role in file_roles.items()
                if str(role) in VOICE_ROLES
            }
        )
    return roles
