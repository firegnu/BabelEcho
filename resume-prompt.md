# Resume Prompt

这个文件是 BabelEcho 新 session 的唯一必读入口。用户下次只需要让 agent 读取本文件；agent 读完后再根据具体任务，自行打开本文件引用的其他文档。

## 下次新 session 最短指令

```text
你现在在 BabelEcho 项目中工作。请先只阅读 resume-prompt.md。
读完后执行 git status --short --branch 和 git log --oneline -3，
然后用中文简要汇报：当前状态、当前 TTS 规则、下一步建议、是否有未提交变更。
不要一上来改代码。
```

## 给新 session 的第一条指令

```text
你现在在 BabelEcho 项目中工作。请先只阅读 resume-prompt.md；本文件是唯一必读入口。读完后先执行 git status --short --branch 和 git log --oneline -3，再用中文简要汇报当前状态、当前 TTS 规则、下一步建议和是否有未提交变更。不要一上来改代码。

01.01 DeepSeek LLM Adapt 基线接入已经完成，01.03 本地中文 TTS 接入也已在 5090D 上完成验证；MVP-0 acceptance 和 MVP-0.5 Self-use 均已完成。

重要约束：
- 当前 MVP-0 是 transcript-first 工程链路；核心路径和 acceptance 已正式收口。
- MVP-0.5 已完成：`babelecho run` 可以串起 `ingest -> normalize -> adapt -> synthesize -> assemble -> publish`，并支持 `--to-stage` 停在指定阶段、`--from-stage` 从指定阶段继续执行。
- `babelecho run --transcript-file` 可以直接导入本地 transcript 文件；每次 run 会写 `workspace/runs/<run-id>/run.json` 记录输入、阶段状态、失败阶段、错误和输出路径。
- `babelecho check` 可以检查中文脚本、TTS wav segment 和最终 MP3；`run` 已在关键阶段后自动调用这些检查。
- `babelecho script` 可以在 TTS 前预览 `script/zh.json`，并提示编辑后从 `synthesize` 继续；`publish` 会把 feed 和 episode artifacts 同步到稳定目录 `workspace/published/`。
- `overrides.path` 和 `babelecho overrides` 可以在 TTS 前对 `script/zh.json` 做本地精确替换；示例词表是 tracked `workspace/config/overrides.example.yaml`，真实词表继续放 ignored `workspace/config/overrides.yaml`。
- 5090D 上 fixture 全链路已经跑通：ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish。
- 当前已有 DeepSeek API 生成中文口播稿的真实 adapt 基线，也已有 5090D 本地 TTS 生成真实 wav/MP3 的真实基线；MVP-1 单 URL 真实播客来源已经完成，Route B audio-first ASR / diarization / speaker profile artifact 已开始并通过真实 smoke。真实 speaker embedding backend 已用 SpeechBrain ECAPA 跑通，并已生成私有跨集 speaker alias candidates；仍未进入原主播 voice clone 或后台服务。
- 自制长样本、NASA 真实 podcast transcript 和 MVP-0.5 自用回归都已经生成可听中文 MP3；MVP-1 单 URL 自用版已完成，Phase 2 方案已落到 `docs/Phase2双轨后端与静态前端架构.md`：后续按双轨后端和只读前端推进，现有 transcript-first 路线保持稳定，新 audio-first 路线独立处理 ASR、声纹/voice profile 和 ASR speaker diarization。
- MVP-1 当前 TTS 运行默认使用 `tts.voice=sft_builtin_4role` 固定角色 profile，但渲染 backend 是本地双模型：`male_a` 走 `CosyVoice2-0.5B` 的 `cross_lingual + speed=1.1`，优先使用 ignored runtime asset `workspace/config/tts-assets/male_a_cosyvoice2_calm_prompt.wav`，缺失时回退 `cross_lingual_prompt.wav`，并做 `male_a` 专用文本平稳化；`female_a / female_b / male_b` 走 `CosyVoice-300M-SFT`，不经过这段逻辑；不做原主播 voice clone。
- 2026-06-18 用户已试听 Practical AI `Model Context Protocol Deep Dive` 全路径输出，反馈“基本还可以”。run-id 是 `llm-practicalai-mcp-real-20260618`：101 段，DeepSeek chunk 6 次，speaker 推断一次，`Jerod -> male_a`、`Daniel -> male_b`、`Chris -> male_a`，最终 MP3 为 `22050 Hz` mono、约 `1819.5s`，本机产物在 ignored `workspace/runs/llm-practicalai-mcp-real-20260618/`。
- 后续音色方向：用户计划微调 `CosyVoice-300M-SFT`，目标是增加多个稳定中文男声和中文女声。这属于固定角色音色扩展，不是原主播 voice clone；当前默认双模型路由不变，等微调模型试听确认后再决定是否替换 `male_a` CosyVoice2 或 `female_b/male_b` 角色。
- 音色校准第一轮已生成三条本地 TTS 样本，未调用 DeepSeek：`workspace/runs/voice-calibration-20260617/a-current-zero-shot-female.mp3`、`b-neutral-instruct2-female.mp3`、`c-cross-lingual-reference.mp3`。这些产物在 ignored `workspace/runs/` 下，不提交。
- 用户曾反馈 SFT 男声 D 版 EQ 比原始男声亮；但后续确认 `male_a` 最终改为 CosyVoice2 cross-lingual speed `1.1`。D 版 EQ 只保留为历史校准记录，`male_b` 仍恢复为 SFT 原规则。
- 不再继续围绕 CosyVoice 内置两个 wav 反复微调。当前 `male_a` 固定走 CosyVoice2 cross-lingual；5090D 上如存在 `workspace/config/tts-assets/male_a_cosyvoice2_calm_prompt.wav` 会优先用它，否则回退内置 `cross_lingual_prompt.wav`。后续如需扩展固定音色，优先微调 `CosyVoice-300M-SFT` 增加多个中文男声/女声。授权男声/中性 reference wav 只作为备用对比路线；这不是原主播 voice clone。
- MVP-1 真实来源第一版已完成：新增 `source.type=podcast_rss` 和 `babelecho run --podcast-feed ...`，只支持 RSS item 内的 `podcast:transcript`，找不到 transcript 时明确失败，不做 ASR。公开 RSS smoke 使用 `https://feeds.transistor.fm/podcasting-advice` 跑到 `adapt`，fixture script 共 74 段，未调用 DeepSeek。
- MVP-1 公开 RSS 端到端 Real Run 已完成：`mvp1-real-rss-monetize-20260617` 使用 `https://feeds.transistor.fm/podcasts-for-profit-with-morgan-franklin` 的 `#030: When Should You Monetize Your Podcast?`，经 RSS transcript -> DeepSeek -> 5090D TTS -> MP3 -> feed 全链路成功；script/manifest 75 段，MP3 约 `840.8s`，产物在 ignored `workspace/runs/mvp1-real-rss-monetize-20260617/`。
- MVP-1 PodcastIndex episode JSON 输入已完成第一步：新增 `source.type=podcast_index_episode`，`babelecho run --source-config ...` 可从已获取的 PodcastIndex episode JSON 中优先读取 `transcripts[].url`，并回退到 `transcriptUrl`。
- MVP-1 PodcastIndex API 输入已完成第一版：新增 `source.type=podcast_index_api`，支持 PodcastIndex API auth headers、`episodes/byid`、`episodes/byfeedid`、`episodes/byfeedurl`、`episodes/byitunesid`，并复用现有 transcript ingest；API key/secret 只从环境变量或 ignored `workspace/config/podcastindex.env` 读取。已新增 `babelecho podcast-index search` / `episodes` CLI，可搜索 feed、列 episode，并把选中 episode 写成可运行 source config；尚未做多 episode 批处理。
- MVP-1 Episode Page Transcript Source 已完成并补过第一轮标准播客真实页面调试：新增 `source.type=episode_page`，可从播客官网 episode 页面发现 transcript 链接或 transcript 正文，并保存干净 `transcript/raw.txt`；支持 `transcript-content`、`cite + p` speaker 标注、Lex 风格 `ts-segment`、以及页面内 `Transcript` heading 后正文段落。99% Invisible 真实 smoke 已通过到 `ingest`；Practical AI 360、Lex Fridman / Jensen Huang、Cognitive Revolution / Daniel Miessler 三个真实 URL 已跑到 `normalize`，quality 均为 `safe_to_adapt`。覆盖率 smoke 后补了 transcript 链接同源优先规则，避免 Acquired 这类页面误抓外站无关 transcript；Acquired Google 现在明确在 `ingest` 失败，不再产出误导性短 transcript。Practical AI 358 已跑通标准播客页面 -> normalize -> chunked DeepSeek adapt，132 段 `script/zh.json` 通过 script QA，未进入 TTS。这不包含 YouTube、Spotify、Apple Podcasts 页面，也不做 JS 渲染、ASR 或音频下载。
- MVP-1 Discovery Adapters 第一版已完成：新增 `babelecho itunes search`，可用 iTunes Search API 找 podcast RSS `feedUrl` 并输出 `source.type=podcast_rss`；新增 `babelecho itunes episodes --url <Apple Podcasts URL>`，可从 Apple Podcasts/iTunes show 或 episode URL 解析节目 id，经 iTunes lookup 拿 `feedUrl` 后列 RSS episodes，并用 `--select-index ... --source-config-out ...` 写出带 `episode_url` 的 `source.type=podcast_rss`；新增 `babelecho rss episodes`，可列 RSS feed 内 episodes、标记 transcript yes/no，并把选中 episode 写成带 `episode_url` 的 `source.type=podcast_rss`；新增 `source.type=youtube_captions`，用本机 `yt-dlp --skip-download` 拉公开视频字幕/自动字幕作为 transcript source，不下载音频，不做 ASR。
- MVP-1 On-demand Episode Convert 已完成第一版：新增 `babelecho episode convert`，用于自用点播式单集转换；`--url` 会把 YouTube URL 映射到 `source.type=youtube_captions`，把普通 http/https 或本地 episode 页面映射到 `source.type=episode_page`，也可直接传 `--source-config` 或 `--transcript-file` 复用现有 pipeline。该入口不做节目订阅扫描、不做多集批处理、不做 ASR。真实入口 smoke `on-demand-99pi-karaoke-fixture-20260618` 已用 99% Invisible `Karaoke Videos` URL 跑到 `adapt`，解析到 150 段 normalized/script；该 smoke 使用 fixture local config，未调用 DeepSeek 或 TTS。5090D 真实 full-chain run `on-demand-99pi-karaoke-real-20260618` 已成功：同一 URL 经 chunked DeepSeek、`speaker_voices.mode: infer_once`、`sft_builtin_4role` TTS、assemble/publish 全链路完成；150 段、7 个 speaker 推断、最终 MP3 约 `1904.3s`，已拷回本机 ignored `workspace/runs/on-demand-99pi-karaoke-real-20260618/output/audio.mp3` 便于试听。
- MVP-1 YouTube 单链接 pre-DeepSeek 清洗和质量门槛第一版已完成：新增 `docs/plans/02-real-podcasts/10-YouTube单链接点播转换计划.md`，`babelecho episode convert --url ... --to-stage normalize` 对单个 YouTube 视频或 YouTube Podcasts 单集 URL 写出 `transcript/raw.vtt`、`transcript/cleaned.vtt`、`transcript/candidates.json`、`transcript/normalized.json` 和 `transcript/quality.json`；会合并碎 cue、解码 `&nbsp;` 等 HTML entities、清理 inline timing / `<c>` caption markup、移除 `>>` speaker arrows，并处理 rolling captions 的重复 overlap；会拒绝 playlist/channel/show 类 URL。YouTube captions 在 normalize 阶段关闭 speaker label 推断，避免 `AI:` / `API:` 等技术词误识别为主持人；其他来源 speaker label 解析不变。带 `t=` / `start=` 的 URL 会记录 `youtube_start_ms`，CLI 输出 `start offset:`，raw/cleaned 字幕保留整条原始字幕，`normalized.json` 裁剪到请求起点之后；YouTube 标题会通过独立 metadata 调用写入 source metadata，用户传入 `--title` 时用户标题优先。quality report 是 deterministic advisory，不调用 LLM，推荐值为 `safe_to_adapt` / `inspect_first` / `reject`，并记录 segment 数、字符长度、speaker 数、dirty markup、HTML entity 和重复度指标。DeepSeek chunked adapt prompt 已收紧：必须按输入 id 一对一返回，可清理字幕格式噪声和无意义口头填充，但要保留事实、数字、人名、问题、因果和有意义强调；chunk 少 id 时会重试，429/5xx/URL tunnel 临时错误也会重试。`babelecho check --checks script` 已新增中文脚本 QA，会在 TTS 前拦截 `>>`、`WEBVTT`、caption markup、HTML entity、时间轴残留和明显整段英文残留。当前本地 smoke config `workspace/config/local-deepseek-chunked-smoke.yaml` 已从 5 段一组调到 12 段一组，减少长视频请求数；该文件是 ignored local runtime config。真实本地 smoke `youtube-pre-deepseek-ai-engineering-20260618` 使用近期 LLM/agent 相关 YouTube 单集 URL 跑到 `normalize`：normalized 48 段、平均约 219 字符、speaker_count=0、quality=`safe_to_adapt`，未调用 DeepSeek/TTS；另测 `youtube-pre-deepseek-claude-second-brain-20260618` 和 `youtube-pre-deepseek-code-with-claude-20260618`，quality 均为 `safe_to_adapt`，dirty markup/entity 均为 0，无 speaker 误判，未进入 DeepSeek。用户 URL `https://www.youtube.com/watch?v=yAI8osNcMNw&t=1521s` 已重跑到 `normalize`、`adapt` 和 5090D TTS：标题为 `特朗普记者会谈美伊备忘录，感谢习近平普京｜新闻特写20260618`，start offset 1521s，normalized 223 段，quality=`safe_to_adapt`，DeepSeek adapt 生成 223 段 `script/zh.json`，脚本通过 `babelecho check --checks script`；新增 `speaker_voices.default_voice_role` 用于无 speaker 的 YouTube run 手动指定默认声线，该 run 使用 `male_a` 完整 TTS 成功，manifest 223 段全部 `male_a`，最终 MP3 为 `22050 Hz` mono，约 `2602.8s`，约 `40 MB`，已拷回本机 ignored `workspace/runs/youtube-user-yai8osncmnw-start1521-20260618/output/audio.mp3`。
- 近期 agent 主题 YouTube 端到端样本 `youtube-agent-skills-briefing-20260619` 已完成：标题 `AI Research Briefing 18062026: Auditing Agent Skills, Financial Reasoning, and Jailbreak Safety`，normalized 28 段，quality=`safe_to_adapt`，DeepSeek adapt 和 script QA 通过，5090D TTS 默认 `female_a`，最终 MP3 为 `22050 Hz` mono，约 `543.8s`，约 `8.3 MB`；用户试听反馈“听起来很不错”。
- 2026-06-19 三个标准播客 full-chain 样本（Practical AI、Radiolab、99% Invisible）用户试听反馈达到预期；试听暴露的 `[掌声]` / 片头音乐、版权/转写说明、`predictionguard。com` 和 `MP三` 已做第一轮清理：`normalize` 丢弃纯舞台提示和常见免责声明，DeepSeek adapt prompt 增加清理约束，`local_cli` TTS 写 `.txt` 前规范化域名点号和 `MP3` / `MP4` 读法。真实广告口播、制作名单、复杂 URL 仍按后续样本窄规则处理。
- 多角色压力样本 `full-99pi-anniversary-20260619` 已在 5090D 跑通：来源 `https://99percentinvisible.org/episode/641-99pi-anniversary-special-15-for-15/`，normalize 后 157 段、10 speaker、quality=`safe_to_adapt`，DeepSeek adapt 完成后曾被 script QA 误判制作名单英文人名过多；已修复 QA 规则，允许中文制作名单中夹带英文专名但仍拦截整段英文残留。最终 `synthesize -> assemble -> publish` 成功，manifest 157 段，使用 `female_a/female_b/male_a/male_b` 四个 voice role，MP3 为 `22050 Hz` mono、约 `2876.3s`、约 `46 MB`，已拷回本机 ignored `workspace/runs/full-99pi-anniversary-20260619/output/audio.mp3`。
- YouTube 单链接探索已先收口；官网 episode page 标准播客页面解析也完成第一轮真实 normalize 验证。iTunes/RSS 自用入口已补齐到单步 CLI 编排：`babelecho episode convert --url ... --select-index ...` 对 Apple Podcasts/iTunes URL 会经 iTunes Lookup -> RSS -> 人工选集，对直接 RSS feed URL 会直接列集并选中指定 index；两者都写出 `source.type=podcast_rss` source config，然后复用现有 normalize/adapt/TTS 后流程，不新增 iTunes/RSS 专用 pipeline，不做订阅扫描。真实 full-chain `itunes-url-practical-ai-zero-trust-full-20260619` 使用 Practical AI 的 Apple Podcasts URL，选中 `Zero Trust for AI Agents`，经 iTunes Lookup -> RSS -> `podcast_rss` -> normalize -> DeepSeek adapt -> 5090D TTS -> assemble -> publish 全链路成功；normalize 后 103 段、3 speaker、quality=`safe_to_adapt`、dirty markup=0，最终 MP3 约 `2176.4s`、约 `33 MB`，已拷回本机 ignored `workspace/runs/itunes-url-practical-ai-zero-trust-full-20260619/output/audio.mp3` 便于试听。单步 normalize smoke `rss-podnews-single-url-20260619` 使用 `https://podnews.net/rss` 第 1 集 `A new AMP member`，18 段、quality=`safe_to_adapt`；`apple-practical-ai-single-url-20260619` 使用 Practical AI Apple Podcasts URL 第 1 集，103 段、3 speaker、quality=`safe_to_adapt`。MVP-1 收口 full-chain `rss-podnews-single-url-full-20260619` 已在 5090D 跑通：18 段、quality=`safe_to_adapt`，DeepSeek adapt、TTS、assemble、publish 成功，MP3 约 `233.535s`、`22050 Hz` mono，已拷回本机 ignored `workspace/runs/rss-podnews-single-url-full-20260619/output/audio.mp3`。订阅扫描、多 episode 批处理、RSS/PodcastIndex 多 candidate 扩展仍后移到 Phase 3；ASR、声纹、ASR speaker diarization、Web UI 和 App 进入 Phase 2。
- MVP-1 Chunked DeepSeek Adapt 已完成：可在 local config 设置 `adapt.mode: chunked`、`chunk_max_segments`、`chunk_max_chars`，将多个完整 transcript segment 合并到一次 DeepSeek 请求；不切开单个 segment，返回必须保留原始 id，最终 `script/zh.json` 按原始 id 顺序合并，TTS 不依赖 chunk 返回顺序。chunk 结果会写入 run-local `script/adapt-chunks/` 便于排查。当前默认 `adapt.style` 是 `faithful_spoken`：尽量忠实保留原 transcript 的信息、顺序、语气、问题、数字、人名和观点组织，只做字幕噪声、舞台提示、转写说明、URL/缩写读法等轻清理；`polished_spoken` 保留为显式可选的宽松中文播客化改写风格。
- MVP-1 TTS 执行效率优化已完成：`local_cli` synthesis 现在写 `segments/tts-batch.json` 并一次启动 `tts-wrapper --batch-file ...`，wrapper 按本批次需要延迟加载 300M SFT 和/或 CosyVoice2 后循环生成所有 segment wav；旧的 `--text-file --output` 单段 wrapper 调用仍兼容。5090D `batch-wrapper-smoke-20260617` 两段真实 CosyVoice smoke 已通过。
- MVP-1 固定音色规则已选定并实现：运行默认使用 `tts.voice=sft_builtin_4role` 固定角色 profile。未启用 speaker voice 推断时，0/1 个 distinct speaker 且没有显式性别标签使用 `female_a`；单个 speaker 标签包含 `male` / `男` 时使用 `male_a`，包含 `female` / `女` 时使用 `female_a`；2 个及以上 distinct speaker 按首次出现顺序映射到 `female_a / male_a / female_b / male_b`。实际渲染时 `male_a` 调用 `CosyVoice2 cross_lingual + speed=1.1`、本地 calm prompt asset 和专用文本平稳化，其余三路调用 `CosyVoice-300M-SFT`。后续 300M 微调只影响未来可选 role/model，不自动改变当前默认。
- `male_a / 中文男` 清亮度实验是历史 SFT 男声校准：5090D run `male-a-brightness-experiment-20260618` 产出 A 当前中文男、B 更强 EQ、C 更强 EQ + 半音升调、D 基于 B 再加亮、E 最大亮度试探，用户当时选择 D；后续 `male_a` 已改走 CosyVoice2，试听文件仍保存在本机 ignored `workspace/runs/male-a-brightness-experiment-20260618/variants/`。
- 混合双模型男一实验已生成并推动最终实现：5090D run `four-role-hybrid-cosyvoice2-male-a-20260618` 使用 `female_a/female_b/male_b` 继续走 `CosyVoice-300M-SFT`，第二段 `male_a` 单独走 `CosyVoice2 cross_lingual + cross_lingual_prompt.wav + speed=1.0`，再统一到 `22050 Hz` mono 后 assemble；MP3 已拷回本机 ignored `workspace/runs/four-role-hybrid-cosyvoice2-male-a-20260618/output/audio.mp3`。
- CosyVoice2 男声自然文本语速实验已生成并作为后续固化依据：5090D run `cosyvoice2-male-natural-speed-preview-20260618` 使用全中文播客句子，分别生成 `cross_lingual + speed=1.0` 和 `speed=1.1`，用户认可 `male-natural-speed-1_1.mp3`，产物已拷回本机 ignored `workspace/runs/cosyvoice2-male-natural-speed-preview-20260618/output/`。
- 混合四角色 speed=1.1 男一实验已固化为默认渲染规则：5090D run `four-role-hybrid-cosyvoice2-male-a-speed11-20260618` 按 `female_a / male_a / female_b / male_b` 顺序生成，只有 `male_a` 使用 `CosyVoice2 cross_lingual + speed=1.1`，其余三段继续 `CosyVoice-300M-SFT`；MP3 已拷回本机 ignored `workspace/runs/four-role-hybrid-cosyvoice2-male-a-speed11-20260618/output/audio.mp3`。
- MVP-1 speaker voice 推断已完成第一版：可在 local config 启用 `speaker_voices.mode: infer_once`，`run`/`synthesize` 会在 TTS 前每集最多调用一次 LLM，根据 speaker 名称和少量上下文推断 `male/female/unknown`，写入 ignored run-local `script/speaker-voices.json`，再由代码稳定映射到 `female_a/male_a/female_b/male_b`。`confidence` 只用于人工复核提示，不阻塞；`unknown` 也会自动获得具体 voice role。若推断失败或文件无效，回退到旧的首次出现规则。
- `sft_builtin_4role` 仍是四个固定 role：`female_a -> 300M SFT 中文女`，`male_a -> CosyVoice2 cross_lingual speed 1.1 + calm prompt if present + text smoothing`，`female_b -> 300M SFT 英文女`，`male_b -> 300M SFT 英文男`；同名 speaker 复用同一角色，超过 4 个 speaker 循环复用。不做原主播 voice clone。
- 本机测试计数以当前 `pytest -q` 为准；5090D 历史 wrapper smoke 已验证四角色真实 SFT wav 输出均为 `22050 Hz` mono；最终混合 `male_a` 代码路径也已验证：`four-role-hybrid-code-preview-20260618-1736` 使用正式 `synthesize -> assemble`，manifest/batch roles 均为 `female_a / male_a / female_b / male_b`，MP3 为 `22050 Hz` mono、约 `17.7s`，已拷回本机 ignored `workspace/runs/four-role-hybrid-code-preview-20260618-1736/output/audio.mp3`。计划记录见 `docs/plans/02-real-podcasts/03-sft-builtin-4role-voice-profile.md`。
- MVP-0 收口已完成：speaker label 解析/清洗、NASA 样本 `normalize -> adapt -> synthesize -> assemble -> publish` 回归、docs 标记完成。
- `docs/roadmap.md` 已记录从 MVP-0 Acceptance、MVP-0.5 Self-use 到 MVP-1 Single URL Self-use、Phase 2 ASR + Product Surface、Phase 3 Automation 的产品路线；MVP-1 已完成，Phase 2 架构计划见 `docs/Phase2双轨后端与静态前端架构.md`。前端只读 artifact 契约与设计 brief 见 `docs/前端Artifact契约与只读界面说明.md`；当前 publish 阶段会同步稳定 `workspace/published/feed.xml`、episode MP3/metadata/transcript，并额外生成前端入口 `workspace/published/index.json` 与 `workspace/published/episodes/<run-id>/artifact.json`。
- `frontend/` 只读前端已加入主分支（`ead73dc feat: add read-only frontend for published artifacts`）：纯静态 HTML/CSS/原生 JS，无构建依赖；运行 `python3 frontend/serve.py 8137` 后打开 `http://127.0.0.1:8137/frontend/`。它只读 `workspace/published/`，不提交 URL、不触发转换、不读 config/sources/runs 内部文件。前端后续工作可交给独立 agent，当前主线继续后端 Route B。
- 当前阶段采用临时混合验证：LLM adaptation 使用 DeepSeek API，TTS 仍在 5090D 本地运行；最终方向仍是 local-first。
- 长期路线已记录可选 LLM 清洗 fallback：先程序抽取/程序清洗并跑 quality gate；只有 `inspect_first` 且属于可修复噪声时，才考虑独立 LLM cleaner 清洗，清洗后必须再次通过 quality gate 才能进入 DeepSeek adapt。它不是当前默认链路，也不应破坏 YouTube/RSS/iTunes/Article 已验证路径。
- Route B audio-first 已开始独立实现：`babelecho audio convert --audio-file ... --to-stage ingest_audio` 可做本地音频文件 ingest，`--audio-url ... --to-stage ingest_audio` 可做显式公网音频 URL ingest；CLI 输入为 `--audio-file | --audio-url` 二选一。URL 入口只属于 audio-first，不是 Route A 的静默 ASR fallback；artifact 只记录 `source_host` / `source_path`，不写 URL query/fragment。当前会写 `source.json`、`audio/input.<ext>`、`audio/metadata.json` 和 `run.json`；`--to-stage asr` 已接 fixture/local_cli ASR provider，可写 `asr/raw.json` contract；`--to-stage diarize` 已接 fixture/none/local_cli diarization provider，可写 `asr/diarization.json` contract；`--to-stage normalize` 已能把 ASR + diarization artifact 桥接成现有后流程可读的 `transcript/normalized.json` 和 audio-first `transcript/quality.json`；`--to-stage publish` 已能用 fixture ASR/diarization/LLM/TTS 跑完整 audio-first artifact 链路，并在 publish artifact 写 `route=audio_first` 和 ASR 摘要。5090D `audio-url-ingest-practicalai-ai-index-20260620` 已用 Practical AI 公网 MP3 跑通 `--audio-url -> ingest_audio`：`source_type=audio_url`、`provider=remote_url`、MP3 约 `2832.4s`、`44100 Hz` mono、约 `45.4 MB`；5090D 受控 URL 回归 `audio-url-normalize-practicalai-zero-trust-8min-20260620` 已用远端 localhost HTTP 临时服务暴露已有 Practical AI 8 分钟真实 wav，跑通 `--audio-url -> asr -> diarize -> normalize`：query 未泄漏，ASR 123 段，diarization 23 turns，normalized 32 段，quality=`safe_to_adapt`，metrics 与同样本本地文件路线一致；5090D 短 URL full-chain `audio-url-fullchain-bbc-6min-screen-time-20260620` 已用 BBC `6 Minute English` 直链跑通 `--audio-url -> ASR -> diarize -> normalize -> DeepSeek -> TTS -> publish`，40 段，quality=`safe_to_adapt`，diarization 4 speakers，四个固定 voice role 均有使用，中文 MP3 为 `22050 Hz` mono、约 `354.8s`、约 `5.7 MB`，已拷回本机 ignored `workspace/runs/audio-url-fullchain-bbc-6min-screen-time-20260620/output/audio.mp3`。真实 ASR 已完成第一步：5090D 上确认本地 `openai-whisper` + CUDA 可跑，英文 `jfk.flac` smoke 输出正确；代码已新增 `asr.provider=local_cli` 和 `tools/openai_whisper_asr_wrapper.py`，核心只调用 wrapper 并校验 canonical `asr/raw.json`；5090D run `audio-asr-jfk-localcli-20260619` 已用 `babelecho audio convert` 跑到 `asr` 和 `normalize`，`provider=openai_whisper`、`model=tiny.en`、`quality.recommendation=safe_to_adapt`。真实 diarization 已完成第一轮烟测：5090D 上独立克隆环境 `/home/th5090d/miniforge3/envs/babelecho-diarization` 已安装 `pyannote.audio 4.0.4`，不污染 `/home/th5090d/miniforge3/envs/babelecho-tts`；`audio-diarization-practicalai-zero-trust-8min-qualitygate-20260619` 使用 Practical AI 8 分钟样本、OpenAI Whisper `small.en` + pyannote Community-1 跑到 `normalize`，识别 `speaker_count=2`、`turn_count=23`、`normalized_segment_count=32`。`asr_segment_crosses_speaker_turns` 已从硬阻断改为量化 advisory warning：quality metrics 会写 `cross_speaker_segment_count/ratio`、`ambiguous_speaker_segment_count/ratio` 和 primary speaker overlap；只有 speaker assignment 模糊数量/比例达到阈值时才加 `ambiguous_speaker_assignments` 并 `inspect_first`。该真实样本已用新代码在 5090D 实际复跑为 `safe_to_adapt`，metrics 为 9/123 crossing、2/123 ambiguous、`min_primary_speaker_overlap_ratio=0.537`、`avg_primary_speaker_overlap_ratio=0.781`。与该集已有官方 speaker VTT 粗略重叠对齐显示 `speaker_1=Daniel`、`speaker_2=Chris`，覆盖片段 overlap accuracy 约 `99.59%`。同一 run 已继续跑通 `audio-first -> DeepSeek -> TTS -> publish`：script/manifest 均 32 段，voice roles 为 `female_a/male_a`，MP3 为 `22050 Hz` mono、约 `370.55s`、约 `5.9 MB`，已拷回本机 ignored `workspace/runs/audio-diarization-practicalai-zero-trust-8min-qualitygate-20260619/output/audio.mp3`；用户试听反馈“整体可以接受”。ASR 横评第一轮同一样本比较 `small.en` 与 `medium.en`：`small.en` cached normalize 约 `23.1s`、粗略 WER `0.165`；`medium.en` 首次下载后 cached normalize 约 `28.7s`、粗略 WER `0.178`。`medium.en` 抓到 1 次 `Claude Code`，但也出现多次 `Clod`，且把 `Whitenack` 误成 `Witek`；因此暂不把默认 ASR 从 `small.en` 升到 `medium.en`。当前 audio-first URL 主链已具备端到端中文 MP3 产出能力；BBC 样本曾暴露动态广告/片尾推广会进入 ASR 和中文稿，已在下一条记录补第一版自动边界清理；不进入 voice clone 或 TTS conditioning。
- Route B audio-first 边界内容自动清理已新增：只处理开头/结尾边界窗口，高置信广告/推广自动删除，低置信只写 warning，不做强制人工确认。5090D 重跑 `audio-url-fullchain-bbc-6min-screen-time-20260620` 的 `normalize -> publish` 后，normalized/script/manifest 为 36 段，自动删除 4 个边界内容段，quality=`safe_to_adapt`，更新后中文 MP3 为 `22050 Hz` mono、约 `339.4s`、约 `5.4 MB`；首段从“大家好，这里是六分钟英语”开始，尾段到“再见”结束，更新产物已拷回本机 ignored `workspace/runs/audio-url-fullchain-bbc-6min-screen-time-20260620/output/audio.mp3`。
- Route B diarization 输入规范化已新增：`local_cli` diarization 对非 WAV 输入会先用 ffmpeg 生成 run-local `audio/diarization-input.wav`（mono、16k、PCM），再传给 pyannote wrapper；原始 `audio/input.*` 仍保留给 ASR 和 source artifact。Podnews `The risk takers in podcasting` MP3 根因验证显示：原始 MP3 带封面图视频流、双声道和非零 start time，pyannote 直接读取会因 10 秒 chunk 样本数不匹配失败；同文件转成标准 WAV 后 wrapper 可正常输出 diarization。5090D 回归 `audio-url-regression-podnews-risk-takers-20260620` 已从 `diarize -> publish` 跑通：quality=`safe_to_adapt`，10 段、2 speakers，自动删除 3 个边界段，1 个 possible boundary warning 保留，最终 MP3 为 `22050 Hz` mono、约 `147.10s`、约 `2.35 MB`，ffmpeg 解码通过，产物已拷回本机 ignored `workspace/runs/audio-url-regression-podnews-risk-takers-20260620/output/audio.mp3`。后续 BBC 类样本已用于质量门和片尾清理回归。
- Route B diarization 质量门校准已完成两轮：speaker overlap 先按 speaker 聚合，避免同一 speaker 被拆成多个 turn 后误算为 cross/ambiguous；`ambiguous_speaker_assignments` 现在要求 ambiguous 数量和比例同时达标，少量低占比 ambiguous 仅保留 advisory warning；`missing_diarization_overlap` 现在记录 count/ratio/duration/boundary metrics，只有正文缺失、缺失过多或边界缺失过长才 `inspect_first`，尾部短 farewell 缺口只保留 advisory。5090D 回归：BBC Advertisers 从 `inspect_first` 变为 `safe_to_adapt` 并已跑通 `adapt -> publish`，最终 MP3 为 `22050 Hz` mono、约 `343.01s`、约 `5.49 MB`；BBC Hantavirus 从 `inspect_first` 变为 `safe_to_adapt`，49 段、3 speakers、`missing_diarization_overlap_segment_count=1`、尾部缺失 1000ms，并已跑通 `normalize -> publish`，最终 MP3 为 `22050 Hz` mono、约 `365.27s`、约 `5.84 MB`，ffmpeg 解码通过，产物已拷回本机 ignored `workspace/runs/audio-url-regression-bbc-news-hantavirus-20260620/output/audio.mp3`；BBC Screen Time 和 Podnews 仍为 `safe_to_adapt`。
- Route B newsletter/podcast promo 片尾清理已补回归：`audio-url-regression-bbc-6min-poetry-20260620` 在 `normalize` 阶段保持 `inspect_first`，原因是开头 ASR/动态内容噪声和 `ambiguous_speaker_assignments`，未强行进入 DeepSeek/TTS；`audio-url-regression-bbc-news-us-iran-20260620` 初始为 `safe_to_adapt` 但尾部残留 newsletter/podcast promo，已扩展高置信边界规则并在 5090D 跑通 `normalize -> publish`：quality=`safe_to_adapt`，warnings 只剩 `asr_segment_crosses_speaker_turns` 和 `dropped_boundary_content_segments`，normalized/script/manifest 均 50 段，自动删除 6 个边界内容段，`possible_boundary_content_segment_count=0`，voice roles 为 `female_a/male_a`，最终 MP3 为 `22050 Hz` mono、约 `396.51s`、约 `6.05 MB`，已拷回本机 ignored `workspace/runs/audio-url-regression-bbc-news-us-iran-20260620/output/audio.mp3`。
- Route B 非 BBC direct-audio 短样本回归已补：`audio-url-regression-npr-newsnow-20260620` 使用 NPR News Now `NPR News: 06-20-2026 4AM EDT` RSS enclosure，输入 MP3 约 `280.06s`、`44100 Hz` stereo，URL artifact 只保留 `source_host=prfx.byspotify.com` 和 `source_path`，不写 query/fragment。5090D 跑通 `--audio-url -> ASR -> diarize -> normalize -> DeepSeek -> TTS -> publish`：quality=`safe_to_adapt`，24 段、4 speakers，warnings 只有 `asr_segment_crosses_speaker_turns`，无 dropped/possible boundary content，manifest 使用 `female_a/female_b/male_a/male_b` 四个 voice role；最终 MP3 为 `22050 Hz` mono、约 `283.95s`、约 `4.54 MB`，ffmpeg 解码通过，published `transcript.zh.json` 已带中文 MP3 时间轴字段，产物已拷回本机 ignored `workspace/runs/audio-url-regression-npr-newsnow-20260620/output/audio.mp3`。下一步转回 private speaker alias 人工确认 contract；仍不进入 voice clone，也不把 embedding 喂给 TTS。
- Route B ASR 专名纠错第一版已实现：audio-first `asr.replacements` 可在 `fixture` / `local_cli` ASR 输出归一化后、写入 `asr/raw.json` 前做显式短语 `from -> to` 替换；默认不开启，不做自动词典或宽泛 `cloud` 替换。命中摘要写入 `metadata.asr_replacements`。本机已通过 `tests/test_asr.py`、`tests/test_asr.py tests/test_audio_pipeline.py tests/test_audio_normalize.py` 和全量 `pytest -q`。5090D 临时 worktree 已用 Practical AI 8 分钟样本验证：`small.en` ASR 仍输出 123 段，3 条窄规则命中 4 次，修正 `Daniel White Knack`、`cloud code`、`cloud co-worker`，同时保留未确认的普通 `cloud security`。5090D 最新 `main` 真实后流程 smoke `audio-diarization-practicalai-replacements-normalize-20260620` 已跑到 `normalize` 和 `adapt`：quality=`safe_to_adapt`，normalized 32 段，DeepSeek 脚本 32 段，script QA 通过，首段脚本保留 `Daniel Whitenack`。
- Route B speaker profile / voice profile contract 最新状态：`diarize` 阶段会从 canonical diarization turns 生成 `asr/speaker-profiles.json`，默认包含 turn 数、总时长、首尾时间、`sample_count=0`、`sample_duration_ms=0`、`profile_kind=diarization_stats`、`embedding_status=not_computed` 和 `embedding_artifact=null`，不做身份识别，不写 voiceprint embedding；audio-first-only `voice_profile.provider=none/fixture/local_cli` 已接入 `babelecho audio convert --to-stage diarize`。`local_cli` 会调用外部 wrapper，把 wrapper 写出的 run-local `asr/voice-profiles/summary.json` 摘要合并回 `speaker-profiles.json`，允许 `embedding_status=computed`；`tools/speaker_embedding_wrapper.py` 已实现 SpeechBrain ECAPA 路径，按 speaker 选择最长 diarization windows，写 run-local `asr/voice-profiles/*.json` 和 `summary.json`。publish 阶段仍只暴露摘要：`artifact.json.asr.speaker_profiles` 不暴露 `embedding_artifact`，也不会复制 `asr/voice-profiles/*.json` 到 `workspace/published/`。5090D 独立 `babelecho-voice-profile` model probe 已选中 `speechbrain/spkrec-ecapa-voxceleb`：pyannote embedding 被 gated repo 403 阻断，SpeechBrain ECAPA 在 Practical AI 8 分钟样本上成功产出 192 维 embedding，speaker 内 cosine 均值约 `0.929/0.849`，speaker 间约 `0.457`，首次 probe 总耗时约 `36.9s`，峰值 RSS 约 `2.4 GB`。5090D 真实 wrapper smoke `audio-voice-profile-speechbrain-smoke-20260620` 已通过：`voice_profile.provider=local_cli` 后 `speaker_1/speaker_2` 均为 `embedding_status=computed`，run-local artifact 均为 192 维；同一 run 的 publish-stage privacy smoke 也通过，公开 artifact 不含 `embedding_artifact`，也未复制 `asr/voice-profiles/`。
- Route B speaker embedding consistency 最新状态：新增 `babelecho speaker-profiles compare --run-dir ... --output-json ...`，可读取多个 run 的私有 `asr/voice-profiles/*.json`，输出 cross-run cosine 相似度报告；本机 focused tests 和全量 `pytest -q` 通过，5090D `tests/test_speaker_similarity.py` 通过。5090D 已用真实 ASR/diarization + SpeechBrain 跑 Practical AI 两个 8 分钟样本：`audio-voice-profile-real-practicalai-zero-trust-8min-20260620` 产出 2 个 192 维 embedding，`audio-voice-profile-real-practicalai-ai-index-8min-20260620` 产出 3 个 192 维 embedding；报告 `workspace/runs/speaker-similarity-practicalai-real-two-episodes-20260620.json` 有 6 个 cross-run pair，`likely_same=2`、`different=4`，最高两对为 `zero-trust speaker_1 -> ai-index speaker_2 cosine=0.959153` 和 `zero-trust speaker_2 -> ai-index speaker_3 cosine=0.881848`。注意：`audio-voice-profile-speechbrain-smoke-20260620` 是 fixture ASR/diarization + 真实 wrapper 的读写/隐私 smoke，不作为跨集结论；JFK 样本窗口不足，embedding 为 `unavailable`。下一步优先用更多真实同节目样本校准阈值和误配风险，再决定是否生成私有 speaker alias map；不要进入 voice clone，也不要把 embedding 喂给 TTS。
- Route B private speaker alias 最新状态：新增 `babelecho speaker-profiles alias --similarity-report ... --output-json ...`，从相似度报告生成私有候选 alias map，不读取 embedding 向量，不输出 `embedding_artifact`。默认阈值为 `same_threshold=0.85`、`min_sample_duration_ms=60000`、`min_members=2`，用于过滤短片头/旁白片段并避免同一 run 多 speaker 冲突。5090D 已追加 3 集 Practical AI 公开 RSS 音频前 8 分钟样本（`mcp-kubernetes`、`hermes-agent`、`model-wars`），五集真实 ASR/diarization/SpeechBrain 报告 `workspace/runs/speaker-similarity-practicalai-real-five-episodes-20260620.json` 包含 14 个 computed speaker、78 个 cross-run pair、`likely_same=19`、`different=59`。alias map `workspace/runs/speaker-aliases-practicalai-real-five-episodes-20260620.json` 生成 2 个候选 alias：`speaker_alias_001` 有 5 个成员，min/avg/max cosine `0.850890/0.909038/0.959153`；`speaker_alias_002` 有 3 个成员，min/avg/max `0.881848/0.898437/0.919010`；4 个约 32 秒的短样本 speaker 被跳过。新增 `babelecho speaker-profiles review --alias-map ... --output-json ... [--existing-review ...]`，把候选 alias map 转成私有审核 contract：默认 `candidate`，可编辑为 `confirmed/rejected/split/ignored`，并可保留既有人工决定；review 文件不被 TTS 消费，不做身份识别，不发布 embedding，也不把 embedding 喂给 TTS。5090D 已用五集 Practical AI alias map 生成 `workspace/runs/speaker-alias-review-practicalai-real-five-episodes-20260620.json`：2 个 alias，`candidate=2`，且不含 `embedding_artifact` 或 `voice-profiles`。新增 `babelecho speaker-profiles voice-roles --review ... --output-json ... [--existing-map ...]`，只把 `confirmed` alias 映射到固定中文 voice role，并可保留既有 `alias_id -> voice_role`；该 map 仍不被 TTS 消费、不发布、不做 voice clone。5090D 已用模拟 confirmed review smoke：`speaker_alias_001 -> female_a`、`speaker_alias_002` 因 `rejected` 跳过，且 `--existing-map` 可保留 `speaker_alias_001 -> male_b`。新增 `babelecho speaker-profiles apply-voice-roles --workspace ... --run-id ... --voice-role-map ... [--overwrite]`，显式 opt-in 把 private map 应用到单次 run 的 `script/speaker-voices.json`；默认不覆盖既有文件。新增配置开关 `speaker_voices.mode: apply_voice_role_map` + `speaker_voices.voice_role_map`，可在 `run`、`synthesize` 和 audio-first `audio convert` 进入 TTS 前显式应用 private map；默认不启用。5090D CLI smoke 已应用到 `audio-voice-profile-real-practicalai-zero-trust-8min-20260620`：写出 `speaker_1 -> female_a`，loader 返回同一映射，重复执行默认 `reused`。5090D 配置开关 smoke 已应用到 `audio-voice-profile-real-practicalai-ai-index-8min-20260620`：写出 `speaker_2 -> female_a`，不含 `embedding_artifact` 或 `voice-profiles`，重复执行默认 `reused`。
- 下一步计划见 `docs/plans/03-audio-first-asr/03-real-voice-profile-provider.md`：private speaker alias 到稳定中文 voice role 的手动确认链路已走通并显式 opt-in 接入 TTS；后续不要默认启用，不要进入原主播 voice clone，也不要把 embedding 用于 TTS。
- Python 环境必须使用项目内 .conda/babelecho-dev，不要使用 base env。
- 真实 runtime config、workspace/runs、生成音频、模型缓存、本地配置和 API key 不要提交。
- 单 URL 自用入口操作手册见 `docs/单URL自用运行手册.md`：先按 URL 类型选择 YouTube / episode page / Apple Podcasts / direct RSS 入口，先跑到 `normalize` 读 `quality.json`，只有 `safe_to_adapt` 才进入 DeepSeek/TTS。
- 5090D 真实验证的详细流程、命令模板、DeepSeek 前置质量门禁和代表样本记录见 `docs/5090D远程测试流程.md`。
```

## 当前执行位置

当前已完成：

```text
docs/plans/01-backend-mvp0/01-local-llm-adapt.md
docs/plans/01-backend-mvp0/03-local-tts.md
MVP-0 Acceptance closeout
MVP-0.5 babelecho run command
MVP-0.5 babelecho check command
MVP-0.5 manual transcript input and run.json status
MVP-0.5 script preview and stable published feed
MVP-0.5 local terminology/pronunciation overrides
MVP-0.5 self-use acceptance
```

进度：

- 01.01 已从“本地 LLM vLLM 接入”改为“DeepSeek LLM Adapt 基线接入”。
- 5090D 上已确认：
  - `git status --short --branch` 输出 `## main...origin/main`
  - `git --no-pager log --oneline -3` 输出：
    - `815c296 docs: mark mvp0 acceptance complete`
    - `9444363 fix: parse transcript speaker labels`
    - `b356114 docs: refresh resume prompt for roadmap`
  - `curl -sS http://127.0.0.1:8000/v1/models` 返回 `{"detail":"Not Found"}`，说明 8000 端口不是当前需要的 OpenAI-compatible LLM endpoint。
