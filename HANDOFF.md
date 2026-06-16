# BabelEcho 交接

## 1. 会话摘要

本次会话围绕 BabelEcho 的 MVP-0 后端骨架推进：确认当前代码只是工程链路冒烟测试，不等于完整产品。已在 5090D Ubuntu 机器上跑通 fixture 全链路，修复了 `ffmpeg concat` 相对路径问题，并完成当前混合验证路径：LLM adaptation 使用 DeepSeek API，TTS 使用 5090D 本地 CosyVoice2。

## 2. 完成的工作

- 明确产品边界：后端负责拉取 transcript、转译、生成中文音频和发布产物；macOS App 后续只消费已转换好的中文 podcast，不参与转换流程。
- 明确 MVP-0 约束：只支持完整 transcript 输入，不做 ASR、不做音频-only 输入、不做原主播 voice clone、不做后台服务或 App 集成。
- 已实现分阶段 Python CLI：
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
- 已确认 5090D 仓库代码更新到最新：
  - `114577b docs: add resume prompt for new sessions`
  - `0644741 docs: add numbered plan for local llm adapt`
  - `9be15d8 docs: refresh handoff after fixture smoke`
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
- 最新代码修复提交：
  - `91ff555 fix: use absolute paths for ffmpeg concat`

## 3. 待完成的工作

- 当前真实能力已经包括 DeepSeek 生成中文口播稿和 5090D 本地 CosyVoice2 合成 wav，但仍不是完整产品：
  - 来源仍是手写 YAML 指向 transcript 文件，没有接真实 Apple Podcasts、Spotify、YouTube 或其他来源发现逻辑。
  - 当前 TTS 是单固定声音，不做原主播 voice clone。
  - 还没有多说话人 `speaker -> voice` 映射。
- 下一步应使用更长 transcript 做听感和分段验证，不要同时接 ASR、voice clone 或 App。
- DeepSeek adapt 基线已经跑通；后续只在 prompt 质量明显不满足时再回到 LLM adapt。

## 4. 关键决策

- MVP-0 采用 CLI-first、文件产物驱动，不先做 Web 后台、队列、数据库或常驻服务。
- 最终方向仍是 local-first，但当前阶段明确接受 DeepSeek API 作为 LLM adaptation 的临时质量基线。
- 先验证 transcript 到中文口播脚本的质量，再投入 TTS 和 voice clone。
- `DEEPSEEK_API_KEY` 只能放在 ignored `workspace/config/deepseek.env` 中，不能写入 tracked 文件。
- 真实 runtime config、生成音频、run outputs、模型缓存、conda env 不进入 git。
- 5090D 执行代码方式：MacBook 修改并 push；必要时通过 `ssh my-5090d-host` 在远端运行验证命令，但不在 5090D 上安装或运行 Codex agent。
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
- `src/babelecho/llm.py`
- `src/babelecho/audio.py`
- `tools/cosyvoice_tts_wrapper.py`
- `tests/test_audio.py`
- `tests/test_llm.py`
- `tests/test_cosyvoice_wrapper.py`

## 6. 下一步建议

1. 用更长的 transcript 样例跑 DeepSeek adapt + CosyVoice synthesize，听感评估中文播客效果。
2. 调整分段策略、语速和固定声音；暂时不做原主播 voice clone。
3. 如果要支持两人播客，再增加 `speaker -> voice` 映射，不要先做 App 或 ASR。

## 当前 Git 状态

- 分支：`main`
- 本轮文档更新前最近提交：
  - `e3e36ad test: isolate missing deepseek key file check`
  - `3417af6 docs: record deepseek adapt verification`
  - `e004674 feat: load deepseek key from ignored env file`
- 本轮文档修改需要完成隐私扫描、提交和推送后，5090D 再 `git pull`。
