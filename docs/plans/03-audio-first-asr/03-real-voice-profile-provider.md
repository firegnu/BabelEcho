# Real Voice Profile Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**状态:** `in_progress`

**Goal:** Add a real Route B speaker embedding provider contract without starting voice clone or exposing private embeddings.

**Architecture:** Keep all real voice profile work behind audio-first `voice_profile.provider=local_cli`. BabelEcho core calls a wrapper, validates canonical JSON, and merges safe metadata into `asr/speaker-profiles.json`; model loading, GPU dependencies, and embedding extraction stay outside the package in ignored 5090D runtime environments. Published artifacts remain summary-only and must not copy embedding files or vectors.

**Tech Stack:** Python 3.12, pytest, YAML runtime config, existing `babelecho audio convert` pipeline, local CLI wrappers under `tools/`, 5090D ignored conda environments.

---

## Progress

### 2026-06-20：local_cli contract implemented locally

- Added audio-first-only `voice_profile.provider=local_cli`.
- BabelEcho core now invokes a local wrapper with audio, diarization, speaker profile input paths, output dir, output summary path, optional model/device/sample settings, and `extra_args`.
- Wrapper `summary.json` is validated and merged into `asr/speaker-profiles.json`; `embedding_status=computed` is now allowed.
- Added `tools/speaker_embedding_wrapper.py` as a contract stub only. It documents the stable CLI shape but intentionally does not load a model.
- Publish remains summary-only: `artifact.json.asr.speaker_profiles` does not expose `embedding_artifact`, and `asr/voice-profiles/*.json` is not copied to `workspace/published/`.
- Next work moved to model probe and then a model-specific wrapper.

### 2026-06-20：5090D model probe selected SpeechBrain ECAPA

- Created `/home/th5090d/miniforge3/envs/babelecho-voice-profile` as an isolated environment. It was cloned from `babelecho-diarization`, then `speechbrain 1.1.0` and `sentencepiece 0.2.1` were installed only in this voice-profile env.
- `pyannote/embedding` was blocked by Hugging Face gated repo 403 with the current `HF_TOKEN`, so pyannote embedding is not the first implementation backend.
- `speechbrain/spkrec-ecapa-voxceleb` ran successfully on `workspace/sources/asr-practicalai-zero-trust-8min.wav` with the existing Practical AI diarization artifact.
- Probe stats: CUDA device, 192-dimensional embeddings, selected 5 samples for `speaker_1` and 4 for `speaker_2`, total probe time about `36.9s`, outer wall time about `38.1s`, peak RSS about `2.4 GB`.
- Separation signal: within-speaker cosine means were about `0.929` and `0.849`; between-speaker cosine was about `0.457`.
- NeMo was not tested because SpeechBrain ECAPA is a viable candidate.
- Follow-up implemented locally: `tools/speaker_embedding_wrapper.py` now uses SpeechBrain ECAPA, writes run-local `asr/voice-profiles/*.json`, and writes summary-only metadata.

### 2026-06-20：SpeechBrain wrapper implemented locally

- `tools/speaker_embedding_wrapper.py` now selects the longest diarization windows per speaker, runs `speechbrain/spkrec-ecapa-voxceleb`, averages per-speaker embeddings, writes private run-local speaker JSON artifacts, and writes `summary.json`.
- Heavy dependencies remain outside BabelEcho core. The wrapper imports SpeechBrain, torch, and torchaudio only when executed.
- Local wrapper unit tests cover sample-window selection and summary/artifact writing without requiring SpeechBrain in the local dev env.
- 5090D real `voice_profile.provider=local_cli` smoke passed in run `audio-voice-profile-speechbrain-smoke-20260620`: both speakers became `embedding_status=computed`, private 192-dimensional artifacts were written under `asr/voice-profiles/`, and the merged summary stayed in `asr/speaker-profiles.json`.
- Publish-stage privacy smoke passed on the same run: `artifact.json.asr.speaker_profiles` did not expose `embedding_artifact`, and `workspace/published/episodes/<run-id>/asr/voice-profiles/` was not created.
- Important boundary: this smoke used fixture ASR/diarization with a real SpeechBrain wrapper, so it validates wrapper integration and publish privacy, not cross-episode speaker identity.

### 2026-06-20：cross-episode similarity report implemented and smoke-tested

