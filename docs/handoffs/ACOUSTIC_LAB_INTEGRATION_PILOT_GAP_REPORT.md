# Acoustic Lab Integration Pilot — Gap Report

**INSTRUMENT CLASS: MEASUREMENT**

Phase 1 analysis. This report documents what the existing TTP experiment
machinery produces for a realistic acoustic campaign and what is missing before
any adapter/code integration. It introduces no advisory logic and prescribes no
builds. It describes gaps in *tooling*, never quality of any specimen.

- **Pilot fixture:** [`examples/acoustic_lab/flat_plate_resonance_pilot_v1.py`](../../examples/acoustic_lab/flat_plate_resonance_pilot_v1.py)
- **Baseline render:** [`docs/handoffs/FLAT_PLATE_RESONANCE_PILOT_EXECUTION_PLAN.md`](./FLAT_PLATE_RESONANCE_PILOT_EXECUTION_PLAN.md)
- **Renderer under test:** `tap_tone_pi/experiment/execution_plan.py`
  (`create_cohort_execution_plan` L375, `render_cohort_execution_plan_markdown` L484) — **unchanged**.

---

## Executive Summary

The existing renderer runs end to end on a realistic acoustic campaign and emits
a clean, traceable, 9-section plan **without modification**. The machinery is
real and reusable — the audit's core thesis holds: TTP is closer to the acoustic
lab than "invent it from scratch" would suggest.

However, the rendered plan is **not yet an operator-usable bench protocol**. Its
vocabulary is cohort-**build** oriented (Sections 4–6: "Cohort Build Plan,"
"Baseline Rebuild Schedule," "Reference Body"), and its measurement instructions
collapse the entire physical procedure into a single opaque workflow id. A
technician handed this plan could not, from it alone, set up the bench, place the
microphone, support/excite the plate, calibrate, decide how many repeats to take,
reject noisy captures, or name the output files.

Separately, the **evidence data chain is not wired**: there is no code path from a
measured `PlateMeasurement` to the regression fitter, and `RegressionInputV1` is
orphaned metadata the fitter never consumes.

**Conclusion:** the next integration patch is small and well-scoped — add
acoustic-bench protocol fields/sections to the plan, and add a
`PlateMeasurement → regression-sequence` adapter. No new architecture is needed.

---

## What the Renderer Already Provides

Verified from the baseline render and `execution_plan.py`:

1. **Plan identity & traceability** (Section 1) — plan id, experiment design id,
   version, created-UTC, cohort size. Good provenance spine.
2. **Declared response variables with units, workflow linkage, and MIE**
   (Section 2) — `T1 frequency / Hz`, `Q / ratio`, `decay time / s`, each with a
   minimum-interesting-effect. This is genuinely useful and lab-relevant.
3. **Covariate registry** (Section 3) — including `support method`, `humidity`,
   `temperature` with declared sources. The *data model* for environment/support
   capture exists.
4. **Cohort sizing + randomization** (Section 4) — size 12, `blocked`.
5. **Reference-body / repeatability hook** (Section 6) — a kept specimen for
   σ_measurement isolation. The *concept* an acoustic lab needs (repeatability
   standard) is already present.
6. **Auto-derived measurement-workflow rollup** (Section 7) — groups response
   variables by workflow id.
7. **Auto-derived execution checklist** (Section 8) — ordered steps:
   record covariates → measure each response → reference-body repeatability →
   export provenance.
8. **Per-artifact provenance requirements** (Section 9) — `measurement_session`
   already mandates `environment_temp_c` and `environment_rh_pct`; each response
   and covariate gets a required-field contract.

In short: identity, variables, covariates, repeatability, provenance, and
checklist scaffolding are **already there**.

---

## Operator Gaps

Each item below was checked against the baseline render. "Present" means a
technician could execute it from the plan alone; "Missing" / "Implicit" means not.

