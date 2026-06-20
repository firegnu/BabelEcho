# BabelEcho 交接

## 0. 2026-06-20 最新接续状态

新 session 优先读取 `resume-prompt.md`；本文件保留更长历史。当前功能基线已包含 audio-first URL ingest、边界内容自动清理、非 WAV diarization 输入规范化，以及 BBC 类短音频 diarization 质量门校准。继续前仍按标准入口执行 `git status --short --branch` 和 `git log --oneline -3` 确认最新点。远端仍有既有 untracked 文件 `workspace/sources/practicalai-mcp-312-transcript.txt`，不要误删。

Phase 2 Route B audio-first 当前状态：

- `babelecho audio convert` 已支持本地音频文件或显式公网音频 URL：CLI 输入为 `--audio-file | --audio-url` 二选一，后续仍走 `ingest_audio -> asr -> diarize -> normalize -> adapt -> synthesize -> assemble -> publish`。
- `--audio-url` 当前是 audio-first 的显式入口，不是 Route A 的静默 ASR fallback；artifact 只记录 `source_host` / `source_path`，不写 URL query/fragment。5090D smoke `audio-url-ingest-practicalai-ai-index-20260620` 已用 Practical AI 公网 MP3 跑到 `ingest_audio`：`source_type=audio_url`、`provider=remote_url`、MP3 约 `2832.4s`、`44100 Hz` mono、约 `45.4 MB`。
- 5090D 受控 URL 回归 `audio-url-normalize-practicalai-zero-trust-8min-20260620` 已通过：用远端 localhost HTTP 临时服务暴露已有 Practical AI 8 分钟真实 wav，再经 `--audio-url -> asr -> diarize -> normalize`；query 未泄漏，ASR 123 段，diarization 23 turns，normalized 32 段，quality=`safe_to_adapt`，metrics 与同样本本地文件路线一致。
- 5090D 短 URL full-chain `audio-url-fullchain-bbc-6min-screen-time-20260620` 已通过：BBC `6 Minute English - Limiting screen time for children` 直链约 8.5 分钟输入，经 `--audio-url -> ASR -> diarize -> normalize -> DeepSeek -> TTS -> publish` 生成中文 MP3，40 段，quality=`safe_to_adapt`，diarization 4 speakers，voice roles `female_a/male_a/female_b/male_b` 均有使用，输出 `22050 Hz` mono、约 `354.8s`、约 `5.7 MB`，已拷回本机 ignored `workspace/runs/audio-url-fullchain-bbc-6min-screen-time-20260620/output/audio.mp3`。
- 该 BBC 样本暴露 audio-first 真实内容清理问题：动态广告/片尾推广进入 ASR 和中文稿，首尾 segment 包含广告/推广性内容。链路可用，但在正式自用前应补 audio-first 的广告/舞台/片尾清理或人工裁剪入口。
- 已新增 audio-first 边界内容自动清理：只处理开头/结尾边界窗口，高置信广告/推广自动删除，低置信只写 warning，不要求人工确认。5090D 重跑同一 BBC run 的 `normalize -> publish` 后，normalized/script/manifest 为 36 段，自动删除 4 个边界内容段，quality 仍为 `safe_to_adapt`，MP3 更新为 `22050 Hz` mono、约 `339.4s`，首段从“大家好，这里是六分钟英语”开始，尾段到“再见”结束；更新后的 MP3 已拷回同一本机 ignored 路径。
- 已新增 diarization 输入规范化：`local_cli` diarization 对非 WAV 输入会先用 ffmpeg 生成 run-local `audio/diarization-input.wav`（mono、16k、PCM），再把该 WAV 传给 pyannote wrapper；原始音频仍保留给 ASR/source artifact。根因验证样本是 Podnews `The risk takers in podcasting` MP3：原始 MP3 含封面图视频流、双声道和非零 start time，pyannote 原始读取会因 10 秒 chunk 样本数不匹配失败；同文件转成标准 WAV 后 wrapper 可正常输出 diarization。5090D 回归 `audio-url-regression-podnews-risk-takers-20260620` 已从 `diarize -> publish` 跑通：quality=`safe_to_adapt`，10 段、2 speakers，自动删除 3 个边界段，1 个 possible boundary warning 保留，最终 MP3 为 `22050 Hz` mono、约 `147.10s`、约 `2.35 MB`，ffmpeg 解码通过，产物已拷回本机 ignored `workspace/runs/audio-url-regression-podnews-risk-takers-20260620/output/audio.mp3`。
- 已校准 audio-first diarization 质量门：ASR segment 与 diarization turn 对齐时先按 speaker 聚合 overlap，避免同一 speaker 被拆成多个 turn 后误算为 cross/ambiguous；`ambiguous_speaker_assignments` 现在要求 ambiguous 数量和比例同时达标，少量低占比 ambiguous 仅保留 advisory warning；`missing_diarization_overlap` 现在会写 count/ratio/duration/boundary metrics，只有正文缺失、缺失过多或边界缺失过长才 `inspect_first`，尾部短 farewell 缺口只保留 advisory。5090D 回归结果：BBC Advertisers 从 `inspect_first` 变为 `safe_to_adapt` 并已跑通 `adapt -> publish`，最终 MP3 `22050 Hz` mono、约 `343.01s`；BBC Hantavirus 从 `inspect_first` 变为 `safe_to_adapt`，49 段、3 speakers、`missing_diarization_overlap_segment_count=1`、尾部缺失 1000ms，并已跑通 `normalize -> publish`，最终 MP3 `22050 Hz` mono、约 `365.27s`、约 `5.84 MB`，ffmpeg 解码通过；BBC Screen Time 和 Podnews 仍为 `safe_to_adapt`。
- ASR provider 已有 `fixture` / `local_cli`；5090D 已验证本地 OpenAI Whisper `small.en`。
- Diarization provider 已有 `none` / `fixture` / `local_cli`；5090D 已用 pyannote Community-1 在 Practical AI 8 分钟样本上分出 `speaker_1/speaker_2`。
- `asr.replacements` 已实现：只做显式短语 `from -> to`，默认不开启；5090D smoke 修正 `Daniel White Knack`、`cloud code`、`cloud co-worker`，不宽泛替换普通 `cloud`。
- `asr/speaker-profiles.json` 统计 profile 已实现并跑通 full publish smoke：只含 turn 数、总时长、首尾时间、`profile_kind=diarization_stats`、`embedding_status=not_computed`，不含 voiceprint embedding；published artifact 会暴露 `speaker-profiles.json` 和摘要。
- 最新 full publish smoke：`audio-speaker-profiles-practicalai-publish-20260620`，ASR 123 段，normalized/script/manifest 均 32 段，quality=`safe_to_adapt`，MP3 `22050 Hz` mono、约 `361.48s`。
- Voice profile 当前已进入诊断性 speaker embedding：`voice_profile.provider=local_cli` 可调用 SpeechBrain ECAPA wrapper，写 run-local `asr/voice-profiles/*.json`，publish 仍不复制 embedding 文件。
- 新增 `babelecho speaker-profiles compare --run-dir ... --output-json ...`，只读取 ignored run-local embedding artifact，输出 cross-run cosine 报告，不进入 TTS、不做 voice clone。
- 5090D 真实两集 smoke 已完成：`audio-voice-profile-real-practicalai-zero-trust-8min-20260620` 产出 2 个 192 维 embedding；`audio-voice-profile-real-practicalai-ai-index-8min-20260620` 产出 3 个 192 维 embedding。报告 `workspace/runs/speaker-similarity-practicalai-real-two-episodes-20260620.json` 共 6 个 cross-run pair：`likely_same=2`、`different=4`；最高两对为 `speaker_1 -> speaker_2 cosine=0.959153` 和 `speaker_2 -> speaker_3 cosine=0.881848`。
- 5090D 已继续补 3 集 Practical AI 真实音频样本：`mcp-kubernetes`、`hermes-agent`、`model-wars`，均为公开 RSS 音频前 8 分钟，均跑通真实 ASR/diarization/SpeechBrain embedding。五集报告 `workspace/runs/speaker-similarity-practicalai-real-five-episodes-20260620.json`：14 个 computed speaker、78 个 cross-run pair、`likely_same=19`、`different=59`。
- 新增 `babelecho speaker-profiles alias --similarity-report ... --output-json ...`，从 similarity report 生成私有 speaker alias candidates；默认 `same_threshold=0.85`、`min_sample_duration_ms=60000`，用于过滤短片头/旁白片段。5090D alias map `workspace/runs/speaker-aliases-practicalai-real-five-episodes-20260620.json` 生成 2 个 alias：`speaker_alias_001` 有 5 个成员，min/avg/max cosine `0.850890/0.909038/0.959153`；`speaker_alias_002` 有 3 个成员，min/avg/max `0.881848/0.898437/0.919010`；4 个约 32 秒的 `speaker_1` 短样本被跳过。alias map 不含 `embedding_artifact`、`voice-profiles` 或 embedding 引用。
- 注意边界：`audio-voice-profile-speechbrain-smoke-20260620` 是 fixture ASR/diarization + 真实 SpeechBrain wrapper 的读写/隐私 smoke，不应当作为跨集声纹结论；JFK smoke 因样本窗口不足，speaker embedding 为 `unavailable`。

