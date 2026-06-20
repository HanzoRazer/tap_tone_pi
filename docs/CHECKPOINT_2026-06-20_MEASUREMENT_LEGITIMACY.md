# Checkpoint: Measurement Legitimacy Stack

**Date:** 2026-06-20
**Version:** 2.3.0-alpha.6
**Classification:** INSTRUMENT CLASS: MEASUREMENT

---

## Summary

This checkpoint marks completion of the Measurement Legitimacy Stack (DO-89A, DO-89B, DO-89C), transitioning `tap_tone_pi` from "Measurement Infrastructure" to "Experimental Knowledge Infrastructure."

The stack enables:

```
Declare experiment → run cohort → separate σ_measurement from σ_build
→ control covariates → derive formula-candidate evidence
```

---

## Completed Dev Orders

| Dev Order | Description | Commit | Tests |
|-----------|-------------|--------|-------|
| DO-89A | Experiment design contract and cohort planning | `67186a8` | 37 |
| DO-89B | Process variance evidence and feasibility summary | `d3ba74e` | 35 |
| DO-89C | Covariate-aware cohort regression evidence | `3fe9c71` | 31 |

**Total:** 103 tests across the provenance stack.

---

## New Contracts

### DO-89A: Experiment Design

| Contract | Purpose |
|----------|---------|
| `ExperimentDesignV1` | Governing object for cohort studies |
| `DeclaredResponseVariableV1` | What outcomes are being measured |
| `MinimumInterestingEffectV1` | Effect size thresholds |
| `CovariateDefinitionV1` | Tracked variables (fixed/random) |
| `RandomizationPlanV1` | Randomization strategy |
| `BaselineRebuildPlanV1` | Baseline rebuild triggers |
| `DesignValidationEvidenceV1` | Completeness validation |

### DO-89B: Process Variance

| Contract | Purpose |
|----------|---------|
| `ReferenceBodyRecordV1` | Metrology standard for σ_measurement isolation |
| `VarianceDecompositionV1` | σ²_total = σ²_measurement + σ²_build |
| `ProcessVarianceEvidenceV1` | Variance decomposition with raw values |
| `FeasibilitySummaryV1` | Cohort-level variance with neutral bands |
| `VarianceBandThresholdsV1` | low/medium/high classification thresholds |

### DO-89C: Cohort Regression

| Contract | Purpose |
|----------|---------|
| `RegressionInputV1` | Covariate values used in regression |
| `RegressionCoefficientV1` | Coefficient with standard error |
| `CohortRegressionEvidenceV1` | OLS results: coefficients, R², residuals |
| `FormulaCandidateEvidenceV1` | Descriptive formula with auto-limitations |

---

## Key Design Decisions

1. **Frozen dataclasses** with `to_dict()` for all contracts
2. **`epistemic_status="derived"`** for all computed evidence
3. **No advisory semantics** — measurement boundary strictly enforced
4. **Neutral variance bands** — "low"/"medium"/"high", not "good"/"bad"
5. **Alphabetical covariate ordering** for reproducibility
6. **Auto-limitations** — "linear model only", "N=X samples" always present
7. **Zero variance handling** — `r_squared = None` + limitation note

---

## Schema Integration

All contracts added to `contracts/phase2_ods_snapshot.schema.json`:

- `experiment_design` (optional)
- `design_validation_evidence` (optional)
- `process_variance_evidence` (optional)
- `feasibility_summary` (optional)
- `cohort_regression_evidence` (optional)
- `formula_candidate_evidence` (optional)

---

## Export Integration

`scripts/phase2/export_viewer_pack_v1.py` updated with provenance readers:

- `_read_experiment_design_provenance()`
- `_read_process_variance_provenance()`
- `_read_cohort_regression_provenance()`

---

## Pre-existing Issues

3 baseline test failures (unrelated to this checkpoint):

- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]` — missing 'bending' key
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]` — missing 'bending' key
- `test_advisory_in_calibration_is_error` — advisory boundary test

---

## Next Steps

1. **DO-89D** — Cohort Execution Plan Export / Lab Manual Integration (if activated)
2. **DO-90→92** — Acoustic Excitation Framework (per `docs/handoffs/TTP_ACOUSTIC_EXCITATION_HANDOFF_2026-06-18.md`)

---

## Validation Commands

```bash
# Run all DO-89 tests
pytest tests/test_experiment_design.py tests/test_process_variance.py tests/test_cohort_regression.py tests/test_cohort_regression_export_anchor.py -v

# Verify schema
python -c "import json; json.load(open('contracts/phase2_ods_snapshot.schema.json'))"

# Verify exports
python -c "from tap_tone_pi.experiment import *; print('All exports available')"
```

---

*This checkpoint is documentation only. Git tag will be created after full validation and PR merge.*
