# Backend MVP-0 Runbook

## Purpose

Run one transcript-first episode through the MVP-0 pipeline on the 5090D Ubuntu machine.

Current validation track: DeepSeek API handles LLM adaptation, and the 5090D handles local TTS, assembly, and publishing. This is a temporary hybrid track; the later all-local track replaces DeepSeek with a local vLLM endpoint.

## Preconditions

- A project conda environment exists. Do not install into `base`.
- `babelecho` is installed into that project environment with `pip install -e . --no-build-isolation`.
- For the current hybrid track, `workspace/config/deepseek.env` exists locally, is ignored by git, and contains the DeepSeek API key.
- For the later all-local track, vLLM is running locally and serving the configured instruct model.
- For local TTS on the 5090D, the `babelecho-tts` conda env exists and the TTS wrapper command from `workspace/config/local.yaml` is available.
- `ffmpeg` is installed.
- Source config points to a complete transcript.

## One-Time Environment Setup

```bash
conda create -p ./.conda/babelecho-dev python=3.12 pip setuptools wheel pytest pyyaml -y
.conda/babelecho-dev/bin/python -m pip install -e . --no-build-isolation
```

## 5090D Local TTS Setup

The verified 5090D setup uses a dedicated conda env:

```text
/home/th5090d/miniforge3/envs/babelecho-tts
```

Keep its GPU stack on the validated CUDA 13 path:

```text
torch 2.11.0+cu130
torchaudio 2.11.0+cu130
torchcodec 0.14.0+cu130
```

Do not install CosyVoice's full `requirements.txt` directly, because it pins `torch==2.3.1` and `cu121`.

The runtime wrapper command is:

```text
/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper
```

An ignored local config can point at it:

```yaml
tts:
  provider: local_cli
  command: "/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper"
  voice: "sft_builtin_4role"
  cosyvoice_repo: "/home/th5090d/Develop/ai_tools/CosyVoice"
  speed: 1.0
  output_format: "wav"
```

For MVP-1, the deployment default keeps the `sft_builtin_4role` role profile and
uses hybrid local rendering:

- 0/1 distinct speaker without an explicit gender marker: use `female_a`.
- 1 distinct speaker labeled with `male` or `男`: use `male_a`.
- 1 distinct speaker labeled with `female` or `女`: use `female_a`.
- 2+ distinct speakers: use first-appearance mapping across the four roles.
- Render `male_a` with `CosyVoice2-0.5B` cross-lingual synthesis,
  speed `1.1`, the ignored calm prompt asset
  `workspace/config/tts-assets/male_a_cosyvoice2_calm_prompt.wav` when present,
  and a male_a-only text smoothing pass. If the calm prompt asset is missing,
  the wrapper falls back to `<cosyvoice_repo>/asset/cross_lingual_prompt.wav`.
- Render `female_a`, `female_b`, and `male_b` with `CosyVoice-300M-SFT`.

The profile is equivalent to this effective config:

```yaml
tts:
  provider: local_cli
  command: "/home/th5090d/miniforge3/envs/babelecho-tts/bin/tts-wrapper"
  voice: "sft_builtin_4role"
  cosyvoice_repo: "/home/th5090d/Develop/ai_tools/CosyVoice"
  speed: 1.0
  output_format: "wav"
```

This profile maps script speakers by first appearance to `female_a`, `male_a`,
`female_b`, and `male_b`. `female_a`, `female_b`, and `male_b` are backed by
the 300M SFT speaker ids `中文女`, `英文女`, and `英文男`; `male_a` is backed by
the CosyVoice2 cross-lingual reference path chosen in the speed `1.1` preview.
It is fixed-role synthesis, not original-host voice cloning.
For scripts with no speaker labels, such as many YouTube caption runs, set
`speaker_voices.default_voice_role` to force the run-level default before ASR or
voiceprint-based speaker detection exists:

```yaml
speaker_voices:
  default_voice_role: "male_a"
```

