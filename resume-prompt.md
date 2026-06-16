# Resume Prompt

这个文件用于新 session 快速接回 BabelEcho 当前上下文。新 session 只需要先读本文件，再按其中引用的文档继续。

## 给新 session 的第一条指令

```text
你现在在 BabelEcho 项目中工作。请先阅读 resume-prompt.md、HANDOFF.md、docs/plans/README.md 和 docs/plans/01-backend-mvp0/01-local-llm-adapt.md，然后从 01.01 本地 LLM Adapt 接入计划继续执行。

重要约束：
- 当前 MVP-0 只是 transcript-first 工程链路，不是完整产品。
- 5090D 上 fixture 全链路已经跑通：ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish。
- 当前还没有真实翻译、真实 TTS、voice clone、ASR 或真实播客来源接入。
- 下一步只接真实本地 LLM 的 adapt，不要同时推进 TTS、来源、voice clone、App 或后台服务。
- 全程本地推理，不使用云 API。
- Python 环境必须使用项目内 .conda/babelecho-dev，不要使用 base env。
- 真实 runtime config、workspace/runs、生成音频、模型缓存和本地配置不要提交。
```

## 当前执行位置

当前正在执行：

```text
docs/plans/01-backend-mvp0/01-local-llm-adapt.md
```

进度：

- `01.01.01 确认代码版本` 已开始。
- 5090D 上已确认：
  - `git status --short --branch` 输出 `## main...origin/main`
  - `docs/plans/01-backend-mvp0/01-local-llm-adapt.md` 存在
- 但 `git log --oneline -3` 当时没有贴出输出，需要补跑无 pager 版本确认。

下一条应让用户在 5090D 上执行：

```bash
cd /home/th5090d/Develop/personal_project/BabelEcho
git --no-pager log --oneline -3
curl -sS http://127.0.0.1:8000/v1/models
```

预期：

- `git --no-pager log --oneline -3` 能看到最新提交，包括计划文档提交。
- `curl /v1/models` 如果本地 LLM 服务已启动，应返回模型列表；如果连接失败，则进入 `01.01.02`，先启动或确认本地 OpenAI-compatible LLM 服务。

## 必读文件

按顺序读：

1. `HANDOFF.md`
2. `docs/plans/README.md`
3. `docs/plans/01-backend-mvp0/01-local-llm-adapt.md`
4. `src/babelecho/llm.py`
5. `workspace/config/local.example.yaml`

## 当前项目事实

- 仓库：`/Users/firegnu/Developer/personal_projs/BabelEcho`，远端 5090D 路径是 `/home/th5090d/Develop/personal_project/BabelEcho`。
- 当前协作方式：本机改代码并 push，5090D `git pull` 后运行；暂不使用 SSH 远程执行。
- 已有 CLI 阶段：
  - `ingest`
  - `normalize`
  - `adapt`
  - `synthesize`
  - `assemble`
  - `publish`
- `adapt(fixture)` 只是生成 `中文口播：<英文原文>`，不是实际翻译。
- `synthesize(fixture)` 只是生成静音 WAV，不是真实 TTS。
- `assemble` 真实调用 `ffmpeg`，此前相对路径 bug 已修复。
- `publish` 真实生成 `feed.xml` 和 episode 静态目录。

## 下一个目标

只验证：

```text
英文 transcript -> 本地 LLM -> 中文口播稿 script/zh.json
```

不要进入：

- 真实 TTS
- voice clone
- 真实播客来源
- ASR
- 后台服务
- macOS App

## 成功标准

本阶段完成时应满足：

- 5090D 上本地 OpenAI-compatible LLM 服务可访问。
- `workspace/config/local-llm.yaml` 存在但未提交。
- `babelecho adapt` 使用 `llm.provider: local_vllm` 成功运行。
- `workspace/runs/fixture-smoke/script/zh.json` 由真实本地 LLM 生成。
- 输出不再是 fixture 的 `中文口播：原英文`。
- 中文内容基本自然，适合口播，且没有明显英文残留、Markdown 或模型解释。

## 如果发生分支情况

- 如果 `curl /v1/models` 失败：不要改 BabelEcho，先处理 LLM serving。
- 如果 `/chat/completions` 返回结构和当前代码不兼容：再改 `src/babelecho/llm.py`，并补测试。
- 如果接口可用但中文质量差：只调 prompt、temperature、max_tokens 或分段策略。
- 如果 `adapt` 成功且质量可接受：再讨论下一个子计划，通常是 `01.02` 真实 transcript 来源或 `01.03` 本地中文 TTS，二选一，不同时做。

## 收尾规则

如果新 session 修改了代码或文档：

- 跑与改动相关的验证。
- 提交前执行隐私扫描：
  - `gitleaks`
  - `trufflehog`
  - 简单 grep 检查 private key、OpenAI/GitHub/AWS/Bearer/password 模式
- 更新 `HANDOFF.md` 或本文件中已经过期的状态。
- 提交并 push 到 `origin/main`，除非用户明确要求暂不提交。

