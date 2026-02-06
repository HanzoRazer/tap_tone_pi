# Tap Tone Pi — Consolidation Progress Bookmark

**Last Updated:** 2026-02-05  
**Session:** Phase 4 in progress

---

## Completed Phases

### ✅ Phase 0: Critical Fixes (commit `3626ec9`)
- [x] Bug 2 fixed: WAV argument transposition in `tap_tone/storage.py:57`
- [x] Regression test added: `tests/test_storage_wav_roundtrip.py`
- [x] Version bumped to 2.0.0 in `pyproject.toml`
- [x] CHANGELOG updated with v2.0.0 section
- [x] Schema location documented: `contracts/schemas/` is canonical
- [x] `out/` directory removed from git tracking (64 files)
- [x] `ttp` CLI alias added to entry points

### ✅ Phase 1: Test Baseline (commit `481b500`)
- [x] 13 Phase 1 pipeline integration tests: `tests/test_phase1_pipeline_integration.py`
- [x] 8 Chladni pipeline integration tests: `tests/test_chladni_pipeline_integration.py`
- [x] Test baseline established: 168 collected, 148 passed initially

### ✅ Phase 2: Package Skeleton (commit `5aa1b84`)
- [x] Created `tap_tone_pi/` package with 10 subpackages
- [x] Copied canonical WAV I/O: `tap_tone_pi/io/wav.py`
- [x] Copied manifest generation: `tap_tone_pi/io/manifest.py`

### ✅ Phase 3: Core + Capture Migration (commit `9fb553d`)
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

---

## 🔄 Phase 4: CLI + GUI Rewrite (COMPLETE)

### Completed
- [x] Unified CLI dispatcher created: `tap_tone_pi/cli/main.py`
- [x] GUI copied with binding bug fix: `tap_tone_pi/gui/app.py`
- [x] Updated `__init__.py` for cli and gui subpackages
- [x] Entry points updated in `pyproject.toml` (ttp primary)
- [x] Explicit package discovery added to pyproject.toml
- [x] Test baseline verified: 190 passed (up from 170!)
- [x] Committed: `f479e53`

---

## Pending Phases

### Phase 5: Cleanup
- [ ] Add deprecation stubs to old locations
- [ ] Update imports in remaining scripts
- [ ] Consider removing old directories (tap-tone-lab, modes, scripts)

### Phase 6: Schema Compliance (Separate PR)
- [ ] Validate all outputs against `contracts/schemas/*.schema.json`
- [ ] Add schema validation to CI

---

## Test Baseline

| Metric | Count |
|--------|-------|
| Collected | 170+ |
| Passed | 170 |
| Failed | 13 (env-dependent: ingest/toolbox) |
| Errors | 7 (viewer pack import paths) |

---

## Git Commits

| Phase | Commit | Description |
|-------|--------|-------------|
| 0 | `3626ec9` | Critical fixes, version bump |
| 1 | `481b500` | Integration tests |
| 2 | `5aa1b84` | Package skeleton + I/O |
| 3 | `9fb553d` | Core + Capture migration |
| 4 | pending | CLI + GUI rewrite |

---

## Resume Instructions

1. Open workspace: `C:\Users\thepr\Downloads\tap_tone_pi`
2. Activate venv: `.venv\Scripts\Activate.ps1`
3. Reinstall package: `pip install -e .`
4. Verify CLI: `ttp-unified --help`
5. Commit Phase 4 and proceed to Phase 5

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
