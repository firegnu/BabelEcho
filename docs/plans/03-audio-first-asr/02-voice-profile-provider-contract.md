# Voice Profile Provider Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow Route B voice profile provider contract that can later host real speaker embedding extraction without polluting transcript-first, article, YouTube, RSS, iTunes, or frontend-only flows.

**Architecture:** Keep voice profile work inside the isolated audio-first backend route. The first implementation should not load a real model: it should formalize provider config, preserve the existing `asr/speaker-profiles.json` artifact, add fixture coverage, and reserve ignored run-local embedding paths for a later real extractor. Published artifacts may expose only safe summaries and must never publish embedding vectors.

**Tech Stack:** Python 3.12, pytest, YAML runtime config, existing `babelecho audio convert` pipeline, existing `asr/speaker-profiles.json` and `workspace/published/episodes/<run-id>/artifact.json`.

---

## Scope

### In

- Add an audio-first-only `voice_profile` config section.
- Support first providers:
  - `provider: none`: preserve current diarization-stat profile behavior.
  - `provider: fixture`: merge deterministic fixture profile metadata into `asr/speaker-profiles.json` for tests and contract validation.
- Extend `asr/speaker-profiles.json` with stable reserved fields:
  - `sample_count`
  - `sample_duration_ms`
  - `embedding_status`
  - `embedding_artifact`
  - `profile_kind`
- Keep `embedding_artifact` run-local and ignored when present.
- Keep publish behavior summary-only: expose `embedding_status`, `profile_kind`, and counts, not vectors.
- Update docs and resume after implementation.

### Out

- Do not install SpeechBrain, pyannote embedding, NeMo, WhisperX, or any new heavy model package in this step.
- Do not compute real speaker embeddings.
- Do not identify real people.
- Do not clone original host voices.
- Do not expose embeddings under `workspace/published/`.
- Do not add a frontend feature or frontend dependency.
- Do not change Route A transcript-first, article-reading, YouTube captions, RSS, Apple/iTunes, PodcastIndex, or episode page behavior.

## Artifact Contract

Target `asr/speaker-profiles.json` shape after this step:

```json
{
  "schema_version": "1.0",
  "provider": "diarization_stats",
  "source": "diarization",
  "diarization_provider": "pyannote",
  "diarization_model": "pyannote/speaker-diarization-community-1",
  "speaker_count": 2,
  "speakers": [
    {
      "id": "speaker_1",
      "label": "speaker_1",
      "turn_count": 15,
      "total_ms": 359521,
      "first_start_ms": 31,
      "last_end_ms": 479973,
      "avg_turn_ms": 23968.1,
      "sample_count": 0,
      "sample_duration_ms": 0,
      "profile_kind": "diarization_stats",
      "embedding_status": "not_computed",
      "embedding_artifact": null
    }
  ]
}
```

Allowed `embedding_status` values for this plan:

- `not_computed`: default for `provider: none`.
- `fixture`: fixture metadata was supplied for contract tests.
- `unavailable`: provider ran but could not produce a profile for this speaker.

Reserved future value:

- `computed`: only for a later real embedding provider, not this plan.

## Files

- Modify: `src/babelecho/diarization.py`
  - Keep current diarization normalization and stats profile generation.
  - Add reserved profile fields with safe defaults.
- Create: `src/babelecho/voice_profile.py`
  - Parse and apply `voice_profile` config.
  - Implement `none` and `fixture` providers.
  - Validate fixture speaker ids and embedding metadata shape.
- Modify: `src/babelecho/audio_pipeline.py`
  - Pass `local_config.get("voice_profile")` into the diarize-stage post-processing hook without adding a new pipeline stage yet.
- Modify: `src/babelecho/publish.py`
  - Keep published output summary-only.
  - Ensure any `embedding_artifact` path is omitted from `artifact.json`.
- Modify: `src/babelecho/status.py`
  - Keep `speaker_profiles` output path stable.
- Test: `tests/test_voice_profile.py`
  - Cover provider config validation and fixture merge behavior.
- Test: `tests/test_audio_pipeline.py`
  - Cover `babelecho audio convert --to-stage diarize` with fixture voice profiles.
- Test: `tests/test_publish.py`
  - Cover that published artifact exposes summary only and does not expose embedding artifact paths.
- Docs:
  - `docs/plans/03-audio-first-asr/01-local-audio-asr-diarization.md`
  - `docs/5090D远程测试流程.md`
  - `docs/前端Artifact契约与只读界面说明.md`
  - `resume-prompt.md`

## Tasks

### Task 1: Stabilize Existing Speaker Profile Defaults

