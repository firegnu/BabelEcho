# Resume Prompt

这个文件用于新 session 快速接回 BabelEcho 当前上下文。新 session 只需要先读本文件，再按其中引用的文档继续。

## 给新 session 的第一条指令

```text
你现在在 BabelEcho 项目中工作。请先阅读 resume-prompt.md、HANDOFF.md、docs/roadmap.md、docs/plans/README.md、docs/plans/01-backend-mvp0/01-local-llm-adapt.md 和 docs/plans/01-backend-mvp0/03-local-tts.md。01.01 DeepSeek LLM Adapt 基线接入已经完成，01.03 本地中文 TTS 接入也已在 5090D 上完成验证；MVP-0 acceptance 已完成，MVP-0.5 的 `babelecho run`、`babelecho check`、手动 transcript 文件入口、`run.json` 状态记录、`babelecho script` 脚本预览和稳定 `workspace/published/feed.xml` 已完成。

重要约束：
- 当前 MVP-0 是 transcript-first 工程链路；核心路径和 acceptance 已正式收口。
- MVP-0.5 已开始：`babelecho run` 可以串起 `ingest -> normalize -> adapt -> synthesize -> assemble -> publish`，并支持 `--from-stage` 从指定阶段继续执行。
- `babelecho run --transcript-file` 可以直接导入本地 transcript 文件；每次 run 会写 `workspace/runs/<run-id>/run.json` 记录输入、阶段状态、失败阶段、错误和输出路径。
- `babelecho check` 可以检查中文脚本、TTS wav segment 和最终 MP3；`run` 已在关键阶段后自动调用这些检查。
- `babelecho script` 可以在 TTS 前预览 `script/zh.json`，并提示编辑后从 `synthesize` 继续；`publish` 会把 feed 和 episode artifacts 同步到稳定目录 `workspace/published/`。
- 5090D 上 fixture 全链路已经跑通：ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish。
- 当前已有 DeepSeek API 生成中文口播稿的真实 adapt 基线，也已有 5090D 本地 CosyVoice2 生成真实 wav/MP3 的真实 TTS 基线，但还没有 voice clone、ASR 或真实播客来源接入。
- 自制长样本和 NASA 真实 podcast transcript 都已经生成可听中文 MP3；下一步不要再做泛泛听感实验，应进入 MVP-0.5 自用流程。
- MVP-0 收口已完成：speaker label 解析/清洗、NASA 样本 `normalize -> adapt -> synthesize -> assemble -> publish` 回归、docs 标记完成。
- `docs/roadmap.md` 已记录从 MVP-0 Acceptance 到 MVP-0.5 Self-use、MVP-1 Real Podcasts、MVP-2 Automation 的产品路线。
- 当前阶段采用临时混合验证：LLM adaptation 使用 DeepSeek API，TTS 仍在 5090D 本地运行；最终方向仍是 local-first。
- Python 环境必须使用项目内 .conda/babelecho-dev，不要使用 base env。
- 真实 runtime config、workspace/runs、生成音频、模型缓存、本地配置和 API key 不要提交。
```

## 当前执行位置

当前已完成：

```text
docs/plans/01-backend-mvp0/01-local-llm-adapt.md
docs/plans/01-backend-mvp0/03-local-tts.md
MVP-0 Acceptance closeout
MVP-0.5 babelecho run command
MVP-0.5 babelecho check command
MVP-0.5 manual transcript input and run.json status
MVP-0.5 script preview and stable published feed
```

进度：

- 01.01 已从“本地 LLM vLLM 接入”改为“DeepSeek LLM Adapt 基线接入”。
- 5090D 上已确认：
  - `git status --short --branch` 输出 `## main...origin/main`
  - `git --no-pager log --oneline -3` 输出：
    - `815c296 docs: mark mvp0 acceptance complete`
    - `9444363 fix: parse transcript speaker labels`
    - `b356114 docs: refresh resume prompt for roadmap`
  - `curl -sS http://127.0.0.1:8000/v1/models` 返回 `{"detail":"Not Found"}`，说明 8000 端口不是当前需要的 OpenAI-compatible LLM endpoint。
