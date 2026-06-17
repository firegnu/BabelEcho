# 02.01 Real Podcast Transcript Source Input 计划

状态：`done`

日期：2026-06-17

父计划：`02-real-podcasts`

## 目标

让 BabelEcho 可以从真实 podcast RSS feed 中找到 episode 公开 transcript，并复用现有 pipeline：

```text
RSS feed -> podcast:transcript -> ingest -> normalize -> adapt -> synthesize -> assemble -> publish
```

## 范围

In:

- 新增 `source.type=podcast_rss`。
- 支持 RSS item 内的 `podcast:transcript url="..."`。
- 支持可选 `episode_url`，用于从 feed 中选择指定 episode。
- `babelecho run` 增加 `--podcast-feed`，并可配合 `--episode-url`。
- 找不到 transcript 时明确失败。
- 继续使用已选定的 MVP-1 默认固定中文音色基线。

Out:

- 不做 ASR。
- 不解析 Apple Podcasts、Spotify、YouTube 页面。
- 不做订阅扫描、多 episode 批处理或跳过已处理 episode。
- 不做 `speaker -> voice` 映射。
- 不做 voice clone。

## 数据约定

RSS source config:

```yaml
source:
  type: podcast_rss
  feed_url: "https://example.com/feed.xml"
  episode_url: "https://example.com/episodes/1" # optional
```

`source.json` 记录：

```text
source_type=podcast_rss
feed_url
episode_url
transcript_url
title
original_url
raw_transcript
```

## 验收标准

- 一个带 `podcast:transcript` 的 RSS fixture 可以被 ingest 到 `raw.vtt`。
- `babelecho run --podcast-feed ... --to-stage adapt` 可以跑到中文脚本阶段。
- RSS item 没有 transcript 时，命令失败并输出清晰错误，不进入 ASR 或音频处理。
- 全量测试通过。

## 验收记录

2026-06-17 已完成：

- 新增 `src/babelecho/podcast.py`，解析 RSS item 的 `podcast:transcript`。
- `src/babelecho/ingest.py` 支持 `source.type=podcast_rss`。
- `babelecho run` 支持 `--podcast-feed` 和可选 `--episode-url`。
- 本机 fixture 回归：`44 passed`。
- 公开 RSS smoke：

  ```bash
  babelecho run \
    --podcast-feed "https://feeds.transistor.fm/podcasting-advice" \
    --episode-url "https://share.transistor.fm/s/e6cbd9db" \
    --to-stage adapt
  ```

  结果：找到 `https://share.transistor.fm/s/e6cbd9db/transcript.txt`，生成 `raw.txt`、`normalized.json` 和 fixture 中文脚本；script 共 74 段。该 smoke 使用 fixture LLM/TTS config，未调用 DeepSeek。
