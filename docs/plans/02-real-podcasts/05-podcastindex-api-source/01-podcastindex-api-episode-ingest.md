# 02.05.01 PodcastIndex API Episode Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `source.type=podcast_index_api` so BabelEcho can fetch PodcastIndex episode metadata with API authentication and ingest the episode transcript.

**Architecture:** Add a small `podcast_index_api` module responsible only for credentials, auth headers, endpoint URL construction, API request, and selecting an episode from API responses. Keep `ingest.py` as the integration point and reuse the existing `discover_podcast_index_transcript()` parser.

**Tech Stack:** Python stdlib only: `hashlib`, `json`, `os`, `time`, `urllib.parse`, `urllib.request`; existing pytest and YAML config flow.

---

状态：`done`

日期：2026-06-18

父计划：`02.05 PodcastIndex API Source`

## Source Config

第一版使用 `--source-config`，不新增 CLI 参数：

```yaml
source:
  type: podcast_index_api
  endpoint: episodes/byid
  episode_id: 123456
  api_key_env: PODCASTINDEX_API_KEY
  api_secret_env: PODCASTINDEX_API_SECRET
  user_agent: "BabelEcho/0.1"
```

也支持从 ignored env 文件读取：

```yaml
source:
  type: podcast_index_api
  endpoint: episodes/byfeedid
  feed_id: 75075
  episode_url: "https://example.com/episodes/target"
  credentials_file: "workspace/config/podcastindex.env"
```

`workspace/config/podcastindex.env` 内容：

```bash
PODCASTINDEX_API_KEY=...
PODCASTINDEX_API_SECRET=...
PODCASTINDEX_USER_AGENT=BabelEcho/0.1
```

## Task 1: PodcastIndex Auth Header Unit Tests

**Files:**

- Create: `src/babelecho/podcast_index_api.py`
- Test: `tests/test_podcast_index_api.py`

- [ ] **Step 1: Write failing auth tests**

Add tests that call:

```python
from babelecho.podcast_index_api import PodcastIndexCredentials, build_auth_headers


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
```

Expected command:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast_index_api.py -q
```

Expected RED: import fails because `babelecho.podcast_index_api` does not exist.

- [ ] **Step 2: Implement minimal auth module**

Add `PodcastIndexCredentials` and `build_auth_headers()` using `hashlib.sha1((api_key + api_secret + unix_time).encode("utf-8")).hexdigest()`.

- [ ] **Step 3: Verify GREEN**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast_index_api.py -q
```

Expected: auth tests pass.

## Task 2: Credential Loading Tests

**Files:**

- Modify: `src/babelecho/podcast_index_api.py`
- Test: `tests/test_podcast_index_api.py`

- [ ] **Step 1: Write failing credential tests**

Cover:

- `api_key_env` + `api_secret_env`.
- `credentials_file` with `PODCASTINDEX_API_KEY`, `PODCASTINDEX_API_SECRET`, optional `PODCASTINDEX_USER_AGENT`.
- Missing credentials raises `ValueError` mentioning the missing key.
- Configuring both env and file raises `ValueError`.

- [ ] **Step 2: Implement minimal credential loader**

Add:

```python
def load_podcast_index_credentials(source_config: dict) -> PodcastIndexCredentials:
    ...
```

Do not store or print secret values.

- [ ] **Step 3: Verify GREEN**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast_index_api.py -q
```

## Task 3: API URL and Response Selection Tests

**Files:**

- Modify: `src/babelecho/podcast_index_api.py`
- Test: `tests/test_podcast_index_api.py`

- [ ] **Step 1: Write failing endpoint tests**

Cover:

- `endpoint: episodes/byid` requires `episode_id` and builds `/episodes/byid?id=<episode_id>&fulltext`.
- `endpoint: episodes/byfeedid` requires `feed_id` and builds `/episodes/byfeedid?id=<feed_id>&max=<max_episodes>&fulltext`.
- `endpoint: episodes/byfeedurl` requires `feed_url` and URL-encodes it.
- `episode_url` selects a matching episode from an `items` list by `link`, `guid`, or `enclosureUrl`.
- Missing transcript in selected episode raises the existing PodcastIndex transcript error after ingest integration.

- [ ] **Step 2: Implement URL construction and selection**

Add:

```python
def build_podcast_index_url(source_config: dict) -> str:
    ...

def select_podcast_index_episode(payload: dict, episode_url: str | None) -> dict:
    ...
```

Keep accepted endpoint strings exact: `episodes/byid`, `episodes/byfeedid`, `episodes/byfeedurl`, `episodes/byitunesid`.

- [ ] **Step 3: Verify GREEN**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast_index_api.py -q
```

## Task 4: Integrate Ingest

**Files:**

- Modify: `src/babelecho/ingest.py`
- Modify: `tests/test_podcast.py`

- [ ] **Step 1: Write failing ingest test**

