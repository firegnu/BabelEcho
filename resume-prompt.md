# Resume Prompt

这个文件用于新 session 快速接回 BabelEcho 当前上下文。新 session 只需要先读本文件，再按其中引用的文档继续。

## 给新 session 的第一条指令

```text
你现在在 BabelEcho 项目中工作。请先阅读 resume-prompt.md、HANDOFF.md、docs/plans/README.md、docs/plans/01-backend-mvp0/01-local-llm-adapt.md 和 docs/plans/01-backend-mvp0/03-local-tts.md。01.01 DeepSeek LLM Adapt 基线接入已经完成，01.03 本地中文 TTS 接入也已在 5090D 上完成最小验证。

重要约束：
- 当前 MVP-0 只是 transcript-first 工程链路，不是完整产品。
- 5090D 上 fixture 全链路已经跑通：ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish。
- 当前已有 DeepSeek API 生成中文口播稿的真实 adapt 基线，也已有 5090D 本地 CosyVoice2 生成真实 wav 的最小 TTS 基线，但还没有 voice clone、ASR 或真实播客来源接入。
- 下一步只用更长 transcript 验证听感和分段，不要同时推进来源、voice clone、ASR、App 或后台服务。
- 当前阶段采用临时混合验证：LLM adaptation 使用 DeepSeek API，TTS 后续仍在 5090D 本地运行；最终方向仍是 local-first。
- Python 环境必须使用项目内 .conda/babelecho-dev，不要使用 base env。
- 真实 runtime config、workspace/runs、生成音频、模型缓存、本地配置和 API key 不要提交。
```

## 当前执行位置

当前已完成：

```text
docs/plans/01-backend-mvp0/01-local-llm-adapt.md
docs/plans/01-backend-mvp0/03-local-tts.md
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
- 01.01 已在 5090D 上完成验收。
- 01.03 已在 5090D 上完成最小本地 TTS 验收。

MacBook 已实现：

- `src/babelecho/llm.py` 增加 `openai_compatible` provider。
- 支持 `api_key_file`、`api_key_env`、Authorization header、可选 `extra_body`。
- `tests/test_llm.py` 覆盖 DeepSeek provider 行为。
- `workspace/config/local.example.yaml` 已改成 DeepSeek LLM + 本地 TTS 示例。
- `workspace/config/deepseek.env.example` 已添加，真实 `workspace/config/deepseek.env` 被 ignore。
- 本机全量测试：`18 passed`。

5090D 已完成 DeepSeek API 和 `adapt` 验证，也完成 CosyVoice2 本地 TTS wrapper 验证。下一步应做更长 transcript 的听感和分段验证，不要同时接真实来源、ASR、voice clone、后台服务或 App。

## 必读文件

按顺序读：

1. `HANDOFF.md`
2. `docs/plans/README.md`
3. `docs/plans/01-backend-mvp0/01-local-llm-adapt.md`
4. `docs/plans/01-backend-mvp0/03-local-tts.md`
5. `src/babelecho/llm.py`
6. `tests/test_llm.py`
7. `tools/cosyvoice_tts_wrapper.py`
8. `workspace/config/local.example.yaml`

## 当前项目事实

- 仓库：`/Users/firegnu/Developer/personal_projs/BabelEcho`，远端 5090D 路径是 `/home/th5090d/Develop/personal_project/BabelEcho`。
- 当前协作方式：本机改代码并 push，必要时通过 `ssh my-5090d-host` 在 5090D 上远程执行验证命令；不在 5090D 上安装或运行 Codex agent。
- 已有 CLI 阶段：
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

## 下一个目标

下一步只验证：

```text
更长中文口播稿 script/zh.json -> 本地中文 TTS -> segments/*.wav -> 可听性评估
```

不要进入：

- voice clone
- 真实播客来源
- ASR
- 后台服务
- macOS App
- 本地 LLM serving

## 成功标准

本阶段完成时应满足：

- 使用更长 transcript 样例，而不是只有一句 `欢迎收听本期节目。`
- 检查中文口播自然度、停顿、语速、分段长度和固定声音可接受度。
- `workspace/runs/<run-id>/segments/manifest.json` 指向真实 TTS 生成的 wav。
- `assemble` 继续生成可播放 MP3。
- 不引入 voice clone，不要求原主播音色。

## 如果发生分支情况

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
