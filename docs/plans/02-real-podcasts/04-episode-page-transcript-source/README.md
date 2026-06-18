# 02.04 Episode Page Transcript Source 大计划

状态：`done`

日期：2026-06-18

父计划：`02-real-podcasts`

## 目标

让 BabelEcho 可以从播客官网单集页面获取 transcript，并继续复用现有 transcript-first pipeline：

```text
episode page -> transcript link/body -> raw.txt -> normalize -> adapt -> synthesize -> assemble -> publish
```

这里的 `episode_page` 指播客自己的单集网页，例如：

```text
https://99percentinvisible.org/episode/641-99pi-anniversary-special-15-for-15/
```

不是 YouTube、Spotify 或 Apple Podcasts 页面。

## 背景

当前 MVP-1 已支持：

- RSS item 内的 `podcast:transcript`。
- 已获取的 PodcastIndex episode JSON 中的 `transcripts[].url` / `transcriptUrl`。
- 手动 transcript 文件。

真实播客里常见的缺口是：RSS 或 PodcastIndex 不一定暴露 transcript URL，但官网 episode 页面有 `Transcript` 链接或正文 transcript。`episode_page` 计划只补这个缺口。

## 范围

In:

- 新增 `source.type=episode_page`。
- 支持从 episode 页面发现 transcript 链接。
- 支持从 transcript 页面抽取正文并保存为 `raw.txt`。
- 支持页面本身就是 transcript 页的情况。
- `source.json` 记录 page URL、transcript page URL、title 和 raw transcript 路径。
- 找不到 transcript 时明确失败。

Out:

- 不做 ASR。
- 不下载 episode 音频。
- 不解析 YouTube captions。
- 不解析 Spotify 内部 transcript。
- 不做全网搜索或订阅扫描。
- 不做站点级复杂爬虫。

## 子计划

| 编号 | 文件 | 状态 | 目标 |
| --- | --- | --- | --- |
| 02.04.01 | [01-episode-page-transcript-only.md](./01-episode-page-transcript-only.md) | `done` | 从 episode 页面找到 transcript 并只跑到 `ingest` / `adapt` 前 |

## 设计边界

- 第一版只实现通用但保守的 HTML 解析：优先找 `href` 或文本里包含 `transcript` 的链接，再抓 transcript 页面正文；当前已补充 `transcript-content`、`cite + p` speaker 标注、Lex 风格 `ts-segment`、以及页面内 `Transcript` heading 后正文段落。
- 第一版至少以 99% Invisible 这类结构清晰的网站作为真实 smoke。
- 如果页面没有 transcript 链接或正文，命令失败并说明原因；不要尝试下载音频或 ASR。
- 如果不同网站结构差异过大，后续再加站点 profile，不在第一版里做复杂规则系统。

## 完成标准

- 一个真实 episode 页面可以被 `babelecho run --source-config "$tmpdir/source.yaml" --to-stage ingest` 拉成干净 `raw.txt`。
- 一个 fixture episode 页面可以在测试中跑通 `ingest`，并记录正确的 `source.json`。
- `babelecho run --source-config "$tmpdir/source.yaml" --to-stage adapt` 可以继续复用现有 normalize/adapt。
- 找不到 transcript 时有清晰错误。
- 全量测试通过。

## 完成记录

- `source.type=episode_page` 已接入 `ingest`，输出 `transcript/raw.txt` 和 `source.json` 的 `page_url` / `transcript_page_url`。
- 真实 99% Invisible smoke 已通过到 `ingest`：`raw.txt` 约 48KB，从 `ROMAN MARS:` transcript 正文开始，后续阶段按 `--to-stage ingest` 标记为 `skipped`。
- 真实标准播客页面 normalize 验证已通过：Practical AI 360 可保留 `Daniel` / `Chris` speaker；Lex Fridman / Jensen Huang 可从 `ts-segment` transcript 页抽正文而不是导航目录；Cognitive Revolution / Daniel Miessler 可从页面内 `Transcript` 章节抽正文。三个 run 的 `transcript/quality.json` 均为 `safe_to_adapt`。
- 覆盖率 smoke 后已补 transcript 链接同源优先规则：当页面同时含有同源 transcript 和外域 transcript 噪声链接时优先同源，Acquired Google 这类无可抽取 transcript 的页面会在 `ingest` 明确失败，不再产出误导性短 transcript。
- Practical AI 358 已跑通标准播客页面 -> normalize -> chunked DeepSeek adapt，132 段 `script/zh.json` 通过 script QA；脚本 QA 已允许中文脚本中保留 URL，不再把重复网址误判为整段英文残留。
- 当前仍不处理 YouTube、Spotify、Apple Podcasts 页面，不做 JS 渲染、ASR 或音频下载。
