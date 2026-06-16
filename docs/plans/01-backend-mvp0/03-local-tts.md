# 01.03 本地中文 TTS 接入计划

状态：`done`

日期：2026-06-16

父计划：`01-backend-mvp0`

## 目标

把 DeepSeek 已生成的中文口播稿接到 5090D 本地中文 TTS，验证：

```text
script/zh.json -> segments/*.wav -> output/audio.mp3
```

本计划只处理本地 TTS wrapper 和最小合成验证，不接真实播客来源、ASR、voice clone、后台服务或 macOS App。

## 方案

- 模型：`FunAudioLLM/CosyVoice2-0.5B`。
- 代码：`/home/th5090d/Develop/ai_tools/CosyVoice`。
- 模型目录：`/home/th5090d/Develop/ai_tools/CosyVoice/pretrained_models/CosyVoice2-0.5B`。
- 专用环境：`/home/th5090d/miniforge3/envs/babelecho-tts`。
- GPU 栈：`torch 2.11.0+cu130`、`torchaudio 2.11.0+cu130`、`torchcodec 0.14.0+cu130`。
- Pipeline 仍通过 `tts.provider: local_cli` 调用 wrapper，不让核心 pipeline 依赖 CosyVoice 内部 API。

## 关键实现

- 新增 `tools/cosyvoice_tts_wrapper.py`。
- 远端 runtime launcher：

  ```text
  /home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper
  ```

- 远端 ignored config：

  ```yaml
  tts:
    provider: local_cli
    command: "/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper"
    voice: "default-zh"
    output_format: "wav"
  ```

`default-zh` 当前使用 CosyVoice 仓库自带的 `asset/zero_shot_prompt.wav` 和示例 prompt text 作为固定中文声音。它不是原播客主播 voice clone。

## 注意事项

- 不要直接安装 CosyVoice 的完整 `requirements.txt`；其中写死了 `torch==2.3.1` 和 `cu121`，不适合 5090D。
- 5090D 已验证可用组合是 `torch 2.11.0+cu130`。
- `onnxruntime-gpu==1.18.0` 会提示找不到 `libcublasLt.so.11`，但当前 PyTorch 推理路径已能成功合成；后续若要优化 ONNX 推理，再单独处理 ONNX Runtime CUDA 依赖。
- 真实 runtime config、生成 wav/mp3、模型权重、conda env 不进入 git。

## 验收记录

2026-06-16 已在 5090D 验证：

- `AutoModel(model_dir="pretrained_models/CosyVoice2-0.5B")` 加载成功，采样率 `24000`。
- 直接调用 CosyVoice 生成 `/tmp/babelecho-cosyvoice-direct.wav`：
  - `pcm_s16le`
  - `24000 Hz`
  - `mono`
  - `5.640000s`
- 通过 `tts-wrapper` 生成 `/tmp/babelecho-wrapper-test.wav`：
  - `pcm_s16le`
  - `24000 Hz`
  - `mono`
  - `6.160000s`
- `babelecho synthesize --workspace workspace --run-id fixture-smoke --local-config workspace/config/local-cosyvoice.yaml` 成功运行。
- `workspace/runs/fixture-smoke/segments/manifest.json` 指向真实 TTS wav：

  ```text
  segments/0001.wav
  ```

- `workspace/runs/fixture-smoke/segments/0001.wav`：
  - `pcm_s16le`
  - `24000 Hz`
  - `mono`
  - `3.080000s`
- `babelecho assemble --workspace workspace --run-id fixture-smoke` 成功生成 `workspace/runs/fixture-smoke/output/audio.mp3`：
  - `mp3`
  - `24000 Hz`
  - `mono`
  - `3.144000s`

## 后续

下一步不要同时接 ASR 或 App。优先做两件事：

- 用更长的真实 transcript 片段评估中文播客听感和分段策略。
- 如需多说话人播客，再在 `speaker -> voice` 映射层扩展，不把它混入当前单声线 MVP 验证。
