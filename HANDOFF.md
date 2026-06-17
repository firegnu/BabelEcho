# BabelEcho 交接

## 1. 会话摘要

本次会话围绕 BabelEcho 的 MVP-0 后端骨架、acceptance 和 MVP-0.5 自用流程收口推进：当前混合验证路径是 LLM adaptation 使用 DeepSeek API，TTS 使用 5090D 本地 CosyVoice2；自制长样本、真实 NASA podcast transcript 和 MVP-0.5 自用回归都已生成可听中文 MP3，且 MVP-0 / MVP-0.5 均已完成。

## 2. 完成的工作

- 明确产品边界：后端负责拉取 transcript、转译、生成中文音频和发布产物；macOS App 后续只消费已转换好的中文 podcast，不参与转换流程。
- 明确 MVP-0 约束：只支持完整 transcript 输入，不做 ASR、不做音频-only 输入、不做原主播 voice clone、不做后台服务或 App 集成。
- 已实现分阶段 Python CLI：
  - `run`：一条命令编排 `ingest -> normalize -> adapt -> synthesize -> assemble -> publish`。
  - `ingest`：读取 transcript URL 或本地 transcript 文件。
  - `normalize`：解析 `.vtt`、`.srt`、`.txt` 到统一 JSON。
  - `adapt`：当前已支持 fixture LLM、本地 OpenAI-compatible vLLM，以及 DeepSeek/OpenAI-compatible provider。
  - `synthesize`：fixture 静音 WAV 或本地 TTS CLI wrapper。
  - `assemble`：调用 `ffmpeg` 拼接 WAV 到 MP3。
  - `publish`：生成静态 episode 目录和 RSS `feed.xml`。
- 5090D 已验证 fixture 全链路：
  - `ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish`
  - 已生成 `workspace/runs/fixture-smoke/output/audio.mp3`
  - 已生成 `workspace/runs/fixture-smoke/publish/feed.xml`
- 修复 `assemble` 在 5090D 上失败的问题：
  - 根因：`concat.txt` 中写入相对路径后，`ffmpeg` 按 `output/` 目录解析，导致路径变成 `output/workspace/runs/...`。
  - 修复：`src/babelecho/audio.py` 写入绝对音频片段路径。
  - 回归测试：`tests/test_audio.py` 覆盖相对 `workspace` 场景。
- 已完成验证：
  - `tests/test_audio.py`: `1 passed`
  - 全量测试：`14 passed`
  - 本机真实 fixture pipeline 跑到 `publish/feed.xml`
  - 对 git 跟踪文件运行 `gitleaks` 和 `trufflehog`，未发现泄露。
- 5090D 仓库可通过 `ssh my-5090d-host` 远程执行验证；新 session 需要以远端 `git status --short --branch` 和 `git log --oneline -3` 确认当前同步点。
- 已确认 `http://127.0.0.1:8000/v1/models` 返回 `{"detail":"Not Found"}`，说明 8000 上有服务但不是当前需要的 OpenAI-compatible LLM endpoint。
- 已决定不继续把 24GB 5090D 优先用于本地 LLM serving；先用 DeepSeek API 建立中文口播稿质量基线，把 5090D 留给本地 TTS。
- 已在 MacBook 实现 DeepSeek/OpenAI-compatible provider：
  - `src/babelecho/llm.py` 新增 `openai_compatible` provider。
  - 支持 `api_key_file` 从 ignored env 文件读取 API key，也保留 `api_key_env` 备用。
  - 请求会带 `Authorization: Bearer ...` header。
  - 支持 `extra_body`，用于 DeepSeek `thinking.type: disabled`。
  - `workspace/config/local.example.yaml` 已改成 DeepSeek LLM + 本地 TTS 示例。
  - `workspace/config/deepseek.env.example` 提供可提交的 env 文件模板，真实 `workspace/config/deepseek.env` 被 ignore。
  - `tests/test_llm.py` 覆盖 auth header、`extra_body` 合并、env 文件读取和缺 key 错误。
