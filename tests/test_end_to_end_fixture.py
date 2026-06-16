import subprocess
import sys
from pathlib import Path


def test_end_to_end_fixture_pipeline(tmp_path: Path):
    workspace = tmp_path / "workspace"
    source_config = tmp_path / "source.yaml"
    local_config = tmp_path / "local.yaml"
    transcript = Path("tests/fixtures/sample.vtt").resolve()
    source_config.write_text(
        f"""
source:
  type: transcript_url
  transcript_url: "{transcript}"
  title: "Sample Episode"
  original_url: "https://example.com/sample"
""",
        encoding="utf-8",
    )
    local_config.write_text(
        """
llm:
  provider: fixture
tts:
  provider: fixture
publish:
  base_url: "https://example.com/babelecho"
""",
        encoding="utf-8",
    )

    commands = [
        ["ingest", "--source-config", str(source_config)],
        [
            "normalize",
            "--raw-transcript",
            str(workspace / "runs" / "demo" / "transcript" / "raw.vtt"),
        ],
        ["adapt", "--local-config", str(local_config)],
        ["synthesize", "--local-config", str(local_config)],
    ]
    for command in commands:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "babelecho",
                command[0],
                "--workspace",
                str(workspace),
                "--run-id",
                "demo",
                *command[1:],
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert (workspace / "runs" / "demo" / "script" / "zh.json").exists()
    assert (workspace / "runs" / "demo" / "segments" / "0001.wav").exists()