This override only applies when the script has zero named speakers; it does not
replace existing `speaker -> voice_role` mappings.
If `model_dir` is not set, the wrapper defaults to
`<cosyvoice_repo>/pretrained_models/CosyVoice-300M-SFT` for the SFT roles.
For `male_a`, the wrapper defaults to
`<cosyvoice_repo>/pretrained_models/CosyVoice2-0.5B` and
`workspace/config/tts-assets/male_a_cosyvoice2_calm_prompt.wav` when that
ignored runtime asset exists; otherwise it uses
`<cosyvoice_repo>/asset/cross_lingual_prompt.wav`.
The SFT profile intentionally does not reuse `COSYVOICE_MODEL_DIR` from the
launcher for the SFT roles.

Later voice expansion should prefer fine-tuning `CosyVoice-300M-SFT` to add
multiple stable Chinese male/female fixed roles. That does not change the
current MVP-1 runtime route unless a tuned model is explicitly selected and
validated by listening tests.

For `local_cli` synthesis, BabelEcho writes a `segments/tts-batch.json` file and
starts the wrapper once per `synthesize` stage. The wrapper lazily loads the
needed backend model or models, then loops over the segment text files to write
`segments/<id>.wav`. The older single-segment wrapper form still works for
direct smoke tests.

## Commands

Preferred MVP-0.5 self-use entry:

```bash
export PYTHON=.conda/babelecho-dev/bin/python
export WORKSPACE=/path/to/babelecho-workspace
export RUN_ID=first-episode
export TRANSCRIPT=/path/to/episode.vtt
export LOCAL_CONFIG=$WORKSPACE/config/local.yaml

$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --transcript-file "$TRANSCRIPT" \
  --title "Episode Title" \
  --local-config "$LOCAL_CONFIG"
```

`--transcript-file` accepts local `.txt`, `.vtt`, and `.srt` transcript files. It is the preferred manual self-use entry because it does not require writing a source YAML file.

The older source config entry remains supported:

```bash
export SOURCE_CONFIG=$WORKSPACE/sources/hardcoded.yaml

$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --source-config "$SOURCE_CONFIG" \
  --local-config "$LOCAL_CONFIG"
```

MVP-1 also supports a narrow RSS transcript entry. The feed must expose a
complete episode transcript through `podcast:transcript`; missing transcripts
fail clearly and do not trigger ASR:

```bash
$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --podcast-feed "https://example.com/podcast/feed.xml" \
  --episode-url "https://example.com/podcast/episodes/1" \
  --local-config "$LOCAL_CONFIG"
```

`--episode-url` is optional. When present, it matches an RSS item by `link`,
`guid`, or `enclosure url`. Without it, BabelEcho uses the first item that has a
`podcast:transcript` URL.

The command runs:

```text
ingest -> normalize -> adapt -> synthesize -> assemble -> publish
```

If `overrides.path` is configured, `run` applies script overrides between `adapt` and `synthesize`.

For preview-first self-use, stop after `adapt`, inspect the Chinese script, then resume from `synthesize`:

```bash
$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --transcript-file "$TRANSCRIPT" \
  --title "Episode Title" \
  --local-config "$LOCAL_CONFIG" \
  --to-stage adapt

$PYTHON -m babelecho script --workspace "$WORKSPACE" --run-id "$RUN_ID"

$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --transcript-file "$TRANSCRIPT" \
  --title "Episode Title" \
  --local-config "$LOCAL_CONFIG" \
  --from-stage synthesize
```

It also runs basic checks after generated artifacts are available:

- after `adapt`: `script/zh.json` exists, has segments, and every segment has nonempty text below the configured length limit.
- after `synthesize`: `segments/tts-batch.json` may exist for `local_cli`; `segments/manifest.json` exists and every listed wav file exists and is nonempty.
- after `assemble`: `output/audio.mp3` exists and `ffprobe` can read codec, duration, sample rate, and channel count.
- after `publish`: run-local publish artifacts are copied to the stable private feed directory under `$WORKSPACE/published/`.

Each `run` writes status to:

```text
$WORKSPACE/runs/$RUN_ID/run.json
```

