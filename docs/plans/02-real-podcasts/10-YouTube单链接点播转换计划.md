# YouTube 单链接点播转换实施计划

> **给 agentic worker：** 实施本计划时，先使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`，按任务逐项执行并在每个任务后验证。所有步骤使用 checkbox 追踪。

**目标：** 支持用户提供一个 YouTube 视频或 YouTube Podcasts 单集 URL 后，生成对应中文播客。

**架构：** 第一版只增强现有 `source.type=youtube_captions` 和 `babelecho episode convert --url` 路径。`yt-dlp` 继续只拉公开字幕或自动字幕，不下载音频；新增 YouTube 字幕候选记录、字幕清洗、碎 cue 合并和更清楚的失败诊断，然后复用现有 `normalize -> adapt -> synthesize -> assemble -> publish`。

**技术栈：** Python 3.12、`yt-dlp`、现有 BabelEcho CLI、pytest、项目内 `.conda/babelecho-dev` 环境。

---

状态：`done`

日期：2026-06-19

父计划：`02-real-podcasts`

## 完成记录

- 已新增 YouTube 单视频 URL 边界判断，playlist、channel、handle/show 类 URL 会明确失败。
- 已新增 `transcript/candidates.json`，记录 YouTube 字幕 candidate、格式、语言、分数、warning、raw path 和 cleaned path。
- 已新增 VTT/SRT cleaning：清理 metadata、cue settings、重复行、HTML entities、inline timing / `<c>` caption markup，并合并过碎 YouTube cue。
- 已处理 YouTube rolling captions：相邻 cue 重复前一段文本再追加新词时，会根据短时间内的 suffix/prefix overlap 只保留新增文本，避免送入 DeepSeek 前出现大段重复句子。
- 已新增字幕说话人箭头清洗：`>>` 这类 caption speaker marker 在 cleaned/normalized 阶段移除，不依赖 DeepSeek 自行处理。
- YouTube captions 在 `normalize` 阶段会关闭 speaker label 推断，避免 `AI:`、`API:`、`RAG:` 等技术词被误识别为主持人；RSS、episode page、transcript file 等来源继续使用原 speaker label 解析。
- `source.type=youtube_captions` 现在保留 `transcript/raw.vtt` / `raw.srt`，同时写出 `transcript/cleaned.vtt` / `cleaned.srt`；`normalize` 优先读取 cleaned transcript。
- 带 `t=` 或 `start=` 的 YouTube 分享 URL 会记录 `youtube_start_ms`，CLI 输出 `start offset:`，并在 `normalize` 后裁剪掉起点之前已经结束的 segments；raw/cleaned 字幕仍保留整条原始字幕用于追溯。
- YouTube ingest 会用独立的 `yt-dlp --print title` metadata 调用提取公开视频标题；用户显式传入 `--title` 时用户标题优先。
- `normalize` 现在会写 `transcript/quality.json`，包含 `safe_to_adapt` / `inspect_first` / `reject` 推荐值、segment 数、平均长度、speaker 数、dirty markup、HTML entity 和重复度指标；CLI 同步输出 `transcript quality:` 与 `quality metrics:` 摘要。
- DeepSeek chunked adapt prompt 已收紧：必须按输入 id 一对一返回，清理字幕格式噪声和无意义口头填充，但保留事实、数字、人名、问题、因果和有意义强调；chunk 少 id 时会重试，429/5xx/URL tunnel 临时错误也会重试。
- `babelecho check --checks script` 现在会在 TTS 前拦截中文脚本中的 transcript artifact，例如 `>>`、`WEBVTT`、caption markup、HTML entity、时间轴残留和整段英文残留。
- 当前本地 DeepSeek smoke config 已从 `chunk_max_segments: 5` 调到 `12`，减少长视频 adapt 请求数；tracked `local.example.yaml` 仍维持通用示例配置。
- `babelecho episode convert --url ... --to-stage normalize` 已通过本地 pre-DeepSeek smoke：`youtube-pre-deepseek-ai-engineering-20260618`，使用近期 LLM/agent 相关 YouTube 单集 URL，生成 48 个 normalized segments，平均约 219 字符，quality 推荐 `safe_to_adapt`，未调用 DeepSeek/TTS。
- 另测 `youtube-pre-deepseek-claude-second-brain-20260618` 和 `youtube-pre-deepseek-code-with-claude-20260618`，均为 `safe_to_adapt`，dirty markup 和 HTML entity 均为 0。
- 用户提供的 `https://www.youtube.com/watch?v=yAI8osNcMNw&t=1521s` 已重跑到 `normalize`、`adapt` 和 5090D TTS：标题为 `特朗普记者会谈美伊备忘录，感谢习近平普京｜新闻特写20260618`，`start offset: 1521s`，normalized 从整条 318 段裁剪并清洗为 223 段，quality 仍为 `safe_to_adapt`；DeepSeek adapt 生成 223 段 `script/zh.json`，script QA 通过。
- 该 YouTube run 的 3 段 5090D TTS 小样本已通过；由于 YouTube captions 通常没有 speaker 标签，后续补充了 `speaker_voices.default_voice_role`，可在声纹/ASR 之前手动指定无 speaker run 的默认男/女声。使用 `default_voice_role: male_a` 的完整 5090D TTS 已通过：manifest 223 段全部 `male_a`，最终 `output/audio.mp3` 为 `22050 Hz` mono，约 `2602.8s`，约 `40 MB`，已拷回本机 ignored `workspace/runs/youtube-user-yai8osncmnw-start1521-20260618/output/audio.mp3` 便于听检。
- 近期 agent 主题 YouTube 端到端样本 `youtube-agent-skills-briefing-20260619` 已通过完整路径：标题 `AI Research Briefing 18062026: Auditing Agent Skills, Financial Reasoning, and Jailbreak Safety`，normalized 28 段，quality=`safe_to_adapt`，DeepSeek adapt 和 script QA 通过，5090D TTS 使用默认 `female_a`，最终 MP3 为 `22050 Hz` mono，约 `543.8s`，约 `8.3 MB`；用户试听反馈“听起来很不错”。
- YouTube 单链接探索到此先收口。原 YouTube 清洗计划没有引入订阅扫描、RSS 多 candidate、PodcastIndex 多 candidate、ASR 或 YouTube 音频下载；本轮额外做的 DeepSeek prompt 收紧和 `speaker_voices.default_voice_role` 仅服务已暴露的单链接质量边界。

