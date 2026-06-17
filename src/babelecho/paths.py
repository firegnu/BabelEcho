from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    workspace: Path
    run_id: str
    run_dir: Path
    transcript_dir: Path
    script_dir: Path
    segments_dir: Path
    output_dir: Path
    publish_dir: Path

    @property
    def source_json(self) -> Path:
        return self.run_dir / "source.json"

    @property
    def run_json(self) -> Path:
        return self.run_dir / "run.json"

    @property
    def normalized_transcript_json(self) -> Path:
        return self.transcript_dir / "normalized.json"

    @property
    def chinese_script_json(self) -> Path:
        return self.script_dir / "zh.json"

    @property
    def output_audio(self) -> Path:
        return self.output_dir / "audio.mp3"


def create_run(workspace: str | Path, run_id: str) -> RunPaths:
    root = Path(workspace)
    run_dir = root / "runs" / run_id
    paths = RunPaths(
        workspace=root,
        run_id=run_id,
        run_dir=run_dir,
        transcript_dir=run_dir / "transcript",
        script_dir=run_dir / "script",
        segments_dir=run_dir / "segments",
        output_dir=run_dir / "output",
        publish_dir=run_dir / "publish",
    )
    for directory in [
        paths.transcript_dir,
        paths.script_dir,
        paths.segments_dir,
        paths.output_dir,
        paths.publish_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    return paths
