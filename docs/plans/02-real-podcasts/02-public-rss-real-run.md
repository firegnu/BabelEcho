# 02.02 Public RSS End-to-End Real Run 记录

状态：`done`

日期：2026-06-17

父计划：`02-real-podcasts`

## 目标

用一个公开 RSS feed 验证 MVP-1 当前真实链路：

```text
RSS feed -> podcast:transcript -> ingest -> normalize -> DeepSeek adapt -> CosyVoice cross_lingual TTS -> assemble -> publish
```

## 输入

- Feed：`https://feeds.transistor.fm/podcasts-for-profit-with-morgan-franklin`
- Episode：`https://morganfranklin.media/when-should-you-monetize-your-podcast/`
- Title：`#030: When Should You Monetize Your Podcast?`
- Transcript：RSS item 内的 `podcast:transcript`，实际下载为 SRT。

## 配置

- LLM：DeepSeek OpenAI-compatible provider，使用 5090D ignored `workspace/config/deepseek.env`。
- TTS：5090D 本地 CosyVoice2 CLI wrapper。
- Voice baseline：`mode=cross_lingual`、`prompt_wav=/home/th5090d/Develop/ai_tools/CosyVoice/asset/cross_lingual_prompt.wav`、`speed=1.0`。
- Run ID：`mvp1-real-rss-monetize-20260617`。

## 验收记录

5090D 已跑通完整链路：

```bash
babelecho run \
  --workspace workspace \
  --run-id mvp1-real-rss-monetize-20260617 \
  --podcast-feed "https://feeds.transistor.fm/podcasts-for-profit-with-morgan-franklin" \
  --episode-url "https://morganfranklin.media/when-should-you-monetize-your-podcast/" \
  --local-config workspace/config/local-cosyvoice-cross.yaml
```

结果：

- `run.json`：`status=succeeded`，`failed_stage=None`。
- `source.json`：title 和 original URL 正确。
- `normalized.json`：75 段。
- `script/zh.json`：75 段。
- `segments/manifest.json`：75 个 wav segment。
- `output/audio.mp3`：`mp3`、`24000 Hz`、mono、约 `840.8s`、约 `13.5 MB`。
- `publish/feed.xml` 已生成。
- `workspace/published/feed.xml` 已更新。

独立检查：

```text
script_segments=75
audio_segments=75
output_sample_rate=24000
output_channels=1
output_duration_seconds=840.816
```

产物已从 5090D 拷回本机 ignored 路径：

```text
workspace/runs/mvp1-real-rss-monetize-20260617/
```

## 观察

- 当前能力已经可以把一个有公开 `podcast:transcript` 的 RSS episode 处理成中文 MP3 和 feed。
- 这次仍是单固定中文音色，不做原主播 voice clone，也没有 `speaker -> voice` 映射。
- 该 run 暴露了 TTS wrapper 每段独立启动 CosyVoice 的性能问题；后续已通过 `local_cli` batch wrapper 修复，`synthesize` 现在一次启动 wrapper 并循环生成 segment wav。
