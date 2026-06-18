import subprocess
import re

from .jsonio import read_json
from .paths import RunPaths


class CheckError(ValueError):
    pass


TRANSCRIPT_ARTIFACT_PATTERNS = (
    re.compile(r">>"),
    re.compile(r"\bWEBVTT\b", re.IGNORECASE),
    re.compile(r"</?c(?:\.[^>]*)?>", re.IGNORECASE),
    re.compile(r"&(?:nbsp|amp|lt|gt|quot);", re.IGNORECASE),
    re.compile(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[,.]\d{3}"),
    re.compile(r"```"),
)
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ENGLISH_NAME_PART_RE = (
    r"(?:[A-Z][A-Za-z'.-]*|[A-Z][a-z]+[A-Z][A-Za-z'.-]*)"
)
ENGLISH_PROPER_NOUN_SEQUENCE_RE = re.compile(
    rf"\b{ENGLISH_NAME_PART_RE}(?:\s+{ENGLISH_NAME_PART_RE}){{1,4}}\b"
)
URL_RE = re.compile(
    r"(?:https?://)?[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
    r"(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?"
)


def _ascii_letter_ratio(text: str) -> float:
    non_space_count = len("".join(text.split()))
    if non_space_count == 0:
        return 0.0
    return len(ASCII_LETTER_RE.findall(text)) / non_space_count


def _text_for_english_heavy_check(text: str) -> str:
    without_urls = URL_RE.sub("", text)
    if not CJK_RE.search(without_urls):
        return without_urls
    return ENGLISH_PROPER_NOUN_SEQUENCE_RE.sub("", without_urls)


def _check_script_text_quality(segment_id: str, text: str) -> None:
    if any(pattern.search(text) for pattern in TRANSCRIPT_ARTIFACT_PATTERNS):
        raise CheckError(f"Script segment {segment_id} contains transcript artifact")
    text_for_english_check = _text_for_english_heavy_check(text)
    ascii_letters = len(ASCII_LETTER_RE.findall(text_for_english_check))
    if ascii_letters >= 60 and _ascii_letter_ratio(text_for_english_check) >= 0.35:
        raise CheckError(f"Script segment {segment_id} is English-heavy")


def _check_script(run_paths: RunPaths, max_script_chars: int) -> dict:
    if not run_paths.chinese_script_json.exists():
        raise CheckError(f"Missing script: {run_paths.chinese_script_json}")
    script = read_json(run_paths.chinese_script_json)
    segments = script.get("segments", [])
    if not segments:
        raise CheckError(f"No script segments in {run_paths.chinese_script_json}")
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        segment_id = segment.get("id", "<unknown>")
        if not text:
            raise CheckError(f"Script segment {segment_id} has empty text")
        if len(text) > max_script_chars:
            raise CheckError(
                f"Script segment {segment_id} is too long: "
                f"{len(text)} > {max_script_chars}"
            )
        _check_script_text_quality(str(segment_id), text)
    return {"script_segments": len(segments)}


def _check_segments(run_paths: RunPaths) -> dict:
    manifest_path = run_paths.segments_dir / "manifest.json"
    if not manifest_path.exists():
        raise CheckError(f"Missing segment manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    segments = manifest.get("segments", [])
    if not segments:
        raise CheckError(f"No audio segments in {run_paths.segments_dir / 'manifest.json'}")
    for segment in segments:
        audio_path = run_paths.run_dir / segment["audio_path"]
        if not audio_path.exists():
            raise CheckError(f"Missing audio segment: {audio_path}")
        if audio_path.stat().st_size == 0:
            raise CheckError(f"Empty audio segment: {audio_path}")
    return {"audio_segments": len(segments)}


def _check_output(run_paths: RunPaths) -> dict:
    if not run_paths.output_audio.exists():
        raise CheckError(f"Missing output audio: {run_paths.output_audio}")
    if run_paths.output_audio.stat().st_size == 0:
        raise CheckError(f"Empty output audio: {run_paths.output_audio}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_name,sample_rate,channels",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(run_paths.output_audio),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise CheckError(f"ffprobe failed for {run_paths.output_audio}: {error}") from error

    lines = completed.stdout.strip().splitlines()
    if len(lines) < 4:
        raise CheckError(f"Unexpected ffprobe output for {run_paths.output_audio}")
    codec, sample_rate, channels, duration = lines[:4]
    if codec != "mp3":
        raise CheckError(f"Unexpected output codec: {codec}")
    return {
        "output_sample_rate": int(sample_rate),
        "output_channels": int(channels),
        "output_duration_seconds": float(duration),
    }


def check_run_artifacts(
    run_paths: RunPaths,
    checks: tuple[str, ...] = ("script", "segments"),
    max_script_chars: int = 1200,
) -> dict:
    result: dict[str, int] = {}
    if "script" in checks:
        result.update(_check_script(run_paths, max_script_chars))
    if "segments" in checks:
        result.update(_check_segments(run_paths))
    if "output" in checks:
        result.update(_check_output(run_paths))
    return result
