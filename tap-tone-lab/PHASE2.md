# PHASE2.md

## Phase 2 Charter — Advanced Acoustic Measurement Extensions

**Project:** `tap_tone_pi`
**Status:** Phase 1 frozen at `v1.0-instrumentation`
**Phase:** Phase 2 — Advanced Measurement
**Audience:** Instrument developers, research collaborators, future maintainers
**Effective Date:** Upon creation of `phase-2-advanced-measurement` milestone

---

## 1. Purpose of Phase 2

Phase 2 exists to **extend the measurement capability** of `tap_tone_pi` while **preserving the scientific integrity** of the v1.0 instrumentation baseline.

Phase 2 **does not reinterpret, grade, optimize, or diagnose instruments**.
Phase 2 adds **additional ways to observe physical response** under controlled excitation.

> **Phase 1 answers:** "What frequencies are present?"
> **Phase 2 answers:** "How does the system respond spatially, temporally, and coherently under excitation?"

---

## 2. Namespace & Phase Enforcement

Phase 2 work is explicitly identified by **filename prefix**, not directory structure.

All experimental scripts **must** use one of the approved prefixes defined in:

- `docs/NAMESPACE_POLICY.md`

Approved experimental prefixes include:

- `wolf_` — wolf-note / instability metrics
- `ir_` — impulse response & time-gated analysis
- `ods_` — operational deflection shapes / roving-grid analysis
- `exp_` — exploratory measurement probes

Any change touching these prefixed scripts is classified as **Phase 2 Experimental** and is enforced by CI
(`scripts/ci/phase_gate.py`) to require both:

- `phase2`
- `experimental`

labels on the pull request.

This rule prevents Phase 2 research from contaminating the frozen Phase 1 instrumentation baseline.

---

## 3. Contributor Quick Rules (Read Before You Commit)

1. **This is a measurement instrument, not a design tool.**
   - Capture and characterize signals.
   - Do not add interpretation, optimization, or musical judgments.

2. **Phase 1 is frozen.**
   - Any change to protected Phase 1 files requires explicit approval (`phase1-approved`).
   - If in doubt, assume a file is protected.

3. **Experimental work must self-identify by filename prefix.**
   - Use one of: `wolf_`, `ir_`, `ods_`, `exp_`
   - Prefixes define Phase 2 scope and trigger CI enforcement.

4. **Label your intent in the PR.**
   - Phase 2 experimental work requires both labels:
     - `phase2`
     - `experimental`
   - CI will fail ambiguous or mislabeled changes.

5. **Do not mutate raw evidence.**
   - Raw audio and primary measurements are immutable.
   - Derived analysis must be versioned and reproducible.

6. **Favor determinism over cleverness.**
   - Same input → same output.
   - If results vary, expose variance; do not hide it.

7. **Filesystem-first, API-second.**
   - Artifacts must be understandable without a database or server.
   - Exportability is a feature, not an afterthought.

8. **When unsure, choose the safer boundary.**
   - Use `exp_` instead of guessing permanence.
   - Ask before modifying baseline paths.

---

## 4. Governing Principles (Non-Negotiable)

Phase 2 work must comply with all of the following:

1. **Measurement-only**

   * Outputs are numerical, spatial, or temporal measurements
   * No subjective descriptors
   * No musical or tonal judgments

2. **Non-invasive**

   * Avoid added mass where possible
   * Prefer air-coupled or reference-based excitation
   * Sequential measurement favored over simultaneous loading

3. **Repeatable**

   * Identical inputs must yield identical outputs (within numerical tolerance)
   * All parameters must be logged and serialized

4. **Auditable**

   * Every derived value must be traceable to raw evidence
   * Raw evidence is always preserved

5. **Phase-isolated**

   * Phase 2 **must not modify** Phase 1 output schemas or semantics
   * Phase 1 remains immutable once frozen

---

## 5. Scope of Phase 2

Phase 2 includes **advanced observation techniques** that are standard in experimental acoustics and structural dynamics.

### 3.1 In-Scope Capabilities

#### A. Time-Gated Impulse Response (IR)