- Added `src/babelecho/speaker_similarity.py` and CLI entrypoint `babelecho speaker-profiles compare`.
- The report reads only run-local `asr/speaker-profiles.json` plus private `embedding_artifact` files, validates artifacts stay under each run dir, computes cross-run cosine scores, and writes a JSON report when `--output-json` is provided.
- Local verification passed: `tests/test_speaker_similarity.py`, voice-profile focused tests, and full `pytest -q` (`235 passed`). 5090D verification passed: `tests/test_speaker_similarity.py`.
- 5090D generated a temporary ignored config `workspace/config/local-audio-real-voice-profile-speechbrain-smoke.yaml` by combining real `local_cli` ASR/diarization with the SpeechBrain `voice_profile` section.
- Real two-episode smoke:
  - `audio-voice-profile-real-practicalai-zero-trust-8min-20260620`: true Whisper ASR + pyannote diarization + SpeechBrain embeddings, 2 computed speakers, 192 dimensions.
  - `audio-voice-profile-real-practicalai-ai-index-8min-20260620`: true Whisper ASR + pyannote diarization + SpeechBrain embeddings, 3 computed speakers, 192 dimensions.
  - Report `workspace/runs/speaker-similarity-practicalai-real-two-episodes-20260620.json`: 6 cross-run pairs, `likely_same=2`, `possible_same=0`, `different=4`.
  - Top matches: Zero Trust `speaker_1` -> AI Index `speaker_2` cosine `0.959153`; Zero Trust `speaker_2` -> AI Index `speaker_3` cosine `0.881848`.
- Negative smoke: JFK audio did not provide usable embedding windows; speakers were marked `unavailable`, so it is not useful for cross-episode consistency.
- Remaining work: calibrate thresholds on more true same-show episodes before producing any private speaker alias map. Do not use embeddings for voice clone, identity recognition, or TTS conditioning.

### 2026-06-20：private speaker alias candidates implemented

- Added `src/babelecho/speaker_aliases.py` and CLI entrypoint `babelecho speaker-profiles alias`.
- The alias command consumes an existing similarity report and writes a private candidate map. It does not read embedding vectors and does not output `embedding_artifact` paths.
- Conservative defaults: `same_threshold=0.85`, `min_sample_duration_ms=60000`, `min_members=2`.
- Safety behavior:
  - speakers below the minimum sample duration are skipped, which filters repeated short intro/narration-like speakers;
  - any connected component with multiple speakers from the same run is skipped instead of forcing a merge.
- Local verification passed: `tests/test_speaker_aliases.py`, speaker-focused tests, and full `pytest -q` (`238 passed`). 5090D verification passed: `tests/test_speaker_aliases.py`.
- 5090D added three more Practical AI public RSS 8-minute samples: `mcp-kubernetes`, `hermes-agent`, and `model-wars`.
- Five-episode report `workspace/runs/speaker-similarity-practicalai-real-five-episodes-20260620.json`: 14 computed speakers, 78 cross-run pairs, `likely_same=19`, `possible_same=0`, `different=59`.
- Alias map `workspace/runs/speaker-aliases-practicalai-real-five-episodes-20260620.json`:
  - `speaker_alias_001`: 5 members, pair_count 9, min/avg/max cosine `0.850890/0.909038/0.959153`;
  - `speaker_alias_002`: 3 members, pair_count 3, min/avg/max cosine `0.881848/0.898437/0.919010`;
  - skipped 4 short speakers around 32 seconds each;
  - verified no `embedding`, `embedding_artifact`, `voice-profiles`, or artifact path references are present in the alias map.
- The explicit human-confirmation contract is implemented in the next section; no alias candidate influences cross-episode Chinese TTS voice-role assignment yet.

### 2026-06-20：private speaker alias review contract implemented

- Added `src/babelecho/speaker_alias_review.py` and CLI entrypoint `babelecho speaker-profiles review`.
- The review command consumes a private alias candidate map and writes a private review JSON. It does not read embedding vectors, does not output `embedding_artifact` paths, and is not consumed by TTS routing.
- Review statuses are explicit and editable: `candidate`, `confirmed`, `rejected`, `split`, `ignored`.
- Default output marks every alias as `candidate`; `--existing-review` preserves any previous decision by `alias_id`, so a confirmed/rejected alias is not overwritten when regenerating the review file from updated candidates.
- The review contract contains only safe metadata: alias id, candidate stats, member run ids/speaker ids, sample counts/durations, reviewer/review time/note fields. It does not identify real people.
- Local verification passed: `tests/test_speaker_aliases.py` covers candidate defaults, safe-field stripping, decision preservation, and the CLI; full `pytest -q` also passed.
- 5090D real smoke passed on the five-episode Practical AI alias map: `workspace/runs/speaker-alias-review-practicalai-real-five-episodes-20260620.json` contains 2 aliases, `review_status_counts={"candidate": 2}`, and no `embedding_artifact` or `voice-profiles` strings.
- Remaining work after this step: decide how `confirmed` aliases map to stable cross-episode Chinese voice roles. Do not auto-apply unconfirmed aliases, do not use embeddings for TTS, and do not do voice clone.

