# 03.04 Stable Voice Role Validation Plan

状态：ready

日期：2026-06-25

父计划：`03-audio-first-asr`

## 目标

验证 Route B 已有的 private speaker alias -> fixed Chinese voice role 链路是否适合自用：同一节目里的同一英文 speaker，跨集转换后应稳定落到同一个中文固定音色。

这一步仍不是 voice clone。它只验证“跨集同一说话人稳定分配中文角色”，不要求中文声音像原主播。

## 范围

### In

- 使用 5090D 上已有 Practical AI 五集真实样本和 alias candidates。
- 人工确认 private alias review 中的 candidate。
- 生成 confirmed alias 到 `female_a / male_a / female_b / male_b` 的 private voice-role map。
- 选择一集新的同节目音频，显式启用 `speaker_voices.mode=apply_voice_role_map` 跑完整 Route B。
- 做试听和 privacy artifact 检查。

### Out

- 不默认启用 alias map。
- 不把 embedding、voice-profiles、alias review 或 voice-role map 发布到 `workspace/published/`。
- 不做人名身份识别。
- 不把 embedding 喂给 TTS。
- 不做原主播 voice clone。
- 不改变 Route A transcript-first / YouTube / RSS / iTunes / PodcastIndex / episode page 已验证路径。

## 前置条件

- `03.01` audio-first ASR / diarization 已完成。
- `03.02` voice profile provider contract 已完成。
- `03.03` real voice profile provider 已完成。
- 5090D 已有 ignored runtime configs、DeepSeek key、本地 ASR/diarization/voice-profile/TTS 环境。
- 继续遵守 MacBook edit/test -> commit/push -> 5090D `git pull --ff-only` -> remote validation 的协作方式。

## 执行步骤

1. 在 5090D 私有 workspace 中打开 `workspace/runs/speaker-alias-review-practicalai-real-five-episodes-20260620.json`，人工确认 `speaker_alias_001` / `speaker_alias_002` 的状态。
2. 把确认后的 review 另存为新的 ignored private review 文件，不提交。
3. 运行 `babelecho speaker-profiles voice-roles --review ... --output-json ...` 生成 private voice-role map；如已有手工映射，用 `--existing-map` 保持旧 alias 的中文音色不漂移。
4. 选择一集新的 Practical AI 或同节目音频，先跑 `babelecho audio convert ... --to-stage normalize`，确认 `transcript/quality.json` 为 `safe_to_adapt` 或人工认可的 `inspect_first`。
5. 用包含 `speaker_voices.mode: apply_voice_role_map` 和 `speaker_voices.voice_role_map: <private-map>` 的 ignored local config 跑到 `publish`。
6. 检查当前 run 的 `script/speaker-voices.json`，确认只写入目标 run 中匹配 confirmed alias 的 speaker，不覆盖未确认 speaker。
7. 试听最终 MP3，记录同一 speaker 是否跨集稳定落到同一中文 voice role。
8. 检查 `workspace/published/` 下的 `artifact.json`、`speaker-profiles.json`、`transcript.zh.json` 和 episode 目录，确认没有 `embedding_artifact`、`voice-profiles`、private alias/review/map、URL query 或 token。

## 验收标准

- 至少一集新的同节目 audio-first run 使用 private confirmed voice-role map 成功跑到 `publish`。
- `script/speaker-voices.json` 中 recurring speaker 的中文 voice role 与已确认 alias map 一致。
- 未确认 alias 不影响 TTS。
- `workspace/published/` 不包含 embedding 文件、embedding path、alias/review/map 私有文件或 URL query/token。
- 试听结果证明“稳定中文角色映射”对自用有价值，或者明确记录为什么不够好。

## 风险和分支处理

- 如果人工确认发现 alias candidate 有误配，先调高阈值或拆分 review，不进入 voice clone。
- 如果新 episode 的 diarization/ASR 质量不稳定，先停在 `normalize` 修质量门或换样本，不强行进入 TTS。
- 如果 stable role 听感价值不足，优先调整固定中文角色或 300M SFT 微调方向，不直接跳到原主播 clone。
- 如果 privacy 检查发现私有 artifact 泄漏，先修 publish 边界再继续。

## 后续

本计划通过后，才新建独立 voice clone feasibility spike。该 spike 需要先回答授权参考音频、模型隔离、中文输出质量、GPU 成本、回滚方式和隐私边界，不应直接接入默认 TTS 路径。
