# Resume Prompt

这个文件是 BabelEcho 新 session 的唯一必读入口。用户下次只需要让 agent 读取本文件；agent 读完后再根据具体任务，自行打开本文件引用的其他文档。

## 下次新 session 最短指令

```text
你现在在 BabelEcho 项目中工作。请先只阅读 resume-prompt.md。
读完后执行 git status --short --branch 和 git log --oneline -3，
然后用中文简要汇报：当前状态、当前 TTS 规则、下一步建议、是否有未提交变更。
不要一上来改代码。
```

## 给新 session 的第一条指令

```text
你现在在 BabelEcho 项目中工作。请先只阅读 resume-prompt.md；本文件是唯一必读入口。读完后先执行 git status --short --branch 和 git log --oneline -3，再用中文简要汇报当前状态、当前 TTS 规则、下一步建议和是否有未提交变更。不要一上来改代码。

01.01 DeepSeek LLM Adapt 基线接入已经完成，01.03 本地中文 TTS 接入也已在 5090D 上完成验证；MVP-0 acceptance 和 MVP-0.5 Self-use 均已完成。

重要约束：
- 当前 MVP-0 是 transcript-first 工程链路；核心路径和 acceptance 已正式收口。
- MVP-0.5 已完成：`babelecho run` 可以串起 `ingest -> normalize -> adapt -> synthesize -> assemble -> publish`，并支持 `--to-stage` 停在指定阶段、`--from-stage` 从指定阶段继续执行。
- `babelecho run --transcript-file` 可以直接导入本地 transcript 文件；每次 run 会写 `workspace/runs/<run-id>/run.json` 记录输入、阶段状态、失败阶段、错误和输出路径。
- `babelecho check` 可以检查中文脚本、TTS wav segment 和最终 MP3；`run` 已在关键阶段后自动调用这些检查。
- `babelecho script` 可以在 TTS 前预览 `script/zh.json`，并提示编辑后从 `synthesize` 继续；`publish` 会把 feed 和 episode artifacts 同步到稳定目录 `workspace/published/`。
- `overrides.path` 和 `babelecho overrides` 可以在 TTS 前对 `script/zh.json` 做本地精确替换；示例词表是 tracked `workspace/config/overrides.example.yaml`，真实词表继续放 ignored `workspace/config/overrides.yaml`。
- 5090D 上 fixture 全链路已经跑通：ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish。
- 当前已有 DeepSeek API 生成中文口播稿的真实 adapt 基线，也已有 5090D 本地 TTS 生成真实 wav/MP3 的真实基线，但还没有 voice clone、ASR 或完整真实播客来源接入。
- 自制长样本、NASA 真实 podcast transcript 和 MVP-0.5 自用回归都已经生成可听中文 MP3；下一步不要再做泛泛听感实验，应进入 MVP-1 Real Podcasts。
- MVP-1 当前 TTS 运行默认已改为单模型：只部署 `CosyVoice-300M-SFT`，使用 `tts.voice=sft_builtin_4role`；不做原主播 voice clone。
- 音色校准第一轮已生成三条本地 TTS 样本，未调用 DeepSeek：`workspace/runs/voice-calibration-20260617/a-current-zero-shot-female.mp3`、`b-neutral-instruct2-female.mp3`、`c-cross-lingual-reference.mp3`。这些产物在 ignored `workspace/runs/` 下，不提交。
- 用户曾反馈 D 最满意；但后续单男、单女、多人验证后，MVP-1 运行默认已改为 `CosyVoice-300M-SFT` 的 `sft_builtin_4role`，历史 D 样本只保留为校准记录。
- 不再继续围绕 CosyVoice 内置两个 wav 反复微调。后续如需新固定音色，准备本地授权的男声/中性参考 wav，再用同一条 `cross_lingual` 路线替换 `prompt_wav` 做对比；该项已按 voice clone 类似方式放入 deferred voice work，但它不是原主播 voice clone。
- MVP-1 真实来源第一版已完成：新增 `source.type=podcast_rss` 和 `babelecho run --podcast-feed ...`，只支持 RSS item 内的 `podcast:transcript`，找不到 transcript 时明确失败，不做 ASR。公开 RSS smoke 使用 `https://feeds.transistor.fm/podcasting-advice` 跑到 `adapt`，fixture script 共 74 段，未调用 DeepSeek。
- MVP-1 公开 RSS 端到端 Real Run 已完成：`mvp1-real-rss-monetize-20260617` 使用 `https://feeds.transistor.fm/podcasts-for-profit-with-morgan-franklin` 的 `#030: When Should You Monetize Your Podcast?`，经 RSS transcript -> DeepSeek -> 5090D TTS -> MP3 -> feed 全链路成功；script/manifest 75 段，MP3 约 `840.8s`，产物在 ignored `workspace/runs/mvp1-real-rss-monetize-20260617/`。
- MVP-1 PodcastIndex episode JSON 输入已完成第一步：新增 `source.type=podcast_index_episode`，`babelecho run --source-config ...` 可从已获取的 PodcastIndex episode JSON 中优先读取 `transcripts[].url`，并回退到 `transcriptUrl`。
- MVP-1 PodcastIndex API 输入已完成第一版：新增 `source.type=podcast_index_api`，支持 PodcastIndex API auth headers、`episodes/byid`、`episodes/byfeedid`、`episodes/byfeedurl`、`episodes/byitunesid`，并复用现有 transcript ingest；API key/secret 只从环境变量或 ignored `workspace/config/podcastindex.env` 读取。已新增 `babelecho podcast-index search` / `episodes` CLI，可搜索 feed、列 episode，并把选中 episode 写成可运行 source config；尚未做多 episode 批处理。
- MVP-1 Episode Page Transcript Source 已完成：新增 `source.type=episode_page`，可从播客官网 episode 页面发现 transcript 链接或 transcript 正文，并保存干净 `transcript/raw.txt`；99% Invisible 真实 smoke 已通过到 `ingest`。这不包含 YouTube、Spotify、Apple Podcasts 页面，也不做 JS 渲染、ASR 或音频下载。
- MVP-1 Discovery Adapters 第一版已完成：新增 `babelecho itunes search`，可用 iTunes Search API 找 podcast RSS `feedUrl` 并输出 `source.type=podcast_rss`；新增 `babelecho rss episodes`，可列 RSS feed 内 episodes、标记 transcript yes/no，并把选中 episode 写成带 `episode_url` 的 `source.type=podcast_rss`；新增 `source.type=youtube_captions`，用本机 `yt-dlp --skip-download` 拉公开视频字幕/自动字幕作为 transcript source，不下载音频，不做 ASR。
- MVP-1 TTS 执行效率优化已完成：`local_cli` synthesis 现在写 `segments/tts-batch.json` 并一次启动 `tts-wrapper --batch-file ...`，wrapper 只加载一次 CosyVoice 后循环生成所有 segment wav；旧的 `--text-file --output` 单段 wrapper 调用仍兼容。5090D `batch-wrapper-smoke-20260617` 两段真实 CosyVoice smoke 已通过。
- MVP-1 固定音色规则已选定并实现：运行默认只用 `CosyVoice-300M-SFT` 的 `tts.voice=sft_builtin_4role`。未启用 speaker voice 推断时，0/1 个 distinct speaker 且没有显式性别标签使用 `female_a`；单个 speaker 标签包含 `male` / `男` 时使用 `male_a`，包含 `female` / `女` 时使用 `female_a`；2 个及以上 distinct speaker 按首次出现顺序映射到 `female_a / male_a / female_b / male_b`。
- MVP-1 speaker voice 推断已完成第一版：可在 local config 启用 `speaker_voices.mode: infer_once`，`run`/`synthesize` 会在 TTS 前每集最多调用一次 LLM，根据 speaker 名称和少量上下文推断 `male/female/unknown`，写入 ignored run-local `script/speaker-voices.json`，再由代码稳定映射到 `female_a/male_a/female_b/male_b`。`confidence` 只用于人工复核提示，不阻塞；`unknown` 也会自动获得具体 voice role。若推断失败或文件无效，回退到旧的首次出现规则。
- `sft_builtin_4role` 使用 `CosyVoice-300M-SFT` 的 `中文女 / 中文男 / 英文女 / 英文男` 四个内置 speaker id；同名 speaker 复用同一角色，超过 4 个 speaker 循环复用。不做原主播 voice clone，不依赖额外参考 wav，不要求部署 `CosyVoice2-0.5B`。
- 本机测试计数以当前 `pytest -q` 为准；5090D 临时 wrapper smoke 已验证四角色真实 SFT wav 输出均为 `22050 Hz` mono。计划记录见 `docs/plans/02-real-podcasts/03-sft-builtin-4role-voice-profile.md`。
- MVP-0 收口已完成：speaker label 解析/清洗、NASA 样本 `normalize -> adapt -> synthesize -> assemble -> publish` 回归、docs 标记完成。
- `docs/roadmap.md` 已记录从 MVP-0 Acceptance 到 MVP-0.5 Self-use、MVP-1 Real Podcasts、MVP-2 Automation 的产品路线；当前下一阶段是 MVP-1。
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
MVP-0.5 local terminology/pronunciation overrides
MVP-0.5 self-use acceptance
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
- 产品路线已整理到 `docs/roadmap.md`，MVP-0.5 已完成，下一步应进入 MVP-1 Real Podcasts。