### 2026-06-20：private confirmed-alias voice-role map contract implemented

- Added `src/babelecho/speaker_voice_role_map.py` and CLI entrypoint `babelecho speaker-profiles voice-roles`.
- The command consumes a private speaker alias review JSON and writes a private voice-role map JSON.
- Only aliases with `review_status=confirmed` are assigned fixed Chinese voice roles. `candidate`, `rejected`, `split`, and `ignored` aliases are listed under `skipped_aliases` with `reason=not_confirmed`.
- Default role assignment uses the existing fixed role sequence `female_a`, `male_a`, `female_b`, `male_b`.
- `--existing-map` preserves existing `alias_id -> voice_role` assignments so regenerating the map does not drift recurring speakers to a different Chinese voice role.
- The output is still a passive contract: it is not consumed by TTS routing, is not published, does not read or output embeddings, and does not perform voice clone.
- Local focused verification passed: `tests/test_speaker_aliases.py tests/test_speaker_similarity.py tests/test_voice_profile.py tests/test_speaker_voices.py`.
- 5090D smoke passed using a simulated confirmed review derived from the five-episode Practical AI review file: `speaker_alias_001 -> female_a`, `speaker_alias_002` was skipped as `rejected`, and the output contained no `embedding_artifact` or `voice-profiles` strings. A second 5090D smoke with `--existing-map` preserved `speaker_alias_001 -> male_b`.
- The explicit opt-in application path is implemented in the next section; the map is still not auto-applied to synthesize.

### 2026-06-20：private voice-role map opt-in application implemented

- Added `babelecho speaker-profiles apply-voice-roles --workspace ... --run-id ... --voice-role-map ... [--overwrite]`.
- The command explicitly applies one private voice-role map to one run by writing `workspace/runs/<run-id>/script/speaker-voices.json`.
- It only writes speakers whose role-map alias members match the target `run_id`; other runs in the same alias are ignored for this per-run output.
- The written file uses the existing `speaker-voices.json` shape consumed by TTS: `speaker_voices` plus `inferences`, with `mode=speaker_voice_role_map`.
- Existing `speaker-voices.json` is reused by default and only replaced with `--overwrite`, so the opt-in command does not silently overwrite prior manual or LLM-inferred roles.
- The default pipeline still does not call this command. Applying the map remains an explicit separate step.
- Local focused verification passed: `tests/test_speaker_voices.py tests/test_speaker_aliases.py tests/test_speaker_similarity.py tests/test_voice_profile.py tests/test_synthesize.py`.
- Local full verification passed: `pytest -q`.
- 5090D smoke passed using `speaker-voice-role-map-practicalai-real-five-episodes-confirmed-smoke-20260620.json` applied to `audio-voice-profile-real-practicalai-zero-trust-8min-20260620`: it wrote `script/speaker-voices.json` with `speaker_1 -> female_a`, contained no `embedding_artifact` or `voice-profiles` strings, `load_speaker_voice_roles()` returned `{"speaker_1": "female_a"}`, and a second run without `--overwrite` returned `reused`.
- Remaining work: decide whether a future config flag should call this explicit application step before synthesize; do not enable it by default.

---

## Scope

### In

- Add audio-first-only `voice_profile.provider=local_cli`.
- Define and validate a wrapper output contract for per-speaker embedding metadata.
- Write run-local embedding artifacts under ignored run directories such as `workspace/runs/audio-voice-profile-smoke/asr/voice-profiles/`.
- Merge only safe metadata into `asr/speaker-profiles.json`:
  - `sample_count`
  - `sample_duration_ms`
  - `profile_kind`
  - `embedding_status`
  - `embedding_artifact`
