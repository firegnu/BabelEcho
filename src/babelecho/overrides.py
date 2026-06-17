from pathlib import Path
from typing import Any

import yaml

from .jsonio import read_json, write_json
from .paths import RunPaths


def _load_rules(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Override config root must be a mapping: {source}")
    replacements = config.get("replacements", [])
    if not isinstance(replacements, list):
        raise ValueError(f"Override replacements must be a list: {source}")

    rules = []
    for index, rule in enumerate(replacements, start=1):
        if not isinstance(rule, dict):
            raise ValueError(f"Override rule #{index} must be a mapping: {source}")
        source_text = rule.get("from")
        target_text = rule.get("to")
        if not isinstance(source_text, str) or not source_text:
            raise ValueError(f"Override rule #{index} must define nonempty 'from': {source}")
        if not isinstance(target_text, str):
            raise ValueError(f"Override rule #{index} must define string 'to': {source}")
        rules.append({"from": source_text, "to": target_text})
    return rules


def apply_script_overrides(run_paths: RunPaths, overrides_config: dict[str, Any] | None) -> dict:
    if not overrides_config:
        return {"rules": 0, "replacements": 0, "script": str(run_paths.chinese_script_json)}

    path = overrides_config.get("path")
    if not path:
        return {"rules": 0, "replacements": 0, "script": str(run_paths.chinese_script_json)}

    rules = _load_rules(path)
    script = read_json(run_paths.chinese_script_json)
    replacement_count = 0
    for segment in script.get("segments", []):
        text = segment.get("text", "")
        if not isinstance(text, str):
            continue
        for rule in rules:
            occurrences = text.count(rule["from"])
            if occurrences:
                text = text.replace(rule["from"], rule["to"])
                replacement_count += occurrences
        segment["text"] = text

    write_json(run_paths.chinese_script_json, script)
    return {
        "rules": len(rules),
        "replacements": replacement_count,
        "script": str(run_paths.chinese_script_json),
    }