前端只读项目当前状态：

- `frontend/` 已加入主分支，提交为 `ead73dc feat: add read-only frontend for published artifacts`。
- 它是纯静态 HTML/CSS/原生 JS，无构建步骤、无依赖，只读 `workspace/published/`。
- 本地运行：`python3 frontend/serve.py 8137`，打开 `http://127.0.0.1:8137/frontend/`。
- 数据入口：`workspace/published/index.json` 和 `workspace/published/episodes/<run-id>/artifact.json`。
- 前端边界：只浏览、播放、下载、查看脚本/来源/质量/metadata；不提交 URL、不触发转换、不读 config/sources/runs 内部文件。
- 详情见 `frontend/README.md` 和 `docs/前端Artifact契约与只读界面说明.md`。前端后续工作可交给独立 agent；当前后端继续 Route B。

下一步计划：

- `audio_url` 已完成 ingest、normalize、短音频 full-chain、自动边界清理、非 WAV diarization 输入规范化和 Hantavirus 类质量门校准。下一步可继续补更多 audio-url 短样本回归，或转回 private speaker alias 人工确认 contract；不要直接把 alias map 接入 TTS。
- 不进入“立即声音 clone”；embedding 仍只做诊断/跨集一致性，不喂给 TTS，不发布向量或声纹文件。
- 本阶段仍要保持 Route B 隔离，不改 Route A 的 YouTube/RSS/iTunes/Article 已验证逻辑。

