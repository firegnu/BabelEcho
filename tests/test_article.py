from pathlib import Path

from babelecho.article import (
    ArticleExtraction,
    extract_article_file,
    extract_web_article,
    ingest_article_source,
    normalize_article,
    prepare_article_tts_script,
    prepare_article_tts_text,
)
from babelecho.jsonio import read_json
from babelecho.jsonio import write_json
from babelecho.paths import create_run


def test_extract_article_file_strips_front_matter_and_duplicate_title(tmp_path: Path):
    article = tmp_path / "essay.md"
    article.write_text(
        """---
title: Ignored Front Matter Title
author: Example Author
---

# A Careful Essay

A Careful Essay

This is the first meaningful paragraph.

- First point
- Second point
""",
        encoding="utf-8",
    )

    extracted = extract_article_file(article, title="A Careful Essay")

    assert extracted == ArticleExtraction(
        source_type="article_file",
        provider="local_file",
        title="A Careful Essay",
        text="This is the first meaningful paragraph.\n\nFirst point\nSecond point",
        metadata={},
    )


def test_extract_web_article_uses_injected_extractor():
    html = "<html><head><title>Ignored</title></head><body><article>body</article></body></html>"

    def fetch_html(url: str) -> str:
        assert url == "https://example.com/post"
        return html

    def extractor(downloaded: str) -> dict:
        assert downloaded == html
        return {
            "title": "Agentic Coding",
            "text": "The article body.\n\nThe second paragraph.",
            "author": "Jane Doe",
            "site_name": "Example Blog",
            "published_time": "2026-06-19",
            "excerpt": "A short summary.",
        }

    extracted = extract_web_article(
        "https://example.com/post",
        fetch_html=fetch_html,
        extractor=extractor,
    )

    assert extracted.source_type == "web_article"
    assert extracted.provider == "trafilatura"
    assert extracted.title == "Agentic Coding"
    assert extracted.text == "The article body.\n\nThe second paragraph."
    assert extracted.metadata == {
        "input_url": "https://example.com/post",
        "author": "Jane Doe",
        "site_name": "Example Blog",
        "published_time": "2026-06-19",
        "excerpt": "A short summary.",
    }


def test_extract_web_article_falls_back_to_basic_html_text():
    extracted = extract_web_article(
        "https://example.com/fallback",
        fetch_html=lambda _url: """
        <html>
          <head><title>Fallback Title</title><script>bad()</script></head>
          <body>
            <nav>Navigation</nav>
            <article>
              <h1>Fallback Title</h1>
              <p>Main paragraph.</p>
              <p>Second paragraph.</p>
            </article>
          </body>
        </html>
        """,
        extractor=lambda _html: None,
    )

    assert extracted.title == "Fallback Title"
    assert extracted.text == "Fallback Title\n\nMain paragraph.\n\nSecond paragraph."


def test_ingest_article_file_writes_article_artifacts_without_local_path_leak(
    tmp_path: Path,
):
    article = tmp_path / "private-input.md"
    article.write_text(
        """# Private Article

Private Article

This paragraph is long enough to be useful.
""",
        encoding="utf-8",
    )
    run_paths = create_run(tmp_path / "workspace", "article-file-ingest")

    raw_path = ingest_article_source(
        {
            "type": "article_file",
            "article_file": str(article),
            "title": "Private Article",
        },
        run_paths,
    )

    assert raw_path == run_paths.transcript_dir / "raw.txt"
    assert raw_path.read_text(encoding="utf-8") == "This paragraph is long enough to be useful."
    assert (run_paths.run_dir / "article" / "raw.txt").read_text(
        encoding="utf-8"
    ) == "This paragraph is long enough to be useful."
    extracted = read_json(run_paths.run_dir / "article" / "extracted.json")
    assert extracted["source_type"] == "article_file"
    assert extracted["provider"] == "local_file"
    source = read_json(run_paths.source_json)
    assert source["source_type"] == "article_file"
    assert source["provider"] == "local_file"
    assert source["title"] == "Private Article"
    assert source["raw_transcript"] == "transcript/raw.txt"
    assert str(article) not in run_paths.source_json.read_text(encoding="utf-8")


def test_ingest_web_article_writes_public_metadata(monkeypatch, tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "web-article-ingest")

    monkeypatch.setattr(
        "babelecho.article.extract_web_article",
        lambda url: ArticleExtraction(
            source_type="web_article",
            provider="trafilatura",
            title="Public Article",
            text="First paragraph.\n\nSecond paragraph.",
            metadata={
                "input_url": url,
                "author": "Jane Doe",
                "site_name": "Example Blog",
                "published_time": "2026-06-19",
                "excerpt": "Short excerpt.",
            },
        ),
        raising=False,
    )

    raw_path = ingest_article_source(
        {
            "type": "web_article",
            "url": "https://example.com/public-article",
        },
        run_paths,
    )

    assert raw_path == run_paths.transcript_dir / "raw.txt"
    assert raw_path.read_text(encoding="utf-8") == "First paragraph.\n\nSecond paragraph."
    extracted = read_json(run_paths.run_dir / "article" / "extracted.json")
    assert extracted["metadata"]["site_name"] == "Example Blog"
    source = read_json(run_paths.source_json)
    assert source["source_type"] == "web_article"
    assert source["provider"] == "trafilatura"
    assert source["title"] == "Public Article"
    assert source["input_url"] == "https://example.com/public-article"
    assert source["author"] == "Jane Doe"
    assert source["site_name"] == "Example Blog"
    assert source["published_time"] == "2026-06-19"


