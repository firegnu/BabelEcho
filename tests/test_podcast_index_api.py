from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from babelecho.podcast_index_api import (
    PodcastIndexCredentials,
    build_auth_headers,
    build_podcast_index_url,
    load_podcast_index_credentials,
    select_podcast_index_episode,
)


def test_build_auth_headers_uses_sha1_token():
    headers = build_auth_headers(
        PodcastIndexCredentials(
            api_key="key",
            api_secret="secret",
            user_agent="BabelEchoTest/0.1",
        ),
        unix_time=1234567890,
    )

    assert headers == {
        "User-Agent": "BabelEchoTest/0.1",
        "X-Auth-Date": "1234567890",
        "X-Auth-Key": "key",
        "Authorization": "81ec4213960f3944b4043c34bb15ed73f7279322",
    }


def test_load_credentials_from_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PODCASTINDEX_API_KEY", "env-key")
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "env-secret")

    credentials = load_podcast_index_credentials(
        {
            "api_key_env": "PODCASTINDEX_API_KEY",
            "api_secret_env": "PODCASTINDEX_API_SECRET",
            "user_agent": "BabelEchoEnv/0.1",
        }
    )

    assert credentials == PodcastIndexCredentials(
        api_key="env-key",
        api_secret="env-secret",
        user_agent="BabelEchoEnv/0.1",
    )


def test_load_credentials_from_file(tmp_path: Path):
    credentials_file = tmp_path / "podcastindex.env"
    credentials_file.write_text(
        """
PODCASTINDEX_API_KEY=file-key
PODCASTINDEX_API_SECRET=file-secret
PODCASTINDEX_USER_AGENT=BabelEchoFile/0.1
""",
        encoding="utf-8",
    )

    credentials = load_podcast_index_credentials(
        {
            "credentials_file": str(credentials_file),
        }
    )

    assert credentials == PodcastIndexCredentials(
        api_key="file-key",
        api_secret="file-secret",
        user_agent="BabelEchoFile/0.1",
    )


def test_load_credentials_reports_missing_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PODCASTINDEX_API_KEY", raising=False)
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "env-secret")

    with pytest.raises(ValueError, match="PODCASTINDEX_API_KEY"):
        load_podcast_index_credentials(
            {
                "api_key_env": "PODCASTINDEX_API_KEY",
                "api_secret_env": "PODCASTINDEX_API_SECRET",
            }
        )


def test_load_credentials_rejects_file_and_environment(tmp_path: Path):
    credentials_file = tmp_path / "podcastindex.env"
    credentials_file.write_text(
        """
PODCASTINDEX_API_KEY=file-key
PODCASTINDEX_API_SECRET=file-secret
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="credentials_file"):
        load_podcast_index_credentials(
            {
                "credentials_file": str(credentials_file),
                "api_key_env": "PODCASTINDEX_API_KEY",
                "api_secret_env": "PODCASTINDEX_API_SECRET",
            }
        )


def test_build_url_for_episode_by_id():
    url = build_podcast_index_url(
        {
            "endpoint": "episodes/byid",
            "episode_id": 42,
        }
    )

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "api.podcastindex.org"
    assert parsed.path == "/api/1.0/episodes/byid"
    assert parse_qs(parsed.query) == {"id": ["42"], "fulltext": ["true"]}


def test_build_url_for_episodes_by_feed_id():
    url = build_podcast_index_url(
        {
            "api_base_url": "http://127.0.0.1:9999/api/1.0",
            "endpoint": "episodes/byfeedid",
            "feed_id": 75075,
            "max_episodes": 3,
        }
    )

    parsed = urlparse(url)
    assert parsed.geturl().startswith(
        "http://127.0.0.1:9999/api/1.0/episodes/byfeedid"
    )
    assert parse_qs(parsed.query) == {
        "id": ["75075"],
        "max": ["3"],
        "fulltext": ["true"],
    }


def test_build_url_for_episodes_by_feed_url():
    url = build_podcast_index_url(
        {
            "endpoint": "episodes/byfeedurl",
            "feed_url": "https://feeds.example.com/show.xml",
        }
    )

    parsed = urlparse(url)
    assert parsed.path == "/api/1.0/episodes/byfeedurl"
    assert parse_qs(parsed.query) == {
        "url": ["https://feeds.example.com/show.xml"],
        "fulltext": ["true"],
    }


def test_build_url_for_episodes_by_itunes_id():
    url = build_podcast_index_url(
        {
            "endpoint": "episodes/byitunesid",
            "itunes_id": 1441923632,
            "max_episodes": 5,
        }
    )

    parsed = urlparse(url)
    assert parsed.path == "/api/1.0/episodes/byitunesid"
    assert parse_qs(parsed.query) == {
        "id": ["1441923632"],
        "max": ["5"],
        "fulltext": ["true"],
    }


def test_build_url_requires_endpoint_specific_id():
    with pytest.raises(ValueError, match="source.episode_id is required"):
        build_podcast_index_url({"endpoint": "episodes/byid"})


def test_select_episode_object_response():
    episode = {
        "title": "Single Episode",
        "link": "https://example.com/single",
    }

    assert select_podcast_index_episode({"episode": episode}, None) == episode


def test_select_episode_from_items_by_episode_url():
    target = {
        "title": "Target Episode",
        "guid": "episode-guid",
        "transcripts": [{"url": "https://example.com/transcript.txt"}],
    }
    payload = {
        "items": [
            {"title": "Other Episode", "link": "https://example.com/other"},
            target,
        ]
    }

    assert select_podcast_index_episode(payload, "episode-guid") == target


def test_select_episode_reports_missing_match():
    with pytest.raises(ValueError, match="Episode not found"):
        select_podcast_index_episode(
            {
                "items": [
                    {
                        "title": "Other Episode",
                        "link": "https://example.com/other",
                    }
                ]
            },
            "https://example.com/missing",
        )