- 已决策：不继续优先部署本地 LLM；先使用 DeepSeek API 做 LLM adaptation，5090D 后续专注本地 TTS。
- 01.01 已在 5090D 上完成验收。
- 01.03 已在 5090D 上完成本地 TTS 验收。
- 真实 NASA transcript 样本已在 5090D 上跑通 `normalize -> adapt -> synthesize -> assemble -> publish`。
- 产品路线已整理到 `docs/roadmap.md`，MVP-0.5 已完成，下一步应进入 MVP-1 Real Podcasts。

MacBook 已实现：

- `src/babelecho/llm.py` 增加 `openai_compatible` provider。
- 支持 `api_key_file`、`api_key_env`、Authorization header、可选 `extra_body`。
- `tests/test_llm.py` 覆盖 DeepSeek provider 行为。
- `src/babelecho/transcript.py` 解析 speaker label，把 `Host:`、`Nick Hague:`、`Host (Dane Turner):` 等标签写入 `segment["speaker"]`，并从 `segment["text"]` 中移除。
- `tests/test_transcript.py` 覆盖段首 label、段内多轮 speaker turn 和普通冒号不误判。
- `src/babelecho/cli.py` 增加 `babelecho run`，支持完整 pipeline 编排和 `--from-stage` 续跑。
- `src/babelecho/cli.py` 支持 `babelecho run --to-stage adapt`，可在 TTS 前停下预览中文脚本。
- `src/babelecho/cli.py` 支持 `babelecho run --transcript-file ... --title ...`，自用时可跳过 source YAML。
- `src/babelecho/ingest.py` 支持 `source.type=transcript_file`。
- `src/babelecho/status.py` 写入 `workspace/runs/<run-id>/run.json`，记录 run 输入、`from_stage`、`to_stage`、每个 stage 状态、失败阶段、错误和输出路径。
- `src/babelecho/checks.py` 增加基础质量检查，`babelecho check` 可检查 script、segments、output。
- `src/babelecho/script.py` 增加 `babelecho script`，输出 `script/zh.json` 路径、段落编号、文本和 `--from-stage synthesize` 续跑提示。
- `src/babelecho/publish.py` 同步 run-local publish artifacts 到稳定目录 `workspace/published/`。
- `src/babelecho/overrides.py` 增加本地精确替换逻辑，读取 `overrides.path` 指向的 YAML 词表并改写 `script/zh.json`。
- `src/babelecho/cli.py` 增加 `babelecho overrides`，`babelecho run` 在 `synthesize` 前自动应用 configured overrides。
- `babelecho run` 在 `adapt`、`synthesize`、`assemble` 后自动检查关键产物。
- `babelecho run` 输出包含 `stable feed: workspace/published/feed.xml`。
- `tests/test_end_to_end_fixture.py` 覆盖 `run` 的 fixture 全链路和从 `synthesize` 恢复执行。
- `tests/test_end_to_end_fixture.py` 覆盖 `run --to-stage adapt` 停在中文脚本阶段，不生成音频。
- `tests/test_end_to_end_fixture.py` 覆盖 `--transcript-file` 自用入口和 ingest 失败时 `run.json` 的失败状态。
- `tests/test_end_to_end_fixture.py` 覆盖 `babelecho script` 输出和 stable publish feed。
- `tests/test_publish.py` 覆盖 run-local 与 stable publish artifacts 同时生成。
- `tests/test_checks.py` 覆盖空中文稿、超长段落、缺失 wav、缺失 MP3 和 ffprobe 元数据。
- `tests/test_overrides.py` 覆盖 override 词表改写、未配置跳过和 CLI 命令。
- `workspace/config/local.example.yaml` 已改成 DeepSeek LLM + 本地 TTS 示例。
- `workspace/config/deepseek.env.example` 已添加，真实 `workspace/config/deepseek.env` 被 ignore。
- `workspace/config/overrides.example.yaml` 已添加示例词表，真实 `workspace/config/overrides.yaml` 被 ignore。
- 本机全量测试：`140 passed`（2026-06-18，script QA 和 chunk smoke 调整后）。

