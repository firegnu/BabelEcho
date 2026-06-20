# 03.01 Audio-first 本地音频 ASR 与说话人分离计划

状态：in_progress

日期：2026-06-19

父计划：`03-audio-first-asr`

## 目标

建立一条独立的 Route B：用户提供本地音频文件或显式音频 URL 后，系统先做 ASR，再做 speaker diarization / 声纹聚类，生成现有后流程可消费的 `transcript/normalized.json`。

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
local audio file / explicit audio URL
  -> audio ingest
  -> ASR
  -> speaker diarization / voice profile
  -> transcript/normalized.json
  -> existing adapt/TTS/publish
```

关键边界：Route B 可以复用 `adapt -> synthesize -> assemble -> publish` 原子能力，但不能改写 `babelecho episode convert`、`babelecho run`、`source.type=youtube_captions`、`podcast_rss`、`episode_page`、`article_reading` 的现有语义。

## 范围

### In

- 新增独立 CLI：`babelecho audio convert`，输入参数为 `--audio-file` / `--audio-url` 二选一。
- 支持本地音频文件和显式公网音频 URL ingest；URL 入口只属于 Route B，不作为 Route A 的静默 ASR fallback。
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
- 发布 artifact 中 `source.type=audio_file` 或 `source.type=audio_url`、`route=audio_first`、`asr` 摘要可展示给只读前端；URL source 只暴露 `source_host` / `source_path`，不写 query/fragment；不含 embedding 的 speaker profile 统计文件可以同步到 published，真实 voiceprint embedding 不发布。

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

URL 音频入口：

```bash
babelecho audio convert \
  --workspace workspace \
  --run-id audio-url-smoke-20260620 \
  --audio-url "https://example.com/episode.mp3" \
  --local-config workspace/config/local-audio.yaml \
  --to-stage ingest_audio
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
  # 可选，仅用于人工确认后的 audio-first ASR 专名修正。
  replacements:
    - from: "cloud code"
      to: "Claude Code"
    - from: "Daniel White Knack"
      to: "Daniel Whitenack"

diarization:
  provider: local_cli
  command: "/home/th5090d/miniforge3/envs/babelecho-diarization/bin/python tools/pyannote_diarization_wrapper.py"
  model: "pyannote/speaker-diarization-community-1"
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
- URL 输入时 `input_kind=audio_url`，允许写 `source_host` 和 `source_path`，但不写 query/fragment。
- 不写远端本地路径。
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

可选。第一版只写 speaker 聚类统计摘要，不写声纹 embedding：

```json
{
  "schema_version": "1.0",
  "provider": "diarization_stats",
  "source": "diarization",
  "diarization_provider": "pyannote",
  "diarization_model": "pyannote/speaker-diarization-community-1",
  "speaker_count": 2,
  "speakers": [
    {
      "id": "speaker_1",
      "label": "speaker_1",
      "turn_count": 12,
      "total_ms": 320500,
      "first_start_ms": 0,
      "last_end_ms": 601200,
      "avg_turn_ms": 26708.3,
      "sample_count": 0,
      "sample_duration_ms": 0,
      "profile_kind": "diarization_stats",
      "embedding_status": "not_computed",
      "embedding_artifact": null
    }
  ]
}
```

约束：

- 文件会写在 ignored run 目录 `asr/speaker-profiles.json`。
- publish 阶段可以把无 embedding 的统计 profile 同步为 `workspace/published/episodes/<run-id>/speaker-profiles.json`，并在 `artifact.json.artifacts.speaker_profiles` 中给出相对路径。
- 如果以后保存真实 embedding，只能保存 run-local 相对路径；published artifact 只能展示统计摘要和 `embedding_status`，不能发布 embedding 文件。
- audio-first runtime config 已支持 `voice_profile.provider=none/fixture`。`none` 保留统计 profile；`fixture` 只用于测试和契约验证，可合并 `sample_count`、`sample_duration_ms`、`profile_kind`、`embedding_status` 和 run-local 相对 `embedding_artifact`。真实 embedding provider 后移。

示例 fixture config：

```yaml
voice_profile:
  provider: fixture
  fixture_path: tests/fixtures/asr/two-speaker-voice-profile.json
```

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
- `speaker-profiles.json` 写入 run 目录；如果只含统计 profile 且 `embedding_status=not_computed`，publish 可以同步到 published 目录。

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

