# BabelEcho

BabelEcho is a local-first pipeline for converting English podcast transcripts into Chinese podcast audio.

MVP-0 and MVP-0.5 are complete. MVP-1 now uses a fixed `sft_builtin_4role` voice-role profile: single-speaker scripts use `female_a` by default, explicit `male`/`男` labels use `male_a`, explicit `female`/`女` labels use `female_a`, and 2+ speakers use stable `speaker -> voice_role` mapping across `female_a / male_a / female_b / male_b`. Rendering is hybrid local TTS: `male_a` uses `CosyVoice2-0.5B` cross-lingual synthesis at speed `1.1`, with a local calm prompt asset and male_a-only text smoothing when available, while `female_a`, `female_b`, and `male_b` use `CosyVoice-300M-SFT`. The current focus is real podcast sources and common interview workflows beyond manually supplied transcripts.

Current validation track: use DeepSeek API for the LLM adaptation baseline, then use the 5090D for local Chinese TTS. This is a temporary hybrid path to validate script quality and audio synthesis before replacing the cloud LLM with a local model.

Later voice expansion should prefer fine-tuning `CosyVoice-300M-SFT` to add multiple stable Chinese male/female fixed roles. This is separate from original-host voice cloning and does not change the current MVP-1 routing until a tuned model is explicitly selected and validated.

## Current Scope

The current pipeline supports:

- Transcript-first input only.
- Local-first execution, with a temporary DeepSeek API exception for the LLM adaptation baseline.
- Stage-by-stage Python CLI commands.
- One-command pipeline orchestration with `babelecho run`.
- On-demand single episode conversion with `babelecho episode convert`.
- Manual transcript input with `babelecho run --transcript-file`.
- Real podcast transcript sources from RSS `podcast:transcript`, iTunes RSS feed discovery, RSS episode selection, PodcastIndex episode metadata, PodcastIndex search/feed selection, first-party episode pages with public transcript text, and YouTube public captions.
- Chunked DeepSeek adaptation that batches complete transcript segments while preserving original segment ids and final script order.
- Partial pipeline execution with `babelecho run --to-stage ...` and resume with `--from-stage ...`.
- Chinese script preview with `babelecho script` before TTS.
- Local terminology and pronunciation overrides before TTS with exact replacements.
- Automatic TTS voice-role selection with hybrid local rendering: unlabeled single speaker uses `female_a`, explicit male/female single speakers use `male_a`/`female_a`, and 2+ speakers use stable `speaker -> voice_role` mapping; only `male_a` is rendered by CosyVoice2 cross-lingual, and the other roles are rendered by 300M SFT.
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
  sources/youtube-captions.example.yaml
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

## On-demand Episode Convert

Convert one episode by exact input:

```bash
babelecho episode convert \
  --workspace workspace \
  --run-id my-episode \
  --url "https://example.com/podcast/episode" \
  --local-config workspace/config/local.yaml
```

Supported exact inputs in the first version:

- YouTube URLs with public captions.
- Podcast episode pages with transcript text or a transcript link.
- Existing `--source-config` YAML.
- Local `--transcript-file`.

If no transcript is available, the command fails clearly instead of falling back to ASR.

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
- [Voice calibration explainer](docs/voice-calibration-explainer.md)
- [Plan index](docs/plans/README.md)
- [Implementation plan](docs/superpowers/plans/2026-06-16-backend-mvp0.md)

## Privacy

Do not commit real local configs, server hostnames, credentials, API keys, model caches, generated media, or run outputs. Keep real runtime config in ignored `workspace/config/*.yaml` files.
