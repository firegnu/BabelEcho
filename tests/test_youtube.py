from pathlib import Path

import pytest

from babelecho.youtube import fetch_youtube_captions


def write_fake_yt_dlp(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake-yt-dlp"
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return script


def test_fetch_youtube_captions_runs_skip_download_and_returns_vtt(tmp_path: Path):
    args_path = tmp_path / "args.txt"
    fake_yt_dlp = write_fake_yt_dlp(
        tmp_path,
        f"""#!/bin/sh
printf '%s\\n' "$@" > "{args_path}"
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
file="${{out%\\.%(ext)s}}.en.vtt"
cat > "$file" <<'VTT'
WEBVTT

00:00:00.000 --> 00:00:02.000
Welcome to this YouTube episode.
VTT
""",
    )

    captions = fetch_youtube_captions(
        {
            "url": "https://www.youtube.com/watch?v=example",
            "language": "en",
            "yt_dlp_command": str(fake_yt_dlp),
        },
        tmp_path / "captions",
    )

    assert captions.path.name == "captions.en.vtt"
    assert captions.language == "en"
    assert captions.path.read_text(encoding="utf-8").startswith("WEBVTT")
    args = args_path.read_text(encoding="utf-8")
    assert "--skip-download" in args
    assert "--write-subs" in args
    assert "--write-auto-subs" in args
    assert "https://www.youtube.com/watch?v=example" in args


def test_fetch_youtube_captions_reads_printed_title(tmp_path: Path):
    fake_yt_dlp = write_fake_yt_dlp(
        tmp_path,
        """#!/bin/sh
for arg in "$@"; do
  if [ "$arg" = "--print" ]; then
    printf '%s\\n' 'Fixture YouTube Title'
    exit 0
  fi
done
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
file="${out%\\.%(ext)s}.en.vtt"
cat > "$file" <<'VTT'
WEBVTT

00:00:00.000 --> 00:00:02.000
Welcome to this YouTube episode.
VTT
""",
    )

    captions = fetch_youtube_captions(
        {
            "url": "https://www.youtube.com/watch?v=example",
            "yt_dlp_command": str(fake_yt_dlp),
        },
        tmp_path / "captions",
    )

    assert captions.title == "Fixture YouTube Title"


def test_fetch_youtube_captions_reports_missing_subtitle(tmp_path: Path):
    fake_yt_dlp = write_fake_yt_dlp(
        tmp_path,
        """#!/bin/sh
exit 0
""",
    )

    with pytest.raises(ValueError, match="No YouTube subtitles downloaded"):
        fetch_youtube_captions(
            {
                "url": "https://www.youtube.com/watch?v=example",
                "yt_dlp_command": str(fake_yt_dlp),
            },
            tmp_path / "captions",
        )
