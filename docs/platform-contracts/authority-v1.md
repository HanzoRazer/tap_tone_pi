# Authority Classes (v1)

**Version:** 1.0.0
**Status:** Draft
**Scope:** Cross-repository contract for authority classification

---

## Purpose

This document defines the six authority classes used across the acoustic measurement and manufacturing ecosystem. Authority class determines what claims an artifact may make and how downstream systems may interpret it.

---

## Core Invariant

```
Decision-support authority may route attention but may not establish truth.
```

---

## Authority Classes

### measurement

Artifacts produced by calibrated sensor capture and deterministic signal processing.

| Property | Value |
|----------|-------|
| Can establish truth | No (capture integrity, not acoustic truth) |
| Can authorize execution | No |
| Can enter measurement export | Yes |
| Epistemic status range | observed, derived, estimated |

**Examples:**
- Raw WAV capture
- FFT peak extraction
- Transfer function computation
- Coherence values

### provenance

Artifacts that record lineage, history, and chain-of-custody without making quality claims.

| Property | Value |
|----------|-------|
| Can establish truth | No |
| Can authorize execution | No |
| Can enter measurement export | Meta only |
| Epistemic status range | historical, operator_annotated |

**Examples:**
- Session timeline
- Calibration certificates
- Operator notes
- Git commit hashes

### decision_support

Artifacts produced by advisory systems that route attention but do not establish facts.

| Property | Value |
|----------|-------|
| Can establish truth | No |
| Can authorize execution | No |
| Can enter measurement export | No |
| Epistemic status range | heuristic |

**Examples:**
- AGE directives
- Wolf candidate highlights
- Review queue priority
- Attention suggestions

### interpretive

Artifacts that contain external predictions, model outputs, or third-party assessments.

| Property | Value |
|----------|-------|
| Can establish truth | No |
| Can authorize execution | No |
| Can enter measurement export | Marked as prediction |
| Epistemic status range | predicted, externally_sourced |

**Examples:**
- Rayleigh-Ritz mode predictions
- Toolbox target frequencies
- Material database lookups
- External calibration data

### operator

Artifacts produced by human operator input with sovereignty over their domain.

| Property | Value |
|----------|-------|
| Can establish truth | No (records human judgment, not objective truth) |
| Can authorize execution | No (records decision, not authorization) |
| Can enter measurement export | As operator annotation only |
| Epistemic status range | operator_annotated |

**Examples:**
- Build selection decisions
- Quality override reasons
- Session notes
- Review decisions

### external

Artifacts imported from external systems with source binding.

| Property | Value |
|----------|-------|
| Can establish truth | No |
| Can authorize execution | No |
| Can enter measurement export | With source citation |
| Epistemic status range | externally_sourced |

**Examples:**
- Imported DXF geometry
- Vectorizer output
- Third-party calibration data
- Material database values

---

## Invariants

1. **No authority escalation.** A downstream artifact cannot claim higher authority than its inputs.

2. **No silent inheritance.** Authority class must be explicit; it cannot be inferred from context.

3. **Capture integrity ≠ acoustic truth.** `measurement` class confirms valid capture, not instrument quality.

4. **Advisory cannot become evidence.** `decision_support` artifacts cannot enter `measurement` exports.

5. **Operator sovereignty.** `operator` class records human decisions but does not grant execution authority.

6. **External binding.** `external` class artifacts retain their source binding and cannot be laundered as local measurement.

---

## Cross-Repository Mapping

| Canonical | tap_tone_pi | luthiers-toolbox | CAM-Assist |
|-----------|-------------|------------------|------------|
| measurement | AuthorityClass.MEASUREMENT | LIFECYCLE_GOVERNED / COMPAT_ONLY | N/A |
| provenance | AuthorityClass.PROVENANCE | artifact.provenance | source_spec_id |
| decision_support | AuthorityClass.DECISION_SUPPORT | Review UX / rank signals | Review packet prose |
| interpretive | AuthorityClass.INTERPRETIVE | candidate.prediction | strategy intent |
| operator | Operator sovereignty | ReviewDecisionRecord | A12 decision record |
| external | Externally-Sourced | imported DXF / vectorizer | source_spec_id |

---

## Non-Goals

This contract does NOT:
- Authorize execution (review approval ≠ execution authorization)
- Merge review systems across repositories
- Replace local enums (use `local_authority_type` for mapping)
- Define confidence scoring (see confidence-v1)
- Define epistemic status taxonomy (see epistemic-status-v1)
- Define review decision semantics (see review-decision-v1)

---

## See Also

- [confidence-v1](confidence-v1.md)
- [epistemic-status-v1](epistemic-status-v1.md)
- [review-decision-v1](review-decision-v1.md)
- tap_tone_pi: ADR-0010, ADR-0011
- luthiers-toolbox: GOVERNANCE_RUNNER.md
