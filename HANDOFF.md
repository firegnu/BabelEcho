# BabelEcho 交接

## 1. 会话摘要

本次会话围绕 BabelEcho 的 MVP-0 后端骨架和 acceptance 收口推进：当前混合验证路径是 LLM adaptation 使用 DeepSeek API，TTS 使用 5090D 本地 CosyVoice2；自制长样本和真实 NASA podcast transcript 都已生成可听中文 MP3，且 MVP-0 acceptance 已完成。

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
- 已开始 MVP-0.5 Self-use：
  - `src/babelecho/cli.py` 增加 `babelecho run`。
  - `run` 支持 `--from-stage` 从 `ingest`、`normalize`、`adapt`、`synthesize`、`assemble` 或 `publish` 继续执行。
  - `src/babelecho/checks.py` 增加基础质量检查，`babelecho check` 可独立检查 script、segments、output。
  - `run` 在 `adapt`、`synthesize`、`assemble` 后自动检查中文脚本、wav segment 和最终 MP3。
  - `tests/test_end_to_end_fixture.py` 覆盖 fixture 全链路和从 `synthesize` 恢复执行，保护手工编辑后的 `script/zh.json` 不被重新 adapt 覆盖。
  - `tests/test_checks.py` 覆盖空中文稿、超长段落、缺失 wav、缺失 MP3 和 ffprobe 元数据。
  - 本机全量测试：`32 passed`。
  - 5090D 全量测试：`32 passed`。
  - 5090D fixture smoke：`run-command-smoke` 使用 `babelecho run` 生成 `transcript/normalized.json`、`script/zh.json`、`segments/manifest.json`、`output/audio.mp3`、`publish/feed.xml` 和 episode MP3；script/manifest 均为 1 段。
  - 5090D check smoke：`check-command-smoke` 使用 `babelecho run` 自动输出 `check script`、`check segments`、`check output`；独立 `babelecho check` 输出 `script_segments=1`、`audio_segments=1`、`output_sample_rate=16000`、`output_channels=1`、`output_duration_seconds=0.504`。

## 3. 待完成的工作

- MVP-0 acceptance 已完成：完整 transcript 到中文 MP3，再到静态 RSS/episode artifacts 的真实路径已经跑通。
- 下一阶段是 MVP-0.5 Self-use，目标是让手动导入 transcript 后可以稳定生成一个私有中文 podcast feed，并能在播客客户端里听。
- MVP-0.5 后续优先任务：
  1. 支持手动导入 transcript 文件作为稳定入口。
  2. 明确每次 run 的状态、输入、输出路径和失败阶段。
  3. 增加 TTS 前中文脚本人工编辑入口。
  4. 增加专有名词和发音 override 的简单配置。
- 当前真实能力已经包括 DeepSeek 生成中文口播稿和 5090D 本地 CosyVoice2 合成 wav，但仍不是完整产品：
  - 来源仍是手写 YAML 指向 transcript 文件，没有接真实 Apple Podcasts、Spotify、YouTube 或其他来源发现逻辑。
  - 真实 transcript 中的段首和段内 speaker label 已有基础解析/清洗，但后续真实来源仍需要更多样本回归。
  - 当前 TTS 是单固定声音，不做原主播 voice clone。
  - 还没有多说话人 `speaker -> voice` 映射；真实两人或多人播客不能长期用一个中文声音读完整集，后续必须支持至少主持人/嘉宾不同固定音色。
- 多人多音色建议作为 MVP-1 或专项计划，不卡住 MVP-0.5 的一条命令自用流程，但必须保留在后续计划中。
- DeepSeek adapt 基线已经跑通；后续只在 prompt 质量明显不满足时再回到 LLM adapt。

## 4. 关键决策

- MVP-0 采用 CLI-first、文件产物驱动，不先做 Web 后台、队列、数据库或常驻服务。
- 最终方向仍是 local-first，但当前阶段明确接受 DeepSeek API 作为 LLM adaptation 的临时质量基线。
- 先把 transcript 到中文口播音频的 MVP-0.5 自用流程做稳，再投入 voice clone、ASR、App 或后台服务。
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
- `tools/cosyvoice_tts_wrapper.py`
- `tests/test_transcript.py`
- `tests/test_audio.py`
- `tests/test_llm.py`
- `tests/test_cosyvoice_wrapper.py`

## 6. 下一步建议

1. 为 MVP-0.5 的下一段写一个小计划，重点是人工脚本编辑，不要扩展真实来源或 App。
2. 增加 TTS 前人工编辑入口，至少允许用户手动改 `script/zh.json` 后用 `babelecho run --from-stage synthesize` 继续跑。
3. 固定私有静态发布目录和稳定 `feed.xml` 路径。
4. 增加专有名词和发音 override 的简单配置。
5. 不要在下一步同时推进 ASR、voice clone、App、后台服务或真实来源发现。

## 当前 Git 状态

- MVP-0 acceptance 收口基线提交：`815c296 docs: mark mvp0 acceptance complete`；当前 `main` / `origin/main` 可能包含后续 handoff 文档刷新提交，新 session 以 `git log --oneline -3` 为准。
- MVP-0 acceptance 代码验证提交：`9444363 fix: parse transcript speaker labels`。
- MVP-0.5 `babelecho run` 功能提交：`96776e8 feat: add pipeline run command`。
- 5090D `/home/th5090d/Develop/personal_project/BabelEcho` 已切回 `main` 并完成过 `815c296` 验证；如需读取最新 handoff 文档，先 `git pull`。
- 本轮最终提交后，新 session 先运行：

  ```bash
  git status --short --branch
  git --no-pager log --oneline -3
  ```

- 如果需要在 5090D 上继续验证，先在远端 `/home/th5090d/Develop/personal_project/BabelEcho` 执行 `git status --short --branch`；如落后再 `git pull`。
- 提交前继续执行隐私扫描：`gitleaks`、`trufflehog`、简单 grep。
