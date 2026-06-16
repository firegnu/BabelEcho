# 01.01 DeepSeek LLM Adapt 基线接入计划

状态：`ready`

日期：2026-06-16

父计划：`01-backend-mvp0`

## 目标

把当前 fixture 版 `adapt` 替换成 DeepSeek API 调用，先建立“英文 transcript -> 中文口播稿”的质量基线。此计划只处理中文脚本生成，不处理真实 TTS、voice clone、来源接入或 macOS App。

这是临时混合验证路径：LLM 使用 DeepSeek API，TTS 后续仍在 5090D 本地运行。BabelEcho 的最终方向仍是 local-first，DeepSeek 输出用于验证脚本质量和指导后续本地 LLM 替换。

## 背景

当前 5090D 已跑通 MVP-0 fixture 全链路：

```text
ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish
```

但其中 `adapt(fixture)` 只是给英文片段加 `中文口播：` 前缀，不是真实翻译或改写。下一步应先用 DeepSeek API 替换这一段，因为中文稿质量决定后续 TTS 和发布产物是否值得继续。

之前计划尝试在 24GB 5090D 上先部署本地 LLM。当前决策改为：先让 DeepSeek 负责 LLM adaptation，把 5090D 留给本地中文 TTS。等脚本质量和 TTS 产物稳定后，再把 LLM 替换回本地 vLLM。

## 范围

In:

- 增加 DeepSeek/OpenAI-compatible LLM provider 支持。
- 配置 `llm.provider: openai_compatible`，通过 `DEEPSEEK_API_KEY` 读取密钥。
- 只运行 `babelecho adapt`。
- 检查 `workspace/runs/fixture-smoke/script/zh.json` 的中文口播质量。
- 必要时调整 `src/babelecho/llm.py` 的接口兼容、DeepSeek 参数和 prompt。

Out:

- 不接真实 Apple Podcasts、Spotify、YouTube 来源。
- 不接真实 TTS。
- 不做 voice clone。
- 不做 ASR。
- 不做后台服务、任务队列或 macOS App。
- 不在本计划内解决本地 LLM serving。

## 前置条件

- 5090D 上仓库已更新到最新 `main`。
- 项目 conda env 已存在并安装当前包：

  ```bash
  .conda/babelecho-dev/bin/python -m pip install -e . --no-build-isolation
  ```

- fixture run 已存在，至少已经生成：

  ```text
  workspace/runs/fixture-smoke/transcript/normalized.json
  ```

- 有可用的 DeepSeek API key。
- `DEEPSEEK_API_KEY` 通过 shell 环境变量提供，不写入 tracked 文件。

## 执行步骤

### 01.01.01 确认代码版本

在 5090D 项目目录执行：

```bash
git pull
git log --oneline -3
```

确认能看到包含以下提交或更新的提交：

```text
91ff555 fix: use absolute paths for ffmpeg concat
9be15d8 docs: refresh handoff after fixture smoke
```

### 01.01.02 验证 DeepSeek API

先不跑 BabelEcho，直接验证 DeepSeek API 和 key 可用：

```bash
export DEEPSEEK_API_KEY='只在当前 shell 设置，不写入仓库'

curl -sS https://api.deepseek.com/models \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY"
```

确认返回模型列表中包含：

```text
deepseek-v4-pro
deepseek-v4-flash
```

再用一次最小 chat completion 验证模型能返回中文口播风格：

```bash
curl -sS https://api.deepseek.com/chat/completions \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{
    "model": "deepseek-v4-pro",
    "messages": [
      {
        "role": "user",
        "content": "请把下面英文播客片段改写成自然、适合口播的简体中文。只输出中文正文，不要解释。\n\nToday we are going to talk about how local-first AI pipelines can help creators publish multilingual podcasts faster."
      }
    ],
    "thinking": {"type": "disabled"},
    "temperature": 0.3,
    "max_tokens": 512,
    "stream": false
  }'
```

如果这一步失败，不进入 BabelEcho，先解决 DeepSeek key、网络或账号问题。

### 01.01.03 增加 OpenAI-compatible provider 支持

当前 `src/babelecho/llm.py` 已有 `local_vllm` provider，但它不支持：