## 范围

### In

- 用户提供单个 YouTube 视频 URL。
- 用户提供 YouTube Podcasts 中某一集对应的视频 URL。
- YouTube URL 中的 `t=` / `start=` 起点参数。
- 通过 `yt-dlp --skip-download` 获取公开字幕或自动字幕。
- 写入 run-local `transcript/candidates.json`，记录字幕候选、选择结果、格式、语言、评分、警告和失败原因。
- 保留原始 `transcript/raw.vtt` / `raw.srt`，另写清洗后的 `transcript/cleaned.vtt` / `cleaned.srt`。
- 合并 YouTube 过碎字幕 cue，避免生成几千个极短 TTS segment。
- 增强 `babelecho episode convert --url ...` 和 `babelecho run` 的 YouTube transcript 诊断输出。
- 生成 pre-DeepSeek `transcript/quality.json`，在不调用 LLM 的情况下给出是否适合进入 adapt 的确定性建议。

### Out

- 不做订阅扫描。
- 不做 playlist / channel / show 页面批处理。
- 不做 RSS 多 candidate。
- 不做 PodcastIndex 多 candidate。
- 不做 ASR。
- 不下载 YouTube 音频。
- 不改 publish/feed 输出结构。

## 成功标准

- 单个 YouTube 视频 URL 可以继续通过 `babelecho episode convert --url ...` 进入现有 pipeline。
- 字幕获取成功时，run 目录下同时保留 raw transcript、cleaned transcript 和 `candidates.json`。
- YouTube VTT/SRT 碎 cue 会合并成适合 DeepSeek/TTS 的稳定 segment 数量。
- `normalize` 后可直接查看 `transcript/quality.json` 或 CLI 摘要，判断是否 `safe_to_adapt`、需要人工检查还是应拒绝。
- playlist、channel、show 等非单集 URL 明确失败，提示需要单集视频 URL。
- 没有公开字幕时明确失败，不静默进入 ASR 或其他 fallback。
- 现有测试通过；新增 YouTube-focused tests 覆盖清洗、合并、诊断和 URL 边界。

