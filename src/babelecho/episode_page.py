from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse


BLOCK_TAGS = {"p", "li", "blockquote"}
IGNORED_TAGS = {"script", "style", "svg"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
TIMESTAMP_PREFIX_RE = re.compile(
    r"^(?:\[\d{1,2}:\d{2}(?::\d{2})?\]|\(?\d{1,2}:\d{2}(?::\d{2})?\)?)\s*"
)


@dataclass(frozen=True)
class EpisodePageTranscript:
    title: str
    page_url: str
    transcript_page_url: str
    text: str


@dataclass(frozen=True)
class Link:
    href: str
    text: str


def _attrs_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name: value or "" for name, value in attrs}


def _classes(attrs: dict[str, str]) -> set[str]:
    return {item for item in attrs.get("class", "").split() if item}


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _clean_speaker(value: str) -> str:
    return _clean_text(value).rstrip(":")


def _speaker_prefix(speaker: str | None, text: str) -> str:
    if not speaker:
        return text
    return f"{_clean_speaker(speaker)}: {text}"


def _clean_transcript_section_block(text: str) -> str | None:
    text = TIMESTAMP_PREFIX_RE.sub("", text).strip()
    lower = text.casefold()
    if "transcript" in lower and "automatically generated" in lower:
        return None
    return text or None


def _is_transcript_heading(text: str, attrs: dict[str, str]) -> bool:
    heading_id = attrs.get("id", "").casefold()
    classes = _classes(attrs)
    if heading_id == "transcript" or "transcript" in classes:
        return True
    heading = _clean_text(text).casefold().rstrip(":")
    return heading in {"transcript", "full transcript", "episode transcript"}


def _join_url(base_url: str, href: str) -> str:
    parsed_base = urlparse(base_url)
    if parsed_base.scheme in {"http", "https"}:
        return urljoin(base_url, href)

    parsed_href = urlparse(href)
    if parsed_href.scheme or Path(href).is_absolute():
        return href
    return str(Path(base_url).parent / href)


def _looks_like_transcript_url(url: str) -> bool:
    return "transcript" in urlparse(url).path.casefold()


def _is_same_location(page_url: str, candidate_url: str) -> bool:
    parsed_page = urlparse(page_url)
    parsed_candidate = urlparse(candidate_url)
    if parsed_page.scheme in {"http", "https"}:
        return (
            parsed_candidate.scheme in {"http", "https"}
            and parsed_candidate.netloc == parsed_page.netloc
        )
    return parsed_candidate.scheme not in {"http", "https"}


class EpisodePageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.links: list[Link] = []
        self.transcript_blocks: list[str] = []
        self.article_transcript_blocks: list[str] = []
        self.ts_segment_blocks: list[str] = []
        self.section_transcript_blocks: list[str] = []
        self.fallback_blocks: list[str] = []
        self.raw_text_parts: list[str] = []
        self.seen_tags = False
        self._ignored_depth = 0
        self._tag_stack: list[str] = []
        self._transcript_depth = 0
        self._article_transcript_depth = 0
        self._current_block_parts: list[str] | None = None
        self._current_block_depth = 0
        self._article_block_parts: list[str] | None = None
        self._article_block_depth = 0
        self._section_block_parts: list[str] | None = None
        self._section_block_depth = 0
        self._fallback_block_parts: list[str] | None = None
        self._fallback_block_depth = 0
        self._capture_title = False
        self._capture_h1_depth = 0
        self._link_href: str | None = None
        self._link_parts: list[str] = []
        self._cite_parts: list[str] | None = None
        self._pending_cite: str | None = None
        self._heading_parts: list[str] | None = None
        self._heading_attrs: dict[str, str] = {}
        self._heading_depth = 0
        self._section_transcript_active = False
        self._ts_segment_depth = 0
        self._ts_name_depth = 0
        self._ts_text_depth = 0
        self._ts_name_parts: list[str] = []
        self._ts_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.seen_tags = True
        tag = tag.lower()
        attr_map = _attrs_map(attrs)
        classes = _classes(attr_map)
        self._tag_stack.append(tag)

        if tag in IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return

        if tag == "title":
            self._capture_title = True
        if tag == "h1" and not self.h1_parts:
            self._capture_h1_depth += 1
        if tag == "a":
            self._link_href = attr_map.get("href")
            self._link_parts = []
        if tag == "cite":
            self._cite_parts = []
        if tag in HEADING_TAGS:
            self._heading_parts = []
            self._heading_attrs = attr_map
            self._heading_depth = 1
        elif self._heading_depth:
            self._heading_depth += 1

        if "ts-segment" in classes:
            self._ts_segment_depth += 1
            self._ts_name_parts = []
            self._ts_text_parts = []
        elif self._ts_segment_depth:
            self._ts_segment_depth += 1
        if self._ts_segment_depth and "ts-name" in classes:
            self._ts_name_depth += 1
        elif self._ts_name_depth:
            self._ts_name_depth += 1
        if self._ts_segment_depth and "ts-text" in classes:
            self._ts_text_depth += 1
        elif self._ts_text_depth:
            self._ts_text_depth += 1

        if "transcript-content" in classes:
            self._transcript_depth += 1
        elif self._transcript_depth:
            self._transcript_depth += 1

        if tag == "article" and "transcript" in classes:
            self._article_transcript_depth += 1
        elif self._article_transcript_depth:
            self._article_transcript_depth += 1

        if self._transcript_depth and tag in BLOCK_TAGS:
            self._current_block_parts = []
            self._current_block_depth = 1
        elif self._current_block_depth:
            self._current_block_depth += 1

        if self._article_transcript_depth and tag in BLOCK_TAGS:
            self._article_block_parts = []
            self._article_block_depth = 1
        elif self._article_block_depth:
            self._article_block_depth += 1

        if self._section_transcript_active and tag in BLOCK_TAGS:
            self._section_block_parts = []
            self._section_block_depth = 1
        elif self._section_block_depth:
            self._section_block_depth += 1

        if tag in BLOCK_TAGS:
            self._fallback_block_parts = []
            self._fallback_block_depth = 1
        elif self._fallback_block_depth:
            self._fallback_block_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._ignored_depth:
            if tag in IGNORED_TAGS:
                self._ignored_depth -= 1
            if self._tag_stack:
                self._tag_stack.pop()
            return

        if tag == "title":
            self._capture_title = False
        if tag == "h1" and self._capture_h1_depth:
            self._capture_h1_depth -= 1
        if tag == "a" and self._link_href:
            self.links.append(Link(self._link_href, _clean_text(" ".join(self._link_parts))))
            self._link_href = None
            self._link_parts = []
        if tag == "cite" and self._cite_parts is not None:
            cite = _clean_text(" ".join(self._cite_parts))
            if cite:
                self._pending_cite = cite
            self._cite_parts = None
        if self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth == 0 and self._heading_parts is not None:
                heading = _clean_text(" ".join(self._heading_parts))
                if _is_transcript_heading(heading, self._heading_attrs):
                    self._section_transcript_active = True
                self._heading_parts = None
                self._heading_attrs = {}

        if self._current_block_depth:
            self._current_block_depth -= 1
            if self._current_block_depth == 0 and self._current_block_parts is not None:
                text = _clean_text(" ".join(self._current_block_parts))
                if text:
                    self.transcript_blocks.append(_speaker_prefix(self._pending_cite, text))
                    self._pending_cite = None
                self._current_block_parts = None

        if self._article_block_depth:
            self._article_block_depth -= 1
            if self._article_block_depth == 0 and self._article_block_parts is not None:
                text = _clean_text(" ".join(self._article_block_parts))
                if text:
                    self.article_transcript_blocks.append(
                        _speaker_prefix(self._pending_cite, text)
                    )
                    self._pending_cite = None
                self._article_block_parts = None

        if self._section_block_depth:
            self._section_block_depth -= 1
            if self._section_block_depth == 0 and self._section_block_parts is not None:
                text = _clean_text(" ".join(self._section_block_parts))
                cleaned = _clean_transcript_section_block(text)
                if cleaned:
                    self.section_transcript_blocks.append(
                        _speaker_prefix(self._pending_cite, cleaned)
                    )
                    self._pending_cite = None
                self._section_block_parts = None

        if self._fallback_block_depth:
            self._fallback_block_depth -= 1
            if self._fallback_block_depth == 0 and self._fallback_block_parts is not None:
                text = _clean_text(" ".join(self._fallback_block_parts))
                if text:
                    self.fallback_blocks.append(_speaker_prefix(self._pending_cite, text))
                    self._pending_cite = None
                self._fallback_block_parts = None

        if self._ts_name_depth:
            self._ts_name_depth -= 1
        if self._ts_text_depth:
            self._ts_text_depth -= 1
        if self._ts_segment_depth:
            self._ts_segment_depth -= 1
            if self._ts_segment_depth == 0:
                speaker = _clean_text(" ".join(self._ts_name_parts))
                text = _clean_text(" ".join(self._ts_text_parts))
                if text:
                    self.ts_segment_blocks.append(_speaker_prefix(speaker, text))
                self._ts_name_parts = []
                self._ts_text_parts = []

        if self._transcript_depth:
            self._transcript_depth -= 1
        if self._article_transcript_depth:
            self._article_transcript_depth -= 1
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = data.strip()
        if not text:
            return
        self.raw_text_parts.append(text)
        if self._capture_title:
            self.title_parts.append(text)
        if self._capture_h1_depth:
            self.h1_parts.append(text)
        if self._link_href is not None:
            self._link_parts.append(text)
        if self._cite_parts is not None:
            self._cite_parts.append(text)
        if self._heading_parts is not None:
            self._heading_parts.append(text)
        if self._ts_name_depth:
            self._ts_name_parts.append(text)
        if self._ts_text_depth:
            self._ts_text_parts.append(text)
        if self._current_block_parts is not None and not self._in_heading():
            self._current_block_parts.append(text)
        if self._article_block_parts is not None and not self._in_heading():
            self._article_block_parts.append(text)
        if self._section_block_parts is not None and not self._in_heading():
            self._section_block_parts.append(text)
        if self._fallback_block_parts is not None and not self._in_heading():
            self._fallback_block_parts.append(text)

    def _in_heading(self) -> bool:
        return any(tag in HEADING_TAGS for tag in self._tag_stack)

    def title(self) -> str | None:
        h1 = _clean_text(" ".join(self.h1_parts))
        if h1:
            return h1
        title = _clean_text(" ".join(self.title_parts))
        return title or None

    def transcript_text(self, source_url: str) -> str | None:
        if self.transcript_blocks:
            return "\n\n".join(self.transcript_blocks)
        if self.article_transcript_blocks:
            return "\n\n".join(self.article_transcript_blocks)
        if self.ts_segment_blocks:
            return "\n\n".join(self.ts_segment_blocks)
        if self.section_transcript_blocks:
            return "\n\n".join(self.section_transcript_blocks)
        if _looks_like_transcript_url(source_url):
            if self.fallback_blocks:
                return "\n\n".join(self.fallback_blocks)
            if not self.seen_tags:
                text = _clean_text(" ".join(self.raw_text_parts))
                return text or None
        return None


