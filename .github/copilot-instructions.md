# Tap Tone Pi - AI Agent Instructions

## Project Purpose
Measurement-only audio analyzer for guitar tonewoods. Emits reproducible facts (peaks, MOE, provenance) as JSON artifacts. **No advisory/scoring logic** - interpretation lives in separate ToolBox repo.

## Critical: Import Boundary (CI-Enforced)
**NEVER import**: `app.`, `services.`, `packages.`, `rmos.`, `cam.`, `compare.`, `art_studio.`

This repo integrates with ToolBox via **file artifacts only**. CI runs `python ci/check_boundary_imports.py --preset analyzer` and fails on violations. See [boundary_spec.json](boundary_spec.json).

## Architecture
| Directory | Purpose |
|-----------|---------|
| `tap_tone/` | Core: `analysis.py` (pure DSP), `capture.py` (audio I/O), `storage.py` (persistence) |
| `modes/` | Standalone measurement scripts (tap_tone, bending_stiffness, acquisition) |
| `modes/_shared/manifest.py` | Artifact bundling with SHA256 hashes |
| `schemas/measurement/` | JSON Schema validation for artifact types |
| `examples/measurement/` | Canonical examples validating against schemas |

## Key Patterns

### 1. Analysis is Pure (NO I/O)
`tap_tone/analysis.py` takes `np.ndarray` + params → returns frozen `AnalysisResult` dataclass. Never add file I/O here; use `storage.py` for persistence.

### 2. Artifact-First Output
Every mode emits JSON with `"artifact_type"` field. New artifacts require:
1. Schema in `schemas/measurement/<type>.schema.json`
2. Example in `examples/measurement/<type>.json`
3. Test in `tests/test_measurement_schemas.py`

### 3. Measure, Don't Interpret
Output raw measurements only. No "tone quality" scores or design advice - that belongs in ToolBox.

## Essential Commands
```bash
pip install -e . && pip install -r requirements.txt  # Install
pytest -q tests/                                      # Run tests
make validate-schemas                                 # Validate artifacts
make run-tap OUT=out/tap.json DUR=3 SR=44100         # Tap-tone capture
make bend-single OUT=out/bend.json                   # Single MOE calculation
make bend-mode-sample                                # Full bending bundle
python gui/app.py                                    # GUI launcher
```

## Adding Features
| Change | Location | Requirement |
|--------|----------|-------------|
| DSP algorithm | `tap_tone/analysis.py` | Keep pure; no file I/O |
| New mode | `modes/<name>/` | CLI + JSON with `artifact_type` + Makefile target |
| New schema | `schemas/measurement/` | Schema + example + test entry |

## Constraints
- Config defaults in `tap_tone/config.py`: 48kHz sample rate, 20Hz highpass, peaks 40-2000Hz
- ADRs in `docs/ADR-*.md` document architectural decisions
