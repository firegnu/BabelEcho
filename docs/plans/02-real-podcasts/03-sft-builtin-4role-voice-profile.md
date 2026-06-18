# 02.03 SFT Built-in 4-role Voice Profile 计划

状态：`done`

日期：2026-06-17

父计划：`02-real-podcasts`

## 目标

为 MVP-1 常见多人访谈节目提供固定中文多说话人基线，并固定自动选择规则：

```text
0/1 speaker without explicit gender marker -> female_a -> CosyVoice-300M-SFT
1 speaker labeled male/男 -> male_a -> CosyVoice2 cross_lingual speed 1.1
1 speaker labeled female/女 -> female_a -> CosyVoice-300M-SFT
2+ speakers -> stable voice role -> role-specific local TTS backend -> wav segment
```

## 结论

已选定 `sft_builtin_4role` 作为 MVP-1 固定角色 profile。它不做原主播 voice clone；角色分配仍稳定使用 `female_a / male_a / female_b / male_b`，但渲染 backend 已改为混合本地模型：`male_a` 使用 `CosyVoice2-0.5B` 的 `cross_lingual` 路线、`cross_lingual_prompt.wav` 和 `speed=1.1`，其余三个角色继续使用 `CosyVoice-300M-SFT`。

最终规则：

- `script/zh.json` 中检测到 0 或 1 个 distinct speaker，且没有显式性别标签：使用 `female_a`。
- 单个 speaker 标签包含 `male` 或 `男`：使用 `male_a`。
- 单个 speaker 标签包含 `female` 或 `女`：使用 `female_a`。
- 检测到 2 个及以上 distinct speaker：按首次出现顺序映射到四个固定角色。

固定角色映射：

| Voice role | Rendering backend | 用途 |
| --- | --- | --- |
| `female_a` | `CosyVoice-300M-SFT` / `中文女` | 第 1 个 speaker |
| `male_a` | `CosyVoice2-0.5B` / `cross_lingual` / `speed=1.1` | 第 2 个 speaker 或显式男声 |
| `female_b` | `CosyVoice-300M-SFT` / `英文女` | 第 3 个 speaker |
| `male_b` | `CosyVoice-300M-SFT` / `英文男` | 第 4 个 speaker |

用户试听结论：

- 路线 2，即 `中文女 / 中文男 / 英文女 / 英文男` 四个内置 speaker，说中文时区分度最大。
- 全部内置 speaker 筛选不适合作为主方案，因为 `日语男 / 粤语女 / 韩语女` 语种感明显。
- 只用 `中文女 / 中文男` 后处理拆四角色可以勉强分开，但听感不如四个内置 speaker。

## 范围

In:

- 新增 `tts.voice: sft_builtin_4role` profile。
- 默认配置写 `tts.voice: sft_builtin_4role`；`synthesize` 也会把旧的 `default-zh` 配置覆盖到 `sft_builtin_4role`。
- 单个 speaker 标签包含 `male` / `男` 时固定分配到 `male_a`；包含 `female` / `女` 或没有显式性别标签时固定分配到 `female_a`。
- `synthesize` 按 `script/zh.json` 里 speaker 首次出现顺序分配角色：
  - 第 1 个 speaker -> `female_a`
  - 第 2 个 speaker -> `male_a`
  - 第 3 个 speaker -> `female_b`
  - 第 4 个 speaker -> `male_b`
  - 第 5 个及以后按四角色循环复用
- 同一个 speaker 在同一 run 中始终复用同一个 voice role。
- batch manifest item 记录每段 `voice_role`。
- wrapper 对 `sft_builtin_4role` 按 `voice_role` 选择 backend：`male_a` 调用 `AutoModel.inference_cross_lingual`，其他角色调用 `CosyVoice.inference_sft`，并统一输出为 `22050 Hz` mono wav。
- 真实点播 run 中 SFT `male_a` 作为男一偏低沉；后续混合四角色 speed `1.1` 预览中用户确认 `male_a` 改走 CosyVoice2 更可接受。
- 5090D 短预览 `four-role-hybrid-cosyvoice2-male-a-speed11-20260618` 已验证最终听感；相关试听文件在 ignored `workspace/runs/` 下。

Out:

- 不做声纹或语义 speaker gender detection；只识别 `speaker` 标签中的显式 `male` / `男` / `female` / `女` 标记。
- 不做自动角色命名或人工修正文件。
- 不做原主播 voice clone。
- 不做新模型训练或修改 `spk2info.pt`。

## 配置

默认配置指向 300M SFT：

```yaml
tts:
  provider: local_cli
  command: "tts-wrapper"
  voice: "sft_builtin_4role"
  cosyvoice_repo: "/path/to/CosyVoice"
  speed: 1.0
```

旧配置中如果仍写 `voice: "default-zh"`，`synthesize` 会自动覆盖为：

```yaml
tts:
  provider: local_cli
  command: "tts-wrapper"
  voice: "sft_builtin_4role"
  cosyvoice_repo: "/home/th5090d/Develop/ai_tools/CosyVoice"
  speed: 1.0
```

`model_dir` 可显式配置 SFT 角色模型；未配置时，wrapper 会默认使用：

```text
<cosyvoice_repo>/pretrained_models/CosyVoice-300M-SFT
```

`male_a` 使用 wrapper 内置的 CosyVoice2 默认：

```text
<cosyvoice_repo>/pretrained_models/CosyVoice2-0.5B
<cosyvoice_repo>/asset/cross_lingual_prompt.wav
speed=1.1
```

## 验收记录

本机测试：

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_cosyvoice_wrapper.py -q
.conda/babelecho-dev/bin/python -m pytest -q
```

结果：

```text
10 passed
111 passed
```

已覆盖：

- 0/1 个 speaker 且没有显式性别标签时使用 `sft_builtin_4role` / `female_a`。
- 单个 speaker 标签包含 `male` / `男` 时使用 `sft_builtin_4role` / `male_a`。
- 单个 speaker 标签包含 `female` / `女` 时使用 `sft_builtin_4role` / `female_a`。
- 2 个及以上 speaker 会使用 `sft_builtin_4role` 的四角色映射。
- `synthesize` 按 speaker 首次出现顺序稳定分配四角色。
- `segments/manifest.json` 记录 `speaker` 和 `voice_role`。
- `tts-batch.json` 每个 item 写入 `voice_role`。
- `local_cli` 可以把 `cosyvoice_repo` 和 `model_dir` 传给 wrapper。
- `sft_builtin_4role` 不会把 `COSYVOICE_MODEL_DIR` 用作 SFT 角色模型；未显式传 `--model-dir` 时 SFT 角色默认使用 `<cosyvoice_repo>/pretrained_models/CosyVoice-300M-SFT`。
- wrapper 支持 `sft_builtin_4role` 内部混合路由：`male_a` 调用 `AutoModel.inference_cross_lingual`，默认 `CosyVoice2-0.5B` / `cross_lingual_prompt.wav` / `speed=1.1`；`female_a / female_b / male_b` 调用 `CosyVoice.inference_sft`。
- 5090D 历史 wrapper smoke 已通过：四个 SFT 角色均可生成 `22050 Hz`、mono wav；最终混合路由还需用代码路径跑一次真实预览。

试听样本保存在 ignored runtime 路径：

```text
workspace/runs/speaker-voice-four-role-20260617/
```

关键文件：

- `approach2-builtin-speakers/four-role-builtin-speakers.mp3`
- `approach2-all-speaker-screen/all-builtins-chinese-screen.mp3`
- `approach3-zh-postprocess/four-role-zh-postprocess.mp3`
