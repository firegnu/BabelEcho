# 单 URL 自用运行手册

本文记录 BabelEcho 当前自用阶段“我提供一个 URL，生成对应中文播客”的固定操作路径。目标是让来源入口保持清楚、可回归，并在进入 DeepSeek/TTS 前先用 deterministic 质量门槛挡住明显不适合继续的 transcript。

## 范围

当前只处理单个输入，不做订阅扫描、多集批处理、ASR、后台服务或网页 UI。

已支持的单 URL 入口：

- YouTube 单视频 URL，含 YouTube Podcasts 中对应的视频 URL。
- 普通标准播客单集页面 URL，页面上需要有 transcript 正文或 transcript 链接。
- Apple Podcasts/iTunes 节目或单集 URL，通过 iTunes Lookup 找 RSS feed，再人工选一集。
- 直接 RSS feed URL，人工选一集。

暂不把 Apple Podcasts URL、RSS feed URL 自动塞进 `episode convert --url`。这两类先显式列集、人工选择、写 `source.type=podcast_rss` YAML，再进入同一个后流程。

## 基本变量

本机或 5090D 都用项目内 Python：

```bash
export PYTHON=.conda/babelecho-dev/bin/python
export WORKSPACE=workspace
```

本机只做 transcript/DeepSeek 前验证时可用 fixture config：

```bash
export LOCAL_CONFIG=workspace/config/fixture-local.yaml
```

本机真实 DeepSeek adapt 使用 ignored local config，例如：

```bash
export LOCAL_CONFIG=workspace/config/local-deepseek-chunked-smoke.yaml
```

5090D full-chain 使用已验证的 ignored runtime config：

```bash
export LOCAL_CONFIG=workspace/config/local-cosyvoice-on-demand-chunked.yaml
```

真实 config、`workspace/sources/*.yaml`、`workspace/runs/`、音频产物和 API key 都不要提交。

## 决策顺序

拿到一个 URL 后先按这个顺序判断：

1. `youtube.com/watch` 或 `youtu.be/...` 单视频：走 YouTube 单视频入口。
2. `podcasts.apple.com/...`：走 Apple Podcasts/iTunes 列集入口。
3. 明确是 RSS/XML feed URL：走 direct RSS feed 列集入口。
4. 其他 http/https 播客单集页面：走 episode page 入口。
5. 本地 transcript 文件：走 `--transcript-file`。

YouTube playlist、channel、show、订阅页暂不支持；需要用户提供具体单集视频 URL。

## 第一步：只跑到 Normalize

任何新 URL 都先跑到 `normalize`。这一步会生成：

```text
workspace/runs/<run-id>/transcript/raw.*
workspace/runs/<run-id>/transcript/normalized.json
workspace/runs/<run-id>/transcript/quality.json
```

### YouTube 单视频

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

带起点的 URL 可以直接保留：

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --url "https://www.youtube.com/watch?v=<video-id>&t=1521s" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

YouTube 会保留完整 raw/cleaned captions，但 `normalized.json` 会裁剪到请求起点之后。

### 普通播客单集页面

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --url "https://example.com/podcast/episode" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

如果页面没有 transcript 正文或 transcript 链接，应在 `ingest` 阶段明确失败，不回退 ASR。

### Apple Podcasts/iTunes URL

首选单步入口。`--select-index` 是人工选集编号；编号可先用 `itunes episodes`
查看，也可以在你已经知道要选第几集时直接执行：

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --url "https://podcasts.apple.com/..." \
  --select-index <n> \
  --source-config-out "workspace/sources/<slug>.yaml" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

需要先查看候选集时，仍可拆成两步排错：

```bash
$PYTHON -m babelecho itunes episodes \
  --url "https://podcasts.apple.com/..." \
  --select-index <n> \
  --source-config-out "workspace/sources/<slug>.yaml"
```

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --source-config "workspace/sources/<slug>.yaml" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

这条路的后续来源类型是 `podcast_rss`，不是 iTunes 专用 pipeline。

### 直接 RSS Feed URL

首选单步入口：

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --url "https://example.com/feed.xml" \
  --select-index <n> \
  --source-config-out "workspace/sources/<slug>.yaml" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

需要先查看候选集时，仍可拆成两步排错：

```bash
$PYTHON -m babelecho rss episodes \
  --feed-url "https://example.com/feed.xml" \
  --select-index <n> \
  --source-config-out "workspace/sources/<slug>.yaml"
```

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --source-config "workspace/sources/<slug>.yaml" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

RSS 和 iTunes 在这里收敛到同一个 `source.type=podcast_rss` 后流程。

### 本地 Transcript 文件

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --transcript-file "/path/to/transcript.vtt" \
  --title "Episode Title" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage normalize
```

## 第二步：读质量门槛

跑完 `normalize` 后先读质量报告：

```bash
$PYTHON - <<'PY'
import json
from pathlib import Path
run = Path("workspace/runs/<run-id>")
print(json.dumps(json.loads((run / "transcript/quality.json").read_text()), ensure_ascii=False, indent=2))
PY
```

按 `recommendation` 决定下一步：

- `safe_to_adapt`：可以进入 DeepSeek / local vLLM adapt。
- `inspect_first`：先人工看 `quality.json`、`normalized.json` 和 raw transcript，不调用 DeepSeek。
- `reject`：不要继续，先换来源或修 transcript 清洗。
- 缺少 `quality.json`：不要继续，先查 `run.json` 和失败阶段。

常见 `inspect_first` 原因：

- `too_fragmented`：字幕 cue 太碎，直接送 DeepSeek 容易浪费 token 或降低文本质量。
- `too_short`：正文可能不是完整节目。
- `dirty_markup` / `html_entities`：清洗不充分。
- `high_repetition`：rolling captions 或页面重复正文可能没清干净。

## 第三步：进入 DeepSeek

只有 `safe_to_adapt` 才进入真实 LLM。

当前默认改写风格是 `adapt.style: faithful_spoken`：尽量忠实保留原 transcript 的信息、顺序、语气、问题、数字、人名和观点组织，只做字幕噪声、舞台提示、转写说明、URL/缩写读法等轻清理，并让中文适合 TTS 朗读。

如果明确想要更像中文播客的宽松润色，可在 ignored local config 中设置：

```yaml
adapt:
  mode: chunked
  style: polished_spoken