5090D 已完成 DeepSeek API 和 `adapt` 验证，也完成本地 TTS wrapper 验证。自制长样本、NASA 真实 podcast transcript 和 MVP-0.5 自用回归都已生成可听 MP3。MVP-0 acceptance 与 MVP-0.5 Self-use 已完成。下一步进入 MVP-1 Real Podcasts。不要同时接 ASR、voice clone、后台服务或 App。

MVP-0.5 `babelecho run` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `run-command-smoke` 使用 fixture config 跑通 `babelecho run`。
- 生成 `transcript/normalized.json`、`script/zh.json`、`segments/manifest.json`、`output/audio.mp3`、`publish/feed.xml` 和 episode MP3。
- script/manifest 均为 1 段。

MVP-0.5 `babelecho check` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `check-command-smoke` 使用 fixture config 跑通 `babelecho run` 自动检查。
- 独立 `babelecho check` 输出 `script_segments=1`、`audio_segments=1`、`output_sample_rate=16000`、`output_channels=1`、`output_duration_seconds=0.504`。

MVP-0.5 `--transcript-file` 和 `run.json` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `manual-input-status-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Manual Input Smoke"` 跑通 fixture pipeline。
- `run.json` 输出 `status=succeeded`、`from_stage=ingest`、`input_transcript_file=tests/fixtures/sample.vtt`、6 个 stage 全部 `succeeded`、`audio=output/audio.mp3`、`feed=publish/feed.xml`。

