# 02.06 Discovery Adapters

状态：`done`

日期：2026-06-18

父计划：`02-real-podcasts`

## 目标

把真实来源发现入口做成可插拔的内部 adapter：每个 adapter 负责一种外部发现方式，输出 BabelEcho 已有的标准 `source` YAML，后续 transcript、翻译、TTS 和合成不关心来源来自哪里。

```text
discovery adapter -> source YAML -> ingest -> normalize -> adapt -> synthesize -> assemble -> publish
```

## 架构边界

- Adapter 是内部 Python 模块，不是第三方插件加载系统。
- 每个 adapter 都只做一个外部入口：
  - iTunes：节目搜索，拿 RSS `feedUrl`，输出 `source.type=podcast_rss`。
  - RSS：列 feed 内 episode，输出带 `episode_url` 的 `source.type=podcast_rss`。
  - YouTube：公开视频字幕获取，输出 `source.type=youtube_captions` 或直接写 run transcript。
- CLI 是薄层，只调用 adapter 并打印/写 source config。
- Pipeline 后段不增加来源特化逻辑。

## 范围

In:

- iTunes Search API：无需 API key，支持搜索 podcast show，并把选择结果写成 RSS source config。
- RSS episode selection：给定 feed URL，列出 episodes 并把选中 episode 写成 RSS source config。
- YouTube captions：用本机 `yt-dlp` 只下载公开字幕/自动字幕，不下载视频。
- 每个入口都有 fixture 测试和真实 smoke 记录。
- 文档记录官方 API/工具边界。

Out:

- 不做 Spotify。
- 不做 YouTube 音频下载。
- 不做 ASR。
- 不做 YouTube OAuth、cookies 或私有视频字幕。
- 不做通用第三方插件加载框架。

## 子计划

| 编号 | 文件 | 状态 | 目标 |
| --- | --- | --- | --- |
| 02.06.01 | [01-itunes-feed-discovery.md](./01-itunes-feed-discovery.md) | `done` | iTunes 搜索节目并输出 RSS source config |
| 02.06.02 | [02-youtube-captions-source.md](./02-youtube-captions-source.md) | `done` | YouTube 公开视频字幕作为 transcript source |
| 02.06.03 | [03-rss-episode-selection.md](./03-rss-episode-selection.md) | `done` | RSS feed episode 列表和选择 |

## 验收标准

- `babelecho itunes search --query ...` 能列出节目和 `feed_url`。
- `babelecho itunes search --query ... --select-index ... --source-config-out ...` 能生成可给 `babelecho run --source-config ...` 使用的 `podcast_rss` YAML。
- `babelecho itunes episodes --url <Apple Podcasts URL> --select-index ... --source-config-out ...` 能从 Apple URL 反查 RSS，列出 episodes，并生成明确单集的 `podcast_rss` YAML。
- `babelecho rss episodes --feed-url ... --select-index ... --source-config-out ...` 能生成带 `episode_url` 的 `podcast_rss` YAML。
- `babelecho run --source-config <youtube-source.yaml> --to-stage adapt` 能从 fixture YouTube subtitle source 走到中文脚本。
- 真实 YouTube smoke 只拉字幕，不下载音频，不调用 LLM/TTS。
- 代码和文档不引入真实密钥或本地私有配置。

## 完成记录

- 已新增 `src/babelecho/itunes.py` 和 `babelecho itunes search`。
- 已新增 `babelecho itunes episodes --url ...`，把 Apple Podcasts/iTunes URL 收敛到 RSS episode 人工选择流程，不自动转换 show。
- 已新增 `babelecho rss episodes`，把 feed 内人工选择的 episode 落成 `podcast_rss` source config。
- 已新增 `babelecho episode convert --url ... --select-index ...` 对 Apple Podcasts/iTunes URL 和直接 RSS feed URL 的单步编排；内部仍先人工选集，再写 `source.type=podcast_rss`，然后复用现有 normalize/adapt/TTS 后流程。
- 已新增 `src/babelecho/youtube.py` 和 `source.type=youtube_captions` ingest。
- iTunes 输出标准 `source.type=podcast_rss`；YouTube 输出标准 transcript raw 文件并继续复用 normalize/adapt。
- 真实 5090D full-chain `itunes-url-practical-ai-zero-trust-full-20260619` 已验证 Apple Podcasts URL -> iTunes Lookup -> RSS -> `podcast_rss` -> normalize -> DeepSeek adapt -> TTS -> assemble -> publish，全程不新增 iTunes 专用后流程。
- 真实短 RSS smoke `rss-podnews-fragment-merge-20260619` 已验证 direct RSS feed URL -> episode selection -> `podcast_rss` -> normalize；样本约 `296s`。normalize 层对非 YouTube timed transcript 增加保守碎段合并后，该样本从 88 段降到 18 段，质量门槛从 `inspect_first` / `too_fragmented` 变为 `safe_to_adapt`，未送入 DeepSeek。
- 单步入口 smoke 已通过：`rss-podnews-single-url-20260619` 使用 `episode convert --url https://podnews.net/rss --select-index 1` 跑到 normalize，18 段、quality=`safe_to_adapt`；`apple-practical-ai-single-url-20260619` 使用 Practical AI Apple Podcasts URL 跑到 normalize，103 段、3 speaker、quality=`safe_to_adapt`。两者均未送入 DeepSeek/TTS。
- MVP-1 收口 full-chain `rss-podnews-single-url-full-20260619` 已在 5090D 跑通：单步 RSS URL -> `podcast_rss` -> normalize -> DeepSeek adapt -> TTS -> assemble -> publish，18 段，MP3 约 `233.535s`、`22050 Hz` mono，并已拷回本机 ignored run 目录。
