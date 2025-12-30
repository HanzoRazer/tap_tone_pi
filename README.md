# Tap Tone PI (Desktop)

A small Raspberry Pi desktop utility to record a tap impulse with a USB mic, analyze resonant peaks, and save artifacts.

## Install (Pi)

```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-dev
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Run

List audio devices:
```bash
python -m tap_tone.main devices
```

Record + analyze:
```bash
python -m tap_tone.main record \
  --device 1 \
  --seconds 2.5 \
  --out ./captures/session_001 \
  --label "OM_top_bridge_tap"
```

Live mode (simple loop):
```bash
python -m tap_tone.main live --device 1 --out ./captures/live
```

## Outputs

Each capture produces:

* `audio.wav`
* `analysis.json` (peaks, dominant frequency, confidence)
* `spectrum.csv` (freq_hz, magnitude)
* `session.jsonl` (append-only log)

## Measurement Bundle Quickstart (Modes + Makefile)

Install dependencies for measurement modes:

```bash
pip install -r requirements.txt
```

Run tap-tone (writes JSON + spectrum PNG):

```bash
make run-tap OUT=out/tap_tone.json DUR=3 SR=44100
```

Single MOE fact (3-point bend):

```bash
make bend-single OUT=out/bending_test.json
```

Batch MOE from CSV:

```bash
make bend-batch CSV=data/deflection_runs.csv OUT=out/moe_results.csv
```

Provenance hashing (no computation):

```bash
make provenance-hash FILE=path/to/grain_field.png OUT=out/provenance.json
```

Emit a manifest.json for one run:

```bash
make manifest OUT=out/manifest.json \
  ARTIFACTS="--artifact out/tap_tone.json --artifact out/bending_test.json" \
  RIG="--rig fixture=3-point --rig span_mm=400 --rig operator=Ross" \
  NOTES="--notes Tap + bending run"
```

Validate example artifacts against schemas:

```bash
make validate-schemas
```

Notes:
- Measurement-only: modes under `modes/` emit facts (peaks, MOE, provenance) and manifests; no advisory or design recommendations.
- Schemas live in `schemas/measurement/`; tiny fixtures in `examples/measurement/`.

## Bending Stiffness Bundle CLI

Generate a full bending stiffness bundle (raw readings + analysis + manifest):

```bash
make bend-mode-sample
```

Pack the latest sample as a ZIP:

```bash
make bend-mode-pack
```

Validate the latest bundle against the bending schema:

```bash
make bend-mode-validate
```

Direct CLI usage (inline pairs or CSV):

```bash
python3 scripts/bending_stiffness_mode.py \
  --out ./out \
  --specimen-id S1 \
  --material-role top \
  --wood-species spruce \
  --grain-orientation longitudinal \
  --span-mm 400 \
  --pair 5,0.2 --pair 10,0.41 --pair 15,0.62 --pair 20,0.83 \
  --method three_point_bending \
  --units-length mm \
  --units-force N
```

Or from CSV with headers `load,deflection`:

```bash
python3 scripts/bending_stiffness_mode.py \
  --out ./out \
  --specimen-id S2 \
  --material-role brace_stock \
  --span-mm 380 \
  --readings-csv ./data/readings.csv \
  --method three_point_bending \
  --units-length mm \
  --units-force N
```

## Measurement Bundle v2 (Offline + Tests + CI)

See [docs/MEASUREMENT_README.md](docs/MEASUREMENT_README.md) for:
- Offline tap analysis from WAV files
- Batch deflection template + CSV loader
- Unit tests (pytest)
- GitHub Actions workflows (CI validation)

Quick start:

Offline tap:
```bash
make run-tap-offline WAV=data/sample_tap.wav OUT=out/tap_offline.json
```

Tests (local):
```bash
pip install pytest
pytest -q tests/test_measurement_schemas.py
```

All CI workflows:
- `no_logic_creep.yml` — grep guardrail (no advisory terms in modes/)
- `schemas_validate.yml` — schema validation for examples
- `examples_matrix.yml` — detailed measurement example validation
- `bending_stiffness_validate.yml` — bending bundle with uncertainty
- `boundary_guard.yml` — prevents importing ToolBox namespaces

---

<a id="boundary-rules"></a>
## 🔒 Boundary Rules (Enforced by CI)

This repository enforces a hard architectural boundary.

❌ Cross-repo imports are not allowed.  
✅ Integration must happen via artifacts, schemas, or HTTP APIs.

If CI fails with a boundary violation:
- Do NOT add an exception.
- Do NOT "just import it".
- Instead, define or extend a contract between systems.

See [docs/architecture/BoundarySpec.md](docs/architecture/BoundarySpec.md) for rationale.