- 本机全量测试通过：`18 passed`。
- 已在 5090D 上完成 DeepSeek adapt 验证：
  - 远端已拉到 `e004674 feat: load deepseek key from ignored env file`。
  - 远端测试通过：`18 passed`。
  - `workspace/config/deepseek.env` 已由用户填写，且被 `.gitignore` 忽略。
  - `workspace/config/local-deepseek.yaml` 使用 `api_key_file`。
  - DeepSeek `/models` 返回 `deepseek-v4-flash` 和 `deepseek-v4-pro`。
  - `babelecho adapt --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-deepseek.yaml` 成功。
  - `workspace/runs/fixture-smoke/script/zh.json` 输出自然中文：`欢迎收听本期节目。`
- 已在 5090D 上完成本地中文 TTS 验证：
  - 新建专用 conda env：`/home/th5090d/miniforge3/envs/babelecho-tts`。
  - 保持 5090D 可用 GPU 栈：`torch 2.11.0+cu130`、`torchaudio 2.11.0+cu130`、`torchcodec 0.14.0+cu130`。
  - CosyVoice 代码目录：`/home/th5090d/Develop/ai_tools/CosyVoice`。
  - 模型目录：`/home/th5090d/Develop/ai_tools/CosyVoice/pretrained_models/CosyVoice2-0.5B`。
  - 新增 repo wrapper：`tools/cosyvoice_tts_wrapper.py`。
  - 远端 runtime launcher：`/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper`。
  - `tts-wrapper` 单句测试生成 `/tmp/babelecho-wrapper-test.wav`，`24000 Hz`、mono、`6.160000s`。
  - `babelecho synthesize --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-cosyvoice.yaml` 成功，生成真实 `segments/0001.wav`。
  - `workspace/runs/fixture-smoke/segments/0001.wav` 为 `24000 Hz`、mono、`3.080000s`。
  - `babelecho assemble --workspace workspace --run-id fixture-smoke` 成功，生成 `output/audio.mp3`，`24000 Hz`、mono、`3.144000s`。
- 已完成更长样本听感实验：
  - `workspace/runs/long-tts-smoke/output/audio.mp3` 已拷回 MacBook。
  - 中文脚本 4 段，最终 MP3 为 `24000 Hz`、mono、约 `92.8s`。
  - 用户试听反馈：效果还行。
- 已完成真实英文 podcast transcript 实验：
  - 来源：NASA 官方 `Houston We Have a Podcast`，Crew-9 episode transcript。
  - run-id：`nasa-crew9-real-smoke`。
  - 真实样本跑通 `normalize -> adapt(DeepSeek) -> synthesize(CosyVoice2) -> assemble`。
  - 本机产物：
    - `workspace/runs/nasa-crew9-real-smoke/output/audio.mp3`
    - `workspace/runs/nasa-crew9-real-smoke/script/zh.json`
    - `workspace/runs/nasa-crew9-real-smoke/transcript/normalized.json`
  - 首轮验证结果：source/script/audio segments 均为 5 段，MP3 为 `24000 Hz`、mono、约 `367.6s`。
  - 首轮暴露两个问题：speaker label 会进入正文；多人播客现在仍是单一中文声音。
- 已完成 MVP-0 acceptance 收口：
  - `src/babelecho/transcript.py` 已解析 speaker label，把 `Host:`、`Nick Hague:`、`Host (Dane Turner):` 等标签写入 `segment["speaker"]`，并从 `segment["text"]` 中移除。
  - `tests/test_transcript.py` 覆盖段首 label、段内多轮 speaker turn 和普通冒号不误判。
  - 本机全量测试：`21 passed`。
  - 5090D 分支验证：`21 passed`。
  - 5090D NASA 回归：`normalize -> adapt -> synthesize -> assemble -> publish` 已完成。
  - `nasa-crew9-real-smoke` 最终 normalized/script/manifest 均为 9 段；英文 segment text 无 `Host:` / `Nick Hague:` 标签残留；中文脚本无 `主持人：` / `尼克·黑格：` 朗读式标签残留。
  - 最终 MP3：`mp3`、`24000 Hz`、mono、约 `361.1s`。
  - 已验证 publish artifacts：`publish/feed.xml`、episode MP3、`transcript.en.json`、`transcript.zh.json`、`metadata.json`。
