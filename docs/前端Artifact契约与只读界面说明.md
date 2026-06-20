# 前端 Artifact 契约与只读界面说明

日期：2026-06-19

## 目的

本文定义 BabelEcho 后端可以稳定交给前端读取的 artifact contract。目标是让前端或设计 agent 只依赖公开产物目录，不需要理解 YouTube、RSS、Apple Podcasts/iTunes、episode page、DeepSeek、ASR、TTS 或 5090D 的内部细节。

Phase 2 的前端第一版是只读界面：浏览、播放、下载和检查已生成的中文播客产物。它不提交 URL，不触发转换，不控制后端任务。

## 边界

前端只读：

- `workspace/published/`

前端不读：

- `workspace/config/`
- `workspace/sources/`
- `workspace/runs/` 内部工作文件
- `.env`、API key、本地模型路径、SSH 信息

前端不执行：

- `babelecho episode convert`
- `babelecho run`
- DeepSeek adapt
- ASR / diarization
- TTS / assemble / publish

后端可以继续把内部文件写在 `workspace/runs/<run-id>/`，但必须把前端需要的稳定副本发布到 `workspace/published/`。

## 现有公开产物

当前后端会在 publish 阶段生成或同步这些文件：

```text
workspace/published/
  feed.xml
  index.json
  episodes/
    <run-id>/
      audio.mp3
      metadata.json
      transcript.en.json
      transcript.zh.json
      artifact.json
```

其中 `index.json` 和 `artifact.json` 是前端 sidecar。它们不改变现有 `feed.xml`、MP3、metadata 和 transcript 文件，只为只读前端提供稳定入口：

```text
workspace/published/
  index.json
  episodes/
    <run-id>/
      artifact.json
```

`index.json` 是前端列表页入口；`artifact.json` 是单集详情页入口。

## 当前实现状态

当前 `schema_version=1.0` 已在 `src/babelecho/publish.py` 的 publish 阶段实现。每次成功 publish 时，后端会自动写入：

- `workspace/published/episodes/<run-id>/artifact.json`
- `workspace/published/index.json`

这一步只追加前端 sidecar，不改变现有 MP3、RSS feed、metadata、transcript 或前面各阶段的业务语义。

当前本机 `workspace/published/` 已有三条真实前端测试数据：

| run_id | 来源 | 标题 | segments | speakers | 时长 | 音频 |
| --- | --- | --- | --- | --- | --- | --- |
| `article-anthropic-infra-noise-20260619` | Anthropic 技术文章 | Quantifying infrastructure noise in agentic coding evals \ Anthropic | 33 | 0 | 684.849342 秒 | 22050 Hz mono MP3 |
| `frontend-publish-practical-ai-faithful-sidecar-20260619` | Practical AI RSS | The AI engineer skills gap | 103 | 5 | 2372.179592 秒 | 22050 Hz mono MP3 |
| `frontend-publish-podnews-sidecar-20260619` | Podnews RSS | A new AMP member | 18 | 0 | 231.523265 秒 | 22050 Hz mono MP3 |

三条样本的 `quality.recommendation` 都是 `safe_to_adapt`。前端 agent 可以直接以这三条作为列表、播放器、脚本、英文对照、质量报告、多 speaker 展示和无 speaker 文章朗读展示的 fixture。

## 路径原则

- 路径都是相对路径，但 base 目录按文件区分：
  - `index.json` 里的 `audio_path` / `artifact_path` 相对 `workspace/published/`，例如 `episodes/<run-id>/audio.mp3`。
  - `artifact.json` 里的 `media.audio_path`、`artifacts.*` 相对该集自身目录 `workspace/published/episodes/<run-id>/`，例如 `audio.mp3`、`../../feed.xml`。
  - 同名字段 `audio_path` 在两个文件里 base 不同，前端解析时不要混用。
- 不在公开 JSON 里写本机绝对路径。
- 不在公开 JSON 里写远端 5090D 路径。
- 不在公开 JSON 里写 API key、env 文件、模型路径或真实 config 路径。
- `workspace/runs/<run-id>/` 只作为后端内部目录；前端不直接依赖它。

## `index.json`

位置：

```text
workspace/published/index.json
```

用途：