MVP-0.5 `babelecho script` 和稳定 `workspace/published/feed.xml` 已在 5090D 上通过验证：

- 远端全量测试：`34 passed`。
- `preview-stable-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Preview Stable Smoke"` 跑通 fixture pipeline。
- stdout 包含 `stable feed: workspace/published/feed.xml`。
- `babelecho script --workspace workspace --run-id preview-stable-smoke` 输出 `script/edit` 路径、`--from-stage synthesize` 提示和中文稿。
- `workspace/published/feed.xml` 和 `workspace/published/episodes/preview-stable-smoke/audio.mp3` 存在且非空；`run.json` 输出 `stable_feed=published/feed.xml`。

MVP-0.5 本地 override 已在 5090D 上通过验证：

- 远端全量测试：`37 passed`。
- `overrides-smoke` 使用临时 workspace、fixture LLM/TTS/publish 和临时 override YAML 跑通 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Overrides Smoke"`。
- stdout 包含 `overrides: 2 replacements from 2 rules`。
- `script_text` 和 `manifest_text` 都为 `中文口播：欢迎 to the 样例节目.`。
- `run.json` 输出 `status=succeeded`，稳定 `published/feed.xml` 存在。

MVP-0.5 self-use acceptance 已在 5090D 上完成：

- 真实 run-id：`mvp05-selfuse-nasa`。
- 回归流程：真实 NASA Crew-9 transcript -> `ingest` -> `normalize` -> `adapt(DeepSeek)` -> `babelecho script` 预览 -> override -> `run --from-stage synthesize` -> 本地 TTS -> `assemble` -> `publish`。
- script/manifest 均为 9 段；override 命中 10 次。
- 最终 MP3 为 `24000 Hz`、mono、约 `355.5s`。
- `run.json` 输出 `status=succeeded`、`from_stage=synthesize`；`workspace/published/feed.xml` 已生成。
- 产物已从 5090D 拷回本机 ignored 路径：`workspace/runs/mvp05-selfuse-nasa/output/audio.mp3`、`script/zh.json`、`segments/manifest.json`、`publish/feed.xml`。

