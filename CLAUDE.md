# CLAUDE.md

Follow `AGENTS.md` for project instructions.

Key reminders:

- MVP-0 is transcript-first and local-only.
- Do not use cloud APIs.
- Do not install Python packages into conda `base`; use `./.conda/babelecho-dev`.
- Do not commit real configs, credentials, server addresses, generated media, or model caches.
- Run tests with:

  ```bash
  .conda/babelecho-dev/bin/python -m pytest -v
  ```

- Keep changes small and tied directly to the current request.
