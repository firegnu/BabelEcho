# 02.09 Transcript Candidate Cleaning 计划

状态：`planned`

日期：2026-06-18

父计划：`02-real-podcasts`

## 目标

提高用户点播某一期节目时拿到可用 transcript 的成功率。

当前 `episode convert` 已能把 URL / source YAML / transcript file 跑进完整 pipeline，但真实节目经常卡在 transcript 层：

- RSS 或页面没有显式 transcript。
- 页面有 transcript，但 HTML 结构导致 speaker 丢失。
- YouTube captions 过碎，可能生成几千个小 segment。
- 页面混入 show notes、导航、广告、章节、播放器文案。
- VTT / SRT / TXT / HTML / JSON 的结构差异很大，直接 normalize 容易质量不稳定。

本计划新增一层 transcript candidate discovery + cleaning：

```text
episode URL / source YAML / transcript file
-> collect transcript candidates
-> score and select best candidate
-> clean and repair transcript text/timing/speaker labels
-> normalize to stable transcript/normalized.json
-> existing DeepSeek / TTS / publish pipeline
```

## 范围

In:

- 从现有来源收集多个 transcript candidates：
  - RSS `podcast:transcript`
  - PodcastIndex `transcripts[]` / `transcriptUrl`
  - episode page transcript link / inline transcript
  - YouTube public captions / auto captions
  - local transcript file
- 对候选做 deterministic scoring，不先引入 LLM 评分。
- 写 run-local `transcript/candidates.json`，记录每个候选的来源、格式、评分、选择结果、警告和失败原因。
- 清洗并生成 run-local cleaned transcript，例如 `transcript/cleaned.vtt` 或 `transcript/cleaned.txt`。
- 修复 YouTube captions 过碎问题：合并相邻 cue，避免一句话被切成多段。
- 修复常见 HTML transcript speaker 丢失问题，例如 `<cite>Speaker:</cite><time>...</time><p>Text</p>`。
- 让 `episode convert` 输出更清楚的 transcript 诊断信息。

Out:

- 不做 ASR。
- 不下载 YouTube 音频。
- 不抓 Spotify 私有内容。
- 不抓 Apple Podcasts App 内自动 transcript。
- 不做 JS 渲染页面抓取；需要 JS 的页面先明确失败。
- 不做多 episode 批处理或订阅扫描。
- 不改 DeepSeek prompt、TTS 路由或发布格式。

## 设计原则

- 先 deterministic，后续确有必要再考虑 LLM 参与质量判断。
- 保留原始 raw transcript，不覆盖原始下载内容。
- cleaning 只改 transcript 结构和噪声，不做中文改写。
- 失败要可解释：用户应知道是没有 transcript、候选太短、HTML 不像 transcript，还是 YouTube 没字幕。
- 现有 source types 继续可用，旧的单候选路径不要被破坏。

## 建议文件

新增：

```text
src/babelecho/transcript_candidates.py
src/babelecho/transcript_cleaning.py
tests/test_transcript_candidates.py
tests/test_transcript_cleaning.py
```

修改：

```text
src/babelecho/ingest.py
src/babelecho/transcript.py
src/babelecho/episode_page.py
src/babelecho/youtube.py
src/babelecho/cli.py
tests/test_ingest.py
tests/test_episode_page.py
tests/test_youtube.py
tests/test_episode_convert.py
docs/plans/README.md
docs/roadmap.md
resume-prompt.md
```

## 数据结构

建议新增 `TranscriptCandidate`：

```text
source_type: rss | podcast_index | episode_page | youtube_captions | transcript_file
source_url: string | null
raw_path: string | null
format: vtt | srt | txt | html | json | unknown
language: string | null
title: string | null
score: number
selected: boolean
warnings: list[string]
rejection_reason: string | null
text_char_count: number
segment_count_estimate: number
speaker_count_estimate: number
has_timestamps: boolean
```

写入：

