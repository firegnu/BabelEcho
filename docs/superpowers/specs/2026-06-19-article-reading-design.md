# Article Reading Route 设计

日期：2026-06-19

## 目标

新增一条独立的文章朗读后端路线，把用户在网站、blog 或手动保存的英文文章转换成中文 TTS 音频。默认风格是“忠实朗读版”：尽量保留作者原文的信息、顺序、观点、例子、术语、数字和引用，只做网页噪声清理、英文到中文转换、中文 TTS 友好的断句和轻微口语化。

这条路线的产物必须发布到 `workspace/published/`，并兼容现有前端 artifact contract。它不应破坏已经跑通的 YouTube、RSS、Apple Podcasts/iTunes、episode page 标准播客来源，也不应和未来 ASR、声纹、speaker diarization 路线互相污染。

## 非目标

- 不做订阅扫描或批量文章抓取。
- 第一版不做 X URL 自动抓取，只支持把 X/thread 内容复制为本地 `.txt` 或 `.md` 后导入；后续如做 X URL，必须作为可选 `x_api_v2` adapter，不走网页硬抓。
- 不做网页登录、付费墙绕过、浏览器自动化或 JS 渲染。
- 不把文章改写成主持人播客、解读节目或评论节目。
- 不做多人 speaker 识别；文章路线第一版固定为单人 narrator。
- 不改变 `episode convert`、`podcast_rss`、`youtube_captions`、`episode_page`、`audio_first` 的语义。

## 阶段计划

### Phase 1：文章 URL 与本地文章文件

先实现最稳定、最通用的 article-reading route：

- `web_article`：普通网站、blog、技术文章、新闻文章 URL，经 `trafilatura` 抽取正文。
- `article_file`：用户复制保存的 `.txt` / `.md`，包括 X/thread 手动复制内容。
- 默认 narrator 音色固定 `female_a`。
- 必须通过现有两道门槛：`normalize` 后 quality gate，`adapt` 后 script QA。
- 最终产物进入 `workspace/published/`，兼容前端 artifact contract。

### Phase 2：可选 X API adapter

如果用户愿意配置 X Developer/API 凭证，再单独实现：

```text
x_post
x_thread
```

provider：

```text
x_api_v2
```

这条 adapter 只负责把 X post/thread 转成 article-reading 的 canonical segments，后续仍复用同一条 `article_reading` 后流程：

```text
X URL -> parse post id -> X API lookup/search -> x_post/x_thread source -> normalize quality gate -> DeepSeek -> script QA -> female_a TTS -> publish
```

约束：

- X token 只从环境变量或 ignored local config 读取，不提交。
- 没有 token、余额、权限或 rate limit 时，X adapter 明确失败，不影响 `web_article` / `article_file`。
- 不做 X 网页 DOM 抓取、登录 cookie 抓取、Playwright 自动展开 thread 或绕过限制。
- 第一版 X API adapter 可先只支持单个 public post URL；thread 重建作为第二步。
- X API 的实际可用范围以用户账号、developer access、pricing credits 和 endpoint 权限为准。

相关官方文档：

- `https://docs.x.com/x-api/getting-started/getting-access`
- `https://docs.x.com/fundamentals/authentication/oauth-2-0/application-only`
- `https://docs.x.com/x-api/getting-started/pricing`
- `https://docs.x.com/x-api/fundamentals/conversation-id`
- `https://docs.x.com/x-api/posts/get-posts-by-ids`

## 为什么 X Phase 1 不抓 URL

X 的内容可以以后单独做，但不应该混进文章路线第一版：

- X 网页不是稳定的文章页面。它更接近动态社交流，thread 展开、引用、回复、图片上下文和登录态会影响实际可见内容。
- 直接抓网页容易引入浏览器自动化、登录 cookie、反爬和不完整 thread 问题，这和当前 local-first、单 URL 自用的低风险目标不匹配。
- 官方 X API 是另一条 credentialed source adapter，需要 developer account、App、Bearer Token 或用户授权；这和普通文章 URL 抽取不是同一个问题。

因此 Phase 1 采用最稳的自用路径：用户把 X/thread 正文复制成 `.txt` 或 `.md`，BabelEcho 按 `article_file` 处理。这样能覆盖“我看到好内容想听”的核心需求，同时不把 X 平台细节带进文章抽取器。Phase 2 如果做 X URL，也只走官方 API adapter，不作为普通网页抽取的一部分。

## Route 与来源类型

新增 route：

```text
article_reading
```