Add a test with a local fake `api_base_url` and HTTP server returning:

```json
{
  "episode": {
    "title": "API Episode",
    "link": "https://example.com/api-episode",
    "transcripts": [
      {"url": "<local transcript path>", "type": "text/plain"}
    ]
  }
}
```

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast.py tests/test_podcast_index_api.py -q
```

Expected RED: unsupported `source.type=podcast_index_api`.

- [ ] **Step 2: Add `podcast_index_api` branch**

In `ingest_transcript_source()`:

- Call `fetch_podcast_index_episode(source_config)`.
- Pass result to `discover_podcast_index_transcript()`.
- Download the discovered transcript URL with existing `_read_source`.
- Write existing `source.json` fields plus `podcast_index_endpoint`, `podcast_index_episode_id`, `feed_id`, `feed_url`.

- [ ] **Step 3: Verify GREEN**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast.py tests/test_podcast_index_api.py -q
```

## Task 5: Run Command Fixture

**Files:**

- Modify: `tests/test_end_to_end_fixture.py`

- [ ] **Step 1: Write failing run fixture test**

Use `source.type=podcast_index_api` with the fake local API server and run:

```bash
.conda/babelecho-dev/bin/python -m babelecho run \
  --workspace "$workspace" \
  --run-id podcastindex-api-flow \
  --source-config "$source_config" \
  --local-config "$local_config" \
  --to-stage adapt
```

Assert:

- stdout contains `ingest:`, `normalize:`, `adapt:`.
- raw transcript exists.
- `source.json` contains `source_type=podcast_index_api`.
- `run.json input.source_config` is recorded.

- [ ] **Step 2: Implement only if CLI path needs changes**

Expected: no CLI changes because `--source-config` already passes through to ingest.

- [ ] **Step 3: Verify GREEN**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast_index_api.py tests/test_podcast.py tests/test_end_to_end_fixture.py -q
```

## Task 6: Example and Docs

**Files:**

- Create: `workspace/sources/podcast-index-api.example.yaml`
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Modify: `resume-prompt.md`

- [ ] **Step 1: Add example source config**

Use env references only:

```yaml
source:
  type: podcast_index_api
  endpoint: episodes/byid
  episode_id: 123456
  api_key_env: PODCASTINDEX_API_KEY
  api_secret_env: PODCASTINDEX_API_SECRET
  user_agent: "BabelEcho/0.1"
```

- [ ] **Step 2: Update docs after implementation**

Mark 02.05.01 done only after tests and any available smoke are complete.

## Task 7: Verification, Scan, Commit, Push

- [ ] **Step 1: Focused tests**

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_podcast_index_api.py tests/test_podcast.py tests/test_end_to_end_fixture.py -q
```

- [ ] **Step 2: Full tests**

```bash
.conda/babelecho-dev/bin/python -m pytest -q
```

- [ ] **Step 3: Optional real smoke**

If credentials exist in environment or ignored `workspace/config/podcastindex.env`, run transcript-only smoke to `ingest`. If not present, record that real smoke was skipped because credentials are unavailable.

- [ ] **Step 4: Secret scans**

```bash
git diff --cached | /opt/homebrew/bin/gitleaks stdin --redact --no-banner --no-color
git diff --cached | /opt/homebrew/bin/trufflehog stdin --no-update --results=verified,unknown --no-color
pattern='PRIVATE'' KEY|BEGIN [A-Z ]*PRIVATE'' KEY|OPENAI''_API''_KEY|sk-[A-Za-z0-9]|ghp_[A-Za-z0-9]|github''_pat_|AKIA[0-9A-Z]{16}|Bearer [A-Za-z0-9_./+=-]{16,}|password\\s*[:=]|api[_-]?key\\s*[:=]'
git diff --cached | rg -n "$pattern"
```

- [ ] **Step 5: Commit and sync**

```bash
git add src/babelecho/podcast_index_api.py src/babelecho/ingest.py tests/test_podcast_index_api.py tests/test_podcast.py tests/test_end_to_end_fixture.py workspace/sources/podcast-index-api.example.yaml docs/plans/README.md docs/roadmap.md resume-prompt.md
git commit -m "feat: ingest podcastindex api episodes"
git checkout main
git pull --ff-only origin main
git merge --ff-only podcastindex-api-ingest
.conda/babelecho-dev/bin/python -m pytest -q
git push origin main
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && git pull --ff-only && git status --short --branch'
```

## 验收记录

- 本地 focused 测试：`tests/test_podcast_index_api.py tests/test_podcast.py tests/test_end_to_end_fixture.py` 通过。
- 已覆盖 fake PodcastIndex API server，验证 API auth headers、episode JSON ingest、`run --to-stage adapt`。
- 本机没有 `PODCASTINDEX_API_KEY` / `PODCASTINDEX_API_SECRET` 或 ignored `workspace/config/podcastindex.env`，真实 PodcastIndex smoke 未执行。
