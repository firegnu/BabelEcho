# 03.01 Audio-first 本地音频 ASR 与说话人分离计划

状态：in_progress

日期：2026-06-19

父计划：`03-audio-first-asr`

## 目标

建立一条独立的 Route B：用户提供本地音频文件后，系统先做 ASR，再做 speaker diarization / 声纹聚类，生成现有后流程可消费的 `transcript/normalized.json`。

第一轮目标不是追求最佳 ASR 或最佳声纹模型，而是先把 audio-first 的工程边界、CLI、artifact contract、质量门禁和回归测试做稳。真实 ASR/diarization 模型随后以 provider/adapter 形式接入，避免把重依赖和模型环境塞进现有 YouTube/RSS/iTunes/Article 路线。

## 背景

当前 BabelEcho 已完成 Route A：

```text
single URL / source YAML / transcript file / article
  -> deterministic transcript/article extraction
  -> transcript/normalized.json
  -> DeepSeek adapt
  -> local TTS
  -> assemble
  -> publish
```

Route B 要新增：

```text
local audio file
  -> audio ingest
  -> ASR
  -> speaker diarization / voice profile
  -> transcript/normalized.json
  -> existing adapt/TTS/publish
```

关键边界：Route B 可以复用 `adapt -> synthesize -> assemble -> publish` 原子能力，但不能改写 `babelecho episode convert`、`babelecho run`、`source.type=youtube_captions`、`podcast_rss`、`episode_page`、`article_reading` 的现有语义。

## 范围

### In

- 新增独立 CLI：`babelecho audio convert`，必填参数包含 `--audio-file`。
- 第一版只接受本地音频文件，不下载 URL 音频。
- 新增独立 audio-first pipeline stage。
- 写入 audio-first 专属 artifacts：
  - `audio/input.*` 或 `audio/input.json`
  - `audio/metadata.json`
  - `asr/raw.json`
  - `asr/diarization.json`
  - `asr/speaker-profiles.json`，可选
  - `transcript/normalized.json`
  - `transcript/quality.json`
- 支持 fixture ASR / fixture diarization provider，用于本机无重模型测试。
- 支持从 `normalize` 之后继续复用 DeepSeek/TTS/publish。
- 质量门禁至少覆盖空文本、时间戳异常、speaker 过碎、低置信度和音频 metadata 缺失。
- 发布 artifact 中 `source.type=audio_file`、`route=audio_first`、`asr` 摘要可展示给只读前端。

### Out

- 不做 YouTube/RSS/iTunes/episode page 的音频下载 fallback。
- 不做订阅扫描或多 episode 批处理。
- 不把 ASR 作为 Route A 的静默 fallback。
- 不做原主播 voice clone。
- 不做真实身份识别。
- 不发布 voiceprint embedding。
- 不把 ASR/diarization 重依赖加入普通开发测试路径。
- 不做 Web UI 任务提交或后台服务。

## 核心原则

1. **路线隔离**
   - Route A 的 transcript-first 和 article-reading 保持稳定。
   - Route B 新增独立 `audio_pipeline.py`、`audio.py` 或同等模块。
   - Route B 的 source adapter、ASR、diarization、voice profile 不进入 `ingest_transcript_source()`。

2. **先 contract，后模型**
   - 先用 fixture provider 固化 `asr/raw.json`、`asr/diarization.json`、`transcript/normalized.json`。
   - 再接真实 ASR provider。
   - 最后接真实 diarization / voice profile provider。

3. **ASR 和 diarization 分层**
   - ASR 负责“说了什么”。
   - Diarization / 声纹负责“谁在说”。
   - Voice profile 只用于 speaker 聚类和固定中文音色映射，不用于身份识别，也不用于生成原主播声音。

4. **后流程兼容**
   - Route B 输出的 `transcript/normalized.json` 必须和 Route A 后流程兼容。
   - 后续 `adapt_to_chinese()`、`synthesize_segments()`、`publish_episode()` 不应依赖具体 ASR 工具私有结构。

5. **重依赖外置**
   - 本机测试默认使用 fixture provider。
   - 真实 ASR/diarization 先通过 `local_cli` wrapper 接入 5090D，避免把模型包硬绑进轻量 Python package。