```text
workspace/runs/<run-id>/transcript/candidates.json
workspace/runs/<run-id>/transcript/raw.<ext>
workspace/runs/<run-id>/transcript/cleaned.<ext>
workspace/runs/<run-id>/transcript/normalized.json
```

## 评分规则

第一版用简单权重，保持可测试：

- 加分：
  - 明确 transcript source，例如 RSS `podcast:transcript` 或 PodcastIndex `transcripts[]`。
  - 格式是 VTT/SRT/TXT 且正文长度足够。
  - 检测到多个 speaker labels。
  - 检测到 timestamps。
  - language 匹配 `en`。
- 扣分：
  - 文本太短，例如低于 1,000 chars。
  - show notes 噪声明显，例如大量 links、subscribe、sponsors、chapters，但少量完整句子。
  - YouTube cue 数量极高且平均每 cue 过短。
  - HTML 只有页面 fallback blocks，没有 transcript container 或 transcript URL 线索。
  - 重复行比例高。
  - 解析后 segment 数为 0。

第一版不需要分数特别聪明，关键是能解释为什么选这个候选、为什么拒绝其他候选。

## 可执行步骤

### 1. Candidate model 和 artifact

- 新增 `src/babelecho/transcript_candidates.py`。
- 增加 `TranscriptCandidate` 和 `write_candidates_json()`。
- 在 `ingest_transcript_source()` 成功写 raw transcript 时，同时写 `transcript/candidates.json`。
- 测试：
  - `tests/test_transcript_candidates.py`
  - 验证 JSON 包含 selected candidate、score、warnings。

### 2. Candidate collection adapter

- 给现有来源补 candidate collection：
  - `podcast_rss`：收集 RSS item 内所有 `podcast:transcript`，而不是只取第一个。
  - `podcast_index_episode` / `podcast_index_api`：收集 `transcripts[]` 和 `transcriptUrl`。
  - `episode_page`：收集 inline transcript、transcript link 页面、直接 transcript 页面。
  - `youtube_captions`：把下载到的 caption 文件作为 candidate。
  - `transcript_file`：本地文件作为最高可信 candidate。
- 保留旧路径行为：如果只有一个 candidate，行为和现在一致。
- 测试：
  - RSS 多 transcript 标签时选择英文 VTT/SRT/TXT。
  - PodcastIndex 有 `transcripts[]` 和 `transcriptUrl` 时都进入 candidates。
  - 找不到任何 candidate 时错误包含 attempted sources。

### 3. Cleaning pipeline

- 新增 `src/babelecho/transcript_cleaning.py`。
- 输入 raw transcript path + format + candidate metadata。
- 输出 cleaned transcript path。
- 清洗规则：
  - 标准化换行和空白。
  - 去除 WebVTT `NOTE`、`STYLE`、`REGION`、cue settings 噪声。
  - 去掉明显重复 caption 行。
  - 去掉纯导航、播放器、订阅、广告模板段落。
  - 保留 speaker label 和 timestamps。
- `normalize_transcript()` 改为优先读取 cleaned transcript。
- 测试：
  - VTT metadata 被清理。
  - 重复 caption 被去重。
  - 正常正文不被过度删除。

### 4. YouTube caption 合并

- 在 cleaning 或 normalize 阶段把过碎 VTT/SRT cue 合并。
- 合并条件：
  - 相邻 cue 时间间隔小。
  - 当前文本未以句末标点结束。
  - 合并后不超过 `max_chars`，例如 350-500 chars。
  - 合并后不超过 `max_duration_ms`，例如 30-45 秒。
- 避免：
  - 不跨明显 speaker label 合并。
  - 不把广告/章节标题合并进正文。
- 测试：
  - 20 个碎 cue 合并成少量稳定 segments。
  - 合并后保持时间从第一个 cue start 到最后一个 cue end。
  - 原始顺序不乱。

### 5. HTML transcript speaker repair

- 扩展 `src/babelecho/episode_page.py` 的 parser。
- 支持结构：
  - `<cite>Speaker:</cite><time>...</time><p>Text</p>`
  - `<div class="speaker">Speaker</div><p>Text</p>`
  - transcript 容器中的 list/table block。