- 已决策：不继续优先部署本地 LLM；先使用 DeepSeek API 做 LLM adaptation，5090D 后续专注本地 TTS。
- 01.01 已在 5090D 上完成验收。
- 01.03 已在 5090D 上完成本地 TTS 验收。
- 真实 NASA transcript 样本已在 5090D 上跑通 `normalize -> adapt -> synthesize -> assemble -> publish`。
- 产品路线已整理到 `docs/roadmap.md`，下一步应进入 MVP-0.5 Self-use，不要跳到 MVP-1 或 Later。

MacBook 已实现：

- `src/babelecho/llm.py` 增加 `openai_compatible` provider。
- 支持 `api_key_file`、`api_key_env`、Authorization header、可选 `extra_body`。
- `tests/test_llm.py` 覆盖 DeepSeek provider 行为。
- `src/babelecho/transcript.py` 解析 speaker label，把 `Host:`、`Nick Hague:`、`Host (Dane Turner):` 等标签写入 `segment["speaker"]`，并从 `segment["text"]` 中移除。
- `tests/test_transcript.py` 覆盖段首 label、段内多轮 speaker turn 和普通冒号不误判。
- `src/babelecho/cli.py` 增加 `babelecho run`，支持完整 pipeline 编排和 `--from-stage` 续跑。
- `src/babelecho/cli.py` 支持 `babelecho run --transcript-file ... --title ...`，自用时可跳过 source YAML。
- `src/babelecho/ingest.py` 支持 `source.type=transcript_file`。
- `src/babelecho/status.py` 写入 `workspace/runs/<run-id>/run.json`，记录 run 输入、每个 stage 状态、失败阶段、错误和输出路径。
- `src/babelecho/checks.py` 增加基础质量检查，`babelecho check` 可检查 script、segments、output。
- `src/babelecho/script.py` 增加 `babelecho script`，输出 `script/zh.json` 路径、段落编号、文本和 `--from-stage synthesize` 续跑提示。
- `src/babelecho/publish.py` 同步 run-local publish artifacts 到稳定目录 `workspace/published/`。
- `babelecho run` 在 `adapt`、`synthesize`、`assemble` 后自动检查关键产物。
- `babelecho run` 输出包含 `stable feed: workspace/published/feed.xml`。
- `tests/test_end_to_end_fixture.py` 覆盖 `run` 的 fixture 全链路和从 `synthesize` 恢复执行。
- `tests/test_end_to_end_fixture.py` 覆盖 `--transcript-file` 自用入口和 ingest 失败时 `run.json` 的失败状态。
- `tests/test_end_to_end_fixture.py` 覆盖 `babelecho script` 输出和 stable publish feed。
- `tests/test_publish.py` 覆盖 run-local 与 stable publish artifacts 同时生成。
- `tests/test_checks.py` 覆盖空中文稿、超长段落、缺失 wav、缺失 MP3 和 ffprobe 元数据。
- `workspace/config/local.example.yaml` 已改成 DeepSeek LLM + 本地 TTS 示例。
- `workspace/config/deepseek.env.example` 已添加，真实 `workspace/config/deepseek.env` 被 ignore。
- 本机全量测试：`34 passed`。

5090D 已完成 DeepSeek API 和 `adapt` 验证，也完成 CosyVoice2 本地 TTS wrapper 验证。自制长样本和 NASA 真实 podcast transcript 都已生成可听 MP3。MVP-0 acceptance 已完成：NASA 样本重新生成 9 段 normalized/script/manifest，中文脚本无朗读式 speaker label，`publish/feed.xml` 和 episode artifacts 已验证。下一步进入 MVP-0.5 Self-use。不要同时接 ASR、voice clone、后台服务、App 或真实来源发现。

