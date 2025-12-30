# Tap Tone Pi - AI Agent Instructions

## Project Purpose
Measurement-only audio analyzer for guitar tonewoods - emits reproducible facts (peaks, MOE, provenance) as JSON artifacts. **No advisory or scoring logic**; interpretation lives in separate ToolBox repo.

## Quick Start
```bash
pip install -e .                                      # Install package
python -m tap_tone.main devices                       # List audio devices
python -m tap_tone.main record --device 1 --out ./captures/test --label "top_tap"
```
On Raspberry Pi: `sudo apt install portaudio19-dev` before install. Full dependencies: `pip install -r requirements.txt` (adds matplotlib, jsonschema, pyserial for modes).

## Critical: Import Boundary (CI-Enforced)
**NEVER import**: `app.`, `services.`, `rmos.`, `cam.`, `compare.`, `art_studio.`, `packages.`

This repo integrates with ToolBox via **file artifacts only** - no Python imports. CI runs `python ci/check_boundary_imports.py --preset analyzer` and fails on violations. See [boundary_spec.json](boundary_spec.json) and [docs/BOUNDARY_RULES.md](docs/BOUNDARY_RULES.md).

## Architecture
| Directory | Purpose |
|-----------|---------|
| `tap_tone/` | Core CLI: `capture.py` (sounddevice I/O), `analysis.py` (pure DSP), `storage.py` (artifact writes) |
| `modes/` | Standalone measurement scripts with CLI + JSON output |
| `modes/_shared/` | `manifest.py` for artifact bundling with SHA256 hashes |
| `schemas/measurement/` | JSON Schema validation for all artifact types |
| `examples/measurement/` | Canonical examples that validate against schemas |
| `gui/` | Optional Tkinter GUI (`gui/app.py`) - measurement-only, no advisory logic |
| `tap-tone-lab/` | Phase 1-2 multi-channel experimentation (separate package) |

## Key Patterns

### 1. Analysis is Pure (NO I/O)
`tap_tone/analysis.py` takes `np.ndarray` + params, returns frozen `AnalysisResult` dataclass. Never add file reads/writes here - use `storage.py` for persistence.

**Example:** `analyze_tap()` returns `AnalysisResult(dominant_hz, peaks, clipped, rms, confidence, spectrum_freq_hz, spectrum_mag)` with no side effects.

### 2. Artifact-First Output
Every capture produces: `audio.wav`, `analysis.json`, `spectrum.csv`, `session.jsonl`. New modes must emit JSON artifacts with `artifact_type` field (e.g., `"artifact_type": "bending_test"`).

### 3. Schema-Driven Validation
Add artifact types by: (1) schema in `schemas/measurement/*.schema.json`, (2) example in `examples/measurement/`, (3) test in `tests/test_measurement_schemas.py`.

**Pattern:** Each test validates example against schema using `jsonschema.validate()`. Run `pytest tests/test_measurement_schemas.py` or `make validate-schemas`.

### 4. Measure, Don't Interpret
Output raw peaks/MOE/hashes - never "tone quality" scores or design advice. If logic requires guitar structural knowledge, it belongs in ToolBox.

**ADR Context:** See [ADR-0001](docs/ADR-0001-measurement-scope.md) (measurement protocol), [ADR-0004](docs/ADR-0004-acoustic-vs-structural-boundary.md) (boundary enforcement).

## Developer Workflows
```bash
# Run tests (schema validation)
pytest -q tests/

# Validate all example artifacts
make validate-schemas

# Tap-tone from device / offline WAV
make run-tap OUT=out/tap.json DUR=3 SR=44100
python modes/tap_tone/offline_from_wav.py --wav path.wav --out out/tap.json

# Bending stiffness (single / batch)
make bend-single OUT=out/bend.json
make bend-batch CSV=data/deflection_runs.csv OUT=out/results.csv

# Bending mode with full bundle (displacement/load series + plots)
make bend-mode-sample --pack  # Creates timestamped bundle in out/bend_*
make bend-mode-validate       # Validates latest bundle against schema

# Serial acquisition (load cell / dial indicator)
python modes/acquisition/loadcell_serial.py --port COM3 --config config/devices/loadcell_example.json
python modes/acquisition/dial_indicator_serial.py --port COM4 --out out/disp.json

# Bundle with manifest (SHA256 + metadata)
make manifest OUT=out/manifest.json ARTIFACTS="--artifact out/tap.json --artifact out/bend.json" RIG="--rig operator=Ross"

# GUI launcher (Tkinter)
python gui/app.py
```

## Adding New Features
| Change | Location | Required |
|--------|----------|----------|
| DSP algorithm | `tap_tone/analysis.py` | Keep pure; unit test with synthetic signals; no file I/O |
| New measurement mode | `modes/<mode_name>/` | CLI script + JSON output with `artifact_type` field |
| New artifact schema | `schemas/measurement/` | Schema + example + `tests/test_measurement_schemas.py` entry |
| Serial acquisition | `modes/acquisition/` | Config in `config/devices/` + emit `load_series.json` or `displacement_series.json` |

**Mode checklist:** (1) Standalone CLI, (2) Emits JSON with `artifact_type`, (3) Makefile target, (4) Schema validation.

## Known Constraints
- Mono capture emits scalar `rms`/`clipped`; multi-channel schemas in `docs/schemas/` expect arrays (see [ADR-0002](docs/ADR-0002-multi-channel-expansion.md))
- Config defaults in `tap_tone/config.py`: 48kHz sample rate, 20Hz highpass, peaks 40-2000Hz
- Phase 1 (single-channel) must be complete before multi-channel work (see [ADR-0001](docs/ADR-0001-measurement-scope.md))
- GUI (`gui/app.py`) is measurement-only - no scoring, no tone advice
- MOE calculations: 3-point/4-point bending formulas in `modes/bending_stiffness/deflection_to_moe.py`
