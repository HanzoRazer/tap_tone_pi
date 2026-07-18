# Session Handoff — 2026-05-22

> **Session scope:** Governance audit + MOE calculation path consolidation
> **Status:** Implementation complete, pending team review
> **Artifacts:** 2 new docs, 1 new test file, 3 modified files

---

## Executive Summary

This session performed two related tasks:

1. **Governance Audit** — A four-axis interrogation of the repository to map authority, provenance, execution, and boundary systems
2. **MOE Path Consolidation** — Tightened governance around the `merge_and_moe.py` duplicate that the audit flagged

The audit finding turned out to be **stale** — the consolidation was already done (shim exists). The work completed here adds governance tightening: instrument class headers, expanded re-exports, documentation updates, and canonicality guard tests.

---

## Part 1: Governance Audit

### What Was Done

Performed a comprehensive audit using four interrogation lenses:

| Axis | Question | Key Findings |
|------|----------|--------------|
| **Ownership** | What claims authority over truth/validity? | 15 schemas in `contracts/`, quality policy engine (Q001-Q013), calibration gate, species normalization |
| **Provenance** | How is observation vs interpretation distinguished? | `measurement_only: true` flag, kind-based file classification, SHA-256 chains, forbidden interpretive language |
| **Execution** | What can mutate state automatically? | CLI commands, session ledgers, Phase 2 state, UWSM, CI/CD pipelines |
| **Boundaries** | What experimental outputs could be mistaken for legitimacy? | WolfAdvisor recommendations, guidance panel, agentic events (all gated) |

### Artifact Created

**File:** [`docs/GOVERNANCE_AUDIT_HANDOFF.md`](GOVERNANCE_AUDIT_HANDOFF.md)

A 400+ line annotated developer guide covering:
- Schema authority and team ownership mapping
- Quality policy rules (HARD vs SOFT) with justifications
- Provenance chain documentation
- Execution mutation vectors
- Two-class instrument system (MEASUREMENT vs DECISION SUPPORT)
- CI guardrails and what they block
- Schema reference matrix
- Validation checklist for new code

**Intended use:** Onboarding reference for developers who need to understand what systems claim truth and where boundaries exist.

---

## Part 2: MOE Calculation Path Consolidation

### Background

The audit flagged `merge_and_moe.py` as existing in two locations:
- `tap_tone_pi/bending/merge_and_moe.py` (canonical)
- `modes/bending_rig/merge_and_moe.py` (legacy)

**Finding:** The consolidation was **already complete**. The legacy file is already a shim that re-exports from the canonical location and emits a `DeprecationWarning`. The audit finding was stale.

### What Was Done

Governance tightening to complete the consolidation:

#### 1. Added Instrument Class Headers

Both files now declare their instrument class per ADR-0009:

```python
#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
```

**Files modified:**
- `tap_tone_pi/bending/merge_and_moe.py` (line 2)
- `modes/bending_rig/merge_and_moe.py` (line 2)

**Justification:** Even shims participate in the measurement import surface. Explicit classification enables CI guardrails.

#### 2. Expanded Shim Re-exports

The legacy shim now re-exports all public symbols, not just a subset:

```python
from tap_tone_pi.bending.merge_and_moe import (
    main,
    _sha256,
    _load_series,
    _lin_interp,
    _resample,
    _linear_fit,
    _calculate_moe,
    _timoshenko_correction_factor,  # NEW
    LinearFitResult,                 # NEW
)
```

**Justification:** The shim already re-exported private helpers (`_sha256`, `_calculate_moe`), so it's compatibility-oriented. Keeping `_timoshenko_correction_factor` out would be inconsistent and could break downstream code that imports it from the legacy path.

#### 3. Updated Documentation

Changed the import example in [`docs/ENGINEER_HANDOFF.md`](ENGINEER_HANDOFF.md) from:

```python
# OLD (legacy path)
from modes.bending_rig import merge_and_moe, plot_f_vs_d
```

to:

```python
# NEW (canonical paths)
from tap_tone_pi.bending import merge_and_moe, plot_f_vs_d
```

**Justification:** Onboarding docs should not teach legacy imports.

#### 4. Created Canonicality Guard Tests

**File:** [`tests/test_merge_and_moe_canonical.py`](../tests/test_merge_and_moe_canonical.py)