| Operator need | Status in baseline plan | Evidence |
|---------------|-------------------------|----------|
| **Mic placement** | **Missing** | No field anywhere. Excitation/sensing geometry is not modeled. |
| **Sensor placement** (accel/laser) | **Missing** | Same — only a `measurement_workflow_id` string. |
| **Support method** | **Implicit only** | Declared as a *covariate to record* (Section 3) and listed in checklist Step 1 "Record covariates…", but there is no setup instruction describing *how* to support free-free (foam/elastic suspension/nodal). It is data-to-log, not a procedure. |
| **Fixture description** | **Missing** | No fixture/jig section. `support method` is a category value, not a described rig. |
| **Tap / sweep protocol** | **Missing** | Checklist Step 2–4 read "Measure {var} using tap_modal_capture_v1." Tap vs. swept-sine, hammer/impactor, strike location, windowing, FFT settings — none expressed. |
| **Calibration steps** | **Missing** | No calibration step in the checklist; no calibration artifact in provenance. (Cross-ref Hardware Status below.) |
| **Repeat count** | **Missing** | Each measure step is a single line with no N. No averaging / take-best / discard rule. |
| **Accept/reject criteria for noisy data** | **Missing** | No coherence/SNR threshold, no re-test trigger. (Note: an `accept/re-test` doctrine already exists in prose in `docs/handoffs/no_soundhole_lab_protocol.md` §17 — it is simply not rendered into plans.) |
| **Environmental controls** | **Partial** | Captured as covariates + required provenance fields (`environment_temp_c`, `environment_rh_pct`), but there is no *control/stabilization instruction* (e.g., acclimation time, RH window to hold). |
| **Output artifact filenames** | **Missing** | Section 9 specifies artifact *types*, *formats*, and *required fields*, but no file-naming/path convention an operator would write to disk. |

**Root cause:** response-variable measurement is represented only by an opaque
`measurement_workflow_id` (`tap_modal_capture_v1`). The renderer dereferences
nothing about that workflow — see `_derive_execution_checklist`
(`execution_plan.py` L287–296), which emits `f"Measure {rv.name} using {workflow}"`
and nothing more. There is no `MeasurementWorkflowV1` contract describing the
bench procedure behind that id.

---

## Missing First-Class Lab Sections

The 9 sections are build/cohort-shaped. For an acoustic bench the plan lacks
dedicated sections for:

1. **Instrumentation / Equipment Setup** — mic(s), preamp, interface, impactor,
   DAQ, sample rate, channel map.
2. **Specimen Mounting / Support & Fixturing** — free-free realization, support
   points relative to nodal lines, coupling avoidance.
3. **Excitation & Capture Protocol** — tap vs. sweep, strike map, window, FFT
   resolution, averaging count, settling time.
4. **Calibration Procedure** — reference-level/known-source calibration, what
   `session_calibration.json` must contain, when to re-calibrate.
5. **Repeated-Measurement Rule** — N per specimen, intra-specimen variance
   handling, reference-body cadence in *measurement* terms (not build numbers).
6. **Data Quality Gate** — coherence/SNR acceptance, re-test triggers, exclusion
   logging.
7. **Output / Artifact Naming** — deterministic filenames and directory layout
   for session, per-response, per-covariate artifacts.

**Vocabulary mismatches observed in the render** (build → bench):
- Section 4 "Cohort **Build** Plan" — plates are *prepared/measured*, not built.
- Section 5 "Baseline **Rebuild** Schedule" rendered "No baseline rebuild schedule
  defined" because `BaselineRebuildPlanV1` is keyed on `rebuild_at_build_numbers`
  / `baseline_recipe_id` (`baseline_plan.py` L23–34) — instrument-build concepts
  with no flat-plate analog.
- Section 6 "Reference **Body**" forced `body_style="flat_plate_reference"` and
  `state="free_free_unclamped"` into a contract designed for assembled instrument
  bodies (`reference_body.py` L40–51). It works mechanically but is semantically
  off.

---

## Data Chain Gaps

Target chain: `FlitchRecord → PlateMeasurement → RegressionInputV1 → fit_linear_cohort_regression(...)`.