## 文件职责

- 新增 `src/babelecho/transcript_candidates.py`：定义 transcript candidate 数据结构、评分和 `candidates.json` 写入。
- 新增 `src/babelecho/transcript_cleaning.py`：清洗 VTT/SRT，合并过碎 cue，输出 cleaned transcript。
- 新增 `src/babelecho/transcript_quality.py`：读取 normalized transcript，生成 pre-DeepSeek `quality.json`。
- 修改 `src/babelecho/youtube.py`：识别单集 URL 边界；返回字幕路径、语言、格式和诊断信息。
- 修改 `src/babelecho/ingest.py`：在 `youtube_captions` 分支写 candidates、cleaned transcript，并把 `source.json` 指向可用于 normalize 的 transcript。
- 修改 `src/babelecho/transcript.py`：保持 raw VTT/SRT 解析兼容，必要时优先读取 cleaned transcript。
- 修改 `src/babelecho/cli.py`：输出 YouTube transcript candidate、cleaned transcript、质量摘要和失败原因。
- 修改 `src/babelecho/episode_convert.py`：拒绝 playlist/channel/show 类 URL，只接受单集视频 URL。
- 新增 `tests/test_transcript_candidates.py`：覆盖 candidate JSON 和 YouTube candidate 评分。
- 新增 `tests/test_transcript_cleaning.py`：覆盖 VTT/SRT 清洗与碎 cue 合并。
- 新增 `tests/test_transcript_quality.py`：覆盖 deterministic quality report、推荐值和指标。
- 修改 `tests/test_youtube.py`、`tests/test_transcript.py`、`tests/test_episode_convert.py`、`tests/test_ingest.py`：覆盖集成行为。

## 执行步骤

### 任务 1：建立测试基线

**Files:**

- Read: `README.md`
- Read: `docs/plans/02-real-podcasts/10-YouTube单链接点播转换计划.md`
- Test: existing test suite

- [ ] 运行当前测试基线。

```bash
.conda/babelecho-dev/bin/python -m pytest -q
```

预期：当前 main 分支测试通过。如果失败，先记录失败测试名和错误，不进入实现。

### 任务 2：明确 YouTube 单集 URL 边界

**Files:**

- Modify: `src/babelecho/episode_convert.py`
- Test: `tests/test_episode_convert.py`

- [ ] 写失败测试：普通 YouTube 视频 URL 仍映射到 `source.type=youtube_captions`。

建议测试名：

```python
def test_build_on_demand_source_config_accepts_youtube_video_url():
    config = build_on_demand_source_config("https://www.youtube.com/watch?v=abc123")
    assert config["source"]["type"] == "youtube_captions"
    assert config["source"]["url"] == "https://www.youtube.com/watch?v=abc123"
```

- [ ] 写失败测试：`list` 参数、`/playlist`、`/channel`、`/@handle` 明确失败。

建议测试名：

```python
def test_build_on_demand_source_config_rejects_youtube_playlist_url():
    with pytest.raises(ValueError, match="single YouTube episode/video URL"):
        build_on_demand_source_config(
            "https://www.youtube.com/playlist?list=PLabc123"
        )
```

- [ ] 运行测试确认失败原因正确。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_episode_convert.py -q
```

预期：新增拒绝测试失败，因为当前代码还没有区分 playlist/channel/show。

- [ ] 最小实现 URL 边界判断。

实现要点：

- `watch?v=...` 和 `youtu.be/<id>` 通过。
- 含 `list=` 的 URL 拒绝。
- path 以 `/playlist`、`/channel`、`/c/`、`/@` 开头的 URL 拒绝。
- 错误信息包含 `single YouTube episode/video URL`。

- [ ] 重新运行测试。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_episode_convert.py -q
```

预期：通过。

### 任务 3：新增 YouTube transcript candidate artifact

**Files:**

- Create: `src/babelecho/transcript_candidates.py`
- Create: `tests/test_transcript_candidates.py`
- Modify: `src/babelecho/ingest.py`
- Test: `tests/test_transcript_candidates.py`
- Test: `tests/test_ingest.py`

