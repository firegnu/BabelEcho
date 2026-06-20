from collections import defaultdict, deque
from typing import Any


DEFAULT_ALIAS_SAME_THRESHOLD = 0.85
DEFAULT_MIN_SAMPLE_DURATION_MS = 60000
DEFAULT_MIN_ALIAS_MEMBERS = 2


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _speaker_key(ref: dict[str, Any]) -> tuple[int, str, str]:
    run_index = ref.get("run_index")
    run_id = ref.get("run_id")
    speaker_id = ref.get("speaker_id")
    if not isinstance(run_index, int):
        raise ValueError("speaker reference run_index must be an integer")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("speaker reference run_id is required")
    if not isinstance(speaker_id, str) or not speaker_id:
        raise ValueError("speaker reference speaker_id is required")
    return run_index, run_id, speaker_id


def _speaker_ref_from_key(key: tuple[int, str, str]) -> dict[str, Any]:
    run_index, run_id, speaker_id = key
    return {
        "run_index": run_index,
        "run_id": run_id,
        "speaker_id": speaker_id,
    }


def _speaker_member(speaker: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_index": speaker["run_index"],
        "run_id": speaker["run_id"],
        "speaker_id": speaker["speaker_id"],
        "sample_count": speaker.get("sample_count", 0),
        "sample_duration_ms": speaker.get("sample_duration_ms", 0),
    }


def _speaker_sample_duration(speaker: dict[str, Any]) -> int:
    value = speaker.get("sample_duration_ms", 0)
    if not isinstance(value, int) or value < 0:
        raise ValueError("speaker sample_duration_ms must be a non-negative integer")
    return value


def _validate_options(
    *,
    same_threshold: float,
    min_sample_duration_ms: int,
    min_members: int,
) -> None:
    if not 0.0 <= same_threshold <= 1.0:
        raise ValueError("speaker alias same_threshold must be between 0 and 1")
    if min_sample_duration_ms < 0:
        raise ValueError("speaker alias min_sample_duration_ms must be non-negative")
    if min_members < 2:
        raise ValueError("speaker alias min_members must be at least 2")


def _build_speaker_index(
    report: dict[str, Any],
    *,
    min_sample_duration_ms: int,
) -> tuple[dict[tuple[int, str, str], dict[str, Any]], set[tuple[int, str, str]], list[dict[str, Any]]]:
    speakers = report.get("speakers")
    if not isinstance(speakers, list):
        raise ValueError("speaker similarity report speakers must be a list")

    speaker_by_key = {}
    eligible = set()
    skipped = []
    for item in speakers:
        speaker = _require_mapping(item, "speaker similarity report speaker")
        key = _speaker_key(speaker)
        speaker_by_key[key] = speaker
        sample_duration_ms = _speaker_sample_duration(speaker)
        if sample_duration_ms < min_sample_duration_ms:
            skipped.append(
                {
                    **_speaker_ref_from_key(key),
                    "sample_duration_ms": sample_duration_ms,
                    "reason": "sample_duration_below_minimum",
                }
            )
            continue
        eligible.add(key)
    return speaker_by_key, eligible, sorted(
        skipped,
        key=lambda item: (item["run_index"], item["run_id"], item["speaker_id"]),
    )


def _connected_components(
    adjacency: dict[tuple[int, str, str], set[tuple[int, str, str]]],
) -> list[list[tuple[int, str, str]]]:
    seen = set()
    components = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        component = []
        while queue:
            key = queue.popleft()
            component.append(key)
            for neighbor in sorted(adjacency[key]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    return components


def _component_has_duplicate_run(component: list[tuple[int, str, str]]) -> bool:
    run_indices = [key[0] for key in component]
    return len(run_indices) != len(set(run_indices))


def _component_cosines(
    component: list[tuple[int, str, str]],
    edge_cosines: dict[frozenset[tuple[int, str, str]], float],
) -> list[float]:
    component_set = set(component)
    return [
        cosine
        for edge, cosine in edge_cosines.items()
        if edge.issubset(component_set)
    ]


def build_speaker_aliases(
    similarity_report: dict[str, Any],
    *,
    same_threshold: float = DEFAULT_ALIAS_SAME_THRESHOLD,
    min_sample_duration_ms: int = DEFAULT_MIN_SAMPLE_DURATION_MS,
    min_members: int = DEFAULT_MIN_ALIAS_MEMBERS,
) -> dict[str, Any]:
    """Build conservative private speaker alias candidates from a similarity report."""

    _validate_options(
        same_threshold=same_threshold,
        min_sample_duration_ms=min_sample_duration_ms,
        min_members=min_members,
    )
    report = _require_mapping(similarity_report, "speaker similarity report")
    speaker_by_key, eligible, skipped_speakers = _build_speaker_index(
        report,
        min_sample_duration_ms=min_sample_duration_ms,
    )
    pairs = report.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("speaker similarity report pairs must be a list")

    adjacency: dict[tuple[int, str, str], set[tuple[int, str, str]]] = defaultdict(set)
    edge_cosines: dict[frozenset[tuple[int, str, str]], float] = {}
    for item in pairs:
        pair = _require_mapping(item, "speaker similarity report pair")
        cosine = pair.get("cosine")
        if isinstance(cosine, bool) or not isinstance(cosine, (int, float)):
            raise ValueError("speaker similarity report pair cosine must be numeric")
        if float(cosine) < same_threshold:
            continue
        left = _speaker_key(_require_mapping(pair.get("left"), "pair left"))
        right = _speaker_key(_require_mapping(pair.get("right"), "pair right"))
        if left not in speaker_by_key or right not in speaker_by_key:
            raise ValueError("speaker similarity pair references an unknown speaker")
        if left not in eligible or right not in eligible:
            continue
        adjacency[left].add(right)
        adjacency[right].add(left)
        edge_cosines[frozenset((left, right))] = float(cosine)

    aliases = []
    skipped_components = []
    for component in _connected_components(adjacency):
        if len(component) < min_members:
            continue
        if _component_has_duplicate_run(component):
            skipped_components.append(
                {
                    "reason": "multiple_speakers_in_one_run",
                    "members": [_speaker_ref_from_key(key) for key in component],
                }
            )
            continue
        cosines = _component_cosines(component, edge_cosines)
        if not cosines:
            continue
        aliases.append(
            {
                "alias_id": f"speaker_alias_{len(aliases) + 1:03d}",
                "member_count": len(component),
                "pair_count": len(cosines),
                "min_cosine": round(min(cosines), 6),
                "max_cosine": round(max(cosines), 6),
                "average_cosine": round(sum(cosines) / len(cosines), 6),
                "members": [
                    _speaker_member(speaker_by_key[key])
                    for key in sorted(component)
                ],
            }
        )

    return {
        "schema_version": "1.0",
        "source": "speaker_similarity_report",
        "thresholds": {
            "same": same_threshold,
            "min_sample_duration_ms": min_sample_duration_ms,
            "min_members": min_members,
        },
        "alias_count": len(aliases),
        "aliases": aliases,
        "skipped_speakers": skipped_speakers,
        "skipped_components": skipped_components,
    }


def format_speaker_alias_summary(alias_map: dict[str, Any]) -> str:
    return (
        f"speaker aliases: {alias_map.get('alias_count', 0)}\n"
        f"skipped speakers: {len(alias_map.get('skipped_speakers') or [])}; "
        f"skipped components: {len(alias_map.get('skipped_components') or [])}"
    )