**Files:**
- Modify: `src/babelecho/diarization.py`
- Test: `tests/test_diarization.py`

- [ ] **Step 1: Write failing tests for reserved fields**

Add assertions to the existing speaker profile tests that every speaker has:

```python
assert profile["sample_count"] == 0
assert profile["sample_duration_ms"] == 0
assert profile["embedding_artifact"] is None
assert profile["embedding_status"] == "not_computed"
```

- [ ] **Step 2: Run red test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py -q
```

Expected: failure because `sample_count`, `sample_duration_ms`, or `embedding_artifact` is missing.

- [ ] **Step 3: Add minimal defaults**

Update the profile dicts created in `src/babelecho/diarization.py` so every generated speaker has:

```python
"sample_count": 0,
"sample_duration_ms": 0,
"embedding_artifact": None,
```

Keep existing fields unchanged.

- [ ] **Step 4: Run green test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_diarization.py -q
```

Expected: all diarization tests pass.

### Task 2: Add Voice Profile Provider Module

**Files:**
- Create: `src/babelecho/voice_profile.py`
- Test: `tests/test_voice_profile.py`

- [ ] **Step 1: Write fixture merge tests**

Create tests that call a function shaped like:

```python
apply_voice_profile_config(
    {"provider": "fixture", "fixture_path": str(fixture_path)},
    run_paths,
    config_path=tmp_path / "local-audio.yaml",
)
```

The fixture file should contain:

```json
{
  "provider": "fixture",
  "speakers": [
    {
      "id": "speaker_1",
      "sample_count": 2,
      "sample_duration_ms": 12000,
      "embedding_status": "fixture",
      "profile_kind": "voice_profile_fixture",
      "embedding_artifact": "asr/voice-profiles/speaker_1.json"
    }
  ]
}
```

Expected merged `asr/speaker-profiles.json` speaker fields:

```python
assert speaker["sample_count"] == 2
assert speaker["sample_duration_ms"] == 12000
assert speaker["embedding_status"] == "fixture"
assert speaker["profile_kind"] == "voice_profile_fixture"
assert speaker["embedding_artifact"] == "asr/voice-profiles/speaker_1.json"
```

- [ ] **Step 2: Write provider validation tests**

Cover:

```python
with pytest.raises(ValueError, match="voice_profile.provider"):
    apply_voice_profile_config({"provider": "unknown"}, run_paths, config_path=config_path)
```

Cover missing fixture path:

```python
with pytest.raises(ValueError, match="voice_profile.fixture_path is required"):
    apply_voice_profile_config({"provider": "fixture"}, run_paths, config_path=config_path)
```

Cover unknown speaker id:

```python
with pytest.raises(ValueError, match="unknown speaker"):
    apply_voice_profile_config(
        {"provider": "fixture", "fixture_path": str(fixture)},
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )
```

- [ ] **Step 3: Run red tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py -q
```

Expected: import or function missing failure.

- [ ] **Step 4: Implement `voice_profile.py`**

Implement these functions:

```python
def apply_voice_profile_config(
    voice_profile_config: dict[str, Any] | None,
    run_paths: RunPaths,
    *,
    config_path: Path,
) -> Path:
    profiles_path = run_paths.run_dir / "asr" / "speaker-profiles.json"
    config = voice_profile_config or {"provider": "none"}
    provider = config.get("provider") or "none"
    if provider == "none":
        return profiles_path
    if provider != "fixture":
        raise ValueError("voice_profile.provider must be none or fixture")
    fixture = _load_fixture_config(config, config_path)
    profiles = _read_existing_profiles(profiles_path)
    merged = _merge_fixture_profiles(profiles, fixture)
    write_json(profiles_path, merged)
    return profiles_path
```

Rules:

- `None`, `{}`, or `{"provider": "none"}` leaves the existing file unchanged and returns `asr/speaker-profiles.json`.
- `provider: fixture` reads a JSON fixture and merges only known speaker ids.
- Validate `embedding_artifact` is either `None` or a relative path under the run directory.
- Do not copy or create embedding files in this step.
- Do not write anything under `workspace/published/`.

- [ ] **Step 5: Run green tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py -q
```

Expected: all voice profile tests pass.

### Task 3: Wire Voice Profile Config Into Audio Pipeline

**Files:**
- Modify: `src/babelecho/audio_pipeline.py`
- Test: `tests/test_audio_pipeline.py`

- [ ] **Step 1: Write CLI fixture test**

Add a test using local config:

