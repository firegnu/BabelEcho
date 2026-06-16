import subprocess
import sys


def test_module_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "babelecho", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "BabelEcho backend pipeline" in result.stdout
