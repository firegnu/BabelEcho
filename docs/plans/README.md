# 计划文档索引

## 目的

`docs/plans/` 用来保存可执行计划。它和架构、调研、runbook 文档分开：架构文档回答“系统应该长什么样”，计划文档回答“下一步按什么顺序做”。

产品阶段和长期优先级见：[BabelEcho Roadmap](../roadmap.md)。

## 编号规则

采用两级编号：

- 大计划目录：`NN-topic/`
- 子计划文件：`NN-short-name.md`
- 如果某个子计划本身需要拆成一组可执行小计划，可以新增 `NN-topic/` 子目录，目录内用 `README.md` 描述大计划，再用 `NN-short-name.md` 保存小计划。

例如：

```text
docs/plans/
  01-backend-mvp0/
    01-local-llm-adapt.md
    02-real-transcript-source.md
    03-local-tts.md
  02-publish-and-app/
    01-static-feed-hosting.md
    02-macos-reader-app.md
  02-real-podcasts/
    04-episode-page-transcript-source/
      README.md
      01-episode-page-transcript-only.md
```

对应关系：

- `01-backend-mvp0/` 是第 1 个大计划。
- `01-backend-mvp0/01-local-llm-adapt.md` 是第 1 个大计划下的第 1 个子计划，也可以口头称为 `01.01`。
- 同一个目录下只追加新编号，不复用旧编号。
- 已有未编号文档暂不重命名，避免破坏链接；后续从 `docs/plans/` 开始保持编号。

## 状态约定

每个计划文件应包含：

- `状态`：`draft`、`ready`、`in_progress`、`done`、`blocked`
- `目标`
- `范围`
- `前置条件`
- `执行步骤`
- `验收标准`
- `风险和分支处理`

## 当前计划

### 01 Backend MVP-0

- [01.01 DeepSeek LLM Adapt 基线接入](./01-backend-mvp0/01-local-llm-adapt.md) - `done`
- [01.03 本地中文 TTS 接入](./01-backend-mvp0/03-local-tts.md) - `done`
- MVP-0 Acceptance closeout - `done`，完成记录见 [BabelEcho Roadmap](../roadmap.md)

### Roadmap

- [BabelEcho Roadmap](../roadmap.md) - `active`

### MVP-1 Real Podcasts

- Fixed Chinese voice baseline - `done`: current route is `sft_builtin_4role` with `male_a` on CosyVoice2 cross-lingual speed `1.1` and the other roles on 300M SFT.
- [02.01 Real Podcast Transcript Source Input](./02-real-podcasts/01-real-podcast-transcript-source.md) - `done`
- [02.02 Public RSS End-to-End Real Run](./02-real-podcasts/02-public-rss-real-run.md) - `done`
- [02.03 SFT Built-in 4-role Voice Profile](./02-real-podcasts/03-sft-builtin-4role-voice-profile.md) - `done`
- [02.04 Episode Page Transcript Source](./02-real-podcasts/04-episode-page-transcript-source/README.md) - `done`
  - [02.04.01 Episode Page Transcript-only Ingest](./02-real-podcasts/04-episode-page-transcript-source/01-episode-page-transcript-only.md) - `done`
- [02.05 PodcastIndex API Source](./02-real-podcasts/05-podcastindex-api-source/README.md) - `done`
  - [02.05.01 PodcastIndex API Episode Ingest](./02-real-podcasts/05-podcastindex-api-source/01-podcastindex-api-episode-ingest.md) - `done`
  - [02.05.02 PodcastIndex Search CLI](./02-real-podcasts/05-podcastindex-api-source/02-podcastindex-search-cli.md) - `done`
- [02.06 Discovery Adapters](./02-real-podcasts/06-discovery-adapters/README.md) - `done`
  - [02.06.01 iTunes Feed Discovery](./02-real-podcasts/06-discovery-adapters/01-itunes-feed-discovery.md) - `done`
  - [02.06.02 YouTube Captions Source](./02-real-podcasts/06-discovery-adapters/02-youtube-captions-source.md) - `done`
  - [02.06.03 RSS Episode Selection](./02-real-podcasts/06-discovery-adapters/03-rss-episode-selection.md) - `done`
- [02.07 Chunked DeepSeek Adapt](./02-real-podcasts/07-chunked-adapt.md) - `done`
- [02.08 On-demand Episode Convert](./02-real-podcasts/08-on-demand-episode-convert.md) - `done`

### Deferred Voice Work

- Authorized male/neutral reference wav comparison - `deferred`: use the same `cross_lingual` route with a local authorized `prompt_wav`; this is fixed-voice expansion, not original-host voice clone.
- Original-host voice clone - `deferred`.
