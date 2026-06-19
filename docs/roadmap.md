# BabelEcho Roadmap

日期：2026-06-19

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
| MVP-1 Single URL Self-use | 用户提供单个 URL 后，手动选集并生成对应中文播客 | active |
| Phase 2 ASR + Product Surface | ASR、声纹/voice profile、ASR speaker diarization、Web UI 和 App | next |
| Phase 3 Automation | 订阅扫描、多 episode 批处理、PodcastIndex 多 candidate 自动选择、YouTube playlist/channel/show 自动展开、远程运维自动化 | later |
| Later | 微调 `CosyVoice-300M-SFT` 扩展多个中文男声/女声、授权参考音色扩展、本地 LLM 替换 | deferred |

当前阶段边界：

- MVP-1 只做单 URL 自用版：YouTube 单视频 / YouTube Podcasts 单集视频、标准 episode page、Apple Podcasts/iTunes URL + 手动选集、直接 RSS feed URL + 手动选集。
- MVP-1 不做订阅扫描、多 episode 批处理、ASR、声纹、ASR speaker diarization、Web UI 或 App。
- Phase 2 进入音频获取和产品化：ASR、声纹/voice profile、ASR speaker diarization、Web UI 和 App。
- Phase 3 再做自动化扩展：订阅扫描、多 episode 批处理、PodcastIndex 多 candidate 自动选择、YouTube playlist/channel/show 自动展开。

## MVP-0 Acceptance

目标：确认当前核心工程链路真正收口，而不只是能生成一次音频。

完成记录：

- Fixture 全链路：`ingest -> normalize -> adapt -> synthesize -> assemble -> publish`。
- DeepSeek API 生成自然中文口播稿。
- 5090D 本地 TTS 生成真实中文 wav/MP3；MVP-1 当前运行默认是混合本地渲染：`male_a` 走 CosyVoice2，其余角色走 `CosyVoice-300M-SFT`。
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

## MVP-1 Single URL Self-use

目标：开始处理真实 podcast 来源和常见访谈节目，而不只是手动样本。

需要做：