* Speaker-air excitation (log chirp or broadband)
* Deconvolution to impulse response
* Time gating to suppress room reflections
* Gated frequency response extraction
* Explicit gating metadata (window type, bounds)

#### B. Cross-Channel Measurement

* Fixed reference sensor (or reference mic)
* Roving response sensor (mic)
* Transfer function magnitude
* Coherence
* Phase

#### C. Roving-Grid Operational Deflection Shapes (ODS)

* Sequential point-by-point capture
* Spatial grid definition in millimeters
* Reconstruction of frequency-dependent response fields
* No requirement for real-time animation

#### D. Experimental Wolf-Related Metrics

* Energy gradients across space vs frequency
* Phase variance metrics
* Localization indices
* Wolf Severity Index (WSI) marked explicitly as *experimental*

---

## 6. Non-Goals (Phase 2)

Phase 2 exists to **extend measurement capability**, not to evolve this project into a design advisor or musical evaluator.

The following are **explicitly out of scope** for Phase 2 and must not be introduced:

### ❌ Interpretive Features
- Musical or tonal descriptors (e.g., "warm," "bright," "balanced")
- Quality scoring, grading, or ranking of instruments
- "Good vs bad" judgments of measurements
- Auto-generated recommendations or prescriptions

### ❌ Design or Optimization Logic
- Brace thinning suggestions
- Material selection advice
- Geometry modification proposals
- Closed-loop optimization or feedback into CAD/CAM

### ❌ Real-Time or Player-Facing Systems
- Real-time signal processing for performance
- Live monitoring intended for musicians
- Effects, EQ, compression, or enhancement

### ❌ Machine Learning / Heuristics
- ML-based pattern recognition
- Black-box inference models
- "Smart" classifiers or predictors

### ❌ Tight ToolBox Coupling
- Hard dependencies on Luthier's ToolBox runtime
- Required API calls during capture or analysis
- Assumptions about downstream consumers

### ❌ Mutation of Evidence
- Editing, normalizing, or filtering raw audio post-capture
- Overwriting primary measurements
- Silent reprocessing without versioning

---

### Rationale

Phase 2 research may feel close to interpretation or optimization, but this project must remain a **forensic measurement instrument**.

Interpretation belongs downstream.
Measurement must remain neutral, reproducible, and defensible.

---

## 7. Data & Schema Discipline

Phase 2 **extends** but does not replace Phase 1 data contracts.

### Requirements:

* Unified `manifest.json` across phases
* Content-addressed files (sha256)
* Explicit `kind` for every artifact
* Optional `point_id` and spatial metadata
* Explicit units (canonical: millimeters)

### Experimental Marking:

Any Phase 2 output that is not yet fully validated **must include**:

```json
"experimental": true
```

---

## 8. Relationship to ToolBox / RMOS

Phase 2 remains **ToolBox-agnostic**.

* RMOS compatibility is achieved via:

  * Stable manifests
  * Content-addressed attachments
  * Clear provenance metadata

Phase 2 data **may inform** design systems later, but **never dictate them**.

> Measurement informs decisions; it does not make them.

---

## 9. Success Criteria for Phase 2 Completion

Phase 2 can be considered complete when:

* A roving-grid session can be captured and reconstructed
* Time-gated IR produces repeatable frequency responses
* Cross-channel coherence and phase are stable and deterministic
* All artifacts validate against schemas
* No Phase 1 behavior has changed
* No interpretive language appears in outputs

---

## 10. Phase Boundaries Going Forward

* **Phase 1:** Single-point frequency presence (baseline, frozen)
* **Phase 2:** Spatial / temporal / coherence observability
* **Phase 3 (future):** Tooling, automation, visualization (new charter required)

No Phase 3 work may begin without a new charter.

---

## 11. Final Statement

Phase 2 exists to **expand observability**, not authority.

The value of `tap_tone_pi` is not that it "knows guitars,"
but that it **measures reality cleanly enough that experts can trust it**.

---

See also:
- `docs/NAMESPACE_POLICY.md` — authoritative naming and phase rules
- `BASELINE.md` — frozen Phase 1 instrumentation contract

---

**Approved by:**
Instrumentation Lead / Maintainer

**Status:** Active upon milestone creation