9 tests across 3 test classes:

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestMergeAndMoeCanonical` | 5 | Verify legacy symbols are identity-equal to canonical |
| `TestCanonicalImplementationFeatures` | 3 | Verify canonical has Timoshenko correction, LinearFitResult |
| `TestLegacyEmitsDeprecationWarning` | 1 | Verify deprecation warning is emitted |

**Key assertions:**
```python
assert legacy.main is canonical.main
assert legacy._calculate_moe is canonical._calculate_moe
assert legacy._timoshenko_correction_factor is canonical._timoshenko_correction_factor
assert legacy.LinearFitResult is canonical.LinearFitResult
```

**Justification:** Prevents accidental divergence where patches are applied to one location but not the other. If someone accidentally converts the shim back to a full implementation, these tests will fail.

---

## Test Results

| Suite | Result |
|-------|--------|
| `tests/test_merge_and_moe_canonical.py` | **9/9 pass** |
| `tests/test_*moe*.py tests/test_*bending*.py` | **87/87 pass** |
| `ci/check_boundary_imports.py --preset analyzer` | **Pass** (no output) |
| `ci/check_advisory_boundary.py` | **Warnings only** (pre-existing, unrelated to this work) |

---

## Files Changed

### Modified (3 files)

| File | Change |
|------|--------|
| `tap_tone_pi/bending/merge_and_moe.py` | Added `# INSTRUMENT CLASS: MEASUREMENT` header |
| `modes/bending_rig/merge_and_moe.py` | Added header + expanded re-exports |
| `docs/ENGINEER_HANDOFF.md` | Updated import example to canonical path |

### Created (2 files)

| File | Purpose |
|------|---------|
| `docs/GOVERNANCE_AUDIT_HANDOFF.md` | Annotated developer guide from governance audit |
| `tests/test_merge_and_moe_canonical.py` | Canonicality guard tests |

---

## What Was NOT Done

1. **CI guard script** (`ci/check_duplicate_measurement_paths.py`) — Skipped per instructions. The canonicality test is sufficient for now.

2. **`plot_f_vs_d.py` consolidation** — Discovered that `modes/bending_rig/plot_f_vs_d.py` is a **full duplicate** (not shimmed) of `tap_tone_pi/bending/plot_f_vs_d.py`. The canonical version has an M2 fix in `percentile_bounds()` that the legacy version lacks. This is a **separate consolidation task** not addressed in this session.

3. **Instrument class headers for other files** — The advisory boundary check shows many files missing instrument class declarations. This is pre-existing technical debt, not in scope for this session.

---

## Recommended Follow-ups

### Priority 1: Commit This Work

The changes are tested and ready. Suggested commit message:

```
governance: unify canonical MoE calculation path

- Add INSTRUMENT CLASS: MEASUREMENT headers to both files
- Expand shim re-exports (LinearFitResult, _timoshenko_correction_factor)
- Update ENGINEER_HANDOFF.md to use canonical import path
- Add canonicality guard tests (9 tests)

The core consolidation was already done (shim existed). This PR adds
governance tightening per ADR-0009 and test coverage to prevent drift.
```

### Priority 2: Consolidate `plot_f_vs_d.py`

Same pattern as `merge_and_moe.py`:
1. `tap_tone_pi/bending/plot_f_vs_d.py` is canonical (has M2 fix)
2. `modes/bending_rig/plot_f_vs_d.py` is a full duplicate (missing M2 fix)
3. Convert legacy to shim, add canonicality tests

### Priority 3: Instrument Class Audit

Many files in `tap_tone_pi/agent/` and `tap_tone_pi/agentic/` lack instrument class declarations. Consider a sweep to add headers, or update `ci/check_advisory_boundary.py` to enforce only on specific directories.

---

## Questions for Team Review

1. **Commit scope:** Should the governance audit document (`GOVERNANCE_AUDIT_HANDOFF.md`) be in a separate commit from the MOE consolidation work?

2. **Shim retention:** The legacy shim emits `DeprecationWarning`. Is there a timeline for removing it entirely, or should it remain indefinitely for backward compatibility?

3. **`plot_f_vs_d.py` priority:** Should consolidation of this duplicate be scheduled, or is it low priority?

---

*Session completed: 2026-05-22*
*Ready for team review and commit*
