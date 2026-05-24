# AGE Constitutional Contract

**Version:** 1.0.0  
**Effective:** 2026-05-23  
**Authority:** ADR-0010 (Guidance Authority Boundary)

---

## Purpose

This document defines what the Analyzer Guidance Engine (AGE) and related advisory
systems may and may not do. It is a constitutional boundary, not a feature specification.

The core principle:

```
Guidance may route attention to evidence.
Guidance may not become evidence.
```

---

## Capability Matrix

| Capability | Allowed | Notes |
|------------|:-------:|-------|
| Highlight a suspicious spectral region | Yes | Attention guidance |
| Suggest reviewing a specific signal | Yes | Non-binding |
| Summarize measurement quality issues | Yes | Explanation scope |
| Explain why SNR is below threshold | Yes | Educational |
| Point to a potential wolf signature | Yes | "Potential", not "detected" |
| Recommend next measurement step | Yes | Workflow hint |
| State "wolf tone detected" | **No** | Interpretive truth claim |
| Recommend brace design changes | **No** | Design advice |
| Suggest "add 2g at bridge" | **No** | Prescriptive action |
| Assign acoustic quality score | **No** | Interpretation/valuation |
| Rank instruments by "tone quality" | **No** | Comparative valuation |
| Change measurement parameters | **No** | M2/actuation forbidden |
| Export directive as measurement fact | **No** | Provenance contamination |
| Use PASS/WARN/FAIL for guidance | **No** | Conflates with measurement |
| Claim causal diagnosis | **No** | Asserts interpretive truth |

---

## Allowed Language

Guidance copy should use:

| Use This | Not This |
|----------|----------|
| "Inspect" | "Diagnose" |
| "Review" | "Fix" |
| "Compare" | "Optimal" |
| "Consider checking" | "Must check" |
| "Potential signature" | "Detected" |
| "Observed pattern" | "Confirmed cause" |
| "Suggested" | "Required" |
| "May indicate" | "Proves" |

---

## Forbidden Phrases

The following phrases must NOT appear in DECISION SUPPORT module output:

- "detected as truth"
- "must fix"
- "optimal"
- "best correction"
- "cause is"
- "required action"
- "approved"
- "validated acoustic quality"
- "tone quality score"
- "instrument grade"

These may appear only in:
- Documentation explaining what to avoid
- Tests explicitly verifying rejection
- Files marked with `# EXEMPT: guidance_language_guard`

---

## Authority Metadata

Every directive emitted by AGE or WolfAdvisor must include:

```json
{
  "authority": {
    "authority_class": "decision_support",
    "authority_scope": "attention_guidance",
    "can_establish_truth": false,
    "can_modify_measurement": false,
    "can_enter_measurement_export": false
  }
}
```

This is machine-readable, auditable, and blocks accidental authority escalation.

---

## Confidence Domain

Confidence values in guidance must be explicitly typed:

```python
TypedConfidenceV1(
    value=0.85,
    domain=ConfidenceDomain.INTERPRETIVE,
    source="wolf_beat_model"
)
```

Guidance modules may only emit:
- `interpretive` confidence
- `recommendation` confidence

They may NOT emit:
- `signal` confidence (reserved for MEASUREMENT)
- `measurement` confidence (reserved for MEASUREMENT)

---

## UI Boundary

Guidance must be visually distinct from measurement results:

### Measurement Block Headings
- Measurement
- Quality Check
- Calibration
- Repeatability

### Guidance Block Headings
- Guidance
- Advisory
- Review Suggested
- Attention

### Forbidden Guidance Headings
- Result
- Verdict
- Diagnosis
- Failure

---

## Export Boundary

Advisory output may appear in:
- `meta/session_timeline_v1.json`
- `agentic/advisory_history.json`
- UI display surfaces

Advisory output must NOT appear in:
- `analysis.json`
- `quality_check.json` (as measurement rules)
- `manifest.json` canonical artifact entries
- Any file in `viewer_pack_v1` that carries measurement authority

---

## Enforcement

| Mechanism | File | Mode |
|-----------|------|------|
| Language guard | `ci/check_guidance_language.py` | `--strict` in CI |
| Export boundary test | `tests/test_guidance_not_in_measurement_exports.py` | pytest |
| Authority metadata check | `tests/test_agentic_contracts.py` | pytest |
| UI copy guard | `tests/test_agent_render.py` | pytest |

---

## Violations

If AGE or any advisory module violates this contract:

1. The guidance output is invalid and must not be displayed
2. CI should block the merge (if `--strict` mode)
3. The violation must be logged for governance audit
4. The module author must remediate before release

---

## Rationale

This contract exists because:

1. **Users conflate guidance with measurement.** If AGE says "wolf tone detected",
   users treat it as a measurement fact, not a hypothesis.

2. **Downstream systems inherit authority.** If a directive enters `viewer_pack_v1`,
   the ToolBox inverse brace engine may treat it as calibrated input.

3. **Language shapes trust.** "Must fix" implies AGE has authority to compel action.
   It does not. It can only suggest inspection.

4. **Confidence without domain is meaningless.** A confidence of 0.85 for a measurement
   is very different from 0.85 for a recommendation.

The goal is not to make AGE less useful. It is to make AGE safer by ensuring its
outputs are clearly labelled as advisory, not diagnostic.

---

## Epistemic Status Constraints (DO-81)

AGE may consume the following epistemic statuses as input:

| Status | May Consume | May Convert to Truth |
|--------|-------------|---------------------|
| Observed | Yes | No |
| Derived | Yes | No |
| Estimated | Yes | No |
| Operator-Annotated | Yes | No |
| Externally-Sourced | Yes | No |
| Predicted | As context only | No |
| Heuristic | N/A (this is AGE output) | No |

AGE outputs are always classified as:
- **Epistemic Status:** Heuristic
- **Authority Class:** DECISION SUPPORT

AGE may NOT:
- Convert Observed data into acoustic truth claims
- Convert Derived data into quality verdicts
- Convert Predicted data into measurement facts
- Claim any epistemic status other than Heuristic for its outputs

See ADR-0011 (Measurement Authority) and ADR-0012 (Epistemic Status Taxonomy) for
complete definitions.

---

## References

- ADR-0009: Advisory Boundary
- ADR-0010: Guidance Authority Boundary
- ADR-0011: Measurement Authority
- ADR-0012: Epistemic Status Taxonomy
- docs/MEASUREMENT_BOUNDARY.md
- docs/EPISTEMIC_STATUS_MATRIX.md
