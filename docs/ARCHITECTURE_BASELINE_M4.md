# Architecture Baseline — Milestone M4

> **Milestone M4 — Scientific Measurement Foundation Complete**
>
> **Type:** Snapshot, not a roadmap. This document records the architecture
> *as it exists* at M4. It is a reference baseline, not a plan.
>
> **As of:** 2026-07-08 · `origin/main` @ `b5d30d2`
>
> **Status of the architecture:** frozen except for defects. After M4, new work
> should be triggered by (1) laboratory discoveries, (2) matured/repeatable
> measurement workflows, or (3) production requirements — not by new ideas
> alone.

`tap_tone_pi` is an **instrumentation platform for empirical luthiery
research**. It captures evidence, computes deterministic DSP summaries, and
persists governed artifacts. It does not interpret tone quality, prescribe
structural changes, optimize designs, or grade instruments. That boundary is
constitutional (see [Constitutional boundaries](#constitutional-boundaries)).

---

## 1. Subsystem diagram

```text
                         ┌─────────────────────────────┐
                         │      EXPERIMENT STACK        │  design intent
                         │  (tap_tone_pi/experiment/)   │
                         └──────────────┬──────────────┘
                                        │ governs
                         ┌──────────────▼──────────────┐
                         │      PROVENANCE STACK        │  who / when / where
                         │  (tap_tone_pi/provenance/)   │
                         └──────────────┬──────────────┘
                                        │ contextualizes
   ┌───────────────┐      ┌─────────────▼─────────────┐      ┌───────────────┐
   │  EXCITATION   │─────▶│      MEASUREMENT STACK     │◀─────│  CALIBRATION  │
   │  + TRANSFER   │ in   │  capture / phase1 / phase2 │ trust│  (loopback,   │
   │  FUNCTION     │      │  / damping / wolf / a0     │      │  compensation)│
   └───────────────┘      └─────────────┬─────────────┘      └───────────────┘
                                        │ produces evidence
                         ┌──────────────▼──────────────┐
                         │   REPEATABILITY / VARIANCE   │  σ_measurement
                         │  (core.repeatability,        │
                         │   experiment.process_variance)│
                         └──────────────┬──────────────┘
                                        │ conditions
                         ┌──────────────▼──────────────┐
                         │        REGRESSION            │  cohort OLS
                         │ (experiment.cohort_regression)│
                         └──────────────┬──────────────┘
                                        │ derives
                         ┌──────────────▼──────────────┐
                         │      FORMULA STACK           │  targets + validation
                         │   (tap_tone_pi/luthiery/)    │
                         └──────────────┬──────────────┘
                                        │ serializes
                         ┌──────────────▼──────────────┐
                         │   EXPORT → viewer_pack_v1    │  additive manifest
                         │ (scripts/phase2/export_...)  │
                         └─────────────────────────────┘
```

Every downstream block is additive over the one above it. Nothing below the
Measurement stack captures new physical evidence — it only derives, conditions,
or serializes.

---

## 2. Dependency graph (data flow)

```text
Experiment Design ──▶ Campaign ──▶ Measurement Workflow ──▶ Calibration
        │                                                        │
        └──────────────────────────┬─────────────────────────────┘
                                    ▼
                         Controlled Excitation
                                    │
                                    ▼
                          Transfer Function
                                    │
                                    ▼
                              Measurement
                                    │
                                    ▼
                             Repeatability  (σ_measurement)
                                    │
                                    ▼
                        Variance Decomposition
                                    │
                                    ▼
                               Regression
                                    │
                                    ▼
                          Formula Candidate
                                    │
                                    ▼
                          Formula Validation
```

Import direction is one-way downstream. `luthiery/` imports from `experiment/`;
`experiment/` and `provenance/` do not import from `luthiery/`. Runner code
(`scripts/`) may import package modules; package modules never import from
`scripts/`.

---

## 3. Constitutional boundaries

The measurement boundary is a hard architectural rule, documented and enforced.

**Doctrine:**

| Document | Role |
|---|---|
| `docs/MEASUREMENT_BOUNDARY.md` | Canonical boundary statement |
| `docs/AGE_CONSTITUTIONAL_CONTRACT.md` | Constitutional contract |
| `docs/BOUNDARY_RULES.md` | Import-boundary rules |
| `docs/ADR-0001-measurement-scope.md` | Original scope decision |
| `docs/ADR-0004-acoustic-vs-structural-boundary.md` | Acoustic vs structural |
| `docs/ADR-0009-advisory-boundary.md` | Advisory boundary |
| `docs/ADR-0010-guidance-authority-boundary.md` | Guidance authority |
| `docs/ADR-0011-measurement-authority.md` | Measurement authority |
| `docs/ADR-0012-epistemic-status-taxonomy.md` | `observed` vs `derived` status |

**Enforcement (CI guards, `ci/`):**

| Guard | Enforces |
|---|---|
| `check_advisory_boundary.py` | No advisory/decision-support leakage into measurement artifacts |
| `check_guidance_language.py` | No authority-claiming language in advisory modules |
| `check_boundary_imports.py` | Layered import boundaries (`--preset analyzer`, `analyzer_isolation`) |
| `no_logic_creep.yml` | No interpretation/optimization logic creep |
| `check_code_health.py` | Structural health checks |

**Invariants:**

- Every measurement artifact carries `schema_version` and `epistemic_status`
  (`observed` for captured, `derived` for computed).
- Provenance is mandatory: SHA-256 of inputs, UTC timestamp, environment.
- No artifact states that a value is good, optimal, proof of quality, or a
  build instruction.

---

## 4. Promotion pipeline

Research concepts do not enter production by assertion. They are promoted only
after evidentiary criteria are met.

```text
   Research note (docs/research/)         ← hypothesis, deferred
            │
            │  promotion criteria met
            ▼
   Lab protocol / matured workflow        ← repeatable, non-speculative
            │
            │  measurement workflow specifiable
            ▼
   TTP production (contracts + code)       ← governed, boundary-checked
```

Reference instance: `docs/research/ACOUSTIC_BALANCE_RESIDUAL_COUPLING.md`
(deferred; seven promotion criteria gate any move into TTP).

Guiding principle: **response mapping is an after-effect of good data
handling** — the evidentiary spine is completed before mapping layers are
built on top of it.

---

## 5. Provenance stack — `tap_tone_pi/provenance/` (DO-86 → DO-89)

| Module | Records |
|---|---|
| `campaign_lifecycle.py` | Campaign lifecycle state; measurement-set aggregation |
| `build_session.py` | Build session provenance |
| `environment.py` | Environmental record (tempC, RH) |
| `fixture.py` | Fixture record |
| `lineage.py` | Measurement lineage / revisions |
| `measurement_set.py`, `aggregation.py` | Measurement set + summary |
| `experiment_contracts.py`, `measurement_links.py` | Campaign / revision / link contracts |

Supported by `core/repeatability.py` (DO-85, measurement validity envelope) and
`core/session_timeline.py`.

---

## 6. Measurement stack

| Subsystem | Location | Role |
|---|---|---|
| Capture | `tap_tone_pi/capture/` | Audio + serial device capture |
| Calibration | `tap_tone_pi/calibration/` | Loopback, reference tone, FR compensation, gate, session context |
| Phase 1 | `tap_tone_pi/phase1/`, `chladni/` | Single-mic tap-tone + FFT peaks |
| Phase 2 | `tap_tone_pi/phase2/` | Roving-grid ODS, coherence, WSI |
| Damping / Wolf | `tap_tone_pi/damping/`, `wolf/` | Q-factor, wolf-tone detection |
| Bending | `tap_tone_pi/bending/` | Static EI / MOE with GUM uncertainty |
| Quality policy | `tap_tone_pi/core/quality_policy.py`, `quality_gate.py` | Hard/soft measurement-validity rules |

---

## 7. Excitation stack — `tap_tone_pi/excitation/` + transfer function (DO-90/91/93)

| Module | Role |
|---|---|
| `excitation/contracts.py` | Controlled excitation contracts (DO-90) |
| `excitation/amplitude.py`, `known_tone.py` | Amplitude + known-tone descriptors |
| `excitation/source_characterization.py` | Source characterization / provenance (DO-91) |
| `excitation/stepped_sweep.py` | Stepped & sweep excitation records (DO-93) |
| `excitation/response_pair.py`, `measurement_link.py` | Input↔response pairing |
| `transfer_function/welch.py`, `estimators.py` | Welch PSD, TF estimators |
| `transfer_function/quality.py`, `result_contract.py` | TF quality + result contract |

Input-side accounting is the prerequisite for any balance-like residual
analysis (see promotion pipeline).

---

## 8. A0 stack — `tap_tone_pi/a0/` (DO-92)

| Module | Role |
|---|---|
| `a0/contracts.py` | A0 main-body air-resonance contracts |
| `a0/peak_detection.py` | A0 peak detection |
| `a0/workflow.py` | A0 measurement workflow |

---

## 9. Experiment stack — `tap_tone_pi/experiment/` (DO-89A → DO-89D)

| Module | Role |
|---|---|
| `response_variables.py` | Declared response variables + minimum interesting effect (DO-89A) |
| `covariates.py` | Covariate definitions (DO-89A) |
| `randomization.py`, `baseline_plan.py` | Randomization + baseline rebuild plans (DO-89A) |
| `experiment_design.py`, `validation.py` | Governing design object + completeness validation (DO-89A) |
| `reference_body.py` | Reference body / metrology standard (DO-89B) |
| `process_variance.py`, `feasibility_summary.py` | σ decomposition + feasibility bands (DO-89B) |
| `cohort_regression.py` | OLS regression evidence + formula candidate (DO-89C) |
| `execution_plan.py` | Nine-section cohort execution plan + Markdown render (DO-89D) |

---

## 10. Formula stack — `tap_tone_pi/luthiery/` (DO-94 / DO-95)

| Module | Role |
|---|---|
| `formula_targets.py` | `LuthieryFormulaTargetV1`, `LuthieryFormulaEvidenceLinkV1` — declarative domain meaning (top graduation, bracing, soundhole, bridge, body air, plate stiffness) (DO-94) |
| `target_helpers.py` | Target construction + candidate-to-target linking (DO-94) |
| `formula_validation.py` | `FormulaValidationEnvelopeV1` — evidence-sufficiency + failure-mode detection (sample count, variance, repeatability, covariates, residuals, extrapolation) (DO-95) |

The formula stack attaches luthiery meaning and error-detection to regression
evidence. It produces evidence, never a verdict.

---

## 10a. Laboratory Manual — `tap_tone_pi/acoustic_lab/manual/` (DO-97)

The Laboratory Manual is an **operational component of the desktop instrument**,
not external documentation and not a measurement subsystem. It is a versioned,
read-only, offline registry of laboratory procedure documents packaged with the
TTP Analyzer.

| Module | Role |
|---|---|
| `acoustic_lab/manual_contracts.py` | `LaboratoryManualEntryV1`, `LaboratoryManualManifestV1`, status vocabulary |
| `acoustic_lab/manual_registry.py` | Read-only load / lookup / filter / path-safe resolution via `importlib.resources` |
| `acoustic_lab/manual/manual_manifest.json` | Versioned manifest (`laboratory_manual_manifest_v1`) |
| `analyzer/widgets/laboratory_manual_view.py` | Desktop **Help → Laboratory Manual** read-only viewer |

It sits **beside**, not within, the measurement stack. It is separated from
measurement execution by construction: the registry imports no capture,
calibration, phase2, cli, or server module, and the Laboratory core imports no
GUI. Procedure maturity (`approved` / `provisional` / `deferred` / `superseded`)
is registered per entry and shown in the viewer; nothing promotes an entry
automatically. This is a documentation-resource manifest, not a measurement
schema — it records document identity and maturity, never whether a hypothesis
is true.

The canonical manifest currently registers **no entries**: a consolidated
Laboratory Manual does not yet exist as a document, and DO-97 prohibited
fabricating one. The viewer shows a controlled empty state.

---

## 11. Contracts (`contracts/`)

Versioned JSON Schemas (draft 2020-12), registered in `schema_registry.json`:

```text
instrument_build_record_v1   phase2_grid              phase2_session_meta
phase1_tap_analysis_v1       phase2_ods_snapshot      phase2_wolf_candidates
wood_flitch_record_v1        phase2_point_capture_meta viewer_pack_v1
```

The M-series experiment / excitation / luthiery contracts are carried as
**optional additive blocks** inside `phase2_ods_snapshot.schema.json`, so
historical exports remain valid. Export serialization: `scripts/phase2/
export_viewer_pack_v1.py` → `viewer_pack_v1`.

---

## 12. Milestone ledger (landed on `origin/main`)

| Dev order | Layer | Status |
|---|---|---|
| DO-85 | Repeatability / measurement validity envelope | ✅ |
| DO-86 | Workflow measurement contracts | ✅ |
| DO-87 | Experiment provenance / campaign lineage | ✅ |
| DO-88 | Build session + environmental provenance | ✅ |
| DO-89 | Campaign lifecycle + measurement sets | ✅ |
| DO-89A | Experiment design + cohort planning | ✅ |
| DO-89B | Process variance + feasibility | ✅ |
| DO-89C | Covariate-aware cohort regression | ✅ |
| DO-89D | Cohort execution planning | ✅ |
| DO-90 | Controlled excitation contracts | ✅ |
| DO-91 | Excitation provenance / transfer function | ✅ |
| DO-92 | A0 main body air resonance workflow | ✅ |
| DO-93 | Stepped & sweep excitation | ✅ |
| DO-94 | Luthiery formula target mapping | ✅ |
| DO-95 | Formula validation & error-detection envelope | ✅ |
| DO-97 | Laboratory Manual packaging & desktop access | ✅ |
| — | Acoustic balance residual coupling (research, deferred) | ✅ note only |

---

## 13. Known housekeeping (non-blocking)

These have zero effect on runtime behavior and are intentionally deferred:

1. **`docs/SESSION_HANDOFF_2026-05-22.md`** — a modified working-tree file
   unrelated to this milestone. Left untouched.
2. **DO-94 numbering collision** — commits `6b74304` / `8255c8e` are tagged
   "(DO-94)" but implement pressure-response mapping, distinct from the six
   luthiery DO-94 commits. Documentation-only; noted in
   `docs/dev_orders/CURRENT.md`.
3. **`analyzer/` is not yet a packaged distribution** — `pyproject.toml`
   packages only `tap_tone_pi*` / `tap_tone*`. The desktop app runs from a
   source checkout. DO-97 shipped the Laboratory Manual **resources** inside
   `tap_tone_pi.acoustic_lab` (which *is* packaged and installed-resource
   tested), but did **not** repair full desktop-installer packaging. That
   remains a separate product-packaging task, out of DO-97 scope.
4. **DO-97's stated DO-96 dependency was vacuous** — the handoff assumed a
   prior "Laboratory manifest and registry from DO-96" and an existing
   `tap_tone_pi/acoustic_lab/` package. Neither existed in the repository;
   DO-96 appears nowhere in history. DO-97 was implemented self-contained,
   creating the `acoustic_lab` package fresh.

---

*This baseline is a snapshot. If it diverges from the code, the code is
authoritative and this document is a defect to be corrected.*