## 1. 会话摘要

本次会话围绕 BabelEcho 的 MVP-0 后端骨架、acceptance、MVP-0.5 自用流程、MVP-1 真实来源和 TTS 路由推进：当前混合验证路径是 LLM adaptation 使用 DeepSeek API，TTS 使用 5090D 本地混合路由。运行默认仍是 `tts.voice=sft_builtin_4role`，其中 `male_a` 使用 `CosyVoice2-0.5B cross_lingual + speed=1.1`，优先使用本地 calm prompt asset 并做 `male_a` 专用文本平稳化；`female_a / female_b / male_b` 使用 `CosyVoice-300M-SFT`。MVP-0 / MVP-0.5 均已完成，MVP-1 点播式单集转换已跑通真实全路径。

## 2. 完成的工作

- 明确产品边界：后端负责拉取 transcript、转译、生成中文音频和发布产物；macOS App 后续只消费已转换好的中文 podcast，不参与转换流程。
- 明确 MVP-0 约束：只支持完整 transcript 输入，不做 ASR、不做音频-only 输入、不做原主播 voice clone、不做后台服务或 App 集成。
- 已实现分阶段 Python CLI：
  - `run`：一条命令编排 `ingest -> normalize -> adapt -> synthesize -> assemble -> publish`。
  - `ingest`：读取 transcript URL 或本地 transcript 文件。
  - `normalize`：解析 `.vtt`、`.srt`、`.txt` 到统一 JSON。
  - `adapt`：当前已支持 fixture LLM、本地 OpenAI-compatible vLLM，以及 DeepSeek/OpenAI-compatible provider。
  - `synthesize`：fixture 静音 WAV 或本地 TTS CLI wrapper。
  - `assemble`：调用 `ffmpeg` 拼接 WAV 到 MP3。
  - `publish`：生成静态 episode 目录和 RSS `feed.xml`。
- 5090D 已验证 fixture 全链路：
  - `ingest -> normalize -> adapt(fixture) -> synthesize(fixture) -> assemble -> publish`
  - 已生成 `workspace/runs/fixture-smoke/output/audio.mp3`
  - 已生成 `workspace/runs/fixture-smoke/publish/feed.xml`
- 修复 `assemble` 在 5090D 上失败的问题：
  - 根因：`concat.txt` 中写入相对路径后，`ffmpeg` 按 `output/` 目录解析，导致路径变成 `output/workspace/runs/...`。
  - 修复：`src/babelecho/audio.py` 写入绝对音频片段路径。
  - 回归测试：`tests/test_audio.py` 覆盖相对 `workspace` 场景。
- 已完成验证：
  - `tests/test_audio.py`: `1 passed`
  - 全量测试：`14 passed`
  - 本机真实 fixture pipeline 跑到 `publish/feed.xml`
  - 对 git 跟踪文件运行 `gitleaks` 和 `trufflehog`，未发现泄露。
