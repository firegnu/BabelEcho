from typing import Any

from .speaker_voices import VOICE_ROLES


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


def _safe_member(member: dict[str, Any]) -> dict[str, Any]:
    safe = {
        "run_index": member.get("run_index"),
        "run_id": member.get("run_id"),
        "speaker_id": member.get("speaker_id"),
        "sample_count": member.get("sample_count", 0),
        "sample_duration_ms": member.get("sample_duration_ms", 0),
    }
    if not isinstance(safe["run_index"], int):
        raise ValueError("speaker voice role member run_index must be an integer")
    _require_string(safe["run_id"], "speaker voice role member run_id")
    _require_string(safe["speaker_id"], "speaker voice role member speaker_id")
    if not isinstance(safe["sample_count"], int) or safe["sample_count"] < 0:
        raise ValueError(
            "speaker voice role member sample_count must be a non-negative integer"
        )
    if not isinstance(safe["sample_duration_ms"], int) or safe["sample_duration_ms"] < 0:
        raise ValueError(
            "speaker voice role member sample_duration_ms must be a non-negative integer"
        )
    return safe


def _existing_voice_roles(existing_map: dict[str, Any] | None) -> dict[str, str]:
    if existing_map is None:
        return {}
    data = _require_mapping(existing_map, "speaker voice role map")
    raw_map = _require_mapping(
        data.get("voice_role_map"), "speaker voice role map voice_role_map"
    )
    result = {}
    for alias_id, role in raw_map.items():
        alias_id = _require_string(alias_id, "speaker voice role map alias_id")
        role = _require_string(role, "speaker voice role")
        if role not in VOICE_ROLES:
            raise ValueError(
                "speaker voice role must be one of: " + ", ".join(VOICE_ROLES)
            )
        result[alias_id] = role
    return result


def _next_role(used_roles: set[str], assignment_index: int) -> tuple[str, int]:
    for offset in range(len(VOICE_ROLES)):
        role = VOICE_ROLES[(assignment_index + offset) % len(VOICE_ROLES)]
        if role not in used_roles:
            used_roles.add(role)
            return role, assignment_index + offset + 1
    role = VOICE_ROLES[assignment_index % len(VOICE_ROLES)]
    return role, assignment_index + 1


def build_speaker_voice_role_map(
    review: dict[str, Any],
    *,
    existing_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a private voice-role map from confirmed speaker alias reviews."""

    review_data = _require_mapping(review, "speaker alias review")
    existing_by_alias = _existing_voice_roles(existing_map)
    confirmed_aliases = []
    skipped_aliases = []

    for item in _require_list(review_data.get("aliases"), "speaker alias review aliases"):
        alias = _require_mapping(item, "speaker alias review alias")
        alias_id = _require_string(alias.get("alias_id"), "speaker alias review alias_id")
        status = alias.get("review_status")
        if status != "confirmed":
            skipped_aliases.append(
                {
                    "alias_id": alias_id,
                    "review_status": status,
                    "reason": "not_confirmed",
                }
            )
            continue
        confirmed_aliases.append(alias)

    used_roles = {
        existing_by_alias[alias["alias_id"]]
        for alias in confirmed_aliases
        if alias["alias_id"] in existing_by_alias
    }
    assignment_index = 0
    aliases = []
    voice_role_map = {}

    for alias in confirmed_aliases:
        alias_id = alias["alias_id"]
        role = existing_by_alias.get(alias_id)
        if role is None:
            role, assignment_index = _next_role(used_roles, assignment_index)
        voice_role_map[alias_id] = role
        aliases.append(
            {
                "alias_id": alias_id,
                "voice_role": role,
                "review_status": "confirmed",
                "members": [
                    _safe_member(_require_mapping(member, "speaker alias member"))
                    for member in _require_list(
                        alias.get("members"), "speaker alias members"
                    )
                ],
            }
        )

    return {
        "schema_version": "1.0",
        "source": "speaker_voice_role_map",
        "assignment_mode": "confirmed_aliases_only",
        "voice_roles": list(VOICE_ROLES),
        "contract": {
            "confirmed_only": "only aliases with review_status=confirmed are assigned a voice_role",
            "private": "this file is a private contract and is not published",
            "not_consumed_by_tts": "current TTS routing does not consume this map",
        },
        "alias_count": len(aliases),
        "voice_role_map": voice_role_map,
        "aliases": aliases,
        "skipped_aliases": skipped_aliases,
    }


def format_speaker_voice_role_map_summary(role_map: dict[str, Any]) -> str:
    return f"speaker voice roles: {role_map.get('alias_count', 0)} aliases"