- Keep `embedding_artifact` as a run-local relative path only.
- Add a deterministic fake local CLI wrapper test before touching real model wrappers.
- Add a 5090D model-probe task that compares candidate embedding backends before choosing a default.
- Build private speaker alias candidates, a private review file, a private confirmed-alias voice-role map, and an explicit opt-in per-run application command from similarity reports after enough same-show samples are available.

### Out

- Do not clone original host voices.
- Do not synthesize Chinese audio using extracted embeddings.
- Do not automatically apply unconfirmed alias candidates, review files, or voice-role maps to TTS voice roles.
- Do not identify real people.
- Do not publish vectors or embedding files under `workspace/published/`.
- Do not change Route A transcript-first, YouTube, RSS, iTunes, PodcastIndex, episode page, article, or frontend-only flows.
- Do not add a web UI or app feature.
- Do not make SpeechBrain, pyannote embedding, NeMo, or any heavy model package a package dependency of BabelEcho core.

## Current Baseline

- ASR is already available through `asr.provider=fixture/local_cli`.
- Diarization is already available through `diarization.provider=none/fixture/local_cli`.
- `voice_profile.provider=none/fixture` is implemented.
- `asr/speaker-profiles.json` already has reserved fields and safe defaults.
- Publish exposes only `artifact.json.asr.speaker_profiles` summary fields and omits `embedding_artifact`.
- 5090D has validated Whisper ASR, pyannote diarization, SpeechBrain speaker embedding extraction, and the diagnostic cross-run similarity report on two Practical AI 8-minute samples.

## Provider Contract

Runtime config shape:

```yaml
voice_profile:
  provider: local_cli
  command: "/home/th5090d/miniforge3/envs/babelecho-voice-profile/bin/python tools/speaker_embedding_wrapper.py"
  model: speechbrain/spkrec-ecapa-voxceleb
  device: cuda
  min_sample_ms: 1500
  max_samples_per_speaker: 5
  extra_args:
    - "--normalize"
    - "true"
```

BabelEcho core command invocation shape, shown with a concrete example run:

```text
/home/th5090d/miniforge3/envs/babelecho-voice-profile/bin/python tools/speaker_embedding_wrapper.py \
  --audio-file workspace/runs/audio-voice-profile-smoke/audio/input.wav \
  --diarization-json workspace/runs/audio-voice-profile-smoke/asr/diarization.json \
  --speaker-profiles-json workspace/runs/audio-voice-profile-smoke/asr/speaker-profiles.json \
  --output-dir workspace/runs/audio-voice-profile-smoke/asr/voice-profiles \
  --output-json workspace/runs/audio-voice-profile-smoke/asr/voice-profiles/summary.json \
  --model speechbrain/spkrec-ecapa-voxceleb \
  --device cuda \
  --min-sample-ms 1500 \
  --max-samples-per-speaker 5 \
  --normalize true
```

Wrapper `summary.json` output:

```json
{
  "provider": "local_cli",
  "model": "pyannote/embedding",
  "speakers": [
    {
      "id": "speaker_1",
      "sample_count": 3,
      "sample_duration_ms": 14320,
      "profile_kind": "speaker_embedding",
      "embedding_status": "computed",
      "embedding_artifact": "asr/voice-profiles/speaker_1.json"
    },
    {
      "id": "speaker_2",
      "sample_count": 0,
      "sample_duration_ms": 0,
      "profile_kind": "speaker_embedding",
      "embedding_status": "unavailable",
      "embedding_artifact": null
    }
  ],
  "metadata": {
    "wrapper": "tools/speaker_embedding_wrapper.py",
    "embedding_dimension": 512
  }
}
```

Allowed `embedding_status` values after this plan:

- `not_computed`: default provider did not run.
- `fixture`: deterministic fixture metadata was supplied.
- `unavailable`: provider ran, but no usable sample was available for the speaker.
- `computed`: provider wrote a run-local embedding artifact.

Embedding artifact file shape for wrapper-owned files:

```json
{
  "schema_version": "1.0",
  "speaker_id": "speaker_1",
  "provider": "pyannote_embedding",
  "model": "pyannote/embedding",
  "embedding_format": "float32",
  "embedding": [0.01, -0.02],
  "sample_windows": [
    {"start_ms": 1200, "end_ms": 5200}
  ]
}
```

This file stays run-local. BabelEcho core may validate that the path is inside `run_paths.run_dir`, but it must not copy this file to `workspace/published/`.

