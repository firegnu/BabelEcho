# 01.01 本地 LLM Adapt 接入计划

状态：`ready`

日期：2026-06-16

父计划：`01-backend-mvp0`

## 目标

把当前 fixture 版 `adapt` 替换成 5090D 上的真实本地 LLM 调用，验证“英文 transcript -> 中文口播稿”的质量。此计划只处理中文脚本生成，不处理真实 TTS、voice clone、来源接入或 macOS App。

## 背景

当前 5090D 已跑通 MVP-0 fixture 全链路：

```text
ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish
```

但其中 `adapt(fixture)` 只是给英文片段加 `中文口播：` 前缀，不是真实翻译或改写。下一步应先替换这一段，因为中文稿质量决定后续 TTS 和发布产物是否值得继续。

## 范围

In:

- 启动或确认 5090D 本地 OpenAI-compatible LLM 服务。
- 配置 `llm.provider: local_vllm`。
- 只运行 `babelecho adapt`。
- 检查 `workspace/runs/fixture-smoke/script/zh.json` 的中文口播质量。
- 必要时调整 `src/babelecho/llm.py` 的接口兼容和 prompt。

Out:

- 不接真实 Apple Podcasts、Spotify、YouTube 来源。
- 不接真实 TTS。
- 不做 voice clone。
- 不做 ASR。
- 不做后台服务、任务队列或 macOS App。

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

- 5090D 上有一个可用的本地大模型，且能通过 OpenAI-compatible HTTP API 暴露。

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

### 01.01.02 启动本地 LLM 服务

目标是让 5090D 暴露一个本机可访问的 OpenAI-compatible 地址，例如：

```text
http://127.0.0.1:8000/v1
```

模型优先使用中文和中英转换能力较好的 instruct 模型。第一版先追求稳定输出，不追求极限速度。

### 01.01.03 验证 LLM HTTP 接口

先不跑 BabelEcho，直接用 HTTP 验证服务是否可用：

```bash
curl -sS http://127.0.0.1:8000/v1/models
```

再用一次最小 chat completion 验证模型能返回中文：

```bash
curl -sS http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "你的模型名",
    "messages": [
      {
        "role": "user",
        "content": "请用一句自然中文说明你可以处理英文播客转写。"
      }
    ],
    "temperature": 0.3,
    "max_tokens": 128
  }'
```

如果这一步失败，不进入 BabelEcho，先解决 LLM serving。

### 01.01.04 创建本地配置

创建 `workspace/config/local-llm.yaml`。该文件被 `.gitignore` 忽略，不提交。

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

本计划里 `tts.provider` 保持 `fixture`，避免真实 LLM 和真实 TTS 两个变量同时变化。

### 01.01.05 只运行 adapt

```bash
export PYTHON=.conda/babelecho-dev/bin/python
export WORKSPACE=workspace
export RUN_ID=fixture-smoke
export LOCAL_CONFIG=workspace/config/local-llm.yaml

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

- 接口失败：修 `src/babelecho/llm.py` 的 OpenAI-compatible 兼容逻辑，补测试后重新跑。
- 接口成功但质量差：只调整 prompt、温度、分段策略，不进入 TTS。
- 质量可接受：冻结第一版 adapt 行为，进入下一个子计划。

## 验收标准

本计划完成必须同时满足：

- 5090D 上 `babelecho adapt` 使用 `local_vllm` 成功运行。
- `workspace/runs/fixture-smoke/script/zh.json` 由真实本地 LLM 生成。
- 输出不再是 `中文口播：原英文` 的 fixture 形式。
- 输出内容基本符合中文播客口播要求。
- 如改代码，本地测试通过并完成提交、推送、隐私扫描。

## 风险和处理

- vLLM 服务不可用：先用 `curl /v1/models` 和 `curl /v1/chat/completions` 定位，不改 BabelEcho。
- 模型名不匹配：以 `/v1/models` 返回值为准更新 `workspace/config/local-llm.yaml`。
- 输出过长或截断：调整 `max_tokens`，必要时缩短单段输入。
- 输出带解释或格式污染：收紧 prompt，要求只输出中文正文。
- 单段调用太慢：先记录耗时，不急着做并发；MVP-0 优先质量和可调试性。

## 完成后的下一个计划

如果 `01.01` 通过，下一步再从以下两个方向中选一个，不同时做：

- `01.02` 真实 transcript 来源接入。
- `01.03` 本地中文 TTS 接入。

