# BabelEcho 交接

## 1. 会话摘要

本次会话围绕 BabelEcho 的 MVP-0 后端骨架推进：确认当前代码只是工程链路冒烟测试，不等于真实翻译、真实 TTS 或 voice clone 已完成。已在 5090D Ubuntu 机器上跑通 fixture 全链路，并修复了 `ffmpeg concat` 在相对 `workspace` 路径下拼错音频片段路径的问题。

## 2. 完成的工作

- 明确产品边界：后端负责拉取 transcript、转译、生成中文音频和发布产物；macOS App 后续只消费已转换好的中文 podcast，不参与转换流程。
- 明确 MVP-0 约束：只支持完整 transcript 输入，不做 ASR、不做音频-only 输入、不做原主播 voice clone、不做后台服务或 App 集成。
- 已实现分阶段 Python CLI：
  - `ingest`：读取 transcript URL 或本地 transcript 文件。
  - `normalize`：解析 `.vtt`、`.srt`、`.txt` 到统一 JSON。
  - `adapt`：fixture LLM 或本地 OpenAI-compatible vLLM。
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
- 最新代码修复提交：
  - `91ff555 fix: use absolute paths for ffmpeg concat`

## 3. 待完成的工作

- 当前真实能力仍然只是 MVP-0 冒烟链路：
  - `adapt(fixture)` 没有真实翻译，只是给英文片段加 `中文口播：` 前缀。
  - `synthesize(fixture)` 没有真实 TTS，只生成静音 WAV。
  - 来源仍是手写 YAML 指向 transcript 文件，没有接真实 Apple Podcasts、Spotify、YouTube 或其他来源发现逻辑。
- 下一步应先替换 `adapt` 为真实本地 LLM，不要同时接真实来源和 TTS。
- 需要在 5090D 上启动 OpenAI-compatible 本地 LLM 服务，例如 vLLM。
- 需要准备本地未提交配置 `workspace/config/local-llm.yaml`，配置：
  - `llm.provider: local_vllm`
  - `llm.base_url`
  - `llm.model`
  - `tts.provider: fixture`
- 真实 LLM 跑通后，再考虑真实 transcript 来源和真实中文 TTS。

## 4. 关键决策

- MVP-0 采用 CLI-first、文件产物驱动，不先做 Web 后台、队列、数据库或常驻服务。
- 全程本地推理，暂不使用云 API。
- 先验证 transcript 到中文口播脚本的质量，再投入 TTS 和 voice clone。
- 真实 runtime config、生成音频、run outputs、模型缓存、conda env 不进入 git。
- 5090D 执行代码方式：MacBook 修改并 push，5090D `git pull` 后运行；暂不使用 SSH 远程执行。
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

## 6. 下一步建议

1. 在 5090D 上确认当前代码已到最新：

   ```bash
   git pull
   git log --oneline -3
   ```

2. 启动本地 OpenAI-compatible LLM 服务，并确认可通过类似地址访问：

   ```text
   http://127.0.0.1:8000/v1
   ```

3. 新建本地配置，不提交：

   ```yaml
   llm:
     provider: local_vllm
     base_url: "http://127.0.0.1:8000/v1"
     model: "你的模型名"
     temperature: 0.3
     max_tokens: 4096
   tts:
     provider: fixture
   publish:
     base_url: "https://example.com/babelecho"
   ```

4. 只跑真实 LLM 的 `adapt`：

   ```bash
   export PYTHON=.conda/babelecho-dev/bin/python
   export WORKSPACE=workspace
   export RUN_ID=fixture-smoke
   $PYTHON -m babelecho adapt --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config workspace/config/local-llm.yaml
   sed -n '1,160p' workspace/runs/fixture-smoke/script/zh.json
   ```

5. 如果 `script/zh.json` 质量可接受，再讨论 prompt、分段策略、术语一致性和真实 TTS 接入。

## 当前 Git 状态

- 分支：`main`
- 更新本文件前最近提交：
  - `91ff555 fix: use absolute paths for ffmpeg concat`
  - `f3a82f5 docs: require pip in conda setup`
  - `8c44b9e docs: add project entrypoint docs`
- 更新本文件前工作区状态：干净。
- 本文件更新会作为独立文档提交推送，保证远端和下一次新会话能看到最新 handoff。