新增和预留 source type：

```text
web_article
article_file
x_post
x_thread
```

`web_article` 表示从公开网页 URL 抽取正文；`article_file` 表示从本地 `.txt` 或 `.md` 文件读取正文；`x_post` / `x_thread` 是 Phase 2 预留的 X API 来源类型。所有来源最终都进入同一条 article-reading 后流程。

Provider 值：

```text
trafilatura
local_file
x_api_v2
```

`trafilatura` 是第一版主抽取器，用于普通文章页、blog、新闻页、技术文章页的正文和 metadata 抽取。`local_file` 用于用户手动保存的 `.txt` / `.md`。`x_api_v2` 是 Phase 2 预留 provider，只有在用户明确配置 X API 凭证后才启用。Mozilla Readability 和 python-readability 先不接入主路径；如果后续真实样本证明 `trafilatura` 覆盖不足，再作为 fallback 单独评估。

## CLI 入口

新增独立命令，避免把文章路线塞进 `episode convert`：

```text
babelecho article convert --url <article-url> --run-id <run-id> --local-config <config> --to-stage <stage>
babelecho article convert --file <path/to/article.md> --title <title> --run-id <run-id> --local-config <config> --to-stage <stage>
```

说明：

- `--url` 和 `--file` 二选一。
- `--to-stage normalize` 是推荐的低成本预检入口；只有质量报告通过后才进入 DeepSeek 和 TTS。
- `--from-stage` 后续可以复用现有 run 恢复能力，从 `adapt`、`synthesize`、`assemble` 或 `publish` 继续。
- 第一版默认 narrator 音色固定为 `female_a`，也就是当前 `CosyVoice-300M-SFT` 的自然女声路线。文章朗读不启用 speaker voice 推断。如果需要临时换音色，优先复用现有 config 里的 default voice role 机制，不新增一套文章专用音色系统。
- Phase 2 如实现 X API adapter，应继续复用 `babelecho article convert --url <x-url>`，但 URL dispatch 到 `source.type=x_post` 或 `x_thread`，而不是 `web_article`。

## 数据流

文章路线仍然是分阶段后端流水线：

```text
extract/ingest -> clean/normalize -> pre-adapt quality gate -> adapt -> pre-TTS script validation -> synthesize -> assemble -> publish
```

它有两道硬门槛：

1. `normalize` 后的 extraction/quality gate：复用现有 `transcript/quality.json` 决策方式，判断抽取正文是否可靠，是否允许进入 DeepSeek。
2. `adapt` 后的 script validation：复用现有 `babelecho check --checks script` / run 内置脚本 QA，判断中文忠实朗读稿是否干净、完整，是否允许进入 TTS。

任一门槛不通过，都停止在当前阶段，不调用后续昂贵资源。文章路线只在这两个现有 checkpoint 上增加文章特有检查项，不新建一套和播客路线平行的门禁系统。

### 1. Ingest

`web_article`：

1. 下载 URL HTML。
2. 使用 `trafilatura` 抽取正文和 metadata。
3. 写入 run-local 文件：
   - `article/source.html`：原始 HTML，便于排查，可选。
   - `article/extracted.json`：抽取结果和 metadata。
   - `article/raw.txt`：抽取后的英文正文纯文本。
4. 写入 `source.json`，只记录公开 URL、source type、provider、标题、作者、站点、发布时间、excerpt 和抽取器信息，不写本机路径、配置路径或凭证。

`article_file`：

1. 读取本地 `.txt` 或 `.md`。
2. 去掉明显 Markdown front matter、空行噪声和重复标题。
3. 写入 `article/raw.txt` 和 `source.json`。
4. `source.json` 不暴露用户本机绝对路径；可以记录 `input_kind=article_file` 和用户传入标题。

`x_post` / `x_thread`：

1. 解析 X URL 中的 post id。
2. 使用 X API v2 和用户本地 token 获取 post 文本、作者、时间、引用/回复关系和必要 metadata。
3. 单 post 先生成一段或少量段落；thread 后续按作者和时间顺序重建为多段。
4. 写入 `article/raw.txt`、`article/extracted.json` 和 `source.json`。
5. `source.json` 可以记录公开 X URL、post id、author username、created_at 和 provider，但不能记录 token、credential 文件路径或请求 header。

### 2. Normalize

把文章正文转成现有后流程能消费的段落结构：

```json
{
  "source_type": "web_article",
  "language": "en",
  "segments": [
    {
      "id": "0001",
      "speaker": "Narrator",
      "text": "..."
    }
  ]
}
```

