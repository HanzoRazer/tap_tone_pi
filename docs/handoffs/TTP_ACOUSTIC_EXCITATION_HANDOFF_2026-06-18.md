# TTP Analyzer — Acoustic Excitation Framework: Implementation Handoff

**Status:** Implementation-ready, re-tiered
**Classification:** `INSTRUMENT CLASS: MEASUREMENT`
**Prepared:** 2026-06-18
**Supersedes:** the expansive "Acoustic Excitation Framework V1" handoff (the all-in-one-V1 draft)
**Operationalizes:** `docs/ROADMAP_ACOUSTIC_EXCITATION.md` (DO-90→95) — aligns to its dev-order numbering, `ExcitationContractV1`, and `KnownToneRecord`
**Companion:** `TTP_DEVELOPER_HANDOFF_2026-06-18.md` (cohort design, §VIII parameters)

---

## 0. What changed from the prior draft, and the one open assumption

The prior handoff was a good *vision* document and the wrong shape for the *next step*. It scoped all five phases as "V1 / High Priority," its acceptance criteria were capability checkboxes rather than quality thresholds, it wrote the modal-participation maps as if a microphone measures mode shape, and it loosened the amplitude guardrail back to full scale. This version keeps that draft's excellent boundary discipline (MEASUREMENT-class, explicit Non-Goals, advisory-only tagging) and fixes the rest.

**The one assumption I made so I could write the protocol** (flip it if wrong): the per-style reference bodies are built in **both** forms — **finished bodies with soundholes** (instrument-style drift-control references) **and** a small set of **closed-top blanks** (uncut research canvases for the soundhole-mapping experiment). They answer different questions and §6 shows you need both; a hole can't be un-cut, so one artifact can't do both jobs.

---

## 1. Purpose and the disciplined scope

The framework replaces **unknown excitation** (the tap — variable energy, location, and force) with **known excitation** (generated tones and sweeps), turning a deconvolution-and-interpret problem into a clean transfer function `H(f) = response(f) / excitation(f)`.

**Why a slice of this is near-term and the rest is deferred.** The broad vision — modal-participation mapping, soundhole research, "acoustic development platform" — stays deferred until there is a characterized process and a formula to hang it on (per the cohort plan). But one narrow slice earns the near-term slot for a concrete reason: **controlled excitation is itself one of the largest σ_process reducers.** Tap variability is a dominant noise source in the dreadnought cohort; replacing the tap with a repeatable known excitation directly tightens process variance. That is not platform ambition — it is noise-floor reduction in service of batch-1.

---

## 2. Track structure (mapped to the repo roadmap)

| Track | Dev Order | Deliverable | Justification |
|---|---|---|---|
| **V1 core (near-term)** | DO-90 | Signal Generator Module (tone / stepped / sweep) | The σ_process reducer — a repeatable excitation source |
| **V1 core (near-term)** | DO-91 | Excitation provenance + transfer-function workflow | Lets cohort measurement workflows invoke known excitation and record it |
| **V1 first application** | DO-92 | `MainBodyAirResonanceWorkflowV1` (A0) | Low-risk, high-value; A0 is a response-variable candidate for the cohort |
| **Deferred (research tier)** | DO-93 | `FlatPlateResonanceWorkflowV1` | Pre-assembly plate study; not on the cohort critical path |
| **Deferred (research tier)** | DO-94 | `ModalParticipationMappingWorkflowV1` | Research; carries unresolved measurement-physics risk (§8) |
| **Deferred (research tier)** | DO-95 | Soundhole Placement Research Workflow | Research; Spiral-Jumbo IP track, hypothesis-stage |

Build DO-90 → DO-91 → DO-92, then stop and let the cohort run. DO-93–95 activate only when the process is characterized and there is a reason to map.

---

## 3. DO-90 — Signal Generator Module

Use the roadmap's `ExcitationContractV1` and `KnownToneRecord` as-is. Three modes:

| Mode | CLI | Use |
|---|---|---|
| Fixed tone | `ttp emit-tone --frequency-hz 440 --duration-s 5 --amplitude 0.2` | Reference / calibration / single-frequency excitation |
| Stepped | `ttp emit-steps --start-hz 80 --stop-hz 130 --step-hz 2` | Resonance discovery, A0 hunting |
| Sweep | `ttp emit-sweep --start-hz 80 --stop-hz 130 --duration-s 20` | Transfer-function estimation |

**Two corrections to the roadmap's validation block:**