## 建议 CLI

第一版：

```bash
babelecho audio convert \
  --workspace workspace \
  --run-id audio-smoke-20260619 \
  --audio-file tests/fixtures/audio/sample.mp3 \
  --local-config workspace/config/local-audio.yaml \
  --to-stage normalize
```

后续继续：

```bash
babelecho audio convert \
  --workspace workspace \
  --run-id audio-smoke-20260619 \
  --audio-file tests/fixtures/audio/sample.mp3 \
  --local-config workspace/config/local-audio.yaml \
  --from-stage adapt \
  --to-stage publish
```

建议 Route B stages：

```text
ingest_audio -> asr -> diarize -> normalize -> adapt -> synthesize -> assemble -> publish
```

说明：

- `ingest_audio`：验证输入音频、复制或引用到 run-local `audio/`。
- `asr`：生成 `asr/raw.json`。
- `diarize`：生成 `asr/diarization.json` 和可选 `asr/speaker-profiles.json`。
- `normalize`：把 ASR + diarization 桥接成 `transcript/normalized.json` 和 `transcript/quality.json`。
- `adapt` 之后复用现有后流程。

## 建议本地配置

Fixture 配置用于测试：

```yaml
asr:
  provider: fixture
  fixture_path: tests/fixtures/asr/two-speaker-asr.json

diarization:
  provider: fixture
  fixture_path: tests/fixtures/asr/two-speaker-diarization.json

llm:
  provider: fixture

tts:
  provider: fixture

publish:
  base_url: "https://example.com/babelecho"
```

真实 5090D 配置建议使用 wrapper：

```yaml
asr:
  provider: local_cli
  command: "/home/th5090d/miniforge3/envs/babelecho-tts/bin/python tools/openai_whisper_asr_wrapper.py"
  model: "tiny.en"
  language: "en"
  device: "cuda"

diarization:
  provider: local_cli
  command: "/home/th5090d/miniforge3/envs/babelecho-asr/bin/diarization-wrapper"
  min_speakers: 1
  max_speakers: 6

publish:
  base_url: "https://example.com/babelecho"
```

真实 DeepSeek、TTS、publish 配置继续放在 5090D ignored runtime config 中，不在计划文档里复制密钥、模型目录或本地 prompt wav 路径。模型和 wrapper 的具体选择单独验证，不写死在核心 pipeline 里。

## Artifact Contract

### `audio/metadata.json`

```json
{
  "input_kind": "audio_file",
  "original_filename": "sample.mp3",
  "audio_path": "audio/input.mp3",
  "duration_seconds": 601.2,
  "sample_rate": 48000,
  "channels": 2,
  "file_size_bytes": 12345678
}
```

约束：

- 不写用户本机绝对路径。
- 不写远端路径。
- 不写模型路径。
- 如果 ffprobe 不可用，metadata 字段可为 `null`，但 quality gate 要记录 warning。

### `asr/raw.json`

第一版 canonical shape：

```json
{
  "provider": "fixture",
  "model": "fixture",
  "language": "en",
  "duration_seconds": 601.2,
  "segments": [
    {
      "id": "asr_0001",
      "start_ms": 0,
      "end_ms": 2400,
      "text": "Welcome to the show.",
      "confidence": 0.91
    }
  ]
}
```

约束：

- `start_ms` / `end_ms` 必须是整数毫秒。
- `text` 必须是未翻译的 ASR 原文。
- provider 私有字段可以放在 `metadata` 下，不让后续阶段依赖。

### `asr/diarization.json`

第一版 canonical shape：

```json
{
  "provider": "fixture",
  "model": "fixture",
  "speaker_count": 2,
  "segments": [
    {
      "start_ms": 0,
      "end_ms": 2400,
      "speaker": "speaker_1",
      "confidence": 0.72
    }
  ]
}
```

约束：

- `speaker` 初期使用 `speaker_1` / `speaker_2`。
- 不做真实身份识别。
- 不发布 voiceprint embedding。
- 允许没有 diarization：单人或 provider disabled 时统一映射为 `speaker_1` 或 `speaker=null`，具体策略由测试固定。