MacBook 已实现：

- `src/babelecho/llm.py` 增加 `openai_compatible` provider。
- 支持 `api_key_file`、`api_key_env`、Authorization header、可选 `extra_body`。
- `tests/test_llm.py` 覆盖 DeepSeek provider 行为。
- `src/babelecho/transcript.py` 解析 speaker label，把 `Host:`、`Nick Hague:`、`Host (Dane Turner):` 等标签写入 `segment["speaker"]`，并从 `segment["text"]` 中移除。
- `tests/test_transcript.py` 覆盖段首 label、段内多轮 speaker turn 和普通冒号不误判。
- `src/babelecho/cli.py` 增加 `babelecho run`，支持完整 pipeline 编排和 `--from-stage` 续跑。
- `src/babelecho/cli.py` 支持 `babelecho run --to-stage adapt`，可在 TTS 前停下预览中文脚本。
- `src/babelecho/cli.py` 支持 `babelecho run --transcript-file ... --title ...`，自用时可跳过 source YAML。
- `src/babelecho/ingest.py` 支持 `source.type=transcript_file`。
- `src/babelecho/status.py` 写入 `workspace/runs/<run-id>/run.json`，记录 run 输入、`from_stage`、`to_stage`、每个 stage 状态、失败阶段、错误和输出路径。
- `src/babelecho/checks.py` 增加基础质量检查，`babelecho check` 可检查 script、segments、output。
- `src/babelecho/script.py` 增加 `babelecho script`，输出 `script/zh.json` 路径、段落编号、文本和 `--from-stage synthesize` 续跑提示。
- `src/babelecho/publish.py` 同步 run-local publish artifacts 到稳定目录 `workspace/published/`。
- `src/babelecho/overrides.py` 增加本地精确替换逻辑，读取 `overrides.path` 指向的 YAML 词表并改写 `script/zh.json`。
- `src/babelecho/cli.py` 增加 `babelecho overrides`，`babelecho run` 在 `synthesize` 前自动应用 configured overrides。
- `babelecho run` 在 `adapt`、`synthesize`、`assemble` 后自动检查关键产物。
- `babelecho run` 输出包含 `stable feed: workspace/published/feed.xml`。
- `tests/test_end_to_end_fixture.py` 覆盖 `run` 的 fixture 全链路和从 `synthesize` 恢复执行。
- `tests/test_end_to_end_fixture.py` 覆盖 `run --to-stage adapt` 停在中文脚本阶段，不生成音频。
- `tests/test_end_to_end_fixture.py` 覆盖 `--transcript-file` 自用入口和 ingest 失败时 `run.json` 的失败状态。
- `tests/test_end_to_end_fixture.py` 覆盖 `babelecho script` 输出和 stable publish feed。
- `tests/test_publish.py` 覆盖 run-local 与 stable publish artifacts 同时生成。
- `tests/test_checks.py` 覆盖空中文稿、超长段落、缺失 wav、缺失 MP3 和 ffprobe 元数据。
- `tests/test_overrides.py` 覆盖 override 词表改写、未配置跳过和 CLI 命令。
- `workspace/config/local.example.yaml` 已改成 DeepSeek LLM + 本地 TTS 示例。
- `workspace/config/deepseek.env.example` 已添加，真实 `workspace/config/deepseek.env` 被 ignore。
- `workspace/config/overrides.example.yaml` 已添加示例词表，真实 `workspace/config/overrides.yaml` 被 ignore。
- 本机全量测试：`38 passed`。

