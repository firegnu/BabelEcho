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
  voice: "default-zh"
  output_format: "wav"
```

## Commands

Preferred MVP-0.5 self-use entry:

```bash
export PYTHON=.conda/babelecho-dev/bin/python
export WORKSPACE=/path/to/babelecho-workspace
export RUN_ID=first-episode
export SOURCE_CONFIG=$WORKSPACE/sources/hardcoded.yaml
export LOCAL_CONFIG=$WORKSPACE/config/local.yaml

$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --source-config "$SOURCE_CONFIG" \
  --local-config "$LOCAL_CONFIG"
```

The command runs:

```text
ingest -> normalize -> adapt -> synthesize -> assemble -> publish
```

It also runs basic checks after generated artifacts are available:

- after `adapt`: `script/zh.json` exists, has segments, and every segment has nonempty text below the configured length limit.
- after `synthesize`: `segments/manifest.json` exists and every listed wav file exists and is nonempty.
- after `assemble`: `output/audio.mp3` exists and `ffprobe` can read codec, duration, sample rate, and channel count.

To resume after editing or preserving earlier artifacts, use `--from-stage`:

```bash
$PYTHON -m babelecho run \
  --workspace "$WORKSPACE" \
  --run-id "$RUN_ID" \
  --source-config "$SOURCE_CONFIG" \
  --local-config "$LOCAL_CONFIG" \
  --from-stage synthesize
```

Supported values are `ingest`, `normalize`, `adapt`, `synthesize`, `assemble`, and `publish`. For example, `--from-stage synthesize` reuses the existing `script/zh.json`, which is useful after manually editing the Chinese script or avoiding another paid LLM call.

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

## Local Fixture Test

Use this on the MacBook or 5090D to verify the pure pipeline without real LLM or TTS execution:

```bash
.conda/babelecho-dev/bin/python -m pytest -v
```