### `asr/speaker-profiles.json`

可选。第一版可以只写 speaker 聚类摘要：

```json
{
  "provider": "fixture",
  "profiles": [
    {
      "speaker": "speaker_1",
      "segment_count": 42,
      "duration_seconds": 320.5,
      "embedding_path": null
    }
  ]
}
```

约束：

- 文件留在 ignored run 目录。
- 不同步到 `workspace/published/`。
- 如果以后保存 embedding，只能保存 run-local 相对路径，并且 published artifact 只能展示摘要。

### `transcript/normalized.json`

Route B 最终桥接到现有后流程的格式：

```json
{
  "episode_id": "audio-smoke-20260619",
  "language": "en",
  "segments": [
    {
      "id": "0001",
      "start_ms": 0,
      "end_ms": 2400,
      "speaker": "speaker_1",
      "text": "Welcome to the show.",
      "source": "asr"
    }
  ]
}
```

约束：

- segment id 使用现有四位数字字符串。
- `speaker` 可以是 `speaker_1` / `speaker_2`，也可以为 `null`，但同一个 run 内必须稳定。
- 文本不翻译、不总结、不润色。
- 时间戳必须单调；重叠段需要被合并、拆分或写 warning。

### `transcript/quality.json`

复用 `safe_to_adapt` / `inspect_first` / `reject` 语义，但 metrics 增加 audio-first 字段：

```json
{
  "recommendation": "inspect_first",
  "metrics": {
    "segment_count": 96,
    "speaker_count": 2,
    "total_chars": 18000,
    "avg_confidence": 0.84,
    "low_confidence_segment_count": 7,
    "timestamp_error_count": 0,
    "speaker_turn_count": 48,
    "avg_speaker_turn_ms": 18000,
    "source_type": "audio_file",
    "extractor": "asr"
  },
  "warnings": ["low_confidence_segments"],
  "reasons": []
}
```

## 文件职责

建议新增：

- `src/babelecho/audio_pipeline.py`
  - 编排 Route B stages。
  - 保持和 `article_pipeline.py` 类似的独立 pipeline。
- `src/babelecho/audio_source.py`
  - 验证本地音频输入。
  - 写 `audio/input.*` 或 `audio/input.json`。
  - 写 `source.json` 和 `audio/metadata.json`。
- `src/babelecho/asr.py`
  - 定义 ASR provider interface。
  - 实现 `fixture` 和 `local_cli` provider。
  - 写 `asr/raw.json`。
- `src/babelecho/diarization.py`
  - 定义 diarization provider interface。
  - 实现 `none`、`fixture` 和 `local_cli` provider。
  - 写 `asr/diarization.json` 和可选 `asr/speaker-profiles.json`。
- `src/babelecho/audio_normalize.py`
  - 合并 ASR text segments 与 diarization turns。
  - 写 `transcript/normalized.json`。
  - 写 audio-first `transcript/quality.json`。
- `tests/test_audio_pipeline.py`
  - 覆盖 CLI/stage 编排和 fixture full-chain。
- `tests/test_audio_source.py`
  - 覆盖音频输入验证、metadata、source privacy。
- `tests/test_asr.py`
  - 覆盖 fixture/local_cli provider shape。
- `tests/test_diarization.py`
  - 覆盖 diarization bridge 和 speaker 稳定性。
- `tests/test_audio_normalize.py`
  - 覆盖 ASR + diarization 到 normalized transcript 的转换和 quality gate。

建议修改：

- `src/babelecho/cli.py`
  - 新增 `audio convert` subcommand。
- `src/babelecho/paths.py`
  - 可选新增 `audio_dir`、`asr_dir` property；或在 Route B 模块内使用 `run_paths.run_dir / "audio"` 和 `run_paths.run_dir / "asr"`，避免影响现有代码。
- `src/babelecho/publish.py`
  - 已有 `audio_file -> audio_first` route 映射；后续补 `asr` 摘要写入 published artifact。
- `docs/Phase2双轨后端与静态前端架构.md`
  - 实现完成后同步状态。
