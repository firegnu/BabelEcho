from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from babelecho.episode_page import discover_episode_page_transcript
from babelecho.ingest import ingest_transcript_source
from babelecho.jsonio import read_json
from babelecho.paths import create_run


def read_local_url(url: str) -> bytes:
    return Path(url).read_bytes()


def run_http_server(pages: dict[str, str]):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            user_agent = self.headers.get("User-Agent", "")
            if user_agent.startswith("Python-urllib"):
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            body = pages.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return

            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_discovers_transcript_link_and_extracts_clean_text(tmp_path: Path):
    episode_page = tmp_path / "episode.html"
    transcript_page = tmp_path / "transcript.html"
    episode_page.write_text(
        f"""<!doctype html>
<html>
  <head><title>Example Episode</title></head>
  <body>
    <nav>Site navigation</nav>
    <article>
      <h1>Example Episode Title</h1>
      <a href="{transcript_page.name}">Transcript</a>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )
    transcript_page.write_text(
        """<!doctype html>
<html>
  <head><title>Example Episode Transcript</title></head>
  <body>
    <nav>Navigation should not be included</nav>
    <div class="page-content transcript-content">
      <p>Host: Hello from the episode.</p>
      <p>Guest: Thanks for having me.</p>
    </div>
    <script>console.log("ignore me")</script>
  </body>
</html>
""",
        encoding="utf-8",
    )

    transcript = discover_episode_page_transcript(str(episode_page), read_local_url)

    assert transcript.title == "Example Episode Title"
    assert transcript.page_url == str(episode_page)
    assert transcript.transcript_page_url == str(transcript_page)
    assert transcript.text == "Host: Hello from the episode.\n\nGuest: Thanks for having me."


def test_extracts_page_when_current_page_is_transcript(tmp_path: Path):
    transcript_page = tmp_path / "transcript.html"
    transcript_page.write_text(
        """<!doctype html>
<html>
  <head><title>Direct Transcript</title></head>
  <body>
    <article class="transcript post">
      <h1>Direct Transcript Title</h1>
      <p>Speaker One: First paragraph.</p>
      <p>Speaker Two: Second paragraph.</p>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )

    transcript = discover_episode_page_transcript(str(transcript_page), read_local_url)

    assert transcript.title == "Direct Transcript Title"
    assert transcript.transcript_page_url == str(transcript_page)
    assert transcript.text == "Speaker One: First paragraph.\n\nSpeaker Two: Second paragraph."


def test_prefers_transcript_content_inside_transcript_article(tmp_path: Path):
    transcript_page = tmp_path / "transcript.html"
    transcript_page.write_text(
        """<!doctype html>
<html>
  <body>
    <article class="transcript post">
      <ul>
        <li>Play Pause</li>
        <li>Download</li>
      </ul>
      <div class="entry-meta">
        <p>Category</p>
        <p>History</p>
      </div>
      <div class="page-content transcript-content">
        <p>ROMAN MARS: This is the real transcript.</p>
        <p>VIVIAN LE: It should start here.</p>
      </div>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )

    transcript = discover_episode_page_transcript(str(transcript_page), read_local_url)

    assert transcript.text == (
        "ROMAN MARS: This is the real transcript.\n\n"
        "VIVIAN LE: It should start here."
    )


def test_prefixes_cite_speaker_on_following_transcript_paragraph(tmp_path: Path):
    transcript_page = tmp_path / "transcript.html"
    transcript_page.write_text(
        """<!doctype html>
<html>
  <body class="transcript">
    <div class="page-content transcript-content">
      <cite>Daniel:</cite>
      <p>Welcome to another Practical AI episode.</p>
      <cite>Chris:</cite>
      <p>Hey, doing great. Glad to be here.</p>
    </div>
  </body>
</html>
""",
        encoding="utf-8",
    )

    transcript = discover_episode_page_transcript(str(transcript_page), read_local_url)

    assert transcript.text == (
        "Daniel: Welcome to another Practical AI episode.\n\n"
        "Chris: Hey, doing great. Glad to be here."
    )


def test_extracts_ts_segment_transcript_instead_of_navigation(tmp_path: Path):
    transcript_page = tmp_path / "jensen-huang-transcript.html"
    transcript_page.write_text(
        """<!doctype html>
<html>
  <body>
    <nav>
      <ul>
        <li>Podcast</li>
        <li>Contact</li>
      </ul>
    </nav>
    <article>
      <div class="ts-segment">
        <span class="ts-name">Lex Fridman</span>
        <span class="ts-timestamp"><a href="#0">(00:00:00)</a></span>
        <span class="ts-text">The following is a conversation about AI.</span>
      </div>
      <div class="ts-segment">
        <span class="ts-name">Jensen Huang</span>
        <span class="ts-timestamp"><a href="#1">(00:01:20)</a></span>
        <span class="ts-text">It is an incredible time for computing.</span>
      </div>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )

    transcript = discover_episode_page_transcript(str(transcript_page), read_local_url)

    assert transcript.text == (
        "Lex Fridman: The following is a conversation about AI.\n\n"
        "Jensen Huang: It is an incredible time for computing."
    )


