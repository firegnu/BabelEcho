from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from .jsonio import write_json
from .paths import RunPaths


TRANSCRIPT_EXTENSIONS = {
    ".vtt": "raw.vtt",
    ".srt": "raw.srt",
    ".txt": "raw.txt",
    ".json": "raw.json",
    ".html": "raw.html",
    ".htm": "raw.html",
}


def _target_name(transcript_url: str) -> str:
    suffix = Path(urlparse(transcript_url).path).suffix.lower()
    return TRANSCRIPT_EXTENSIONS.get(suffix, "raw.txt")


def _read_source(transcript_url: str) -> bytes:
    parsed = urlparse(transcript_url)
    if parsed.scheme in {"http", "https"}:
        with urlopen(transcript_url, timeout=30) as response:
            return response.read()
    return Path(transcript_url).read_bytes()


def ingest_transcript_source(source_config: dict, run_paths: RunPaths) -> Path:
    if source_config.get("type") != "transcript_url":
        raise ValueError("MVP-0 supports only source.type=transcript_url")
    transcript_url = source_config.get("transcript_url")
    if not transcript_url:
        raise ValueError("source.transcript_url is required")

    raw_path = run_paths.transcript_dir / _target_name(transcript_url)
    raw_path.write_bytes(_read_source(transcript_url))

    write_json(
        run_paths.source_json,
        {
            "run_id": run_paths.run_id,
            "source_type": "transcript_url",
            "title": source_config.get("title", "Untitled Episode"),
            "original_url": source_config.get("original_url"),
            "transcript_url": transcript_url,
            "raw_transcript": str(raw_path.relative_to(run_paths.run_dir)),
        },
    )
    return raw_path