- `resume-prompt.md`
  - 实现完成后同步当前 Route B 状态。

## 执行阶段

### 阶段 0：保护现有 Route A

目标：确认新增 Route B 前，现有来源入口有回归保护。

步骤：

1. 运行基线测试。

```bash
.conda/babelecho-dev/bin/python -m pytest -q
```

2. 单独运行来源矩阵。

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_source_matrix.py -q
```

验收：

- 当前 main 测试通过。
- 来源矩阵覆盖 YouTube、RSS、Apple/iTunes、直接 RSS。
- 如果失败，先修已有失败，不进入 Route B 实现。

### 阶段 1：Route B 最小骨架

目标：新增 `babelecho audio convert --audio-file tests/fixtures/audio/sample.mp3 --to-stage ingest_audio`，只创建 run 目录、source、audio metadata 和 run status，不跑 ASR。

TDD 步骤：

1. 写失败测试：`audio convert` 接受本地 audio file。
2. 写失败测试：缺失 audio file 明确失败。
3. 写失败测试：`source.json` 不泄露本机绝对路径。
4. 实现最小 `audio_source.py` 和 `audio_pipeline.py`。
5. 运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_source.py tests/test_audio_pipeline.py -q
```

验收：

- `source.json` 至少包含：
  - `source_type=audio_file`
  - `provider=local_file`
  - `title`
  - `audio_input=audio/input.<ext>` 或 `audio/input.json`
- `audio/metadata.json` 生成。
- 不改动 `babelecho episode convert`。

### 阶段 2：Fixture ASR Provider

目标：不接真实模型，先固定 `asr/raw.json` contract。

TDD 步骤：

1. 新增 `tests/fixtures/asr/two-speaker-asr.json`。
2. 写失败测试：`asr.provider=fixture` 会把 fixture 复制/规范化到 `asr/raw.json`。
3. 写失败测试：ASR segment 缺 `start_ms`、`end_ms` 或 `text` 时失败。
4. 实现 `asr.py` fixture provider。
5. 运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_asr.py tests/test_audio_pipeline.py -q
```

验收：

- `asr/raw.json` shape 稳定。
- CLI 输出包含 `asr: workspace/runs/<run-id>/asr/raw.json`。
- 无真实模型依赖。

### 阶段 3：Fixture Diarization Provider

目标：固定 `asr/diarization.json` contract，并能在无 diarization 时降级。

TDD 步骤：

1. 新增 `tests/fixtures/asr/two-speaker-diarization.json`。
2. 写失败测试：fixture diarization 输出 `speaker_1` / `speaker_2`。
3. 写失败测试：`diarization.provider=none` 时不产生多 speaker，仍可 normalize。
4. 写失败测试：diarization 时间戳逆序或缺 speaker 时失败。
5. 实现 `diarization.py`。
6. 运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py tests/test_audio_pipeline.py -q
```

验收：

- 有 diarization 时 speaker 标签稳定。
- 无 diarization 时仍可输出 transcript，质量报告给 warning 而不是崩溃。

### 阶段 4：ASR + Diarization 到 normalized.json

目标：实现 `audio_normalize.py`，把 ASR text segments 与 diarization turns 合并为现有后流程可读的 `transcript/normalized.json`。

合并策略第一版：

- 对每个 ASR segment，找时间重叠最多的 diarization speaker。
- 如果没有 diarization，speaker 为 `null` 或固定 `speaker_1`，以测试固定。
- 如果一个 ASR segment 横跨多个 speaker turn，第一版不拆分，选择最大重叠 speaker，并记录 warning。
- 过滤空文本。
- 合并相邻同 speaker 且间隔很短的短片段，避免过碎。

TDD 步骤：

