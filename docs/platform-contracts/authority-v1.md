# Authority Classes (v1)

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository contract for authority classification

---

## Purpose

This document defines the four authority classes used across the acoustic measurement and manufacturing ecosystem. Authority class determines what claims an artifact may make and how downstream systems may interpret it.

---

## Authority Classes

### MEASUREMENT

Artifacts produced by calibrated sensor capture and deterministic signal processing.

| Property | Value |
|----------|-------|
| Can establish truth | No (capture integrity, not acoustic truth) |
| Can modify measurement | N/A (is measurement) |
| Can enter measurement export | Yes |
| Epistemic status range | Observed, Derived, Estimated |

**Examples:**
- Raw WAV capture
- FFT peak extraction
- Transfer function computation
- Coherence values

### PROVENANCE

Artifacts that record lineage, history, and chain-of-custody without making quality claims.

| Property | Value |
|----------|-------|
| Can establish truth | No |
| Can modify measurement | No |
| Can enter measurement export | Meta only |
| Epistemic status range | Historical, Operator-Annotated |

**Examples:**
- Session timeline
- Calibration certificates
- Operator notes
- Git commit hashes

### DECISION_SUPPORT

Artifacts produced by advisory systems that route attention but do not establish facts.

| Property | Value |
|----------|-------|
| Can establish truth | No |
| Can modify measurement | No |
| Can enter measurement export | No |
| Epistemic status range | Heuristic |

**Examples:**
- AGE directives
- Wolf candidate highlights
- Review queue priority
- Attention suggestions

### INTERPRETIVE

Artifacts that contain external predictions, model outputs, or third-party assessments.

| Property | Value |
|----------|-------|
| Can establish truth | No |
| Can modify measurement | No |
| Can enter measurement export | Marked as prediction |
| Epistemic status range | Predicted, Externally-Sourced |

**Examples:**
- Rayleigh-Ritz mode predictions
- Toolbox target frequencies
- Material database lookups
- External calibration data

---

## Invariants

1. **No authority escalation.** A downstream artifact cannot claim higher authority than its inputs.

2. **No silent inheritance.** Authority class must be explicit; it cannot be inferred from context.

3. **Capture integrity ≠ acoustic truth.** MEASUREMENT class confirms valid capture, not instrument quality.

4. **Advisory cannot become evidence.** DECISION_SUPPORT artifacts cannot enter MEASUREMENT exports.

---

## Cross-Repository Mapping

| Repository | MEASUREMENT | PROVENANCE | DECISION_SUPPORT | INTERPRETIVE |
|------------|-------------|------------|------------------|--------------|
| tap_tone_pi | `AuthorityClass.MEASUREMENT` | `AuthorityClass.PROVENANCE` | `AuthorityClass.DECISION_SUPPORT` | `AuthorityClass.INTERPRETIVE` |
| luthiers-toolbox | `AuthorityState.GOVERNED` | `AuthorityState.BLOCKED_PROVENANCE` | `AuthorityState.UNDER_REVIEW` | `AuthorityState.PREDICTION` |
| CAM-Assist-Blueprint | `authority_block.measurement` | `authority_block.provenance` | `authority_block.advisory` | `authority_block.external` |

---

## Non-Goals

This contract does NOT:
- Define confidence scoring (see confidence-v1)
- Define epistemic status taxonomy (see epistemic-status-v1)
- Define review decision semantics (see review-decision-v1)
- Prescribe implementation details
- Require shared runtime packages

---

## See Also

- [confidence-v1](confidence-v1.md)
- [epistemic-status-v1](epistemic-status-v1.md)
- [review-decision-v1](review-decision-v1.md)
- tap_tone_pi: ADR-0010, ADR-0011
- luthiers-toolbox: GOVERNANCE_RUNNER.md
