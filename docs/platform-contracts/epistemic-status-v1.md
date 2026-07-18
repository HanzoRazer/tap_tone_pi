# Epistemic Status Taxonomy (v1)

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository contract for epistemic status classification

---

## Purpose

This document defines the seven epistemic statuses used to classify data artifacts across the acoustic measurement and manufacturing ecosystem. Epistemic status determines what an artifact represents epistemically — its relationship to truth, observation, and inference.

---

## Core Rules

```
Predicted cannot become observed.
Heuristic cannot become measurement.
Derived cannot upgrade to observed.
Any downgrade to heuristic must be explicit.
```

---

## Epistemic Statuses

### observed

Direct sensor capture with no transformation beyond digitization.

| Property | Value |
|----------|-------|
| Authority class | measurement |
| May enter measurement export | Yes |
| Requires attribution | Capture metadata |

**Examples:**
- Raw WAV audio capture
- Accelerometer time series
- Temperature sensor reading

### derived

Computed deterministically from observed data using documented algorithms.

| Property | Value |
|----------|-------|
| Authority class | measurement |
| May enter measurement export | Yes |
| Requires attribution | Algorithm + input hash |

**Examples:**
- FFT spectrum
- Transfer function
- Coherence calculation
- Peak extraction

### estimated

Approximation computed from observed or derived data with explicit uncertainty bounds.

| Property | Value |
|----------|-------|
| Authority class | measurement |
| May enter measurement export | Yes, with bounds |
| Requires attribution | Method + uncertainty |

**Examples:**
- SNR estimate
- Q-factor approximation
- Interpolated values

### predicted

Model output based on physical theory or statistical inference.

| Property | Value |
|----------|-------|
| Authority class | interpretive |
| May enter measurement export | No |
| Requires attribution | Model + parameters |

**Examples:**
- Rayleigh-Ritz mode predictions
- FEA simulation output
- Statistical forecast

### heuristic

Rule-based suggestion without measurement authority.

| Property | Value |
|----------|-------|
| Authority class | decision_support |
| May enter measurement export | No |
| Requires attribution | Rule source |

**Examples:**
- AGE directive
- Wolf candidate highlight
- Quality warning

### operator_annotated

Human input recorded as metadata.

| Property | Value |
|----------|-------|
| Authority class | operator |
| May enter measurement export | As annotation only |
| Requires attribution | Operator identity |

**Examples:**
- Session notes
- Build selection
- Quality override reason

### externally_sourced

Data imported from external systems with source binding.

| Property | Value |
|----------|-------|
| Authority class | external |
| May enter measurement export | With source citation |
| Requires attribution | Source citation |

**Examples:**
- Material database lookup
- Calibration certificate
- Third-party target frequency

---

## Transition Rules

### Allowed Transitions

```
observed → derived      (algorithm transforms observation)
derived → estimated     (uncertainty acknowledged)
Any → heuristic         (explicit downgrade for advisory)
```

### Forbidden Transitions

```
predicted → derived     (model cannot become measurement)
predicted → observed    (model cannot become observation)
heuristic → derived     (advisory cannot become measurement)
heuristic → observed    (advisory cannot become observation)
derived → observed      (cannot upgrade authority)
externally_sourced → observed  (cannot launder external data)
```

---

## Invariants

1. **No silent inheritance.** Epistemic status must be explicit; downstream artifacts cannot silently inherit input status.

2. **Status determines export eligibility.** Only `observed`, `derived`, and `estimated` (with bounds) may enter measurement exports.

3. **Downgrade is always allowed.** Any status may be explicitly downgraded to `heuristic` for advisory use.

4. **Upgrade is never allowed.** Lower-authority status cannot become higher-authority status.

5. **Prediction laundering forbidden.** `predicted` data cannot be converted to `observed` or `derived` through any path.

---

## Typed Status Structure

```json
{
  "status": "derived",
  "source": "fft_peak_extractor",
  "may_enter_measurement_export": true,
  "authority_notes": "Computed from observed WAV capture",
  "prohibited_transitions": ["observed"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| status | string | Yes | One of the seven epistemic statuses |
| source | string | Yes | Algorithm, operator, or system that produced the artifact |
| may_enter_measurement_export | boolean | Yes | Whether this artifact may enter measurement exports |
| authority_notes | string | No | Additional context about authority |
| prohibited_transitions | array | No | Statuses this artifact may not transition to |

---

## Cross-Repository Mapping

| Canonical | tap_tone_pi | luthiers-toolbox | CAM-Assist |
|-----------|-------------|------------------|------------|
| observed | EpistemicStatus.OBSERVED | governed capture / lifecycle-complete artifact | external source only |
| derived | EpistemicStatus.DERIVED | guarded DXF / computed geometry | derived strategy geometry |
| estimated | EpistemicStatus.ESTIMATED | approximation with bounds | N/A |
| predicted | EpistemicStatus.PREDICTED | IBG/vectorizer candidates | strategy intent |
| heuristic | EpistemicStatus.HEURISTIC | rank_score / review routing | advisory package text |
| operator_annotated | EpistemicStatus.OPERATOR_ANNOTATED | ReviewDecisionRecord | A12 decision record |
| externally_sourced | EpistemicStatus.EXTERNALLY_SOURCED | imported DXF | source_spec_id |

---

## Non-Goals

This contract does NOT:
- Define specific validation rules
- Prescribe storage format
- Define UI presentation
- Require status on all fields
- Allow status upgrades

---

## See Also

- [authority-v1](authority-v1.md)
- [confidence-v1](confidence-v1.md)
- [review-decision-v1](review-decision-v1.md)
- tap_tone_pi: ADR-0011, ADR-0012
- EPISTEMIC_STATUS_MATRIX.md