- 运行默认使用 `sft_builtin_4role` 固定角色 profile；`male_a` 渲染走 `CosyVoice2-0.5B cross_lingual speed=1.1`，优先使用本地 calm prompt asset 并做 `male_a` 专用文本平稳化；`female_a / female_b / male_b` 渲染走 `CosyVoice-300M-SFT`。
- 固定音色校准只选择或调整本地 TTS 可用声音和参数，不做原主播 voice clone。
- 历史 `cross_lingual_prompt.wav + mode=cross_lingual + speed=1.0` 样本只保留为校准记录；当前固定使用 speed `1.1` 作为 `male_a` 路线，不再围绕 CosyVoice 内置的两个 wav 反复微调。
- 后续如需新固定音色，优先明确替换哪个固定 role，不阻塞真实 podcast 来源接入。
- 已支持第一版 RSS feed 输入：`babelecho run --podcast-feed ...`，并用公开 feed 跑通到 `adapt`。
- 已支持 RSS item 内的 `podcast:transcript`。
- 已完成公开 RSS 端到端真实 run：`mvp1-real-rss-monetize-20260617` 使用 `Podcasts for Profit` 的 SRT transcript，经 DeepSeek adapt 和 5090D TTS 生成 75 段中文音频，最终 MP3 约 `840.8s`，并生成 `publish/feed.xml`。
- 已支持 `adapt.mode: chunked`：DeepSeek 改写可按完整 segment 聚合 chunk 批量调用，chunk 不切断 segment，返回按原始 id 校验和重建 `script/zh.json`，TTS 不依赖 chunk 顺序。
- `babelecho check --checks script` 会在 TTS 前拦截中文脚本中的 transcript artifact 和明显整段英文残留，避免脏稿直接进入 TTS。
- 已优化真实节目 TTS 执行效率：`local_cli` 现在每个 `synthesize` stage 只启动一次 wrapper，并通过 `segments/tts-batch.json` 批量生成 wav；5090D `batch-wrapper-smoke-20260617` 两段真实 CosyVoice smoke 已通过。
- 已选定 MVP-1 固定角色 TTS 规则：默认规则仍可按 speaker 首次出现顺序稳定映射，启用 `speaker_voices.mode: infer_once` 后会每集最多调用一次 LLM 推断 speaker 的 `male/female/unknown` 方向，再由代码映射到具体 `voice_role`。
- `sft_builtin_4role` 现在是混合本地渲染：`female_a -> 300M SFT 中文女`、`male_a -> CosyVoice2 cross_lingual speed 1.1 + calm prompt if present + text smoothing`、`female_b -> 300M SFT 英文女`、`male_b -> 300M SFT 英文男`；它不做原主播 voice clone。
- 对没有 speaker 标签的 YouTube captions 类点播 run，已支持用 `speaker_voices.default_voice_role` 手动指定 `male_a` / `female_a` 等默认角色；该配置只在脚本没有任何 speaker 时生效，不覆盖多人播客已有的 speaker 映射。
- YouTube 用户 URL `youtube-user-yai8osncmnw-start1521-20260618` 已完成 5090D 完整男声 TTS：223 段全部 `male_a`，最终 MP3 为 `22050 Hz` mono，约 `2602.8s`，已拷回本机 ignored run 目录；用户听检认为整体可接受。
- 近期 agent 主题 YouTube 端到端样本 `youtube-agent-skills-briefing-20260619` 已完成：normalized 28 段，quality=`safe_to_adapt`，DeepSeek adapt 和 script QA 通过，5090D TTS 默认 `female_a`，最终 MP3 为 `22050 Hz` mono，约 `543.8s`；用户试听反馈“听起来很不错”。
- 2026-06-18 的 Practical AI `Model Context Protocol Deep Dive` 点播实跑已通过完整路径：来源 transcript -> chunked DeepSeek -> 每集一次 speaker role 推断 -> 混合本地 TTS -> MP3/RSS；用户试听反馈“基本还可以”。当前规则继续沿用，不再为 MVP-1 阻塞音色实验。
- 已支持 `speaker -> voice_role` 稳定映射：同一 run 中同名 speaker 复用同一角色；LLM 推断的 `male/female` 会分别进入男/女角色池，`unknown` 和推断失败会自动兜底到具体角色，不要求人工介入。
- 已支持 `source.type=podcast_index_episode`，可从已获取的 PodcastIndex episode JSON 中优先读取 `transcripts[].url`，并回退到 `transcriptUrl`。
- 已支持 `source.type=podcast_index_api`，可用 PodcastIndex API 鉴权请求获取 episode metadata，再复用现有 transcript ingest；API credentials 只从环境变量或 ignored env 文件读取。
- 已支持第一版 PodcastIndex 搜索/选择 CLI：`babelecho podcast-index search --query ...` 可搜索 feed，`babelecho podcast-index episodes --feed-id ... --select-index ... --source-config-out ...` 可生成现有 `source.type=podcast_index_api` 配置。
- 已支持 `source.type=episode_page`，可从播客官网 episode 页面发现 transcript 链接或 transcript 正文，并保存为干净 `transcript/raw.txt`；99% Invisible 真实 smoke 已通过到 `ingest`。
- 已支持第一版 iTunes feed discovery：`babelecho itunes search --query ...` 可从 iTunes Search API 找 podcast RSS `feedUrl`，并写出 `source.type=podcast_rss`。
- 已支持 Apple Podcasts/iTunes URL 自用入口：`babelecho itunes episodes --url ...` 可从 URL 解析节目 id，经 iTunes lookup 拿 RSS `feedUrl`，列出 episodes，并把人工选中的单集写成带 `episode_url` 的 `source.type=podcast_rss`。该入口不自动选择 show 内最新集，不直接转换整档节目。
- 已支持第一版 RSS episode selection：`babelecho rss episodes --feed-url ...` 可列出 feed 内 episodes，标记 transcript yes/no，并把选中 episode 写成 `source.type=podcast_rss`。
- 已支持第一版 `source.type=youtube_captions`：用 `yt-dlp --skip-download` 拉公开视频字幕/自动字幕作为 transcript source，不下载音频，不做 ASR。
- 已完成 YouTube 单链接 pre-DeepSeek 清洗和质量门槛第一版：`babelecho episode convert --url ... --to-stage normalize` 对单个 YouTube 视频或 YouTube Podcasts 单集 URL 写出 `transcript/raw.vtt`、`transcript/cleaned.vtt`、`transcript/candidates.json`、`transcript/normalized.json` 和 `transcript/quality.json`；带 `t=` / `start=` 的 URL 会记录 `youtube_start_ms` 并裁剪 normalized 输入；YouTube 标题会写入 source metadata；CLI 会输出 `safe_to_adapt` / `inspect_first` / `reject` 建议和关键指标；字幕说话人箭头 `>>` 会在 deterministic cleaning 阶段移除；会拒绝 playlist/channel/show 类 URL，不做订阅扫描。
- 点播式单集转换入口已完成：用户给一个 episode URL、已有 source YAML 或 transcript file，系统只转换这一集。
- YouTube 单链接探索已先收口；当前真实瓶颈转向标准播客点播来源对接：YouTube Podcasts 单集、RSS/iTunes feed、PodcastIndex episode 和官网 episode 页面之间的 URL 归一、transcript discovery、candidate 选择和清洗诊断。
- 多 episode 批处理和跳过已处理 episode 后移，不作为当前主流程。
- Spotify 和 Apple Podcasts 页面不在 `episode_page` 范围内；YouTube 只走字幕 source，不走页面正文解析。
- 找不到完整 transcript 时，明确标记为不可处理，不静默失败。
- 支持点播转换的清晰失败诊断：不支持的 URL、没有公开字幕、页面/RSS 没有 transcript；下一步会扩展为候选 transcript 记录、评分、清洗和拒绝原因。
- 支持 speaker label 解析、每集一次 LLM speaker voice 推断、可编辑 run-local `script/speaker-voices.json` 和缺失/unknown speaker 的回退策略。
- 支持每个 podcast 的 source config 和每个 speaker 的 voice config。