- 已完成 MVP-0.5 Self-use：
  - `src/babelecho/cli.py` 增加 `babelecho run`。
  - `run` 支持 `--from-stage` 从 `ingest`、`normalize`、`adapt`、`synthesize`、`assemble` 或 `publish` 继续执行。
  - `run` 支持 `--transcript-file` 直接导入本地 transcript，并可用 `--title` 写入 episode 标题，避免自用时手写 source YAML。
  - `src/babelecho/status.py` 增加 `workspace/runs/<run-id>/run.json`，记录 input、`from_stage`、每个 stage 状态、失败阶段、错误和已知输出路径。
  - `src/babelecho/checks.py` 增加基础质量检查，`babelecho check` 可独立检查 script、segments、output。
  - `src/babelecho/script.py` 增加 `babelecho script`，可在 TTS 前打印 `script/zh.json` 路径、段落编号、文本和 `--from-stage synthesize` 续跑提示。
  - `src/babelecho/publish.py` 仍保留 run-local publish artifacts，同时同步 `feed.xml` 和 episode artifacts 到稳定目录 `workspace/published/`。
  - `run` 在 `adapt`、`synthesize`、`assemble` 后自动检查中文脚本、wav segment 和最终 MP3。
  - `run` 输出包含 `stable feed: workspace/published/feed.xml`。
  - `tests/test_end_to_end_fixture.py` 覆盖 fixture 全链路和从 `synthesize` 恢复执行，保护手工编辑后的 `script/zh.json` 不被重新 adapt 覆盖。
  - `tests/test_end_to_end_fixture.py` 覆盖 `--transcript-file` 自用入口和 ingest 失败时的 `run.json` 失败记录。
  - `tests/test_end_to_end_fixture.py` 覆盖 `babelecho script` 输出和 `workspace/published/feed.xml` 生成。
  - `tests/test_publish.py` 覆盖 run-local publish artifacts 与 stable publish artifacts 同时生成。
  - `tests/test_checks.py` 覆盖空中文稿、超长段落、缺失 wav、缺失 MP3 和 ffprobe 元数据。
  - 本机全量测试：`34 passed`。
  - 5090D 全量测试：`34 passed`。
  - 5090D fixture smoke：`run-command-smoke` 使用 `babelecho run` 生成 `transcript/normalized.json`、`script/zh.json`、`segments/manifest.json`、`output/audio.mp3`、`publish/feed.xml` 和 episode MP3；script/manifest 均为 1 段。
  - 5090D check smoke：`check-command-smoke` 使用 `babelecho run` 自动输出 `check script`、`check segments`、`check output`；独立 `babelecho check` 输出 `script_segments=1`、`audio_segments=1`、`output_sample_rate=16000`、`output_channels=1`、`output_duration_seconds=0.504`。
  - 5090D manual input smoke：`manual-input-status-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Manual Input Smoke"` 跑通；`run.json` 显示 `status=succeeded`、`from_stage=ingest`、6 个 stage 全部 `succeeded`、`audio=output/audio.mp3`、`feed=publish/feed.xml`、`source_type=transcript_file`。
  - 5090D preview/stable publish smoke：`preview-stable-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Preview Stable Smoke"` 跑通；stdout 包含 `stable feed: workspace/published/feed.xml`；`babelecho script` 输出 `script/edit` 路径、`--from-stage synthesize` 提示和中文稿；`workspace/published/feed.xml` 存在且非空，`run.json` 输出 `stable_feed=published/feed.xml`。
