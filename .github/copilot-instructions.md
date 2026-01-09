# Tap Tone Pi — AI Coding Agent Instructions

## Mission (Non-Negotiable)
**Acoustic measurement instrument** — outputs facts (peaks, coherence, phase, RMS), NOT design advice.
- ✅ FFT spectra, ODS transfer functions, Wolf Stress Index, MOE values
- ❌ NO tone scoring, voicing recommendations, or optimization suggestions

## CI Boundary — Will Fail Build
```bash
python ci/check_boundary_imports.py --preset analyzer  # Runs in CI
```
**Forbidden imports:** `app.*`, `services.*`, `packages.*` (Luthier's ToolBox namespaces)  
**Pass data via artifacts** (JSON/CSV/WAV + manifests), never Python imports.

## Architecture
```
tap_tone/          # Phase 1 CLI (frozen v1.0) — single-channel tap tone
scripts/phase2/    # Phase 2 package — 2-channel ODS, coherence, wolf metrics
modes/             # Specialized modes: bending_rig/, chladni/, acquisition/
contracts/         # Schema registry + *.schema.json output contracts
```
**Two packages:** `tap_tone/` is stable; `tap-tone-lab/` is experimental. Know which you're editing.

## Commands
```bash
pip install -e .                                    # Install
make test                                           # pytest suite
python scripts/phase2_slice.py run --synthetic \    # Validate without hardware
  --grid examples/phase2_grid_mm.json --out ./runs_phase2
```

## Code Patterns (Enforced)

### Pure DSP Functions — No I/O in Analysis
```python
# tap_tone/analysis.py — returns dataclass, never writes files
def analyze_tap(audio: np.ndarray, sample_rate: int, **params) -> AnalysisResult: ...
```
All file writes go through `storage.py` or `modes/_shared/emit_manifest.py`.

### WAV I/O — Single Source of Truth
```python
from modes._shared.wav_io import read_wav_mono, read_wav_2ch, write_wav_mono, write_wav_2ch
# Readers: float32 [-1, 1] | Writers: accept float32, emit int16 PCM
```
Do NOT use `scipy.io.wavfile` directly elsewhere — causes int16↔float drift.

### Frozen Dataclasses for Results
```python
@dataclass(frozen=True)
class TFResult:  # scripts/phase2/dsp.py
    freq_hz: np.ndarray
    H_mag: np.ndarray
    H_phase_deg: np.ndarray
    coherence: np.ndarray
```
Always return full spectrum arrays for downstream reprocessing.

## Artifact Outputs
Phase 2 sessions produce (`runs_phase2/session_*/`):
- `points/point_*/audio.wav` — 2-channel (ch0=reference, ch1=roving)
- `derived/ods_snapshot.json` — transfer function per point  
- `derived/wolf_candidates.json` — WSI candidates

**Schema validation:** All outputs validated against `contracts/*.schema.json`.  
**Registry:** `contracts/schema_registry.json` — bump version on schema changes.

## When Adding Features
1. **DSP:** Pure functions → frozen dataclass output → test with synthetic sine bursts
2. **New output field:** Update schema, bump `schema_registry.json` version
3. **Multi-channel:** Requires shared-clock interface (not independent USB mics)
4. **Breaking change:** Document in `docs/ADR-*.md`

## Key References
- [docs/MEASUREMENT_BOUNDARY.md](../docs/MEASUREMENT_BOUNDARY.md) — Scope policy
- [docs/MEASUREMENT_README.md](../docs/MEASUREMENT_README.md) — Bending rig quickstart
- [DEV_HANDOFF.md](../DEV_HANDOFF.md) — Architecture overview