段落规则：

- 保留原文段落顺序。
- 标题、小标题可以作为独立短段，便于 TTS 断句。
- 列表项可以合并为自然段，也可以保留为短段；不能丢失项目内容。
- 代码块、表格和脚注第一版不做复杂朗读优化；能安全转成文本就保留，无法可靠处理时在 quality warning 里提示。
- 太长的段落按句子边界切分，避免单段超出 DeepSeek/TTS 稳定长度。

### 3. Quality Gate

DeepSeek 前必须生成 `transcript/quality.json`。推荐状态仍为：

```text
safe_to_adapt
inspect_first
reject
```

第一版检查：

- 正文字符数是否过少。
- 段落数是否为 0。
- URL 抽取是否疑似拿到导航、广告、评论区或相关文章列表。
- 是否包含大量 cookie/newsletter/subscribe/share/navigation 文本。
- 是否含有明显登录墙、付费墙或错误页文本。
- 单段是否过长。

只有 `safe_to_adapt` 默认进入 DeepSeek。`inspect_first` 需要用户显式确认或先停在 `normalize` 人工检查；`reject` 直接失败，不调用 LLM/TTS。

### 4. Adapt

新增文章专用 adapt prompt 或 input kind：

```text
article_faithful_reading
```

约束：

- 忠实翻译，不总结、不扩写、不评论。
- 保留作者的结构、论证顺序和重要措辞。
- 保留专有名词、产品名、人名、数字、引用、链接含义。
- 删除网页噪声：导航、广告、cookie、newsletter、版权尾巴、推荐阅读。
- 把 URL、缩写、代码名、数字写成 TTS 友好的中文朗读形式，但不能改变含义。
- 输出 segment id 必须和输入一一对应，沿用当前 chunked adapt 的 id 校验和重试机制。

输出仍写到：

```text
script/zh.json
```

### 5. Pre-TTS Script Validation

进入 TTS 前必须验证 `script/zh.json`。这一步类似现有 YouTube/播客路线的 script QA，但增加文章路线的检查项：

- segment id 必须和输入一一对应，不能丢段、并段或乱序。
- 每段必须有中文朗读文本，不能是空字符串。
- 不能残留 HTML tag、Markdown front matter、导航菜单、cookie/newsletter/subscribe/share 这类网页噪声。
- 不能残留明显整段英文；专有名词、产品名、代码名和短引用可以保留。
- URL、缩写、文件格式和数字读法要适合 TTS，例如域名点号和 `MP3` 不能被错误中文化。
- 单段长度不能超过 TTS 稳定阈值。
- narrator speaker 必须稳定为 `Narrator`。

如果验证失败，run 停在 `adapt` 或 `check` 后，不进入 TTS。用户可以检查 `script/zh.json`，必要时人工编辑后从 `synthesize` 继续。

### 6. Synthesize / Assemble

文章路线固定为单 narrator：

- `speaker` 固定为 `Narrator`。
- 不启用 speaker voice 推断。
- 不启用 ASR speaker diarization。
- 不启用声纹或 voice clone。
- 默认 `voice_role` 固定为 `female_a`，走当前 `CosyVoice-300M-SFT` 女声。
- TTS 后流程复用现有 `synthesize -> assemble`。

### 7. Publish

发布到现有稳定目录：

```text
workspace/published/episodes/<run-id>/
  audio.mp3
  metadata.json
  transcript.en.json
  transcript.zh.json
  artifact.json
```

`artifact.json` 兼容现有前端契约，关键字段建议如下：

```json
{
  "schema_version": "1.0",
  "run_id": "<run-id>",
  "route": "article_reading",
  "status": "succeeded",
  "title": "<article title>",
  "source": {
    "type": "web_article",
    "provider": "trafilatura",
    "input_url": "https://example.com/article",
    "site_name": "Example",
    "author": "Author Name",
    "published_time": "2026-06-19"
  },
  "quality": {
    "recommendation": "safe_to_adapt",
    "metrics": {
      "segment_count": 24,
      "speaker_count": 1,
      "total_chars": 12000,
      "extractor": "trafilatura"
    }
  },
  "speakers": [
    {
      "id": "speaker_1",
      "display_name": "Narrator",
      "segment_count": 24,
      "voice_role": "female_a",
      "inferred_gender": "unknown"
    }
  ],
  "asr": null,
  "ui": {
    "default_tab": "script",
    "badges": ["article-reading", "safe-to-adapt"]
  }
}
```

