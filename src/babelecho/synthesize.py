from .jsonio import read_json, write_json
from .paths import RunPaths
from .tts import synthesize_many_to_wav


def synthesize_segments(run_paths: RunPaths, tts_config: dict) -> str:
    script = read_json(run_paths.chinese_script_json)
    manifest_segments = []
    tts_items = []
    for segment in script["segments"]:
        audio_path = run_paths.segments_dir / f"{segment['id']}.wav"
        tts_items.append((segment["text"], audio_path))
        manifest_segments.append(
            {
                "id": segment["id"],
                "audio_path": str(audio_path.relative_to(run_paths.run_dir)),
                "text": segment["text"],
            }
        )
    synthesize_many_to_wav(tts_items, run_paths.segments_dir / "tts-batch.json", tts_config)
    manifest = {
        "episode_id": script["episode_id"],
        "segments": manifest_segments,
    }
    manifest_path = run_paths.segments_dir / "manifest.json"
    write_json(manifest_path, manifest)
    return str(manifest_path)
