# 后端 MVP-0 设计

日期：2026-06-16

## 目标

MVP-0 的目标是在 5090D 常驻机器上，用一组分阶段脚本，把一个硬编码英文 podcast episode 转换成可播放、可发布的中文音频产物。

本阶段只验证端到端生产链路：

```text
英文播客来源 -> 完整 transcript -> 标准化 transcript -> 中文口播稿 -> 固定中文 TTS -> 中文音频 -> 最小 RSS 发布产物
```

MVP-0 接受固定中文声音，不做原主播 voice clone，也不做 ASR。没有完整 transcript 的 episode 在 MVP-0 中直接标记为不支持。

整体架构边界见：[architecture.md](./architecture.md)。
来源层调研见：[source-ingestion-research.md](./source-ingestion-research.md)。

## 运行环境

主运行环境：

- 5090D 常驻机器。
- 公网可访问。
- 负责实际转换、生成音频和发布产物。

辅助环境：

- M4 Max MacBook Pro。
- 作为开发机、管理机、试听和验收设备。

MVP-0 不要求先做 Web 管理后台或常驻 API 服务。可以通过 SSH 在 5090D 上运行脚本。

## 非目标

MVP-0 明确不做：

- 不做 macOS App。
- 不做 Web 后台。
- 不做任务队列。
- 不做多节目订阅扫描。
- 不做用户账号或权限系统。
- 不做原主播 voice clone。
- 不做复杂 speaker diarization。
- 不做 ASR 或仅音频输入处理。
- 不做公开分发策略。

这些能力可以在端到端链路跑通后再逐步加入。

## 推荐实现形态

采用“分阶段脚本 + 文件产物”。

每个阶段：

- 从磁盘读取输入文件。
- 向磁盘写出输出文件。
- 可以独立重跑。
- 不依赖上一步留在内存里的状态。

这样做的好处：

- 调试简单。
- 中间结果可人工检查。
- 某一步失败时可以从该阶段重跑。
- 后续可以自然演进成 worker 或任务队列。

## 目录结构

建议每次转换创建一个独立 `run-id` 目录：

```text
workspace/
  sources/
    hardcoded.yaml
  runs/
    <run-id>/
      source.json
      transcript/
        raw.vtt
        raw.srt
        raw.txt
        normalized.json
      script/
        zh.json
      segments/
        0001.wav
        0002.wav
      output/
        audio.m4a
      publish/
        feed.xml
        episodes/
          <episode-id>/
            audio.m4a
            metadata.json
            transcript.en.json
            transcript.zh.json
```

实际文件可以少于上面结构。例如来源直接提供 plain text transcript 时，不需要 `raw.vtt` 或 `raw.srt`。

MVP-0 不保存或处理原始英文音频。原始音频 URL 可以记录在 `source.json` 中，留给后续 ASR 或 voice clone 阶段使用。

## 阶段设计

### 01_ingest

职责：

- 读取硬编码来源配置。
- 定位 episode metadata。
- 获取完整 transcript。
- 记录原始 episode URL、transcript URL、可选音频 URL 等来源信息。

输入：

- `sources/hardcoded.yaml`

输出：

- `runs/<run-id>/source.json`
- `runs/<run-id>/transcript/raw.*`

MVP-0 可以先只支持一个固定 RSS episode 或一个固定 transcript URL。如果该 episode 没有完整 transcript，则本阶段失败并给出明确原因。

### 02_normalize_transcript

职责：

- 将 VTT、SRT、plain text、HTML 或 JSON transcript 统一成内部 transcript 格式。
- 保留时间戳、speaker、原文段落和来源信息。
- 真实播客 transcript 中常见的 `Host:` / `Guest:` / 人名冒号前缀不能当作正文处理。当前 plain text parser 已支持轻量 speaker-label 解析和段内 speaker turn 拆分，把说话人写入 `speaker` 字段，而不是让 TTS 读出“某某：”。

输入：

- `transcript/raw.*`

输出：

- `transcript/normalized.json`

建议格式：

```json
{
  "episode_id": "example-episode",
  "language": "en",
  "segments": [
    {
      "id": "0001",
      "start_ms": 0,
      "end_ms": 4200,
      "speaker": null,
      "text": "Original English text.",
      "source": "transcript"
    }
  ]
}
```

### 03_adapt_to_chinese

职责：

- 将英文 transcript 转换成适合中文收听的口播稿。
- 保留段落边界，方便后续逐段 TTS。
- 不追求逐词直译，优先自然中文播客表达。

输入：

- `transcript/normalized.json`

输出：

- `script/zh.json`

建议格式：

```json
{
  "episode_id": "example-episode",
  "language": "zh-CN",
  "segments": [
    {
      "id": "0001",
      "source_segment_ids": ["0001"],
      "speaker": null,
      "text": "自然的中文口播稿。"
    }
  ]
}
```

