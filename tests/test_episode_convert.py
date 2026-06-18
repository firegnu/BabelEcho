from pathlib import Path

import pytest

from babelecho.episode_convert import build_on_demand_source_config


def test_build_on_demand_source_config_uses_youtube_captions_for_youtube_url():
    source_config = build_on_demand_source_config(
        "https://www.youtube.com/watch?v=abc123",
        title="Neural Networks",
        language="en",
    )

    assert source_config == {
        "source": {
            "type": "youtube_captions",
            "url": "https://www.youtube.com/watch?v=abc123",
            "language": "en",
            "title": "Neural Networks",
            "original_url": "https://www.youtube.com/watch?v=abc123",
        }
    }


def test_build_on_demand_source_config_uses_episode_page_for_http_url():
    source_config = build_on_demand_source_config(
        "https://example.com/podcast/episode-42",
        title=None,
        language="en",
    )

    assert source_config == {
        "source": {
            "type": "episode_page",
            "page_url": "https://example.com/podcast/episode-42",
            "original_url": "https://example.com/podcast/episode-42",
        }
    }


def test_build_on_demand_source_config_accepts_local_episode_page(tmp_path: Path):
    page = tmp_path / "episode.html"
    page.write_text("<html><body>Transcript</body></html>", encoding="utf-8")

    source_config = build_on_demand_source_config(str(page), title="Local Episode")

    assert source_config == {
        "source": {
            "type": "episode_page",
            "page_url": str(page),
            "title": "Local Episode",
            "original_url": str(page),
        }
    }


def test_build_on_demand_source_config_rejects_unknown_input():
    with pytest.raises(ValueError, match="Unsupported episode input"):
        build_on_demand_source_config("not a url")
