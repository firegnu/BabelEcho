# 02.03 SFT Built-in 4-role Voice Profile 计划

状态：`done`

日期：2026-06-17

父计划：`02-real-podcasts`

## 目标

为 MVP-1 常见多人访谈节目提供固定中文多说话人基线，并固定自动选择规则：

```text
0/1 speaker without explicit gender marker -> CosyVoice-300M-SFT female_a
1 speaker labeled male/男 -> CosyVoice-300M-SFT male_b
1 speaker labeled female/女 -> CosyVoice-300M-SFT female_a
2+ speakers -> stable voice role -> CosyVoice-300M-SFT speaker id -> wav segment
```

## 结论

已选定 `sft_builtin_4role` 作为 MVP-1 单模型 TTS 基线。它不做原主播 voice clone，也不需要额外参考 wav；运行默认只使用 `CosyVoice-300M-SFT` 自带 speaker id，不再要求部署 `CosyVoice2-0.5B`。

最终规则：

- `script/zh.json` 中检测到 0 或 1 个 distinct speaker，且没有显式性别标签：使用 `female_a`。
- 单个 speaker 标签包含 `male` 或 `男`：使用 `male_b`。
- 单个 speaker 标签包含 `female` 或 `女`：使用 `female_a`。
- 检测到 2 个及以上 distinct speaker：按首次出现顺序映射到四个固定角色。

固定角色映射：

| Voice role | SFT speaker id | 用途 |
| --- | --- | --- |
| `female_a` | `中文女` | 第 1 个 speaker |
| `male_b` | `英文男` | 第 2 个 speaker |
| `female_b` | `英文女` | 第 3 个 speaker |
| `male_a` | `中文男` | 第 4 个 speaker |

用户试听结论：

- 路线 2，即 `中文女 / 中文男 / 英文女 / 英文男` 四个内置 speaker，说中文时区分度最大。
- 全部内置 speaker 筛选不适合作为主方案，因为 `日语男 / 粤语女 / 韩语女` 语种感明显。
- 只用 `中文女 / 中文男` 后处理拆四角色可以勉强分开，但听感不如四个内置 speaker。

## 范围

In:

- 新增 `tts.voice: sft_builtin_4role` profile。
- 默认配置写 `tts.voice: sft_builtin_4role`；`synthesize` 也会把旧的 `default-zh` 配置覆盖到 `sft_builtin_4role`，避免运行时依赖 CosyVoice2。
- 单个 speaker 标签包含 `male` / `男` 时固定分配到 `male_b`；包含 `female` / `女` 或没有显式性别标签时固定分配到 `female_a`。
- `synthesize` 按 `script/zh.json` 里 speaker 首次出现顺序分配角色：
  - 第 1 个 speaker -> `female_a`
  - 第 2 个 speaker -> `male_b`
  - 第 3 个 speaker -> `female_b`
  - 第 4 个 speaker -> `male_a`
  - 第 5 个及以后按四角色循环复用
- 同一个 speaker 在同一 run 中始终复用同一个 voice role。
- batch manifest item 记录每段 `voice_role`。
- wrapper 对 `sft_builtin_4role` 使用 `CosyVoice.inference_sft`，并对各段做固定响度处理。
- 真实点播 run 中 `male_a` 作为男一偏低沉；当前男声优先顺序改为 `male_b -> male_a`。
- 5090D 短预览 `male-role-swap-preview-20260618` 已真实生成 `male_b / male_a / male_b / male_a`，输出 MP3 为 `17.728435s`。

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
20 passed
58 passed
```

已覆盖：

- 0/1 个 speaker 且没有显式性别标签时使用 `sft_builtin_4role` / `female_a`。
- 单个 speaker 标签包含 `male` / `男` 时使用 `sft_builtin_4role` / `male_b`。
- 单个 speaker 标签包含 `female` / `女` 时使用 `sft_builtin_4role` / `female_a`。
- 2 个及以上 speaker 会使用 `sft_builtin_4role` 的四角色映射。
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