def test_normalize_article_has_no_speaker_and_does_not_infer_speaker_labels(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "article-normalize")
    write_json(
        run_paths.source_json,
        {
            "run_id": "article-normalize",
            "source_type": "article_file",
            "provider": "local_file",
            "title": "Article Normalize",
            "raw_transcript": "transcript/raw.txt",
        },
    )
    raw_path = run_paths.transcript_dir / "raw.txt"
    raw_path.write_text(
        "Important: this is part of the article, not a speaker label.\n\n"
        "The second paragraph remains plain article text.",
        encoding="utf-8",
    )

    normalize_article(run_paths, raw_path)

    normalized = read_json(run_paths.normalized_transcript_json)
    assert normalized["segments"] == [
        {
            "id": "0001",
            "start_ms": None,
            "end_ms": None,
            "speaker": None,
            "text": "Important: this is part of the article, not a speaker label.",
            "source": "article",
        },
        {
            "id": "0002",
            "start_ms": None,
            "end_ms": None,
            "speaker": None,
            "text": "The second paragraph remains plain article text.",
            "source": "article",
        },
    ]
    quality = read_json(run_paths.transcript_quality_json)
    assert quality["metrics"]["source_type"] == "article_file"
    assert quality["metrics"]["extractor"] == "local_file"


def test_normalize_article_cleans_technical_markup_before_quality_check(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "article-technical-markup")
    write_json(
        run_paths.source_json,
        {
            "run_id": "article-technical-markup",
            "source_type": "web_article",
            "provider": "trafilatura",
            "title": "Technical Article",
            "raw_transcript": "transcript/raw.txt",
        },
    )
    raw_path = run_paths.transcript_dir / "raw.txt"
    raw_path.write_text(
        "Teams often organize prompts with <background_information> and "
        "</instructions> sections so the agent has a predictable frame of "
        "reference. The names are meaningful article content, but the angle "
        "brackets are markup-like noise for the transcript quality gate and "
        "for a Chinese reading workflow.\n\n"
        "TOOL CALL: salesforce.updateRecord({ data: { Notes: \"Discussed Q4 "
        "goals and follow-up actions with the customer success lead.\" } })Copy\n\n"
        "The surrounding explanation remains useful. It describes why an "
        "example may ask a model to write a full transcript into context, why "
        "that can be expensive, and how the workflow should keep the article "
        "faithful without reading interface labels as part of the narrative.",
        encoding="utf-8",
    )

    normalize_article(run_paths, raw_path)

    normalized = read_json(run_paths.normalized_transcript_json)
    joined_text = "\n".join(segment["text"] for segment in normalized["segments"])
    assert "<background_information>" not in joined_text
    assert "</instructions>" not in joined_text
    assert "background_information" in joined_text
    assert "instructions" in joined_text
    assert "})Copy" not in joined_text
    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert quality["metrics"]["dirty_markup_count"] == 0


def test_prepare_article_tts_text_normalizes_technical_reading():
    prepared = prepare_article_tts_text(
        "GPT-5.3-Codex used Prompt.md with SWE-bench, Terminal-Bench 2.0, "
        "p<0.01, OOM, API, and MCP logs."
    )

    assert "G P T 5 点 3 Codex" in prepared
    assert "Prompt M D" in prepared
    assert "S W E Bench" in prepared
    assert "Terminal Bench 2.0" in prepared
    assert "p 值小于 0.01" in prepared
    assert "O O M" in prepared
    assert "A P I" in prepared
    assert "M C P" in prepared
    assert "GPT-" not in prepared
    assert ".md" not in prepared


def test_prepare_article_tts_script_preserves_no_speaker_article_segments(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "article-tts-script")
    write_json(
        run_paths.chinese_script_json,
        {
            "episode_id": "article-tts-script",
            "language": "zh",
            "segments": [
                {
                    "id": "0001",
                    "speaker": None,
                    "text": "GPT-5-Codex 读取 Prompt.md 后报告 p<0.01。",
                }
            ],
        },
    )

    prepare_article_tts_script(run_paths)

    script = read_json(run_paths.chinese_script_json)
    segment = script["segments"][0]
    assert segment["speaker"] is None
    assert segment["text"] == "G P T 5 Codex 读取 Prompt M D 后报告 p 值小于 0.01。"