| Hop | Status | Evidence |
|-----|--------|----------|
| `FlitchRecord → PlateMeasurement` | **Connected** | `FlitchRecord.measurements: list[PlateMeasurement]` (`materials/wood_db.py` L162–192); `WoodDatabase.add_measurement()` L~391. |
| `PlateMeasurement → RegressionInputV1` | **No adapter** | No function converts measurements into regression inputs. Searched: no `*_to_regression_input` / `measurements_to_*`. |
| `RegressionInputV1 → fit_linear_cohort_regression()` | **Orphaned metadata** | `fit_linear_cohort_regression(...)` (`experiment/cohort_regression.py` L209) consumes raw `response_values: Sequence[float]`, `primary_variable_values: Sequence[float]`, `covariates: Mapping[str, Sequence[float]]` — it **never takes `RegressionInputV1`** (L26). The input contract documents intent but is not wired into the fitter. |
| `WoodDatabase → experiment` pathway | **Unclear / absent** | Covariates declare `source="wood_database"` (data model intent), but there is no code that reads `WoodDatabase` and emits the sequences the fitter needs, nor that joins measurements to an `experiment_design_id` / `campaign_id`. |

**Net:** two real breaks — (a) no `PlateMeasurement → sequences` converter, and
(b) `RegressionInputV1` is not consumed by the fitter. Both must be addressed for
end-to-end evidence flow. **Not implemented in this phase (by design).**

---

## Hardware Status

- **`session_calibration.json` files found?** Yes — 6 on disk under `out/`
  (e.g. `out/bend_20251229T042148Z/calibration/session_calibration.json`,
  `out/session_S_20251229_A/session_calibration.json`).
- **Tracked or local?** **Local only.** `out/` is gitignored (`.gitignore:38`),
  and `git ls-files` returns **zero** tracked `session_calibration` paths.
- **Committed calibration records?** **None.** No calibration data is under
  version control.
- **Physical rig confirmed built & calibrated?** **Unknown.** Not determinable
  from the repo; requires operator confirmation. Local calibration output proves
  the calibration *code path has been exercised at least once*, not that a
  current, calibrated physical rig exists.
- **Conclusion:** **Do not claim calibrated hardware readiness.** Treat hardware
  as `UNKNOWN` until the operator confirms a physically built+calibrated rig and
  calibration records are committed (or referenced from a tracked manifest).

---

## Recommended Next Patch

Scoped, measurement-only, no advisory logic. Suggested order:

1. **`MeasurementWorkflowV1` contract** — describe the bench procedure behind a
   `measurement_workflow_id`: instrumentation, support/fixture, excitation
   (tap/sweep) protocol, calibration step, repeat count, data-quality gate,
   artifact naming. Render it into the plan (new Sections or enriched Section 7/8).
   This closes the bulk of the Operator Gaps without touching analysis.
2. **Mine `no_soundhole_lab_protocol.md`** (812 lines, 20 sections incl.
   instrumentation §4, measurement sequence §7, accept/re-test §17) into the new
   workflow contract fields — normalize existing prose into structured, rendered
   sections rather than re-authoring.
3. **`PlateMeasurement → regression sequences` adapter** — a pure function
   extracting `response_values`, `primary_variable_values`, and `covariates`
   (Mapping) from a cohort of `FlitchRecord`/`PlateMeasurement`, plus deciding
   whether `RegressionInputV1` should be *consumed by* (not just describe) the
   fitter. Closes the data-chain breaks.
4. **Acoustic-bench vocabulary** — either generalize Sections 4–6 labels or add
   a plate/bench plan variant so "build/rebuild/body" wording stops misfitting
   plate cohorts.

Each is independently shippable and testable; none requires a new architecture,
formula engine, or advisory system.

---

## Non-Goals (held this phase)

- No `PlateMeasurement → regression` adapter implemented (documented only).
- No new advisory or scoring system.
- No build prescriptions or quality claims.
- No new formula engine.
- No renderer behavior changes (baseline render is the unmodified output).
- No separate acoustic-lab repo.

---

*Phase 1 analysis only. Acceptance: one realistic plan rendered, operator gaps
listed, data-chain gaps identified, hardware classified honestly, next patch
defined.*
