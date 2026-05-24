# Confidence Domains (v1)

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository contract for typed confidence values

---

## Purpose

This document defines the confidence domain taxonomy used across the acoustic measurement and manufacturing ecosystem. Confidence values without domain context are ambiguous — a 0.85 signal confidence is fundamentally different from a 0.85 recommendation confidence.

---

## Problem Statement

Bare `confidence: float` fields create authority inheritance risk:

```python
# Ambiguous — does this mean signal quality or recommendation strength?
{
  "wolf_candidate": {
    "frequency": 220.5,
    "confidence": 0.85
  }
}
```

Without domain context, downstream systems may interpret advisory confidence as measurement confidence, violating authority boundaries.

---

## Confidence Domains

### SIGNAL

Confidence derived from signal processing metrics (SNR, coherence, peak prominence).

| Property | Value |
|----------|-------|
| Authority class | MEASUREMENT |
| Source | DSP algorithms |
| Interpretation | Signal quality metric |
| May imply approval | No |

**Examples:**
- Peak detection confidence
- Coherence-weighted reliability
- SNR-derived certainty

### MEASUREMENT

Confidence in a complete measurement result (combination of capture quality, repeatability, calibration state).

| Property | Value |
|----------|-------|
| Authority class | MEASUREMENT |
| Source | Quality check pipeline |
| Interpretation | Measurement validity metric |
| May imply approval | No |

**Examples:**
- Quality gate confidence
- Repeatability score
- Calibration validity

### INTERPRETIVE

Confidence in an interpretation or classification (pattern matching, anomaly detection).

| Property | Value |
|----------|-------|
| Authority class | DECISION_SUPPORT |
| Source | Advisory algorithms |
| Interpretation | Classification certainty |
| May imply approval | No |

**Examples:**
- Wolf tone candidate confidence
- Mode shape classification confidence
- Anomaly detection score

### RECOMMENDATION

Confidence in an advisory recommendation (priority, attention routing).

| Property | Value |
|----------|-------|
| Authority class | DECISION_SUPPORT |
| Source | Guidance engines |
| Interpretation | Suggestion strength |
| May imply approval | No |

**Examples:**
- Review priority score
- Attention routing weight
- Suggested action confidence

---

## Invariants

1. **Domain is mandatory.** Confidence values without explicit domain are invalid.

2. **Domain determines authority ceiling.** INTERPRETIVE and RECOMMENDATION confidence cannot claim MEASUREMENT authority.

3. **Confidence ≠ approval.** No confidence value, regardless of domain or magnitude, implies approval or validation.

4. **Cross-domain comparison is invalid.** A 0.95 SIGNAL confidence is not "better" than a 0.80 MEASUREMENT confidence.

---

## Typed Confidence Structure

```json
{
  "typed_confidence": {
    "value": 0.85,
    "domain": "INTERPRETIVE",
    "source": "wolf_beat_model"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| value | float | Yes | Confidence value in [0.0, 1.0] |
| domain | string | Yes | One of: SIGNAL, MEASUREMENT, INTERPRETIVE, RECOMMENDATION |
| source | string | No | Algorithm or process that produced the value |

---

## Migration Path

Existing bare `confidence: float` fields should be migrated to typed confidence:

```python
# Before (ambiguous)
{"confidence": 0.85}

# After (explicit domain)
{"typed_confidence": {"value": 0.85, "domain": "INTERPRETIVE", "source": "wolf_detector"}}
```

During migration, bare `confidence` fields should be treated as INTERPRETIVE domain by default (most conservative interpretation).

---

## Cross-Repository Mapping

| Repository | Implementation |
|------------|----------------|
| tap_tone_pi | `TypedConfidenceV1` in `agentic/contracts/confidence_domain.py` |
| luthiers-toolbox | `ConfidenceDeclaration` (proposed) |
| CAM-Assist-Blueprint | `rank_score` + `confidence_domain` (proposed) |

---

## Non-Goals

This contract does NOT:
- Define specific confidence thresholds
- Prescribe confidence calculation algorithms
- Define UI presentation of confidence
- Require confidence on all artifacts

---

## See Also

- [authority-v1](authority-v1.md)
- [epistemic-status-v1](epistemic-status-v1.md)
- tap_tone_pi: ADR-0012, TypedConfidenceV1
