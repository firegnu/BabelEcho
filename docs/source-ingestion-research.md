# 播客来源调研

调研日期：2026-06-16

## 目标

本阶段只解决一个问题：原始播客内容从哪里来。

这里的“来源”不是指用户在哪个平台看到播客，而是指 App 能否稳定拿到后续处理所需的内容：

- 首选：原始 transcript / captions。
- 备选：公开可访问的 episode 音频文件，用于自行转写。
- 不接受：只有平台内播放能力或仅有节目元数据，但没有 transcript 或可处理音频。

本阶段不讨论翻译、中文口播改写、TTS、voice clone 或音频合成。

## 核心结论

稳定来源不应该绑定 Apple Podcasts、Spotify 或 YouTube 这样的播放平台。它们更适合作为发现入口。

真正适合作为处理来源的是：

1. 公开 RSS feed。
2. PodcastIndex 这类开放播客索引。
3. episode 页面或 show notes 中公开链接的 transcript。
4. 用户手动导入的 transcript。

平台链接需要尽量解析回 canonical source：RSS feed、episode page、transcript URL 或 enclosure audio URL。无法解析的链接应标记为不可处理，而不是绕过平台限制抓取内容。

## 来源可用性矩阵

| 来源 | 发现节目/单集 | 获取 transcript | 获取音频 | 建议定位 |
|---|---:|---:|---:|---|
| 直接 RSS feed | 高 | 中，取决于是否包含 `podcast:transcript` | 高，取 RSS `enclosure` | 第一优先级 |
| PodcastIndex | 高 | 中，API 暴露 `transcripts` / `transcriptUrl` | 高，API 暴露 `enclosureUrl` | 第一优先级 |
| Apple Podcasts | 高 | 低，Apple 自动 transcript 主要在 Apple App / Podcasts Connect 内 | 间接，通过原 RSS | 发现入口 |
| Spotify | 高 | 低，Web API 未提供 transcript 字段 | 不适合，政策禁止下载 Spotify content | 发现入口 |
| YouTube | 高 | 中，但官方 captions 下载要求有编辑权限 | 不建议作为音频下载源 | 特殊入口 |
| 节目官网 / show notes | 中 | 中到高，取决于节目是否公开 transcript | 不稳定 | 辅助补全 |
| 手动导入 transcript | 低 | 最高 | 无 | 必须支持 |

## 建议的来源解析流程

1. 用户输入来源：
   - RSS URL
   - Apple Podcasts 链接
   - Spotify 链接
   - YouTube 链接
   - 节目名 / 单集名搜索
   - 手动粘贴或导入 transcript

2. App 解析成内部 canonical episode：
   - 优先定位 RSS feed 和 RSS item。
   - Apple Podcasts / Spotify 链接只作为发现入口，尽量反查对应 RSS。
   - YouTube 保留为 YouTube source，不伪装成 podcast RSS；第一版只拉公开字幕，不下载音频。
   - 手动 transcript 直接创建本地 episode record。

3. 内容获取优先级：
   - RSS `podcast:transcript`
   - PodcastIndex `transcripts` / `transcriptUrl`
   - episode webpage / show notes 中的 transcript 链接
   - 用户手动导入 transcript
   - RSS `enclosure` 音频下载后自行 ASR

4. 失败处理：
   - 只有平台元数据，没有 transcript，也没有可合法处理的音频时，标记为不可处理。
   - 不做 Spotify stream ripping。
   - 不把 YouTube 官方 API 权限外的 captions 下载当成稳定方案。

## MVP 来源范围

MVP 建议只支持：

1. 用户输入 RSS feed。
2. 用户通过 PodcastIndex 搜索节目。
3. 用户手动导入 transcript。
4. 在没有 transcript 时，从 RSS `enclosure` 音频 fallback 到自行转写。

暂不把 Spotify 作为主来源。YouTube 可以作为字幕-only 特殊入口接入：只处理公开字幕或自动字幕，不下载音频，不做 ASR fallback。

## 需要在产品上明确的边界

- Transcript 可以提供内容，但不能单独提供可克隆的原主播音色。
- 如果要 clone 原主播声音，仍需要对应 speaker 的参考音频或已授权 voice profile。
- 私人自用和公开分发的版权风险不同。来源层应保留 source attribution 和原始链接。
- 平台内自动生成 transcript 不等于第三方 App 可直接获取 transcript。

## 已查证依据

- [RSS 2.0 Specification](https://www.rssboard.org/rss-specification)：RSS `enclosure` 是 episode 媒体文件入口，包含 `url`、`length`、`type`。
- [Podcast Namespace `podcast:transcript`](https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/tags/transcript.md)：标准 transcript 标签，支持多种格式和语言属性。
- [PodcastIndex API](https://podcastindex-org.github.io/docs-api/)：episode 数据包含 `enclosureUrl`、`transcriptUrl`、`transcripts` 等字段。
- [Apple iTunes Search API](https://performance-partners.apple.com/search-api)：无需 API key，可按 `media=podcast` / `entity=podcast` 搜索 podcast show，并返回 RSS `feedUrl`。
- [Apple Podcasts Transcripts](https://podcasters.apple.com/support/5316-transcripts-on-apple-podcasts)：Apple 会自动生成 transcripts，也支持创作者通过 RSS transcript tag 提供 transcript，但主要面向 Apple Podcasts App / Podcasts Connect。
- [Spotify Get Episode API](https://developer.spotify.com/documentation/web-api/reference/get-an-episode)：Spotify Web API 主要提供 metadata，且政策说明 Spotify content 不可下载。
- [YouTube Captions Download API](https://developers.google.com/youtube/v3/docs/captions/download)：官方 captions 下载需要有编辑视频的权限，不能作为任意公开视频 transcript 抓取方案；BabelEcho 第一版 YouTube source 因此使用本机 `yt-dlp` 只拉公开视频公开字幕。
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：支持 `--skip-download`、`--write-subs`、`--write-auto-subs` 等字幕-only 获取参数。

## 下一步讨论

来源层之后，建议继续拆：

1. Transcript 标准化：如何把 VTT/SRT/plain text/HTML/JSON 统一成内部片段结构。
2. Speaker 识别：transcript 自带 speaker、无 speaker、音频 fallback 三种情况如何处理。
3. 中文口播稿生成：直译、意译、播客化改写之间的产品选择。
4. Voice clone / TTS：按 speaker 选择音色、授权边界和质量评估。
5. 音频生成与导出：时间轴、拼接、章节、封面、RSS 输出。
