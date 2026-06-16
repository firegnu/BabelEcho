# Resume Prompt

这个文件用于新 session 快速接回 BabelEcho 当前上下文。新 session 只需要先读本文件，再按其中引用的文档继续。

## 给新 session 的第一条指令

```text
你现在在 BabelEcho 项目中工作。请先阅读 resume-prompt.md、HANDOFF.md、docs/plans/README.md 和 docs/plans/01-backend-mvp0/01-local-llm-adapt.md，然后从 01.01 DeepSeek LLM Adapt 基线接入计划继续执行。

重要约束：
- 当前 MVP-0 只是 transcript-first 工程链路，不是完整产品。
- 5090D 上 fixture 全链路已经跑通：ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish。
- 当前还没有真实翻译、真实 TTS、voice clone、ASR 或真实播客来源接入。
- 下一步只接 DeepSeek API 的 adapt 基线，不要同时推进 TTS、来源、voice clone、App 或后台服务。
- 当前阶段采用临时混合验证：LLM adaptation 使用 DeepSeek API，TTS 后续仍在 5090D 本地运行；最终方向仍是 local-first。
- Python 环境必须使用项目内 .conda/babelecho-dev，不要使用 base env。
- 真实 runtime config、workspace/runs、生成音频、模型缓存、本地配置和 API key 不要提交。
```

## 当前执行位置

当前正在执行：

```text
docs/plans/01-backend-mvp0/01-local-llm-adapt.md
```

进度：

- 01.01 已从“本地 LLM vLLM 接入”改为“DeepSeek LLM Adapt 基线接入”。
- 5090D 上已确认：
  - `git status --short --branch` 输出 `## main...origin/main`
  - `git --no-pager log --oneline -3` 输出：
    - `114577b docs: add resume prompt for new sessions`
    - `0644741 docs: add numbered plan for local llm adapt`
    - `9be15d8 docs: refresh handoff after fixture smoke`
  - `curl -sS http://127.0.0.1:8000/v1/models` 返回 `{"detail":"Not Found"}`，说明 8000 端口不是当前需要的 OpenAI-compatible LLM endpoint。
- 已决策：不继续优先部署本地 LLM；先使用 DeepSeek API 做 LLM adaptation，5090D 后续专注本地 TTS。

MacBook 已实现：

- `src/babelecho/llm.py` 增加 `openai_compatible` provider。
- 支持 `api_key_file`、`api_key_env`、Authorization header、可选 `extra_body`。
- `tests/test_llm.py` 覆盖 DeepSeek provider 行为。
- `workspace/config/local.example.yaml` 已改成 DeepSeek LLM + 本地 TTS 示例。
- `workspace/config/deepseek.env.example` 已添加，真实 `workspace/config/deepseek.env` 被 ignore。
- 本机全量测试：`16 passed`。

下一步应让 5090D 填写 ignored `workspace/config/deepseek.env`，创建 ignored `workspace/config/local-deepseek.yaml` 并运行 `adapt`。

## 必读文件

按顺序读：

1. `HANDOFF.md`
2. `docs/plans/README.md`
3. `docs/plans/01-backend-mvp0/01-local-llm-adapt.md`
4. `src/babelecho/llm.py`
5. `tests/test_llm.py`
6. `workspace/config/local.example.yaml`

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
- `openai_compatible` LLM provider 已实现，但还没有在 5090D 上用真实 DeepSeek API key 跑过 `adapt`。

## 下一个目标

只验证：

```text
英文 transcript -> DeepSeek API -> 中文口播稿 script/zh.json
```

不要进入：

- 真实 TTS
- voice clone
- 真实播客来源
- ASR
- 后台服务
- macOS App
- 本地 LLM serving

## 成功标准

本阶段完成时应满足：

- 5090D 上 DeepSeek API key 可用。
- `workspace/config/deepseek.env` 存在但未提交，且只在远端本地保存真实 key。
- `workspace/config/local-deepseek.yaml` 存在但未提交。
- `babelecho adapt` 使用 `llm.provider: openai_compatible` 成功运行。
- `workspace/runs/fixture-smoke/script/zh.json` 由 DeepSeek 生成。
- 输出不再是 fixture 的 `中文口播：原英文`。
- 中文内容基本自然，适合口播，且没有明显英文残留、Markdown 或模型解释。
- `DEEPSEEK_API_KEY` 未写入 tracked 文件、日志或示例配置；真实 key 只放 ignored `workspace/config/deepseek.env`。

## 如果发生分支情况

- 如果 DeepSeek `curl /models` 失败：不要改 TTS，先处理 key、网络、账号或余额。
- 如果 `/chat/completions` 返回结构和当前代码不兼容：改 `src/babelecho/llm.py`，并补测试。
- 如果接口可用但中文质量差：只调 prompt、temperature、max_tokens 或分段策略。
- 如果 `adapt` 成功且质量可接受：进入 `01.03` 本地中文 TTS；真实 transcript 来源继续后置。

## 收尾规则

如果新 session 修改了代码或文档：

- 跑与改动相关的验证。
- 提交前执行隐私扫描：
  - `gitleaks`
  - `trufflehog`
  - 简单 grep 检查 private key、OpenAI/GitHub/AWS/Bearer/password 模式
- 更新 `HANDOFF.md` 或本文件中已经过期的状态。
- 提交并 push 到 `origin/main`，除非用户明确要求暂不提交。
