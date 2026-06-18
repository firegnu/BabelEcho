# 02.08 On-demand Episode Convert

状态：ready

## 目标

把 MVP-1 的下一步主线从“订阅某些播客并持续扫描”校正为“用户对某一期感兴趣时，把这一期转换成中文播客音频”。

第一版优先支持精确输入，不做泛搜索：

```text
episode URL / source YAML / transcript file
-> transcript discovery
-> normalize
-> chunked DeepSeek adapt
-> local TTS
-> assemble MP3
-> optional publish feed item
```

## 范围

In:

- 新增一个点播式 CLI 入口，用于转换单集。
- 支持精确 URL 输入，优先复用现有 `youtube_captions`、`episode_page`、`podcast_rss`、`transcript_file` source 合同。
- 找不到 transcript 时明确失败，并说明原因。
- 保留 `--to-stage adapt` / `--from-stage synthesize` 等阶段控制。
- 输出现有 run artifacts，不新增发布格式。

Out:

- 不做节目订阅扫描。
- 不做多 episode 批处理。
- 不把 skip-processed 作为当前主流程。
- 不解析 Spotify 或 Apple Podcasts 页面。
- 不做 ASR。
- 不下载 YouTube 音频。
- 不做原主播 voice clone。

## 可执行步骤

1. 写失败测试：URL resolver 可以识别 YouTube URL 和普通 episode page URL，并拒绝未知 URL。
2. 实现最小 URL resolver，只把输入映射到现有 source config，不新增解析能力。
3. 写失败测试：CLI 接收 `--url` 后生成 run source，并复用现有 pipeline 到指定 stage。
4. 实现点播式 CLI 薄层，例如 `babelecho episode convert --url ...`。
5. 写失败测试：找不到 transcript 时错误信息清楚，不进入后续阶段。
6. 用 fixture 跑通至少一个 URL source 到 `adapt`。
7. 跑完整 pytest。
8. 更新 `README.md`、`docs/roadmap.md` 和 `resume-prompt.md` 的下一步说明。

## 验收标准

- 用户给一个可支持的 episode URL，可以一条命令转换这一集。
- 成功时输出 `script/zh.json` 和 `output/audio.mp3`，可选输出 `publish/feed.xml`。
- 失败时能明确说明是不支持该 URL、没有公开字幕，还是页面/RSS 没有 transcript。
- 代码不引入 ASR、订阅扫描或站点特化的大型 scraper。

## 后续

- 增加“节目名 + 期数/关键词”的搜索选择流程。
- 增加 converted episode library，用于查看历史转换结果。
- 如以后需要，再做多 episode batch 和 skip-processed。