### 2026-06-19：阶段 7 Diarization local_cli 接入口

- 已新增 `diarization.provider=local_cli`：
  - core pipeline 只调用本地命令并校验 `asr/diarization.json`
  - 普通本机测试不导入、不安装真实 diarization 模型
  - fixture 和 none provider 保持兼容
- `local_cli` wrapper 调用约定：
  - 输入：`--audio-file`
  - 输出：`--output-json`
  - 可选：`--model`、`--min-speakers`、`--max-speakers`
  - 支持 `diarization.extra_args`
- 已新增可选真实 wrapper：
  - `tools/pyannote_diarization_wrapper.py`
  - 默认模型：`pyannote/speaker-diarization-community-1`
  - 默认从 `HF_TOKEN` 环境变量读取 Hugging Face token，避免 token 出现在命令行
  - 也可把 `--model` 指向本地下载好的 pyannote pipeline 目录，供离线运行
  - wrapper 输出 BabelEcho canonical `asr/diarization.json`，speaker 名统一映射为 `speaker_1`、`speaker_2` 等稳定标签
- 5090D 真实 diarization 环境已准备：
  - 为避免污染 TTS 环境，已从 `/home/th5090d/miniforge3/envs/babelecho-tts` 克隆独立环境到 `/home/th5090d/miniforge3/envs/babelecho-diarization`
  - `babelecho-diarization` 已安装 `pyannote.audio 4.0.4`
  - 安装后只在克隆环境中移除了与 NumPy 2.x 不兼容的旧 `onnxruntime-gpu 1.18.0`
  - `babelecho-tts` 保持不动，继续负责 OpenAI Whisper ASR 和 CosyVoice TTS
- 5090D 真实 pyannote smoke 已执行：
  - run-id：`audio-diarization-practicalai-zero-trust-8min-qualitygate-20260619`
  - audio：`workspace/sources/asr-practicalai-zero-trust-8min.wav`，8 分钟，16 kHz mono
  - ASR：OpenAI Whisper `small.en`，`raw_segment_count=123`
  - Diarization：pyannote Community-1，`speaker_count=2`、`turn_count=23`、`avg_turn_ms=20735.7`
  - Normalize：`normalized_segment_count=32`，speakers 为 `speaker_1` / `speaker_2`
  - 旧 Quality：`recommendation=inspect_first`，warning 为 `asr_segment_crosses_speaker_turns`
  - 运行耗时约 `36.5s`，峰值 RSS 约 `3.0GB`
  - 与该集已有官方 speaker VTT 粗略重叠对齐，`speaker_1=Daniel`、`speaker_2=Chris`，覆盖片段 overlap accuracy 约 `99.59%`
- 当前判断：
  - 真实 diarization 分离结果可用
  - `inspect_first` 来自 ASR segment 横跨 speaker turn 的旧保守 warning，不代表 pyannote 未分出人
  - 这一步未进入 DeepSeek/TTS，仍保持 audio-first 独立验证边界
- 已处理 `asr_segment_crosses_speaker_turns` 的质量门禁：
  - `asr_segment_crosses_speaker_turns` 保留为 advisory warning，不再单独触发 `inspect_first`
  - quality metrics 新增 `cross_speaker_segment_count/ratio`、`ambiguous_speaker_segment_count/ratio`、`min_primary_speaker_overlap_ratio`、`avg_primary_speaker_overlap_ratio`
  - 主 speaker overlap 小于 `0.60` 的 crossing 计为 ambiguous
  - ambiguous segment 数量达到 3 个或比例达到 5% 时，写 `ambiguous_speaker_assignments` 并 `inspect_first`
  - Practical AI 8 分钟样本已用新代码在 5090D 实际复跑为 `safe_to_adapt`，metrics 为 9/123 crossing、2/123 ambiguous、`min_primary_speaker_overlap_ratio=0.537`、`avg_primary_speaker_overlap_ratio=0.781`
  - 同一 run 已继续跑通 `audio-first -> DeepSeek -> TTS -> publish`
  - script/manifest 均 32 段，voice roles 为 `female_a/male_a`
  - 最终 MP3 为 `22050 Hz` mono、约 `370.55s`、约 `5.9 MB`
  - MP3 已拷回本机 ignored `workspace/runs/audio-diarization-practicalai-zero-trust-8min-qualitygate-20260619/output/audio.mp3`
  - 用户试听反馈“整体可以接受”
