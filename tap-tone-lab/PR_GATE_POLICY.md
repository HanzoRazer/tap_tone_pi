# PR_GATE_POLICY.md

## Pull Request Gate Policy — Phase Isolation & Instrument Integrity

**Project:** `tap_tone_pi`
**Applies to:** All pull requests
**Effective:** Immediately
**Authority:** Instrumentation Maintainer

---

## 1. Purpose

This policy exists to **protect the scientific integrity of the v1.0 instrumentation baseline** while allowing controlled expansion under Phase 2.

The primary risk addressed by this policy is **phase contamination**:

* Phase 2 features silently altering Phase 1 behavior
* Experimental work leaking into baseline measurement paths
* Interpretation creeping into measurement code

This policy ensures:

* Phase 1 remains immutable
* Phase 2 is explicitly additive
* Experimental work is clearly labeled and isolated

---

## 2. Phase Definitions (Binding)

### Phase 1 — Instrumentation Baseline (Frozen)

* Tagged: `v1.0-instrumentation`
* Status: **Immutable**
* Purpose: Single-point acoustic measurement and characterization

### Phase 2 — Advanced Measurement (Active)

* Milestone: `phase-2-advanced-measurement`
* Purpose: Spatial, temporal, and cross-channel observability
* Status: Additive only

No other phases are recognized without a formal charter.

---

## 3. Protected Phase 1 Surface

The following are **Phase 1 protected assets**:

### 3.1 Protected Directories

Changes to these paths are **blocked by default**:

```
tap_tone/
├── capture.py
├── analysis.py
├── storage.py
├── main.py
├── ui_simple.py
schemas/
├── measurement.schema.json
├── analysis.schema.json
BASELINE.md
```

### 3.2 Protected Semantics

Even if files are unchanged:

* Output field names
* Units
* Status semantics
* Peak detection meaning
* JSON structure

**Must not change**.

---

## 4. Allowed Changes (Without Exception)

PRs are allowed without special approval if they meet **all** of the following:

* Only add new files
* Only modify files under:

  ```
  scripts/
  phase2/
  docs/
  tests/
  ```
* Do not change Phase 1 outputs
* Do not reinterpret data
* Are tagged with:

  * `phase2` OR `maintenance`

---

## 5. Changes Requiring Explicit Review & Approval

The following **require maintainer approval** and must include justification:

### 5.1 Phase 1 Touches

Any PR that:

* Modifies protected Phase 1 files
* Changes schemas affecting Phase 1
* Alters analysis behavior, thresholds, or math

**Required additions to PR description:**

* Explicit reason
* Proof it does not alter v1.0 semantics
* Regression test evidence

---

### 5.2 Schema Extensions

Allowed only if:

* New fields are optional
* Existing fields remain unchanged
* Experimental fields are explicitly marked

Example:

```json
"experimental": true
```

---

## 6. Experimental Feature Requirements (Phase 2)

All Phase 2 experimental outputs must:

* Include `"experimental": true`
* Include algorithm/version metadata
* Preserve raw evidence (WAV, raw spectra)
* Avoid prescriptive or interpretive language

---

## 7. Required PR Metadata

Every PR must include:

* **Phase tag** in title or labels:

  * `[Phase1-Maintenance]`
  * `[Phase2]`
* Short statement answering:

  > "Does this PR alter Phase 1 behavior?"

Example:

```text
Phase impact: Phase 2 only — additive scripts and schemas; Phase 1 untouched.
```

PRs without this statement **will not be merged**.

---

## 8. CI / Automation Hooks (Future)

This policy is designed to be enforceable via CI in the future:

### Planned Checks

* Diff-based path protection
* Schema compatibility checks
* Golden WAV regression tests
* Experimental flag validation

Until automated, **human review enforces this policy**.

---

## 9. Enforcement Authority

The Instrumentation Maintainer has final authority to:

* Block PRs
* Require rework
* Roll back merged changes that violate this policy

No exception exists for convenience or speed.

---

## 10. Final Statement

This project is an **instrument**, not a feature playground.

Every PR must preserve:

* repeatability
* auditability
* physical honesty

If a change cannot be defended in a lab notebook, it does not belong here.

---

**Approved by:**
Instrumentation Maintainer

**Status:** Active
