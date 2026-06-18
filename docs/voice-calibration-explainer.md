# Voice Calibration Explainer

日期：2026-06-17

本文解释 BabelEcho 当前 CosyVoice2 音色校准中的两个问题：

- 为什么模型仓库只带两个参考 wav，但听起来可以生成多个有差异的样本。
- 之前所谓的“情感调整”具体是如何做出来的。

## 当前结论

MVP-1 当前固定角色路由已经更新：

```text
female_a -> CosyVoice-300M-SFT / 中文女
male_a   -> CosyVoice2-0.5B / calm prompt asset if present, fallback cross_lingual_prompt.wav / speed=1.1 / male_a-only text smoothing
female_b -> CosyVoice-300M-SFT / 英文女
male_b   -> CosyVoice-300M-SFT / 英文男
```

本文下方记录的是历史 CosyVoice2 单固定音色校准。当前 `male_a` 继续使用 CosyVoice2 cross-lingual 路线和 speed `1.1`；5090D 上如果存在 ignored runtime asset `workspace/config/tts-assets/male_a_cosyvoice2_calm_prompt.wav`，会优先使用它，否则回退到内置 `cross_lingual_prompt.wav`。`male_a` 还会在 wrapper 内做专用文本平稳化；其他三个角色不使用这一路，也不经过该文本平稳化。

历史试听样本：

```text
workspace/runs/voice-calibration-20260617-round2/d-cross-lingual-speed-100.mp3
```

这些试听产物在 ignored `workspace/runs/` 下，不进入 git。

## 两个参考 wav 不等于只能生成两种声音

5090D 当前 CosyVoice 仓库的 asset 目录只有两个内置参考音频：

```text
zero_shot_prompt.wav
cross_lingual_prompt.wav
```

这不等于模型只能生成两种完全固定、不可变化的音频。更准确地说，`prompt_wav` 是推理时的条件输入，不是一个简单的“音色库文件”。

CosyVoice2 本身已经在训练阶段学过大量语音、音色、韵律和说话方式。推理时，模型会从 `prompt_wav` 中提取参考音频里的说话人、风格、韵律等条件，再用这些条件去生成目标中文文本。

所以：

- 用 `zero_shot_prompt.wav` 做参考，会得到接近这个参考条件的一类声音。
- 用 `cross_lingual_prompt.wav` 做参考，会得到接近另一个参考条件的一类声音。
- 如果后续放入本地授权的男声或中性 `prompt_wav`，模型可以用新的参考音频作为条件，生成另一类固定音色。

因此，模型理论上可以生成更多可控音色，但前提是提供更多合适、授权、可长期使用的参考音频。当前我们没有提供新参考 wav，所以真正稳定可用的内置参考方向基本只有这两个。

## D/E/F 不是三种新音色

第二轮样本 D/E/F 使用的是同一个参考音频：

```text
cross_lingual_prompt.wav
```

同一个推理模式：

```text
mode = cross_lingual
```

区别只是 `speed` 参数：

```text
D: speed = 1.0
E: speed = 0.95
F: speed = 0.90
```

所以 D/E/F 严格来说不是三个不同 speaker，也不是三种新音色。它们是同一基准参考音色下的语速和节奏变体。

语速会影响停顿、拉长、句子节奏和播客感，因此听起来会有差异。但这不是换了一个说话人。

选择 D 在当时的含义是：

```text
当时 MVP-1 默认基线采用 cross_lingual_prompt.wav 这个参考音色，并使用正常速度 speed=1.0。
```

后续结论已经更新：`cross_lingual_prompt.wav` 只固定用于 `male_a`，并采用 speed `1.1`。

## C 和 D 为什么也可能略有差异

C 和 D 都是 `cross_lingual_prompt.wav` 路线，本质上不是两个不同音色。

它们可能仍有轻微差别，常见原因包括：

- TTS 生成本身可能有采样随机性，除非显式固定 seed。
- 文本前端可能会做 normalization 和 split，不同调用方式下切分、停顿可能略有变化。
- 即使同一个参考 wav、同一个文本，神经 TTS 输出也未必每次 bit-level 完全一致。
- 人耳会把轻微节奏和停顿差异感知成“更稳”或“更自然”。

这不代表 C/D 是两个不同 speaker。它们仍然是同一个 `cross_lingual_prompt.wav` 基准。

## 之前的情感是如何调整的

之前的“情感调整”没有训练模型，也没有微调模型权重，更不是设置一个明确的 `emotion=calm` 参数。它主要通过不同推理模式和条件输入，间接影响模型的语气、节奏和情绪饱满度。

第一轮候选样本可以理解为：

```text
A: zero_shot_prompt.wav + inference_zero_shot
B: zero_shot_prompt.wav + inference_instruct2 + 克制/平静/自然之类的文字指令
C: cross_lingual_prompt.wav + inference_cross_lingual
```

其中真正尝试用文字指令压情绪的是 B。

CosyVoice2 的 `inference_instruct2` 路线可以传入自然语言 instruction，例如让它更自然、平静、克制、适合播客。模型会把这个 instruction 当作条件之一，尝试影响生成时的表达方式。

但这不是硬规则。它更像告诉模型“请平静一点”，模型尝试往这个方向靠。它不是音频后期处理，也不是模型参数微调，所以稳定性和可控性有限。

## 为什么最后选了 cross-lingual 路线

C/D 不是靠文字 instruction 压情绪，而是换了参考条件：

```text
cross_lingual_prompt.wav + inference_cross_lingual
```

这条路线听起来更克制，主要原因是 `cross_lingual_prompt.wav` 提取出来的参考风格更适合播客。它不是因为我们显式设置了“少点情绪”的参数，而是参考音频条件本身比当前 zero-shot 女声 baseline 更少过度表演感。

后来的 D/E/F 只是继续调整 `speed`：

```text
D: speed = 1.0
E: speed = 0.95
F: speed = 0.90
```

语速也会影响情绪感知。慢一点可能更稳、更沉着，但太慢也可能显得拖、刻意或播音腔。最终选择 D，说明正常速度下的 cross-lingual 基准最自然。

## 当前可用的控制手段

当前我们实际用过的控制手段有三类：

```text
1. 换推理模式：zero_shot / instruct2 / cross_lingual
2. 换条件输入：prompt_wav / prompt_text / instruct_text
3. 调节参数：speed
```

当前没有做：

```text
- 没有训练模型
- 没有微调模型权重
- 没有 voice clone
- 没有后期情感编辑
- 没有生成真正的新 speaker 音色库
```

## 后续方向

不再继续围绕 CosyVoice 内置的两个 wav 反复微调。

2026-06-18 后，固定音色扩展的优先方向改为微调 `CosyVoice-300M-SFT`，目标是增加多个可长期使用的中文男声和中文女声。授权男声或中性参考 wav 仍可作为单点对比或备用路线，但不是当前优先方向。

这属于固定音色扩展，不是原主播 voice clone。