1. 写失败测试：两个 speaker 的 ASR/diarization 输出 normalized segments。
2. 写失败测试：时间戳非单调进入 `inspect_first` 或 `reject`。
3. 写失败测试：过多短 speaker turn 进入 `inspect_first`。
4. 写失败测试：空 ASR 文本直接 `reject`。
5. 实现 `audio_normalize.py`。
6. 运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_normalize.py tests/test_audio_pipeline.py -q
```

验收：

- `transcript/normalized.json` 可以被 `adapt_to_chinese()` 读取。
- `transcript/quality.json` 使用 `safe_to_adapt` / `inspect_first` / `reject`。
- 不修改全局 transcript parser 的 Route A 行为。

### 阶段 5：Fixture Full-chain

目标：使用 fixture ASR、fixture diarization、fixture LLM、fixture TTS 跑完整 Route B 到 publish。

命令：

```bash
.conda/babelecho-dev/bin/python -c 'from babelecho.cli import main; raise SystemExit(main([
  "audio", "convert",
  "--workspace", "workspace",
  "--run-id", "audio-fixture-full-chain",
  "--audio-file", "tests/fixtures/audio/sample.mp3",
  "--local-config", "tests/fixtures/audio/local-audio-fixture.yaml",
  "--to-stage", "publish"
]))'
```

测试中应使用临时目录，不依赖真实 `workspace/`。

验收：

- 生成：
  - `source.json`
  - `audio/metadata.json`
  - `asr/raw.json`
  - `asr/diarization.json`
  - `transcript/normalized.json`
  - `script/zh.json`
  - `segments/manifest.json`
  - `output/audio.mp3`
  - `publish/feed.xml`
  - `published/episodes/<run-id>/artifact.json`
- artifact 中：
  - `route=audio_first`
  - `source.type=audio_file`
  - `asr` 不再是 `null`，至少包含 provider/model/segment_count/speaker_count/quality 摘要。

### 阶段 6：5090D 真实 ASR Provider Smoke

目标：在 5090D 上用短音频接入真实 ASR wrapper，只跑到 `asr` 或 `normalize`，不急着 TTS。

前置：

- 先确定 ASR runtime env，例如 `/home/th5090d/miniforge3/envs/babelecho-asr`。
- wrapper 命令只接受本地音频路径和输出 JSON 路径。
- wrapper 输出必须转换成 BabelEcho canonical `asr/raw.json`。

建议命令：

```bash
ssh my-5090d-host '
  cd /home/th5090d/Develop/personal_project/BabelEcho &&
  git pull --ff-only &&
  /home/th5090d/miniforge3/envs/babelecho-dev/bin/python -c '"'"'from babelecho.cli import main; raise SystemExit(main([
    "audio", "convert",
    "--workspace", "workspace",
    "--run-id", "audio-asr-smoke-20260619",
    "--audio-file", "workspace/sources/audio-smoke.mp3",
    "--local-config", "workspace/config/local-audio-asr.yaml",
    "--to-stage", "normalize"
  ]))'"'"'
'
```

执行前把短音频样本放在 5090D ignored 路径 `workspace/sources/audio-smoke.mp3`，并把真实 ASR/diarization runtime config 放在 ignored `workspace/config/local-audio-asr.yaml`。

验收：

- 5-10 分钟以内短音频生成 `asr/raw.json`。
- 人工抽查文本可读。
- `transcript/quality.json` 不为 `reject`，除非样本本身音质太差。

### 阶段 7：5090D 真实 Diarization / Voice Profile Smoke

目标：在真实多人短音频上输出稳定 speaker 段落。

步骤：

1. 选择 2 人或 3 人、5-10 分钟样本。
2. 跑到 `diarize`。
3. 检查 `asr/diarization.json` speaker_count、turn 数、平均 turn 长度。
4. 跑到 `normalize`。
5. 读 `transcript/normalized.json`，人工检查 speaker 分布是否明显错乱。

验收：

- 多人样本至少能分出 `speaker_1` / `speaker_2`。
- 单人样本不会被过度切成很多 speaker。
- `speaker-profiles.json` 不进入 published 目录。

### 阶段 8：Route B 小样本完整链路

目标：跑一条真实短音频：

```text
audio -> ASR -> diarization -> normalize -> DeepSeek -> TTS -> publish
```

建议先用 5-10 分钟样本，避免 ASR/TTS 调参成本过高。

验收：

- 用户试听 MP3。
- 检查 speaker voice role 是否能和 `speaker_1` / `speaker_2` 稳定映射。
- 检查 publish artifact 可被只读前端读取。
- 不破坏 Route A 来源矩阵。

## 测试矩阵

每个实现阶段至少运行：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_source.py -q
.conda/babelecho-dev/bin/python -m pytest tests/test_asr.py -q
.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py -q
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_normalize.py -q
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py -q
```