- [ ] 写失败测试：YouTube captions 成功 ingest 后写 `transcript/candidates.json`。

建议断言：

```python
data = read_json(run_paths.transcript_dir / "candidates.json")
assert data["selected"]["source_type"] == "youtube_captions"
assert data["selected"]["format"] == "vtt"
assert data["selected"]["language"] == "en"
assert data["selected"]["selected"] is True
assert data["selected"]["raw_path"] == "transcript/raw.vtt"
assert data["candidates"][0]["score"] > 0
```

- [ ] 写失败测试：没有字幕时错误信息仍保留 `No YouTube subtitles downloaded`，并且不伪造 selected candidate。

- [ ] 运行测试确认失败。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_transcript_candidates.py tests/test_ingest.py -q
```

预期：失败，因为 candidate 模块和 JSON 写入还不存在。

- [ ] 最小实现 `TranscriptCandidate`、`write_candidates_json()` 和 YouTube candidate 评分。

字段第一版固定为：

```text
source_type
source_url
raw_path
cleaned_path
format
language
title
score
selected
warnings
rejection_reason
text_char_count
segment_count_estimate
speaker_count_estimate
has_timestamps
```

评分第一版保持简单：

- VTT/SRT 加分。
- 有语言且语言是 `en` 加分。
- 有 timestamps 加分。
- 字符数低于 1000 加 warning。
- cue 数极高且平均文本过短加 warning。

- [ ] 重新运行测试。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_transcript_candidates.py tests/test_ingest.py -q
```

预期：通过。

### 任务 4：新增字幕清洗和碎 cue 合并

**Files:**

- Create: `src/babelecho/transcript_cleaning.py`
- Create: `tests/test_transcript_cleaning.py`
- Test: `tests/test_transcript_cleaning.py`

- [ ] 写失败测试：VTT metadata 被清理。

输入包含：

```text
WEBVTT

NOTE generated by service

STYLE
::cue { color: white }

00:00:00.000 --> 00:00:01.000 align:start position:0%
Hello
```

预期 cleaned 输出保留：

```text
WEBVTT

00:00:00.000 --> 00:00:01.000
Hello
```

- [ ] 写失败测试：重复 caption 行被去重。

输入相邻 cue 文本相同或高度重复时，cleaned 输出只保留一个自然文本片段。

- [ ] 写失败测试：20 个短 cue 合并成少量 cue。

合并规则：

- 相邻 cue 时间间隔不超过 900ms。
- 当前合并文本未以 `.?!` 结束时优先合并。
- 合并后字符数不超过 450。
- 合并后总时长不超过 45 秒。
- 不跨 speaker label 合并。

- [ ] 运行测试确认失败。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_transcript_cleaning.py -q
```

预期：失败，因为清洗模块还不存在。

- [ ] 最小实现 VTT/SRT cue parser、metadata 清理、重复文本去重和 cue 合并。

实现边界：

- 不做语义修复。
- 不翻译。
- 不移动原始 raw 文件。
- 输出仍是 VTT/SRT，让现有 `parse_timed_text()` 可继续解析。

- [ ] 重新运行测试。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_transcript_cleaning.py -q
```

预期：通过。

### 任务 5：把 cleaned transcript 接入 ingest/normalize

**Files:**

- Modify: `src/babelecho/ingest.py`
- Modify: `src/babelecho/transcript.py`
- Modify: `tests/test_youtube.py`
- Modify: `tests/test_transcript.py`
- Modify: `tests/test_ingest.py`

- [ ] 写失败测试：`source.type=youtube_captions` ingest 后生成 `transcript/raw.vtt` 和 `transcript/cleaned.vtt`。

建议断言：

```python
assert (run_paths.transcript_dir / "raw.vtt").exists()
assert (run_paths.transcript_dir / "cleaned.vtt").exists()
source = read_json(run_paths.source_json)
assert source["raw_transcript"] == "transcript/raw.vtt"
assert source["normalized_transcript_source"] == "transcript/cleaned.vtt"
```

- [ ] 写失败测试：normalize 优先读取 cleaned transcript，碎 cue 合并后 segment 数减少。

建议断言：