### 04_synthesize

职责：

- 使用固定中文 TTS 声音生成每段音频。
- 输出分段音频，便于失败重试和人工检查。

输入：

- `script/zh.json`

输出：

- `segments/0001.wav`
- `segments/0002.wav`
- ...

MVP-0 不做 voice clone，但 `speaker` 字段保留，MVP-1 已可以按 speaker 选择固定音色。

真实多人播客不能长期用同一个固定中文声音读完整集。MVP-1 当前规则是：运行默认只部署 `CosyVoice-300M-SFT` 的 `sft_builtin_4role`；可启用 `speaker_voices.mode: infer_once` 在每集 TTS 前最多调用一次 LLM，根据 speaker 名称和少量上下文推断 `male/female/unknown` 方向，再由代码稳定映射到 `female_a / male_a / female_b / male_b` 四个固定角色。`confidence` 只用于人工复核提示，不阻塞；`unknown` 也会自动获得具体角色。未启用推断、推断失败或映射文件无效时，回退到原来的首次出现顺序映射。

### 05_assemble

职责：

- 将分段音频拼接成完整中文音频。
- 做基础静音间隔、响度和格式处理。

输入：

- `segments/*.wav`

输出：

- `output/audio.m4a`

MVP-0 不要求严格对齐原音频时长。优先保证可听、连贯、无明显拼接错误。

### 06_publish

职责：

- 生成可消费的发布产物。
- 输出最小中文 podcast feed。

输入：

- `output/audio.m4a`
- `source.json`
- `script/zh.json`
- `transcript/normalized.json`

输出：

- `publish/feed.xml`
- `publish/episodes/<episode-id>/audio.m4a`
- `publish/episodes/<episode-id>/metadata.json`
- 可选 `transcript.en.json`
- 可选 `transcript.zh.json`

MVP-0 的 `feed.xml` 只需要支持一个 episode。后续再扩展为多 episode feed。

## 最小配置

`sources/hardcoded.yaml` 可以先非常简单：

```yaml
source:
  type: rss_episode
  feed_url: "https://example.com/feed.xml"
  episode_guid: "example-guid"

tts:
  provider: local_cli
  command: "tts-wrapper"
  voice: "sft_builtin_4role"
  cosyvoice_repo: "/path/to/CosyVoice"

publish:
  base_url: "https://example.com/babelecho"
```

如果第一条测试数据直接使用 transcript URL，也可以改为：

```yaml
source:
  type: transcript_url
  transcript_url: "https://example.com/episode.vtt"
  title: "Example Episode"
  original_url: "https://example.com/episode"
```

## 第一条测试数据约束

MVP-0 的第一条测试数据应刻意选择低风险 episode，避免把样本难度误判为系统设计问题。

推荐选择：

- 有完整、公开、可下载的英文 transcript。
- transcript 质量较高，段落清晰。
- 单集篇幅不要太长，优先 5 到 15 分钟。
- 优先单人播客或 speaker 数量很少的访谈。
- 主题术语不要过密，避免第一轮就被专业名词和上下文一致性拖慢。

暂不选择：

- 没有 transcript、只有音频的 episode。
- 多人圆桌、频繁插话、speaker 难以区分的 episode。
- speaker label 格式很混乱、无法被轻量规则识别的 transcript，除非先人工整理。
- 超长节目。
- 大量专有名词、代码、法律、医学或金融细节的 episode。
- 需要保留原主播音色才有价值的内容。

## 成功标准

MVP-0 完成时必须能证明：

1. 5090D 机器上可以运行完整 pipeline。
2. 一个硬编码英文 episode 能生成 `runs/<run-id>/output/audio.mp3`。
3. 生成的中文音频可以正常播放。
4. 每个阶段都有可检查的中间文件。
5. 失败阶段可以单独重跑，不必从头开始。
6. `publish/feed.xml` 和中文音频文件能组成最小中文 podcast 产物。

## 后续 MVP-1 预留点

MVP-0 的文件格式需要为后续扩展保留字段，但不实现复杂逻辑：

- `speaker`：为 speaker diarization 和多音色 TTS 预留。
- `source_segment_ids`：为一对多、多对一翻译改写预留。
- `start_ms` / `end_ms`：为时间轴对齐和章节生成预留。
- `metadata.json`：为原始来源 attribution、处理版本和模型版本预留。
- `segments/`：为单段重试、质量检查和后续 voice clone 预留。

MVP-1 可以在不推翻 MVP-0 的前提下加入：

- 多 episode 批量处理。
- 订阅清单定时扫描。
- 仅音频输入处理和 ASR fallback。
- 更复杂的 speaker label 解析、speaker diarization 或人工 speaker 修正。
- 更细的多说话人 `speaker -> voice` 配置，例如每个 podcast 的人工角色修正。
- 原主播 voice clone。
- 更完整的 RSS feed 发布。