5090D 已完成 DeepSeek API 和 `adapt` 验证，也完成本地 TTS wrapper 验证。自制长样本、NASA 真实 podcast transcript 和 MVP-0.5 自用回归都已生成可听 MP3。MVP-0 acceptance 与 MVP-0.5 Self-use 已完成。下一步进入 MVP-1 Real Podcasts。不要同时接 ASR、voice clone、后台服务或 App。

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

MVP-0.5 本地 override 已在 5090D 上通过验证：

- 远端全量测试：`37 passed`。
- `overrides-smoke` 使用临时 workspace、fixture LLM/TTS/publish 和临时 override YAML 跑通 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Overrides Smoke"`。
- stdout 包含 `overrides: 2 replacements from 2 rules`。
- `script_text` 和 `manifest_text` 都为 `中文口播：欢迎 to the 样例节目.`。
- `run.json` 输出 `status=succeeded`，稳定 `published/feed.xml` 存在。

MVP-0.5 self-use acceptance 已在 5090D 上完成：

- 真实 run-id：`mvp05-selfuse-nasa`。
- 回归流程：真实 NASA Crew-9 transcript -> `ingest` -> `normalize` -> `adapt(DeepSeek)` -> `babelecho script` 预览 -> override -> `run --from-stage synthesize` -> 本地 TTS -> `assemble` -> `publish`。
- script/manifest 均为 9 段；override 命中 10 次。
- 最终 MP3 为 `24000 Hz`、mono、约 `355.5s`。
- `run.json` 输出 `status=succeeded`、`from_stage=synthesize`；`workspace/published/feed.xml` 已生成。
- 产物已从 5090D 拷回本机 ignored 路径：`workspace/runs/mvp05-selfuse-nasa/output/audio.mp3`、`script/zh.json`、`segments/manifest.json`、`publish/feed.xml`。