```python
data = read_json(normalize_transcript(run_paths, cleaned_path))
assert len(data["segments"]) < original_cue_count
assert data["segments"][0]["start_ms"] == 0
```

- [ ] 运行测试确认失败。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_youtube.py tests/test_transcript.py tests/test_ingest.py -q
```

预期：失败，因为 ingest 还没有接入 cleaned transcript。

- [ ] 最小接入：

- YouTube branch 复制字幕到 `raw.*`。
- 调用 cleaning 输出 `cleaned.*`。
- `source.json` 保留 `raw_transcript`，新增 `normalized_transcript_source`。
- `babelecho run` normalize 阶段优先使用 `normalized_transcript_source`，缺失时回退 `raw_transcript`，保证旧 source 不破坏。

- [ ] 重新运行测试。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_youtube.py tests/test_transcript.py tests/test_ingest.py -q
```

预期：通过。

### 任务 6：增强 CLI 诊断输出

**Files:**

- Modify: `src/babelecho/cli.py`
- Modify: `tests/test_episode_convert.py`
- Modify: `tests/test_end_to_end_fixture.py`

- [ ] 写失败测试：YouTube ingest 成功时 stdout 包含候选、清洗路径和 warning。

建议输出关键词：

```text
transcript candidates:
selected transcript:
cleaned transcript:
warnings:
```

- [ ] 写失败测试：没有字幕时错误包含 `No YouTube subtitles downloaded` 和 `single episode/video URL` 的边界提示不混淆。

- [ ] 运行测试确认失败。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_episode_convert.py tests/test_end_to_end_fixture.py -q
```

预期：失败，因为 CLI 还没输出这些诊断。

- [ ] 最小实现诊断输出：

- `ingest` 或 `run` 阶段完成后，如果存在 `transcript/candidates.json`，打印 selected candidate summary。
- 如果存在 cleaned transcript，打印相对路径。
- 只打印 warning 摘要，不打印完整 transcript 内容。

- [ ] 重新运行测试。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_episode_convert.py tests/test_end_to_end_fixture.py -q
```

预期：通过。

### 任务 7：更新文档状态和示例

**Files:**

- Modify: `README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/README.md`
- Modify: `resume-prompt.md`
- Modify: `workspace/sources/youtube-captions.example.yaml`

- [ ] 更新 README 的 YouTube 说明，明确第一版支持单个视频/单集 URL，不支持 playlist/channel/show 批处理。

- [ ] 更新 roadmap 当前最高优先级，说明当前 02.09 的第一阶段先做 YouTube-first 单 URL 清洗。

- [ ] 在 `docs/plans/README.md` 增加本计划链接，状态从 `ready` 开始，实施完成后再改为 `done`。

- [ ] 更新 `resume-prompt.md`，记录当前目标和不做订阅扫描/RSS/PodcastIndex 多 candidate。

- [ ] 运行文档相关快速检查。

```bash
rg -n "订阅扫描|playlist|PodcastIndex 多 candidate|YouTube" README.md docs/roadmap.md docs/plans/README.md resume-prompt.md
```

预期：文本边界一致，不出现把订阅扫描或 RSS 多 candidate 放入当前目标的表述。

### 任务 8：本地完整验证

**Files:**

- Test: full suite

- [ ] 运行 YouTube-focused tests。

```bash
.conda/babelecho-dev/bin/python -m pytest \
  tests/test_transcript_candidates.py \
  tests/test_transcript_cleaning.py \
  tests/test_youtube.py \
  tests/test_transcript.py \
  tests/test_episode_convert.py \
  tests/test_ingest.py -q
```

预期：通过。

- [ ] 运行全量测试。

```bash
.conda/babelecho-dev/bin/python -m pytest -q
```

预期：通过。

### 任务 9：本地 YouTube pre-DeepSeek smoke

**Files:**

- Runtime outputs only under ignored `workspace/runs/`

- [ ] 选择一个公开字幕可用的单个 YouTube 视频或 YouTube Podcasts 单集 URL。

- [ ] 先只跑到 `normalize`，不调用 DeepSeek，不跑 TTS。

示例命令：

```bash
babelecho episode convert \
  --workspace workspace \
  --run-id youtube-pre-deepseek-smoke \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --local-config workspace/config/local.yaml \
  --to-stage normalize
```