1. **Amplitude default and ceiling.** The contract field stays normalized `0.0–1.0`, but the *operational default* is **0.2** (band 0.1–0.25), and amplitudes above ~0.5 must emit a clipping/over-drive warning. Full-scale output distorts the source and risks the input chain. Never default to 1.0.
2. **Source characterization is mandatory, not optional.** A generated tone is only "known" at the DAC. By the time it reaches the plate it has passed through an amplifier and a speaker that distort — and a small speaker driven at low frequency produces harmonics that land *inside* your measurement band. **The FRF is only as clean as the source.** DO-90 must include a source-response capture (loopback / reference-mic characterization of the emit chain) stored alongside `KnownToneRecord`, so excitation distortion is measured, not assumed. This is the same discipline as the OPA1612 input side, applied to the output side.

---

## 4. DO-91 — Excitation provenance + transfer function

Wire excitation into the existing provenance stack exactly as the roadmap's integration table specifies (DO-86 workflow contract, DO-87 lineage, DO-88 fixture/environment, DO-89 measurement set). The transfer-function workflow computes `H(f) = measured_response(f) / excitation(f)` and records the excitation event (`ExcitationContractV1` + source characterization) as part of the measurement's provenance — so any FRF can be traced to the exact signal that produced it. `epistemic_status` of derived quantities follows ADR-0012.

---

## 5. DO-92 — Main Body Air Resonance (A0) workflow

This is the strongest, most-buildable application. Drive the cavity and read pressure at the soundhole to isolate the Helmholtz/A0 mode from the soundboard mode that normally overshadows it.

**Setup:** speaker 6–12 in from soundhole; microphone 1–2 in in front of soundhole; sweep 70–130 Hz; ≥3 reps.
**Outputs → `A0MeasurementRecord`:** A0 frequency, amplitude, bandwidth, Q, measurement confidence, repeatability score.

**Caveat to record in the workflow doc:** even soundhole-pressure A0 is a *cavity-coupled* measurement; the speaker position and room contribute. Fix speaker and mic geometry as part of the workflow contract (DO-88 fixture record) and log the ambient-noise baseline before excitation. Repeatability is only meaningful at fixed geometry.

---

## 6. Reference Artifact / Baseline Body Protocol  ★ new, load-bearing

This is the part neither prior document had, and it is what makes the cohort's σ_process number honest.

### 6.1 Why it exists — the variance decomposition

Build-to-build scatter is two independent noise sources:

```
σ²_total = σ²_measurement + σ²_build
```

- `σ_measurement` = instrument + fixture + operator + environment noise (your *measuring*).
- `σ_build` = recipe-to-recipe variation (your *hands*).

The batch-1 plan as originally framed measured `σ_total` and silently called it "process variance." You cannot fix what you cannot separate — and if the dominant term turns out to be `σ_measurement`, no amount of careful building rescues the experiment. **A kept physical reference body separates the two for free.**

### 6.2 The two reference types (build both)

| Reference | What it is | Isolates | Re-used how |
|---|---|---|---|
| **Kept physical baseline body** | One finished body per style, neck attached, **no strings, no tuners** | **σ_measurement** | Re-measure the *same physical body* N times across days → the spread *is* σ_measurement |
| **Rebuilt baseline spec** | The same frozen recipe re-built at builds 1 / 8 / 15 / 20 | **σ_build** + builder skill drift | Each rebuild is a fresh instance of the control recipe |
| **Closed-top research blank** | Uncut top on body, built for mapping | n/a (research canvas) | DO-94/95 modal mapping — needs an *uncut* top so you can map, then cut |

The kept body is your **metrology reference** (a gauge block); the rebuilt spec is your **process-control reference**. They are complementary, not redundant.

### 6.3 The baseline body state (per the oud method, corrected)

The reference state is a **complete body with the neck attached but no strings and no tuning keys** — the maximally repeatable *relaxed assembled* state. It keeps neck coupling (real: neck mass and stiffness move the whole-instrument modes) while stripping the two variable, removable, hard-to-control elements (string tension, tuner mass). This is the oud builders' state and it is the right one for a reference standard, because a standard needs *consistency*, not finality.

### 6.4 Per-style coverage

Build one reference body per target geometry — **dreadnought, OM, OOO, Jumbo** — giving a per-geometry control *plus*, as a byproduct, a **cross-style scaling dataset**: how A0 and the main top monopole move with body size. Store each with full metadata (species, dimensions, thickness map, mass, grain, build date, measured E_L/E_C/ρ).

### 6.5 Three caveats that go in the protocol now

