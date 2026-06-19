# Article Reading Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated `article_reading` backend route for faithful Chinese TTS from public article URLs and local `.txt` / `.md` files.

**Architecture:** Add focused article extraction/normalization helpers and route them through the existing staged backend pipeline. Keep `web_article` / `article_file` input handling separate from YouTube, RSS, Apple/iTunes, episode page, and future audio-first routes, while reusing existing quality gate, DeepSeek adapt, script QA, TTS, assemble, and publish artifact contract.

**Tech Stack:** Python 3.12, argparse CLI, optional `trafilatura` import with deterministic fallback, existing BabelEcho run stages, pytest.

---

### Task 1: Article Extraction Module

**Files:**
- Create: `src/babelecho/article.py`
- Test: `tests/test_article.py`

- [ ] **Step 1: Write failing tests**

Cover:
- `extract_article_file()` reads `.txt` / `.md`, strips YAML front matter and duplicate title.
- `extract_web_article()` can use an injected HTML fetcher and trafilatura-like extractor.
- extracted payload contains title, source type, provider, raw text, and safe public metadata.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: FAIL because `babelecho.article` does not exist.

- [ ] **Step 2: Implement minimal module**

Add:
- `ArticleExtraction` dataclass.
- `extract_article_file(path, title=None)`.
- `extract_web_article(url, fetch_html=None, extractor=None)`.
- private helpers for markdown front matter, duplicate title, and simple HTML fallback.

- [ ] **Step 3: Verify tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: PASS.

### Task 2: Ingest Source Types

**Files:**
- Modify: `src/babelecho/ingest.py`
- Test: `tests/test_article.py`

- [ ] **Step 1: Write failing ingest tests**

Cover:
- `source.type=article_file` writes `article/raw.txt`, `article/extracted.json`, `transcript/raw.txt`, and `source.json` without leaking absolute local paths.
- `source.type=web_article` writes article metadata and uses provider `trafilatura`.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: FAIL because ingest rejects article source types.

- [ ] **Step 2: Implement ingest branches**

Add `article_file` and `web_article` branches in `ingest_transcript_source()`. Keep existing source branches unchanged. For article sources, write `source_json` fields needed by publish and set `raw_transcript` to `transcript/raw.txt`.

- [ ] **Step 3: Verify targeted tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: PASS.

### Task 3: Article Normalize Behavior And Quality Metrics

**Files:**
- Modify: `src/babelecho/transcript.py`
- Modify: `src/babelecho/transcript_quality.py`
- Test: `tests/test_article.py`

- [ ] **Step 1: Write failing normalize tests**

Cover:
- `article_file` / `web_article` normalizes paragraphs into `speaker="Narrator"` segments.
- article normalization does not infer `Title:` as a speaker label.
- quality metrics include `source_type` and `extractor` for article sources.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: FAIL because article segments currently have no forced narrator and no article metrics.

- [ ] **Step 2: Implement minimal article normalization**

Add source-type checks so `web_article`, `article_file`, `x_post`, and `x_thread` disable speaker-label inference and assign `Narrator` to each normalized segment. Extend `write_transcript_quality()` to copy article extractor/source metadata into quality metrics when present.

- [ ] **Step 3: Verify targeted tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: PASS.

### Task 4: CLI Article Convert Entry

**Files:**
- Modify: `src/babelecho/cli.py`
- Test: `tests/test_end_to_end_fixture.py`

- [ ] **Step 1: Write failing CLI tests**

Cover:
- `babelecho article convert --file ... --to-stage normalize` routes to `source.type=article_file`.
- `babelecho article convert --url ... --to-stage normalize` routes to `source.type=web_article`.
- article route injects `speaker_voices.default_voice_role=female_a` so narrator uses the current 300M `female_a` path.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_end_to_end_fixture.py -q -k article`
Expected: FAIL because `article` command is missing.

- [ ] **Step 2: Implement parser and dispatch**

Add `article convert` subcommand with `--url` / `--file`, `--title`, `--local-config`, `--from-stage`, and `--to-stage`. Extend `run_pipeline()` to accept an in-memory source config and optional local config overrides. For article route, force `speaker_voices.default_voice_role=female_a` without changing non-article runs.

- [ ] **Step 3: Verify targeted CLI tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_end_to_end_fixture.py -q -k article`
Expected: PASS.

### Task 5: Publish Contract And Docs

**Files:**
- Modify: `src/babelecho/publish.py`
- Modify: `docs/前端Artifact契约与只读界面说明.md`
- Test: `tests/test_publish.py`

- [ ] **Step 1: Write failing publish test**

Cover:
- article source publishes `route=article_reading`.
- artifact source includes `site_name`, `author`, `published_time`, and provider.
- speaker summary shows `Narrator` with `voice_role=female_a`.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py -q`
Expected: FAIL because publish routes all non-audio sources to `transcript_first`.

- [ ] **Step 2: Implement publish mapping and docs**

Map `web_article`, `article_file`, `x_post`, and `x_thread` to `article_reading`. Add provider/source metadata fields to the public source object. Update the frontend artifact contract with article route/source values.

- [ ] **Step 3: Verify publish tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py -q`
Expected: PASS.

### Task 6: Regression And Completion

**Files:**
- Modify as needed from prior tasks only.

- [ ] **Step 1: Run source route matrix**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_source_matrix.py -q`
Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run: `.conda/babelecho-dev/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 3: Run diff and secret checks before any commit**

Run:
- `git diff --check`
- `git diff --cached --check`
- `git diff --cached | /opt/homebrew/bin/gitleaks stdin --redact --no-banner --log-level error`
- `git diff --cached --name-only -z | xargs -0 /opt/homebrew/bin/trufflehog filesystem --no-update --fail --force-skip-binaries --force-skip-archives`

Expected: all clean.