def test_extracts_transcript_section_from_episode_page(tmp_path: Path):
    episode_page = tmp_path / "episode.html"
    episode_page.write_text(
        """<!doctype html>
<html>
  <body>
    <article class="post tag-episode content">
      <h1>AI Agent Episode</h1>
      <h2>Show Notes</h2>
      <p>These links are show notes and should not be treated as transcript.</p>
      <h2 id="transcript">Transcript</h2>
      <p><em>This transcript is automatically generated.</em></p>
      <hr>
      <h2 id="introduction">Introduction</h2>
      <p><a href="#t0"><strong>[00:00]</strong></a> Hello and welcome back.</p>
      <p><a href="#t1"><strong>[00:42]</strong></a><strong>Nathan Labenz:</strong> Today we are talking about agents.</p>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )

    transcript = discover_episode_page_transcript(str(episode_page), read_local_url)

    assert transcript.text == (
        "Hello and welcome back.\n\n"
        "Nathan Labenz: Today we are talking about agents."
    )


def test_prefers_same_host_transcript_link_over_external_transcript_noise(
    tmp_path: Path,
):
    episode_page = tmp_path / "episode.html"
    transcript_page = tmp_path / "transcript.html"
    external_page = tmp_path / "external-transcript.html"
    episode_page.write_text(
        f"""<!doctype html>
<html>
  <body>
    <article>
      <h1>Correct Episode</h1>
      <a href="https://joincolossus.com/episode/unrelated/?tab=transcript">Transcript</a>
      <a href="{transcript_page.name}">Read transcript</a>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )
    transcript_page.write_text(
        """<!doctype html>
<html>
  <body>
    <div class="transcript-content">
      <p>Host: This is the correct transcript.</p>
    </div>
  </body>
</html>
""",
        encoding="utf-8",
    )
    external_page.write_text(
        """<!doctype html>
<html>
  <body>
    <div class="transcript-content">
      <p>Other Host: This transcript is unrelated.</p>
    </div>
  </body>
</html>
""",
        encoding="utf-8",
    )

    def read_url(url: str) -> bytes:
        if url.startswith("https://joincolossus.com/"):
            return external_page.read_bytes()
        return Path(url).read_bytes()

    transcript = discover_episode_page_transcript(str(episode_page), read_url)

    assert transcript.transcript_page_url == str(transcript_page)
    assert transcript.text == "Host: This is the correct transcript."


def test_fails_when_episode_page_has_no_transcript(tmp_path: Path):
    episode_page = tmp_path / "episode.html"
    episode_page.write_text(
        """<!doctype html>
<html>
  <head><title>No Transcript Episode</title></head>
  <body>
    <article>
      <h1>No Transcript Episode</h1>
      <p>Show notes only.</p>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No transcript link found"):
        discover_episode_page_transcript(str(episode_page), read_local_url)


def test_ingest_episode_page_writes_clean_raw_text_and_source_json(tmp_path: Path):
    episode_page = tmp_path / "episode.html"
    transcript_page = tmp_path / "transcript.html"
    episode_page.write_text(
        """<!doctype html>
<html>
  <body>
    <article>
      <h1>Ingest Episode Title</h1>
      <a href="transcript.html">Read transcript</a>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )
    transcript_page.write_text(
        """<!doctype html>
<html>
  <body>
    <header>Ignore header</header>
    <div class="transcript-content">
      <p>Host: Ingest works.</p>
      <p>Guest: It is clean.</p>
    </div>
  </body>
</html>
""",
        encoding="utf-8",
    )
    run_paths = create_run(tmp_path / "workspace", "episode-page-demo")

    raw_path = ingest_transcript_source(
        {
            "type": "episode_page",
            "page_url": str(episode_page),
        },
        run_paths,
    )

    source = read_json(run_paths.source_json)
    assert raw_path == run_paths.transcript_dir / "raw.txt"
    assert raw_path.read_text(encoding="utf-8") == (
        "Host: Ingest works.\n\nGuest: It is clean."
    )
    assert source["source_type"] == "episode_page"
    assert source["page_url"] == str(episode_page)
    assert source["transcript_page_url"] == str(transcript_page)
    assert source["title"] == "Ingest Episode Title"
    assert source["original_url"] == str(episode_page)


def test_ingest_episode_page_http_uses_non_default_user_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    server = run_http_server(
        {
            "/episode": """<!doctype html>
<html>
  <body>
    <article>
      <h1>HTTP Episode</h1>
      <a href="/transcript">Transcript</a>
    </article>
  </body>
</html>
""",
            "/transcript": """<!doctype html>
<html>
  <body>
    <div class="transcript-content">
      <p>Host: HTTP page worked.</p>
    </div>
  </body>
</html>
""",
        }
    )
    try:
        run_paths = create_run(tmp_path / "workspace", "episode-page-http")
        page_url = f"http://127.0.0.1:{server.server_port}/episode"

        raw_path = ingest_transcript_source(
            {
                "type": "episode_page",
                "page_url": page_url,
            },
            run_paths,
        )
    finally:
        server.shutdown()
        server.server_close()

    source = read_json(run_paths.source_json)
    assert raw_path.read_text(encoding="utf-8") == "Host: HTTP page worked."
    assert source["transcript_page_url"] == (
        f"http://127.0.0.1:{server.server_port}/transcript"
    )
