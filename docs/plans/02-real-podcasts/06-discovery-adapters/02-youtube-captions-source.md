# 02.06.02 YouTube Captions Source

状态：`done`

日期：2026-06-18

父计划：`02.06 Discovery Adapters`

## 目标

把公开视频的 YouTube 字幕作为 transcript source 接入 BabelEcho。第一版只获取字幕，不下载音频，不做 ASR。

## 范围

In:

- 新增 `source.type=youtube_captions`。
- source config 支持 `url`、`language`、`yt_dlp_command`。
- ingest 调用 `yt-dlp --skip-download` 写 VTT/SRT 到临时目录，再复制到 `transcript/raw.vtt` 或 `raw.srt`。
- 记录 `source.json` 中的 `youtube_url`、`youtube_language`、`youtube_subtitle_file`。
- fixture 测试用本地 fake `yt-dlp` 脚本模拟字幕输出。

Out:

- 不用 YouTube Data API OAuth。
- 不处理 cookies、会员内容、私有视频或登录态。
- 不下载视频或音频。
- 不做 ASR fallback。

## 执行步骤

1. 写失败测试：YouTube source config 通过 fake `yt-dlp` 写出 `transcript/raw.vtt` 和 `source.json`。
2. 写失败测试：没有字幕文件时给出明确错误。
3. 实现 `src/babelecho/youtube.py`。
4. 在 `ingest.py` 接入 `source.type=youtube_captions`。
5. 补 example source config 和 docs。
6. 跑本地测试和真实字幕-only smoke。

## 验收标准

- fixture 能完整跑到 `adapt`。
- 真实 smoke 命令包含 `--skip-download`。
- 没有字幕时失败，不静默进入 ASR 或音频下载。

## 完成记录

- `source.type=youtube_captions` 已接入 `ingest`。
- `yt-dlp` 调用固定包含 `--skip-download`、`--write-subs` 和 `--write-auto-subs`。
- fixture fake `yt-dlp` 已覆盖字幕写入、缺字幕失败和 `run --to-stage adapt`。