- 5090D 仓库可通过 `ssh my-5090d-host` 远程执行验证；新 session 需要以远端 `git status --short --branch` 和 `git log --oneline -3` 确认当前同步点。
- 已确认 `http://127.0.0.1:8000/v1/models` 返回 `{"detail":"Not Found"}`，说明 8000 上有服务但不是当前需要的 OpenAI-compatible LLM endpoint。
- 已决定不继续把 24GB 5090D 优先用于本地 LLM serving；先用 DeepSeek API 建立中文口播稿质量基线，把 5090D 留给本地 TTS。
- 已在 MacBook 实现 DeepSeek/OpenAI-compatible provider：
  - `src/babelecho/llm.py` 新增 `openai_compatible` provider。
  - 支持 `api_key_file` 从 ignored env 文件读取 API key，也保留 `api_key_env` 备用。
  - 请求会带 `Authorization: Bearer ...` header。
  - 支持 `extra_body`，用于 DeepSeek `thinking.type: disabled`。
  - `workspace/config/local.example.yaml` 已改成 DeepSeek LLM + 本地 TTS 示例。
  - `workspace/config/deepseek.env.example` 提供可提交的 env 文件模板，真实 `workspace/config/deepseek.env` 被 ignore。
  - `tests/test_llm.py` 覆盖 auth header、`extra_body` 合并、env 文件读取和缺 key 错误。
- 本机全量测试通过：`18 passed`。
- 已在 5090D 上完成 DeepSeek adapt 验证：
  - 远端已拉到 `e004674 feat: load deepseek key from ignored env file`。
  - 远端测试通过：`18 passed`。
  - `workspace/config/deepseek.env` 已由用户填写，且被 `.gitignore` 忽略。
  - `workspace/config/local-deepseek.yaml` 使用 `api_key_file`。
  - DeepSeek `/models` 返回 `deepseek-v4-flash` 和 `deepseek-v4-pro`。
  - `babelecho adapt --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-deepseek.yaml` 成功。
  - `workspace/runs/fixture-smoke/script/zh.json` 输出自然中文：`欢迎收听本期节目。`
- 已在 5090D 上完成本地中文 TTS 验证：
  - 新建专用 conda env：`/home/th5090d/miniforge3/envs/babelecho-tts`。
  - 保持 5090D 可用 GPU 栈：`torch 2.11.0+cu130`、`torchaudio 2.11.0+cu130`、`torchcodec 0.14.0+cu130`。
  - CosyVoice 代码目录：`/home/th5090d/Develop/ai_tools/CosyVoice`。
  - CosyVoice2 模型目录：`/home/th5090d/Develop/ai_tools/CosyVoice/pretrained_models/CosyVoice2-0.5B`；MVP-1 当前 `male_a` 默认路由要求它可用。
  - 新增 repo wrapper：`tools/cosyvoice_tts_wrapper.py`。
  - 远端 runtime launcher：`/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper`。
  - `tts-wrapper` 单句测试生成 `/tmp/babelecho-wrapper-test.wav`，`24000 Hz`、mono、`6.160000s`。
  - `babelecho synthesize --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-cosyvoice.yaml` 成功，生成真实 `segments/0001.wav`。
  - `workspace/runs/fixture-smoke/segments/0001.wav` 为 `24000 Hz`、mono、`3.080000s`。
  - `babelecho assemble --workspace workspace --run-id fixture-smoke` 成功，生成 `output/audio.mp3`，`24000 Hz`、mono、`3.144000s`。
- 已完成更长样本听感实验：
  - `workspace/runs/long-tts-smoke/output/audio.mp3` 已拷回 MacBook。
  - 中文脚本 4 段，最终 MP3 为 `24000 Hz`、mono、约 `92.8s`。
  - 用户试听反馈：效果还行。
- 已完成真实英文 podcast transcript 实验：
  - 来源：NASA 官方 `Houston We Have a Podcast`，Crew-9 episode transcript。
  - run-id：`nasa-crew9-real-smoke`。
  - 真实样本曾跑通 `normalize -> adapt(DeepSeek) -> synthesize(CosyVoice2) -> assemble`；当前 TTS 默认已更新为 `sft_builtin_4role` 混合本地渲染。
  - 本机产物：
    - `workspace/runs/nasa-crew9-real-smoke/output/audio.mp3`
    - `workspace/runs/nasa-crew9-real-smoke/script/zh.json`
    - `workspace/runs/nasa-crew9-real-smoke/transcript/normalized.json`
  - 首轮验证结果：source/script/audio segments 均为 5 段，MP3 为 `24000 Hz`、mono、约 `367.6s`。
  - 首轮当时暴露两个问题：speaker label 会进入正文；多人播客仍是单一中文声音。前者已在 MVP-0 收口，后者已在 MVP-1 通过 `sft_builtin_4role` profile 给出固定四角色基线。
- 已完成 MVP-0 acceptance 收口：
  - `src/babelecho/transcript.py` 已解析 speaker label，把 `Host:`、`Nick Hague:`、`Host (Dane Turner):` 等标签写入 `segment["speaker"]`，并从 `segment["text"]` 中移除。
  - `tests/test_transcript.py` 覆盖段首 label、段内多轮 speaker turn 和普通冒号不误判。
  - 本机全量测试：`21 passed`。
  - 5090D 分支验证：`21 passed`。
  - 5090D NASA 回归：`normalize -> adapt -> synthesize -> assemble -> publish` 已完成。
  - `nasa-crew9-real-smoke` 最终 normalized/script/manifest 均为 9 段；英文 segment text 无 `Host:` / `Nick Hague:` 标签残留；中文脚本无 `主持人：` / `尼克·黑格：` 朗读式标签残留。
  - 最终 MP3：`mp3`、`24000 Hz`、mono、约 `361.1s`。
  - 已验证 publish artifacts：`publish/feed.xml`、episode MP3、`transcript.en.json`、`transcript.zh.json`、`metadata.json`。