## Tasks

### Task 1: Extend Voice Profile Status Contract

**Files:**
- Modify: `src/babelecho/voice_profile.py`
- Test: `tests/test_voice_profile.py`
- Docs: `docs/plans/03-audio-first-asr/01-local-audio-asr-diarization.md`

- [ ] **Step 1: Write failing test for computed status**

Add this test to `tests/test_voice_profile.py`:

```python
def test_fixture_voice_profile_allows_computed_status(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-computed")
    _write_profiles(run_paths)
    fixture = tmp_path / "voice-profile-fixture.json"
    write_json(
        fixture,
        {
            "provider": "fixture",
            "speakers": [
                {
                    "id": "speaker_1",
                    "sample_count": 1,
                    "sample_duration_ms": 4200,
                    "embedding_status": "computed",
                    "profile_kind": "speaker_embedding",
                    "embedding_artifact": "asr/voice-profiles/speaker_1.json",
                }
            ],
        },
    )

    apply_voice_profile_config(
        {"provider": "fixture", "fixture_path": str(fixture)},
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    profiles = read_json(run_paths.run_dir / "asr" / "speaker-profiles.json")
    assert profiles["speakers"][0]["embedding_status"] == "computed"
```

- [ ] **Step 2: Run red test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py::test_fixture_voice_profile_allows_computed_status -q
```

Expected: fail because `computed` is still reserved and not allowed.

- [ ] **Step 3: Add `computed` to allowed statuses**

In `src/babelecho/voice_profile.py`, change:

```python
ALLOWED_EMBEDDING_STATUS = {"not_computed", "fixture", "unavailable"}
```

to:

```python
ALLOWED_EMBEDDING_STATUS = {"not_computed", "fixture", "unavailable", "computed"}
```

- [ ] **Step 4: Run green test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py::test_fixture_voice_profile_allows_computed_status -q
```

Expected: pass.

### Task 2: Add `local_cli` Provider Validation

**Files:**
- Modify: `src/babelecho/voice_profile.py`
- Test: `tests/test_voice_profile.py`

- [ ] **Step 1: Write failing tests for local CLI config**

Add tests:

```python
def test_local_cli_voice_profile_requires_command(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-local-cli-no-command")
    _write_profiles(run_paths)

    with pytest.raises(ValueError, match="voice_profile.command is required"):
        apply_voice_profile_config(
            {"provider": "local_cli"},
            run_paths,
            config_path=tmp_path / "local-audio.yaml",
        )


def test_voice_profile_rejects_invalid_extra_args(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "voice-profile-extra-args")
    _write_profiles(run_paths)

    with pytest.raises(ValueError, match="voice_profile.extra_args must be a list of strings"):
        apply_voice_profile_config(
            {
                "provider": "local_cli",
                "command": "python tools/speaker_embedding_wrapper.py",
                "extra_args": ["--ok", 1],
            },
            run_paths,
            config_path=tmp_path / "local-audio.yaml",
        )
```

- [ ] **Step 2: Run red tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py::test_local_cli_voice_profile_requires_command tests/test_voice_profile.py::test_voice_profile_rejects_invalid_extra_args -q
```

Expected: fail because `local_cli` is not supported yet.

- [ ] **Step 3: Add config parsing helpers**

In `src/babelecho/voice_profile.py`, add helpers matching existing ASR/diarization style:

```python
import shlex
import subprocess


def _command_parts(command: Any) -> list[str]:
    if isinstance(command, str):
        parts = shlex.split(command)
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        parts = list(command)
    else:
        raise ValueError("voice_profile.command must be a string or list of strings")
    if not parts:
        raise ValueError("voice_profile.command must not be empty")
    return parts


