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
| MVP-0.5 Self-use | 手动导入 transcript 后，一条命令生成可订阅中文 feed | done |
| MVP-1 Real Podcasts | 支持真实 podcast 来源、多说话人和多 episode feed | active |
| MVP-2 Automation | 自动扫描、批处理、状态记录和远程运维 | later |
| Later | 授权参考音色扩展、ASR、voice clone、本地 LLM 替换、App/Web UI | deferred |

## MVP-0 Acceptance

目标：确认当前核心工程链路真正收口，而不只是能生成一次音频。

完成记录：

- Fixture 全链路：`ingest -> normalize -> adapt -> synthesize -> assemble -> publish`。
- DeepSeek API 生成自然中文口播稿。
- 5090D 本地 TTS 生成真实中文 wav/MP3；MVP-1 当前运行默认已切到 `CosyVoice-300M-SFT`。
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
- 已支持 `babelecho run --to-stage adapt`，可在 TTS 前停下预览中文脚本，再用 `--from-stage synthesize` 续跑。
- 已固定私有静态发布目录和稳定 `workspace/published/feed.xml` 路径。
- 基础质量检查已覆盖：
  - 中文脚本为空时失败。
  - 单段文本过长时提醒或失败。
  - TTS 输出 wav 为空时失败。
  - 最终 MP3 时长、采样率、声道可检查。
- 已增加专有名词和发音 override 的简单配置：`overrides.path` 加 `babelecho overrides`，在 TTS 前对中文脚本做本地精确替换。
- 已完成真实自用回归：`mvp05-selfuse-nasa` 使用 NASA Crew-9 transcript，经 DeepSeek adapt、`babelecho script` 预览、override、5090D 本地 TTS、assemble 和 publish 跑通。
- `mvp05-selfuse-nasa` 验证结果：script/manifest 均为 9 段；override 命中 10 次；最终 MP3 为 `24000 Hz`、mono、约 `355.5s`；`workspace/published/feed.xml` 已生成。

验收标准：

- 手动放入一个真实 transcript 后，一条命令可以生成可播放 MP3 和可订阅 feed。
- 同一个 run 失败后，可以从失败阶段继续。
- 生成产物路径清楚，不需要翻日志找文件。

## MVP-1 Real Podcasts

目标：开始处理真实 podcast 来源和常见访谈节目，而不只是手动样本。

需要做：

- 运行默认已改为单模型 `CosyVoice-300M-SFT` / `sft_builtin_4role`，不用再部署 CosyVoice2。
- 固定音色校准只选择或调整本地 TTS 可用声音和参数，不做原主播 voice clone。
- 历史 `cross_lingual_prompt.wav + mode=cross_lingual + speed=1.0` 样本只保留为校准记录；当前不再继续围绕 CosyVoice 内置的两个 wav 反复微调。
- 后续如需新固定音色，优先找可直接用于 300M SFT 或同级单模型部署的方案，不阻塞真实 podcast 来源接入。
- 已支持第一版 RSS feed 输入：`babelecho run --podcast-feed ...`，并用公开 feed 跑通到 `adapt`。
- 已支持 RSS item 内的 `podcast:transcript`。
- 已完成公开 RSS 端到端真实 run：`mvp1-real-rss-monetize-20260617` 使用 `Podcasts for Profit` 的 SRT transcript，经 DeepSeek adapt 和 5090D TTS 生成 75 段中文音频，最终 MP3 约 `840.8s`，并生成 `publish/feed.xml`。
- 已优化真实节目 TTS 执行效率：`local_cli` 现在每个 `synthesize` stage 只启动一次 wrapper，并通过 `segments/tts-batch.json` 批量生成 wav；5090D `batch-wrapper-smoke-20260617` 两段真实 CosyVoice smoke 已通过。
- 已选定 MVP-1 单模型 TTS 规则：运行默认只部署 `CosyVoice-300M-SFT` 的 `sft_builtin_4role`；0/1 个 distinct speaker 且没有显式性别标签时使用 `female_a`，单个 speaker 标签包含 `male` / `男` 时使用 `male_a`，包含 `female` / `女` 时使用 `female_a`；2 个及以上 distinct speaker 使用 `speaker -> voice_role` 稳定映射。
- `sft_builtin_4role` 使用 `CosyVoice-300M-SFT` 的 `中文女 / 中文男 / 英文女 / 英文男` 四个内置 speaker id；它不做原主播 voice clone，不依赖额外参考 wav，也不要求部署 `CosyVoice2-0.5B`。
- 已支持 `speaker -> voice_role` 稳定映射：同一 run 中按 speaker 首次出现顺序分配 `female_a / male_a / female_b / male_b`，同名 speaker 复用同一角色，超过 4 个 speaker 循环复用。
- 已支持 `source.type=podcast_index_episode`，可从已获取的 PodcastIndex episode JSON 中优先读取 `transcripts[].url`，并回退到 `transcriptUrl`。
- 后续仍需接入 PodcastIndex API 鉴权/请求，或从 episode 页面解析 transcript 链接。
- `episode_page` 来源扩展已拆成计划：`docs/plans/02-real-podcasts/04-episode-page-transcript-source/`。
- 找不到完整 transcript 时，明确标记为不可处理，不静默失败。
- 支持多 episode feed，跳过已处理 episode。
- 支持 speaker label 解析、人工 speaker 修正文件和缺失 speaker 的回退策略。
- 支持每个 podcast 的 source config 和每个 speaker 的 voice config。

验收标准：

- 当前运行默认改为 `CosyVoice-300M-SFT`，历史 `cross_lingual_prompt.wav + speed=1.0` 只保留为校准记录，不作为部署要求。
- 一个有公开 `podcast:transcript` 的 RSS feed 可以被处理成中文 feed。
- 两人访谈的主持人和嘉宾可以用不同固定中文音色输出；三到四人节目可以用 `sft_builtin_4role` 输出可区分的固定角色。
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

- 后续固定音色扩展：优先评估不重新引入双模型部署的方案；它是固定音色扩展，不是原主播 voice clone。
- 本地 LLM 替代 DeepSeek。
- ASR fallback，用于没有 transcript 的 episode。
- 原主播 voice clone。
- 更精细的 speaker diarization。
- Web 管理后台。
- macOS thin client。
- 封面、章节、响度归一、时间轴对齐等发布增强。

## 当前最高优先级

1. 继续扩展真实来源：在已支持 PodcastIndex episode JSON 的基础上，接入 PodcastIndex API 鉴权/请求，或支持 episode 页面提供的 transcript 链接。
2. 在真实 RSS run 上验证 `sft_builtin_4role` 多 speaker profile，并补充人工 speaker 修正文件。
3. 支持多 episode feed，跳过已处理 episode。