## 按需打开的文件

新 session 不需要一开始按顺序读完下面所有文件。先读本文件即可；如果任务涉及对应方向，再打开相关文件：

1. `HANDOFF.md`
2. `docs/roadmap.md`
3. `docs/plans/README.md`
4. `docs/5090D远程测试流程.md`
5. `docs/plans/01-backend-mvp0/01-local-llm-adapt.md`
6. `docs/plans/01-backend-mvp0/03-local-tts.md`
7. `src/babelecho/transcript.py`
8. `tests/test_transcript.py`
9. `src/babelecho/llm.py`
10. `tests/test_llm.py`
11. `tools/cosyvoice_tts_wrapper.py`
12. `src/babelecho/cli.py`
13. `src/babelecho/status.py`
14. `src/babelecho/overrides.py`
15. `tests/test_end_to_end_fixture.py`
16. `tests/test_overrides.py`
17. `workspace/config/local.example.yaml`
18. `workspace/config/overrides.example.yaml`
19. `docs/Phase2双轨后端与静态前端架构.md`
20. `docs/前端Artifact契约与只读界面说明.md`
21. `docs/plans/03-audio-first-asr/01-local-audio-asr-diarization.md`

## 当前项目事实

- 仓库：`/Users/firegnu/Developer/personal_projs/BabelEcho`，远端 5090D 路径是 `/home/th5090d/Develop/personal_project/BabelEcho`。
- 当前协作方式：本机改代码并 push，必要时通过 `ssh my-5090d-host` 在 5090D 上远程执行验证命令；不在 5090D 上安装或运行 Codex agent。
- MVP-0 acceptance 收口基线提交是 `815c296 docs: mark mvp0 acceptance complete`；当前 `origin/main` 可能包含后续 handoff 文档刷新提交。新 session 以 `git log --oneline -3` 为准；如果需要在 5090D 上跑验证，先在远端 `git pull`。
- 已有 CLI 阶段：
  - `run`
  - `check`
  - `ingest`
  - `normalize`
  - `adapt`
  - `overrides`
  - `speaker-voices`
  - `synthesize`
  - `assemble`
  - `publish`