1. **Unstrung ≠ the strung acoustic state.** No string down-bearing means the strung top sits stiffer and its modes shift. The unstrung body is a valid *reference* and is arguably the correct state for modal-location and relative-comparison work. But any formula meant to predict the *strung* instrument needs a characterized string-load delta. **Decide up front** whether the unstrung signature is the optimization proxy (the oud tradition's implicit choice) or whether you carry the offset.
2. **A hole can't be un-cut.** A finished reference body cannot double as the soundhole-mapping canvas — that needs an *uncut* closed-top blank (§6.2 row 3). Two artifacts, two jobs.
3. **The reference itself drifts.** Wood breathes with humidity and ages. Treat the kept body as a *relative* drift check — watch for *changes* in its signature, not absolute constancy — store it in controlled humidity, and correct each measurement with the environmental provenance you already log (DO-88). A reference standard you don't environmentally control will lie to you.

---

## 7. Cohort integration — what the feasibility evidence must now report

The batch-1 deliverable (per the companion developer handoff §IV) is the **process-variance feasibility evidence** — measurement-class, not a verdict. With the reference body in place, that evidence must report the two terms **separately**:

- `σ_measurement` — from repeated measurement of the kept reference body.
- `σ_build` — from `σ_total` (the five nominally-identical dreadnoughts) with `σ_measurement` subtracted.

Only then can the feasibility summary answer the real question — *is my variation in my building or my measuring?* — and only then is the green/yellow/red σ_process band (developer handoff §VIII-4) meaningful. The DO-85 repeatability/validity-envelope output is the natural home for this decomposition.

---

## 8. Deferred research tier (DO-93 / 94 / 95) — caveats baked in

Activate only after the process is characterized. When written, these workflow docs **must carry** the following, or they will produce confounded data presented as clean (CBSP21 territory):

- **DO-94 Modal Participation Mapping — the measurement-physics caveat.** A microphone moved above a plate measures **radiated near-field pressure, not plate surface velocity (mode shape).** The pressure map is confounded by diffraction and, critically, **room standing waves** across 90–880 Hz. For true operating-deflection-shape, measure *motion* (accelerometer / laser vibrometer) or use the existing Phase-2 ODS tap-grid. State this limitation in the artifact; treat the pressure map as an *approximation* of antinode location, environment-controlled.
- **DO-95 Soundhole Placement — the hypothesis flag.** The oud method (and the spiral-as-frequency-selective-coupling idea) is a **hypothesis to test, not a mechanism**. Placing an aperture at a 440 Hz antinode *changes* that mode (compliance/coupling shifts) — there is feedback in the loop. The workflow's value is that it lets you *test* whether modal activity predicts good aperture placement, rigorously, rather than mythologize it. Any `SoundholePlacementRecommendation` artifact is **advisory-only** and lives outside the measurement provenance chain.

---

## 9. Schema & provenance requirements (rigor hooks)

Every new record type must be a real contract, not a gesture:

| Record | Requirement |
|---|---|
| `ExcitationContractV1`, `KnownToneRecord` | Schema in `contracts/schemas/`, entry in `schema_registry.json`, `epistemic_status` per ADR-0012 |
| `A0MeasurementRecord`, `PlateResponseRecord`, `ModalParticipationMap` | Same; plus lineage wiring (DO-87), fixture + environment context (DO-88), measurement-set grouping (DO-89) |
| `ReferenceBodyRecord` (new) | Schema + registry entry; links the kept body to its repeated measurements so σ_measurement is queryable over time |
| All modules | `# INSTRUMENT CLASS: MEASUREMENT` header; pass `ci/check_advisory_boundary.py` and `guidance_language_guard` |

`SoundholePlacementRecommendation` is the sole DECISION-SUPPORT artifact and must be gated accordingly (never enters `viewer_pack_v1`).

---

## 10. Non-Goals (kept from the prior draft — verbatim intent)

Not in this framework: automatic luthier advice, tone-quality scoring, AI recommendations, build recommendations. The framework is **measurement-first**; interpretation is left to the researcher. The one advisory artifact (§8) is explicitly tagged and gated.

---

## 11. Acceptance criteria (threshold-based, not capability-based)

V1 (DO-90→92) is complete when:

1. Fixed, stepped, and swept excitation emit correctly **and the emit chain's own response is characterized and stored** (not just "tones play").
2. A measurement workflow can invoke excitation and record `ExcitationContractV1` in its provenance.
3. The A0 workflow produces A0 frequency with **repeatability CV ≤ a stated threshold** (default ≤ 3% on the kept reference body at fixed geometry) — a number, not "produces results."
4. The kept reference body yields a stable `σ_measurement` estimate, and the feasibility summary reports `σ_measurement` and `σ_build` separately.
5. All excitation and measurement events carry metadata, lineage, fixture, and environment provenance.

DO-93–95 remain explicitly **out of V1**.

---

## 12. Recommended build order

```
DO-90 Signal Generator (+ source characterization)
   → DO-91 Excitation provenance + TF workflow
   → DO-92 A0 workflow
   → Build the per-style reference bodies (finished + closed-top blanks)
   → Stand up σ_measurement / σ_build decomposition in the feasibility summary
   → [run the dreadnought cohort]
   → DO-93/94/95 only when process is characterized and mapping has a purpose
```

The excitation source exists to make the cohort's measurements repeatable and to give you a metrology reference. Build it for that first. The research platform is what it *becomes*, not what you build today.
