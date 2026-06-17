# TTS Batch Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add batch synthesis for `local_cli` so CosyVoice loads once per `synthesize` stage instead of once per segment.

**Architecture:** Keep core pipeline file-based. `synthesize_segments()` delegates all segment audio generation to a new `synthesize_many_to_wav()` helper. `local_cli` writes a batch JSON and calls the existing wrapper once; the wrapper loads `AutoModel` once and loops over batch items.

**Tech Stack:** Python 3.12 project code, pytest, existing CosyVoice wrapper CLI, JSON batch file.

---

### Task 1: Add Pipeline Batch Helper

**Files:**
- Modify: `tests/test_synthesize.py`
- Modify: `src/babelecho/tts.py`
- Modify: `src/babelecho/synthesize.py`

- [ ] **Step 1: Write failing test for one subprocess call**

Add a test in `tests/test_synthesize.py` that calls `synthesize_many_to_wav()` with two segments and asserts `subprocess.run` is called once with `--batch-file`.

- [ ] **Step 2: Run test to verify failure**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_synthesize.py::test_local_cli_tts_batches_segments_in_one_wrapper_call -v`

Expected: import error or missing function failure for `synthesize_many_to_wav`.

- [ ] **Step 3: Implement minimal helper**

In `src/babelecho/tts.py`, add `synthesize_many_to_wav(items, batch_path, tts_config)`. For `fixture`, write silent wavs. For `local_cli`, write text files and `batch_path`, then call wrapper once with `--batch-file`.

- [ ] **Step 4: Wire synthesize stage**

In `src/babelecho/synthesize.py`, build `(text, audio_path)` items from script segments, call `synthesize_many_to_wav()`, then write the same manifest format.

- [ ] **Step 5: Verify task**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_synthesize.py -v`

Expected: all `tests/test_synthesize.py` tests pass.

### Task 2: Add Wrapper Batch Mode

**Files:**
- Modify: `tests/test_cosyvoice_wrapper.py`
- Modify: `tools/cosyvoice_tts_wrapper.py`

- [ ] **Step 1: Write failing wrapper batch test**

Add a test in `tests/test_cosyvoice_wrapper.py` that writes a batch JSON with two items, stubs `AutoModel`, and asserts fake model initialization count is `1` and both output paths are saved.

- [ ] **Step 2: Run test to verify failure**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_cosyvoice_wrapper.py::test_synthesize_batch_reuses_model_for_multiple_outputs -v`

Expected: parser or missing batch support failure.

- [ ] **Step 3: Implement wrapper batch config**

Update parser to allow `--batch-file` as an alternative to `--text-file --output`. Extend `WrapperConfig` with `batch_file`.

- [ ] **Step 4: Implement shared model synthesis**

Split model loading from single item synthesis. `synthesize(config)` loads the model once, then either handles one `(text_file, output)` pair or loops over batch JSON items.

- [ ] **Step 5: Verify task**

Run: `.conda/babelecho-dev/bin/python -m pytest tests/test_cosyvoice_wrapper.py -v`

Expected: all wrapper tests pass.

### Task 3: Regression, Docs, Remote Smoke

**Files:**
- Modify if needed: `docs/backend-mvp0-runbook.md`
- Modify if needed: `HANDOFF.md`
- Modify if needed: `resume-prompt.md`

- [ ] **Step 1: Run focused and full tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_synthesize.py tests/test_cosyvoice_wrapper.py -v
.conda/babelecho-dev/bin/python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run 5090D smoke**

Push branch, pull on 5090D, and run a small real TTS smoke with at least two segments using the cross-lingual config.

Expected: one `synthesize` stage succeeds and produces multiple wav files; logs show one wrapper process instead of one per segment.

- [ ] **Step 3: Run scans and commit**

Run tracked-file `gitleaks` and `trufflehog` scans before final push.

Expected: no verified or unverified secrets.
