# 02.06.03 RSS Episode Selection

状态：`done`

日期：2026-06-18

父计划：`02.06 Discovery Adapters`

## 目标

补齐 iTunes feed discovery 之后的下一步：给定 RSS `feedUrl`，列出 feed 内 episodes，人工选择一集后生成现有 `source.type=podcast_rss` 配置。

## 范围

In:

- `babelecho rss episodes --feed-url ...`
- 输出 episode title、episode selector URL、transcript yes/no。
- `--select-index ... --source-config-out ...` 写 YAML。
- 测试覆盖 RSS item 解析、transcript availability、source config 输出和 CLI fixture。

Out:

- 不做自动批量处理。
- 不跳过已处理 episode。
- 不下载音频。
- 不做 ASR fallback。

## 执行步骤

1. 写失败测试：从 RSS XML 列出 episodes，包含 transcript yes/no 信息。
2. 写失败测试：选中 episode 后生成 `source.type=podcast_rss` YAML。
3. 写失败测试：CLI `rss episodes` 可写 source config。
4. 实现 `list_podcast_episodes()`、`fetch_podcast_episodes()` 和 source config builder。
5. 实现 `babelecho rss episodes` CLI。
6. 跑测试和真实 RSS smoke。

## 验收标准

- `babelecho rss episodes --feed-url <rss>` 能列出 episodes。
- 输出能标记该 episode 是否有 RSS transcript。
- 选中 episode 后生成的 YAML 可直接传给 `babelecho run --source-config ...`。

## 完成记录

- 已新增 RSS episode listing 和 source config builder。
- 已新增 `babelecho rss episodes` CLI。
- fixture 已覆盖 list/select/write source config。
