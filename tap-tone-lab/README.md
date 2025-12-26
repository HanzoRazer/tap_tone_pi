# Tap Tone Lab (Offline / Phase 1–2)

A **desktop/offline** tap-tone measurement + testing repo that produces **durable artifact bundles**:
- `audio.wav`
- `analysis.json`
- `spectrum.csv`
- optional: `channels.json`, `geometry.json`
- optional plots: `coherence.png`, `phase_deg.png`, `spectrum.png`, `waveform.png`

This repo is designed to evolve into multi-channel acoustic testing while keeping claims scientifically defensible.

## Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Phase 1 CLI (primary)

List devices:

```bash
tap-tone devices
```

Record + analyze:

```bash
tap-tone record --device 1 --seconds 2.5 --out ./captures_phase1 --label "bridge_tap"
```

Live loop:

```bash
tap-tone live --device 1 --seconds 2.5 --out ./captures_phase1 --label "live_bridge"
```

### Alternate entrypoint (exact same CLI)

If you prefer module execution (no console script):

```bash
python -m tap_tone.main devices
python -m tap_tone.main record --device 1 --seconds 2.5 --out ./captures_phase1
```

> Both entrypoints share one parser (`tap_tone/_cli_core.py`) so they cannot drift.

## Phase 2: List devices for 2-channel capture

```bash
python scripts/two_channel_coherence.py devices
```

## Run a 2-channel capture (Phase 2)

> Requires a **single 2-input audio device** (shared clock), e.g. a USB audio interface with 2 mic inputs.

```bash
python scripts/two_channel_coherence.py run \
  --device 3 \
  --seconds 3 \
  --sample-rate 48000 \
  --out ./captures_phase2 \
  --label "OM_bridge_tap_stereo" \
  --focus-band "60,600" \
  --write-channels \
  --write-geometry \
  --mic-distance-mm 300 \
  --write-plots \
  --plot-max-hz 1500
```

## Validate a bundle

```bash
python scripts/validate_bundle.py \
  --capture-dir ./captures_phase2/capture_YYYYMMDDTHHMMSSZ \
  --schemas-dir ./schemas
```

## Generate a manifest (hashes)

```bash
python scripts/make_manifest.py --capture-dir ./captures_phase2/capture_YYYYMMDDTHHMMSSZ
```

## Generate a PDF lab report

```bash
python scripts/reports/generate_report.py \
  --bundle ./captures_phase2/capture_YYYYMMDDTHHMMSSZ \
  --out ./captures_phase2/capture_YYYYMMDDTHHMMSSZ/report.pdf \
  --title "Tap Tone Lab Report" \
  --author "Your Name"
```

Automatically includes (if present): metadata.json, geometry.json, grid.json, wolf_map.json, resonance_table.json, plots/*.png, manifest.json

## Time-gated impulse response (Phase 2/3 extension)

Generate chirp excitation:

```bash
python scripts/time_gated_ir.py generate-chirp --out ./chirp.wav --fs 48000 --duration 3.0 --f0 30 --f1 2000
```

Process captured audio with time-gating (suppresses room reflections):

```bash
python scripts/time_gated_ir.py process \
  --audio ./captures/capture_123/audio.wav \
  --excitation ./chirp.wav \
  --out ./captures/capture_123 \
  --gate-start-ms 5.0 \
  --gate-end-ms 100.0 \
  --window tukey \
  --write-plots
```

Outputs: `impulse/ir_*.npy`, `impulse/gated_spectrum_*.csv`, `plots/impulse_response.png`, `plots/gated_spectrum.png`

## RMOS RunArtifact export

Generate RMOS-compatible artifact payload:

```bash
python scripts/rmos_export.py \
  --bundle ./captures/capture_123 \
  --out ./exports/export_123 \
  --instrument-id "OM-001" \
  --build-stage "pre_finish" \
  --operator "Your Name"
```

With attachments for RMOS upload:

```bash
python scripts/rmos_export.py --bundle ./captures/capture_123 --out ./exports/export_123 --pack-attachments
```

Outputs: `rmos_artifact.json` (POST to RMOS API), `manifest.json`, optional `attachments/`

## Repeatability run (Phase 1 gate helper)

This expects a Phase-1 style `tap_tone` module; if you aren't using it yet, skip this script until you add Phase 1 module code.

```bash
python scripts/repeatability_run.py --device 3 --out ./captures_repeat --takes 10 --seconds 2.5 --sample-rate 48000
```

## Docs

See `docs/ADR-0001..0007` for the operating rules, boundaries, and integration plan.

- ADR-0001: Measurement scope and protocol v0.1
- ADR-0002: Multi-channel expansion (Phase 2-5)
- ADR-0003: Artifact schema for multi-channel bundles
- ADR-0004: Acoustic vs structural boundary (claim constraints)
- ADR-0005: Repeatability, variance, and confidence
- ADR-0006: RMOS RunArtifact mapping (forward-compatible)
- ADR-0007: Phase 3 roving-grid ODS methodology (research)
