import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from .jsonio import read_json, write_json
from .paths import RunPaths
from .transcript_quality import build_transcript_quality_report


@dataclass(frozen=True)
class ArticleExtraction:
    source_type: str
    provider: str
    title: str
    text: str
    metadata: dict


FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")
TECHNICAL_TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9_-]{0,60})>")
CODE_COPY_LINE_RE = re.compile(r"(?m)^\s*Copy\s*$")
CODE_COPY_SUFFIX_RE = re.compile(r"(?<=[)}\];])Copy(?=\s*(?:\n|$))")
GPT_VERSION_RE = re.compile(
    r"\bGPT-(?P<major>\d+)(?:\.(?P<minor>\d+))?(?P<suffix>(?:-[A-Za-z][A-Za-z0-9]*)*)\b"
)
FILE_EXTENSION_RE = re.compile(
    r"\b(?P<stem>[A-Za-z][A-Za-z0-9_-]{0,80})"
    r"\.(?P<ext>md|json|py|ts|tsx|js|jsx|html|xml|yaml|yml)\b",
    re.IGNORECASE,
)
P_VALUE_RE = re.compile(r"\bp\s*<\s*(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE)
ACRONYM_RE = re.compile(
    r"\b(API|ASR|CLI|CPU|GPU|GPT|HTML|IDE|JSON|LLM|MCP|OOM|RSS|SDK|SWE|TTS|URL|XML|YAML)\b"
)

FILE_EXTENSION_SPEECH = {
    "html": "H T M L",
    "json": "J S O N",
    "js": "J S",
    "jsx": "J S X",
    "md": "M D",
    "py": "P Y",
    "ts": "T S",
    "tsx": "T S X",
    "xml": "X M L",
    "yaml": "Y A M L",
    "yml": "Y M L",
}


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self._title_depth = 0
        self._article_depth = 0
        self._body_depth = 0
        self.title_parts: list[str] = []
        self.article_parts: list[str] = []
        self.body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "aside"}:
            self._ignored_depth += 1
        if tag == "title":
            self._title_depth += 1
        if tag == "article":
            self._article_depth += 1
        if tag == "body":
            self._body_depth += 1
        if tag in {"p", "h1", "h2", "h3", "li", "blockquote", "br"}:
            self._append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "h1", "h2", "h3", "li", "blockquote"}:
            self._append("\n\n")
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "aside"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        if tag == "title":
            self._title_depth = max(0, self._title_depth - 1)
        if tag == "article":
            self._article_depth = max(0, self._article_depth - 1)
        if tag == "body":
            self._body_depth = max(0, self._body_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._title_depth:
            self.title_parts.append(data)
            return
        self._append(data)

    def _append(self, value: str) -> None:
        if self._article_depth:
            self.article_parts.append(value)
        elif self._body_depth:
            self.body_parts.append(value)


def _collapse_text(value: str) -> str:
    paragraphs = [
        "\n".join(
            " ".join(line.split())
            for line in part.splitlines()
            if line.strip()
        )
        for part in re.split(r"\n\s*\n", value)
        if part.strip()
    ]
    return "\n\n".join(paragraphs)


def _clean_article_technical_markup(value: str) -> str:
    text = TECHNICAL_TAG_RE.sub(lambda match: match.group(1), value)
    text = CODE_COPY_LINE_RE.sub("", text)
    return CODE_COPY_SUFFIX_RE.sub("", text)


def _clean_article_text(value: str, title: str | None = None) -> str:
    text = FRONT_MATTER_RE.sub("", value).strip()
    text = _clean_article_technical_markup(text)
    lines = []
    normalized_title = " ".join((title or "").split()).casefold()
    has_content = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        line = MARKDOWN_HEADING_RE.sub("", line).strip()
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        normalized_line = " ".join(line.split()).casefold()
        if normalized_title and normalized_line == normalized_title and not has_content:
            continue
        lines.append(line)
        has_content = True
    return _collapse_text("\n".join(lines))


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "BabelEcho/0.1"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _default_extractor(downloaded: str) -> dict | None:
    try:
        from trafilatura import extract
    except ImportError:
        return None
    extracted = extract(downloaded, output_format="json", with_metadata=True)
    if not extracted:
        return None
    data = json.loads(extracted)
    return {
        "title": data.get("title"),
        "text": data.get("text"),
        "author": data.get("author"),
        "site_name": data.get("sitename") or data.get("site_name"),
        "published_time": data.get("date"),
        "excerpt": data.get("description"),
    }


def _fallback_html_extraction(url: str, html: str) -> ArticleExtraction:
    parser = _ReadableHtmlParser()
    parser.feed(html)
    title = _collapse_text(" ".join(parser.title_parts)) or Path(url).stem or "Untitled Article"
    body_text = "".join(parser.article_parts or parser.body_parts)
    text = _clean_article_text(body_text, title=None)
    if not text:
        raise ValueError(f"No article text extracted from {url}")
    return ArticleExtraction(
        source_type="web_article",
        provider="trafilatura",
        title=title,
        text=text,
        metadata={"input_url": url},
    )


def extract_article_file(path: str | Path, title: str | None = None) -> ArticleExtraction:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    article_title = title or source.stem
    cleaned = _clean_article_text(text, article_title)
    if not cleaned:
        raise ValueError(f"No article text extracted from {source}")
    return ArticleExtraction(
        source_type="article_file",
        provider="local_file",
        title=article_title,
        text=cleaned,
        metadata={},
    )


def extract_web_article(
    url: str,
    *,
    fetch_html=None,
    extractor=None,
) -> ArticleExtraction:
    html = (fetch_html or _fetch_html)(url)
    extracted = (extractor or _default_extractor)(html)
    if not extracted:
        return _fallback_html_extraction(url, html)
    title = str(extracted.get("title") or Path(url).stem or "Untitled Article")
    text = _clean_article_text(str(extracted.get("text") or ""), title=None)
    if not text:
        raise ValueError(f"No article text extracted from {url}")
    metadata = {
        "input_url": url,
        "author": extracted.get("author"),
        "site_name": extracted.get("site_name"),
        "published_time": extracted.get("published_time"),
        "excerpt": extracted.get("excerpt"),
    }
    return ArticleExtraction(
        source_type="web_article",
        provider="trafilatura",
        title=title,
        text=text,
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


def ingest_article_source(source_config: dict, run_paths: RunPaths) -> Path:
    source_type = source_config.get("type")
    if source_type == "article_file":
        article_file = source_config.get("article_file")
        if not article_file:
            raise ValueError("source.article_file is required")
        extraction = extract_article_file(article_file, title=source_config.get("title"))
    elif source_type == "web_article":
        url = source_config.get("url")
        if not url:
            raise ValueError("source.url is required")
        extraction = extract_web_article(url)
    else:
        raise ValueError("article pipeline supports source.type=article_file or web_article")
    return _write_article_ingest(extraction, run_paths, source_config)


def _write_article_ingest(
    extraction: ArticleExtraction,
    run_paths: RunPaths,
    source_config: dict,
) -> Path:
    article_dir = run_paths.run_dir / "article"
    article_dir.mkdir(parents=True, exist_ok=True)
    article_raw_path = article_dir / "raw.txt"
    article_raw_path.write_text(extraction.text, encoding="utf-8")
    write_json(
        article_dir / "extracted.json",
        {
            "source_type": extraction.source_type,
            "provider": extraction.provider,
            "title": extraction.title,
            "text": extraction.text,
            "metadata": extraction.metadata,
        },
    )

    raw_path = run_paths.transcript_dir / "raw.txt"
    raw_path.write_text(extraction.text, encoding="utf-8")
    metadata = extraction.metadata
    source_payload = {
        "run_id": run_paths.run_id,
        "source_type": extraction.source_type,
        "provider": extraction.provider,
        "title": extraction.title,
        "original_url": source_config.get("original_url") or metadata.get("input_url"),
        "input_url": metadata.get("input_url"),
        "raw_transcript": str(raw_path.relative_to(run_paths.run_dir)),
        "article_raw": str(article_raw_path.relative_to(run_paths.run_dir)),
    }
    for key in ["author", "site_name", "published_time", "excerpt"]:
        if metadata.get(key) is not None:
            source_payload[key] = metadata[key]
    if extraction.source_type == "article_file":
        source_payload["input_kind"] = "article_file"
    write_json(run_paths.source_json, source_payload)
    return raw_path


def _article_segments(text: str) -> list[dict]:
    text = _clean_article_technical_markup(text)
    paragraphs = [
        " ".join(part.split())
        for part in re.split(r"\n\s*\n", text)
        if part.strip()
    ]
    return [
        {
            "id": f"{index:04d}",
            "start_ms": None,
            "end_ms": None,
            "speaker": None,
            "text": paragraph,
            "source": "article",
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def normalize_article(run_paths: RunPaths, raw_path: str | Path | None = None) -> Path:
    source = Path(raw_path) if raw_path else run_paths.transcript_dir / "raw.txt"
    content = source.read_text(encoding="utf-8")
    segments = _article_segments(content)
    if not segments:
        raise ValueError(f"No article segments parsed from {source}")
    normalized = {
        "episode_id": run_paths.run_id,
        "language": "en",
        "segments": segments,
    }
    write_json(run_paths.normalized_transcript_json, normalized)

    quality = build_transcript_quality_report(normalized)
    if run_paths.source_json.exists():
        source_info = read_json(run_paths.source_json)
        quality["metrics"]["source_type"] = source_info.get("source_type")
        quality["metrics"]["extractor"] = source_info.get("provider", "unknown")
    write_json(run_paths.transcript_quality_json, quality)
    return run_paths.normalized_transcript_json


def _spell_letters(value: str) -> str:
    return " ".join(value.upper())


def prepare_article_tts_text(text: str) -> str:
    def speak_gpt_version(match: re.Match[str]) -> str:
        pieces = ["G P T", match.group("major")]
        minor = match.group("minor")
        if minor:
            pieces.extend(["点", minor])
        suffix = " ".join(part for part in match.group("suffix").split("-") if part)
        if suffix:
            pieces.append(suffix)
        return " ".join(pieces)

    def speak_file_extension(match: re.Match[str]) -> str:
        extension = match.group("ext").casefold()
        return f"{match.group('stem')} {FILE_EXTENSION_SPEECH[extension]}"

    def speak_p_value(match: re.Match[str]) -> str:
        return f"p 值小于 {match.group('value')}"

    prepared = GPT_VERSION_RE.sub(speak_gpt_version, text)
    prepared = FILE_EXTENSION_RE.sub(speak_file_extension, prepared)
    prepared = re.sub(r"\bSWE-bench\b", "S W E Bench", prepared)
    prepared = re.sub(r"\bTerminal-Bench\b", "Terminal Bench", prepared)
    prepared = P_VALUE_RE.sub(speak_p_value, prepared)
    prepared = ACRONYM_RE.sub(lambda match: _spell_letters(match.group(1)), prepared)
    return " ".join(prepared.split())


def prepare_article_tts_script(run_paths: RunPaths) -> Path:
    script = read_json(run_paths.chinese_script_json)
    for segment in script.get("segments") or []:
        segment["text"] = prepare_article_tts_text(str(segment.get("text") or ""))
    write_json(run_paths.chinese_script_json, script)
    return run_paths.chinese_script_json
