from urllib.parse import parse_qs, urlparse

import pytest

from babelecho.itunes import (
    build_itunes_lookup_url,
    build_itunes_search_url,
    build_podcast_rss_source_config,
    parse_itunes_podcast_results,
    parse_apple_podcast_collection_id,
)


def test_build_itunes_search_url_for_podcasts():
    url = build_itunes_search_url(
        {
            "api_base_url": "http://127.0.0.1:9999/search",
            "query": "99 percent invisible",
            "country": "US",
            "max": 5,
        }
    )

    parsed = urlparse(url)
    assert parsed.geturl().startswith("http://127.0.0.1:9999/search")
    assert parse_qs(parsed.query) == {
        "term": ["99 percent invisible"],
        "country": ["US"],
        "media": ["podcast"],
        "entity": ["podcast"],
        "limit": ["5"],
    }


def test_parse_apple_podcast_collection_id_from_show_or_episode_url():
    assert (
        parse_apple_podcast_collection_id(
            "https://podcasts.apple.com/us/podcast/99-invisible/id394775318"
        )
        == "394775318"
    )
    assert (
        parse_apple_podcast_collection_id(
            "https://podcasts.apple.com/us/podcast/99-invisible/id394775318?i=1000651234567"
        )
        == "394775318"
    )


def test_build_itunes_lookup_url_for_apple_podcast_url():
    url = build_itunes_lookup_url(
        {
            "api_base_url": "http://127.0.0.1:9999/lookup",
            "url": "https://podcasts.apple.com/us/podcast/99-invisible/id394775318",
            "country": "US",
        }
    )

    parsed = urlparse(url)
    assert parsed.geturl().startswith("http://127.0.0.1:9999/lookup")
    assert parse_qs(parsed.query) == {
        "id": ["394775318"],
        "country": ["US"],
        "entity": ["podcast"],
    }


def test_parse_itunes_results_keeps_only_podcasts_with_feed_url():
    results = parse_itunes_podcast_results(
        {
            "results": [
                {
                    "wrapperType": "track",
                    "kind": "podcast",
                    "collectionName": "99% Invisible",
                    "artistName": "Roman Mars",
                    "feedUrl": "https://feeds.example.com/99pi.xml",
                    "collectionViewUrl": "https://podcasts.apple.com/us/podcast/99pi",
                },
                {
                    "wrapperType": "track",
                    "kind": "podcast",
                    "collectionName": "Missing Feed",
                },
                {
                    "wrapperType": "track",
                    "kind": "song",
                    "collectionName": "Not Podcast",
                    "feedUrl": "https://example.com/not-podcast.xml",
                },
            ]
        }
    )

    assert results == [
        {
            "title": "99% Invisible",
            "artist": "Roman Mars",
            "feed_url": "https://feeds.example.com/99pi.xml",
            "apple_url": "https://podcasts.apple.com/us/podcast/99pi",
        }
    ]


def test_parse_itunes_results_reports_no_podcast_feeds():
    with pytest.raises(ValueError, match="No podcast feeds found"):
        parse_itunes_podcast_results({"results": [{"kind": "song"}]})


def test_build_podcast_rss_source_config_from_itunes_result():
    source_config = build_podcast_rss_source_config(
        {
            "title": "99% Invisible",
            "artist": "Roman Mars",
            "feed_url": "https://feeds.example.com/99pi.xml",
            "apple_url": "https://podcasts.apple.com/us/podcast/99pi",
        }
    )

    assert source_config == {
        "source": {
            "type": "podcast_rss",
            "feed_url": "https://feeds.example.com/99pi.xml",
            "title": "99% Invisible",
            "original_url": "https://podcasts.apple.com/us/podcast/99pi",
        }
    }
