# 02.04.01 Episode Page Transcript-only Ingest 计划

状态：`ready`

日期：2026-06-18

父计划：`02.04 Episode Page Transcript Source`

## 目标

新增 `source.type=episode_page`，让 BabelEcho 能从播客官网单集页面找到 transcript 链接或正文，并只把 transcript 拉到本地 `raw.txt`；后续阶段继续复用现有 `normalize -> adapt -> synthesize -> assemble -> publish`。

## 设计

输入 source config：

```yaml
source:
  type: episode_page
  page_url: "https://example.com/episode/1"
  title: "Optional Title"
```

`ingest` 行为：

```text
读取 page_url HTML
-> 如果页面有 transcript 链接，解析绝对 URL 并下载 transcript 页面
-> 如果页面本身就是 transcript 页面，直接抽取正文
-> 抽取 transcript 正文为纯文本
-> 保存 workspace/runs/<run-id>/transcript/raw.txt
-> 写 source.json
```

`source.json` 记录：

```text
source_type=episode_page
page_url
transcript_page_url
title
original_url
raw_transcript
```

## 范围

In:

- 新增 `src/babelecho/episode_page.py`。
- `src/babelecho/ingest.py` 增加 `source.type=episode_page` 分支。
- 支持相对 transcript 链接解析，例如 `/episode/x/transcript`。
- 支持 transcript 正文容器：
  - `class` 包含 `transcript-content`
  - `article` 的 `class` 包含 `transcript`
  - 页面标题或链接明确是 transcript 时的正文 fallback
- 输出干净纯文本，不把 HTML 标签、导航、脚本和样式写进 transcript。
- 测试覆盖成功、相对链接、页面本身是 transcript、缺失 transcript。

Out:

- 不引入 BeautifulSoup/lxml 依赖；第一版用 Python 标准库 `html.parser`。
- 不做 JavaScript 渲染页面。
- 不做站点级 profile 配置。
- 不做 YouTube/Spotify/Apple 页面。
- 不做 ASR 或音频下载。

## 执行步骤

### 1. 写失败测试：episode 页面发现 transcript 链接

新增 `tests/test_episode_page.py`，创建本地 `episode.html` 和 `transcript.html` fixture。

测试意图：

```text
episode.html 包含 <a href="/episode/1/transcript">Transcript</a>
transcript.html 包含 <div class="transcript-content"><p>Host: Hello.</p></div>
discover_episode_page_transcript 返回 title、transcript_page_url、text
```

运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_episode_page.py -q
```

预期：失败，原因是 `babelecho.episode_page` 不存在。

### 2. 实现最小 HTML 解析器

新增 `src/babelecho/episode_page.py`。

建议接口：

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class EpisodePageTranscript:
    title: str
    page_url: str
    transcript_page_url: str
    text: str


def discover_episode_page_transcript(page_url: str, read_url) -> EpisodePageTranscript:
    """Return transcript metadata and clean transcript text for an episode page."""
```

设计约束：

- `read_url(url) -> bytes` 由 `ingest.py` 传入，避免 parser 自己做网络 IO，便于测试。
- 使用 `urllib.parse.urljoin` 解析相对链接。
- 优先选择 href 或链接文字包含 `transcript` 的 `<a>`。
- 正文抽取只返回可见文本；忽略 `script`、`style`、`svg`。
- 如果没有 transcript 链接且当前页面不像 transcript 页，抛出 `ValueError("No transcript link found in episode page")`。
- 如果抽取后正文为空，抛出 `ValueError("No transcript text found in episode page")`。

### 3. 写失败测试：ingest 支持 `source.type=episode_page`

在 `tests/test_podcast.py` 或新增 `tests/test_episode_page.py` 中覆盖：

```text
source.type=episode_page
page_url=<本地 episode.html>
ingest_transcript_source 生成 transcript/raw.txt
source.json 记录 source_type、page_url、transcript_page_url、title、original_url
```

