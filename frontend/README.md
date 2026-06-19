# BabelEcho 只读前端

私有、本地/局域网的 artifact 浏览器。只读 `workspace/published/` 里已生成的中文播客产物：浏览、播放、下载、查看脚本 / 来源 / 质量 / metadata。**不**提交 URL、不触发转换、无任务队列 / 登录 / 后台。

纯静态 HTML + CSS + 原生 JS，无构建步骤、无依赖。视觉照搬 `design-reference/BabelEcho.dc.html`（claude design 交付稿），数据全部来自真实 published 产物。

## 运行

前端需要能通过同源 HTTP 访问 `workspace/published/`。最简单的方式是从**仓库根目录**起一个静态服务：

```bash
python3 frontend/serve.py 8137
# 打开 http://127.0.0.1:8137/frontend/
```

`serve.py` 从仓库根目录伺服（`/frontend/` 与 `/workspace/published/` 都可访问），并**支持 HTTP Range 请求**——音频拖动 / ±15s / 键盘 seek 依赖它。直接用 `python -m http.server` 也能打开页面、能顺序播放，但**不支持 Range，无法跳转**。

> 开发用：worktree 里 `workspace/published` 是指向主 checkout 的符号链接（`workspace/published/` 是 gitignore 的生成产物，不在仓库里）。

### 指向其它数据位置

数据根由 `window.BABELECHO_BASE` 控制，默认 `/workspace/published`。若把前端文件直接放进 published 目录一起伺服，可在 `index.html` 的脚本前加：

```html
<script>window.BABELECHO_BASE = '.';</script>
```

## 数据契约

依据 `docs/前端Artifact契约与只读界面说明.md`：

- 列表入口 `index.json`；其 `audio_path` / `artifact_path` 相对 `published/`。
- 详情入口 `episodes/<run-id>/artifact.json`；其 `media.audio_path` / `artifacts.*` 相对该集目录。
- 脚本 `transcript.zh.json`（默认）/ `transcript.en.json`（对照）。

## 文件

| 文件 | 作用 |
| --- | --- |
| `serve.py` | 带 Range 支持的本地静态服务（音频 seek 需要） |
| `index.html` | 应用外壳（顶栏、`#app`、`<audio>`） |
| `fonts/` | 自托管 Space Grotesk / JetBrains Mono（变量 woff2，离线可用） |
| `css/tokens.css` | `@font-face` + 设计 token（暗色）+ 基础样式 |
| `css/app.css` | 组件样式（含响应式） |
| `js/format.js` | 纯展示辅助（时间、host、音色色、质量、标题判定、波形种子） |
| `js/data.js` | 只读数据层：取 index / artifact / transcript，处理路径 base |
| `js/app.js` | hash 路由、Library / Detail 渲染、真实播放器、筛选、tab、移动折叠 |
| `design-reference/` | claude design 交付的设计稿与 HANDOFF（仅参考，非运行代码） |

## 相对设计稿的有意调整

设计稿是模拟运行时（写死 fixture、模拟播放器）。实现真实前端时按 HANDOFF 做了如下调整：

- **真实 `<audio>` 播放器**：替换模拟计时器；波形为真实进度条（点击 seek、−15/＋15s、倍速可用）。中文脚本无段级时间戳，故不做跟读高亮。
- **纯暗色**：按 HANDOFF「纯暗色」，移除设计稿里无对应浅色 token 的主题切换。
- **真正响应式**：用 ≤820px 媒体查询让同一套页面在窄屏重排（资料库隐藏筛选栏、详情单列、播放器吸顶、说话人 / 来源可折叠），取代设计稿用于展示的「移动端预览」假手机框。
- **文章英文 tab**：`transcript.en.json` 实际含英文正文（无时间戳），按阅读排版展示，而非设计稿里的空态。
- **列表副标题显示 `run_id`**：`index.json` 不含来源 URL，故列表第二行用 `run_id`（host 在详情页展示）。
- **文章小标题**：`transcript.zh.json` 无显式标题标记，按「短且无句末标点」启发式识别小标题段。
- **离线字体**：Space Grotesk / JetBrains Mono 自托管于 `fonts/`（变量 woff2，latin 子集，~56KB），不依赖 Google Fonts CDN；中文正文用系统 CJK 字体（PingFang SC / 微软雅黑），不打包体积庞大的 Noto Sans SC。
- **键盘可达**：波形是 `role="slider"`，方向键 ±5s、PageUp/Down ±30s、Home/End；tab 支持左右键切换。
- **移动端**：详情页把来源 / 说话人 / 信息折叠卡放在播放器正下方（脚本之前），不必滚过整段脚本才够得到。

## 边界

前端只读已发布产物，不写、不触发任何后端流程，不读取 `workspace/` 下的 config / sources / runs 内部文件。
