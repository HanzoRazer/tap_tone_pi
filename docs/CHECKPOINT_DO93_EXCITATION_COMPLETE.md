# Checkpoint: DO-93 Excitation Infrastructure Complete

**Date:** 2026-06-21
**Version:** 2.3.0-alpha.7
**Commits:** 67186a8 → 9f6b63b (9 commits)

## Summary

The Measurement Legitimacy Stack is complete through DO-93. The excitation
provenance infrastructure is now first-class, with all excitation types
(tone, stepped, sweep) producing traceable provenance records.

## Completed Dev Orders

| Order | Title | Commits | Tests |
|-------|-------|---------|-------|
| DO-89A | Experiment Design Contract | 67186a8 | 37 |
| DO-89B | Process Variance Evidence | d3ba74e | 35 |
| DO-89C | Covariate-Aware Cohort Regression | 3fe9c71 | 31 |
| DO-89D | Cohort Execution Plan Export | 2fe261d | 33 |
| DO-90 | Controlled Excitation Contracts | 43f7ebd | 36 |
| DO-91 | Excitation Provenance + TF Workflow | 55f4ed7 | 28 |
| DO-92 | A0 Main Body Air Resonance Workflow | e487d2a | 38 |
| DO-93 | Stepped & Sweep Excitation Records | 9f6b63b | 25 |

**Total new tests:** 263

## Architecture State

### Experiment Infrastructure
```
ExperimentDesignV1
    ↓
VarianceDecompositionV1 (σ²_measurement vs σ²_build)
    ↓
CohortRegressionEvidenceV1
    ↓
CohortExecutionPlanV1
```

### Excitation Provenance
```
ExcitationContractV1
    ├── KnownToneRecordV1      (emit_tone)
    ├── SteppedExcitationRecordV1  (emit_stepped)
    └── SweepExcitationRecordV1    (emit_sweep)
         ↓
ExcitationMeasurementLinkV1
         ↓
ExcitationResponsePairV1
         ↓
TransferFunctionResultV1
```

### First Applied Workflow
```
MainBodyAirResonanceWorkflowV1 (DO-92)
    → A0PeakCandidateV1
    → A0MeasurementEvidenceV1
    → A0MeasurementRecordV1
```

## Test Suite Status

```
3041 passed, 52 skipped, 1 xfailed, 5 warnings
2 failed (stale fixture data — pre-existing, not a regression)
```

The 2 failures are real-session validation tests with January 2026 data
that predates current schema requirements (missing `bending` field).
Not a code regression.

## Governance Guards

- All new files have `# INSTRUMENT CLASS: MEASUREMENT` header
- Advisory-free semantics verified in all serialization tests
- No logic creep: all contracts are provenance/evidence, not recommendations

## Known Issues

1. **Stale real-session fixtures:** `out/viewer_packs/session_2026010*` need
   re-export to match current schema
2. **__init__.py version drift:** Now synced to 2.3.0-alpha.7

## Next Steps

### Recommended: DO-94 Modal Participation Mapping

**Important caveat:** Microphone grid maps radiated pressure, not plate velocity.
Contract should be named appropriately:

```
PressureResponseMapV1  (not ModeShapeV1)
```

The map shows where radiated pressure is strongest at each frequency, which
correlates with but is not identical to the plate's velocity distribution.

### Scope for DO-94

- `PressureResponseMapV1` — grid of pressure amplitude at each frequency
- `GridPointResponseV1` — single point's frequency response
- `MapComputationEvidenceV1` — provenance for map computation
- Integration with ExcitationResponsePairV1
- Viewer-pack export support
- Advisory-free semantics (no "best position" recommendations)

## Files Changed in This Stack

### New Packages
- `tap_tone_pi/experiment/` (DO-89A/B/C/D)
- `tap_tone_pi/excitation/` (DO-90/91/93)
- `tap_tone_pi/a0/` (DO-92)

### New Contracts
- `tap_tone_pi/transfer_function/result_contract.py` (DO-91)

### Updated
- `tap_tone_pi/transfer_function/__init__.py`
- `tap_tone_pi/cli/main.py` (emit-tone command)

### Tests
- `tests/test_experiment_design.py`
- `tests/test_process_variance.py`
- `tests/test_cohort_regression.py`
- `tests/test_execution_plan.py`
- `tests/test_excitation.py`
- `tests/test_excitation_provenance.py`
- `tests/test_a0_workflow.py`
- `tests/test_stepped_sweep.py`

---

*Checkpoint verified: 2026-06-21*