def _parse_html(content: bytes) -> EpisodePageParser:
    parser = EpisodePageParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.close()
    return parser


def _find_transcript_link(parser: EpisodePageParser, page_url: str) -> str | None:
    transcript_links: list[tuple[int, str]] = []
    for index, link in enumerate(parser.links):
        candidate = f"{link.href} {link.text}".casefold()
        if re.search(r"\btranscript\b", candidate):
            joined_url = _join_url(page_url, link.href)
            location_rank = 0 if _is_same_location(page_url, joined_url) else 1
            transcript_links.append((location_rank, index, joined_url))
    if not transcript_links:
        return None
    return sorted(transcript_links)[0][2]


def discover_episode_page_transcript(page_url: str, read_url) -> EpisodePageTranscript:
    page_parser = _parse_html(read_url(page_url))
    transcript_text = page_parser.transcript_text(page_url)
    transcript_page_url = page_url

    if transcript_text is None:
        transcript_link = _find_transcript_link(page_parser, page_url)
        if transcript_link is None:
            raise ValueError("No transcript link found in episode page")
        transcript_page_url = transcript_link
        transcript_parser = _parse_html(read_url(transcript_link))
        transcript_text = transcript_parser.transcript_text(transcript_link)
        title = page_parser.title() or transcript_parser.title() or "Untitled Episode"
    else:
        title = page_parser.title() or "Untitled Episode"

    if not transcript_text:
        raise ValueError("No transcript text found in episode page")

    return EpisodePageTranscript(
        title=title,
        page_url=page_url,
        transcript_page_url=transcript_page_url,
        text=transcript_text,
    )
