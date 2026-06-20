from math import sqrt
from pathlib import Path
from typing import Any

from .jsonio import read_json


DEFAULT_SAME_THRESHOLD = 0.8
DEFAULT_POSSIBLE_THRESHOLD = 0.65


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _embedding_vector(value: Any, artifact_path: Path) -> list[float]:
    artifact = _require_mapping(value, str(artifact_path))
    embedding = artifact.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise ValueError(f"embedding artifact missing non-empty embedding: {artifact_path}")
    vector = []
    for item in embedding:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"embedding artifact contains a non-numeric value: {artifact_path}")
        vector.append(float(item))
    return vector


def _resolve_embedding_artifact(run_dir: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("speaker profile embedding_artifact must be a relative path")
    artifact = Path(value)
    if artifact.is_absolute():
        raise ValueError("speaker profile embedding_artifact must be run-local")
    resolved_run = run_dir.resolve()
    resolved_artifact = (run_dir / artifact).resolve()
    if not resolved_artifact.is_relative_to(resolved_run):
        raise ValueError("speaker profile embedding_artifact must be run-local")
    if not resolved_artifact.exists():
        raise ValueError(f"speaker profile embedding_artifact does not exist: {value}")
    return resolved_artifact


def _speaker_ref(speaker: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_index": speaker["run_index"],
        "run_id": speaker["run_id"],
        "speaker_id": speaker["speaker_id"],
    }


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("speaker embedding dimensions do not match")
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("speaker embedding must not be a zero vector")
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    return dot / (left_norm * right_norm)


def _classify_similarity(
    cosine: float,
    *,
    same_threshold: float,
    possible_threshold: float,
) -> str:
    if cosine >= same_threshold:
        return "likely_same"
    if cosine >= possible_threshold:
        return "possible_same"
    return "different"


def _validate_thresholds(same_threshold: float, possible_threshold: float) -> None:
    if not 0.0 <= possible_threshold <= same_threshold <= 1.0:
        raise ValueError(
            "speaker similarity thresholds must satisfy "
            "0 <= possible_threshold <= same_threshold <= 1"
        )


def _load_run_speakers(run_dir: Path, run_index: int) -> tuple[list[dict[str, Any]], int]:
    profiles_path = run_dir / "asr" / "speaker-profiles.json"
    profiles = _require_mapping(read_json(profiles_path), str(profiles_path))
    speakers = profiles.get("speakers")
    if not isinstance(speakers, list):
        raise ValueError(f"speaker profiles speakers must be a list: {profiles_path}")

    loaded = []
    skipped_count = 0
    for speaker in speakers:
        speaker_profile = _require_mapping(speaker, "speaker profile")
        speaker_id = speaker_profile.get("id")
        if not isinstance(speaker_id, str) or not speaker_id.strip():
            raise ValueError(f"speaker profile id is required: {profiles_path}")
        if speaker_profile.get("embedding_status") != "computed":
            skipped_count += 1
            continue
        artifact_path = _resolve_embedding_artifact(
            run_dir,
            speaker_profile.get("embedding_artifact"),
        )
        vector = _embedding_vector(read_json(artifact_path), artifact_path)
        loaded.append(
            {
                "run_index": run_index,
                "run_id": run_dir.name,
                "speaker_id": speaker_id,
                "label": speaker_profile.get("label") or speaker_id,
                "sample_count": speaker_profile.get("sample_count", 0),
                "sample_duration_ms": speaker_profile.get("sample_duration_ms", 0),
                "embedding_dimension": len(vector),
                "embedding_artifact": speaker_profile.get("embedding_artifact"),
                "_embedding": vector,
            }
        )
    return loaded, skipped_count


def compare_speaker_profiles(
    run_dirs: list[str | Path],
    *,
    same_threshold: float = DEFAULT_SAME_THRESHOLD,
    possible_threshold: float = DEFAULT_POSSIBLE_THRESHOLD,
) -> dict[str, Any]:
    """Compare computed speaker embeddings across run directories."""

    _validate_thresholds(same_threshold, possible_threshold)
    if len(run_dirs) < 2:
        raise ValueError("At least two run directories are required")

    resolved_run_dirs = [Path(run_dir) for run_dir in run_dirs]
    speakers = []
    skipped_speaker_count = 0
    for run_index, run_dir in enumerate(resolved_run_dirs):
        loaded, skipped = _load_run_speakers(run_dir, run_index)
        speakers.extend(loaded)
        skipped_speaker_count += skipped

    pairs = []
    for left_index, left in enumerate(speakers):
        for right in speakers[left_index + 1 :]:
            if left["run_index"] == right["run_index"]:
                continue
            cosine = _cosine(left["_embedding"], right["_embedding"])
            pairs.append(
                {
                    "left": _speaker_ref(left),
                    "right": _speaker_ref(right),
                    "same_run": False,
                    "cosine": round(cosine, 6),
                    "classification": _classify_similarity(
                        cosine,
                        same_threshold=same_threshold,
                        possible_threshold=possible_threshold,
                    ),
                }
            )

    public_speakers = [
        {key: value for key, value in speaker.items() if key != "_embedding"}
        for speaker in speakers
    ]
    return {
        "schema_version": "1.0",
        "run_count": len(resolved_run_dirs),
        "speaker_count": len(public_speakers),
        "skipped_speaker_count": skipped_speaker_count,
        "thresholds": {
            "same": same_threshold,
            "possible": possible_threshold,
        },
        "speakers": public_speakers,
        "pairs": pairs,
    }


def format_speaker_similarity_summary(report: dict[str, Any]) -> str:
    counts = {"likely_same": 0, "possible_same": 0, "different": 0}
    for pair in report.get("pairs") or []:
        classification = pair.get("classification")
        if classification in counts:
            counts[classification] += 1
    return (
        f"speaker profile pairs: {len(report.get('pairs') or [])}\n"
        f"computed speakers: {report.get('speaker_count', 0)}; "
        f"skipped speakers: {report.get('skipped_speaker_count', 0)}\n"
        "classifications: "
        f"likely_same={counts['likely_same']} "
        f"possible_same={counts['possible_same']} "
        f"different={counts['different']}"
    )
