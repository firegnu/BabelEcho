# 02.06.01 iTunes Feed Discovery

状态：`done`

日期：2026-06-18

父计划：`02.06 Discovery Adapters`

## 目标

用 Apple iTunes Search API 搜索 podcast show，提取 `feedUrl`，并生成现有 `source.type=podcast_rss` 配置。

## 范围

In:

- `babelecho itunes search --query ...`
- `--country US` 和 `--max` 参数。
- `--select-index ... --source-config-out ...` 写 YAML。
- 测试覆盖 URL 构造、结果解析、source config 输出和 CLI fixture。

Out:

- 不搜索单集标题。
- 不解析 Apple Podcasts 页面。
- 不下载 Apple/Podcast 音频。

## 执行步骤

1. 写失败测试：iTunes search URL 使用 `media=podcast`、`entity=podcast`、`term`、`country` 和 `limit`。
2. 写失败测试：从搜索结果生成 `podcast_rss` source config。
3. 写失败测试：CLI 使用 fake iTunes server 搜索并写 source config。
4. 实现 `src/babelecho/itunes.py`。
5. 实现 `babelecho itunes search` CLI。
6. 补示例和 roadmap/resume。
7. 跑测试和真实 iTunes search smoke。

## 验收标准

- 搜索结果显示节目 title、artist、feed URL 和 Apple URL。
- 选中结果输出的 YAML 只包含 RSS 处理所需字段，不保存 Apple 私有状态。

## 完成记录

- `babelecho itunes search --query ...` 已可列出 podcast show、artist、feed URL 和 Apple URL。
- `--select-index ... --source-config-out ...` 已可写出 `source.type=podcast_rss` YAML。
- fake server CLI fixture 已覆盖 search -> source config 输出。
- `babelecho itunes episodes --url <Apple Podcasts URL>` 已可从 Apple Podcasts/iTunes URL 解析节目 id，lookup 出 RSS `feedUrl`，复用 `rss episodes` 列表与 `--select-index ... --source-config-out ...` 生成明确单集的 `podcast_rss` YAML。
- 真实 smoke `itunes-url-practical-ai-zero-trust-deepseek-adapt-20260619` 使用 Practical AI Apple Podcasts URL，选中 `Zero Trust for AI Agents`，normalize 后 103 段、3 speaker、quality=`safe_to_adapt`，DeepSeek adapt 和 script QA 通过，未进入 TTS。
