# Backend MVP-0 Runbook

## Purpose

Run one transcript-first episode through the MVP-0 pipeline on the 5090D Ubuntu machine.

Current validation track: DeepSeek API handles LLM adaptation, and the 5090D handles local TTS, assembly, and publishing. This is a temporary hybrid track; the later all-local track replaces DeepSeek with a local vLLM endpoint.

## Preconditions

- A project conda environment exists. Do not install into `base`.
- `babelecho` is installed into that project environment with `pip install -e . --no-build-isolation`.
- For the current hybrid track, `DEEPSEEK_API_KEY` is set in the shell and the local config points LLM adaptation at DeepSeek.
- For the later all-local track, vLLM is running locally and serving the configured instruct model.
- TTS wrapper command from `workspace/config/local.yaml` is available in `PATH`.
- `ffmpeg` is installed.
- Source config points to a complete transcript.

## One-Time Environment Setup

```bash
conda create -p ./.conda/babelecho-dev python=3.12 pip setuptools wheel pytest pyyaml -y
.conda/babelecho-dev/bin/python -m pip install -e . --no-build-isolation
```

## Commands

```bash
export PYTHON=.conda/babelecho-dev/bin/python
export WORKSPACE=/path/to/babelecho-workspace
export RUN_ID=first-episode
export SOURCE_CONFIG=$WORKSPACE/sources/hardcoded.yaml
export LOCAL_CONFIG=$WORKSPACE/config/local.yaml
export DEEPSEEK_API_KEY='<set in shell only>'

$PYTHON -m babelecho ingest --workspace "$WORKSPACE" --run-id "$RUN_ID" --source-config "$SOURCE_CONFIG"
$PYTHON -m babelecho normalize --workspace "$WORKSPACE" --run-id "$RUN_ID" --raw-transcript "$WORKSPACE/runs/$RUN_ID/transcript/raw.vtt"
$PYTHON -m babelecho adapt --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
$PYTHON -m babelecho synthesize --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
$PYTHON -m babelecho assemble --workspace "$WORKSPACE" --run-id "$RUN_ID"
$PYTHON -m babelecho publish --workspace "$WORKSPACE" --run-id "$RUN_ID" --local-config "$LOCAL_CONFIG"
```

## Expected Outputs

- `$WORKSPACE/runs/$RUN_ID/transcript/normalized.json`
- `$WORKSPACE/runs/$RUN_ID/script/zh.json`
- `$WORKSPACE/runs/$RUN_ID/segments/manifest.json`
- `$WORKSPACE/runs/$RUN_ID/output/audio.mp3`
- `$WORKSPACE/runs/$RUN_ID/publish/feed.xml`
- `$WORKSPACE/runs/$RUN_ID/publish/episodes/$RUN_ID/audio.mp3`

## Local Fixture Test

Use this on the MacBook or 5090D to verify the pure pipeline without real LLM, TTS, or ffmpeg execution:

```bash
.conda/babelecho-dev/bin/python -m pytest -v
```
