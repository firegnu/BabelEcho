# 后端 MVP-0 技术选型

日期：2026-06-16

## 目标

本文档落地 MVP-0 的技术选型。

MVP-0 已在 [backend-mvp.md](./backend-mvp.md) 中定义为 transcript-only、分阶段脚本流程。本文只回答“用什么技术把这个流程跑起来”，不扩展 MVP 范围。

## 总体原则

- 最终目标保持 local-first；当前验证阶段允许 DeepSeek API 作为 LLM adaptation 的临时质量基线。
- 优先跑通端到端链路，不先做服务化平台。
- 每一步都用文件衔接，便于调试、缓存和单阶段重跑。
- 模型调用和业务 pipeline 分离，避免模型依赖污染业务脚本环境。
- TTS 先 CLI-first，确认质量和稳定性后再考虑服务化。
- API key、真实地址和本地配置只放环境变量或 ignored config，不进入 git。

## 运行角色

5090D Ubuntu 机器：

- 运行 pipeline。
- 运行本地 TTS。
- 运行 `ffmpeg` 音频处理。
- 生成发布产物。
- 当前混合验证阶段通过 DeepSeek API 调用 LLM。
- 后续全本地阶段再运行本地 LLM。

M4 Max MacBook Pro：

- 开发和远程管理。
- 拉取产物试听。
- 后续作为 macOS App 开发和验收设备。

## Python pipeline

MVP-0 采用 Python 分阶段 CLI：

```text
01_ingest
02_normalize_transcript
03_adapt_to_chinese
04_synthesize
05_assemble
06_publish
```

每个阶段：

- 接收 `run-id` 或 workspace 路径。
- 读取上一步文件产物。
- 写出本阶段文件产物。
- 可以独立运行和重跑。

推荐单独环境：

```text
babelecho-pipeline
```

该环境只放业务脚本依赖：

- YAML 配置解析。
- RSS / XML / HTML / transcript 解析。
- JSON schema 校验。
- HTTP client，用于调用 OpenAI-compatible LLM API。
- 调用 `ffmpeg` 的薄封装。

不要把 LLM 或 TTS 模型依赖直接装进 pipeline 环境。

## LLM Adapt

用途：

- `03_adapt_to_chinese`
- 输入 `transcript/normalized.json`
- 输出 `script/zh.json`

当前验证选型：

- DeepSeek API 作为临时 LLM 质量基线。
- 首选 `deepseek-v4-pro`，必要时用 `deepseek-v4-flash` 控制成本和延迟。
- pipeline 通过 OpenAI-compatible `/chat/completions` 调用 DeepSeek。
- 显式关闭 thinking，避免输出解释、推理字段或不可控参数行为。

选择理由：

- DeepSeek 适合作为英文 transcript 到中文口播稿的质量标尺。
- 24GB 5090D 可以先专注本地 TTS，避免 LLM 和 TTS 同时争抢显存。
- OpenAI-compatible 形态便于后续把 provider 切回本地 vLLM。
- 后续替换模型时，尽量只改配置，不改 pipeline 阶段接口。

MVP-0 建议：

- 先使用 DeepSeek 跑通真实中文稿，不同时接真实 LLM 本地部署和真实 TTS。
- 对 DeepSeek 请求优先使用 ignored `workspace/config/deepseek.env` 文件，不把 key 写进 YAML 或 shell 命令。
- 只把 DeepSeek 当成当前验证路径，不把它写成最终生产依赖。

配置草案：

```yaml
llm:
  provider: openai_compatible
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-pro"
  api_key_file: "workspace/config/deepseek.env"
  temperature: 0.3
  max_tokens: 4096
  extra_body:
    thinking:
      type: disabled
```

后续全本地选型：

- vLLM 作为本地 LLM serving。
- 24GB 5090D 优先选择 8B/14B instruct 模型，不以 30B+ 作为第一版目标。
- pipeline 通过 OpenAI-compatible `/v1/chat/completions` 调用本地 vLLM。
- 不在业务脚本内直接加载 transformers 模型。
- 不把 vLLM 暴露到公网，只允许本机或内网访问。

