# AGENTS.md

## Project Goal

BabelEcho converts English podcast transcripts into Chinese podcast audio through a local-first backend pipeline. The current milestone is MVP-0: complete transcript input, Chinese script adaptation, local TTS synthesis, audio assembly, and static RSS publishing.

Current decision: use DeepSeek API for the MVP-0 LLM adaptation baseline, while keeping TTS on the 5090D locally. This is a temporary hybrid validation track; the final production direction remains local-first and should later replace the cloud LLM with a local model.

## Scope Rules

- Keep MVP-0 transcript-first. Do not add ASR unless explicitly requested.
- Do not add original host voice cloning unless explicitly requested.
- Do not add Web UI, job queue, subscription scanning, or macOS App code while working on MVP-0 backend tasks.
- Do not use cloud APIs for MVP-0 unless the user explicitly selects a temporary hybrid validation track. If a cloud LLM is used, keep API keys in environment variables or ignored local config only, treat the output as a quality baseline, and do not make the final production path depend on cloud inference.
- Keep the macOS App concept thin: it consumes already-published Chinese podcast artifacts.

## Development Workflow

- Work in a feature branch or worktree for implementation tasks.
- Use a project-specific conda environment. Do not install dependencies into conda `base`.
- Prefer TDD for new behavior:
  - Write the test first.
  - Run it and confirm the expected failure.
  - Implement the smallest code that passes.
  - Run the relevant test again.
- Keep changes surgical. Do not refactor unrelated code.
- Match the existing simple Python CLI style.

## Test Commands

```bash
conda create -p ./.conda/babelecho-dev python=3.12 pip setuptools wheel pytest pyyaml -y
.conda/babelecho-dev/bin/python -m pip install -e . --no-build-isolation
.conda/babelecho-dev/bin/python -m pytest -v
```

If an environment already exists, run:

```bash
.conda/babelecho-dev/bin/python -m pytest -v
```

## Runtime Files

Tracked examples:

- `workspace/config/local.example.yaml`
- `workspace/sources/hardcoded.example.yaml`

Ignored real runtime files:

- `workspace/config/*.yaml`
- `workspace/sources/*.yaml`
- `workspace/runs/`
- generated audio/transcript outputs
- model caches and checkpoints

Never commit real server addresses, credentials, API keys, private tokens, generated media, or local model caches.

## 5090D Handoff Flow

The preferred collaboration loop is:

```text
MacBook implements and pushes -> 5090D pulls and runs -> user shares logs -> MacBook fixes and pushes
```

Do not assume SSH access to the 5090D machine.

## Important Docs

- `README.md`
- `HANDOFF.md`
- `docs/architecture.md`
- `docs/backend-mvp.md`
- `docs/backend-mvp0-tech-stack.md`
- `docs/backend-mvp0-runbook.md`
- `docs/source-ingestion-research.md`
- `docs/superpowers/plans/2026-06-16-backend-mvp0.md`