跨路线回归：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_source_matrix.py -q
.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q
.conda/babelecho-dev/bin/python -m pytest -q
```

如果真实模型只在 5090D 上可用，本机 tests 必须继续只依赖 fixture provider。

## 风险与处理

| 风险 | 处理 |
| --- | --- |
| ASR 依赖重，污染普通开发环境 | 核心代码只定义 provider contract；真实模型走 5090D local_cli wrapper。 |
| Diarization speaker 过碎 | quality report 加 `too_many_speaker_turns` / `avg_speaker_turn_too_short` warning；TTS 前允许人工检查。 |
| ASR 错字或断句差 | 先忠实进入 DeepSeek，不在 ASR bridge 做大改写；后续可加 ASR-specific cleaning。 |
| 声纹敏感 | 只做本地 speaker 聚类，不做身份识别；embedding 不 publish，不提交。 |
| 多 speaker 与现有 voice role 冲突 | normalized speaker 使用稳定 `speaker_1`；后续由现有 `speaker_voices` 机制映射到固定中文音色。 |
| 长音频耗时高 | 第一轮 smoke 限制 5-10 分钟；长音频 chunking/批处理后移。 |
| Route B 改动破坏 Route A | 每次改动跑 `tests/test_source_matrix.py` 和 full pytest。 |

## 完成标准

第一轮完成时：

- `babelecho audio convert --audio-file tests/fixtures/audio/sample.mp3 --to-stage normalize` 可用。
- 本机 fixture 能跑到 `publish`。
- 真实 5090D 短音频至少能跑到 `normalize`。
- `transcript/normalized.json` 可复用现有 DeepSeek/TTS/publish 后流程。
- `publish` artifact 对 `audio_first` 有合理 source/asr/quality/media 字段。
- Route A 来源矩阵和全量测试仍通过。

## 当前完成记录

### 2026-06-19：阶段 1 Route B 最小骨架

- 已新增独立 `babelecho audio convert` CLI。
- 阶段 1 初始版本只支持 `--to-stage ingest_audio`，不接 ASR、不接 diarization、不进 DeepSeek/TTS/publish。
- 已新增 `source.type=audio_file` 本地音频输入验证和 run-local artifact：
  - `source.json`
  - `audio/input.<ext>`
  - `audio/metadata.json`
  - `run.json`
- `source.json` 和 `audio/metadata.json` 不写本机绝对路径，只写 run-local 相对路径。
- `run.json.outputs` 已能记录 `audio_metadata=audio/metadata.json`。
- 已新增测试：
  - `tests/test_audio_source.py`
  - `tests/test_audio_pipeline.py`
- 验证通过：
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_source.py tests/test_audio_pipeline.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_source_matrix.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_article.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest -q`

### 2026-06-19：阶段 2 Fixture ASR Provider

- 已新增 fixture ASR provider：`asr.provider=fixture`。
- `babelecho audio convert --to-stage asr` 已能在 run-local 写入：
  - `asr/raw.json`
- `asr/raw.json` 当前 canonical shape 包含：
  - `provider`
  - `model`
  - `language`
  - `duration_seconds`
  - `segments[]`
- `segments[]` 必须包含：
  - `start_ms`
  - `end_ms`
  - `text`
- 当前仍不接真实 ASR 模型、不接 diarization、不做声纹、不进 DeepSeek/TTS/publish。
- 已新增测试：
  - `tests/test_asr.py`
  - `tests/fixtures/asr/two-speaker-asr.json`