```

`polished_spoken` 不作为默认。日常自用优先使用 `faithful_spoken`，避免 LLM 过度压缩、补充或重组原文。

本机只跑到 DeepSeek adapt，不跑 TTS：

```bash
$PYTHON -m babelecho episode convert \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --url "<url>" \
  --local-config "workspace/config/local-deepseek-chunked-smoke.yaml" \
  --from-stage adapt \
  --to-stage adapt
```

如果输入是 Apple/RSS 生成的 source config，把 `--url` 换成：

```bash
--source-config "workspace/sources/<slug>.yaml"
```

adapt 后检查中文脚本：

```bash
$PYTHON -m babelecho check \
  --workspace "$WORKSPACE" \
  --run-id "<run-id>" \
  --checks script
```

如果 script check 不通过，不进入 TTS。

## 第四步：5090D Full-Chain

完整 TTS/publish 优先在 5090D 上跑。详细远程流程见 [5090D远程测试流程](5090D远程测试流程.md)。

先确保 5090D 是最新 `main`：

```bash
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && git pull --ff-only && git status --short --branch'
```

YouTube / episode page 直接 URL：

```bash
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && .conda/babelecho-dev/bin/python -m babelecho episode convert --workspace workspace --run-id <run-id> --url "<url>" --local-config workspace/config/local-cosyvoice-on-demand-chunked.yaml --to-stage publish'
```

Apple/RSS source config：

`workspace/sources/<slug>.yaml` 是 ignored runtime 文件，不会随 git 同步到 5090D。远端 full-chain 前，要么在 5090D 上重新运行 `itunes episodes` / `rss episodes` 生成同名 source config，要么从本机 `scp` 过去。

```bash
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && .conda/babelecho-dev/bin/python -m babelecho episode convert --workspace workspace --run-id <run-id> --source-config workspace/sources/<slug>.yaml --local-config workspace/config/local-cosyvoice-on-demand-chunked.yaml --to-stage publish'
```

运行后做 artifact check：

```bash
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && .conda/babelecho-dev/bin/python -m babelecho check --workspace workspace --run-id <run-id> --checks script segments output'
```

## 拷回试听产物

通常只拷 MP3 和小元数据，不拷分段 wav：

```bash
run="workspace/runs/<run-id>"
remote="/home/th5090d/Develop/personal_project/BabelEcho/workspace/runs/<run-id>"
mkdir -p "$run/output" "$run/transcript" "$run/script" "$run/segments" "$run/publish"
scp "my-5090d-host:$remote/output/audio.mp3" "$run/output/audio.mp3"
scp "my-5090d-host:$remote/run.json" "$run/run.json"
scp "my-5090d-host:$remote/transcript/quality.json" "$run/transcript/quality.json"
scp "my-5090d-host:$remote/script/speaker-voices.json" "$run/script/speaker-voices.json"
scp "my-5090d-host:$remote/segments/manifest.json" "$run/segments/manifest.json"
scp "my-5090d-host:$remote/publish/feed.xml" "$run/publish/feed.xml"
```

确认 MP3：

```bash
ffprobe -v error -show_entries format=duration,size:stream=codec_name,sample_rate,channels -of json "$run/output/audio.mp3"
```

`workspace/runs/` 是 ignored runtime 目录，试听产物不要提交。

## 已验证的入口状态

- YouTube 单视频：已跑过 normalize、DeepSeek、5090D TTS full-chain。
- 标准 episode page：已跑过多个真实标准播客 normalize，99PI/Practical AI 等样本已跑过 full-chain。
- Apple Podcasts/iTunes URL：`itunes-url-practical-ai-zero-trust-full-20260619` 已在 5090D full-chain 通过；单步 `episode convert --url ... --select-index ...` smoke `apple-practical-ai-single-url-20260619` 已跑到 normalize，103 段、3 speaker、quality=`safe_to_adapt`。
- 直接 RSS feed URL：单步 `episode convert --url ... --select-index ...` smoke `rss-podnews-single-url-20260619` 已跑到 normalize；Podnews timed transcript 样本经碎段合并后从 88 段降到 18 段，quality=`safe_to_adapt`。收口 full-chain `rss-podnews-single-url-full-20260619` 已在 5090D 跑通 DeepSeek/TTS/assemble/publish，MP3 约 `233.535s`、`22050 Hz` mono，已拷回本机 ignored run 目录。

## 失败时先看哪里

1. `workspace/runs/<run-id>/run.json`：失败阶段和错误字符串。
2. `workspace/runs/<run-id>/transcript/quality.json`：是否允许进入 DeepSeek。
3. `workspace/runs/<run-id>/source.json`：实际 source type、transcript URL、episode URL。
4. YouTube 额外看 `transcript/candidates.json`：字幕候选和拒绝原因。
5. DeepSeek 失败看 `script/adapt-chunks/`：哪个 chunk 失败或重试。

如果失败发生在来源发现阶段，先换一个明确的单集 URL 或 RSS item；不要把订阅扫描、多 candidate 搜索、ASR 混进当前路径。
