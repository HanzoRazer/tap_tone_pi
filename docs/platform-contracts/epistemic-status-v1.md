# Epistemic Status Taxonomy (v1)

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository contract for epistemic status classification

---

## Purpose

This document defines the seven epistemic statuses used to classify data artifacts across the acoustic measurement and manufacturing ecosystem. Epistemic status determines what an artifact represents epistemically — its relationship to truth, observation, and inference.

---

## Epistemic Statuses

### Observed

Direct sensor capture with no transformation beyond digitization.

| Property | Value |
|----------|-------|
| Authority class | MEASUREMENT |
| Can become measurement | Already is |
| Requires attribution | Capture metadata |

**Examples:**
- Raw WAV audio capture
- Accelerometer time series
- Temperature sensor reading

### Derived

Computed deterministically from Observed data using documented algorithms.

| Property | Value |
|----------|-------|
| Authority class | MEASUREMENT |
| Can become measurement | Yes |
| Requires attribution | Algorithm + input hash |

**Examples:**
- FFT spectrum
- Transfer function
- Coherence calculation
- Peak extraction

### Estimated

Approximation computed from Observed or Derived data with explicit uncertainty bounds.

| Property | Value |
|----------|-------|
| Authority class | MEASUREMENT |
| Can become measurement | Yes, with bounds |
| Requires attribution | Method + uncertainty |

**Examples:**
- SNR estimate
- Q-factor approximation
- Interpolated values

### Predicted

Model output based on physical theory or statistical inference.

| Property | Value |
|----------|-------|
| Authority class | INTERPRETIVE |
| Can become measurement | No |
| Requires attribution | Model + parameters |

**Examples:**
- Rayleigh-Ritz mode predictions
- FEA simulation output
- Statistical forecast

### Heuristic

Rule-based suggestion without measurement authority.

| Property | Value |
|----------|-------|
| Authority class | DECISION_SUPPORT |
| Can become measurement | No |
| Requires attribution | Rule source |

**Examples:**
- AGE directive
- Wolf candidate highlight
- Quality warning

### Operator-Annotated

Human input recorded as metadata.

| Property | Value |
|----------|-------|
| Authority class | PROVENANCE |
| Can become measurement | No |
| Requires attribution | Operator identity |

**Examples:**
- Session notes
- Build selection
- Quality override reason

### Externally-Sourced

Data imported from external systems with source binding.

| Property | Value |
|----------|-------|
| Authority class | INTERPRETIVE |
| Can become measurement | No |
| Requires attribution | Source citation |

**Examples:**
- Material database lookup
- Calibration certificate
- Third-party target frequency

---

## Transition Rules

### Allowed Transitions

```
Observed → Derived      (algorithm transforms observation)
Derived → Estimated     (uncertainty acknowledged)
Any → Heuristic         (explicit downgrade for advisory)
```

### Forbidden Transitions

```
Predicted → Derived     (model cannot become measurement)
Heuristic → Derived     (advisory cannot become measurement)
Derived → Observed      (cannot upgrade authority)
Externally-Sourced → Observed  (cannot launder external data)
```

---

## Invariants

1. **No silent inheritance.** Epistemic status must be explicit; downstream artifacts cannot silently inherit input status.

2. **Status determines export eligibility.** Only Observed, Derived, and Estimated (with bounds) may enter measurement exports.

3. **Downgrade is always allowed.** Any status may be explicitly downgraded to Heuristic for advisory use.

4. **Upgrade is never allowed.** Lower-authority status cannot become higher-authority status.

---

## Cross-Repository Mapping

| Status | tap_tone_pi | luthiers-toolbox | CAM-Assist |
|--------|-------------|------------------|------------|
| Observed | `EpistemicStatus.OBSERVED` | `artifact.observed` | `source: sensor` |
| Derived | `EpistemicStatus.DERIVED` | `artifact.derived` | `source: computed` |
| Estimated | `EpistemicStatus.ESTIMATED` | `artifact.estimated` | `source: approximation` |
| Predicted | `EpistemicStatus.PREDICTED` | `candidate.prediction` | `source: model` |
| Heuristic | `EpistemicStatus.HEURISTIC` | `advisory.suggestion` | `source: heuristic` |
| Operator-Annotated | `EpistemicStatus.OPERATOR_ANNOTATED` | `note.operator` | `source: human` |
| Externally-Sourced | `EpistemicStatus.EXTERNALLY_SOURCED` | `import.external` | `source: external` |

---

## Non-Goals

This contract does NOT:
- Define specific validation rules
- Prescribe storage format
- Define UI presentation
- Require status on all fields

---

## See Also

- [authority-v1](authority-v1.md)
- [confidence-v1](confidence-v1.md)
- tap_tone_pi: ADR-0011, ADR-0012
- EPISTEMIC_STATUS_MATRIX.md