全本地配置草案：

```yaml
llm:
  provider: local_vllm
  base_url: "http://127.0.0.1:8000/v1"
  model: "Qwen/Qwen3-14B"
  temperature: 0.3
  max_tokens: 4096
```

实际模型名可以根据 5090D 显存、下载情况和推理速度调整。

## 本地 TTS

用途：

- `04_synthesize`
- 输入 `script/zh.json`
- 输出 `segments/*.wav`

MVP-0 选型：

- CLI-first。
- 固定中文声音。
- 每个 segment 单独调用 TTS wrapper，生成一个音频文件。
- 不做 TTS HTTP 服务。
- 不做 voice clone。

第一候选路线：

- CosyVoice / Fun-CosyVoice。

选择理由：

- 中文支持好。
- 本地可运行。
- 后续可扩展到 zero-shot、跨语言或 voice clone。
- 先用 CLI 或薄 wrapper 可以绕开服务化和并发问题。

推荐单独环境：

```text
babelecho-tts
```

TTS wrapper 的职责：

- 接收文本、输出路径和 voice 配置。
- 调用具体 TTS 模型。
- 输出 wav 文件。
- 遇到失败时返回非零退出码。

pipeline 阶段只需要知道：

```text
tts-wrapper --text-file <segment.txt> --output <segment.wav> --voice default-zh
```

不要让 pipeline 直接依赖 CosyVoice 的内部 Python API。这样后续换成其它 TTS 时，pipeline 不需要重写。

配置草案：

```yaml
tts:
  provider: local_cli
  command: "tts-wrapper"
  voice: "default-zh"
  output_format: "wav"
```

## 音频处理

用途：

- `05_assemble`
- 拼接 `segments/*.wav`
- 输出 `output/audio.m4a` 或 `output/audio.mp3`

推荐选型：

- `ffmpeg` CLI。

选择理由：

- 格式支持稳定。
- 播客音频产物兼容性好。
- 可以处理拼接、转码、采样率、响度、静音间隔。
- 避免在 Python 中手写复杂音频处理。

MVP-0 建议：

- 分段 TTS 输出统一 wav。
- 最终输出优先 mp3 或 m4a。
- 第一版只做基础拼接和格式转换。
- 响度归一可以作为同阶段后续增强，不阻塞端到端验证。

## 发布产物

用途：

- `06_publish`
- 生成静态中文 podcast 产物。

推荐选型：

- Python 生成 `feed.xml`。
- 静态文件目录承载音频和 metadata。
- Nginx 或已有静态文件服务对外提供访问。

MVP-0 只需要单 episode feed：

```text
publish/
  feed.xml
  episodes/
    <episode-id>/
      audio.mp3
      metadata.json
      transcript.en.json
      transcript.zh.json
```

发布层不依赖数据库。

## 配置文件

MVP-0 先使用 YAML 配置。

建议拆成：

```text
workspace/
  sources/
    hardcoded.yaml
  config/
    local.yaml
```

`sources/hardcoded.yaml` 放 episode 输入。

`config/local.yaml` 放本机模型、命令、路径和发布配置。

不要把密钥、私有公网地址或服务器凭证写进仓库。

## 健康检查

MVP-0 实现前需要手动确认：

1. DeepSeek API 可以用 ignored `workspace/config/deepseek.env` 完成一次短文本中文改写。
2. 如果切回全本地路径，vLLM 本地接口可访问，且选定模型可以完成一次短文本中文改写。
3. TTS wrapper 可以把一句中文生成 wav。
4. `ffmpeg` 可以把两个 wav 拼成一个 mp3 或 m4a。
5. 静态发布目录可以通过 HTTP 访问。

这些检查可以先作为手动命令，不需要做成自动化监控。

## 后续演进

MVP-0 跑通后再考虑：

- 把 TTS CLI 包装成本地 HTTP 服务。
- 增加 ASR 模型和仅音频输入。
- 增加 voice clone。
- 增加任务队列和断点续跑状态表。
- 增加订阅清单定时扫描。
- 增加 Web 管理后台。

这些都不进入 MVP-0。
