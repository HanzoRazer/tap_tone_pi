# Tap Tone Pi — Consolidation Exit Summary

**Completed:** 2026-02-05
**Release:** v2.0.0
**Tag:** https://github.com/HanzoRazer/tap_tone_pi/releases/tag/v2.0.0

---

## ✅ All Phases Complete

### Phase 0: Critical Fixes (commit `3626ec9`)
- [x] Bug 2 fixed: WAV argument transposition in `tap_tone/storage.py:57`
- [x] Regression test added: `tests/test_storage_wav_roundtrip.py`
- [x] Version bumped to 2.0.0 in `pyproject.toml`
- [x] CHANGELOG updated with v2.0.0 section
- [x] Schema location documented: `contracts/schemas/` is canonical
- [x] `out/` directory removed from git tracking (64 files)
- [x] `ttp` CLI alias added to entry points

### Phase 1: Test Baseline (commit `481b500`)
- [x] 13 Phase 1 pipeline integration tests: `tests/test_phase1_pipeline_integration.py`
- [x] 8 Chladni pipeline integration tests: `tests/test_chladni_pipeline_integration.py`
- [x] Test baseline established: 168 collected, 148 passed initially

### Phase 2: Package Skeleton (commit `5aa1b84`)
- [x] Created `tap_tone_pi/` package with 10 subpackages
- [x] Copied canonical WAV I/O: `tap_tone_pi/io/wav.py`
- [x] Copied manifest generation: `tap_tone_pi/io/manifest.py`

### Phase 3: Core + Capture Migration (commit `9fb553d`)
- [x] `tap_tone_pi/core/analysis.py` (from tap-tone-lab, includes clipping penalty fix)
- [x] `tap_tone_pi/core/config.py` (from tap-tone-lab)
- [x] `tap_tone_pi/core/dsp.py` (from scripts/phase2)
- [x] `tap_tone_pi/capture/loadcell_serial.py`
- [x] `tap_tone_pi/capture/dial_indicator_serial.py`
- [x] `tap_tone_pi/capture/simulators.py` (combined)
- [x] `tap_tone_pi/bending/merge_and_moe.py`
- [x] `tap_tone_pi/bending/plot_f_vs_d.py`
- [x] `tap_tone_pi/chladni/peaks_from_wav.py`
- [x] `tap_tone_pi/chladni/index_patterns.py`

### Phase 4: CLI + GUI Rewrite (commit `f479e53`)
- [x] Unified CLI dispatcher created: `tap_tone_pi/cli/main.py`
- [x] GUI copied with binding bug fix: `tap_tone_pi/gui/app.py`
- [x] Updated `__init__.py` for cli and gui subpackages
- [x] Entry points updated in `pyproject.toml` (ttp primary)
- [x] Explicit package discovery added to pyproject.toml
- [x] Test baseline verified: 190 passed (up from 170!)
- [x] Committed: `f479e53`

### Phase 5: Cleanup (commit `993417a`)
- [x] Deleted `tap-tone-lab/` directory (49 files, -7,305 lines)
- [x] Verified no imports broke (190 tests pass)
- [x] `modes/` kept — still imported by tests/scripts (future migration)
- [x] `gui/` kept — fallback import in CLI works

### Phase 6: GUI Enhancements (commit `5381568`)
- [x] Schema validation already in CI (`contracts-validate.yml`, `schemas_validate.yml`)
- [x] GUI: Direct Python imports (`tap_tone_pi.core.analysis`, `tap_tone_pi.io.wav`)
- [x] GUI: Matplotlib inline spectrum visualization (`SpectrumViewer` class)
- [x] Graceful fallback to subprocess when direct imports unavailable

---

## Final Statistics

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 148 | 190 |
| Lines deleted | — | 7,305 |
| Packages | 3 fragmented | 1 unified |
| CLI entry points | tap-tone | ttp (primary) |
| Known bugs | 2 | 0 |
| Schema location | scattered | `contracts/schemas/` (canonical) |
| Artifact contract | implicit | explicit (schemas + pack) |

---

## Breaking Changes / Migration Notes

| Change | Impact | Action |
|--------|--------|--------|
| CLI entry point renamed | `tap-tone` → `ttp` (primary) | Update scripts/aliases |
| `out/` no longer tracked | Build artifacts excluded from git | Use `.gitignore`, create locally |
| `tap-tone-lab/` deleted | Old lab package removed | Import from `tap_tone_pi.*` |
| `quality_check.json` added | New evidence file per capture | Update validators/consumers |

**Shims retained (not extended):**
- `tap_tone/` — legacy imports still work, but add new code to `tap_tone_pi/`
- `gui/` fallback — CLI checks `tap_tone_pi.gui` first, falls back to `gui.app`

---

## Governance / Contract

**Canonical schema location:** `contracts/schemas/`

**Pack schema:** `viewer_pack_v1` (see `contracts/viewer_pack_v1.schema.json`)

