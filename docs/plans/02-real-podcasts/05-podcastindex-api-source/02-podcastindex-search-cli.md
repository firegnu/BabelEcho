# 02.05.02 PodcastIndex Search CLI

状态：`done`

日期：2026-06-18

父计划：`02.05 PodcastIndex API Source`

## 目标

补一个 workflow 上的 CLI 第一步：先用 PodcastIndex 搜索节目，再列出 feed 下的 episode，人工选择一个 episode 后生成现有 `source.type=podcast_index_api` YAML。后续 transcript 获取、翻译、TTS 和合成继续走 `babelecho run --source-config ...`。

## 范围

In:

- `babelecho podcast-index search --query ...`：默认调用 `search/byterm`，`--by-title` 调用 `search/bytitle`。
- `babelecho podcast-index episodes --feed-id ...`：调用 `episodes/byfeedid`，列出 episode 标题、guid/link 和 transcript hint。
- `--select-index ... --source-config-out ...`：把选中 episode 写成 `source.type=podcast_index_api`。
- API credentials 仍只来自环境变量或 ignored env 文件。

Out:

- 不做交互式 UI。
- 不做全网 episode 关键词搜索。
- 不做订阅扫描、多 episode 批处理或跳过已处理。
- 不拉 transcript，不翻译，不 TTS。

## 前置条件

- 已有 `source.type=podcast_index_api` ingest。
- 本地或 5090D 有 PodcastIndex API credentials 时才能做真实 API smoke。

## 执行步骤

1. 写 URL/source config 单元测试，覆盖 `search/byterm` 和选中 episode 生成 YAML。
2. 写 CLI fixture 测试，用本地 fake API server 覆盖 search -> episodes -> source config 输出。
3. 实现 PodcastIndex search fetch、episode list fetch、CLI 子命令和 YAML 输出。
4. 更新 README、roadmap、resume 和计划文档。
5. 跑相关测试、全量测试和提交前隐私扫描。
6. 如 credentials 可用，做一次真实 search/episodes smoke。

## 验收标准

- `babelecho podcast-index search --query "99% Invisible"` 能列出 feed 和 `feed_id`。
- `babelecho podcast-index episodes --feed-id <id> --select-index <n> --source-config-out <path>` 能生成可直接给 `babelecho run --source-config <path>` 使用的 YAML。
- 没有把 API key / secret 写入 tracked 文件。

## 完成记录

- 已新增 `src/babelecho/podcast_index_api.py` 中的 search URL、fetch 和 source config builder。
- 已新增 `babelecho podcast-index search` 和 `babelecho podcast-index episodes` CLI。
- 已用端到端 fixture 覆盖 search -> episodes -> source config 输出。