`index.json` 里的 episode entry 只需要新增：

```text
route=article_reading
source_type=web_article 或 article_file
speaker_count=1
```

前端遇到未知 route/source type 已按契约要求通用展示；实现后仍应同步 `docs/前端Artifact契约与只读界面说明.md`，把 `article_reading`、`web_article` 和 `article_file` 写成正式支持值。

## 错误处理

- URL 下载失败：停在 ingest，写明 HTTP/网络错误。
- 正文抽取失败：停在 ingest 或 normalize，不进入 DeepSeek。
- 抽取正文过短或疑似网页噪声：写 `quality.recommendation=inspect_first` 或 `reject`。
- DeepSeek 返回缺 segment id：沿用当前 chunked retry。
- pre-TTS script validation 失败：停在 adapt/check 后，不调用 TTS。
- TTS 失败：沿用现有 run stage failure 和 `--from-stage synthesize` 恢复方式。

## 测试策略

单元测试：

- `web_article` source config 可以写出 `source.json`、`article/raw.txt` 和 `article/extracted.json`。
- `article_file` 可以从 `.txt` 和 `.md` 生成 canonical segments。
- Phase 2 的 `x_post` 可以从 fixture X API JSON 生成 canonical segments，且不需要真实 token。
- normalize 能按段落顺序保留标题、段落和列表内容。
- quality gate 能拦截空正文、过短正文、登录墙/错误页和明显导航噪声。
- article adapt prompt 使用忠实朗读约束，并保持 id 一一对应。
- pre-TTS script validation 能拦截缺段、网页噪声、HTML/Markdown 残留、明显英文残留和超长段。
- article route 默认 narrator voice role 为 `female_a`，不调用 speaker voice 推断。
- publish artifact 能生成 `route=article_reading`、`source.type=web_article/article_file`、单 narrator speaker 和稳定 index entry。

集成 smoke：

- 使用 fixture HTML，不访问网络，跑到 `normalize`。
- 使用 fixture `.md`，跑到 `adapt` 的 fixture LLM。
- 使用 1 条真实公开英文文章 URL，先只跑到 `normalize` 检查抽取质量；确认后再在 5090D 跑一条短文章 full-chain。
- Phase 2 只在用户提供 X API token 后做真实 X URL smoke；没有 token 时跳过，不影响 Phase 1 验收。

回归：

- 现有 YouTube、RSS、Apple Podcasts/iTunes、episode page 测试不能变。
- 现有 `publish` sidecar 测试需要追加 article case，但不能改掉 transcript-first 的断言。

## 实施边界

推荐新增小模块，而不是修改现有播客解析器：

```text
src/babelecho/article.py
src/babelecho/article_extract.py
tests/test_article.py
```

必要共享点：

- 可以复用现有 run stage、status、checks、chunked adapt、TTS、assemble 和 publish。
- 可以给 publish artifact 的 route/source type 增加 article 值。
- 不把文章 URL 自动塞进 `episode convert`。
- 不把 `episode_page` parser 改成通用 article parser。

这样文章路线、transcript-first 播客路线和未来 audio-first 路线在入口和 source type 上隔离，在 publish artifact 上兼容。

## 第一版验收标准

1. `babelecho article convert --file sample.md --to-stage publish` 可用 fixture LLM/TTS 跑通，并生成兼容的 `artifact.json` 和 `index.json`。
2. `babelecho article convert --url <public-article-url> --to-stage normalize` 能抽取正文、metadata 和质量报告。
3. 一篇真实公开英文文章必须先通过 `normalize` 后质量门槛，再通过 `adapt` 后 script validation，之后才允许进入 TTS。
4. 5090D 上使用一篇不太长的真实英文文章跑通 DeepSeek -> `female_a` TTS -> publish。
5. 现有全量测试通过。
6. `docs/前端Artifact契约与只读界面说明.md` 同步新增 article route/source type。

Phase 2 X API adapter 的独立验收：

1. 用户提供 X API token 后，`babelecho article convert --url <x-post-url> --to-stage normalize` 可以生成 `source.type=x_post` 的 normalized segments 和 quality report。
2. 没有 token 或 API 返回权限/余额/rate-limit 错误时，run 明确失败在 ingest，不进入 DeepSeek。
3. X route 的后流程仍然通过同一套 quality gate、script QA、`female_a` TTS 和 publish artifact。
4. 不实现 X 网页硬抓或登录态浏览器自动化。
