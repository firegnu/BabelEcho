from typing import Any


ALLOWED_REVIEW_STATUSES = ("candidate", "confirmed", "rejected", "split", "ignored")


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
        raise ValueError("speaker alias member run_index must be an integer")
    _require_string(safe["run_id"], "speaker alias member run_id")
    _require_string(safe["speaker_id"], "speaker alias member speaker_id")
    if not isinstance(safe["sample_count"], int) or safe["sample_count"] < 0:
        raise ValueError("speaker alias member sample_count must be a non-negative integer")
    if not isinstance(safe["sample_duration_ms"], int) or safe["sample_duration_ms"] < 0:
        raise ValueError(
            "speaker alias member sample_duration_ms must be a non-negative integer"
        )
    return safe


def _candidate_stats(alias: dict[str, Any]) -> dict[str, Any]:
    return {
        "member_count": alias.get("member_count", 0),
        "pair_count": alias.get("pair_count", 0),
        "min_cosine": alias.get("min_cosine"),
        "max_cosine": alias.get("max_cosine"),
        "average_cosine": alias.get("average_cosine"),
    }


def _existing_reviews(existing_review: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if existing_review is None:
        return {}
    review = _require_mapping(existing_review, "speaker alias review")
    aliases = _require_list(review.get("aliases"), "speaker alias review aliases")
    result = {}
    for item in aliases:
        alias = _require_mapping(item, "speaker alias review alias")
        alias_id = _require_string(alias.get("alias_id"), "speaker alias review alias_id")
        status = alias.get("review_status")
        if status not in ALLOWED_REVIEW_STATUSES:
            raise ValueError(
                "speaker alias review_status must be one of "
                + ", ".join(ALLOWED_REVIEW_STATUSES)
            )
        result[alias_id] = alias
    return result


def build_speaker_alias_review(
    alias_map: dict[str, Any],
    *,
    existing_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a private review contract for speaker alias candidates.

    The output is deliberately passive: it records candidate aliases and manual
    review fields, but nothing in the runtime consumes it for TTS routing yet.
    """

    candidates = _require_mapping(alias_map, "speaker alias map")
    existing_by_alias = _existing_reviews(existing_review)
    review_aliases = []
    status_counts: dict[str, int] = {}

    for item in _require_list(candidates.get("aliases"), "speaker alias map aliases"):
        alias = _require_mapping(item, "speaker alias")
        alias_id = _require_string(alias.get("alias_id"), "speaker alias alias_id")
        existing = existing_by_alias.get(alias_id, {})
        status = existing.get("review_status", "candidate")
        if status not in ALLOWED_REVIEW_STATUSES:
            raise ValueError(
                "speaker alias review_status must be one of "
                + ", ".join(ALLOWED_REVIEW_STATUSES)
            )
        status_counts[status] = status_counts.get(status, 0) + 1
        review_aliases.append(
            {
                "alias_id": alias_id,
                "candidate_alias_id": alias_id,
                "review_status": status,
                "reviewer": existing.get("reviewer"),
                "reviewed_at": existing.get("reviewed_at"),
                "review_note": existing.get("review_note"),
                "candidate": _candidate_stats(alias),
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
        "source": "speaker_alias_review",
        "allowed_review_statuses": list(ALLOWED_REVIEW_STATUSES),
        "review_contract": {
            "candidate": "unreviewed model-generated alias candidate",
            "confirmed": "reviewed and accepted as the same recurring speaker",
            "rejected": "reviewed and rejected as not the same recurring speaker",
            "split": "reviewed and requires manual split before it can be confirmed",
            "ignored": "intentionally left unused without treating it as wrong",
        },
        "alias_count": len(review_aliases),
        "review_status_counts": status_counts,
        "aliases": review_aliases,
    }


def format_speaker_alias_review_summary(review: dict[str, Any]) -> str:
    counts = review.get("review_status_counts") or {}
    ordered = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"speaker alias review: {review.get('alias_count', 0)} aliases\n{ordered}"