- 已完成 MVP-0.5 本地专有名词和发音 override：
  - `src/babelecho/overrides.py` 增加本地精确替换逻辑，读取 `overrides.path` 指向的 YAML 词表，改写 `workspace/runs/<run-id>/script/zh.json`。
  - `src/babelecho/cli.py` 增加 `babelecho overrides --workspace ... --run-id ... --local-config ...`。
  - `babelecho run` 在 `synthesize` 前自动应用 configured overrides，并在 stdout 输出替换数量。
  - `workspace/config/overrides.example.yaml` 提供可提交的示例词表，真实 `workspace/config/overrides.yaml` 继续被 ignore。
  - `workspace/config/local.example.yaml`、README、runbook 和 roadmap 已记录 override 用法。
  - 本机全量测试：`37 passed`。
  - 5090D 全量测试：`37 passed`。
  - 5090D fixture smoke：`overrides-smoke` 使用临时 workspace 和 fixture provider 跑通；stdout 包含 `overrides: 2 replacements from 2 rules`；`script_text` 和 `manifest_text` 都为 `中文口播：欢迎 to the 样例节目.`；`run.json` 状态为 `succeeded`，稳定 `published/feed.xml` 存在。
- 已完成 MVP-0.5 self-use acceptance：
  - `src/babelecho/cli.py` 增加 `babelecho run --to-stage ...`，默认仍到 `publish`；可用 `--to-stage adapt` 在 TTS 前停下预览。
  - `src/babelecho/status.py` 的 `run.json` 记录 `to_stage`，请求范围外阶段标记为 `skipped`。
  - `tests/test_end_to_end_fixture.py` 覆盖 `run --to-stage adapt` 停在中文脚本阶段，不生成音频。
  - 本机全量测试：`38 passed`。
  - 5090D 真实自用回归 run-id：`mvp05-selfuse-nasa`。
  - 回归流程：真实 NASA Crew-9 transcript -> `ingest` -> `normalize` -> `adapt(DeepSeek)` -> `babelecho script` 预览 -> override -> `run --from-stage synthesize` -> CosyVoice2 TTS -> `assemble` -> `publish`。
  - 回归结果：script/manifest 均为 9 段；override 命中 10 次；最终 MP3 为 `24000 Hz`、mono、约 `355.5s`；`workspace/published/feed.xml` 已生成；`run.json` 为 `status=succeeded`、`from_stage=synthesize`。
  - 产物已从 5090D 拷回本机 ignored 路径：`workspace/runs/mvp05-selfuse-nasa/output/audio.mp3`、`script/zh.json`、`segments/manifest.json`、`publish/feed.xml`。

## 3. 待完成的工作

- MVP-0 acceptance 已完成：完整 transcript 到中文 MP3，再到静态 RSS/episode artifacts 的真实路径已经跑通。
- MVP-0.5 Self-use 已完成：手动导入 transcript 后，可以生成私有中文 podcast feed，并已完成真实自用回归。
- 下一阶段是 MVP-1 Real Podcasts，目标是开始处理真实 podcast 来源和常见访谈节目。
- MVP-1 后续优先任务：
  1. 先做固定中文音色校准，解决当前默认女声情绪过满的问题，选出更克制、清晰、适合长时间播客收听的默认音色。
  2. 支持一个真实 podcast RSS 或 episode URL 输入，并优先复用公开 transcript。
  3. 为常见访谈节目设计 `speaker -> voice` 映射，至少支持主持人和嘉宾不同固定中文音色。
