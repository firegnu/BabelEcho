# BabelEcho 交接

## 1. 当前状态

新 session 仍然先读 `resume-prompt.md`，再运行 `git status --short --branch` 和 `git log --oneline -3`。本文件只保留当前可接手摘要。

截至 2026-06-25：

- MVP-0、MVP-0.5、MVP-1 单 URL 自用链路都已完成。
- 当前主线是 Phase 2 Route B audio-first：音频输入 -> ASR -> diarization -> normalize -> DeepSeek adapt -> 本地 TTS -> publish。
- `03.03 Real Voice Profile Provider` 已收口：真实 speaker embedding、跨集相似度、private alias、人工 review contract、confirmed alias 到固定中文 voice role 的 map、单 run apply 命令、以及 `speaker_voices.mode=apply_voice_role_map` 显式配置开关均已实现并做过本机/5090D smoke。
- 说话人分离已做完第一版：5090D 上已用 OpenAI Whisper `small.en` + pyannote Community-1 跑通过真实 Practical AI、BBC、NPR、Podnews 等 audio-first 样本。
- Speaker embedding 已做完第一版：5090D 上用 SpeechBrain ECAPA 生成私有 192 维 embedding，写在 ignored run-local `workspace/runs/<run-id>/asr/voice-profiles/*.json`。
- 还没有进入原主播 voice clone：embedding 不喂给 TTS、不发布、不做人名身份识别、不自动影响默认音色。

## 2. 当前 TTS 规则

- 默认 `tts.voice=sft_builtin_4role`。
- `male_a` 走 `CosyVoice2-0.5B`，`cross_lingual + speed=1.1`，优先使用 ignored runtime asset `workspace/config/tts-assets/male_a_cosyvoice2_calm_prompt.wav`，缺失时回退 `cross_lingual_prompt.wav`。
- `female_a`、`female_b`、`male_b` 走 `CosyVoice-300M-SFT`。
- `speaker_voices.mode=apply_voice_role_map` 是显式 opt-in，只在配置时把 private confirmed alias map 应用到当前 run 的 `script/speaker-voices.json`；默认不启用。

## 3. 关键边界

- 不默认启用 alias map。
- 不把 speaker embedding 或 `asr/voice-profiles/*.json` 发布到 `workspace/published/`。
- 不把 embedding 用作 TTS conditioning。
- 不做真实身份识别。
- 不把当前工作误认为 voice clone；现在只是 voice clone 前的声纹和稳定中文角色映射基础设施。

## 4. 下一步建议

1. 执行 `docs/plans/03-audio-first-asr/04-stable-voice-role-validation.md`。
2. 用 5090D 上已有 Practical AI 五集样本，人工确认 `speaker_alias_001` / `speaker_alias_002` 是否真是跨集同一说话人。
3. 基于人工确认后的 private review，生成正式 private `voice-role-map`。
4. 选一集新的同节目音频，跑完整 Route B，并显式启用 `speaker_voices.mode=apply_voice_role_map`。
5. 试听验证重点：同一英文 speaker 在不同集里是否稳定落到同一中文固定音色，而不是是否像原主播。
6. 做 publish artifact 隐私检查，确认没有 `embedding_artifact`、`voice-profiles`、private alias/review/map 或 URL query/token 泄漏。
7. 上述验证通过后，再新建独立 voice clone feasibility spike。这个 spike 应独立于默认 TTS 路径，并先验证授权参考音频、中文输出质量、模型隔离和回滚边界。

## 5. 重要文件

- `resume-prompt.md`
- `docs/plans/README.md`
- `docs/plans/03-audio-first-asr/03-real-voice-profile-provider.md`
- `docs/plans/03-audio-first-asr/04-stable-voice-role-validation.md`
- `docs/Phase2双轨后端与静态前端架构.md`
- `docs/5090D远程测试流程.md`
- `src/babelecho/voice_profile.py`
- `src/babelecho/speaker_similarity.py`
- `src/babelecho/speaker_aliases.py`
- `src/babelecho/speaker_alias_review.py`
- `src/babelecho/speaker_voice_role_map.py`
- `src/babelecho/speaker_voices.py`
- `tools/speaker_embedding_wrapper.py`

## 6. 验证记录

最近代码提交：

- `1c910f5 docs: record speaker voice map config smoke`
- `36bd740 feat: add speaker voice map config mode`
- `b2a1879 docs: record voice role map apply smoke`

本次文档同步是 docs-only；如继续改代码，使用项目内 `.conda/babelecho-dev`，不要使用 conda `base`。提交前仍需检查 secrets，特别是 server 地址、API key、token、runtime config、`workspace/runs/`、生成音频和模型缓存。