- 已新增/扩展测试：
  - `tests/test_diarization.py::test_local_cli_diarization_invokes_wrapper_and_writes_canonical_json`
  - `tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_supports_local_cli_provider`
  - `tests/test_audio_normalize.py::test_audio_normalize_keeps_low_risk_cross_speaker_segments_safe`
  - `tests/test_audio_normalize.py::test_audio_normalize_marks_ambiguous_cross_speaker_segments_for_inspection`
- ASR 模型横评第一轮：
  - 同一样本使用已有官方 VTT 做粗略 WER 对比。
  - `small.en`：cached normalize 约 `23.1s`，粗略 WER `0.165`，quality=`safe_to_adapt`。
  - `medium.en`：首次下载后 cached normalize 约 `28.7s`，粗略 WER `0.178`，quality=`safe_to_adapt`。
  - 专名表现：`small.en` 多把 `Claude` 写成 `cloud`；`medium.en` 抓到 1 次 `Claude Code`，但也多次写成 `Clod`，并把 `Whitenack` 写成 `Witek`。
  - 当前不把默认 ASR 从 `small.en` 升到 `medium.en`。
- ASR 专名纠错第一版：
  - 已新增 `asr.replacements`，仅在 audio-first `fixture` / `local_cli` ASR 输出归一化后执行。
  - 默认不开启，只支持显式短语 `from -> to`，按配置顺序应用，不做自动词典和宽泛 `cloud` 替换。
  - 命中摘要写入 `asr/raw.json` 的 `metadata.asr_replacements`。
  - 5090D 临时 worktree 已用 Practical AI 8 分钟样本验证：`tests/test_asr.py` 通过，`small.en` ASR 仍输出 123 段；3 条窄规则命中 4 次，修正 `Daniel White Knack`、`cloud code`、`cloud co-worker`，同时保留未确认的普通 `cloud security`。
  - 5090D 最新 `main` 已跑 `audio-diarization-practicalai-replacements-normalize-20260620`：`small.en` + pyannote 到 `normalize` 仍为 `safe_to_adapt`，ASR 123 段、normalized 32 段、3 条规则命中 4 次；继续 `adapt` 后 DeepSeek 生成 32 段中文脚本，script QA 通过，首段脚本保留 `Daniel Whitenack`。
- Speaker profile contract 第一版：
  - `diarize` 阶段会从 canonical diarization turns 生成 `asr/speaker-profiles.json`。
  - 当前 profile 含 turn 数、总时长、首尾时间、`sample_count`、`sample_duration_ms`、`profile_kind`、`embedding_status` 和保留的 run-local `embedding_artifact` 字段；默认 `embedding_status=not_computed`，不做身份识别，不写 voiceprint embedding。
  - 已支持 audio-first-only `voice_profile.provider=none/fixture`。`fixture` 只合并 deterministic 测试元数据，不加载真实模型、不创建 embedding 文件。
  - publish 阶段如果发现该文件，会复制到 episode published 目录，并在 `artifact.json.artifacts.speaker_profiles` 与 `artifact.json.asr.speaker_profiles` 中暴露摘要。
  - 5090D 临时 worktree 已用 Practical AI 8 分钟样本跑到 `diarize`：`speaker_count=2`，speaker ids 为 `speaker_1/speaker_2`，所有 profile `embedding_status=not_computed`，`run.json.outputs.speaker_profiles=asr/speaker-profiles.json`。
  - 5090D 最新 `main` full publish smoke `audio-speaker-profiles-practicalai-publish-20260620` 已通过：ASR 123 段、normalized/script/manifest 均 32 段，quality=`safe_to_adapt`，最终 MP3 为 `22050 Hz` mono、约 `361.48s`；published artifact 中 `speaker-profiles.json` 存在，`artifact.json.artifacts.speaker_profiles="speaker-profiles.json"`，`artifact.json.asr.speaker_profiles.embedding_status="not_computed"`。
