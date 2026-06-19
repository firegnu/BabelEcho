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

## 路径原则

- 所有面向前端的路径都使用相对 `workspace/published/` 的相对路径。
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

示例：

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-19T08:27:33Z",
  "title": "BabelEcho",
  "description": "Locally generated Chinese podcast artifacts.",
  "episodes": [
    {
      "run_id": "rss-podnews-single-url-full-20260619",
      "title": "A new AMP member",
      "route": "transcript_first",
      "status": "succeeded",
      "source_type": "podcast_rss",
      "quality_recommendation": "safe_to_adapt",
      "speaker_count": 0,
      "duration_seconds": 233.535,
      "published_at": "2026-06-19T08:27:33Z",
      "audio_path": "episodes/rss-podnews-single-url-full-20260619/audio.mp3",
      "artifact_path": "episodes/rss-podnews-single-url-full-20260619/artifact.json"
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
| `episodes[].route` | string | yes | `transcript_first` 或 `audio_first`。 |
| `episodes[].status` | string | yes | `succeeded`、`partial`、`failed`。列表页默认只展示 `succeeded`。 |
| `episodes[].source_type` | string | yes | 例如 `youtube_captions`、`episode_page`、`podcast_rss`、`audio_file`。 |
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
  "run_id": "rss-podnews-single-url-full-20260619",
  "route": "transcript_first",
  "status": "succeeded",
  "title": "A new AMP member",
  "summary": null,
  "created_at": "2026-06-19T08:26:27Z",
  "published_at": "2026-06-19T08:27:33Z",
  "source": {
    "type": "podcast_rss",
    "provider": "rss",
    "input_url": "https://podnews.net/rss",
    "episode_url": "https://example.com/episode",
    "transcript_url": "https://example.com/transcript"
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
      "html_entity_count": 0
    }
  },
  "media": {
    "audio_path": "audio.mp3",
    "mime_type": "audio/mpeg",
    "duration_seconds": 233.535,
    "sample_rate": 22050,
    "channels": 1,
    "file_size_bytes": 3741234
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
| `route` | string | yes | `transcript_first` 或 `audio_first`。 |
| `status` | string | yes | `succeeded`、`partial`、`failed`。 |
| `title` | string | yes | 单集标题。 |
| `summary` | string/null | no | 后续可由 LLM 或 RSS metadata 提供，第一版可为 `null`。 |
| `created_at` | string | no | run 创建时间。 |
| `published_at` | string | no | publish 完成时间。 |
| `source` | object | yes | 来源信息。只放公开 URL 和类型，不放内部 config。 |
| `quality` | object | no | 质量报告摘要。来自 `transcript/quality.json` 或 ASR 路线质量报告。 |
| `media` | object | yes | 最终可播放音频信息。 |
| `artifacts` | object | yes | 前端可读的相对文件路径。 |
| `speakers` | array | yes | speaker 展示信息；无 speaker 时为空数组。 |
| `asr` | object/null | no | audio-first 路线的 ASR/diarization 摘要。transcript-first 路线为 `null`。 |
| `ui` | object | no | 非业务关键的前端提示，例如默认 tab、badge。 |

## Source Contract

`source.type` 建议值：

| 值 | 含义 |
| --- | --- |
| `youtube_captions` | YouTube / YouTube Podcasts 单集视频公开字幕。 |
| `episode_page` | 标准播客官网 episode 页面 transcript。 |
| `podcast_rss` | RSS feed item 内 transcript。Apple/iTunes 和直接 RSS 最终都归到这里。 |
| `transcript_file` | 用户本地 transcript file。 |
| `audio_file` | Phase 2 audio-first 本地音频文件。 |

`source.provider` 建议值：

| 值 | 含义 |
| --- | --- |
| `youtube` | YouTube 视频字幕。 |
| `rss` | 直接 RSS feed。 |
| `itunes_lookup` | Apple Podcasts/iTunes URL 经 iTunes Lookup 找到 RSS。 |
| `episode_page` | 官网页面。 |
| `local_file` | 本地文件。 |

前端只展示这些字段，不根据 provider 决定业务逻辑。

## Speaker Contract

`speakers` 示例：

```json
[
  {
    "id": "speaker_1",
    "display_name": "Jerod",
    "voice_role": "male_a",
    "inferred_gender": "male",
    "segment_count": 42,
    "duration_seconds": 820.2
  },
  {
    "id": "speaker_2",
    "display_name": "Daniel",
    "voice_role": "male_b",
    "inferred_gender": "male",
    "segment_count": 39,
    "duration_seconds": 760.8
  }
]
```

规则：

- `display_name` 可以来自 transcript speaker label，也可以是 `speaker_1`。
- `voice_role` 是 BabelEcho 固定中文音色角色，例如 `female_a`、`male_a`、`female_b`、`male_b`。
- `inferred_gender` 仅用于辅助展示，可为 `male`、`female`、`unknown` 或 `null`。
- 不暴露声纹 embedding。
- 不暴露原始 speaker profile 文件。
- 不暗示真实身份识别。

## ASR / Diarization Contract

audio-first 路线以后可以填充 `asr`：

```json
{
  "model": "local-asr-model-name",
  "language": "en",
  "duration_seconds": 601.2,
  "segment_count": 96,
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

前端展示建议：

- 中文脚本为默认 tab。
- 英文 transcript 可作为对照 tab。
- 长文本按 segment 渲染，不一次性拼成单个段落。
- 有 speaker 时显示 speaker 标签；无 speaker 时隐藏 speaker 列。

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

为了不修改现有业务逻辑，建议后端只追加一个 artifact 生成步骤：

1. 读取现有 `run.json`、`source.json`、`transcript/quality.json`、`segments/manifest.json`、`output/audio.mp3` 和 publish 目录文件。
2. 生成 `workspace/published/episodes/<run-id>/artifact.json`。
3. 扫描或维护 `workspace/published/episodes/*/artifact.json`。
4. 生成 `workspace/published/index.json`。

这个步骤可以放在 publish 之后，也可以做成独立命令：

```text
babelecho artifacts refresh --workspace workspace
```

要求：

- 只读已有 run 产物。
- 只写公开 sidecar JSON。
- 不改变 `episode convert`、`run`、`normalize`、`adapt`、`synthesize`、`assemble` 的现有语义。
- 缺失可选字段时写 `null` 或省略，不让旧 run 无法发布。

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

## 给前端 Agent 的最短上下文

可以把下面这段直接交给前端或设计 agent：

```text
这是 BabelEcho 的只读前端。它不负责转换播客，不提交 URL，不触发后端任务，只读取已经生成的静态产物。

数据入口是 workspace/published/index.json。列表项里的 artifact_path 指向每集详情 JSON，audio_path 指向 MP3。详情 JSON 是 workspace/published/episodes/<run-id>/artifact.json，里面包含 source、quality、media、speakers、asr 和 transcript/script 文件路径。

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