预期：

- `workspace/runs/youtube-pre-deepseek-smoke/transcript/raw.vtt` 或 `raw.srt` 存在。
- `workspace/runs/youtube-pre-deepseek-smoke/transcript/cleaned.vtt` 或 `cleaned.srt` 存在。
- `workspace/runs/youtube-pre-deepseek-smoke/transcript/candidates.json` 存在。
- `workspace/runs/youtube-pre-deepseek-smoke/transcript/normalized.json` 的 segment 数合理，不是几千个短段。
- `workspace/runs/youtube-pre-deepseek-smoke/script/zh.json` 不存在，因为本 smoke 不进入 `adapt`。

- [ ] 检查 normalized segment 数和平均长度。

```bash
.conda/babelecho-dev/bin/python - <<'PY'
import json
from pathlib import Path
path = Path("workspace/runs/youtube-pre-deepseek-smoke/transcript/normalized.json")
data = json.loads(path.read_text())
segments = data["segments"]
avg = sum(len(item["text"]) for item in segments) / max(len(segments), 1)
print({"segments": len(segments), "avg_chars": round(avg, 1)})
PY
```

预期：segment 数和平均长度适合进入 DeepSeek/TTS。如果仍然过碎，回到任务 4 调整合并阈值。

- [ ] pre-DeepSeek smoke 通过后，再单独决定是否跑到 `adapt`。

```bash
babelecho episode convert \
  --workspace workspace \
  --run-id youtube-adapt-smoke \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --local-config workspace/config/local.yaml \
  --to-stage adapt
```

预期：只有当 `normalized.json` 质量可接受时才调用 DeepSeek；如果 normalized 质量不稳定，先修 transcript 清洗，不消耗 LLM 调用。

### 任务 10：提交前检查

**Files:**

- All changed files

- [ ] 查看工作区差异，确认只包含本计划范围内文件。

```bash
git status --short
git diff --stat
```

- [ ] 运行 secret / privacy 扫描。

```bash
/opt/homebrew/bin/gitleaks dir .
/opt/homebrew/bin/trufflehog filesystem .
rg -n "BEGIN (RSA|OPENSSH|EC|DSA)? ?PRIVATE KEY|sk-[A-Za-z0-9]|ghp_|AKIA|Bearer [A-Za-z0-9._-]+|password\\s*[:=]" .
```

预期：没有真实密钥、token、服务器地址或生成媒体进入 git。若扫描命中 fixture 假数据，记录原因并确认不是秘密。

- [ ] 提交并推送。

```bash
git add .
git commit -m "feat: improve youtube single-url transcript cleaning"
git push origin main
```

- [ ] 如需 5090D 验证，远端 pull 后只跑 transcript-only smoke，确认无误再跑完整 TTS。

```bash
ssh my-5090d-host
cd /home/th5090d/Develop/personal_project/BabelEcho
git pull --ff-only
```

## 风险和分支处理

- 如果某个 YouTube URL 没有公开字幕：明确失败，不进入 ASR。
- 如果 URL 是 playlist/channel/show：明确失败，要求用户提供单集视频 URL。
- 如果自动字幕语义差：本计划只修结构，不修语义。
- 如果 cleaned transcript 仍然过碎：优先调整 cue 合并阈值，不改 DeepSeek prompt 或 TTS。
- 如果 `yt-dlp` 站点行为变化：先修 `src/babelecho/youtube.py` 的字幕选择和错误诊断，不改 pipeline 其他阶段。
- 如果真实 smoke 需要网络或本机 `yt-dlp` 不可用：本地 tests 仍用 fake `yt-dlp`；真实 smoke 标记为未执行，并在 5090D 或可联网环境补跑。

## 自检清单

- [ ] 本计划只覆盖 YouTube / YouTube Podcasts 单 URL。
- [ ] 本计划没有把订阅扫描、RSS 多 candidate、PodcastIndex 多 candidate 放入当前实现范围。
- [ ] 每个实现任务都有对应测试。
- [ ] 原始字幕保留，cleaned transcript 单独写出。
- [ ] 失败路径可解释。
- [ ] 不引入 ASR、音频下载、DeepSeek prompt 改动或 TTS 路由改动。