- Voice profile local_cli contract 起步：
  - 已支持 audio-first-only `voice_profile.provider=local_cli`，核心只调用本地 wrapper，不直接依赖 pyannote embedding、SpeechBrain、NeMo 等重模型包。
  - wrapper 输入为 run-local audio、`asr/diarization.json`、`asr/speaker-profiles.json`，输出为 ignored run-local `asr/voice-profiles/summary.json` 和可选 `asr/voice-profiles/*.json`。
  - `summary.json` 只把 safe metadata 合并回 `asr/speaker-profiles.json`：`sample_count`、`sample_duration_ms`、`profile_kind`、`embedding_status`、`embedding_artifact`；`embedding_status=computed` 已进入合法状态。
  - `tools/speaker_embedding_wrapper.py` 已从契约 stub 升级为 SpeechBrain ECAPA wrapper：按 speaker 选择最长 diarization windows，运行 `speechbrain/spkrec-ecapa-voxceleb`，写 run-local `asr/voice-profiles/<speaker>.json` 和 `summary.json`。
  - 5090D 独立 `babelecho-voice-profile` model probe 已选中 `speechbrain/spkrec-ecapa-voxceleb`：pyannote embedding 被 gated repo 403 阻断，SpeechBrain ECAPA 在 Practical AI 8 分钟样本上成功产出 192 维 embedding，speaker 内 cosine 均值约 `0.929/0.849`，speaker 间约 `0.457`，首次 probe 总耗时约 `36.9s`，峰值 RSS 约 `2.4 GB`。
  - 5090D 真实 wrapper smoke `audio-voice-profile-speechbrain-smoke-20260620` 已通过：`voice_profile.provider=local_cli` 调用 SpeechBrain wrapper 后，`speaker_1/speaker_2` 均为 `embedding_status=computed`，写入 run-local 192 维 `asr/voice-profiles/speaker_*.json`，并合并摘要到 `asr/speaker-profiles.json`。
  - 同一 run 已继续做 publish-stage privacy smoke：`artifact.json.asr.speaker_profiles` 不包含 `embedding_artifact`，也没有把 `asr/voice-profiles/*.json` 复制到 `workspace/published/`。
  - 这一步仍不是 voice clone，不做原主播声音复刻、不做真实身份识别，也不把 embedding 用于 TTS。