MVP-0.5 `babelecho run` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `run-command-smoke` 使用 fixture config 跑通 `babelecho run`。
- 生成 `transcript/normalized.json`、`script/zh.json`、`segments/manifest.json`、`output/audio.mp3`、`publish/feed.xml` 和 episode MP3。
- script/manifest 均为 1 段。

MVP-0.5 `babelecho check` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `check-command-smoke` 使用 fixture config 跑通 `babelecho run` 自动检查。
- 独立 `babelecho check` 输出 `script_segments=1`、`audio_segments=1`、`output_sample_rate=16000`、`output_channels=1`、`output_duration_seconds=0.504`。

MVP-0.5 `--transcript-file` 和 `run.json` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `manual-input-status-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Manual Input Smoke"` 跑通 fixture pipeline。
- `run.json` 输出 `status=succeeded`、`from_stage=ingest`、`input_transcript_file=tests/fixtures/sample.vtt`、6 个 stage 全部 `succeeded`、`audio=output/audio.mp3`、`feed=publish/feed.xml`。

MVP-0.5 `babelecho script` 和稳定 `workspace/published/feed.xml` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `preview-stable-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Preview Stable Smoke"` 跑通 fixture pipeline。
- stdout 包含 `stable feed: workspace/published/feed.xml`。
- `babelecho script --workspace workspace --run-id preview-stable-smoke` 输出 `script/edit` 路径、`--from-stage synthesize` 提示和中文稿。
- `workspace/published/feed.xml` 和 `workspace/published/episodes/preview-stable-smoke/audio.mp3` 存在且非空；`run.json` 输出 `stable_feed=published/feed.xml`。

## 必读文件

按顺序读：

1. `HANDOFF.md`
2. `docs/roadmap.md`
3. `docs/plans/README.md`
4. `docs/plans/01-backend-mvp0/01-local-llm-adapt.md`
5. `docs/plans/01-backend-mvp0/03-local-tts.md`
6. `src/babelecho/transcript.py`
7. `tests/test_transcript.py`
8. `src/babelecho/llm.py`
9. `tests/test_llm.py`
10. `tools/cosyvoice_tts_wrapper.py`
11. `workspace/config/local.example.yaml`

## 当前项目事实

- 仓库：`/Users/firegnu/Developer/personal_projs/BabelEcho`，远端 5090D 路径是 `/home/th5090d/Develop/personal_project/BabelEcho`。
- 当前协作方式：本机改代码并 push，必要时通过 `ssh my-5090d-host` 在 5090D 上远程执行验证命令；不在 5090D 上安装或运行 Codex agent。
- MVP-0 acceptance 收口基线提交是 `815c296 docs: mark mvp0 acceptance complete`；当前 `origin/main` 可能包含后续 handoff 文档刷新提交。新 session 以 `git log --oneline -3` 为准；如果需要在 5090D 上跑验证，先在远端 `git pull`。
- 已有 CLI 阶段：
  - `run`
  - `check`
  - `ingest`
  - `normalize`
  - `adapt`
  - `synthesize`
  - `assemble`
  - `publish`
