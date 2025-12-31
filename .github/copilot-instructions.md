# Tap Tone Pi — AI Coding Agent Instructions

## Mission & Boundaries
**Acoustic measurement instrument for luthiers** — produces reproducible FFT/peak data, NOT voicing advice.

- ✅ Output facts: peak frequencies, coherence, phase, RMS, spectra, ODS shapes, Wolf Stress Index
- ❌ NO design recommendations, tone scoring, or optimization suggestions
- See [MEASUREMENT_BOUNDARY.md](../docs/MEASUREMENT_BOUNDARY.md) for full policy

## Repository Structure
```
tap_tone_pi/
├── tap_tone/           # Phase 1: Core single-channel CLI (frozen baseline)
│   ├── capture.py      # sounddevice audio I/O
│   ├── analysis.py     # FFT + peak detection (pure functions)
│   ├── storage.py      # Artifact persistence (WAV/JSON/CSV)
│   └── main.py         # CLI entrypoint
├── scripts/            # Phase 2: ODS/Coherence/Wolf metrics
│   ├── roving_grid_capture.py    # 2-channel grid capture
│   ├── ods_compute.py            # Transfer functions H(f)
│   ├── grid_coherence.py         # γ²(f) coherence analysis
│   └── wolf_metrics.py           # WSI(f) wolf stress index
├── modes/              # Specialized measurement modes
│   ├── bending_rig/    # MOE from load+displacement streams
│   ├── acquisition/    # Serial capture (loadcell, dial indicator)
│   └── _shared/        # emit_manifest.py, common utilities
├── config/             # Device and grid configurations
│   ├── devices/        # loadcell_example.json, dial_indicator_example.json
│   └── grids/          # guitar_top_35pt.json (ODS grid definitions)
├── docs/schemas/       # JSON schemas for artifact validation
├── contracts/          # External interface schemas
└── Makefile            # Measurement chain targets
```

**Two packages exist**: `tap_tone/` (stable v1.0) and `tap-tone-lab/` (experimental). Check which you're modifying.

## Key Commands
```bash
# Install
pip install -e .

# Phase 1 CLI (tap tone)
tap-tone devices                           # List audio inputs
tap-tone record --device 1 --seconds 2.5 --out ./captures --label "bridge_tap"
tap-tone live --device 1 --out ./captures  # Continuous loop

# Phase 2: ODS / Wolf Metrics (Makefile)
make grid-capture DEVICE=1 GRID=config/grids/guitar_top_35pt.json OUT=out/grid_001
make phase2-analyze CAPDIR=out/grid_001 FREQS=100,150,185,220,280
# Or individual steps:
make ods-compute CAPDIR=out/grid_001 FREQS=100,150,185,220,280
make grid-coherence CAPDIR=out/grid_001 FREQS=100,150,185,220,280
make wolf-metrics CAPDIR=out/grid_001 WSI_THRESH=0.6

# Bending Rig (MOE measurement)
make loadcell CFG=config/devices/loadcell_example.json OUT=out/run/load_series.json
make dial PORT=COM3 OUT=out/run/displacement_series.json UNIT=mm DUR=8
make bend-merge-moe LOAD=out/run/load_series.json DISP=out/run/displacement_series.json \
     OUTDIR=out/run/rig METHOD=3point SPAN=400 WIDTH=20 THICKNESS=3.0
make plot-fvd PAIRS=out/run/rig/pairs.csv OUT=out/run/rig/f_vs_d.png
make manifest OUT=out/run/manifest.json ARTIFACTS="--artifact ..." RIG="--rig k=v"
```

See [docs/MEASUREMENT_README.md](../docs/MEASUREMENT_README.md) for full bending rig workflow.

## Artifact Contract (Non-Negotiable)
Every capture produces a timestamped folder:
```
capture_20251231T120000Z/
├── audio.wav       # int16, mono or multi-channel
├── analysis.json   # ts_utc, dominant_hz, peaks[], rms, clipped, confidence
├── spectrum.csv    # freq_hz,magnitude (for reprocessing)
└── session.jsonl   # Append-only session log (at parent dir)
```

Phase 2 grid captures produce:
```
grid_run_001/
├── grid.json               # Grid definition (copied)
├── points/                 # Per-point captures
│   ├── A1/audio.wav        # 2-channel: ref + roving
│   ├── A1/capture_meta.json
│   └── ...
└── derived/                # Computed outputs
    ├── ods/ods_summary.json
    ├── coherence/coherence_summary.json
    └── wolf/wolf_candidates.json
```

Schema validation: `python scripts/validate_bundle.py --schemas-dir ./docs/schemas`

## Code Patterns

### DSP Functions Must Be Pure
```python
# ✅ Good: analysis.py returns data, no I/O
def analyze_tap(audio: np.ndarray, sample_rate: int, **params) -> AnalysisResult: ...

# ❌ Bad: mixing analysis with file writes
def analyze_and_save(audio, path): ...
```

### Dataclasses for Structured Results
```python
@dataclass(frozen=True)
class Peak:
    freq_hz: float
    magnitude: float

@dataclass(frozen=True)  
class AnalysisResult:
    dominant_hz: float | None
    peaks: list[Peak]
    spectrum_freq_hz: np.ndarray  # Always return full spectrum
    spectrum_mag: np.ndarray
```

### Storage Layer Handles All I/O
`storage.py` writes artifacts — analysis code should never touch filesystem.

## Technical Stack
- Python 3.10+ (Pi OS compatibility)
- `sounddevice` for audio (NOT PyAudio)
- `scipy.signal` for FFT, filtering, peak detection, coherence
- `scipy.fft.rfft` with Hanning window
- Butterworth 2nd-order highpass at 20Hz
- `pyserial` for hardware acquisition
- `matplotlib` for plotting

## When Modifying Code

### Adding DSP Features
1. Keep functions pure — input arrays, output dataclasses
2. Return full spectrum arrays (not just peaks) for downstream reprocessing
3. Test with synthetic signals: `np.sin(2*np.pi*freq*t)` at known frequencies
4. Update schema if adding new output fields

### Multi-Channel Work (Phase 2+)
- Requires single audio interface with shared clock (no independent USB mics)
- Phase accuracy is critical — verify with `scripts/grid_coherence.py`
- ODS: `H(f) = FFT(roving) / FFT(reference)` — reference is channel 0
- Wolf metrics: WSI = weighted sum of gradient energy, phase entropy, localization, coherence

### Schema Changes
1. Update `docs/schemas/*.schema.json`
2. Run `python scripts/validate_bundle.py` against existing captures
3. Document in ADR if breaking backward compatibility

## Hardware Context
- Primary target: Raspberry Pi 4/5 with USB measurement mic (UMIK-1 class)
- Test on Pi — ALSA behavior differs from desktop
- Aim for RMS 0.01–0.05, avoid clipping (flagged in `analysis.json`)

## Related Documentation
- [BASELINE.md](../tap-tone-lab/BASELINE.md) — v1.0 frozen baseline definition
- [DEV_HANDOFF.md](../DEV_HANDOFF.md) — Architecture overview
- [ADR-0001](../docs/ADR-0001-measurement-scope.md) — Measurement-only boundary rationale
- [MEASUREMENT_README.md](../docs/MEASUREMENT_README.md) — Bending rig quick-start
