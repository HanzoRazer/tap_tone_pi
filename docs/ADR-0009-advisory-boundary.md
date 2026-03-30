# ADR-0009: Advisory Boundary — Measurement vs. Decision Support

## Status
Accepted

## Date
2026-03-30

## Context

tap_tone_pi's instrument scope (INSTRUMENT_SCOPE.md) states:

> "tap-tone-pi is a measurement instrument. It captures evidence, not conclusions."

Since that document was written, three modules have been added that produce
outputs that are interpretive rather than purely measured:

1. `tap_tone_pi/wolf/wolf_advisor.py` — emits ranked `MitigationType`
   recommendations (`ADD_MASS`, `INCREASE_DAMPING`, `SHIFT_BODY_MODE`) with
   confidence levels, based on an avoided-crossing physics model applied to
   measured peak pairs.

2. `analyzer/analysis/wood_properties.py` — computes `quality_grade: str`
   (A/B/C/D) from estimated Young's modulus and radiation coefficient derived
   from tap tone measurements.

3. `tap_tone_pi/transfer_function/estimators.py` — `CoherenceAnalysis` dataclass
   contains `quality_grade: str` ("excellent", "good", "acceptable", "poor")
   derived from mean coherence statistics.

The `ci/no_logic_creep.yml` guard only checks `modes/` for advisory language.
It does not cover `tap_tone_pi/wolf/`, `tap_tone_pi/transfer_function/`, or
`analyzer/analysis/`. This means advisory content can accumulate inside the
instrument boundary without any CI gate.

## Decision

### 1. Define two instrument classes — permanently

| Class | Definition | Examples |
|---|---|---|
| **MEASUREMENT** | Produces calibrated, provenance-tracked, reproducible numeric facts. No ranking, grading, or recommendations. | `analyze_tap()`, `compute_transfer_and_coherence()`, bending MOE, coherence γ²(f) |
| **DECISION SUPPORT** | Applies physics models or domain heuristics to measurements to produce ranked recommendations or grades. Requires operator expertise to interpret. Never appears in `viewer_pack_v1`. | `WolfAdvisor`, `quality_grade` in `wood_properties.py`, `CoherenceAnalysis.quality_grade` |

These two classes must never be mixed in the same module. A module is either
a measurement module or a decision support module. It cannot be both.

### 2. Module-level instrument class declaration (required for all modules)

Every module in `tap_tone_pi/` and `analyzer/` must declare its class in its
module docstring as the **first line after the summary**, using this exact
format:

```python
# INSTRUMENT CLASS: MEASUREMENT
```
or
```python
# INSTRUMENT CLASS: DECISION SUPPORT
# Outputs from this module do not appear in viewer_pack_v1.
# Operator expertise required to interpret recommendations.
```

### 3. viewer_pack_v1 is MEASUREMENT-only

No field derived from a DECISION SUPPORT module may appear in a
`viewer_pack_v1` export bundle. The export pipeline (`tap_tone_pi/export/`,
`scripts/phase2/export_viewer_pack_v1.py`) must not import from:

- `tap_tone_pi/wolf/wolf_advisor.py`
- `analyzer/analysis/wood_properties.py` (quality_grade field)
- Any module carrying the `INSTRUMENT CLASS: DECISION SUPPORT` declaration

### 4. Specific module remediation

| Module | Current State | Required Change |
|---|---|---|
| `tap_tone_pi/wolf/wolf_advisor.py` | No class declaration | Add `# INSTRUMENT CLASS: DECISION SUPPORT` banner |
| `tap_tone_pi/wolf/wolf_beat.py` | No class declaration | Add `# INSTRUMENT CLASS: MEASUREMENT` banner (beat analysis is measurement) |
| `analyzer/analysis/wood_properties.py` | Contains `quality_grade: str` A/B/C/D | Add `# INSTRUMENT CLASS: DECISION SUPPORT` banner; add docstring note that quality_grade is a heuristic, not a calibrated measurement |
| `tap_tone_pi/transfer_function/estimators.py` | `CoherenceAnalysis.quality_grade` | **Rename to `coherence_band: str`** to use objective language ("high", "medium", "low" replacing "excellent", "poor"); add `# INSTRUMENT CLASS: MEASUREMENT` banner |

### 5. CI gate extension

`ci/no_logic_creep.yml` must be extended to scan `tap_tone_pi/` (not just
`modes/`) for modules that contain both `# INSTRUMENT CLASS: MEASUREMENT` and
outputs categorized as advisory.

A new `ci/check_advisory_boundary.py` script will:
- Scan all `.py` files for the `# INSTRUMENT CLASS:` declaration
- Flag any file in `tap_tone_pi/` that lacks the declaration
- Flag any file in the export pipeline that imports a DECISION SUPPORT module
- Exit non-zero on any violation

## Rationale

The measurement boundary is not a documentation preference — it is the product's
primary credibility claim. A luthier using this instrument needs to know whether
a number they are looking at is:

(a) a calibrated measurement they can reproduce and compare, or
(b) a model-derived recommendation that requires interpretation

Mixing these two in the same output stream (e.g., a `viewer_pack_v1` that
contains both coherence γ²(f) and a `quality_grade: "good"`) destroys the
distinction and erodes trust in the provenance chain.

The `wolf_advisor.py` outputs are **valuable** and should stay in the product.
The `quality_grade` field is **useful** and should stay in the analyzer UI.
This ADR does not remove them — it demarcates them clearly so a downstream
consumer knows exactly what they are looking at.

## Consequences

**Positive:**
- Instrument scope claim becomes architecturally enforced, not just documented
- viewer_pack_v1 consumers (Production Shop) can trust they receive only
  measurements, never recommendations
- New contributors cannot accidentally add advisory content to measurement modules
  without CI failure

**Negative:**
- Requires renaming `CoherenceAnalysis.quality_grade` → `coherence_band` (breaking
  change for any consumer that keys on that field — schema bump required)
- Every module in the codebase needs a one-line banner added (411 files — but
  this can be done incrementally; gate only new/modified files initially)

## Implementation Order

1. Add banners to the four specific modules named above (1 day)
2. Rename `CoherenceAnalysis.quality_grade` → `coherence_band`, bump schema (1 day)
3. Write `ci/check_advisory_boundary.py` and add to `boundary_guard.yml` (2 days)
4. Backfill banners across all modules in `tap_tone_pi/` and `analyzer/` (1 week,
   can be done as modules are touched)

## Related ADRs

- ADR-0001: Measurement Scope (original boundary definition)
- ADR-0004: Acoustic vs. Structural Boundary
- ADR-0005: Repeatability and Confidence
