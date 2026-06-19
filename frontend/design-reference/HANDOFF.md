# BabelEcho 只读前端 — 设计交接包（给 Claude Code）

## 你的任务（一句话）
照着本目录里的 `BabelEcho.dc.html` 这份高保真设计稿，在本项目的技术栈里实现一个**真实的只读前端**：视觉（布局 / 配色 / 字体 / 各种状态）完全照搬设计稿，但数据从 `workspace/published/` 读取真实产物，而不是设计稿里写死的示例数据。

## 这份设计稿是什么 / 不是什么
- `BabelEcho.dc.html` 是设计稿，靠同目录 `support.js` 运行时渲染。**它不是生产代码**：播放器是模拟的（无真实音频），三条数据是写死的 fixture。
- 请把它当**视觉与交互规范**来读：照抄它的版式、颜色、字体、组件状态、空状态。不要照抄它的运行时机制（support.js / DCLogic）。
- 用你项目现有的框架实现（React / Vue / 原生皆可，跟随本仓库约定）。

## 数据契约（唯一事实来源）
完整契约见 `uploads/前端Artifact契约与只读界面说明.md`，务必通读。要点：
- 列表入口：`workspace/published/index.json` → 渲染 episode 列表。
- 详情入口：列表项的 `artifact_path` → `workspace/published/episodes/<run-id>/artifact.json`。
- 音频：用 `audio_path`（index.json 中相对 `workspace/published/`；artifact.json 中 `media.audio_path` 相对该集目录）。不要用 `metadata.audio_url`（可能是占位）。
- 脚本：`transcript.zh.json`（中文，默认 tab）/ `transcript.en.json`（英文对照）。
- 前端**只读** `workspace/published/`；不提交 URL、不触发转换、不做任务队列 / 登录 / 后台配置。

## 必须正确处理的状态（最容易做错的地方）
- `quality.recommendation = safe_to_adapt` 是「正常可播放」，**不要**表现成「绝对正确」。其余值：`inspect_first`(复核) / `reject`(不建议播放) / `unknown`(未生成质量报告)。筛选 UI 要保留这四种视觉态，即使当前没有对应数据。
- `speakers = []`：隐藏说话人区，或显示轻量「无角色分段」。
- `route = article_reading`：不出现主持人 / 嘉宾概念；来源区按「只有一个 URL」的空态设计；正文用阅读排版而非转录行。
- 有 speaker 的集里，单个 segment 的 `speaker` 也可能为 null（过场 / 旁白）→ 不显标签，绝不显示「null」。
- `asr = null`：不显示 ASR 模块（可在 metadata/质量页注明「未使用 ASR」）。
- 中文脚本**无段级时间戳** → 不要把「跟读高亮 / 点击 seek」当成保证能力。
- `summary` / `created_at` 可能为 null；缺失字段一律留白或隐藏，**绝不显示 "null"**。
- 标题可能带抓取残留（如 `… \ Anthropic`），按原文展示，不要报错或硬截断。
- 未知 `route` / `source_type` → 按通用 episode 展示。

## 设计系统（从设计稿提取，可直接抄）
纯暗色。
- 背景 `--bg:#08090d`，顶部柔光：`radial-gradient(1200px 760px at 50% -24%, color-mix(in srgb, var(--accent) 17%, transparent), transparent 62%)` 叠一层 accent-2 的弱光。
- 面板 `--panel:rgba(255,255,255,.045)`；描边 `--border:rgba(255,255,255,.09)` / `--border-2:rgba(255,255,255,.15)`。
- 文字 `--fg:#eef0f6` / `--fg-2:#a6abbd` / `--fg-3:#6b7184`。
- 主强调 `--accent:#8b97ff`；次强调 `--accent-2:#4be0c4`。
- 质量色：safe `#56d6b0`、inspect `#ffcf5e`、reject `#ff7e8a`、unknown `#7c8190`。
- voice_role 配色：`male_a #8b97ff`、`male_b #4be0c4`、`female_a #ff85c0`、`female_b #ffd166`（头像 / role 徽章 / 脚本 speaker 标签统一用）。
- 波形未播放段 `rgba(255,255,255,.13)`，已播放段用 accent（article 用 accent-2）。
- route 色脊 / 徽章：`transcript_first`→accent，`article_reading`→accent-2。
- 字体：标题与拉丁文用 **Space Grotesk**；中文正文 **Noto Sans SC**；机器信息（route/source/时间码/路径/run_id/采样率）一律 **JetBrains Mono**。
- 阴影克制（`box-shadow` blur 控制在 ~26px 内，避免大面积发灰）。

## 四个画面
1. **Library 列表**：左侧筛选栏（route / source / quality / speaker，含 0 计数的占位态）；主列表每行 = 标题 + 来源 host + route·source 徽章 + 时长 + 角色数 + 质量点 + 发布时间；顶部命令行抬头 + 总时长/route 数状态条。
2. **Podcast 详情**：波形播放器 + tabs（中文脚本 / 英文原文 / 质量 / Metadata）+ 右栏说话人列表（含非真人「Sponsors」伪 speaker）。
3. **Article 详情**：阅读排版正文 + 小标题段；无说话人；来源区只有一个 URL 的空态。
4. **Mobile（390×844）**：列表 → 详情可导航；播放器置顶，脚本为主内容，来源/说话人折叠。

## 三条可用于联调的真实数据（已在 workspace/published/）
- `frontend-publish-practical-ai-faithful-sidecar-20260619` — 多人播客（5 speaker）。
- `frontend-publish-podnews-sidecar-20260619` — 短播客，无 speaker。
- `article-anthropic-infra-noise-20260619` — 文章朗读，`web_article`，无 speaker。

## 落地建议
1. 先实现数据层：读 `index.json` → 列表；读 `artifact.json` + `transcript.*.json` → 详情。
2. 再按上面的 token / 组件把设计稿的视觉搬过来。
3. 用上面三条真实数据逐一验收每种状态。