- 当前真实能力已经包括 DeepSeek 生成中文口播稿和 5090D 本地 CosyVoice2 合成 wav，但仍不是完整产品：
  - 来源仍是手动提供 transcript 文件或 source config，没有接真实 Apple Podcasts、Spotify、YouTube 或其他来源发现逻辑。
  - 真实 transcript 中的段首和段内 speaker label 已有基础解析/清洗，但后续真实来源仍需要更多样本回归。
  - 当前 TTS 是单固定声音，不做原主播 voice clone。
  - 还没有多说话人 `speaker -> voice` 映射；真实两人或多人播客不能长期用一个中文声音读完整集，后续必须支持至少主持人/嘉宾不同固定音色。
- 多人多音色进入 MVP-1 或专项计划；不要把它回填到 MVP-0.5。
- DeepSeek adapt 基线已经跑通；后续只在 prompt 质量明显不满足时再回到 LLM adapt。
- MVP-1 固定中文音色校准已开始：
  - 本轮未调用 DeepSeek API，直接使用已有 `mvp05-selfuse-nasa/script/zh.json` 中文稿片段做 TTS。
  - 5090D 当前 CosyVoice 目录只有 `asset/zero_shot_prompt.wav` 和 `asset/cross_lingual_prompt.wav` 两个内置参考音频；`CosyVoice2-0.5B` 没有内置 SFT speaker 列表。
  - 已生成三条第一轮候选样本，并拷回本机 ignored 路径 `workspace/runs/voice-calibration-20260617/`：
    - `a-current-zero-shot-female.mp3`：当前默认 zero-shot 女声 baseline，约 `27.5s`。
    - `b-neutral-instruct2-female.mp3`：同一参考音频，使用 `inference_instruct2` 尝试压情绪到自然平静，约 `23.6s`。
    - `c-cross-lingual-reference.mp3`：使用 `cross_lingual_prompt.wav` 的参考音色，约 `24.3s`。
  - 三条样本均为 `24000 Hz`、mono；真实 wav/MP3 和 manifest 不进入 git。
  - 用户当前反馈：C 最好。下一轮优先沿 cross-lingual/reference-audio 路线继续微调，而不是继续围绕默认 zero-shot 女声。
  - 已提交 `ee30dd6 feat: configure cosyvoice reference mode`：
    - `src/babelecho/tts.py` 会把 `tts.mode`、`tts.prompt_wav` 和 `tts.speed` 转发给本地 wrapper。
    - `tools/cosyvoice_tts_wrapper.py` 支持 `zero_shot` 和 `cross_lingual` 两种非 voice-clone 模式，并支持 `speed`。
    - 本机全量测试：`41 passed`。
  - 已在 5090D 生成第二轮 cross-lingual speed 微调样本，并拷回本机 ignored 路径 `workspace/runs/voice-calibration-20260617-round2/`：
    - `d-cross-lingual-speed-100.mp3`：`mode=cross_lingual`，`speed=1.0`，约 `24.7s`。
    - `e-cross-lingual-speed-095.mp3`：`mode=cross_lingual`，`speed=0.95`，约 `26.0s`。
    - `f-cross-lingual-speed-090.mp3`：`mode=cross_lingual`，`speed=0.90`，约 `27.5s`。
  - 第二轮未调用 DeepSeek，只使用第一轮相同中文样本文本和 `cross_lingual_prompt.wav`。5090D 当前 CosyVoice asset 目录仍只有 `zero_shot_prompt.wav` 和 `cross_lingual_prompt.wav`；如 D/E/F 仍不够克制，下一步需要放入本地授权的男声/中性参考 wav 后继续同一路线。

## 4. 关键决策