- 输出 raw text 时恢复为：

```text
Speaker: Text

Speaker 2: Text
```

- 测试：
  - Practical AI 风格 `<cite>` speaker 不丢失。
  - `time` 文本不进入 TTS 正文。
  - show notes / page nav 不进入 transcript。

### 6. Quality gate

- 在 normalize 后增加 transcript quality summary。
- 如果 segment 数过多、平均长度过短、全文太短或 speaker 全丢失，给 warning；严重时失败。
- 写入 `run.json` 或 `candidates.json`：

```text
normalized_segments
avg_chars_per_segment
speaker_count
warnings
```

- 测试：
  - 空 transcript 失败。
  - 只有 show notes 的 HTML 失败。
  - 4000+ 微小 captions 触发 warning 或被合并后通过。

### 7. CLI 诊断输出

- `babelecho episode convert` 和 `babelecho run` 的 ingest/normalize 输出增加：

```text
transcript candidates: 3
selected transcript: youtube_captions/en/vtt score=...
warnings: ...
cleaned transcript: workspace/runs/<run-id>/transcript/cleaned.vtt
```

- 失败时输出：

```text
No usable transcript candidate found.
attempted:
- episode_page: no transcript link
- youtube_captions: no subtitles downloaded
```

### 8. Fixture tests

新增 fixtures：

```text
tests/fixtures/transcripts/youtube-fragmented.vtt
tests/fixtures/transcripts/practicalai-cite.html
tests/fixtures/transcripts/show-notes-only.html
tests/fixtures/transcripts/rss-multiple-transcripts.xml
```

测试命令：

```bash
.conda/babelecho-dev/bin/python -m pytest \
  tests/test_transcript_candidates.py \
  tests/test_transcript_cleaning.py \
  tests/test_episode_page.py \
  tests/test_youtube.py \
  tests/test_transcript.py \
  tests/test_episode_convert.py -q
```

最终跑：

```bash
.conda/babelecho-dev/bin/python -m pytest -q
```

### 9. 真实 smoke

分三步，不一上来跑完整 TTS：

1. YouTube captions 真实 smoke：
   - 只跑到 `normalize` 或 `adapt`。
   - 验证碎片合并后 segment 数合理。
2. Episode page HTML 真实 smoke：
   - 使用 Practical AI 或类似 `<cite>` speaker 页面。
   - 验证 speaker 保留。
3. RSS / PodcastIndex 多 transcript candidate smoke：
   - 验证 `candidates.json` 记录多个候选和选择原因。

只有 transcript 质量可接受后，再选一个真实 episode 跑完整 DeepSeek/TTS。

## 验收标准

- 用户输入一个 supported episode URL 后，系统能列出并记录所有 transcript candidates。
- 有多个 candidates 时，系统能选择最可信 candidate，并说明选择原因。
- YouTube captions 不再直接生成几千个 TTS segments。
- Practical AI 风格 HTML speaker 不再丢失。
- show notes-only 页面不会被误判为 transcript。
- `workspace/runs/<run-id>/transcript/candidates.json` 和 cleaned transcript 可用于排查。
- 现有 full pipeline tests 仍通过。

## 风险和边界

- 评分规则可能误选：第一版必须把候选和分数写清楚，便于手工发现问题。
- HTML 结构千差万别：只支持常见 transcript pattern，不做无限站点特化。
- YouTube 自动字幕可能语义错误：本计划只修结构，不修语义。
- JS 渲染页面仍不支持：第一版明确失败，后续再决定是否加 Playwright optional source。
- 不做 ASR：无 transcript 的 episode 仍会失败。

## 后续

- 如果 deterministic scoring 不够，再考虑每集一次 LLM transcript quality review。
- 如果用户经常输入 Apple Podcasts / Spotify 链接，再做 canonical RSS/feed 反查增强。
- 如果 transcript source 很多，再加 per-site adapters，但必须先有通用 candidate/cleaning 层。
