from pathlib import Path

import pytest

from babelecho.config import load_yaml, require_keys
from babelecho.jsonio import read_json, write_json
from babelecho.paths import RunPaths, create_run


def test_load_yaml_reads_mapping(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("source:\n  type: transcript_url\n", encoding="utf-8")

    assert load_yaml(config_path) == {"source": {"type": "transcript_url"}}


def test_require_keys_reports_missing_key():
    with pytest.raises(ValueError, match="Missing required key: source"):
        require_keys({}, ["source"])


def test_create_run_builds_expected_directories(tmp_path: Path):
    run_paths = create_run(tmp_path, "demo-run")

    assert isinstance(run_paths, RunPaths)
    assert run_paths.run_dir == tmp_path / "runs" / "demo-run"
    assert run_paths.transcript_dir.is_dir()
    assert run_paths.script_dir.is_dir()
    assert run_paths.segments_dir.is_dir()
    assert run_paths.output_dir.is_dir()
    assert run_paths.publish_dir.is_dir()


def test_json_round_trip(tmp_path: Path):
    path = tmp_path / "data.json"

    write_json(path, {"hello": "world"})

    assert read_json(path) == {"hello": "world"}
