from pathlib import Path
from unittest.mock import patch

from babelecho.audio import assemble_audio
from babelecho.jsonio import write_json
from babelecho.paths import create_run
from babelecho.tts import write_silent_wav


def test_assemble_audio_writes_concat_list_and_invokes_ffmpeg(tmp_path: Path):
    run_paths = create_run(tmp_path, "audio-run")
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
    assert "segments/0001.wav" in concat_list.read_text(encoding="utf-8")
    assert output == str(run_paths.output_audio)
    run.assert_called_once()
