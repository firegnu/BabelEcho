# 02.03 SFT Built-in 4-role Voice Profile 计划

状态：`done`

日期：2026-06-17

父计划：`02-real-podcasts`

## 目标

为 MVP-1 常见多人访谈节目提供固定中文多说话人基线，并固定自动选择规则：

```text
0/1 speaker -> CosyVoice2 cross_lingual
2+ speakers -> stable voice role -> CosyVoice-300M-SFT speaker id -> wav segment
```

## 结论

已选定 `sft_builtin_4role` 作为 MVP-1 多 speaker 基线。它不做原主播 voice clone，也不需要额外参考 wav；它只使用 `CosyVoice-300M-SFT` 自带 speaker id。

最终规则：

- `script/zh.json` 中检测到 0 或 1 个 distinct speaker：继续使用原默认模型 `CosyVoice2-0.5B` 的 `cross_lingual_prompt.wav + mode=cross_lingual + speed=1.0`。
- 检测到 2 个及以上 distinct speaker：自动切换到 `CosyVoice-300M-SFT` 的 `sft_builtin_4role`。

固定角色映射：

| Voice role | SFT speaker id | 用途 |
| --- | --- | --- |
| `female_a` | `中文女` | 第 1 个 speaker |
| `male_a` | `中文男` | 第 2 个 speaker |
| `female_b` | `英文女` | 第 3 个 speaker |
| `male_b` | `英文男` | 第 4 个 speaker |

用户试听结论：

- 路线 2，即 `中文女 / 中文男 / 英文女 / 英文男` 四个内置 speaker，说中文时区分度最大。
- 全部内置 speaker 筛选不适合作为主方案，因为 `日语男 / 粤语女 / 韩语女` 语种感明显。
- 只用 `中文女 / 中文男` 后处理拆四角色可以勉强分开，但听感不如四个内置 speaker。

## 范围

In:

- 新增 `tts.voice: sft_builtin_4role` profile。
- 默认配置仍可写 `tts.voice: default-zh`；`synthesize` 会按 speaker 数量自动选择实际 TTS voice。
- `synthesize` 按 `script/zh.json` 里 speaker 首次出现顺序分配角色：
  - 第 1 个 speaker -> `female_a`
  - 第 2 个 speaker -> `male_a`
  - 第 3 个 speaker -> `female_b`
  - 第 4 个 speaker -> `male_b`
  - 第 5 个及以后按四角色循环复用
- 同一个 speaker 在同一 run 中始终复用同一个 voice role。
- batch manifest item 记录每段 `voice_role`。
- wrapper 对 `sft_builtin_4role` 使用 `CosyVoice.inference_sft`，并对各段做固定响度处理。
- `male_a` 使用更明亮的 EQ 和响度处理，避免 `中文男` 偏闷、偏小。

Out:

- 不做 speaker gender detection。
- 不做自动角色命名或人工修正文件。
- 不做原主播 voice clone。
- 不做新模型训练或修改 `spk2info.pt`。

## 配置

默认配置仍然指向单音色基线；当 script 里只有 0/1 个 speaker 时使用它：

```yaml
tts:
  provider: local_cli
  command: "tts-wrapper"
  voice: "default-zh"
  mode: "cross_lingual"
  prompt_wav: "/path/to/CosyVoice/asset/cross_lingual_prompt.wav"
  speed: 1.0
```

多人播客不用手动切换 voice。只要 `script/zh.json` 中有 2 个及以上 speaker，`synthesize` 会自动使用：

```yaml
tts:
  provider: local_cli
  command: "tts-wrapper"
  voice: "sft_builtin_4role" # selected automatically for 2+ speakers
  cosyvoice_repo: "/home/th5090d/Develop/ai_tools/CosyVoice"
  speed: 1.0
```

`model_dir` 可显式配置；未配置时，wrapper 会默认使用：

```text
<cosyvoice_repo>/pretrained_models/CosyVoice-300M-SFT
```

## 验收记录

本机测试：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_synthesize.py tests/test_cosyvoice_wrapper.py -q
.conda/babelecho-dev/bin/python -m pytest -q
```

结果：

```text
15 passed
54 passed
```

已覆盖：

- 0/1 个 speaker 保持 `default-zh` / `CosyVoice2 cross_lingual`。
- 2 个及以上 speaker 会从 `default-zh` 自动切到 `sft_builtin_4role`。
- `synthesize` 按 speaker 首次出现顺序稳定分配四角色。
- `segments/manifest.json` 记录 `speaker` 和 `voice_role`。
- `tts-batch.json` 每个 item 写入 `voice_role`。
- `local_cli` 可以把 `cosyvoice_repo` 和 `model_dir` 传给 wrapper。
- `sft_builtin_4role` 不会误用 launcher 中指向 CosyVoice2 的 `COSYVOICE_MODEL_DIR`；未显式传 `--model-dir` 时默认使用 `<cosyvoice_repo>/pretrained_models/CosyVoice-300M-SFT`。
- wrapper 支持 `sft_builtin_4role` 并调用 `CosyVoice.inference_sft`。
- 5090D 临时 wrapper smoke 已通过：四个角色均生成 `22050 Hz`、mono wav。

试听样本保存在 ignored runtime 路径：

```text
workspace/runs/speaker-voice-four-role-20260617/
```

关键文件：

- `approach2-builtin-speakers/four-role-builtin-speakers.mp3`
- `approach2-all-speaker-screen/all-builtins-chinese-screen.mp3`
- `approach3-zh-postprocess/four-role-zh-postprocess.mp3`