## 按需打开的文件

新 session 不需要一开始按顺序读完下面所有文件。先读本文件即可；如果任务涉及对应方向，再打开相关文件：

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
11. `src/babelecho/cli.py`
12. `src/babelecho/status.py`
13. `src/babelecho/overrides.py`
14. `tests/test_end_to_end_fixture.py`
15. `tests/test_overrides.py`
16. `workspace/config/local.example.yaml`
17. `workspace/config/overrides.example.yaml`

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
  - `overrides`
  - `speaker-voices`
  - `synthesize`
  - `assemble`
  - `publish`
- `babelecho run` 支持 `--to-stage` 停在指定阶段，也支持 `--from-stage` 从指定阶段继续。
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
- 历史 CosyVoice2 模型目录是 `/home/th5090d/Develop/ai_tools/CosyVoice/pretrained_models/CosyVoice2-0.5B`；MVP-1 当前运行默认不再要求部署它。
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

MVP-0 acceptance 和 MVP-0.5 Self-use 已完成：

```text
真实英文 transcript -> normalized.json -> DeepSeek 中文口播稿 -> 5090D CosyVoice-300M-SFT -> wav segments -> MP3 -> publish/feed.xml
```

下一步继续 MVP-1 Real Podcasts：

1. 在真实 RSS、episode_page 或 podcast_index_api run 上验证 `speaker_voices.mode: infer_once` 的多 speaker profile，并听测 speaker 性别方向是否明显改善。
2. 用 iTunes -> RSS episode selection 选出有 transcript 的真实 episode，跑到 `adapt`。
3. 支持多 episode feed，跳过已处理 episode。
4. 继续补真实来源的失败诊断和站点/API 边界记录。

不要进入：

- voice clone
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

MVP-0.5 acceptance 已满足：

- `mvp05-selfuse-nasa` 使用真实 NASA Crew-9 transcript，跑通 DeepSeek adapt、脚本预览、override、5090D 本地 TTS、assemble 和 publish。
- 最终 MP3 和稳定 feed 已生成，产物已拷回本机 ignored `workspace/runs/mvp05-selfuse-nasa/`。
- `run --to-stage adapt` 已支持 TTS 前停下预览，`run --from-stage synthesize` 已支持从预览/编辑后的脚本继续。

仍然保留到后续阶段：

- 真实 RSS / episode_page / podcast_index_api 上的 `speaker_voices.mode: infer_once` 多 speaker profile 仍需真实回归；每个 podcast 的 source config 和批处理仍未做。
- 真实 podcast 来源扩展和多 episode feed 仍在 MVP-1 后续；官网 episode 页面 transcript 链接解析已通过 `source.type=episode_page` 完成第一版，PodcastIndex API episode ingest 已通过 `source.type=podcast_index_api` 完成第一版，PodcastIndex 搜索/选择 CLI 已完成第一版，iTunes feed discovery、RSS episode selection 和 YouTube captions source 已完成第一版代码路径。
- 固定中文音色校准只选择或调整本地 TTS 可用声音和参数，不做原主播 voice clone。
- 第一轮和第二轮音色校准样本已在 5090D 生成并拷回本机 ignored `workspace/runs/`；这些音频不进入 git。
- 用户曾反馈 D 最满意；后续单男、单女、多人验证后，MVP-1 运行默认已改为 `CosyVoice-300M-SFT` 的 `sft_builtin_4role`，D 样本只保留为历史校准记录。
- 公开 RSS 端到端 Real Run 已完成，证明给定 RSS 后可以自动读取 RSS item 内的 transcript 并生成中文 MP3/feed；已支持从已获取的 PodcastIndex episode JSON 读取 `transcripts[].url` / `transcriptUrl`；已支持 PodcastIndex API episode ingest 和搜索/选择 CLI；已支持官网 episode 页面 transcript-only ingest；TTS batch wrapper 已解决每段重复加载 CosyVoice 的主要性能问题；`sft_builtin_4role` 已提供 MVP-1 多 speaker 基线，`speaker_voices.mode: infer_once` 已补上每集一次 LLM 性别方向推断。后续重点转向真实 RSS / episode_page / podcast_index_api 多 speaker 回归和多 episode feed。授权男声/中性 reference wav 比选进入 deferred voice work，不阻塞 MVP-1 来源接入。

## 如果发生分支情况

- 如果 MVP-1 真实来源输入边界不清：先写一个小计划，不直接堆 CLI 参数。
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