**Guaranteed artifacts per capture:**

| File | Status | Description |
|------|--------|-------------|
| `audio.wav` | Required | PCM int16 WAV |
| `analysis.json` | Required | FFT peaks, dominant_hz, confidence |
| `quality_check.json` | Required | Verdict + triggered rules |
| `capture_meta.json` | Required | Device, sample rate, timestamp |
| `spectrum.png` | Optional | Visual spectrum plot |

**Schema policy:** `additionalProperties: true` — new files/fields may be added without breaking downstream consumers (ToolBox, validators).

**Evidence governance:**
- `ttp record` — QC recorded, not gated (evidence always produced)
- `ttp measure` — QC gated (blocks on FAIL, allows retry/override)

---

## Migration Scope

### Not Migrated (Intentional)

- `modes/` — retained for backwards compatibility with tests/scripts
- `tap_tone/` — shim layer retained, not extended
- `gui/` (legacy) — fallback import path, not primary

### Canonical Going Forward

| Purpose | Canonical Import |
|---------|------------------|
| Analysis | `tap_tone_pi.core.analysis.analyze_tap` |
| Capture | `tap_tone_pi.capture.record_audio` |
| Quality Gate | `tap_tone_pi.core.quality_gate.check_quality` |
| CLI | `tap_tone_pi.cli.main` (`ttp` entry point) |
| WAV I/O | `tap_tone_pi.io.wav` |

New code should be added to `tap_tone_pi/`, not legacy locations.

---

## Release

**Tag:** v2.0.0
**URL:** https://github.com/HanzoRazer/tap_tone_pi/releases/tag/v2.0.0

---

## New Package Structure

```
tap_tone_pi/
├── core/         ← analysis.py, config.py, dsp.py
├── capture/      ← loadcell, dial indicator, simulators
├── io/           ← wav.py, manifest.py
├── bending/      ← merge_and_moe.py, plot_f_vs_d.py
├── chladni/      ← peaks_from_wav.py, index_patterns.py
├── cli/          ← main.py (unified dispatcher)
├── gui/          ← app.py (with matplotlib SpectrumViewer)
├── export/       ← (placeholder)
├── phase1/       ← (placeholder)
└── phase2/       ← (placeholder)
```

---

## Quick Start (Post-Consolidation)

```bash
# Install
pip install -e .

# Run CLI
ttp --help
ttp devices
ttp record --seconds 2.5 --out ./out

# Quality-gated measurement (blocks on FAIL)
ttp measure --out ./out

# Run GUI
ttp gui
# or
python -m tap_tone_pi.cli.main gui

# Run tests
python -m pytest
```

---

## Verification Checklist (Raspberry Pi Deployments)

Run these after install to confirm working setup:

```bash
# 1. Device detection
ttp devices
# ✓ Should show at least one input device with "*" marker

# 2. Device persistence
ttp setup
# ✓ Stores device by name (survives index changes on reboot)

# 3. Basic capture with QC evidence
ttp record --seconds 2.5 --out ./out --label test
# ✓ Creates capture directory with:
#   - audio.wav
#   - analysis.json
#   - quality_check.json

# 4. Pack export (if Phase 2 session exists)
ttp export-pack --session runs_phase2/session_0001 --out pack.zip --validate --strict
# ✓ Creates validated viewer pack ZIP
```

---

## Next Steps

**v2.0.0 is consolidation + baseline.** UX/governance work continues:

| Phase | Status | Description |
|-------|--------|-------------|
| Quality gate evidence | ✅ Done | `quality_check.json` everywhere |
| Operator loop | ✅ Done | PASS/WARN/FAIL with retry/override |
| Workflow tests | ✅ Done | 40 tests for attempt + operator loop |
| UI polish | 🔜 Next | Meters, setup wizard, session browser |
| Pack diff tooling | 🔜 Next | Before/after comparison |

---

## Key Files Created in tap_tone_pi/

```
tap_tone_pi/
├── __init__.py
├── bending/
│   ├── __init__.py
│   ├── merge_and_moe.py
│   └── plot_f_vs_d.py
├── capture/
│   ├── __init__.py
│   ├── dial_indicator_serial.py
│   ├── loadcell_serial.py
│   └── simulators.py
├── chladni/
│   ├── __init__.py
│   ├── index_patterns.py
│   └── peaks_from_wav.py
├── cli/
│   ├── __init__.py
│   └── main.py          ← NEW in Phase 4
├── core/
│   ├── __init__.py
│   ├── analysis.py
│   ├── config.py
│   └── dsp.py
├── export/
│   └── __init__.py
├── gui/
│   ├── __init__.py
│   └── app.py           ← NEW in Phase 4 (binding bug fixed)
├── io/
│   ├── __init__.py
│   ├── manifest.py
│   └── wav.py
├── phase1/
│   └── __init__.py
└── phase2/
    └── __init__.py
```
