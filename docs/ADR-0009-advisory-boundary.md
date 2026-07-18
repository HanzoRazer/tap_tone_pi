# ADR-0009: Advisory Boundary — Measurement vs Decision Support Instrument Classes

**Status:** Accepted
**Date:** 2026-03-30
**Sprint:** QW (Quick Wins), v2.3.0-alpha.4
**Enforced by:** `ci/check_advisory_boundary.py`, `.github/workflows/advisory_boundary_guard.yml`

---

## Context

`tap_tone_pi` is a measurement instrument. Its outputs are calibrated numerical
results — frequencies, coherence values, transfer functions — that carry
provenance metadata and SHA256 integrity hashes. These outputs flow into
`viewer_pack_v1` bundles and ultimately into downstream advisory systems
(the Production Shop inverse brace engine, RMOS).

A second class of output exists within the codebase: **recommendations**,
**grades**, **directives**, and **mitigations** produced by advisory modules
such as `WolfAdvisor`, `wood_properties.py`, and `AnalyzerGuidanceEngine`.
These are interpretations, not measurements. They must never appear in
`viewer_pack_v1` because mixing them with calibrated data would corrupt the
provenance chain and misrepresent the instrument's output class.

Prior to this ADR, the boundary was implicit and unenforced. Several modules
had begun leaking advisory fields (e.g. `mitigation_type`, `wolf_directive`,
`quality_grade`) into export paths.

---

## Decision

All Python modules in `tap_tone_pi/` and `analyzer/analysis/` must declare
their instrument class at the top of the file:

```python
# INSTRUMENT CLASS: MEASUREMENT
```
or
```python
# INSTRUMENT CLASS: DECISION SUPPORT
```

**MEASUREMENT modules:**
- May appear in `viewer_pack_v1` exports
- Subject to provenance tracking and SHA256 integrity
- May be compared across sessions
- Examples: `tap_tone_pi/wolf/wolf_beat.py`, `tap_tone_pi/transfer_function/estimators.py`

**DECISION SUPPORT modules:**
- Must NOT appear in `viewer_pack_v1` exports
- Output flows to the agentic spine (`AttentionDirectiveV1`) or operator display only
- Examples: `tap_tone_pi/wolf/wolf_advisor.py`, `analyzer/analysis/wood_properties.py`,
  `analyzer/guidance/engine.py`

---

## Enforcement

`ci/check_advisory_boundary.py` runs three checks:

1. **Declaration coverage** — every `.py` in scope must carry one of the two banners
2. **Export isolation** — no export pipeline module (`export_viewer_pack_v1.py`) may
   import a DECISION SUPPORT module
3. **Viewer pack isolation** — `viewer_pack_v1` schema origin must be MEASUREMENT only

The wolf purity gate in `scripts/phase2/export_viewer_pack_v1.py` additionally
blocks export if `wolf_candidates.json` contains any of these prohibited fields:
`mitigation_type`, `recommendations`, `wolf_directive`, `severity_label`,
`action_required`, `operator_guidance`, `confidence_label`, `urgency`, `next_steps`.

---

## Consequences

- Modules that produce recommendations are clearly labelled and cannot accidentally
  enter the measurement data path
- `quality_grade` was renamed to `coherence_band` in `estimators.py` to remove
  advisory language from a MEASUREMENT module
- `AnalyzerGuidanceEngine` (Sprint AGE) is explicitly DECISION SUPPORT and emits
  only to `GuidancePanelWidget`, never to `viewer_pack_v1`
- CI fails on any import that violates the boundary

---

## References

- `ci/check_advisory_boundary.py`
- `.github/workflows/advisory_boundary_guard.yml`
- `scripts/phase2/export_viewer_pack_v1.py` — wolf purity gate
- `tap_tone_pi/agent/wolf_guidance.py`
- `analyzer/guidance/engine.py`
