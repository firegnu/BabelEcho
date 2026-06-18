# BabelEcho 架构草案

日期：2026-06-16

## 核心判断

BabelEcho 不应先被设计成一个“负责一切的 macOS App”。更合理的系统边界是：

1. 转换系统负责把英文 podcast 来源转换成中文音频产物。
2. 发布产物层负责把转换结果整理成稳定、可消费的中文 podcast。
3. macOS App 只消费已经转换好的中文 podcast，不参与来源解析、转写、翻译、TTS 或任务调度。

这样隔离之后，转换系统可以独立演进，App 也可以保持轻量、稳定、原生。

## 架构分层

```text
English Podcast Sources
        |
        v
Conversion System
        |
        v
Published Chinese Podcast Artifacts
        |
        v
macOS App / Any Podcast Client
```

## 1. 转换系统

转换系统是核心生产链路。它可以是后台服务、命令行工具、定时任务、远程 worker，或者这些形态的组合。

输入：

- RSS feed URL
- iTunes / Apple Podcasts 等可反查 RSS 的发现入口
- YouTube 公开视频字幕入口
- 单集 URL
- 手动导入的 transcript
- 后续可能支持批量节目订阅列表

职责：

- 解析来源，定位 canonical RSS / episode / transcript / audio。
- 拉取 transcript 或音频资源。
- 将 VTT、SRT、plain text、HTML、JSON、ASR 输出统一成内部 transcript 结构。
- 处理 speaker 信息。
- 将英文内容转成中文口播稿。
- 按 speaker 生成中文语音。
- 拼接、响度处理、封面和元数据处理。
- 生成最终中文音频和发布所需元数据。

非职责：

- 不承担播放体验。
- 不绑定 macOS App。
- 不要求 App 知道任何转换任务状态。

来源层调研见：[source-ingestion-research.md](./source-ingestion-research.md)。

### 来源发现 Adapter

MVP-1 的来源扩展采用内部 adapter 设计，而不是一开始做动态第三方插件加载系统。

每个 adapter 只负责一种外部入口，并输出标准 `source` YAML 或标准 transcript raw 文件：

- RSS / iTunes feed discovery and episode selection -> `source.type=podcast_rss`
- PodcastIndex API / search -> `source.type=podcast_index_api`
- Episode page transcript -> `source.type=episode_page`
- YouTube public captions -> `source.type=youtube_captions`

这样后续插入新入口时，只需要新增一个 adapter 模块和一层 CLI，不改 `normalize -> adapt -> synthesize -> assemble -> publish` 主链路。

## 2. 发布产物层

发布产物层是转换系统和客户端之间的唯一契约。

推荐优先采用静态文件 + RSS feed，而不是自定义任务 API。这样转换结果可以被任何播客客户端消费，也方便先验证内容质量。

建议产物：

```text
published/
  feed.xml
  episodes/
    <episode-id>/
      audio.m4a
      metadata.json
      transcript.en.json
      transcript.zh.json
      cover.jpg
```

其中：

- `feed.xml` 是中文播客订阅入口。
- `audio.m4a` 或 `audio.mp3` 是最终中文音频。
- `metadata.json` 保存原始来源、标题、描述、发布时间、处理版本等信息。
- `transcript.en.json` 保存标准化后的英文 transcript。
- `transcript.zh.json` 保存中文口播稿或中文 transcript。
- `cover.jpg` 可复用原节目封面，也可后续生成中文版本封面。

最小 MVP 产物可以先只有：

- `feed.xml`
- 中文音频文件
- 基础 episode metadata

## 3. macOS App

macOS App 是薄客户端。它只关心“已经发布好的中文播客”，不关心这些内容是如何被转换出来的。

输入：

- 一个私有 RSS feed URL。
- 或一个本地 `published/` 目录。

职责：

- 展示中文节目和单集列表。
- 播放中文音频。
- 管理播放进度。
- 下载或缓存音频。
- 收藏、已听、继续播放等本地状态。

非职责：

- 不提交转换任务。
- 不配置模型或 API key。
- 不解析 Apple Podcasts / Spotify / YouTube 原始链接。
- 不拉取英文原始音频。
- 不做 ASR、翻译、TTS、voice clone、音频拼接。

这个边界意味着 macOS App 可以非常接近一个专用中文播客播放器，而不是转换工作台。

## 系统契约

转换系统和 App 之间的契约应尽量稳定：

- App 只依赖 `feed.xml` 和音频 URL。
- 可选增强信息通过 episode metadata 提供。
- 原始来源 attribution 必须保留在 metadata 中。
- 转换系统可以重新生成 feed 和音频，但应保持 episode ID 稳定。
- App 的本地播放进度和收藏状态不应依赖转换系统数据库。

## 建议开发顺序

1. 定义发布产物结构。
   - 验证：用静态 `feed.xml` 和一个本地音频文件跑通订阅/播放。

2. 实现最小转换 pipeline。
   - 验证：输入一个 RSS episode，输出中文音频和 metadata。

3. 生成中文 podcast RSS。
   - 验证：用现有播客客户端订阅生成的 feed。

4. 再实现 macOS App。
   - 验证：App 能读取同一个 feed，播放转换好的中文音频。

## 暂不解决的问题

- 是否公开分发生成后的中文播客。
- 具体选择哪个 ASR、LLM、TTS 或 voice clone 模型。
- 是否需要用户账号和权限系统。
- 是否需要远程 GPU worker。
- 是否需要 App 内展示转换进度。

这些问题应在发布产物契约和最小 pipeline 验证后再定。
