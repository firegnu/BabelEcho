from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be a mapping: {source}")
    return value


def require_keys(mapping: dict[str, Any], keys: list[str]) -> None:
    for key in keys:
        if key not in mapping:
            raise ValueError(f"Missing required key: {key}")
