# BabelEcho 交接

## 1. 会话摘要

本次会话确定了 BabelEcho 的产品边界和 MVP-0 后端方案：先做 transcript-first 的本地推理管线，不做 ASR、不做原主播 voice clone、不做 App 转换工作台。已实现并推送 Python 分阶段 CLI，支持从完整 transcript 到中文脚本、TTS 分段、音频拼接和静态 RSS 发布的 MVP-0 骨架。

## 2. 完成的工作

- 新增架构和调研文档：
  - `docs/architecture.md`
  - `docs/source-ingestion-research.md`
  - `docs/backend-mvp.md`
  - `docs/backend-mvp0-tech-stack.md`
  - `docs/superpowers/plans/2026-06-16-backend-mvp0.md`
- 实现后端 MVP-0 Python 包：
  - `src/babelecho/cli.py`
  - `src/babelecho/ingest.py`
  - `src/babelecho/transcript.py`
  - `src/babelecho/adapt.py`
  - `src/babelecho/synthesize.py`
  - `src/babelecho/audio.py`
  - `src/babelecho/publish.py`
- 新增 fixture 测试和端到端纯逻辑测试，当前本地测试为 `14 passed`。
- 新增 `docs/backend-mvp0-runbook.md`，说明 5090D 上的运行步骤。
- 新增项目入口和代理说明：
  - `README.md`
  - `HANDOFF.md`
  - `AGENTS.md`
  - `CLAUDE.md`
- 已将 MVP-0 实现合并到 `main` 并推送到 `origin/main`。

## 3. 待完成的工作

- 需要在 5090D Ubuntu 机器上 `git pull` 后跑真实环境验证。
- 需要准备真实 `workspace/config/local.yaml`，配置本地 vLLM、TTS CLI wrapper 和发布 base URL。
- 需要选择第一条低风险测试 episode：完整公开 transcript、5 到 15 分钟、speaker 少、术语不密。
- 需要接入真实本地 TTS wrapper。当前测试中使用的是 fixture TTS。
- 需要接入真实 vLLM/Qwen 服务。当前测试中使用的是 fixture LLM。

## 4. 关键决策

- 系统分三层：转换系统、发布产物层、macOS App。
- macOS App 后续只消费已转换好的中文 podcast，不参与后端转换。
- MVP-0 只支持完整 transcript 输入；没有 transcript 的音频-only episode 留到 MVP-1。
- MVP-0 全程本地推理，不使用云 API。
- 后端采用分阶段 Python CLI 和文件产物，不先做 Web 后台、任务队列或常驻服务。
- LLM 走本地 vLLM OpenAI-compatible API；TTS 先 CLI-first。
- 真实 runtime config、生成音频、模型缓存和 run outputs 不进入 git。

## 5. 重要文件

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/backend-mvp0-runbook.md`
- `docs/backend-mvp.md`
- `docs/backend-mvp0-tech-stack.md`
- `docs/source-ingestion-research.md`
- `workspace/config/local.example.yaml`
- `workspace/sources/hardcoded.example.yaml`
- `src/babelecho/cli.py`

## 6. 下一步建议

1. 在 5090D 上执行：

   ```bash
   git pull
   conda create -p ./.conda/babelecho-dev python=3.12 pytest pyyaml -y
   .conda/babelecho-dev/bin/python -m pip install -e . --no-build-isolation
   .conda/babelecho-dev/bin/python -m pytest -v
   ```

2. 准备 `workspace/config/local.yaml` 和 `workspace/sources/hardcoded.yaml`，不要提交真实配置。
3. 先用 fixture 或短 transcript 跑到 `script/zh.json`，再接入真实 vLLM。
4. 真实 LLM 跑通后，再接入 TTS CLI wrapper。
5. 5090D 上遇到失败时，把命令、stderr/stdout、去敏后的 config 和 `runs/<run-id>/` 生成到哪一步贴回来。

## 当前 Git 状态

- 分支：`main`
- 写入本交接文件前的最近提交：
  - `619ef80 docs: add backend mvp0 runbook`
  - `9d1e610 test: cover fixture backend pipeline`
  - `1f900a2 feat: publish static podcast feed`
- 本轮新增 `README.md`、`HANDOFF.md`、`AGENTS.md`、`CLAUDE.md` 四个入口文件。