- 前端启动时读取。
- 渲染 episode 列表。
- 提供每一集的最小展示信息和详情入口。
- 列表默认按 `published_at` 倒序排列（最新在前）；当前本机文件即按此顺序，article 集在最前。

示例：

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-19T13:01:30Z",
  "title": "BabelEcho",
  "description": "Locally generated Chinese podcast artifacts.",
  "episodes": [
    {
      "run_id": "article-anthropic-infra-noise-20260619",
      "title": "Quantifying infrastructure noise in agentic coding evals \\ Anthropic",
      "route": "article_reading",
      "status": "succeeded",
      "source_type": "web_article",
      "quality_recommendation": "safe_to_adapt",
      "speaker_count": 0,
      "duration_seconds": 684.849342,
      "published_at": "2026-06-19T13:01:30Z",
      "audio_path": "episodes/article-anthropic-infra-noise-20260619/audio.mp3",
      "artifact_path": "episodes/article-anthropic-infra-noise-20260619/artifact.json"
    },
    {
      "run_id": "frontend-publish-practical-ai-faithful-sidecar-20260619",
      "title": "The AI engineer skills gap",
      "route": "transcript_first",
      "status": "succeeded",
      "source_type": "podcast_rss",
      "quality_recommendation": "safe_to_adapt",
      "speaker_count": 5,
      "duration_seconds": 2372.179592,
      "published_at": "2026-06-19T10:13:37Z",
      "audio_path": "episodes/frontend-publish-practical-ai-faithful-sidecar-20260619/audio.mp3",
      "artifact_path": "episodes/frontend-publish-practical-ai-faithful-sidecar-20260619/artifact.json"
    },
    {
      "run_id": "frontend-publish-podnews-sidecar-20260619",
      "title": "A new AMP member",
      "route": "transcript_first",
      "status": "succeeded",
      "source_type": "podcast_rss",
      "quality_recommendation": "safe_to_adapt",
      "speaker_count": 0,
      "duration_seconds": 231.523265,
      "published_at": "2026-06-19T10:00:57Z",
      "audio_path": "episodes/frontend-publish-podnews-sidecar-20260619/audio.mp3",
      "artifact_path": "episodes/frontend-publish-podnews-sidecar-20260619/artifact.json"
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | yes | 当前契约版本，第一版固定为 `1.0`。 |
| `generated_at` | string | yes | ISO 8601 时间，索引生成时间。 |
| `title` | string | yes | 前端可展示的站点标题。 |
| `description` | string | no | 前端可展示的简短说明。 |
| `episodes` | array | yes | 可展示 episode 列表。 |
| `episodes[].run_id` | string | yes | 后端 run id，也是前端稳定 episode id。 |
| `episodes[].title` | string | yes | 中文或原始 episode 标题。 |
| `episodes[].route` | string | yes | `transcript_first`、`article_reading` 或 `audio_first`。 |
| `episodes[].status` | string | yes | `succeeded`、`partial`、`failed`。列表页默认只展示 `succeeded`。 |
| `episodes[].source_type` | string | yes | 例如 `youtube_captions`、`episode_page`、`podcast_rss`、`web_article`、`article_file`、`audio_file`。 |
| `episodes[].quality_recommendation` | string | no | `safe_to_adapt`、`inspect_first`、`reject` 或 `unknown`。 |
| `episodes[].speaker_count` | number | no | speaker 数量，未知时可省略。 |
| `episodes[].duration_seconds` | number | no | 最终 MP3 时长。 |
| `episodes[].published_at` | string | no | publish 完成时间。 |
| `episodes[].audio_path` | string | yes | 相对 `workspace/published/` 的 MP3 路径。 |
| `episodes[].artifact_path` | string | yes | 相对 `workspace/published/` 的单集详情 JSON 路径。 |

## `artifact.json`

位置：

```text
workspace/published/episodes/<run-id>/artifact.json
```

用途：

- 单集详情页读取。
- 展示媒体、来源、质量、speaker、脚本和 transcript。
- 给前端提供完整但只读的数据入口。

示例：

```json
{
  "schema_version": "1.0",
  "run_id": "frontend-publish-podnews-sidecar-20260619",
  "route": "transcript_first",
  "status": "succeeded",
  "title": "A new AMP member",
  "summary": null,
  "created_at": null,
  "published_at": "2026-06-19T10:00:57Z",
  "source": {
    "type": "podcast_rss",
    "provider": "rss",
    "input_url": "https://podnews.net/rss",
    "episode_url": "https://podnews.net/update/amp-member",
    "transcript_url": "https://podnews.net/audio/podnews260618.mp3.vtt",
    "feed_url": "https://podnews.net/rss"
  },
  "quality": {
    "recommendation": "safe_to_adapt",
    "warnings": [],
    "reasons": [],
    "metrics": {
      "segment_count": 18,
      "speaker_count": 0,
      "total_chars": 4251,
      "avg_chars_per_segment": 236.2,
      "max_chars_per_segment": 279,
      "dirty_markup_count": 0,
      "html_entity_count": 0,
      "repeated_line_score": 0.0,
      "repeated_phrase_score": 0.003
    }
  },
  "media": {
    "audio_path": "audio.mp3",
    "mime_type": "audio/mpeg",
    "duration_seconds": 231.523265,
    "sample_rate": 22050,
    "channels": 1,
    "file_size_bytes": 3704834
  },
  "artifacts": {
    "metadata": "metadata.json",
    "transcript_en": "transcript.en.json",
    "script_zh": "transcript.zh.json",
    "feed": "../../feed.xml"
  },
  "speakers": [],
  "asr": null,
  "ui": {
    "default_tab": "script",
    "badges": ["transcript-first", "safe-to-adapt"]
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | yes | 当前契约版本。 |
| `run_id` | string | yes | 后端 run id。 |
| `route` | string | yes | `transcript_first`、`article_reading` 或 `audio_first`。 |
| `status` | string | yes | `succeeded`、`partial`、`failed`。 |
| `title` | string | yes | 单集标题。 |
| `summary` | string/null | no | 后续可由 LLM 或 RSS metadata 提供，第一版可为 `null`。 |
| `created_at` | string/null | no | run 创建时间；旧 run 或缺失 metadata 时可为 `null`。 |
| `published_at` | string | no | publish 完成时间。 |
| `source` | object | yes | 来源信息。只放公开 URL 和类型，不放内部 config。 |
| `quality` | object | no | 质量报告摘要。来自 `transcript/quality.json` 或 ASR 路线质量报告。`metrics` 是开放字段集，不同 route 可能含额外 key（如 `web_article` 多出 `source_type`、`extractor`），前端按字段存在性渲染，未知字段忽略。 |
| `media` | object | yes | 最终可播放音频信息；`media.audio_path` 相对该集目录（如 `audio.mp3`）。 |
| `artifacts` | object | yes | 前端可读的相对文件路径，均相对该集目录 `episodes/<run-id>/`（如 `audio.mp3`、`transcript.zh.json`、`../../feed.xml`）。 |
| `speakers` | array | yes | speaker 展示信息；无 speaker 时为空数组。 |
| `asr` | object/null | no | audio-first 路线的 ASR/diarization 摘要。transcript-first 路线为 `null`。 |
| `ui` | object | no | 非业务关键的前端提示，例如默认 tab、badge。 |

关于 `metadata.json`：当前只含最小字段（如 `episode_id`、`title`、`original_url`、`transcript_url`、`audio_url`），其中 `audio_url` 可能是占位值（例如 `https://example.com/...`）。前端播放只使用 `index.json` / `artifact.json` 里的 `audio_path`，不要依赖 `metadata.audio_url`。可下载产物以 MP3（`audio_path`）为主；`transcript.*.json` 与 `feed.xml` 建议以「查看 / 打开链接」形式提供，不必都做成下载按钮。

## Source Contract

`source.type` 当前已使用或预留值：

| 值 | 含义 |
| --- | --- |
| `youtube_captions` | YouTube / YouTube Podcasts 单集视频公开字幕。 |
| `episode_page` | 标准播客官网 episode 页面 transcript。 |
| `podcast_rss` | RSS feed item 内 transcript。Apple/iTunes 和直接 RSS 最终都归到这里。 |
| `transcript_file` | 用户本地 transcript file。 |
| `audio_file` | Phase 2 audio-first 本地音频文件。 |
| `web_article` | 文章朗读路线的公开网页正文。 |
| `article_file` | 文章朗读路线的本地 `.txt` / `.md` 正文文件。 |
| `x_post` | Phase 2 预留：通过 X 官方 API 获取的单条 post。 |
| `x_thread` | Phase 2 预留：通过 X 官方 API 获取的 thread。 |

`source.provider` 当前已使用或预留值：

| 值 | 含义 |
| --- | --- |
| `youtube` | YouTube 视频字幕。 |
| `rss` | 直接 RSS feed。 |
| `itunes_lookup` | Apple Podcasts/iTunes URL 经 iTunes Lookup 找到 RSS。 |
| `episode_page` | 官网页面。 |
| `local_file` | 本地文件。 |
| `trafilatura` | 文章朗读路线的网页正文抽取。 |
| `x_api` | Phase 2 预留：X 官方 API。 |

当前 Apple Podcasts/iTunes URL 会先解析成 RSS，再进入同一条标准播客后流程；发布后的 artifact 目前表现为 `source.type=podcast_rss`、`source.provider=rss`。`itunes_lookup` 只作为以后想显式展示原始解析器时的预留值。

前端只展示这些字段，不根据 provider 决定业务逻辑。

文章朗读路线使用 `route=article_reading`。该路线是独立后端管道，不做 speaker 识别；`speakers` 必须是空数组。`source` 可能额外包含 `site_name`、`author`、`published_time`、`excerpt`，前端可展示这些字段，缺失时忽略。

注意：当前唯一的 article fixture（`article-anthropic-infra-noise-20260619`）的 `source` 只有 `type`、`provider`、`input_url`、`episode_url`，上述 `site_name` / `author` / `published_time` / `excerpt` 全部缺失，`metadata.json` 也未提供。设计 article 详情页时应以「来源区基本只有一个 URL」为默认态，把作者 / 站点名 / 发布时间 / 摘要当作可缺失的增强字段，不要预设有富 metadata。

## Speaker Contract

`speakers` 示例：

```json
[
  {
    "id": "speaker_1",
    "display_name": "Jerod",
    "voice_role": "male_a",
    "inferred_gender": "male",
    "segment_count": 2
  },
  {
    "id": "speaker_2",
    "display_name": "Daniel",
    "voice_role": "male_b",
    "inferred_gender": "male",
    "segment_count": 14
  }
]
```

规则：

- `display_name` 可以来自 transcript speaker label，也可以是 `speaker_1`。
- `voice_role` 是 BabelEcho 固定中文音色角色，例如 `female_a`、`male_a`、`female_b`、`male_b`。
- `inferred_gender` 仅用于辅助展示，可为 `male`、`female`、`unknown` 或 `null`。
- 当前实现生成 `segment_count`；speaker 级 `duration_seconds` 暂不生成，前端如遇到该字段可展示，缺失时应忽略。
- 文章朗读路线不识别 speaker，不生成角色列表，`speakers=[]`。
- 不暴露声纹 embedding。
- 不暴露 run-local 原始 speaker profile 或 embedding 文件；如果 `artifacts.speaker_profiles` 存在，前端只读取 published 目录下的安全摘要文件。
- 不暗示真实身份识别。

## ASR / Diarization Contract

audio-first 路线以后可以填充 `asr`：

```json
{
  "model": "local-asr-model-name",
  "language": "en",
  "duration_seconds": 601.2,
  "segment_count": 96,
  "speaker_profiles": {
    "provider": "diarization_stats",
    "speaker_count": 3,
    "profile_kind": "diarization_stats",
    "embedding_status": "not_computed"
  },
  "diarization": {
    "enabled": true,
    "speaker_count": 3,
    "confidence": "medium"
  },
  "quality": {
    "recommendation": "inspect_first",
    "warnings": ["low_confidence_segments", "speaker_overlap_detected"]
  }
}
```

规则：

- 这个字段只做展示和人工判断。
- 前端不依赖具体 ASR 模型名做分支逻辑。
- 前端不展示或保存 voiceprint embedding。
- 如果 `artifacts.speaker_profiles` 存在，它指向 published episode 目录下的 speaker profile 摘要，例如 turn 数、总时长、首尾时间、`sample_count`、`sample_duration_ms`、`profile_kind` 和 `embedding_status`；前端可用于详情页展示 speaker 分布。
- `artifact.json.asr.speaker_profiles` 不包含 `embedding_artifact`。即使 published `speaker-profiles.json` 里出现 run-local 相对 `embedding_artifact` 元数据，前端也不能把它当作公开下载、播放或请求目标。
- `confidence` 第一版可以是粗粒度字符串：`high`、`medium`、`low`、`unknown`。

## Transcript / Script Contract

前端可以读取：

```text
workspace/published/episodes/<run-id>/transcript.en.json
workspace/published/episodes/<run-id>/transcript.zh.json
```

第一版建议前端只需要支持这两种常见结构：

```json
{
  "segments": [
    {
      "id": "0001",
      "speaker": "Host",
      "text": "..."
    }
  ]
}
```

和：

```json
[
  {
    "id": "0001",
    "speaker": "Host",
    "text": "..."
  }
]
```

如果后端后续统一结构，应优先使用对象包装：

```json
{
  "language": "zh-CN",
  "segments": []
}
```

实际文件里的 segment 还可能包含 `start_ms`、`end_ms`、`duration_ms`、`source`、`source_segment_ids`。`transcript.zh.json` 在该集经过 `assemble` 生成音频后，每段带 `start_ms`/`end_ms`/`duration_ms`（毫秒，基于各段中文 TTS 音频时长按拼接顺序累加，即中文 MP3 的时间轴）；尚未经过 assemble 的旧集这些字段缺失。`transcript.en.json` 的 `start_ms`/`end_ms` 是英文原音时间轴（仅 podcast 路线有真实值），与中文 MP3 不对齐，不用于中文跟读。前端可按需使用，未知或缺失时忽略。

前端展示建议：

- 中文脚本为默认 tab。
- 英文 transcript 可作为对照 tab。
- 长文本按 segment 渲染，不一次性拼成单个段落。
- 有 speaker 时显示 speaker 标签；无 speaker 时隐藏 speaker 列。
- 即使是有 speaker 的集，单个 segment 的 `speaker` 也可能为 `null`（过场、旁白、赞助口播衔接），null 段直接不显标签，不要显示「null」或空角色。
- 中文脚本段在该集经过 `assemble` 后含段级时间戳（`start_ms`/`end_ms`/`duration_ms`），前端据此启用「随播放高亮 + 自动滚动 + 点击段落 seek」（podcast 中文脚本与 `article_reading` 正文均支持）；无这些字段的旧集自动降级为静态展示。`transcript.en.json` 的时间戳是英文原音时间轴，与中文 MP3 不对齐，不用于中文跟读。
- `article_reading` 的中文「脚本」实际是文章正文 + 小标题段（如「我们是如何发现这一点的」这类短标题段），建议用阅读 / 正文排版，而非主持人转录行布局。

## 状态与质量展示

状态：

| 值 | 前端展示建议 |
| --- | --- |
| `succeeded` | 可播放。 |
| `partial` | 可检查，但可能没有最终音频。 |
| `failed` | 默认不出现在公开列表；如出现，只展示诊断，不播放。 |

质量建议：

| 值 | 前端展示建议 |
| --- | --- |
| `safe_to_adapt` | 正常状态。 |
| `inspect_first` | 显示需要复核的提示。 |
| `reject` | 显示不可处理原因，不建议播放。 |
| `unknown` | 显示“未生成质量报告”。 |

前端不应该把 `safe_to_adapt` 翻译成“绝对正确”；它只表示后端质量门禁允许进入后流程。

## 后端生成策略

当前后端已经在 publish 阶段追加 artifact 生成步骤：

1. 读取现有 `run.json`、`source.json`、`transcript/quality.json`、`segments/manifest.json`、`output/audio.mp3` 和 publish 目录文件。
2. 生成 `workspace/published/episodes/<run-id>/artifact.json`。
3. 扫描或维护 `workspace/published/episodes/*/artifact.json`。
4. 生成 `workspace/published/index.json`。

要求：

- 只读已有 run 产物。
- 只写公开 sidecar JSON。
- 不改变 `episode convert`、`run`、`normalize`、`adapt`、`synthesize`、`assemble` 的现有语义。
- 缺失可选字段时写 `null` 或省略，不让旧 run 无法发布。
- 如果以后需要给历史 published 目录补 sidecar，可以再做独立 refresh 命令；第一版前端不依赖这个命令。

## 只读前端设计 Brief

前端定位：

- 私有本地/局域网 artifact browser。
- 面向用户自己使用，不是公开 SaaS。
- 视觉上应像一个安静、清晰的播客资料库，而不是营销页。

建议信息架构：

1. Episode 列表页
   - 左侧或顶部筛选：route、source type、quality、speaker count。
   - 主列表显示标题、来源、时长、质量状态、发布时间。
   - 每项提供播放入口和详情入口。

2. Episode 播放页
   - 顶部显示标题、来源、状态 badge。
   - 中央是音频播放器。
   - 下方或侧栏显示 speaker 列表、时长、source URL。
   - 默认展示中文脚本 tab。
   - 可切换到英文 transcript、quality report、metadata。

3. Artifact 检查页或详情侧栏
   - 展示 `quality.warnings`、`quality.reasons`、segment 统计。
   - 展示 ASR/diarization 摘要。
   - 展示文件路径和下载链接。

第一版不需要：

- 登录。
- URL 输入框。
- 转换按钮。
- 队列状态页。
- 实时日志。
- 后端任务重试。
- 配置管理。

设计约束：

- 以列表、播放器、详情面板为核心。
- 避免落地页和大 hero。
- 不展示本机绝对路径。
- 错误或缺失字段要优雅降级。
- 移动端至少能播放和查看脚本；桌面端优先支持并排查看播放器和脚本。

## 高保真 Mockup 设计 Brief

本节可以直接交给设计 agent，用来产出高保真 mockup。目标是设计图，不是生产代码；可以用静态 HTML、Figma 或图片稿表达，但必须基于本文契约里的真实字段和三条 fixture。

### 输出要求

- 至少产出桌面端主界面，推荐尺寸 `1440x900`。
- 至少补一张移动端关键页，推荐尺寸 `390x844`。
- 优先做 3 个核心画面：
  1. Library 列表页：展示三条真实 episode，支持按 route/source/quality/speaker count 筛选的视觉状态。注意三条 fixture 的 quality 全是 `safe_to_adapt`、route 只有 `article_reading` / `transcript_first` 两种、speaker_count 为 {0, 5, 0}，真实筛选维度稀疏；筛选 UI 不必做成沉重的左栏，但 mock 仍需刻意展示 `inspect_first` / `reject` / `unknown` 这些没有 fixture 的状态。
  2. Episode 播放详情页：以音频播放器、中文脚本和 source/quality 信息为核心。
  3. Transcript 对照/质量检查页或详情侧栏：展示英文 transcript、中文脚本、quality metrics、warnings/reasons 和 metadata。
- 如要做设计方向探索，可以出 2-3 个视觉方向，但每个方向都必须使用同一批真实 fixture，不要编造新节目。

### 视觉方向

- 气质：私有、安静、清晰、偏工具型的播客资料库。
- 不要做 landing page、营销 hero、宣传页或大幅说明页。
- 不要把页面做成 SaaS 官网；第一屏就是可用的资料库/播放器。
- 以信息密度和可扫读性为优先：标题、来源、时长、质量状态、route/source、speaker 数要容易比较。
- 颜色克制，避免大面积紫蓝渐变、装饰光斑、背景 orb、花哨插画。
- 可以用小图标辅助导航、播放、下载、筛选、展开/折叠和状态 badge。
- 卡片只用于 episode item 或详情面板，不要卡片套卡片；主页面结构应更像应用 shell。
- UI 文字建议用中文；episode 标题、source title、专有名词和 URL 保持原始文本。

### 布局建议

桌面端推荐三栏或两栏应用布局：

```text
左侧导航/筛选
  Library
  Route: transcript_first / article_reading / audio_first
  Source: podcast_rss / web_article / ...
  Quality: safe_to_adapt / inspect_first / reject

中间 episode 列表
  标题
  route/source badge
  duration
  speaker count
  quality
  published_at

右侧详情/播放器
  标题 + source
  audio player
  tabs: 中文脚本 / 英文原文 / 质量 / Metadata
```

移动端推荐单列：

```text
顶部：Library 标题 + 筛选按钮
列表：episode cards
详情页：播放器固定在上方，脚本作为主内容，source/quality 折叠展示
```

### 三条 Fixture 的设计用途

| run_id | 设计用途 |
| --- | --- |
| `frontend-publish-practical-ai-faithful-sidecar-20260619` | 多 speaker 标准播客。用于展示 speaker 列表、speaker badge、多人脚本段落和较长音频。 |
| `frontend-publish-podnews-sidecar-20260619` | 短标准播客，无 speaker。用于展示简单 episode、短音频和无 speaker 的降级状态。 |
| `article-anthropic-infra-noise-20260619` | 技术文章朗读，`route=article_reading`、`source_type=web_article`、`speakers=[]`。用于展示文章 route、网页 source metadata、无 speaker 的详情页。 |

### 必须体现的状态

- `safe_to_adapt` 是正常可播放状态，但不要设计成“绝对正确”。
- `speakers=[]` 时隐藏 speaker 列表，或展示轻量的“无角色分段”状态。
- `article_reading` 不展示主持人/嘉宾概念。
- `asr=null` 时不展示 ASR 模块；可以在 metadata/quality 页显示“未使用 ASR”。
- 缺失可选字段时界面要留白或隐藏，不要显示 `null`。
- 未知 `route` / `source_type` 应按通用 episode 展示。
- `summary` 和 `created_at` 当前三条 fixture 全为 `null`，详情页头部不要依赖它们，需有无摘要的默认排版。
- 标题可能带来源站点分隔符残留（如 `Quantifying infrastructure noise in agentic coding evals \ Anthropic` 尾部的 `\ Anthropic`）。前端按原文展示即可，不要据此报错或硬截断；如需更干净的标题由后端处理。

### 不要设计的功能

- URL 输入框。
- 转换按钮。
- 任务队列。
- 实时日志。
- 登录/账号。
- 后端配置管理。
- DeepSeek、TTS、ASR 的启动/停止控制。
- 订阅扫描或批处理管理。

### 可交付物建议

- `Library` 桌面高保真图。
- `Episode Detail - Podcast` 桌面高保真图，使用 Practical AI 多人样本。
- `Episode Detail - Article` 桌面高保真图，使用 Anthropic 技术文章样本。
- `Mobile Episode Detail` 移动端高保真图。
- 可选：一个简短交互说明，描述列表选择 episode、tab 切换、播放器和下载按钮。

## 给前端 Agent 的最短上下文

可以把下面这段直接交给前端或设计 agent：

```text
这是 BabelEcho 的只读前端。它不负责转换播客，不提交 URL，不触发后端任务，只读取已经生成的静态产物。

数据入口是 workspace/published/index.json。列表项里的 artifact_path 指向每集详情 JSON，audio_path 指向 MP3。详情 JSON 是 workspace/published/episodes/<run-id>/artifact.json，里面包含 source、quality、media、speakers、asr 和 transcript/script 文件路径。

当前可用于 mock 和联调的真实数据有三条：frontend-publish-practical-ai-faithful-sidecar-20260619 是多人 Practical AI 标准播客样本；frontend-publish-podnews-sidecar-20260619 是短 Podnews 标准播客样本；article-anthropic-infra-noise-20260619 是 article_reading/web_article 技术文章朗读样本，speakers 为空，前端应隐藏 speaker 区域或显示无角色状态。

前端第一版需要：episode 列表、音频播放页、中文脚本查看、英文 transcript 对照、quality report 展示、metadata/source 展示、MP3 下载。不要做登录、任务队列、URL 输入、转换按钮或后台管理。

界面风格应是私有播客资料库：安静、清晰、偏工具型，方便反复听和检查生成质量。
```

## 后续兼容规则

- 新字段只能追加，不改变已有字段含义。
- 删除字段需要升级 `schema_version`。
- 前端遇到未知字段应忽略。
- 前端遇到未知 `route` 或 `source_type` 应按通用 episode 展示。
- `audio_path` 和 `artifact_path` 是列表页最小可用字段，必须保持稳定。
- ASR、声纹、diarization 相关字段只做展示，不成为前端运行依赖。
