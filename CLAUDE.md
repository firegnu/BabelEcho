# CLAUDE.md

Follow `AGENTS.md` for project instructions.

Key reminders:

- MVP-0 is transcript-first and local-first.
- Current validation track uses DeepSeek API for LLM adaptation and 5090D local TTS. Treat this as a temporary hybrid exception, not the final production target.
- Do not use cloud APIs unless the user explicitly chooses the hybrid validation track. Keep API keys out of tracked files.
- Do not install Python packages into conda `base`; use `./.conda/babelecho-dev`.
- Do not commit real configs, credentials, server addresses, generated media, or model caches.
- Run tests with:

  ```bash
  .conda/babelecho-dev/bin/python -m pytest -v
  ```

- Keep changes small and tied directly to the current request.