运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_episode_page.py tests/test_podcast.py -q
```

预期：失败，原因是 `ingest.py` 不支持 `episode_page`。

### 4. 接入 `ingest.py`

修改 `src/babelecho/ingest.py`：

- import `discover_episode_page_transcript`。
- 在 `source_type == "episode_page"` 分支读取 `page_url`。
- 调用 `discover_episode_page_transcript(page_url, _read_source)`。
- 写入 `raw.txt`，而不是保存原始 HTML。
- `source.json` 增加 `page_url` 和 `transcript_page_url`。
- 更新不支持 source type 的错误消息。

不需要给 `babelecho run` 增加新 CLI 参数；第一版走 `--source-config`，避免 CLI 参数膨胀。

### 5. 写失败测试：`babelecho run --source-config "$tmpdir/source.yaml" --to-stage adapt`

在 `tests/test_end_to_end_fixture.py` 增加一个 fixture flow：

```text
source-config episode_page
local-config fixture llm/tts/publish
babelecho run --to-stage adapt
```

断言：

- return code 为 0。
- stdout 包含 `ingest:`、`normalize:`、`adapt:`。
- `transcript/raw.txt` 存在且不含 `<p>`、`<div>`。
- `script/zh.json` 存在。
- `run.json input.source_config` 正确。

### 6. 补真实 transcript-only smoke

使用真实 99% Invisible episode 页面，只跑到 ingest：

```bash
tmpdir=$(mktemp -d /tmp/babelecho-episode-page.XXXXXX)
cat > "$tmpdir/source.yaml" <<'YAML'
source:
  type: episode_page
  page_url: "https://99percentinvisible.org/episode/641-99pi-anniversary-special-15-for-15/"
YAML

.conda/babelecho-dev/bin/python -m babelecho run \
  --workspace "$tmpdir/workspace" \
  --run-id episode-page-99pi-smoke \
  --source-config "$tmpdir/source.yaml" \
  --local-config workspace/config/local.example.yaml \
  --to-stage ingest
```

验证：

```bash
wc -c "$tmpdir/workspace/runs/episode-page-99pi-smoke/transcript/raw.txt"
sed -n '1,20p' "$tmpdir/workspace/runs/episode-page-99pi-smoke/transcript/raw.txt"
```

预期：

- `raw.txt` 非空。
- 开头包含 `ROMAN MARS:` / `VIVIAN LE:` 等 transcript 正文。
- 没有 HTML 标签。
- `run.json` 后续阶段为 `skipped`。

### 7. 更新示例和计划索引

新增：

```text
workspace/sources/episode-page.example.yaml
```

内容：

```yaml
source:
  type: episode_page
  page_url: "https://example.com/podcast/episodes/1"
```

更新：

- `docs/plans/README.md`：登记 `02.04 Episode Page Transcript Source` 和 `02.04.01`。
- `docs/roadmap.md`：把 episode page 从“后续仍需”改为对应状态。
- `resume-prompt.md`：只在实现完成后更新，不在计划阶段提前标记 done。

### 8. 验证和收尾

运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_episode_page.py tests/test_podcast.py tests/test_end_to_end_fixture.py -q
.conda/babelecho-dev/bin/python -m pytest -q
```

提交前扫描：

```bash
git diff --cached | /opt/homebrew/bin/gitleaks stdin --redact --no-banner --no-color
git diff --cached | /opt/homebrew/bin/trufflehog stdin --no-update --results=verified,unknown --no-color
pattern='PRIVATE'' KEY|BEGIN [A-Z ]*PRIVATE'' KEY|OPENAI''_API''_KEY|sk-[A-Za-z0-9]|ghp_[A-Za-z0-9]|github''_pat_|AKIA[0-9A-Z]{16}|Bearer [A-Za-z0-9_./+=-]{16,}|password\\s*[:=]|api[_-]?key\\s*[:=]'
git diff --cached | rg -n "$pattern"
```

提交：

```bash
git add src/babelecho/episode_page.py src/babelecho/ingest.py tests/test_episode_page.py tests/test_end_to_end_fixture.py workspace/sources/episode-page.example.yaml docs/plans/README.md docs/roadmap.md resume-prompt.md
git commit -m "feat: ingest episode page transcripts"
git push origin main
```

如需同步 5090D：

```bash
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && git pull --ff-only && git status --short --branch'
```

## 验收标准

- `source.type=episode_page` 能从 fixture episode 页面解析 transcript 链接并保存干净 `raw.txt`。
- `source.type=episode_page` 能处理页面本身就是 transcript 页的 fixture。
- 缺少 transcript 的 episode 页面会失败，错误清晰，不尝试 ASR。
- 真实 99% Invisible episode 页面 transcript-only smoke 成功。
- `babelecho run --source-config "$tmpdir/source.yaml" --to-stage adapt` 可复用现有后续 pipeline。
- 全量测试通过。

## 风险和分支处理

- 如果某网站 transcript 需要 JavaScript 渲染：第一版标记不可处理，不引入浏览器自动化。
- 如果页面正文抽取夹杂导航：先收紧容器选择，不做复杂网页清洗框架。
- 如果不同站点结构差异很大：新增后续子计划做站点 profile，不在 02.04.01 内扩展。
- 如果真实页面反爬或超时：保留 fixture 覆盖，真实 smoke 标记为网络依赖失败，不阻塞本地功能测试。
