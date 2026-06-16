# BabelEcho 交接

## 1. 会话摘要

本次会话围绕 BabelEcho 的 MVP-0 后端骨架推进：确认当前代码只是工程链路冒烟测试，不等于真实翻译、真实 TTS 或 voice clone 已完成。已在 5090D Ubuntu 机器上跑通 fixture 全链路，并修复了 `ffmpeg concat` 在相对 `workspace` 路径下拼错音频片段路径的问题。当前新决策是先采用混合验证路径：LLM adaptation 使用 DeepSeek API，TTS 后续仍在 5090D 本地运行。

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
- 最新代码修复提交：
  - `91ff555 fix: use absolute paths for ffmpeg concat`

## 3. 待完成的工作

- 当前真实能力仍然只是 MVP-0 冒烟链路：
  - `adapt(fixture)` 没有真实翻译，只是给英文片段加 `中文口播：` 前缀。
  - `synthesize(fixture)` 没有真实 TTS，只生成静音 WAV。
  - 来源仍是手写 YAML 指向 transcript 文件，没有接真实 Apple Podcasts、Spotify、YouTube 或其他来源发现逻辑。
- 下一步应进入本地中文 TTS 接入，不要同时接真实来源、ASR、voice clone 或 App。
- DeepSeek adapt 基线已经跑通；后续只在 prompt 质量明显不满足时再回到 LLM adapt。

## 4. 关键决策

- MVP-0 采用 CLI-first、文件产物驱动，不先做 Web 后台、队列、数据库或常驻服务。
- 最终方向仍是 local-first，但当前阶段明确接受 DeepSeek API 作为 LLM adaptation 的临时质量基线。
- 先验证 transcript 到中文口播脚本的质量，再投入 TTS 和 voice clone。
- `DEEPSEEK_API_KEY` 只能放在 ignored `workspace/config/deepseek.env` 中，不能写入 tracked 文件。
- 真实 runtime config、生成音频、run outputs、模型缓存、conda env 不进入 git。
- 5090D 执行代码方式：MacBook 修改并 push；必要时通过 `ssh my-5090d-host` 在远端运行验证命令，但不在 5090D 上安装或运行 Codex agent。
- Python 环境使用项目内 conda env：`.conda/babelecho-dev`，不要使用 base env。

## 5. 重要文件

- `README.md`
- `resume-prompt.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/backend-mvp0-runbook.md`
- `docs/backend-mvp.md`
- `docs/backend-mvp0-tech-stack.md`
- `docs/source-ingestion-research.md`
- `workspace/config/local.example.yaml`
- `workspace/sources/hardcoded.example.yaml`
- `src/babelecho/cli.py`
- `src/babelecho/llm.py`
- `src/babelecho/audio.py`
- `tests/test_audio.py`
- `tests/test_llm.py`

## 6. 下一步建议

1. 进入本地中文 TTS 接入计划。
2. 先在 5090D 上手动选型并验证一个中文 TTS CLI wrapper 能把一句中文生成 wav。
3. 保持 `adapt` 已验证配置不变；不要同时接真实 transcript 来源。

## 当前 Git 状态

- 分支：`main`
- 本轮文档更新前最近提交：
  - `e004674 feat: load deepseek key from ignored env file`
  - `dc962af feat: add openai compatible llm provider`
  - `b58eb73 docs: switch mvp0 llm plan to deepseek baseline`
- 本轮文档修改需要完成隐私扫描、提交和推送后，5090D 再 `git pull`。