- `babelecho run` 支持 `--to-stage` 停在指定阶段，也支持 `--from-stage` 从指定阶段继续。
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
- CosyVoice2 模型目录是 `/home/th5090d/Develop/ai_tools/CosyVoice/pretrained_models/CosyVoice2-0.5B`；MVP-1 当前 `male_a` 渲染默认要求它可用。
- 远端 runtime launcher 是 `/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper`。
- `workspace/config/local-cosyvoice.yaml` 是 ignored runtime config，TTS command 指向上述 launcher。
- `babelecho synthesize --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-cosyvoice.yaml` 已成功生成真实 wav。
- `babelecho assemble --workspace workspace --run-id fixture-smoke` 已成功把真实 TTS wav 拼成 MP3。
- `nasa-crew9-real-smoke` 已在 5090D 上完成 acceptance 回归：
  - `normalize` 输出 9 段，speaker label 写入 `speaker`，`segment["text"]` 无 `Host:` / `Nick Hague:` 标签残留。
  - `adapt` 输出 9 段，speaker 继续保留，中文脚本无 `主持人：` / `尼克·黑格：` 朗读式标签残留。
  - `synthesize -> assemble` 重新生成真实 MP3，`ffprobe` 为 `mp3`、`24000 Hz`、mono、约 `361.1s`。
  - `publish` 生成 `publish/feed.xml`、episode MP3、`transcript.en.json`、`transcript.zh.json`、`metadata.json`。

