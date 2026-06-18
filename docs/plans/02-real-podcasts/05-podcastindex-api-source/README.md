# 02.05 PodcastIndex API Source 大计划

状态：`done`

日期：2026-06-18

父计划：`02-real-podcasts`

## 目标

让 BabelEcho 可以直接请求 PodcastIndex API 获取 episode metadata，并继续复用现有 transcript-first pipeline：

```text
PodcastIndex API -> episode JSON -> transcript URL -> raw transcript -> normalize -> adapt -> synthesize -> assemble -> publish
```

## 背景

当前 MVP-1 已支持：

- `source.type=podcast_index_episode`：读取已经下载好的 PodcastIndex episode JSON。
- `source.type=podcast_rss`：读取 RSS item 内的 `podcast:transcript`。
- `source.type=episode_page`：从播客官网 episode 页面发现 transcript 链接或 transcript 正文。

缺口是：还没有从 PodcastIndex API 发起真实鉴权请求，也没有把 API 返回的 episode metadata 直接接到 ingest。

官方 OpenAPI 文档当前说明：

- base URL：`https://api.podcastindex.org/api/1.0`
- 鉴权 headers：`User-Agent`、`X-Auth-Date`、`X-Auth-Key`、`Authorization`
- `Authorization` 为 `sha1(apiKey + apiSecret + unixTime)`
- 相关 episode endpoints 包括 `/episodes/byid`、`/episodes/byfeedid`、`/episodes/byfeedurl`、`/episodes/byitunesid`

参考：https://podcastindex-org.github.io/docs-api/

## 范围

In:

- 新增 `source.type=podcast_index_api`。
- 支持 `episodes/byid`，通过 `episode_id` 获取单个 episode。
- 支持 `episodes/byfeedid` / `episodes/byfeedurl`，通过 `episode_url` 选择目标 episode。
- 复用现有 `discover_podcast_index_transcript()`，优先读取 `transcripts[].url`，回退 `transcriptUrl`。
- API key / secret 只从环境变量或 ignored 本地 env 文件读取。
- `source.json` 记录 API 查询参数、title、original_url、transcript_url、raw_transcript。

Out:

- 不做 PodcastIndex 搜索 UI。
- 不做订阅扫描或多 episode 批处理。
- 不做 ASR。
- 不下载音频。
- 不把 API key / secret 写入 tracked YAML。

## 子计划

| 编号 | 文件 | 状态 | 目标 |
| --- | --- | --- | --- |
| 02.05.01 | [01-podcastindex-api-episode-ingest.md](./01-podcastindex-api-episode-ingest.md) | `done` | 接入 PodcastIndex API 鉴权和 episode transcript ingest |

## 完成标准

- 单元测试覆盖 PodcastIndex 鉴权 header，包含 SHA-1 token。
- fixture API response 可以通过 `source.type=podcast_index_api` 写出 transcript raw 文件。
- `babelecho run --source-config ... --to-stage adapt` 可以复用现有 pipeline。
- 没有 API credentials 时错误清晰。
- 如果本机有 PodcastIndex credentials，补一个真实 transcript-only smoke；没有 credentials 时记录为未执行，不阻塞本地测试。

## 完成记录

- `source.type=podcast_index_api` 已接入 `ingest`，支持 `episodes/byid`、`episodes/byfeedid`、`episodes/byfeedurl`、`episodes/byitunesid`。
- API 鉴权 headers 使用 `User-Agent`、`X-Auth-Date`、`X-Auth-Key`、`Authorization=sha1(apiKey+apiSecret+unixTime)`。
- Credentials 只从环境变量或 ignored env 文件读取；tracked 文件只提供 `.example`。
- 端到端 fixture 已覆盖 `babelecho run --source-config ... --to-stage adapt`。
- 本机没有 `PODCASTINDEX_API_KEY` / `PODCASTINDEX_API_SECRET` 或 ignored `workspace/config/podcastindex.env`，真实 API smoke 未执行。
