# Confidence Domains (v1)

**Version:** 1.0.0
**Status:** Draft
**Scope:** Cross-repository contract for typed confidence values

---

## Purpose

This document defines the confidence domain taxonomy used across the acoustic measurement and manufacturing ecosystem. Confidence values without domain context are ambiguous — a 0.85 signal confidence is fundamentally different from a 0.85 recommendation confidence.

---

## Core Rules

- No bare confidence in new shared contracts
- Confidence requires domain + value + source
- Rank score is not approval
- Advisory confidence is not measurement confidence

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

### signal

Confidence derived from signal processing metrics (SNR, coherence, peak prominence).

| Property | Value |
|----------|-------|
| Authority class | measurement |
| Source | DSP algorithms |
| Interpretation | Signal quality metric |
| May imply approval | No |

**Examples:**
- Peak detection confidence
- Coherence-weighted reliability
- SNR-derived certainty

### measurement

Confidence in a complete measurement result (combination of capture quality, repeatability, calibration state).

| Property | Value |
|----------|-------|
| Authority class | measurement |
| Source | Quality check pipeline |
| Interpretation | Measurement validity metric |
| May imply approval | No |

**Examples:**
- Quality gate confidence
- Repeatability score
- Calibration validity

### interpretive

Confidence in an interpretation or classification (pattern matching, anomaly detection).

| Property | Value |
|----------|-------|
| Authority class | decision_support |
| Source | Advisory algorithms |
| Interpretation | Classification certainty |
| May imply approval | No |

**Examples:**
- Wolf tone candidate confidence
- Mode shape classification confidence
- Anomaly detection score

### recommendation

Confidence in an advisory recommendation (priority, attention routing).

| Property | Value |
|----------|-------|
| Authority class | decision_support |
| Source | Guidance engines |
| Interpretation | Suggestion strength |
| May imply approval | No |

**Examples:**
- Review priority score
- Attention routing weight
- Suggested action confidence

### historical

Confidence in historical or provenance data (reconstruction accuracy, timeline consistency).

| Property | Value |
|----------|-------|
| Authority class | provenance |
| Source | Provenance systems |
| Interpretation | Historical reliability |
| May imply approval | No |

**Examples:**
- Timeline reconstruction confidence
- Provenance chain integrity
- Historical match certainty

### ranking

Confidence used for ordering or prioritization without authority claims.

| Property | Value |
|----------|-------|
| Authority class | decision_support |
| Source | Ranking algorithms |
| Interpretation | Relative ordering metric |
| May imply approval | No |

**Examples:**
- Review queue rank_score
- Candidate priority score
- Attention ordering weight

---

## Invariants

1. **Domain is mandatory.** Confidence values without explicit domain are invalid in shared contracts.

2. **Domain determines authority ceiling.** `interpretive` and `recommendation` confidence cannot claim `measurement` authority.

3. **Confidence ≠ approval.** No confidence value, regardless of domain or magnitude, implies approval or validation.

4. **Cross-domain comparison is invalid.** A 0.95 `signal` confidence is not "better" than a 0.80 `measurement` confidence.

5. **Ranking is not approval.** High `ranking` confidence does not authorize execution or bypass review.

---

## Typed Confidence Structure

```json
{
  "domain": "interpretive",
  "value": 0.85,
  "source": "wolf_beat_model",
  "does_not_imply": ["approval", "execution_authority"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| domain | string | Yes | One of: signal, measurement, interpretive, recommendation, historical, ranking |
| value | float | Yes | Confidence value in [0.0, 1.0] |
| source | string | Yes | Algorithm or process that produced the value |
| does_not_imply | array | No | Explicit list of things this confidence does not imply |

---

## does_not_imply Values

| Value | Meaning |
|-------|---------|
| correctness | This confidence does not imply the result is correct |
| approval | This confidence does not imply approval or validation |
| execution_authority | This confidence does not authorize machine execution |
| review_bypass | This confidence does not bypass human review |
| measurement_truth | This confidence does not establish measurement truth |

---

## Migration Path

Existing bare `confidence: float` fields should be migrated to typed confidence:

```python
# Before (ambiguous)
{"confidence": 0.85}

# After (explicit domain)
{"domain": "interpretive", "value": 0.85, "source": "wolf_detector"}
```

During migration, bare `confidence` fields should be treated as `interpretive` domain by default (most conservative interpretation).

---

## Cross-Repository Mapping

| Canonical | tap_tone_pi | luthiers-toolbox | CAM-Assist |
|-----------|-------------|------------------|------------|
| signal | ConfidenceDomain.SIGNAL | N/A | N/A |
| measurement | ConfidenceDomain.MEASUREMENT | DxfLifecycle confidence (if ratified) | N/A |
| interpretive | ConfidenceDomain.INTERPRETIVE | ConfidenceType.HEURISTIC/EPISTEMIC | review prose only |
| recommendation | ConfidenceDomain.RECOMMENDATION | advisory confidence | N/A |
| historical | N/A | provenance confidence | N/A |
| ranking | N/A | rank_score | N/A |

---

## Non-Goals

This contract does NOT:
- Define specific confidence thresholds
- Prescribe confidence calculation algorithms
- Define UI presentation of confidence
- Require confidence on all artifacts
- Imply that high confidence means approval

---

## See Also

- [authority-v1](authority-v1.md)
- [epistemic-status-v1](epistemic-status-v1.md)
- tap_tone_pi: ADR-0012, TypedConfidenceV1
