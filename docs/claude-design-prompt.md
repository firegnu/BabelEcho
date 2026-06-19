# 给 Claude Design 的高保真 Mockup 提示词

日期：2026-06-19

本文件是交给 claude design 的提示词。设计依据是 `docs/前端Artifact契约与只读界面说明.md`（唯一 source of truth），Phase2 架构文档不作为设计输入。下方提示词已自包含关键约束和三条真实 fixture，可整段复制使用。

---

```text
你是 BabelEcho 只读前端的设计主创。请基于真实数据产出高保真 mockup（设计稿，不是生产代码；静态 HTML / Figma / 图片均可）。

【权威依据】
仓库内 docs/前端Artifact契约与只读界面说明.md 是唯一设计依据，请通读。下面是关键约束与真实数据摘要，与文档冲突时以文档为准。不要编造新的节目或新字段，只用下面这三条真实 fixture。

【产品定位 / 气质】
- 私有的本地/局域网「播客资料库」，给用户自己反复听和检查生成质量用，不是公开 SaaS。
- 安静、清晰、偏工具型。第一屏就是可用的资料库/播放器。
- 不要 landing page、营销 hero、宣传页、大幅说明页、SaaS 官网感。
- 信息密度与可扫读优先：标题、来源、时长、质量、route/source、speaker 数要容易比较。
- 颜色克制，避免大面积紫蓝渐变、装饰光斑、背景 orb、花哨插画。可用小图标辅助导航/播放/下载/筛选/展开折叠/状态 badge。
- 卡片只用于 episode item 或详情面板，不要卡片套卡片；主结构像应用 shell。
- UI 文字用中文；episode 标题、来源名、专有名词、URL 保持原文。

【必交付 4 个画面】
1. Library 桌面页（1440×900）：列出下面三条 episode，含 route/source/quality/speaker 的筛选视觉状态。
2. Podcast Episode Detail 桌面页：用「多人播客」fixture（下方 fixture A）。
3. Article Episode Detail 桌面页：用「文章朗读」fixture（下方 fixture C）。
4. Mobile Episode Detail（390×844）：播放器固定在上方，脚本为主内容，source/quality 折叠。

详情页核心：标题 + 来源 + 状态 badge → 音频播放器 → tabs（默认「中文脚本」/「英文原文」/「质量」/「Metadata」）→ speaker/时长/来源链接 → 下载 MP3。

【三条真实 fixture】
A. 多人标准播客（用于 Podcast 详情页）
- 标题：The AI engineer skills gap
- route=transcript_first，source=podcast_rss（provider rss）
- 时长 2372.18s（约 39:32），quality=safe_to_adapt，segments=103
- 来源：episode_url https://share.transistor.fm/s/e3639074；有 feed（可显示「打开 RSS」）
- 5 个 speaker（含一个非真人的「Sponsors」伪 speaker），各自有中文音色角色：
  Jerod(2段, male_a) / Daniel(14, male_b) / Chris(7, male_a) / Ramin(17, male_b) / Sponsors(1, female_a)
- 中文脚本样例：
  [Jerod]「欢迎收听 Practical AI 播客，在这里我们拆解人工智能的真实世界应用……你可以在 practicalai 点 fm 了解更多。」
  [无 speaker]「现在进入正题。」
  [Daniel]「欢迎收听新一期的 Practical AI 播客。我是 Daniel Wightnack，Prediction Guard 的 CEO……Chris，你怎么样？」
  [Chris]「嘿，今天挺好的，Daniel。你怎么样？」
- 英文原文样例（仅 podcast 的英文有时间戳，可用于对照）：
  [Jerod]「Welcome to the Practical AI Podcast, where we break down the real world applications of artificial intelligence…」

B. 短标准播客，无 speaker（用于 Library，及无角色降级态）
- 标题：A new AMP member
- route=transcript_first，source=podcast_rss
- 时长 231.52s（约 3:52），quality=safe_to_adapt，segments=18，speakers=[]
- 来源：episode_url https://podnews.net/update/amp-member，feed https://podnews.net/rss
- 中文样例：「来自我们的免费每日新闻通讯，podnews.net 的最新消息，由 Spots Now 赞助播出。」

C. 技术文章朗读（用于 Article 详情页）
- 标题：Quantifying infrastructure noise in agentic coding evals \ Anthropic（注意尾部「\ Anthropic」是抓取残留，按原文展示、不要报错或硬截断）
- route=article_reading，source=web_article（provider trafilatura）
- 时长 684.85s（约 11:25），quality=safe_to_adapt，segments=33，speakers=[]
- 来源只有一个 URL：https://www.anthropic.com/engineering/infrastructure-noise；无 author/站点名/发布时间/摘要，无 feed
- 中文「正文」样例（含小标题段，应按阅读/正文排版，而非主持人转录行）：
  正文：「像 SWE-bench 和 Terminal-Bench 这样的智能体编程基准测试，常被用来比较前沿模型的软件工程能力……差距达到了 6 个百分点（p 值小于 0.01）。」
  小标题段：「我们是如何发现这一点的」

【必须正确体现的真实状态】
- safe_to_adapt 是「正常可播放」，不要表现成「绝对正确」。
- speakers=[]（fixture B、C）：隐藏 speaker 区，或显示轻量「无角色分段」状态。
- article_reading（fixture C）：不出现主持人/嘉宾概念；来源区基本只有一个 URL，按空态设计；正文用阅读排版。
- asr=null：不显示 ASR 模块，可在 metadata/质量页注明「未使用 ASR」。
- 中文脚本没有段级时间戳：不要把「跟读高亮 / 点击 seek」当作保证能力来设计；播放器与脚本可并排，但不依赖段级同步。
- 有 speaker 的集里，单个段的 speaker 也可能为空（如「现在进入正题。」），空段不显标签。
- summary / created_at 当前全为空：详情页头部不要依赖摘要或创建时间，需有缺省排版。
- 缺失字段一律留白或隐藏，绝不显示「null」。
- 筛选维度其实很稀疏（quality 全是 safe_to_adapt，route 只有两种，speaker_count 为 {0,5,0}）：筛选 UI 不必做成沉重左栏，但请刻意展示 inspect_first / reject / unknown 这些没有 fixture 的视觉状态。

【绝对不要设计的功能】
URL 输入框、转换/生成按钮、任务队列、实时日志、登录/账号、后端配置管理、DeepSeek/TTS/ASR 的启动停止控制、订阅扫描或批处理。本前端只浏览、播放、下载、查看已生成产物。

【输出】
至少：桌面主界面 1440×900 + 移动关键页 390×844。可出 2–3 个视觉方向，但每个方向都必须用上面这同一批真实 fixture。可附一段简短交互说明（列表选集、tab 切换、播放、下载）。
```
