# ADR-0012: Epistemic Status Taxonomy

**Status:** Accepted  
**Date:** 2026-05-24  
**Supersedes:** None  
**Related:** ADR-0010, ADR-0011

---

## Context

Data flows through tap_tone_pi from raw capture to derived computation to advisory output. Each transformation changes the epistemic status of the data—its relationship to ground truth and its authority for downstream use.

Without explicit epistemic classification, consumers cannot distinguish between directly observed data, computed derivations, model predictions, and heuristic suggestions. This creates risk of authority inheritance: treating a prediction as if it had the same authority as an observation.

---

## Decision

### Core Invariant

```
No epistemic state may silently inherit another state's authority.
```

A value derived from an observation does not automatically carry the observation's authority. A prediction based on a derivation does not carry the derivation's authority. Each transformation must be explicitly tracked.

---

## Epistemic Status Definitions

### Observed

**Definition:** Directly captured from physical sensors with no computation beyond digitization.

**Allowed Source:** Hardware sensors, ADC, serial devices, calibrated instruments.

**Authority Level:** Record authority. The highest level of epistemic certainty in the system.

**Export Implication:** May appear in canonical measurement exports.

**May Influence Guidance:** Yes, as factual input.

**Examples:**
- `audio.wav` (raw capture)
- Temperature sensor reading
- Calibration reference tone

---

### Derived

**Definition:** Computed from Observed data using deterministic, documented algorithms.

**Allowed Source:** DSP pipelines, mathematical transformations, statistical aggregations.

**Authority Level:** Computation authority. Correctness depends on algorithm validity and input quality.

**Export Implication:** May appear in measurement exports with algorithm provenance.

**May Influence Guidance:** Yes, as computed input.

**Examples:**
- FFT peaks from audio
- Transfer function from stimulus/response
- Q-factor from decay curve
- Coherence between channels

---

### Estimated

**Definition:** Approximation with acknowledged uncertainty or incomplete information.

**Allowed Source:** Interpolation, curve fitting, statistical inference with confidence bounds.

**Authority Level:** Limited inference. Should include uncertainty quantification.

**Export Implication:** May appear in exports with uncertainty metadata.

**May Influence Guidance:** Yes, with uncertainty acknowledged.

**Examples:**
- SNR estimate from limited samples
- Mode frequency from noisy peak
- Interpolated grid point

---

### Predicted

**Definition:** Output of a predictive model, not directly computed from current observations.

**Allowed Source:** Machine learning models, physics simulations, external prediction services.

**Authority Level:** External expectation. No measurement authority.

**Export Implication:** Must be marked as prediction, not measurement.

**May Influence Guidance:** As context only, not as fact.

**Examples:**
- Toolbox target frequencies
- Expected mode shapes from Rayleigh-Ritz
- Material property lookup from database

---

### Heuristic

**Definition:** Rule-of-thumb or pattern-based suggestion without rigorous derivation.

**Allowed Source:** Expert rules, threshold policies, attention algorithms.

**Authority Level:** Non-authoritative. Advisory only.

**Export Implication:** Advisory/meta exports only. Never canonical measurement.

**May Influence Guidance:** Yes, this IS guidance output.

**Examples:**
- "Review this region" directive
- Wolf tone candidate flag
- FTUE workflow hint

---

### Operator-Annotated

**Definition:** Human-entered information not derived from system measurement.

**Allowed Source:** User input, builder notes, manual classification.

**Authority Level:** Human judgment. Explicitly marked as operator-sourced.

**Export Implication:** May appear in exports with operator attribution.

**May Influence Guidance:** As context, not as system-derived fact.

**Examples:**
- Specimen label
- Build stage notes
- Subjective quality observation
- "Known issue" flag

---

### Externally-Sourced

**Definition:** Data imported from outside the tap_tone_pi measurement session.

**Allowed Source:** Material databases, reference libraries, external APIs, imported files.

**Authority Level:** Source-bound. Authority depends on the external source.

**Export Implication:** Must preserve source attribution. Cannot claim local measurement authority.

**May Influence Guidance:** As reference context only.

**Examples:**
- Wood species properties from database
- Reference spectrum from library
- Imported calibration certificate
- Historical session data

---

## Status Transition Rules

### Allowed Transitions

| From | To | Requires |
|------|-----|----------|
| Observed | Derived | Documented algorithm |
| Derived | Estimated | Uncertainty quantification |
| Any | Heuristic | Explicit authority downgrade |
| External | Operator-Annotated | Human review and acceptance |

### Forbidden Transitions

| From | To | Why Forbidden |
|------|-----|---------------|
| Derived | Observed | Cannot upgrade authority |
| Predicted | Derived | Model output ≠ measurement |
| Heuristic | Derived | Advisory cannot become measurement |
| Any | Observed | Only sensors produce Observed |

---

## Summary Table

| Status | Meaning | Example | Authority |
|--------|---------|---------|-----------|
| Observed | Directly captured | audio.wav | Record authority |
| Derived | Computed from observed | FFT peaks | Computation authority |
| Estimated | Approximation | SNR estimate | Limited inference |
| Predicted | Model-generated | Toolbox target | External expectation |
| Heuristic | Rule-of-thumb | Advisory hint | Non-authoritative |
| Operator-Annotated | Human note | Builder context | Human judgment |
| Externally-Sourced | Imported data | Material DB | Source-bound |

---

## Consequences

### Positive

- Clear vocabulary for data provenance
- Prevents silent authority inheritance
- Enables future schema metadata
- Supports governance and audit

### Negative

- Classification overhead
- Developers must track epistemic status
- Some existing code may need annotation

---

## Future Work

- Schema fields for epistemic status (not in this ADR)
- Runtime propagation rules (not in this ADR)
- Export validation against status (not in this ADR)

---

## References

- ADR-0010: Guidance Authority Boundary
- ADR-0011: Measurement Authority
- docs/AGE_CONSTITUTIONAL_CONTRACT.md
- docs/MEASUREMENT_BOUNDARY.md