- `adapt(fixture)` 只是生成 `中文口播：<英文原文>`；DeepSeek `openai_compatible` adapt 已在 5090D 上跑通真实中文口播稿。
- `synthesize(fixture)` 仍可生成静音 WAV；真实 TTS 路径通过 `tts.provider: local_cli` 调用 CosyVoice wrapper。
- `assemble` 真实调用 `ffmpeg`，此前相对路径 bug 已修复。
- `publish` 真实生成 `feed.xml` 和 episode 静态目录。
- `openai_compatible` LLM provider 已实现，并已在 5090D 上用 DeepSeek API 跑通 `adapt`。
- 5090D 上 `workspace/config/deepseek.env` 已由用户填写，且被 `.gitignore` 忽略。
- 5090D 上 `babelecho adapt --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-deepseek.yaml` 已成功运行。
- DeepSeek 生成的 `workspace/runs/fixture-smoke/script/zh.json` 样例输出为自然中文：`欢迎收听本期节目。`
- 5090D 上本地 TTS 专用环境是 `/home/th5090d/miniforge3/envs/babelecho-tts`。
- CosyVoice 代码目录是 `/home/th5090d/Develop/ai_tools/CosyVoice`。
- CosyVoice2 模型目录是 `/home/th5090d/Develop/ai_tools/CosyVoice/pretrained_models/CosyVoice2-0.5B`。
- 远端 runtime launcher 是 `/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper`。
- `workspace/config/local-cosyvoice.yaml` 是 ignored runtime config，TTS command 指向上述 launcher。
- `babelecho synthesize --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-cosyvoice.yaml` 已成功生成真实 wav。
- `babelecho assemble --workspace workspace --run-id fixture-smoke` 已成功把真实 TTS wav 拼成 MP3。
- `nasa-crew9-real-smoke` 已在 5090D 上完成 acceptance 回归：
  - `normalize` 输出 9 段，speaker label 写入 `speaker`，`segment["text"]` 无 `Host:` / `Nick Hague:` 标签残留。
  - `adapt` 输出 9 段，speaker 继续保留，中文脚本无 `主持人：` / `尼克·黑格：` 朗读式标签残留。
  - `synthesize -> assemble` 重新生成真实 MP3，`ffprobe` 为 `mp3`、`24000 Hz`、mono、约 `361.1s`。
  - `publish` 生成 `publish/feed.xml`、episode MP3、`transcript.en.json`、`transcript.zh.json`、`metadata.json`。

## 下一个目标

MVP-0 acceptance 已完成，MVP-0.5 第一段 `babelecho run` 和基础 `babelecho check` 已完成：

```text
真实英文 transcript -> normalized.json -> DeepSeek 中文口播稿 -> 5090D CosyVoice2 -> wav segments -> MP3 -> publish/feed.xml
```

下一步继续 MVP-0.5 Self-use：

1. 增加专有名词和发音 override 的简单配置。

不要进入：

- voice clone
- 真实播客来源
- ASR
- 后台服务
- macOS App
- 本地 LLM serving

## 成功标准

MVP-0 acceptance 已满足：

- 使用 NASA 真实 transcript 样例，而不是只有一句 `欢迎收听本期节目。`
- 真实 transcript 的 `Host:` / 人名冒号 speaker label 已解析或清洗到 `speaker` 字段。
- `adapt` 输出继续保留 speaker。
- `workspace/runs/nasa-crew9-real-smoke/segments/manifest.json` 指向真实 TTS 生成的 wav。
- `assemble` 生成可播放 MP3。
- `publish` 生成 RSS feed 和 episode 静态 artifacts。
- 不引入 voice clone，不要求原主播音色。

仍然保留到后续阶段：

- 真实两人或多人播客不能长期使用单一中文声音；后续必须做 `speaker -> voice` 映射，至少支持主持人和嘉宾不同固定音色。
- 自用版本还缺专有名词/发音 override；更复杂的多音色和真实来源仍留到后续阶段。

## 如果发生分支情况

- 如果 MVP-0.5 一条命令流程设计不清：先写一个小计划，不直接堆 CLI 参数。
- 如果 TTS 环境或模型安装失败：先定位 TTS serving/CLI，不改 LLM adapt。
- 如果 TTS wrapper 输出格式不兼容：只修 TTS wrapper 或 `src/babelecho/tts.py` 的 CLI 适配，补测试。
- 如果语音质量差：只调 TTS 模型、voice、语速和切分策略，不接真实来源。

## 收尾规则

如果新 session 修改了代码或文档：

- 跑与改动相关的验证。
- 提交前执行隐私扫描：
  - `gitleaks`
  - `trufflehog`
  - 简单 grep 检查 private key、OpenAI/GitHub/AWS/Bearer/password 模式
- 更新 `HANDOFF.md` 或本文件中已经过期的状态。
- 提交并 push 到 `origin/main`，除非用户明确要求暂不提交。
