from .jsonio import read_json
from .paths import RunPaths


def preview_chinese_script(run_paths: RunPaths) -> str:
    script = read_json(run_paths.chinese_script_json)
    segments = script.get("segments") or []
    if not segments:
        raise ValueError(f"No script segments found in {run_paths.chinese_script_json}")

    lines = [
        f"script: {run_paths.chinese_script_json}",
        f"edit: {run_paths.chinese_script_json}",
        (
            "resume: babelecho run "
            f"--workspace {run_paths.workspace} "
            f"--run-id {run_paths.run_id} "
            "--from-stage synthesize ..."
        ),
        "",
    ]
    for index, segment in enumerate(segments):
        if index:
            lines.append("")
        segment_id = segment.get("id", f"{index + 1:04d}")
        speaker = segment.get("speaker")
        heading = f"{segment_id} [{speaker}]" if speaker else str(segment_id)
        lines.append(heading)
        lines.append(segment.get("text", ""))
    return "\n".join(lines)