- `Authorization: Bearer <api key>` header。
- 从环境变量读取 API key。
- DeepSeek 的 extra body，例如关闭 thinking。
- DeepSeek `base_url` 不带 `/v1` 的路径形态。

最小实现目标：

- 新增 `openai_compatible` provider。
- 保留 `fixture` 和 `local_vllm` 行为不变。
- `api_key_env` 只引用环境变量名，不把密钥写入 config。
- 支持可选 `extra_body`，用于传入：

  ```yaml
  extra_body:
    thinking:
      type: disabled
  ```

- 补测试覆盖：
  - provider 构造时读取 `api_key_env`。
  - 请求包含 `Authorization` header。
  - 请求 body 合并 `extra_body`。
  - 缺少 API key 时给出明确错误。

### 01.01.04 创建本地配置

创建 `workspace/config/local-deepseek.yaml`。该文件被 `.gitignore` 忽略，不提交。

```yaml
llm:
  provider: openai_compatible
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-pro"
  api_key_env: "DEEPSEEK_API_KEY"
  temperature: 0.3
  max_tokens: 4096
  extra_body:
    thinking:
      type: disabled

tts:
  provider: fixture

publish:
  base_url: "https://example.com/babelecho"
```

本计划里 `tts.provider` 保持 `fixture`，避免真实 LLM 和真实 TTS 两个变量同时变化。

### 01.01.05 只运行 adapt

```bash
export PYTHON=.conda/babelecho-dev/bin/python
export WORKSPACE=workspace
export RUN_ID=fixture-smoke
export LOCAL_CONFIG=workspace/config/local-deepseek.yaml
export DEEPSEEK_API_KEY='只在当前 shell 设置，不写入仓库'

$PYTHON -m babelecho adapt \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --local-config "$LOCAL_CONFIG"
```

预期输出：

```text
workspace/runs/fixture-smoke/script/zh.json
```

### 01.01.06 检查中文脚本

```bash
sed -n '1,200p' workspace/runs/fixture-smoke/script/zh.json
```

重点检查：

- 是否为简体中文。
- 是否保留英文原意。
- 是否像中文播客口播，而不是生硬直译。
- 是否混入英文原文、解释性废话、Markdown 或模型自述。
- 是否每个 segment 都有输出。

### 01.01.07 决策下一步

根据结果分支：

- API 失败：先修 DeepSeek key、网络、余额或 base URL，不改 TTS。
- 请求结构不兼容：修 `src/babelecho/llm.py` 的 OpenAI-compatible 兼容逻辑，补测试后重新跑。
- 接口成功但质量差：只调整 prompt、temperature、max_tokens 或 DeepSeek 模型，不进入 TTS。
- 质量可接受：冻结第一版 adapt 行为，进入本地中文 TTS 接入计划。

后续如果要恢复全本地 LLM，再新开本地 vLLM 子计划，不和本 DeepSeek 基线计划混在一起。

## 验收标准

本计划完成必须同时满足：

- `babelecho adapt` 使用 `openai_compatible` provider 和 DeepSeek API 成功运行。
- `workspace/runs/fixture-smoke/script/zh.json` 由 DeepSeek 生成。
- 输出不再是 `中文口播：原英文` 的 fixture 形式。
- 输出内容基本符合中文播客口播要求。
- `DEEPSEEK_API_KEY` 未写入 tracked 文件、日志或示例配置。
- 如改代码，本地测试通过并完成提交、推送、隐私扫描。

## 风险和处理

- DeepSeek API 不可用：先用 `curl /models` 和 `curl /chat/completions` 定位 key、网络、余额和账号状态。
- 模型名不匹配：以 `/models` 返回值为准更新 `workspace/config/local-deepseek.yaml`。
- key 泄漏风险：key 只放环境变量，不放 YAML、README、HANDOFF、命令历史片段或提交内容。
- 输出过长或截断：调整 `max_tokens`，必要时缩短单段输入。
- 输出带解释或格式污染：收紧 prompt，要求只输出中文正文。
- 单段调用太慢或成本过高：先记录耗时和 token 用量，不急着做并发；MVP-0 优先质量和可调试性。

## 完成后的下一个计划

如果 `01.01` 通过，下一步优先进入：

- `01.03` 本地中文 TTS 接入。

真实 transcript 来源接入推迟到中文脚本和本地 TTS 都可听之后。
