# ADR-0011: Measurement Authority

**Status:** Accepted
**Date:** 2026-05-24
**Supersedes:** None
**Related:** ADR-0009, ADR-0010, ADR-0012

---

## Context

The tap_tone_pi system produces multiple artifact types: raw audio captures, derived measurements, quality assessments, and advisory outputs. Without clear authority boundaries, consumers may conflate capture integrity with acoustic truth, or treat derived computations as authoritative facts about instrument quality.

This ADR defines what measurement authority means and establishes the vocabulary for artifact authority classification.

---

## Decision

### Core Invariant

```
Capture integrity ≠ acoustic truth.
```

A captured artifact being a valid, uncorrupted record does not mean it establishes acoustic truth about the instrument. Capture authority proves "this signal was recorded"; it does not prove "this signal reveals instrument quality."

---

## Artifact Authority Classification

### Authoritative Capture Artifact

**Definition:** A raw, unmodified record of a physical measurement event.

**Examples:** `audio.wav`, loopback reference recording, serial timestamp log.

**Authority:** May claim "this signal was captured at this time under these conditions."

**May NOT claim:** "This signal proves acoustic quality" or "This is the correct measurement."

---

### Observational Artifact

**Definition:** Direct sensor output with minimal processing.

**Examples:** Raw WAV files, raw accelerometer data, temperature readings.

**Authority:** Record of observation. May be used as input to derived computations.

**May NOT claim:** Interpretation of what the observation means.

---

### Derived Artifact

**Definition:** Computed from observational artifacts using deterministic algorithms.

**Examples:** FFT peaks, transfer functions, coherence values, Q-factor estimates.

**Authority:** Computation authority. May claim "given inputs X, algorithm Y produced output Z."

**May NOT claim:** "This computation is the acoustic truth" or "This value is correct."

---

### Interpretive Artifact

**Definition:** Output that assigns meaning or significance to derived data.

**Examples:** Wolf tone candidate list, mode shape classification, anomaly flags.

**Authority:** Pattern recognition. May claim "this pattern matches criteria for X."

**May NOT claim:** "This is definitely X" or "This requires action."

---

### Advisory Artifact

**Definition:** Output intended to guide operator attention or suggest next steps.

**Examples:** AttentionDirectiveV1, guidance panel suggestions, workflow hints.

**Authority:** Decision support only. May claim "consider reviewing this."

**May NOT claim:** Acoustic truth, measurement validity, or required actions.

---

### Historical Artifact

**Definition:** Record of past measurements, decisions, or system state.

**Examples:** Session timeline, build history, calibration log.

**Authority:** Provenance record. May claim "this event occurred."

**May NOT claim:** Current validity or future applicability.

---

### Operator Annotation

**Definition:** Human-entered context, notes, or judgments.

**Examples:** Builder notes, specimen labels, subjective quality observations.

**Authority:** Human judgment. Explicitly marked as operator-sourced.

**May NOT claim:** Measurement authority or system-validated truth.

---

## Authority Table

| Artifact Type | Authority Domain | May Claim | May NOT Claim |
|---------------|------------------|-----------|---------------|
| Raw WAV | Observational record | "captured signal" | "acoustic truth" |
| FFT peaks | Derived measurement | "computed frequency peaks" | "correct frequencies" |
| Quality check | Measurement validity | "capture usable/unusable" | "instrument quality" |
| Wolf advisory | Decision support | "review suggested" | "wolf tone confirmed" |
| Operator note | Human annotation | "operator context" | "validated fact" |
| Toolbox prediction | External prediction | "model expectation" | "target truth" |

---

## Forbidden Claims

No artifact produced by tap_tone_pi may claim:

- "This is acoustically correct"
- "This proves quality"
- "This validates design"
- "This is the best target"
- "This measurement is true"

These claims require human expert judgment and are outside the system's authority.

---

## Consequences

### Positive

- Clear vocabulary for discussing artifact authority
- Prevents accidental authority escalation
- Enables precise schema metadata in future work
- Supports audit and governance requirements

### Negative

- Additional documentation overhead
- Developers must understand authority levels
- Some users may expect more definitive outputs

---

## Compliance

Code that produces artifacts should:

1. Know which authority class the artifact belongs to
2. Not use language that exceeds that authority
3. Include authority metadata where schema supports it (future work)

---

## References

- ADR-0009: Advisory Boundary
- ADR-0010: Guidance Authority Boundary
- ADR-0012: Epistemic Status Taxonomy
- docs/MEASUREMENT_BOUNDARY.md
- docs/AGE_CONSTITUTIONAL_CONTRACT.md
