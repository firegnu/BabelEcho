from pathlib import Path

import pytest

from babelecho.audio_source import ingest_audio_source
from babelecho.jsonio import read_json
from babelecho.paths import create_run


def test_ingest_audio_file_writes_public_artifacts_without_local_path_leak(
    tmp_path: Path,
):
    audio = tmp_path / "private-input.mp3"
    audio.write_bytes(b"fixture audio bytes")
    run_paths = create_run(tmp_path / "workspace", "audio-file-ingest")

    audio_path = ingest_audio_source(
        {
            "type": "audio_file",
            "audio_file": str(audio),
            "title": "Private Audio",
        },
        run_paths,
    )

    assert audio_path == run_paths.run_dir / "audio" / "input.mp3"
    assert audio_path.read_bytes() == b"fixture audio bytes"
    source = read_json(run_paths.source_json)
    assert source == {
        "run_id": "audio-file-ingest",
        "source_type": "audio_file",
        "provider": "local_file",
        "title": "Private Audio",
        "audio_input": "audio/input.mp3",
        "audio_metadata": "audio/metadata.json",
    }
    metadata = read_json(run_paths.run_dir / "audio" / "metadata.json")
    assert metadata["input_kind"] == "audio_file"
    assert metadata["original_filename"] == "private-input.mp3"
    assert metadata["audio_path"] == "audio/input.mp3"
    assert metadata["file_size_bytes"] == len(b"fixture audio bytes")
    assert metadata["duration_seconds"] is None
    assert metadata["sample_rate"] is None
    assert metadata["channels"] is None
    assert "ffprobe_unavailable_or_failed" in metadata["warnings"]
    assert str(audio) not in run_paths.source_json.read_text(encoding="utf-8")
    assert str(audio) not in (run_paths.run_dir / "audio" / "metadata.json").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("missing.mp3", None, "Audio file does not exist"),
        ("empty.mp3", b"", "Audio file is empty"),
    ],
)
def test_ingest_audio_file_rejects_invalid_input(
    tmp_path: Path,
    filename: str,
    content: bytes | None,
    message: str,
):
    audio = tmp_path / filename
    if content is not None:
        audio.write_bytes(content)
    run_paths = create_run(tmp_path / "workspace", "audio-invalid")

    with pytest.raises(ValueError, match=message):
        ingest_audio_source({"type": "audio_file", "audio_file": str(audio)}, run_paths)


def test_ingest_audio_file_rejects_directory_input(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "audio-directory")

    with pytest.raises(ValueError, match="Audio input is not a file"):
        ingest_audio_source(
            {"type": "audio_file", "audio_file": str(tmp_path)},
            run_paths,
        )


def test_ingest_audio_url_downloads_without_query_leak(monkeypatch, tmp_path: Path):
    requests = []

    class FakeResponse:
        def __init__(self):
            self._sent = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size=-1):
            if self._sent:
                return b""
            self._sent = True
            return b"remote audio bytes"

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("babelecho.audio_source.urlopen", fake_urlopen)
    run_paths = create_run(tmp_path / "workspace", "audio-url-ingest")

    audio_path = ingest_audio_source(
        {
            "type": "audio_url",
            "audio_url": "https://media.example.com/private/episode.mp3?token=secret",
            "title": "Remote Audio",
        },
        run_paths,
    )

    assert audio_path == run_paths.run_dir / "audio" / "input.mp3"
    assert audio_path.read_bytes() == b"remote audio bytes"
    request, timeout = requests[0]
    assert request.full_url == "https://media.example.com/private/episode.mp3?token=secret"
    assert timeout == 60
    source = read_json(run_paths.source_json)
    assert source == {
        "run_id": "audio-url-ingest",
        "source_type": "audio_url",
        "provider": "remote_url",
        "title": "Remote Audio",
        "source_host": "media.example.com",
        "source_path": "/private/episode.mp3",
        "audio_input": "audio/input.mp3",
        "audio_metadata": "audio/metadata.json",
    }
    metadata = read_json(run_paths.run_dir / "audio" / "metadata.json")
    assert metadata["input_kind"] == "audio_url"
    assert metadata["source_host"] == "media.example.com"
    assert metadata["source_path"] == "/private/episode.mp3"
    assert metadata["original_filename"] == "episode.mp3"
    assert metadata["audio_path"] == "audio/input.mp3"
    assert metadata["file_size_bytes"] == len(b"remote audio bytes")
    assert "token=secret" not in run_paths.source_json.read_text(encoding="utf-8")
    assert "token=secret" not in (run_paths.run_dir / "audio" / "metadata.json").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("url", ["ftp://example.com/audio.mp3", "not-a-url"])
def test_ingest_audio_url_rejects_unsupported_urls(tmp_path: Path, url: str):
    run_paths = create_run(tmp_path / "workspace", "audio-url-invalid")

    with pytest.raises(ValueError, match="source.audio_url must be an http"):
        ingest_audio_source({"type": "audio_url", "audio_url": url}, run_paths)
