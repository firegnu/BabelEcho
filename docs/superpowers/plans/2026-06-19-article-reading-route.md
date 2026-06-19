# Article Reading Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated `article_reading` backend route for faithful Chinese TTS from public article URLs and local `.txt` / `.md` files.

**Architecture:** Add focused article extraction/normalization helpers plus an independent `article_pipeline.py` orchestrator. Do not extend existing `babelecho run`, `episode convert`, or `ingest_transcript_source()` input dispatch; keep `web_article` / `article_file` input handling separate from YouTube, RSS, Apple/iTunes, episode page, and future audio-first routes. Reuse only stable downstream primitives: DeepSeek adapt, script QA, TTS, assemble, and publish artifact contract.

**Tech Stack:** Python 3.12, argparse CLI, optional `trafilatura` import with deterministic fallback, existing BabelEcho run stages, pytest.

---

### Task 1: Article Extraction Module

**Files:**
- Create: `src/babelecho/article.py`
- Test: `tests/test_article.py`

- [x] **Step 1: Write failing tests**

Cover:
- `extract_article_file()` reads `.txt` / `.md`, strips YAML front matter and duplicate title.
- `extract_web_article()` can use an injected HTML fetcher and trafilatura-like extractor.
- extracted payload contains title, source type, provider, raw text, and safe public metadata.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: FAIL because `babelecho.article` does not exist.

- [x] **Step 2: Implement minimal module**

Add:
- `ArticleExtraction` dataclass.
- `extract_article_file(path, title=None)`.
- `extract_web_article(url, fetch_html=None, extractor=None)`.
- private helpers for markdown front matter, duplicate title, and simple HTML fallback.

- [x] **Step 3: Verify tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: PASS.

### Task 2: Article Ingest Source Types

**Files:**
- Modify: `src/babelecho/article.py`
- Test: `tests/test_article.py`

- [x] **Step 1: Write failing ingest tests**

Cover:
- `ingest_article_source()` handles `source.type=article_file`, writes `article/raw.txt`, `article/extracted.json`, `transcript/raw.txt`, and `source.json` without leaking absolute local paths.
- `ingest_article_source()` handles `source.type=web_article`, writes article metadata and uses provider `trafilatura`.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: FAIL because `ingest_article_source()` does not exist.

- [x] **Step 2: Implement ingest branches**

Add `ingest_article_source()` in `src/babelecho/article.py`. Do not modify `src/babelecho/ingest.py`. For article sources, write `source_json` fields needed by publish and set `raw_transcript` to `transcript/raw.txt`.

- [x] **Step 3: Verify targeted tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: PASS.

### Task 3: Article Normalize Behavior And Quality Metrics

**Files:**
- Modify: `src/babelecho/article.py`
- Test: `tests/test_article.py`

- [x] **Step 1: Write failing normalize tests**

Cover:
- `article_file` / `web_article` normalizes paragraphs without speaker labels.
- article normalization does not infer `Title:` as a speaker label.
- quality metrics include `source_type` and `extractor` for article sources.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: FAIL because `normalize_article()` does not exist.

- [x] **Step 2: Implement minimal article normalization**

Add `normalize_article()` in `src/babelecho/article.py`. It should read `article/raw.txt` or `transcript/raw.txt`, split article paragraphs, write `transcript/normalized.json` with no speaker labels, build a quality report with the existing `build_transcript_quality_report()` helper plus article metrics, and write `transcript/quality.json`. Do not modify `src/babelecho/transcript.py` or `src/babelecho/transcript_quality.py`.

- [x] **Step 3: Verify targeted tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
Expected: PASS.

### Task 4: CLI Article Convert Entry

**Files:**
- Create: `src/babelecho/article_pipeline.py`
- Modify: `src/babelecho/cli.py`
- Test: `tests/test_end_to_end_fixture.py`

- [x] **Step 1: Write failing CLI tests**

Cover:
- `babelecho article convert --file ... --to-stage normalize` uses the independent article pipeline and writes `source.type=article_file`.
- `babelecho article convert --url ... --to-stage normalize` uses the independent article pipeline and writes `source.type=web_article`.
- article route uses the current no-speaker TTS default, which resolves to `female_a`, and does not call speaker voice inference.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_end_to_end_fixture.py -q -k article`
Expected: FAIL because `article` command is missing.

- [x] **Step 2: Implement parser and dispatch**

Add `article convert` subcommand with `--url` / `--file`, `--title`, `--local-config`, `--from-stage`, and `--to-stage`. Implement `run_article_pipeline()` in `src/babelecho/article_pipeline.py`. Do not call or modify the existing `run_pipeline()` for article inputs. For article route, skip speaker voice inference and rely on the existing no-speaker `sft_builtin_4role` default, which is `female_a`, without changing non-article runs.

- [x] **Step 3: Verify targeted CLI tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_end_to_end_fixture.py -q -k article`
Expected: PASS.

### Task 5: Publish Contract And Docs

**Files:**
- Modify: `src/babelecho/publish.py`
- Modify: `docs/前端Artifact契约与只读界面说明.md`
- Test: `tests/test_publish.py`

- [x] **Step 1: Write failing publish test**

Cover:
- article source publishes `route=article_reading`.
- artifact source includes `site_name`, `author`, `published_time`, and provider.
- artifact speaker summary stays empty (`speakers=[]`) because article route does not identify speakers.

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py -q`
Expected: FAIL because publish routes all non-audio sources to `transcript_first`.

- [x] **Step 2: Implement publish mapping and docs**

Map `web_article`, `article_file`, `x_post`, and `x_thread` to `article_reading`. Add provider/source metadata fields to the public source object. Update the frontend artifact contract with article route/source values.

- [x] **Step 3: Verify publish tests pass**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py -q`
Expected: PASS.

### Task 6: Regression And Completion

**Files:**
- Modify as needed from prior tasks only.

- [x] **Step 1: Run source route matrix**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_source_matrix.py -q`
Expected: PASS.

- [x] **Step 2: Run full test suite**

Run: `.conda/babelecho-dev/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 3: Run diff and secret checks before any commit**

Run:
- `git diff --check`
- `git diff --cached --check`
- `git diff --cached | /opt/homebrew/bin/gitleaks stdin --redact --no-banner --log-level error`
- `git diff --cached --name-only -z | xargs -0 /opt/homebrew/bin/trufflehog filesystem --no-update --fail --force-skip-binaries --force-skip-archives`

Expected: all clean.

Status: deferred until commit time because no files are staged in the current implementation pass.
