# BabelEcho Roadmap

日期：2026-06-17

## 目的

本文回答“BabelEcho 距离我自己日常可用还差什么”。它不是单个实现计划，而是把 MVP-0 收口、自用版本、真实播客增强和长期能力排成优先级。

详细执行步骤仍放在 `docs/plans/`。本文只维护阶段、范围和验收标准。

## 原则

- 先把 transcript-first 链路做稳，再做 ASR、voice clone、App 或后台服务。
- 先服务个人使用，不先做多用户、账号、权限或复杂 Web 后台。
- 优先静态 RSS 输出，让现有播客客户端可以直接消费。
- 保持 local-first；DeepSeek API 只作为当前 LLM adaptation 的临时质量基线。
- 真实配置、密钥、模型缓存和生成音频都不进入 git。

## 阶段概览

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| MVP-0 Acceptance | 完成一个真实 transcript 到可发布中文 podcast artifact 的验收闭环 | done |
| MVP-0.5 Self-use | 手动导入 transcript 后，一条命令生成可订阅中文 feed | in progress |
| MVP-1 Real Podcasts | 支持真实 podcast 来源、多说话人和多 episode feed | planned |
| MVP-2 Automation | 自动扫描、批处理、状态记录和远程运维 | later |
| Later | ASR、voice clone、本地 LLM 替换、App/Web UI | deferred |

## MVP-0 Acceptance

目标：确认当前核心工程链路真正收口，而不只是能生成一次音频。

完成记录：

- Fixture 全链路：`ingest -> normalize -> adapt -> synthesize -> assemble -> publish`。
- DeepSeek API 生成自然中文口播稿。
- 5090D 本地 CosyVoice2 生成真实中文 wav/MP3。
- Transcript parser 已解析并清洗真实 speaker label，例如 `Host:`、`Nick Hague:`；label 写入 `segment["speaker"]`，不再留在 `segment["text"]` 中被 TTS 朗读。
- NASA 真实 transcript 样本已在 5090D 上重新跑通 `normalize -> adapt -> synthesize -> assemble -> publish`。
- `nasa-crew9-real-smoke` 验证结果：normalized/script/manifest 都是 9 段；中文脚本 label 扫描无 `主持人：` / `尼克·黑格：` 朗读式标签；最终 MP3 为 `24000 Hz`、mono、约 `361.1s`。
- `publish/feed.xml`、episode MP3、`transcript.en.json`、`transcript.zh.json`、`metadata.json` 已生成并验证存在。

不进入 MVP-0：

- 多说话人多音色。
- ASR fallback。
- 原主播 voice clone。
- 订阅扫描。
- App 或 Web UI。

## MVP-0.5 Self-use

目标：你可以手动给一个 transcript，稳定生成一个私有中文 podcast feed，并能在播客客户端里听。

需要做：

- 已增加一条完整 pipeline 命令：`babelecho run --workspace ... --run-id ... --source-config ... --local-config ...`。
- 已支持手动 transcript 文件入口：`babelecho run --transcript-file ...`。
- 已支持 `--from-stage` 从指定阶段继续执行，避免每次从头跑。
- 已通过 `workspace/runs/<run-id>/run.json` 明确每次 run 的状态、输入、输出路径和失败阶段。
- 已增加基础质量检查命令：`babelecho check --workspace ... --run-id ...`。
- `babelecho run` 已在 `adapt`、`synthesize`、`assemble` 后自动检查关键产物。
- 已增加 TTS 前中文脚本预览入口：`babelecho script --workspace ... --run-id ...`。
- 已固定私有静态发布目录和稳定 `workspace/published/feed.xml` 路径。
- 基础质量检查已覆盖：
  - 中文脚本为空时失败。
  - 单段文本过长时提醒或失败。
  - TTS 输出 wav 为空时失败。
  - 最终 MP3 时长、采样率、声道可检查。
- 已增加专有名词和发音 override 的简单配置：`overrides.path` 加 `babelecho overrides`，在 TTS 前对中文脚本做本地精确替换。

验收标准：

- 手动放入一个真实 transcript 后，一条命令可以生成可播放 MP3 和可订阅 feed。
- 同一个 run 失败后，可以从失败阶段继续。
- 生成产物路径清楚，不需要翻日志找文件。

## MVP-1 Real Podcasts

目标：开始处理真实 podcast 来源和常见访谈节目，而不只是手动样本。

需要做：

- 支持 RSS feed 或 episode URL 输入。
- 支持 RSS `podcast:transcript`。
- 支持 PodcastIndex 的 `transcripts` / `transcriptUrl`。
- 找不到完整 transcript 时，明确标记为不可处理，不静默失败。
- 支持多 episode feed，跳过已处理 episode。
- 支持 speaker label 解析、人工 speaker 修正文件和缺失 speaker 的回退策略。
- 支持 `speaker -> voice` 映射。
- 准备 2 到 3 个固定中文音色，至少区分主持人和嘉宾。
- 支持每个 podcast 的 source config 和每个 speaker 的 voice config。

验收标准：

- 一个有公开 transcript 的 RSS feed 可以被处理成中文 feed。
- 两人访谈的主持人和嘉宾可以用不同固定中文音色输出。
- 已处理 episode 不重复生成。

## MVP-2 Automation

目标：减少手动操作，让 5090D 可以稳定作为转换机器使用。

需要做：

- 支持订阅清单定时扫描。
- 支持多 episode 批处理。
- 支持 run 状态记录和失败重试。
- 支持跳过已完成、重跑指定阶段、清理失败 run。
- 增加 5090D 环境检查：
  - conda env 是否存在。
  - TTS wrapper 是否可执行。
  - CosyVoice 模型路径是否存在。
  - CUDA / GPU 是否可用。
  - `ffmpeg` 是否可用。
- 增加日志归档和常见失败诊断。
- 增加静态发布目录同步或托管策略。

验收标准：

- 5090D 可以定期扫描一组 podcast，并处理新 episode。
- 失败可以定位到明确阶段，并能重试。
- 播客客户端订阅的 feed 长期稳定。

## Later

这些能力有价值，但不应该阻塞自用版本：

- 本地 LLM 替代 DeepSeek。
- ASR fallback，用于没有 transcript 的 episode。
- 原主播 voice clone。
- 更精细的 speaker diarization。
- Web 管理后台。
- macOS thin client。
- 封面、章节、响度归一、时间轴对齐等发布增强。

## 当前最高优先级

1. 用一个真实 transcript 做一次 MVP-0.5 自用流程回归，确认 `run`、脚本预览、override、续跑和发布产物的实际手感。
2. 保留多说话人 `speaker -> voice` 映射到后续 MVP-1/专项计划。
