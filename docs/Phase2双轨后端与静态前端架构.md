# Phase 2 双轨后端与静态前端架构计划

日期：2026-06-19

## 背景

MVP-1 已完成单 URL 自用闭环：用户提供一个 YouTube / YouTube Podcasts 单集视频、标准 episode page、Apple Podcasts/iTunes URL 或直接 RSS feed URL，系统拿到现有 transcript 后，经 `normalize -> adapt -> synthesize -> assemble -> publish` 生成中文播客音频和 feed。

Phase 2 不应该把 ASR、声纹、Web UI 和 App 混进现有 transcript-first 路线里。下一阶段的核心目标是建立两个相互隔离的后端路线，并让前端只消费已经生成好的音频产物。

## 核心决策

1. 保留现有 transcript-first 路线作为稳定主线。
   - 输入是单 URL、source YAML 或本地 transcript file。
   - 只处理已经存在或可抓取的 transcript。
   - 不做 ASR，不下载原始音频，不做订阅扫描。

2. 新增 audio-first 路线作为独立后端。
   - 输入是本地音频文件，后续再扩展到可下载音频的 episode URL。
   - 先做 ASR，再做 speaker diarization / 声纹分离。
   - 输出结构化 transcript，再通过明确的文件契约进入后续中文改写和 TTS。

3. 两条路线只共享稳定契约，不共享来源获取逻辑。
   - 可以共享 `normalized.json`、中文脚本、TTS manifest、publish artifacts 等文件契约。
   - 不让 ASR 下载、diarization、声纹 profile 逻辑进入现有 YouTube/RSS/iTunes/episode page 入口。
   - 不让现有 transcript source adapter 依赖 ASR 相关包或模型环境。

4. 后端是离线生成器，不作为前端服务。
   - 后端继续以 CLI / batch job 形式由用户自己调用。
   - 不先做后台 API、队列、账号、多用户、权限或远程任务控制。
   - 前端不保存密钥，不调用 DeepSeek，不直接控制 TTS 或 ASR。

5. 前端是只读产物浏览和播放层。
   - 前端只伺服生成后的 MP3、feed、metadata、transcript 和质量报告。
   - 第一版前端不提交 URL、不触发转换、不展示实时任务队列。
   - 后续如果需要控制台，再作为独立阶段设计。

## 非目标

- 不做订阅扫描。
- 不做多 episode 自动批处理。
- 不做 PodcastIndex 多 candidate 自动选择。
- 不做 YouTube playlist / channel / show 自动展开。
- 不做原主播 voice clone。
- 不做多用户 Web 后台。
- 不把前端做成转换服务入口。

这些能力继续放在 Phase 3 或 Later。

## 总体架构

```text
Route A: transcript-first

single URL / source YAML / transcript file
  -> source adapter
  -> transcript/raw + transcript/normalized.json
  -> DeepSeek adapt
  -> local TTS on 5090D
  -> MP3 + feed + artifacts

Route B: audio-first

audio file / future audio URL
  -> audio acquisition
  -> ASR
  -> diarization / voice profile
  -> transcript/normalized.json
  -> DeepSeek adapt
  -> local TTS on 5090D
  -> MP3 + feed + artifacts

Frontend / App

published artifacts only
  -> browse
  -> play
  -> download
  -> inspect metadata / transcript / quality report
```

关键边界：Route B 可以把结果写成和 Route A 兼容的 transcript artifact，但 Route B 不应该改写 Route A 的来源解析、质量门禁或 CLI 语义。

## Route A：Transcript-first 稳定路线

现有路线继续覆盖：

- YouTube 单视频 / YouTube Podcasts 单集视频公开字幕。
- 标准 episode page transcript。
- Apple Podcasts/iTunes URL -> iTunes Lookup -> RSS -> 手动选集。
- 直接 RSS feed URL -> 手动选集。
- 本地 transcript file。

这条路线的保护规则：

- 保持 `babelecho episode convert --url ...` 的现有语义。
- 来源入口只负责拿 transcript，不静默降级到 ASR。
- 进入 DeepSeek 前必须继续经过 `quality.json` 和 script QA。
- 任何改动先跑来源矩阵回归：YouTube 单条、episode page、Apple Podcasts/iTunes URL、直接 RSS feed URL。
- 不引入 ASR、diarization、音频下载模型依赖。

## Route B：Audio-first ASR 路线

第一版建议从本地音频文件开始，不急着做 URL 下载：

```text
babelecho audio convert --audio-file <path> --run-id <id> --to-stage normalize
```

第一阶段输出：

- `audio/input.*`：原始音频或本地引用。
- `asr/raw.json`：ASR 原始输出，保留时间戳和文本。
- `asr/diarization.json`：说话人分段结果。
- `asr/speaker-profiles.json`：可选声纹 profile，仅用于同一集或同一节目的 speaker 聚类。
- `transcript/normalized.json`：进入现有后流程的结构化 transcript。
- `transcript/quality.json`：ASR 路线自己的质量检查结果。

Route B 的关键规则：

- ASR 解决“说了什么”。
- Speaker diarization / 声纹解决“谁在说”。
- 声纹只用于 speaker 聚类和固定中文音色映射，不默认做真实身份识别。
- 声纹不等于原主播 voice clone，也不生成相似原声。
- speaker 名称初期可以是 `speaker_1`、`speaker_2`，后续再允许用户手工改名。
- ASR 输出必须先变成 `normalized.json`，再进入 adapt/TTS；不要让后续阶段直接依赖某个 ASR 工具的私有 JSON。