- 验证通过：
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_asr.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_asr_stage_writes_fixture_asr_artifact -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_source.py tests/test_audio_pipeline.py tests/test_asr.py -q`

### 2026-06-19：阶段 3 Fixture Diarization Provider

- 已新增 fixture diarization provider：`diarization.provider=fixture`。
- `babelecho audio convert --to-stage diarize` 已能在 run-local 写入：
  - `asr/diarization.json`
- `asr/diarization.json` 当前 canonical shape 包含：
  - `provider`
  - `model`
  - `speaker_count`
  - `segments[]`
- `segments[]` 必须包含：
  - `start_ms`
  - `end_ms`
  - `speaker`
- `diarization.provider=none` 会写空 artifact：
  - `speaker_count=1`
  - `segments=[]`
  - `warnings=["diarization_disabled"]`
- 当前仍不接真实 diarization 模型、不做声纹、不进 DeepSeek/TTS/publish。
- 已新增测试：
  - `tests/test_diarization.py`
  - `tests/fixtures/asr/two-speaker-diarization.json`
- 验证通过：
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_writes_fixture_diarization_artifact -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_source.py tests/test_audio_pipeline.py tests/test_asr.py tests/test_diarization.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest -q`

### 2026-06-19：阶段 4 ASR + Diarization 到 normalized.json

- 已新增 audio-first normalize bridge：`audio_normalize.py`。
- `babelecho audio convert --to-stage normalize` 已能把 fixture ASR + fixture/none diarization 转换为：
  - `transcript/normalized.json`
  - `transcript/quality.json`
- `transcript/normalized.json` 使用现有后流程兼容 shape：
  - `episode_id`
  - `language`
  - `segments[]`
- `segments[]` 使用四位字符串 id，保留 ASR 原文，不翻译、不总结、不润色，`source="asr"`。
- 第一版 speaker 分配策略：
  - 有 diarization 时，对每个 ASR segment 选择时间重叠最多的 speaker turn。
  - `diarization.provider=none` 或无 turn 时，统一映射为 `speaker_1`。
  - ASR segment 横跨多个 speaker turn 时不拆分，选择最大重叠 speaker，并写 warning。
  - 相邻同 speaker、间隔短、文本短的 ASR segment 会合并，避免过碎。
- `transcript/quality.json` 为 audio-first 专属报告，保留 `safe_to_adapt` / `inspect_first` / `reject` 语义，并增加：
  - `avg_confidence`
  - `low_confidence_segment_count`
  - `timestamp_error_count`
  - `speaker_turn_count`
  - `avg_speaker_turn_ms`
  - `short_speaker_turn_count`
  - `source_type`
  - `extractor`
- 当前仍不接真实 ASR、真实 diarization、声纹、DeepSeek/TTS/publish。
- 已新增测试：
  - `tests/test_audio_normalize.py`
- 验证通过：
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_normalize.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_normalize_stage_writes_transcript_artifacts -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_source.py tests/test_audio_pipeline.py tests/test_asr.py tests/test_diarization.py tests/test_audio_normalize.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest -q`

### 2026-06-19：阶段 5 Fixture Full-chain

- `babelecho audio convert --to-stage publish` 已能用 fixture ASR、fixture diarization、fixture LLM、fixture TTS 跑完整 Route B 到 publish。
- audio-first pipeline 当前 stage 顺序：
  - `ingest_audio`
  - `asr`
  - `diarize`
  - `normalize`
  - `adapt`
  - `synthesize`
  - `assemble`
  - `publish`
- 复用现有后流程原子能力：
  - `adapt_to_chinese()`
  - `synthesize_segments()`
  - `assemble_audio()`
  - `publish_episode()`
- Fixture full-chain 已生成并验证：
  - `source.json`
  - `audio/metadata.json`
  - `asr/raw.json`
  - `asr/diarization.json`
  - `transcript/normalized.json`
  - `script/zh.json`
  - `segments/manifest.json`
  - `output/audio.mp3`
  - `publish/feed.xml`
  - `published/episodes/<run-id>/artifact.json`
- `publish` artifact 对 `route=audio_first` 已输出 ASR 摘要，不发布私有路径或 voiceprint embedding：
  - `provider`
  - `model`
  - `language`
  - `duration_seconds`
  - `segment_count`
  - `speaker_count`
  - `diarization_provider`
  - `quality`
- 当前仍不接真实 ASR、真实 diarization 或声纹。
- 已新增/扩展测试：
  - `tests/test_audio_pipeline.py::test_audio_convert_publish_stage_runs_fixture_full_chain`
  - `tests/test_publish.py::test_publish_episode_adds_audio_first_asr_summary`
- 验证通过：
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_publish_stage_runs_fixture_full_chain -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py::test_publish_episode_adds_audio_first_asr_summary -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_source.py tests/test_audio_pipeline.py tests/test_asr.py tests/test_diarization.py tests/test_audio_normalize.py tests/test_publish.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest -q`