- 已完成 MVP-0.5 Self-use：
  - `src/babelecho/cli.py` 增加 `babelecho run`。
  - `run` 支持 `--from-stage` 从 `ingest`、`normalize`、`adapt`、`synthesize`、`assemble` 或 `publish` 继续执行。
  - `run` 支持 `--transcript-file` 直接导入本地 transcript，并可用 `--title` 写入 episode 标题，避免自用时手写 source YAML。
  - `src/babelecho/status.py` 增加 `workspace/runs/<run-id>/run.json`，记录 input、`from_stage`、每个 stage 状态、失败阶段、错误和已知输出路径。
  - `src/babelecho/checks.py` 增加基础质量检查，`babelecho check` 可独立检查 script、segments、output。
  - `src/babelecho/script.py` 增加 `babelecho script`，可在 TTS 前打印 `script/zh.json` 路径、段落编号、文本和 `--from-stage synthesize` 续跑提示。
  - `src/babelecho/publish.py` 仍保留 run-local publish artifacts，同时同步 `feed.xml` 和 episode artifacts 到稳定目录 `workspace/published/`。
  - `run` 在 `adapt`、`synthesize`、`assemble` 后自动检查中文脚本、wav segment 和最终 MP3。
  - `run` 输出包含 `stable feed: workspace/published/feed.xml`。
  - `tests/test_end_to_end_fixture.py` 覆盖 fixture 全链路和从 `synthesize` 恢复执行，保护手工编辑后的 `script/zh.json` 不被重新 adapt 覆盖。
  - `tests/test_end_to_end_fixture.py` 覆盖 `--transcript-file` 自用入口和 ingest 失败时的 `run.json` 失败记录。
  - `tests/test_end_to_end_fixture.py` 覆盖 `babelecho script` 输出和 `workspace/published/feed.xml` 生成。
  - `tests/test_publish.py` 覆盖 run-local publish artifacts 与 stable publish artifacts 同时生成。
  - `tests/test_checks.py` 覆盖空中文稿、超长段落、缺失 wav、缺失 MP3 和 ffprobe 元数据。
  - 本机全量测试：`34 passed`。
  - 5090D 全量测试：`34 passed`。
  - 5090D fixture smoke：`run-command-smoke` 使用 `babelecho run` 生成 `transcript/normalized.json`、`script/zh.json`、`segments/manifest.json`、`output/audio.mp3`、`publish/feed.xml` 和 episode MP3；script/manifest 均为 1 段。
  - 5090D check smoke：`check-command-smoke` 使用 `babelecho run` 自动输出 `check script`、`check segments`、`check output`；独立 `babelecho check` 输出 `script_segments=1`、`audio_segments=1`、`output_sample_rate=16000`、`output_channels=1`、`output_duration_seconds=0.504`。
  - 5090D manual input smoke：`manual-input-status-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Manual Input Smoke"` 跑通；`run.json` 显示 `status=succeeded`、`from_stage=ingest`、6 个 stage 全部 `succeeded`、`audio=output/audio.mp3`、`feed=publish/feed.xml`、`source_type=transcript_file`。
  - 5090D preview/stable publish smoke：`preview-stable-smoke` 使用 `babelecho run --transcript-file tests/fixtures/sample.vtt --title "Preview Stable Smoke"` 跑通；stdout 包含 `stable feed: workspace/published/feed.xml`；`babelecho script` 输出 `script/edit` 路径、`--from-stage synthesize` 提示和中文稿；`workspace/published/feed.xml` 存在且非空，`run.json` 输出 `stable_feed=published/feed.xml`。
- 已完成 MVP-0.5 本地专有名词和发音 override：
  - `src/babelecho/overrides.py` 增加本地精确替换逻辑，读取 `overrides.path` 指向的 YAML 词表，改写 `workspace/runs/<run-id>/script/zh.json`。
  - `src/babelecho/cli.py` 增加 `babelecho overrides --workspace ... --run-id ... --local-config ...`。
  - `babelecho run` 在 `synthesize` 前自动应用 configured overrides，并在 stdout 输出替换数量。
  - `workspace/config/overrides.example.yaml` 提供可提交的示例词表，真实 `workspace/config/overrides.yaml` 继续被 ignore。
  - `workspace/config/local.example.yaml`、README、runbook 和 roadmap 已记录 override 用法。
  - 本机全量测试：`37 passed`。
  - 5090D 全量测试：`37 passed`。
  - 5090D fixture smoke：`overrides-smoke` 使用临时 workspace 和 fixture provider 跑通；stdout 包含 `overrides: 2 replacements from 2 rules`；`script_text` 和 `manifest_text` 都为 `中文口播：欢迎 to the 样例节目.`；`run.json` 状态为 `succeeded`，稳定 `published/feed.xml` 存在。
