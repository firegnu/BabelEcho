from pathlib import Path

from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run
from babelecho.synthesize import synthesize_segments


def test_synthesize_segments_with_fixture_tts(tmp_path: Path):
    run_paths = create_run(tmp_path, "tts-run")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "tts-run",
            "language": "zh-CN",
            "segments": [
                {
                    "id": "0001",
                    "source_segment_ids": ["0001"],
                    "speaker": None,
                    "text": "中文口播：欢迎。",
                }
            ],
        },
    )

    manifest_path = synthesize_segments(run_paths, {"provider": "fixture"})
    manifest = read_json(manifest_path)

    audio_path = run_paths.run_dir / manifest["segments"][0]["audio_path"]
    assert audio_path.exists()
    assert audio_path.suffix == ".wav"