- MVP-0 采用 CLI-first、文件产物驱动，不先做 Web 后台、队列、数据库或常驻服务。
- 最终方向仍是 local-first，但当前阶段明确接受 DeepSeek API 作为 LLM adaptation 的临时质量基线。
- MVP-0.5 自用流程已收口；下一阶段先投入固定中文音色校准，再做真实 podcast 来源和多说话人固定音色，不进入 voice clone、ASR、App 或后台服务。
- MVP-0 可以接受单固定中文声音；真实多人播客体验需要 `speaker -> voice` 映射，单独进入下一阶段。
- `DEEPSEEK_API_KEY` 只能放在 ignored `workspace/config/deepseek.env` 中，不能写入 tracked 文件。
- 真实 runtime config、生成音频、run outputs、模型缓存、conda env 不进入 git。
- 5090D 执行代码方式：MacBook 修改并 push；必要时通过 `ssh my-5090d-host` 在远端运行验证命令，但不在 5090D 上安装或运行 Codex agent。
- `docs/roadmap.md` 是产品路线入口；`docs/plans/` 放具体执行计划。
- Python pipeline 环境使用项目内 conda env：`.conda/babelecho-dev`，不要使用 base env。
- TTS 模型环境使用 5090D 专用 conda env：`babelecho-tts`，不要把 CosyVoice 的完整 `requirements.txt` 直接装进 pipeline 环境。

## 5. 重要文件

- `README.md`
- `resume-prompt.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/backend-mvp0-runbook.md`
- `docs/backend-mvp.md`
- `docs/backend-mvp0-tech-stack.md`
- `docs/source-ingestion-research.md`
- `docs/plans/01-backend-mvp0/03-local-tts.md`
- `workspace/config/local.example.yaml`
- `workspace/sources/hardcoded.example.yaml`
- `src/babelecho/cli.py`
- `src/babelecho/transcript.py`
- `src/babelecho/llm.py`
- `src/babelecho/adapt.py`
- `src/babelecho/synthesize.py`
- `src/babelecho/audio.py`
- `src/babelecho/publish.py`
- `src/babelecho/overrides.py`
- `src/babelecho/status.py`
- `tools/cosyvoice_tts_wrapper.py`
- `tests/test_transcript.py`
- `tests/test_audio.py`
- `tests/test_llm.py`
- `tests/test_cosyvoice_wrapper.py`
- `tests/test_overrides.py`
- `workspace/config/overrides.example.yaml`

## 6. 下一步建议

1. 先做 MVP-1 固定中文音色校准，解决当前默认女声情绪过满的问题。
2. 再支持一个真实 podcast RSS 或 episode URL 输入，并优先复用公开 transcript。
3. 设计 `speaker -> voice` 映射，至少支持主持人和嘉宾不同固定中文音色。
4. 仍不要同时推进 ASR、voice clone、App 或后台服务。

## 当前 Git 状态

- MVP-0 acceptance 收口基线提交：`815c296 docs: mark mvp0 acceptance complete`；当前 `main` / `origin/main` 可能包含后续 handoff 文档刷新提交，新 session 以 `git log --oneline -3` 为准。
- MVP-0 acceptance 代码验证提交：`9444363 fix: parse transcript speaker labels`。
- MVP-0.5 `babelecho run` 功能提交：`96776e8 feat: add pipeline run command`。
- MVP-0.5 override 功能提交：`4f92d37 feat: add script overrides`。
- MVP-0.5 self-use 收口提交包含 `run --to-stage`、真实 `mvp05-selfuse-nasa` 验证记录和 docs 状态更新；具体提交以 `git log --oneline -3` 为准。
- 5090D `/home/th5090d/Develop/personal_project/BabelEcho` 已用于本轮分支验证；新 session 如需继续远端验证，先执行 `git status --short --branch` 和 `git --no-pager log --oneline -3`，再按需要 `git pull` 或切回 `main`。
- 本轮最终提交后，新 session 先运行：

  ```bash
  git status --short --branch
  git --no-pager log --oneline -3
  ```

- 如果需要在 5090D 上继续验证，先在远端 `/home/th5090d/Develop/personal_project/BabelEcho` 执行 `git status --short --branch`；如落后再 `git pull`。
- 提交前继续执行隐私扫描：`gitleaks`、`trufflehog`、简单 grep。