- URL 音频入口：
  - 已新增 `babelecho audio convert --audio-url ...`，CLI 输入现在是 `--audio-file | --audio-url` 二选一。
  - `audio_url` 入口写 `source_type=audio_url`、`provider=remote_url`、`audio/input.<ext>`、`audio/metadata.json`，并只保留 `source_host` / `source_path`，不把 URL query/fragment 写入 artifact。
  - publish 已把 `audio_url` 归为 `route=audio_first`，并在公开 source 中只暴露 safe source 字段。
  - 本机验证：`tests/test_audio_source.py tests/test_audio_pipeline.py tests/test_publish.py tests/test_cli_smoke.py -q` 为 24 passed；全量 `.conda/babelecho-dev/bin/python -m pytest -q` 为 244 passed。
  - 5090D 已 `git pull --ff-only` 到 `fd8d259` 并通过 `tests/test_audio_source.py tests/test_audio_pipeline.py::test_audio_convert_cli_accepts_audio_url -q`：8 passed。
  - 5090D 真实公网 smoke `audio-url-ingest-practicalai-ai-index-20260620` 使用 Practical AI MP3 跑到 `ingest_audio`：`source_type=audio_url`、`provider=remote_url`、`source_host=pscrb.fm`、`duration_seconds=2832.404898`、`sample_rate=44100`、mono、`file_size_bytes=45365394`、warnings 为空。
  - 5090D 受控 normalize 回归 `audio-url-normalize-practicalai-zero-trust-8min-20260620` 使用远端 localhost HTTP 临时服务暴露已有 Practical AI 8 分钟真实 wav，跑通 `--audio-url -> asr -> diarize -> normalize`：query 未泄漏，ASR 123 段，diarization 23 turns，normalized 32 段，quality=`safe_to_adapt`，`cross_speaker_segment_count=9`，`ambiguous_speaker_segment_count=2`，metrics 与同样本本地文件路线一致。
  - 5090D 短 URL full-chain `audio-url-fullchain-bbc-6min-screen-time-20260620` 使用 BBC `6 Minute English - Limiting screen time for children` 直链跑通 `--audio-url -> ASR -> diarize -> normalize -> DeepSeek -> TTS -> publish`：输入约 `508.97s`、ASR 153 段、diarization 4 speakers/51 turns、normalized/script/manifest 均 40 段、quality=`safe_to_adapt`、voice roles `female_a/male_a/female_b/male_b` 均有使用，输出 MP3 为 `22050 Hz` mono、约 `354.8s`、约 `5.7 MB`，已拷回本机 ignored `workspace/runs/audio-url-fullchain-bbc-6min-screen-time-20260620/output/audio.mp3`。
  - 该 BBC 样本暴露真实 audio-first 清理问题：动态广告和片尾推广会进入 ASR/中文稿，首尾 segment 有广告/推广内容；这不是 URL 链路失败，但正式自用前需要广告/舞台/片尾清理或人工裁剪入口。
  - 已新增 audio-first 边界内容自动清理：只处理开头/结尾边界窗口，高置信广告/推广自动删除，低置信只写 warning，不要求人工确认。5090D 重跑同一 BBC run 的 `normalize -> publish` 后，normalized/script/manifest 为 36 段，自动删除 4 个边界内容段，quality=`safe_to_adapt`，更新后 MP3 为 `22050 Hz` mono、约 `339.4s`、约 `5.4 MB`。
  - 已新增 `local_cli` diarization 输入规范化：非 WAV 输入会先转成 run-local `audio/diarization-input.wav`（mono、16k、PCM）再传给 wrapper，原始音频保留给 ASR/source artifact。根因验证样本为 Podnews `The risk takers in podcasting`：原始 MP3 含封面图视频流、双声道和非零 start time，pyannote 直接读取失败为 `requested chunk ... 439895 samples instead of ... 441000 samples`；同文件转成标准 WAV 后 wrapper 成功输出 2 speakers / 8 segments。5090D 回归 `audio-url-regression-podnews-risk-takers-20260620` 已从 `diarize -> publish` 跑通：quality=`safe_to_adapt`，normalized/script/manifest 均 10 段，voice roles 为 `female_a/male_a`，自动删除 3 个边界段，1 个 possible boundary warning 保留，最终 MP3 为 `22050 Hz` mono、约 `147.10s`、约 `2.35 MB`，ffmpeg 解码通过。
  - 已校准 audio-first diarization 质量门：ASR/diarization overlap 先按 speaker 聚合，避免同一 speaker 被拆成多个 turns 后误算为 cross/ambiguous；`ambiguous_speaker_assignments` 现在要求 ambiguous 数量和比例同时达到阈值，少量低占比 ambiguous 只保留 advisory；`missing_diarization_overlap` 现在写 count/ratio/duration/boundary metrics，只有正文缺失、缺失过多或边界缺失过长才 `inspect_first`，尾部短 farewell 缺口只保留 advisory。5090D 回归：BBC Advertisers 从 `inspect_first` 变为 `safe_to_adapt`，35 段、3 speakers，自动删除 8 个边界段，并已跑通 `adapt -> publish`，最终 MP3 为 `22050 Hz` mono、约 `343.01s`、约 `5.49 MB`，ffmpeg 解码通过；BBC Hantavirus 从 `inspect_first` 变为 `safe_to_adapt`，49 段、3 speakers、`missing_diarization_overlap_segment_count=1`、尾部缺失 1000ms，并已跑通 `normalize -> publish`，最终 MP3 为 `22050 Hz` mono、约 `365.27s`、约 `5.84 MB`，ffmpeg 解码通过；BBC Screen Time 和 Podnews 仍为 `safe_to_adapt`。
  - 已补 BBC newsletter/podcast promo 片尾清理回归：`audio-url-regression-bbc-6min-poetry-20260620` 使用 BBC `6 Minute English - The power of poetry`，`normalize` 结果保持 `inspect_first`，32 段、4 speakers，warnings 包含 `ambiguous_speaker_assignments`，且开头 ASR/动态内容噪声明显，未强行进入 DeepSeek/TTS；`audio-url-regression-bbc-news-us-iran-20260620` 使用 BBC `Learning English from the News - US-Iran peace deal`，初始 `safe_to_adapt` 但残留 newsletter/podcast promo 尾巴。已扩展高置信片尾规则，重跑后 quality=`safe_to_adapt`，warnings 只剩 `asr_segment_crosses_speaker_turns` 和 `dropped_boundary_content_segments`，normalized/script/manifest 均 50 段，自动删除 6 个边界内容段，`possible_boundary_content_segment_count=0`，voice roles 为 `female_a/male_a`，最终 MP3 为 `22050 Hz` mono、约 `396.51s`、约 `6.05 MB`，ffmpeg 解码通过，产物已拷回本机 ignored `workspace/runs/audio-url-regression-bbc-news-us-iran-20260620/output/audio.mp3`。
  - 已补非 BBC direct-audio 短样本回归：`audio-url-regression-npr-newsnow-20260620` 使用 NPR News Now `NPR News: 06-20-2026 4AM EDT` RSS enclosure，输入 MP3 约 `280.06s`、`44100 Hz` stereo，URL artifact 只保留 `source_host=prfx.byspotify.com` 和 `source_path`，不写 query/fragment。5090D 跑通 `--audio-url -> ASR -> diarize -> normalize -> DeepSeek -> TTS -> publish`：quality=`safe_to_adapt`，24 段、4 speakers，warnings 只有 `asr_segment_crosses_speaker_turns`，`dropped_boundary_content_segment_count=0`，`possible_boundary_content_segment_count=0`，manifest 使用 `female_a/female_b/male_a/male_b` 四个 voice role；最终 MP3 为 `22050 Hz` mono、约 `283.95s`、约 `4.54 MB`，ffmpeg 解码通过，published `transcript.zh.json` 已带中文 MP3 时间轴字段，产物已拷回本机 ignored `workspace/runs/audio-url-regression-npr-newsnow-20260620/output/audio.mp3`。