```yaml
asr:
  provider: fixture
  fixture_path: "<two-speaker-asr.json>"
diarization:
  provider: fixture
  fixture_path: "<two-speaker-diarization.json>"
voice_profile:
  provider: fixture
  fixture_path: "<voice-profile-fixture.json>"
publish:
  base_url: "https://example.com/babelecho"
```

Run:

```bash
python -m babelecho audio convert --workspace <tmp> --run-id audio-voice-profile-cli --audio-file <audio> --local-config <config> --to-stage diarize
```

Assert:

```python
profiles = read_json(run_dir / "asr" / "speaker-profiles.json")
assert profiles["speakers"][0]["embedding_status"] == "fixture"
status = read_json(run_dir / "run.json")
assert status["outputs"]["speaker_profiles"] == "asr/speaker-profiles.json"
```

- [ ] **Step 2: Run red test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_applies_fixture_voice_profile -q
```

Expected: failure because `voice_profile` config is ignored.

- [ ] **Step 3: Wire post-processing**

In `src/babelecho/audio_pipeline.py`, after the existing `run_diarization` call succeeds inside the `diarize` stage, call:

```python
apply_voice_profile_config(
    local_config.get("voice_profile"),
    run_paths,
    config_path=Path(local_config_path),
)
```

Keep the stage name `diarize`; do not add a new stage yet.

- [ ] **Step 4: Run green test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_applies_fixture_voice_profile -q
```

Expected: pass.

### Task 4: Keep Publish Safe

**Files:**
- Modify: `src/babelecho/publish.py`
- Test: `tests/test_publish.py`

- [ ] **Step 1: Write publish privacy test**

Create an audio-first publish fixture where `asr/speaker-profiles.json` includes:

```json
"embedding_artifact": "asr/voice-profiles/speaker_1.json"
```

Assert in the published `artifact.json`:

```python
assert artifact["asr"]["speaker_profiles"]["embedding_status"] == "fixture"
assert "embedding_artifact" not in artifact["asr"]["speaker_profiles"]
```

Assert the copied `speaker-profiles.json` remains summary-only or keeps only relative metadata that is safe to view; do not copy any actual embedding file.

- [ ] **Step 2: Run publish test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py -q
```

Expected: pass after publish summary behavior is confirmed or tightened.

### Task 5: Documentation And Resume Sync

**Files:**
- Modify: `docs/plans/03-audio-first-asr/01-local-audio-asr-diarization.md`
- Modify: `docs/5090D远程测试流程.md`
- Modify: `docs/前端Artifact契约与只读界面说明.md`
- Modify: `resume-prompt.md`

- [ ] **Step 1: Document config**

Add example:

```yaml
voice_profile:
  provider: fixture
  fixture_path: tests/fixtures/asr/two-speaker-voice-profile.json
```

Document that real embedding providers are deferred and embeddings must stay ignored/run-local.

- [ ] **Step 2: Update frontend contract wording**

Clarify:

- frontend may read `speaker-profiles.json`;
- frontend must not rely on raw embeddings;
- `embedding_artifact` is not a public playback or download target.

- [ ] **Step 3: Update resume**

Add a one-paragraph current status and next-step pointer to this plan.

### Task 6: Verification And 5090D Smoke

**Files:**
- No code changes expected after this task unless verification fails.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py tests/test_diarization.py tests/test_audio_pipeline.py tests/test_publish.py -q
```

Expected: all pass.

- [ ] **Step 2: Run full tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest -q
```

Expected: all pass.

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output, exit code 0.

- [ ] **Step 4: 5090D smoke after push**

After commit and push, on 5090D:

```bash
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && git pull --ff-only && .conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_applies_fixture_voice_profile -q'
```

Expected: pass.

No real model smoke is required for this plan.

## Risks

- **Embedding leakage:** prevent by never writing vectors into `artifact.json` and never copying embedding files to `workspace/published/`.
- **Route contamination:** keep all logic behind `babelecho audio convert` and `voice_profile` config; do not touch transcript source ingestion.
- **Schema churn:** preserve current speaker profile fields and add only reserved optional fields with safe defaults.
- **Overbuilding:** stop at `none` and `fixture`; defer real extractor installation and GPU environment work to a later plan.

## Acceptance Criteria

- `asr/speaker-profiles.json` includes reserved voice profile fields for every speaker.
- `voice_profile.provider=none` preserves existing behavior.
- `voice_profile.provider=fixture` can deterministically mark speaker profile metadata in tests.
- Published artifacts expose only summary fields and no embedding vectors.
- Full local pytest passes.
- 5090D can pull and run the fixture voice profile smoke without installing new model packages.