- 已完成 MVP-0.5 self-use acceptance：
  - `src/babelecho/cli.py` 增加 `babelecho run --to-stage ...`，默认仍到 `publish`；可用 `--to-stage adapt` 在 TTS 前停下预览。
  - `src/babelecho/status.py` 的 `run.json` 记录 `to_stage`，请求范围外阶段标记为 `skipped`。
  - `tests/test_end_to_end_fixture.py` 覆盖 `run --to-stage adapt` 停在中文脚本阶段，不生成音频。
  - 本机全量测试：`38 passed`。
  - 5090D 真实自用回归 run-id：`mvp05-selfuse-nasa`。
  - 回归流程：真实 NASA Crew-9 transcript -> `ingest` -> `normalize` -> `adapt(DeepSeek)` -> `babelecho script` 预览 -> override -> `run --from-stage synthesize` -> 本地 TTS -> `assemble` -> `publish`。
  - 回归结果：script/manifest 均为 9 段；override 命中 10 次；最终 MP3 为 `24000 Hz`、mono、约 `355.5s`；`workspace/published/feed.xml` 已生成；`run.json` 为 `status=succeeded`、`from_stage=synthesize`。
  - 产物已从 5090D 拷回本机 ignored 路径：`workspace/runs/mvp05-selfuse-nasa/output/audio.mp3`、`script/zh.json`、`segments/manifest.json`、`publish/feed.xml`。

## 3. 待完成的工作

- MVP-0 acceptance 已完成：完整 transcript 到中文 MP3，再到静态 RSS/episode artifacts 的真实路径已经跑通。
- MVP-0.5 Self-use 已完成：手动导入 transcript 后，可以生成私有中文 podcast feed，并已完成真实自用回归。
- 下一阶段仍是 MVP-1 Real Podcasts；YouTube 单链接探索已先收口，下一步转向标准播客点播来源对接，包括 YouTube Podcasts 单集、RSS/iTunes feed、PodcastIndex episode 和官网 episode 页面。
- MVP-1 后续优先任务：
  1. 保持点播式单集转换为主入口，先处理用户提供的单个标准播客 URL。
  2. 对 YouTube Podcasts、iTunes/RSS、PodcastIndex 和官网 episode 页面做候选发现、transcript 质量验证和失败诊断。
  3. `docs/plans/02-real-podcasts/09-transcript-candidate-cleaning.md` 中的 HTML speaker 修复、RSS 多 candidate、PodcastIndex 多 candidate 可作为下一轮拆解来源；订阅扫描、多 episode feed、跳过已处理 episode 后移到 MVP-2。
- 当前真实能力已经包括 DeepSeek 生成中文口播稿和 5090D 本地 TTS 合成 wav，但仍不是完整产品：
  - 来源已新增第一版 RSS feed 输入：`source.type=podcast_rss` 和 `babelecho run --podcast-feed ...`，只支持 RSS item 内的 `podcast:transcript`；公开 RSS smoke 使用 `https://feeds.transistor.fm/podcasting-advice` 跑到 `adapt`，fixture script 共 74 段，未调用 DeepSeek。还没有接 Apple Podcasts、Spotify、YouTube 页面解析。
  - 公开 RSS 端到端 Real Run 已完成：`mvp1-real-rss-monetize-20260617` 使用 `Podcasts for Profit` 的 `#030: When Should You Monetize Your Podcast?`，经 RSS transcript -> DeepSeek -> 5090D TTS -> assemble -> publish 成功；script/manifest 75 段，最终 MP3 约 `840.8s`，产物已拷回本机 ignored `workspace/runs/mvp1-real-rss-monetize-20260617/`。
  - TTS 执行效率优化已完成：`local_cli` synthesis 会写 `segments/tts-batch.json` 并一次启动 wrapper，wrapper 只加载一次 CosyVoice 后循环生成 wav；旧单段 `--text-file --output` wrapper 调用仍保留。5090D `batch-wrapper-smoke-20260617` 两段真实 CosyVoice smoke 已通过。
  - 真实 transcript 中的段首和段内 speaker label 已有基础解析/清洗，但后续真实来源仍需要更多样本回归。
  - MVP-1 固定音色规则已实现：运行默认使用 `tts.voice=sft_builtin_4role` 固定角色 profile。0/1 个 distinct speaker 且没有显式性别标签时使用 `female_a`；单个 speaker 标签包含 `male` / `男` 时使用 `male_a`，包含 `female` / `女` 时使用 `female_a`；2 个及以上 distinct speaker 按首次出现顺序映射到 `female_a / male_a / female_b / male_b`。
  - `sft_builtin_4role` 当前是混合本地渲染：`female_a -> CosyVoice-300M-SFT / 中文女`，`male_a -> CosyVoice2 cross_lingual / calm prompt if present, fallback cross_lingual_prompt.wav / speed=1.1 / text smoothing`，`female_b -> CosyVoice-300M-SFT / 英文女`，`male_b -> CosyVoice-300M-SFT / 英文男`；同名 speaker 复用同一角色，超过 4 个 speaker 循环复用。
  - `sft_builtin_4role` 不做原主播 voice clone。5090D 历史 wrapper smoke 已验证四个 SFT 角色真实 wav 输出为 `22050 Hz` mono；最终混合 `male_a` 代码路径也已验证。
  - 2026-06-18 Practical AI `Model Context Protocol Deep Dive` 全路径 run `llm-practicalai-mcp-real-20260618` 已完成：101 段，DeepSeek chunk 6 次，speaker 推断一次，`Jerod -> male_a`、`Daniel -> male_b`、`Chris -> male_a`，最终 MP3 为 `22050 Hz` mono、约 `1819.5s`；用户试听反馈基本可接受。
