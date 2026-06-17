# BabelEcho

BabelEcho is a local-first pipeline for converting English podcast transcripts into Chinese podcast audio.

MVP-0 and MVP-0.5 are complete. MVP-1 has selected the default fixed Chinese podcast voice baseline: `cross_lingual_prompt.wav + mode=cross_lingual + speed=1.0`. The current focus is real podcast sources and common interview workflows beyond manually supplied transcripts.

Current validation track: use DeepSeek API for the LLM adaptation baseline, then use the 5090D for local Chinese TTS. This is a temporary hybrid path to validate script quality and audio synthesis before replacing the cloud LLM with a local model.

## Current Scope

The current pipeline supports:

- Transcript-first input only.
- Local-first execution, with a temporary DeepSeek API exception for the LLM adaptation baseline.
- Stage-by-stage Python CLI commands.
- One-command pipeline orchestration with `babelecho run`.
- Manual transcript input with `babelecho run --transcript-file`.
- Partial pipeline execution with `babelecho run --to-stage ...` and resume with `--from-stage ...`.
- Chinese script preview with `babelecho script` before TTS.
- Local terminology and pronunciation overrides before TTS with exact replacements.
- Basic artifact checks with `babelecho check`.
- Run status tracking in `workspace/runs/<run-id>/run.json`.
- File-based intermediate artifacts under `workspace/runs/<run-id>/`.
- Fixture tests for the full pure pipeline.
- Static podcast output under both `workspace/runs/<run-id>/publish/` and stable `workspace/published/`.

MVP-0 does not support:

- ASR from audio-only episodes.
- Original host voice cloning.
- Podcast subscription scanning.
- Web management UI.
- macOS app playback.

Those are intentionally deferred until the transcript-first pipeline is stable.

## Repository Layout

```text
docs/
  architecture.md
  backend-mvp.md
  backend-mvp0-tech-stack.md
  backend-mvp0-runbook.md
  source-ingestion-research.md
src/babelecho/
  cli.py
  ingest.py
  transcript.py
  adapt.py
  synthesize.py
  audio.py
  publish.py
  script.py
  overrides.py
  status.py
tests/
workspace/
  config/local.example.yaml
  config/overrides.example.yaml
  sources/hardcoded.example.yaml
```

## Local Test Setup

Use a project-specific conda environment. Do not install into `base`.

```bash
conda create -p ./.conda/babelecho-dev python=3.12 pip setuptools wheel pytest pyyaml -y
.conda/babelecho-dev/bin/python -m pip install -e . --no-build-isolation
.conda/babelecho-dev/bin/python -m pytest -v
```

## Running The Pipeline

See [docs/backend-mvp0-runbook.md](docs/backend-mvp0-runbook.md).

The real 5090D run expects:

- A complete transcript source.
- Either DeepSeek API LLM config with an ignored `workspace/config/deepseek.env` key file, or a local vLLM endpoint for the later all-local path.
- A local TTS CLI wrapper configured in `workspace/config/local.yaml`.
- Optional local terminology overrides configured through an ignored `workspace/config/overrides.yaml`.
- `ffmpeg` available on `PATH`.

## Important Docs

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Source ingestion research](docs/source-ingestion-research.md)
- [Backend MVP-0 design](docs/backend-mvp.md)
- [Backend MVP-0 tech stack](docs/backend-mvp0-tech-stack.md)
- [Backend MVP-0 runbook](docs/backend-mvp0-runbook.md)
- [Plan index](docs/plans/README.md)
- [Implementation plan](docs/superpowers/plans/2026-06-16-backend-mvp0.md)

## Privacy

Do not commit real local configs, server hostnames, credentials, API keys, model caches, generated media, or run outputs. Keep real runtime config in ignored `workspace/config/*.yaml` files.