验收标准：

- 当前运行默认使用 `sft_builtin_4role` 固定角色 profile；`male_a` 用 `CosyVoice2 cross_lingual speed=1.1`、本地 calm prompt asset 和专用文本平稳化，其余角色用 `CosyVoice-300M-SFT`。
- 一个有公开 `podcast:transcript` 的 RSS feed 可以被处理成中文 feed。
- 两人访谈的主持人和嘉宾可以用不同固定中文音色输出；三到四人节目可以用 `sft_builtin_4role` 输出可区分的固定角色。
- 用户指定某一期时，可以把这一期转换成中文 MP3，并可选生成播客客户端可播放的 feed item；99% Invisible `Karaoke Videos` 已通过 `episode convert --url` 在 5090D 跑完整真实链路。

## Phase 2 ASR + Product Surface

目标：从 transcript-first 扩展到音频输入，并提供可日常使用的操作界面。

需要做：

- ASR fallback，用于没有 transcript 的 episode。
- ASR speaker diarization / 声纹分离：ASR 解决“说了什么”，diarization 解决“谁在说”。两者结合后生成带 `speaker_1` / `speaker_2` 时间段的结构化 transcript，再进入现有 `normalize -> adapt -> TTS` 链路。
- Speaker diarization / 声纹分离只用于多人音频的说话人分段和固定中文音色映射，不默认做真实身份识别，也不等同于原主播 voice clone。
- Web UI：提交 URL、查看 run 状态、预览 `quality.json` / 中文脚本、触发 TTS、浏览产物。
- App：先作为 thin client 消费已发布的中文播客 artifacts，不把复杂转换逻辑塞进客户端。

验收标准：

- 没有公开 transcript 的 episode 可以通过音频进入 ASR，并生成结构化 transcript。
- 多人音频至少能稳定分出说话人段落，并映射到固定中文音色。
- 用户不用终端也能提交单个 URL、查看状态和下载/播放产物。

## Phase 3 Automation

目标：减少手动操作，让 5090D 可以稳定作为转换机器使用。

需要做：

- 支持订阅清单定时扫描。
- 支持多 episode 批处理。
- 支持 PodcastIndex 多 candidate 自动选择。
- 支持 YouTube playlist/channel/show 自动展开。
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

- 后续固定音色扩展：先明确替换或新增哪个固定 role；它是固定音色扩展，不是原主播 voice clone。
- 微调 `CosyVoice-300M-SFT`，目标是增加多个可长期使用的中文男声和中文女声，逐步减少当前借用 `英文女` / `英文男` speaker id 作为中文角色的临时性，并在试听确认后再决定是否替换现有 `male_a` CosyVoice2 路线。
- 本地 LLM 替代 DeepSeek。
- 原主播 voice clone。
- 封面、章节、响度归一、时间轴对齐等发布增强。

## 当前最高优先级

1. 完成 MVP-1 最后一块：`episode convert --url ... --select-index ...` 统一支持 Apple Podcasts/iTunes URL 和直接 RSS feed URL，复用现有 `podcast_rss` 后流程。
2. 保持 YouTube 单视频 / YouTube Podcasts 单集视频、标准 episode page、Apple/RSS 四类单 URL 入口相互隔离，任何改动先跑来源矩阵回归。
3. 再跑一个短 Apple/RSS 代表样本的 5090D full-chain，确认单 URL 自用版可以收口。
4. 音色方向后移到 300M SFT 微调：先定义固定角色需求、样本和试听验收，不影响当前 MVP-1 默认规则。
