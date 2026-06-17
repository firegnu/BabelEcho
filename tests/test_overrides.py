import subprocess
import sys
from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.overrides import apply_script_overrides
from babelecho.paths import create_run


def _write_script(run_paths):
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": run_paths.run_id,
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "source_segment_ids": ["0001"],
                    "speaker": None,
                    "text": "NASA Crew-9 采访 Nick Hague。",
                }
            ],
        },
    )


def test_apply_script_overrides_rewrites_script_text(tmp_path: Path):
    run_paths = create_run(tmp_path, "override-run")
    _write_script(run_paths)
    overrides = tmp_path / "overrides.yaml"
    overrides.write_text(
        """
replacements:
  - from: "NASA"
    to: "美国国家航空航天局"
  - from: "Crew-9"
    to: "Crew Nine"
  - from: "Nick Hague"
    to: "尼克·黑格"
""",
        encoding="utf-8",
    )

    result = apply_script_overrides(run_paths, {"path": str(overrides)})
    script = read_json(run_paths.chinese_script_json)

    assert result["rules"] == 3
    assert result["replacements"] == 3
    assert script["segments"][0]["text"] == "美国国家航空航天局 Crew Nine 采访 尼克·黑格。"


def test_apply_script_overrides_skips_when_unconfigured(tmp_path: Path):
    run_paths = create_run(tmp_path, "no-override-run")
    _write_script(run_paths)

    result = apply_script_overrides(run_paths, None)
    script = read_json(run_paths.chinese_script_json)

    assert result["rules"] == 0
    assert result["replacements"] == 0
    assert script["segments"][0]["text"] == "NASA Crew-9 采访 Nick Hague。"


def test_overrides_command_updates_existing_script(tmp_path: Path):
    workspace = tmp_path / "workspace"
    run_paths = create_run(workspace, "override-cli-run")
    _write_script(run_paths)
    overrides = tmp_path / "overrides.yaml"
    local_config = tmp_path / "local.yaml"
    overrides.write_text(
        """
replacements:
  - from: "NASA"
    to: "美国国家航空航天局"
""",
        encoding="utf-8",
    )
    local_config.write_text(
        f"""
overrides:
  path: "{overrides}"
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "babelecho",
            "overrides",
            "--workspace",
            str(workspace),
            "--run-id",
            "override-cli-run",
            "--local-config",
            str(local_config),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    script = read_json(run_paths.chinese_script_json)

    assert result.returncode == 0, result.stderr
    assert "overrides: 1 replacements from 1 rules" in result.stdout
    assert script["segments"][0]["text"] == "美国国家航空航天局 Crew-9 采访 Nick Hague。"