## 下一个目标

MVP-0 acceptance 和 MVP-0.5 Self-use 已完成：

```text
真实英文 transcript -> normalized.json -> DeepSeek 中文口播稿 -> 5090D 混合本地 TTS -> wav segments -> MP3 -> publish/feed.xml
```

下一步按 Phase 2 双轨架构推进：

1. 先按 `docs/Phase2双轨后端与静态前端架构.md` 固化 artifact manifest 和 Route A 来源矩阵回归。
2. Phase 2 不应破坏 MVP-1 单 URL CLI；任何来源入口改动先跑来源矩阵回归。
3. 再做独立 audio-first 路线：本地音频文件或显式音频 URL -> ASR -> speaker diarization / 声纹 profile -> `normalized.json` -> 现有 adapt/TTS/publish 后流程。
4. 前端和 App 第一版只读消费已经生成的音频、feed、metadata 和质量报告，不作为转换服务入口。
5. 订阅扫描、多 episode 批处理、PodcastIndex 多 candidate 自动选择、YouTube playlist/channel/show 自动展开继续放到 Phase 3。

不要进入：

- voice clone
- ASR 作为 Route A 静默 fallback
- Web UI / App
- 订阅扫描或多 episode 批处理
- 本地 LLM serving

## 成功标准

MVP-0 acceptance 已满足：