## 共享契约

两条路线可以共享这些稳定产物：

- `workspace/runs/<run-id>/transcript/normalized.json`
- `workspace/runs/<run-id>/transcript/quality.json`
- `workspace/runs/<run-id>/script/zh.json`
- `workspace/runs/<run-id>/script/speaker-voices.json`
- `workspace/runs/<run-id>/segments/manifest.json`
- `workspace/runs/<run-id>/output/audio.mp3`
- `workspace/runs/<run-id>/publish/feed.xml`
- `workspace/published/feed.xml`

建议新增只面向前端和人工浏览的公开 artifact sidecar：

```text
workspace/published/index.json
workspace/published/episodes/<run-id>/artifact.json
```

它们只描述已经生成的文件、标题、来源、时长、声道、采样率、质量状态、可播放路径和可检查路径。前端只读这些 published sidecar，不反向驱动 pipeline，也不直接依赖 `workspace/runs/` 内部目录。

面向前端和设计 agent 的详细契约见 `docs/前端Artifact契约与只读界面说明.md`。该文档定义 `workspace/published/index.json` 和 `workspace/published/episodes/<run-id>/artifact.json`，并说明只读前端的页面范围和设计边界。

## 前端与 App 边界

第一版前端目标：

- 浏览已发布 episode。
- 播放 MP3。
- 下载 MP3。
- 查看 source metadata、`quality.json`、中文脚本和 run 状态摘要。
- 打开稳定 RSS feed 地址。

第一版前端不做：

- 提交 URL。
- 触发 DeepSeek。
- 触发 TTS。
- 触发 ASR。
- 任务队列、重试、取消、权限、登录。

App 方向：

- App 先作为 thin client。
- App 消费已发布的中文 podcast artifacts。
- App 不内嵌转换逻辑。
- App 不保存后端密钥或模型配置。

## 实施顺序

1. 固化 artifact manifest。
   - 目标：让后续前端有稳定只读入口。
   - 验证：现有 MVP-1 run 可以生成或导出 manifest，不影响 MP3/feed 输出。

2. 建立 Route A 回归矩阵。
   - 覆盖 YouTube 单条、episode page、Apple Podcasts/iTunes URL、直接 RSS feed URL。
   - 验证：只跑到 `normalize` 或 fixture adapt，不重跑长 TTS。

3. 建立 Route B 最小 CLI 骨架。
   - 只接受本地音频文件。
   - 先生成 run 目录、记录输入、写占位质量报告。
   - 验证：不影响 `episode convert`。

4. 接入第一版 ASR。
   - 输入短音频样本。
   - 输出带时间戳的 `asr/raw.json`。
   - 验证：人工检查文字可读，自动检查段落非空、时间戳单调。

5. 接入第一版 diarization。
   - 输出 `speaker_1` / `speaker_2` 等稳定 speaker 标签。
   - 验证：多人样本可以分段，单人样本不会被过度切碎。

6. 实现 Route B 到 `normalized.json` 的桥。
   - 把 ASR + diarization 输出转换为现有后流程可读的 transcript。
   - 验证：从 `adapt` 阶段继续可以复用现有 DeepSeek/TTS。

7. 跑 Route B 小样本全链路。
   - 选择 5 到 10 分钟的音频。
   - 跑 `ASR -> diarization -> normalize -> adapt -> TTS -> publish`。
   - 验证：用户试听，检查 speaker 映射和音频可听性。

8. 做只读前端原型。
   - 读取 `artifact.json` 和 publish 目录。
   - 提供播放、下载、质量报告和脚本查看。
   - 验证：前端不需要后端服务、不需要密钥、不触发转换。

## 验收标准

Phase 2 第一轮完成时应该满足：

- MVP-1 的四类单 URL 来源仍然可用。
- Route A 改动有低成本来源矩阵回归保护。
- Route B 可以从一个本地音频文件生成结构化 transcript。
- Route B 的多人样本至少能输出稳定 speaker 分段。
- Route B 生成的 `normalized.json` 可以复用现有 DeepSeek/TTS/publish 后流程。
- 前端可以只读浏览和播放已生成 artifact。
- 前端和 App 不依赖 DeepSeek key、TTS 环境或 ASR 模型环境。

## 风险与护栏

- ASR 模型、diarization 模型和 TTS 环境都重，必须避免把依赖装进现有轻量 transcript source 路线。
- 声纹属于敏感能力，先只做本地 speaker 聚类，不做身份识别，不提交 profile 文件。
- ASR 结果容易有错字、断句错误和 speaker 切分错误，因此 Route B 必须有独立质量报告，不能无检查直接进入 DeepSeek。
- 前端如果过早承担任务控制，会自然滑向后台服务和队列；第一版应坚持只读。
- 任何共享代码都应围绕文件契约和 artifact manifest，避免把 Route A 和 Route B 的业务流程耦合在一起。

## 下一步

下一步先做文档级设计收口和低成本保护：

1. 为现有 MVP-1 run 增加或整理 artifact manifest 方案。
2. 建立 Route A 来源矩阵回归，保护 YouTube、episode page、Apple/iTunes、直接 RSS。
3. 再开始 Route B 的本地音频最小骨架。
