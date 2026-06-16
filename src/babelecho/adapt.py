from .jsonio import read_json, write_json
from .llm import build_llm_client
from .paths import RunPaths


def adapt_to_chinese(run_paths: RunPaths, llm_config: dict) -> str:
    transcript = read_json(run_paths.normalized_transcript_json)
    client = build_llm_client(llm_config)
    segments = []
    for segment in transcript["segments"]:
        text = client.adapt_segment(segment["text"])
        segments.append(
            {
                "id": segment["id"],
                "source_segment_ids": [segment["id"]],
                "speaker": segment.get("speaker"),
                "text": text,
            }
        )
    script = {
        "episode_id": transcript["episode_id"],
        "language": "zh-CN",
        "segments": segments,
    }
    write_json(run_paths.chinese_script_json, script)
    return str(run_paths.chinese_script_json)