- 多人多音色已作为 MVP-1 固定 profile 落地；不要把它回填到 MVP-0.5。
- DeepSeek adapt 基线已经跑通；后续只在 prompt 质量明显不满足时再回到 LLM adapt。
- MVP-1 固定中文音色校准已开始：
  - 本轮未调用 DeepSeek API，直接使用已有 `mvp05-selfuse-nasa/script/zh.json` 中文稿片段做 TTS。
  - 历史校准时，5090D CosyVoice2 目录只有 `asset/zero_shot_prompt.wav` 和 `asset/cross_lingual_prompt.wav` 两个内置参考音频；`CosyVoice2-0.5B` 没有内置 SFT speaker 列表。
  - 已生成三条第一轮候选样本，并拷回本机 ignored 路径 `workspace/runs/voice-calibration-20260617/`：
    - `a-current-zero-shot-female.mp3`：当前默认 zero-shot 女声 baseline，约 `27.5s`。
    - `b-neutral-instruct2-female.mp3`：同一参考音频，使用 `inference_instruct2` 尝试压情绪到自然平静，约 `23.6s`。
    - `c-cross-lingual-reference.mp3`：使用 `cross_lingual_prompt.wav` 的参考音色，约 `24.3s`。
  - 三条样本均为 `24000 Hz`、mono；真实 wav/MP3 和 manifest 不进入 git。
  - 第一轮用户反馈：C 最好，因此第二轮沿 cross-lingual/reference-audio 路线继续微调，而不是继续围绕默认 zero-shot 女声。
  - 已提交 `ee30dd6 feat: configure cosyvoice reference mode`：
    - `src/babelecho/tts.py` 会把 `tts.mode`、`tts.prompt_wav` 和 `tts.speed` 转发给本地 wrapper。
    - `tools/cosyvoice_tts_wrapper.py` 支持 `zero_shot` 和 `cross_lingual` 两种非 voice-clone 模式，并支持 `speed`。
    - 本机全量测试：`41 passed`。
  - 已在 5090D 生成第二轮 cross-lingual speed 微调样本，并拷回本机 ignored 路径 `workspace/runs/voice-calibration-20260617-round2/`：
    - `d-cross-lingual-speed-100.mp3`：`mode=cross_lingual`，`speed=1.0`，约 `24.7s`。
    - `e-cross-lingual-speed-095.mp3`：`mode=cross_lingual`，`speed=0.95`，约 `26.0s`。
    - `f-cross-lingual-speed-090.mp3`：`mode=cross_lingual`，`speed=0.90`，约 `27.5s`。
  - 用户曾反馈 D 最满意；后续单男、单女、多人验证后，MVP-1 运行默认先改为 300M SFT 四角色，之后又按试听结果把 `male_a` 单独切回 CosyVoice2 cross-lingual speed `1.1`，D 样本只保留为历史校准记录。
  - 第二轮未调用 DeepSeek，只使用第一轮相同中文样本文本和 `cross_lingual_prompt.wav`。
  - 不再继续围绕 CosyVoice2 内置两个 wav 反复微调。后续音色方向改为微调 `CosyVoice-300M-SFT`，目标是增加多个稳定中文男声和中文女声；这是固定角色音色扩展，不是原主播 voice clone。微调结果需试听确认后再决定是否替换当前 `male_a` CosyVoice2 或 `female_b/male_b` 角色。

## 4. 关键决策

