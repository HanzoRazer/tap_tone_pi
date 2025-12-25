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

## List devices

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

## Repeatability run (Phase 1 gate helper)

This expects a Phase-1 style `tap_tone` module; if you aren't using it yet, skip this script until you add Phase 1 module code.

```bash
python scripts/repeatability_run.py --device 3 --out ./captures_repeat --takes 10 --seconds 2.5 --sample-rate 48000
```

## Docs

See `docs/ADR-0001..0006` for the operating rules, boundaries, and integration plan.