- 本机验证通过：
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_normalize.py::test_audio_normalize_aggregates_same_speaker_split_turns tests/test_audio_normalize.py::test_audio_normalize_keeps_sparse_ambiguous_segments_safe -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_normalize.py::test_audio_normalize_drops_trailing_newsletter_promo -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_normalize.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_normalize.py tests/test_audio_pipeline.py tests/test_publish.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py::test_local_cli_diarization_canonicalizes_compressed_audio_before_wrapper -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_supports_local_cli_provider tests/test_audio_pipeline.py::test_audio_convert_asr_stage_supports_local_cli_provider -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_applies_local_cli_voice_profile -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py::test_publish_episode_adds_audio_first_asr_summary -q`
  - `.conda/babelecho-dev/bin/python tools/speaker_embedding_wrapper.py --help`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_asr.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_asr.py tests/test_audio_pipeline.py tests/test_audio_normalize.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py tests/test_audio_pipeline.py tests/test_publish.py -q`
  - `.conda/babelecho-dev/bin/python tools/pyannote_diarization_wrapper.py --help`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py::test_local_cli_diarization_invokes_wrapper_and_writes_canonical_json tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_supports_local_cli_provider -q`
  - `.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py tests/test_audio_pipeline.py tests/test_audio_normalize.py -q`
  - `.conda/babelecho-dev/bin/python -m pytest -q`

## 后续

- 用真实 5090D 样本验证 `asr.replacements` 对 `Claude/cloud/Clod`、`Whitenack/Witek/White Knack` 等高频 AI podcast 专名的改善幅度。
- 或继续横评 `large-v3` / faster-whisper，但必须继续只在 audio-first 路线验证，不作为 Route A fallback。
- 真实 ASR 模型横评和默认模型选择。
- 真实 diarization 模型横评和默认模型选择。
- 继续补更多 audio-url 短样本回归，重点观察 missing diarization overlap 是否只发生在首尾短 farewell/广告残留，以及 high cross 是否仍由高 primary-overlap 的 speaker-turn 细切分导致。
- 同一节目跨 episode speaker profile 复用。
- 人工 speaker 改名工具。
- 长音频 chunking。
- Private speaker alias 人工确认/审核 contract、confirmed alias 到稳定中文 voice role 的私有映射 contract、显式 opt-in 应用到单次 run 的 speaker_voices 已完成；后续补 5090D 应用 smoke。
- 扩充保守 audio-first 广告/片尾清理规则，或增加可选裁剪 override。
- ASR 结果人工校对入口。