- MVP-0 采用 CLI-first、文件产物驱动，不先做 Web 后台、队列、数据库或常驻服务。
- 最终方向仍是 local-first，但当前阶段明确接受 DeepSeek API 作为 LLM adaptation 的临时质量基线。
- MVP-0.5 自用流程已收口；MVP-1 已完成混合 TTS 规则和四角色多 speaker profile，后续继续点播入口失败诊断、搜索式 episode 选择和 PodcastIndex 真实回归，不进入 voice clone、ASR、App 或后台服务。
- MVP-0 可以接受单固定中文声音；MVP-1 当前运行默认使用 `sft_builtin_4role`，单人默认 `female_a`，单个 `male` / `男` speaker 用 `male_a`，单个 `female` / `女` speaker 用 `female_a`，2+ speakers 用四角色稳定映射；实际渲染时 `male_a` 走 CosyVoice2，其他角色走 300M SFT。
- `DEEPSEEK_API_KEY` 只能放在 ignored `workspace/config/deepseek.env` 中，不能写入 tracked 文件。
- 真实 runtime config、生成音频、run outputs、模型缓存、conda env 不进入 git。
- 5090D 执行代码方式：MacBook 修改并 push；必要时通过 `ssh my-5090d-host` 在远端运行验证命令，但不在 5090D 上安装或运行 Codex agent。
- `docs/roadmap.md` 是产品路线入口；`docs/plans/` 放具体执行计划。
- Python pipeline 环境使用项目内 conda env：`.conda/babelecho-dev`，不要使用 base env。
- TTS 模型环境使用 5090D 专用 conda env：`babelecho-tts`，不要把 CosyVoice 的完整 `requirements.txt` 直接装进 pipeline 环境。

## 5. 重要文件

- `README.md`
- `resume-prompt.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/backend-mvp0-runbook.md`
- `docs/backend-mvp.md`
- `docs/backend-mvp0-tech-stack.md`
- `docs/source-ingestion-research.md`
- `docs/plans/01-backend-mvp0/03-local-tts.md`
- `workspace/config/local.example.yaml`
- `workspace/sources/hardcoded.example.yaml`
- `src/babelecho/cli.py`
- `src/babelecho/transcript.py`
- `src/babelecho/llm.py`
- `src/babelecho/adapt.py`
- `src/babelecho/synthesize.py`
- `src/babelecho/audio.py`
- `src/babelecho/publish.py`
- `src/babelecho/overrides.py`
- `src/babelecho/status.py`
- `tools/cosyvoice_tts_wrapper.py`
- `tests/test_transcript.py`
- `tests/test_audio.py`
- `tests/test_llm.py`
- `tests/test_cosyvoice_wrapper.py`
- `tests/test_overrides.py`
- `workspace/config/overrides.example.yaml`

## 6. 下一步建议

1. 继续保持点播式单集转换为主入口，下一步接标准播客来源：YouTube Podcasts 单集、iTunes/RSS、PodcastIndex 和官网 episode 页面。
2. 先用用户给的单个 URL 做 transcript candidate、清洗质量和失败诊断验证，再决定是否进入 DeepSeek/TTS。
3. 音色方向后移到 300M SFT 微调：先定义固定角色需求、训练/试听样本和验收标准，不影响当前 MVP-1 默认规则。
4. 仍不要同时推进 ASR、voice clone、App 或后台服务。

## 当前 Git 状态

- MVP-0 acceptance 收口基线提交：`815c296 docs: mark mvp0 acceptance complete`；当前 `main` / `origin/main` 可能包含后续 handoff 文档刷新提交，新 session 以 `git log --oneline -3` 为准。
- MVP-0 acceptance 代码验证提交：`9444363 fix: parse transcript speaker labels`。
- MVP-0.5 `babelecho run` 功能提交：`96776e8 feat: add pipeline run command`。
- MVP-0.5 override 功能提交：`4f92d37 feat: add script overrides`。
- MVP-0.5 self-use 收口提交包含 `run --to-stage`、真实 `mvp05-selfuse-nasa` 验证记录和 docs 状态更新；具体提交以 `git log --oneline -3` 为准。
- 5090D `/home/th5090d/Develop/personal_project/BabelEcho` 已用于本轮分支验证；新 session 如需继续远端验证，先执行 `git status --short --branch` 和 `git --no-pager log --oneline -3`，再按需要 `git pull` 或切回 `main`。
- 本轮最终提交后，新 session 先运行：

  ```bash
  git status --short --branch
  git --no-pager log --oneline -3
  ```

- 如果需要在 5090D 上继续验证，先在远端 `/home/th5090d/Develop/personal_project/BabelEcho` 执行 `git status --short --branch`；如落后再 `git pull`。
- 提交前继续执行隐私扫描：`gitleaks`、`trufflehog`、简单 grep。