def _optional_string(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    if value is None:
        return None
    value = str(value)
    return value if value else None
```

- [ ] **Step 4: Add local CLI dispatch shell**

In `apply_voice_profile_config`, accept `provider == "local_cli"` and route to a new `run_local_cli_voice_profile` function. In this task the function should validate `command` and `extra_args`, then return `profiles_path` without running a wrapper; Task 3 replaces that stub with real local CLI execution.

- [ ] **Step 5: Run green tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py -q
```

Expected: all voice profile tests pass.

### Task 3: Implement Fake Local CLI Merge

**Files:**
- Modify: `src/babelecho/voice_profile.py`
- Test: `tests/test_voice_profile.py`

- [ ] **Step 1: Write failing fake wrapper test**

Add a test that creates a fake wrapper script:

```python
def test_local_cli_voice_profile_merges_wrapper_summary(tmp_path: Path):
    wrapper = tmp_path / "fake_voice_profile_wrapper.py"
    wrapper.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--audio-file", required=True)
parser.add_argument("--diarization-json", required=True)
parser.add_argument("--speaker-profiles-json", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--output-json", required=True)
parser.add_argument("--model")
parser.add_argument("--device")
parser.add_argument("--min-sample-ms")
parser.add_argument("--max-samples-per-speaker")
args = parser.parse_args()

output_dir = Path(args.output_dir)
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / "speaker_1.json").write_text(
    json.dumps({"speaker_id": "speaker_1", "embedding": [0.1, 0.2]}),
    encoding="utf-8",
)
Path(args.output_json).write_text(json.dumps({
    "provider": "fake_embedding",
    "model": args.model,
    "speakers": [
        {
            "id": "speaker_1",
            "sample_count": 1,
            "sample_duration_ms": 4200,
            "profile_kind": "speaker_embedding",
            "embedding_status": "computed",
            "embedding_artifact": "asr/voice-profiles/speaker_1.json"
        }
    ]
}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    run_paths = create_run(tmp_path / "workspace", "voice-profile-local-cli")
    _write_profiles(run_paths)
    audio_dir = run_paths.run_dir / "audio"
    audio_dir.mkdir(parents=True)
    (audio_dir / "input.wav").write_bytes(b"fake audio")
    write_json(run_paths.source_json, {"audio_input": "audio/input.wav"})
    write_json(run_paths.run_dir / "asr" / "diarization.json", {"segments": []})

    apply_voice_profile_config(
        {
            "provider": "local_cli",
            "command": f"{sys.executable} {wrapper}",
            "model": "fake-model",
            "device": "cpu",
            "min_sample_ms": 1500,
            "max_samples_per_speaker": 5,
        },
        run_paths,
        config_path=tmp_path / "local-audio.yaml",
    )

    profiles = read_json(run_paths.run_dir / "asr" / "speaker-profiles.json")
    assert profiles["speakers"][0]["embedding_status"] == "computed"
    assert profiles["speakers"][0]["embedding_artifact"] == "asr/voice-profiles/speaker_1.json"
    assert (run_paths.run_dir / "asr" / "voice-profiles" / "speaker_1.json").exists()
```

Also import `sys` in the test file.

- [ ] **Step 2: Run red test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py::test_local_cli_voice_profile_merges_wrapper_summary -q
```

Expected: fail because local CLI execution and summary merge are not implemented.

- [ ] **Step 3: Implement local CLI execution**

In `src/babelecho/voice_profile.py`, implement:

```python
def _resolve_audio_input(run_paths: RunPaths) -> Path:
    source = _require_mapping(read_json(run_paths.source_json), "audio source")
    audio_input = source.get("audio_input")
    if not isinstance(audio_input, str) or not audio_input.strip():
        raise ValueError("source.audio_input is required before voice profile extraction")
    audio_path = run_paths.run_dir / audio_input
    if not audio_path.exists():
        raise ValueError(f"Voice profile audio input does not exist: {audio_path}")
    return audio_path
```

Build the command:

```python
audio_path = _resolve_audio_input(run_paths)
diarization_path = run_paths.run_dir / "asr" / "diarization.json"
profiles_path = run_paths.run_dir / "asr" / "speaker-profiles.json"
output_dir = run_paths.run_dir / "asr" / "voice-profiles"
summary_path = output_dir / "summary.json"
command = _command_parts(command_value)
command.extend([
    "--audio-file", str(audio_path),
    "--diarization-json", str(diarization_path),
    "--speaker-profiles-json", str(profiles_path),
    "--output-dir", str(output_dir),
    "--output-json", str(summary_path),
])
```

Append optional `model`, `device`, `min_sample_ms`, and `max_samples_per_speaker` with CLI names:

```text
--model
--device
--min-sample-ms
--max-samples-per-speaker
```

Run with `subprocess.run(..., check=True, text=True, capture_output=True)` and raise a clear `RuntimeError` on non-zero exit, matching `src/babelecho/asr.py` style.

- [ ] **Step 4: Validate and merge wrapper summary**

Read `summary_path`, require it to be a mapping with `speakers` list, then reuse the same merge path as fixture summaries. Validate every `embedding_artifact` remains under `run_paths.run_dir`. Do not read vectors.

- [ ] **Step 5: Run green tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py -q
```

Expected: all voice profile tests pass.

### Task 4: Wire Local CLI Through Audio Pipeline

**Files:**
- Modify: `tests/test_audio_pipeline.py`
- No production file may be needed if Task 3 modifies `apply_voice_profile_config` only.

- [ ] **Step 1: Write CLI pipeline test**

Add a test beside `test_audio_convert_diarize_stage_applies_fixture_voice_profile` using the same ASR and diarization fixtures, but set:

```yaml
voice_profile:
  provider: local_cli
  command: "{sys.executable} {wrapper}"
  model: fake-model
  device: cpu
```

Assert:

```python
profiles = read_json(run_dir / "asr" / "speaker-profiles.json")
assert profiles["speakers"][0]["embedding_status"] == "computed"
assert profiles["speakers"][0]["embedding_artifact"] == "asr/voice-profiles/speaker_1.json"
assert status["outputs"]["speaker_profiles"] == "asr/speaker-profiles.json"
```

- [ ] **Step 2: Run test**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_applies_local_cli_voice_profile -q
```

Expected: pass after Task 3. If it fails, fix only the voice profile hook path.

### Task 5: Preserve Publish Privacy

**Files:**
- Modify: `tests/test_publish.py`
- Modify: `src/babelecho/publish.py` only if the test fails.

- [ ] **Step 1: Extend existing publish privacy test**

Ensure the test where `asr/speaker-profiles.json` contains:

```json
"embedding_status": "computed",
"embedding_artifact": "asr/voice-profiles/speaker_1.json"
```

asserts:

```python
assert artifact["asr"]["speaker_profiles"]["embedding_status"] == "computed"
assert "embedding_artifact" not in artifact["asr"]["speaker_profiles"]
assert not (
    run_paths.workspace
    / "published"
    / "episodes"
    / "audio-publish-run"
    / "asr"
    / "voice-profiles"
    / "speaker_1.json"
).exists()
```

- [ ] **Step 2: Run publish tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_publish.py -q
```

Expected: pass. If it fails, update `src/babelecho/publish.py` so public summaries remain summary-only and embedding artifacts are never copied.

### Task 6: Add Wrapper Skeleton

**Files:**
- Create: `tools/speaker_embedding_wrapper.py`
- Test: no model test in this task; CLI help only.

- [ ] **Step 1: Add wrapper CLI parser**

Create `tools/speaker_embedding_wrapper.py` with:

```python
#!/usr/bin/env python3
import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract speaker embeddings and write BabelEcho voice profile JSON."
    )
    parser.add_argument("--audio-file", required=True)
    parser.add_argument("--diarization-json", required=True)
    parser.add_argument("--speaker-profiles-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--min-sample-ms", type=int, default=1500)
    parser.add_argument("--max-samples-per-speaker", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    parse_args(argv)
    raise SystemExit(
        "speaker_embedding_wrapper.py is a contract stub; "
        "run a model-specific wrapper after the 5090D model probe."
    )


if __name__ == "__main__":
    raise SystemExit(main())
```

This skeleton documents the stable CLI shape but intentionally does not load a model.

- [ ] **Step 2: Run help smoke**

Run:

```bash
.conda/babelecho-dev/bin/python tools/speaker_embedding_wrapper.py --help
```

Expected: exits 0 and prints the arguments.

### Task 7: 5090D Model Probe

**Files:**
- Create ignored runtime notes only under `workspace/runs/` or `workspace/sources/`.
- Update docs after probe: `docs/5090D远程测试流程.md`
- Do not commit model caches or runtime config.

- [ ] **Step 1: Confirm no package install in base env**

On 5090D:

```bash
ssh my-5090d-host 'conda info --envs | rg "babelecho"'
```

Expected: existing project envs are visible. Do not install into `base`.

- [ ] **Step 2: Create or choose isolated voice profile env**

Use a separate environment name:

```bash
/home/th5090d/miniforge3/bin/conda create -n babelecho-voice-profile python=3.12 -y
```

Expected: env exists at `/home/th5090d/miniforge3/envs/babelecho-voice-profile`.

- [ ] **Step 3: Probe one candidate at a time**

Candidate order:

1. pyannote embedding if it can reuse the already accepted pyannote model access path.
2. SpeechBrain ECAPA if pyannote embedding is blocked or too awkward.
3. NeMo only if the first two are unsuitable.

For each candidate, run a short standalone Python script against the existing Practical AI 8-minute sample and record:

```text
model name
install commands
GPU/CPU device
embedding dimension
runtime on 8-minute sample
whether two speakers produce separate vectors
whether dependencies conflict with existing ASR/TTS/diarization envs
```

- [ ] **Step 4: Stop after a viable probe**

Do not wire a real model into BabelEcho until the probe has one clear candidate. If all candidates fail, mark the plan blocked with exact errors.

### Task 8: Docs, Resume, Verification, And Push

**Files:**
- Modify: `docs/plans/03-audio-first-asr/01-local-audio-asr-diarization.md`
- Modify: `docs/5090D远程测试流程.md`
- Modify: `docs/前端Artifact契约与只读界面说明.md`
- Modify: `resume-prompt.md`

- [ ] **Step 1: Update docs**

Document:

```yaml
voice_profile:
  provider: local_cli
  command: "/home/th5090d/miniforge3/envs/babelecho-voice-profile/bin/python tools/speaker_embedding_wrapper.py"
  model: speechbrain/spkrec-ecapa-voxceleb
  device: cuda
```

State that embeddings are run-local and not public. If the 5090D probe selects SpeechBrain ECAPA or NeMo instead of pyannote embedding, document that exact selected model name in this same config block.

- [ ] **Step 2: Run focused tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py tests/test_audio_pipeline.py tests/test_publish.py -q
```

Expected: pass.

- [ ] **Step 3: Run full tests**

Run:

```bash
.conda/babelecho-dev/bin/python -m pytest -q
```

Expected: pass.

- [ ] **Step 4: Run diff and secret checks**

Run:

```bash
git diff --check
/opt/homebrew/bin/gitleaks protect --staged --verbose
git -c core.quotePath=false diff --cached --name-only -z | xargs -0 /opt/homebrew/bin/trufflehog filesystem --fail --only-verified
git diff --cached | rg -n "(?i)(-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|Bearer [A-Za-z0-9._~+/-]{20,}|password\\s*[:=]|api[_-]?key\\s*[:=]|secret\\s*[:=])"
```

Expected: `gitleaks` and `trufflehog` find no leaks; grep returns no matches.

- [ ] **Step 5: Commit, push, and 5090D smoke**

Run:

```bash
git add src/babelecho/voice_profile.py src/babelecho/audio_pipeline.py src/babelecho/publish.py tools/speaker_embedding_wrapper.py tests/test_voice_profile.py tests/test_audio_pipeline.py tests/test_publish.py docs/plans/03-audio-first-asr/01-local-audio-asr-diarization.md docs/5090D远程测试流程.md docs/前端Artifact契约与只读界面说明.md resume-prompt.md
git commit -m "feat: add local voice profile provider"
git push origin main
ssh my-5090d-host 'cd /home/th5090d/Develop/personal_project/BabelEcho && git pull --ff-only && .conda/babelecho-dev/bin/python -m pytest tests/test_voice_profile.py tests/test_audio_pipeline.py::test_audio_convert_diarize_stage_applies_local_cli_voice_profile -q'
```

Expected: 5090D fixture/local CLI tests pass without installing a real embedding model.

## Acceptance Criteria

- `voice_profile.provider=local_cli` exists and is audio-first-only.
- Fake local CLI tests prove wrapper output can mark a speaker as `embedding_status=computed`.
- `embedding_artifact` remains a run-local relative path.
- Publish does not expose `embedding_artifact` in `artifact.json.asr.speaker_profiles`.
- Publish does not copy `asr/voice-profiles/*.json` into `workspace/published/`.
- 5090D model probe identifies one viable backend or records why none are ready.
- No voice clone or identity recognition is implemented.

## Risk Handling

- If wrapper output references an unknown speaker id, fail the `diarize` stage with a clear error.
- If wrapper exits non-zero, record the failure in `run.json` through the existing stage failure path.
- If a speaker has no long enough clean sample, set `embedding_status=unavailable`, `sample_count=0`, `sample_duration_ms=0`, and `embedding_artifact=null`.
- If model install conflicts with TTS or diarization packages, stop and use a separate 5090D environment.
- If any embedding data appears in `workspace/published/`, treat it as a privacy bug and fix before commit.