### 2026-06-19：阶段 6 真实 ASR Provider Smoke 起步

- 5090D 上已确认本地 ASR 基础环境：
  - Python env：`/home/th5090d/miniforge3/envs/babelecho-tts`
  - Whisper CLI：`/home/th5090d/miniforge3/envs/babelecho-tts/bin/whisper`
  - `torch 2.11.0+cu130`
  - CUDA 可用，设备为 `NVIDIA GeForce RTX 5090 D v2`
  - 已安装 `openai-whisper`；暂未安装 `faster-whisper` / `whisperx`
- 已用公开英文短样本 `jfk.flac` 做本地 smoke：
  - `tiny.en` 模型可自动下载到 `/home/th5090d/.cache/whisper/tiny.en.pt`
  - `--device cuda --fp16 True` 可运行
  - 输出 JSON 包含 2 个英文 ASR segment，内容与样本语音一致
- 已新增真实 ASR wrapper：
  - `tools/openai_whisper_asr_wrapper.py`
  - 输入：`--audio-file`
  - 输出：`--output-json`
  - 可选：`--model`、`--language`、`--device`、`--task`、`--fp16`
  - wrapper 输出 BabelEcho canonical `asr/raw.json`，不让后续流程依赖 Whisper 私有结构。
- 已新增 `asr.provider=local_cli`：
  - core pipeline 只调用本地命令并校验 `asr/raw.json`
  - 普通本机测试不导入、不安装 Whisper
  - fixture provider 保持兼容
- 已新增/扩展测试：
  - `tests/test_asr.py::test_local_cli_asr_invokes_wrapper_and_writes_canonical_raw_json`
  - `tests/test_audio_pipeline.py::test_audio_convert_asr_stage_supports_local_cli_provider`
- 本机验证通过：
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_asr.py::test_local_cli_asr_invokes_wrapper_and_writes_canonical_raw_json tests/test_audio_pipeline.py::test_audio_convert_asr_stage_supports_local_cli_provider -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_asr.py tests/test_audio_pipeline.py -q`
- 5090D 已同步 `1741179 feat: add local cli asr wrapper` 后完成真实 `babelecho audio convert` smoke：
  - run-id：`audio-asr-jfk-localcli-20260619`
  - audio：`workspace/sources/asr-smoke-jfk.flac`
  - config：`workspace/config/local-audio-asr-smoke.yaml`，ignored runtime config
  - `--to-stage asr` 成功写入 `asr/raw.json`
  - `provider=openai_whisper`
  - `model=tiny.en`
  - `language=en`
  - `segment_count=2`
  - transcript：`And so my fellow Americans... ask what you can do for your country.`
  - 从 `--from-stage diarize --to-stage normalize` 继续成功，`quality.recommendation=safe_to_adapt`
  - 当前 `diarization.provider=none`，所以 `quality.warnings=["diarization_disabled"]`
- 注意：这一步证明真实 OpenAI Whisper ASR runtime、`local_cli` 接口和 audio-first `asr -> normalize` 桥接可用；尚未接真实 diarization 或声纹。

## 后续

- 下一步用更接近播客的英文短样本验证 `base.en` 或 `small.en`，再决定是否进入 faster-whisper；不急着跑 TTS。
- 真实 ASR 模型横评和默认模型选择。
- 真实 diarization 模型横评和默认模型选择。
- 同一节目跨 episode speaker profile 复用。
- 人工 speaker 改名工具。
- 长音频 chunking。
- URL 音频下载 adapter。
- ASR 结果人工校对入口。