- 使用 NASA 真实 transcript 样例，而不是只有一句 `欢迎收听本期节目。`
- 真实 transcript 的 `Host:` / 人名冒号 speaker label 已解析或清洗到 `speaker` 字段。
- `adapt` 输出继续保留 speaker。
- `workspace/runs/nasa-crew9-real-smoke/segments/manifest.json` 指向真实 TTS 生成的 wav。
- `assemble` 生成可播放 MP3。
- `publish` 生成 RSS feed 和 episode 静态 artifacts。
- 不引入 voice clone，不要求原主播音色。

MVP-0.5 acceptance 已满足：

- `mvp05-selfuse-nasa` 使用真实 NASA Crew-9 transcript，跑通 DeepSeek adapt、脚本预览、override、5090D 本地 TTS、assemble 和 publish。
- 最终 MP3 和稳定 feed 已生成，产物已拷回本机 ignored `workspace/runs/mvp05-selfuse-nasa/`。
- `run --to-stage adapt` 已支持 TTS 前停下预览，`run --from-stage synthesize` 已支持从预览/编辑后的脚本继续。

仍然保留到后续阶段：

- 真实 RSS、episode_page/on-demand 和 transcript-file 路径已有多 speaker 真实回归；PodcastIndex API 上的 `speaker_voices.mode: infer_once` 多 speaker profile 仍需真实回归；每个 podcast 的 source config 和批处理仍未做。
- 真实 podcast 来源扩展仍在 MVP-1 后续；当前主线已校正为点播式单集转换，而不是订阅式多 episode 扫描。官网 episode 页面 transcript 链接解析已通过 `source.type=episode_page` 完成第一版，并已补过 Practical AI、Lex Fridman、Cognitive Revolution 三类真实页面 normalize 验证；PodcastIndex API episode ingest 已通过 `source.type=podcast_index_api` 完成第一版，PodcastIndex 搜索/选择 CLI 已完成第一版，iTunes feed discovery、RSS episode selection 和 YouTube captions source 已完成第一版代码路径；YouTube 单链接 pre-DeepSeek 清洗、`t=` 起点裁剪、标题提取、`quality.json`、DeepSeek adapt 和 5090D TTS 已通过真实测试并先收口。下一步转 YouTube Podcasts / iTunes/RSS / PodcastIndex 单 URL 的 transcript 质量验证；02.09 剩余多 candidate 工作后移。
- 固定中文音色校准只选择或调整本地 TTS 可用声音和参数，不做原主播 voice clone。
- 第一轮和第二轮音色校准样本已在 5090D 生成并拷回本机 ignored `workspace/runs/`；这些音频不进入 git。
- 用户曾反馈 SFT 男声 D 版 EQ 比原始男声亮；后续确认 `male_a` 最终改为 `CosyVoice2 cross_lingual + speed=1.1`，D 样本只保留为历史校准记录。
- 公开 RSS 端到端 Real Run 已完成，证明给定 RSS 后可以自动读取 RSS item 内的 transcript 并生成中文 MP3/feed；已支持从已获取的 PodcastIndex episode JSON 读取 `transcripts[].url` / `transcriptUrl`；已支持 PodcastIndex API episode ingest 和搜索/选择 CLI；已支持官网 episode 页面 transcript-only ingest，并已通过 Practical AI、Lex Fridman、Cognitive Revolution 三个真实页面 normalize 验证；YouTube 单链接 captions 清洗、合并、deterministic `quality.json`、DeepSeek adapt 和 5090D TTS 已完成一轮真实验收；DeepSeek adapt 已支持按完整 segment chunk 批量调用；TTS batch wrapper 已解决每段重复启动 wrapper 的主要性能问题；`sft_builtin_4role` 已提供 MVP-1 多 speaker 角色基线，`male_a` 已改走 CosyVoice2 speed 1.1，`speaker_voices.mode: infer_once` 已补上每集一次 LLM 性别方向推断。后续先做 YouTube Podcasts / iTunes/RSS / PodcastIndex 单 URL 的 transcript 质量验证，再决定是否进入 DeepSeek/TTS；订阅扫描、多 episode 批处理、PodcastIndex API 真实多 speaker 回归和 02.09 剩余多 candidate 工作后移。授权男声/中性 reference wav 比选降级；更优先的音色扩展方向是微调 300M SFT 以增加多个中文男声/女声。

## 如果发生分支情况

- 如果 MVP-1 真实来源输入边界不清：先写一个小计划，不直接堆 CLI 参数。
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
