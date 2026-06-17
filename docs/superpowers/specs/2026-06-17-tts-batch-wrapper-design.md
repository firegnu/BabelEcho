# TTS Batch Wrapper Design

Date: 2026-06-17

## Goal

Reduce real podcast synthesis time by avoiding one CosyVoice model load per segment.

## Current Root Cause

`synthesize_segments()` loops over script segments and calls `synthesize_text_to_wav()` once per segment. For `tts.provider: local_cli`, each call starts a new `tts-wrapper` process. The wrapper imports Torch/CosyVoice and initializes `AutoModel(...)` inside that process, so a 75 segment episode loads the model 75 times.

## Design

Add a batch path for `local_cli` while preserving the existing single-segment wrapper interface.

- `src/babelecho/synthesize.py` continues to produce the same `segments/<id>.wav` files and `segments/manifest.json`.
- `src/babelecho/tts.py` gains a `synthesize_many_to_wav()` helper.
- For `provider: fixture`, the helper writes silent wav files in-process as before.
- For `provider: local_cli`, the helper writes each segment text to the existing `segments/<id>.txt`, writes a batch JSON file, then starts the configured wrapper once with `--batch-file`.
- `tools/cosyvoice_tts_wrapper.py` accepts either the existing `--text-file --output` pair or the new `--batch-file`.
- In batch mode, the wrapper resolves voice/model config once, loads `AutoModel` once, then loops over items and writes each output wav.

## Data Format

`segments/tts-batch.json`:

```json
{
  "items": [
    {
      "text_file": "workspace/runs/<run-id>/segments/0001.txt",
      "output": "workspace/runs/<run-id>/segments/0001.wav"
    }
  ]
}
```

Paths are written as strings exactly as passed to the wrapper. The wrapper does not need run context.

## Compatibility

The existing wrapper command remains valid:

```bash
tts-wrapper --text-file segment.txt --output segment.wav --voice default-zh
```

No publish, assemble, manifest, or downstream artifact format changes.

## Error Handling

If any batch item has empty text or CosyVoice generates no audio, wrapper exits non-zero. `subprocess.run(..., check=True)` keeps the existing failure behavior and marks `synthesize` failed.

## Tests

- Unit test that `synthesize_many_to_wav()` with `local_cli` invokes `subprocess.run` once for multiple segments and forwards voice options.
- Unit test that wrapper batch mode loads fake `AutoModel` once and saves all requested outputs.
- Existing single-segment wrapper tests continue to pass.
