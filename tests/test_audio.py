from pathlib import Path
from unittest.mock import patch

from babelecho.audio import assemble_audio
from babelecho.jsonio import write_json
from babelecho.paths import create_run
from babelecho.tts import write_silent_wav


def test_assemble_audio_writes_absolute_concat_paths_for_relative_workspace(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    run_paths = create_run(Path("workspace"), "audio-run")
    first = run_paths.segments_dir / "0001.wav"
    second = run_paths.segments_dir / "0002.wav"
    write_silent_wav(first)
    write_silent_wav(second)
    write_json(
        run_paths.segments_dir / "manifest.json",
        {
            "episode_id": "audio-run",
            "segments": [
                {"id": "0001", "audio_path": "segments/0001.wav", "text": "一"},
                {"id": "0002", "audio_path": "segments/0002.wav", "text": "二"},
            ],
        },
    )

    with patch("subprocess.run") as run:
        output = assemble_audio(run_paths, {"format": "mp3"})

    concat_list = run_paths.output_dir / "concat.txt"
    assert concat_list.exists()
    assert concat_list.read_text(encoding="utf-8") == (
        f"file '{first.resolve()}'\n"
        f"file '{second.resolve()}'\n"
    )
    assert output == str(run_paths.output_audio)
    run.assert_called_once()