The file records the input, `from_stage`, `to_stage`, each stage status, failed stage, error string, and known output paths. Use it first when a run fails.

To preview the Chinese script before TTS:

```bash
$PYTHON -m babelecho script --workspace "$WORKSPACE" --run-id "$RUN_ID"
```

The command prints the `script/zh.json` path, numbered script segments, and the `--from-stage synthesize` resume hint. Edit `$WORKSPACE/runs/$RUN_ID/script/zh.json` manually, then resume from `synthesize`.

To apply local terminology or pronunciation overrides before TTS, copy the tracked example to an ignored local config and enable it from `local.yaml`:

```bash
cp workspace/config/overrides.example.yaml "$WORKSPACE/config/overrides.yaml"
```

```yaml
overrides:
  path: "workspace/config/overrides.yaml"
```

Overrides are exact text replacements applied to `$WORKSPACE/runs/$RUN_ID/script/zh.json`. They are intentionally simple and local: use them for names, acronyms, and phrases that should be rewritten before TTS. When configured, `babelecho run` applies them automatically before `synthesize`.

To apply overrides manually after previewing or editing the script:

```bash
$PYTHON -m babelecho overrides \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --local-config "$LOCAL_CONFIG"
```

To resume after editing or preserving earlier artifacts, use `--from-stage`:

```bash
$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --transcript-file "$TRANSCRIPT" \
  --local-config "$LOCAL_CONFIG" \
  --from-stage synthesize
```

Supported `--from-stage` and `--to-stage` values are `ingest`, `normalize`, `adapt`, `synthesize`, `assemble`, and `publish`. For example, `--to-stage adapt` stops before TTS for script review, and `--from-stage synthesize` reuses the existing `script/zh.json`, which is useful after manually editing the Chinese script or avoiding another paid LLM call.

Individual stage commands remain useful for debugging:

```bash
export PYTHON=.conda/babelecho-dev/bin/python
export WORKSPACE=/path/to/babelecho-workspace
export RUN_ID=first-episode
export SOURCE_CONFIG=$WORKSPACE/sources/hardcoded.yaml
export LOCAL_CONFIG=$WORKSPACE/config/local.yaml

$PYTHON -m babelecho ingest --workspace "$WORKSPACE" --run-id "$RUN_ID" --source-config "$SOURCE_CONFIG"
$PYTHON -m babelecho normalize --workspace "$WORKSPACE" --run-id "$RUN_ID" --raw-transcript "$WORKSPACE/runs/$RUN_ID/transcript/raw.vtt"
$PYTHON -m babelecho adapt --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
$PYTHON -m babelecho overrides --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
$PYTHON -m babelecho synthesize --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
$PYTHON -m babelecho assemble --workspace "$WORKSPACE" --run-id "$RUN_ID"
$PYTHON -m babelecho publish --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
```

You can run checks independently:

```bash
$PYTHON -m babelecho check --workspace "$WORKSPACE" --run-id "$RUN_ID"
```

To check only selected artifacts:

```bash
$PYTHON -m babelecho check \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --checks script segments \
  --max-script-chars 1200
```

## Expected Outputs

- `$WORKSPACE/runs/$RUN_ID/transcript/normalized.json`
- `$WORKSPACE/runs/$RUN_ID/script/zh.json`
- `$WORKSPACE/runs/$RUN_ID/segments/manifest.json`
- `$WORKSPACE/runs/$RUN_ID/output/audio.mp3`
- `$WORKSPACE/runs/$RUN_ID/publish/feed.xml`
- `$WORKSPACE/runs/$RUN_ID/publish/episodes/$RUN_ID/audio.mp3`
- `$WORKSPACE/runs/$RUN_ID/run.json`
- `$WORKSPACE/published/feed.xml`
- `$WORKSPACE/published/episodes/$RUN_ID/audio.mp3`

## Local Fixture Test

Use this on the MacBook or 5090D to verify the pure pipeline without real LLM or TTS execution:

```bash
.conda/babelecho-dev/bin/python -m pytest -v
```
