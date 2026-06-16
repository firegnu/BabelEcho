# BabelEcho

BabelEcho is a local-first pipeline for converting English podcast transcripts into Chinese podcast audio.

The current focus is MVP-0: take one complete English transcript, adapt it into a natural Chinese spoken script, synthesize Chinese audio locally, assemble the final audio file, and publish a minimal podcast feed.

## Current Scope

MVP-0 supports:

- Transcript-first input only.
- Local inference only, with no cloud API dependency.
- Stage-by-stage Python CLI commands.
- File-based intermediate artifacts under `workspace/runs/<run-id>/`.
- Fixture tests for the full pure pipeline.
- Static podcast output: `feed.xml` plus generated audio artifacts.

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
tests/
workspace/
  config/local.example.yaml
  sources/hardcoded.example.yaml
```

## Local Test Setup

Use a project-specific conda environment. Do not install into `base`.

```bash
conda create -p ./.conda/babelecho-dev python=3.12 pip setuptools wheel pytest pyyaml -y
.conda/babelecho-dev/bin/python -m pip install -e . --no-build-isolation
.conda/babelecho-dev/bin/python -m pytest -v
```

## Running MVP-0

See [docs/backend-mvp0-runbook.md](docs/backend-mvp0-runbook.md).

The real 5090D run expects:

- A complete transcript source.
- A local vLLM endpoint configured in `workspace/config/local.yaml`.
- A local TTS CLI wrapper configured in `workspace/config/local.yaml`.
- `ffmpeg` available on `PATH`.

## Important Docs

- [Architecture](docs/architecture.md)
- [Source ingestion research](docs/source-ingestion-research.md)
- [Backend MVP-0 design](docs/backend-mvp.md)
- [Backend MVP-0 tech stack](docs/backend-mvp0-tech-stack.md)
- [Backend MVP-0 runbook](docs/backend-mvp0-runbook.md)
- [Plan index](docs/plans/README.md)
- [Implementation plan](docs/superpowers/plans/2026-06-16-backend-mvp0.md)

## Privacy

Do not commit real local configs, server hostnames, credentials, API keys, model caches, generated media, or run outputs. Keep real runtime config in ignored `workspace/config/*.yaml` files.
