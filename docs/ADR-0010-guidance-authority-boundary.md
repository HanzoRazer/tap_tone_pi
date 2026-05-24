# ADR-0010: Guidance Authority Boundary — AGE Constitutional Limits

**Status:** Accepted  
**Date:** 2026-05-23  
**Sprint:** DO-78 (Analyzer Guidance Engine Constitutional Contract)  
**Supersedes:** None  
**References:** ADR-0009 (Advisory Boundary)

---

## Context

ADR-0009 established the two-class instrument system: MEASUREMENT modules produce
calibrated facts; DECISION SUPPORT modules produce interpretations and recommendations.
This boundary prevents advisory output from contaminating the measurement provenance chain.

However, ADR-0009 does not specify **what authority DECISION SUPPORT modules may claim**.
A guidance engine that declares itself DECISION SUPPORT can still:
- Use language implying diagnostic certainty ("wolf tone detected")
- Present recommendations as requirements ("must fix")
- Assign quality scores that imply measurement authority
- Export confidence values without domain context

This ADR establishes the **guidance authority boundary**: what advisory modules may
and may not do, even when operating entirely within the DECISION SUPPORT class.

The core invariant:

```
Guidance may prioritize attention.
Guidance may not establish truth.
```

---

## Decision

### D1: Four Authority Classes

All outputs from `tap_tone_pi` belong to one of four authority classes:

| Authority Class | May Establish Truth? | May Enter Measurement Export? | Examples |
|-----------------|---------------------|------------------------------|----------|
| **MEASUREMENT** | Yes | Yes | FFT peaks, coherence values, transfer functions |
| **PROVENANCE** | Yes (about process) | Yes | Calibration records, environment records, timestamps |
| **DECISION SUPPORT** | No | No | Directives, recommendations, attention guidance |
| **INTERPRETIVE** | No | No | Quality grades, tone assessments, design advice |

DECISION SUPPORT is the class for AGE, WolfAdvisor, and similar modules.
INTERPRETIVE is reserved for future systems that make value judgments (not implemented in TTP).

### D2: Guidance Scope Enumeration

DECISION SUPPORT modules operate within one of these scopes:

| Scope | Allowed Actions | Examples |
|-------|-----------------|----------|
| **ATTENTION_GUIDANCE** | Point, highlight, prioritize, suggest inspection | "Review peak at 247Hz" |
| **EXPLANATION** | Summarize, explain measurement quality issues | "SNR below threshold due to ambient noise" |
| **WORKFLOW_HINT** | Suggest next measurement step | "Consider re-tapping with mic repositioned" |

Guidance modules must declare their scope explicitly.

### D3: Forbidden Guidance Semantics

DECISION SUPPORT modules must NOT:

1. **Establish acoustic truth** — "Wolf tone detected" implies a truth claim. Use "Potential wolf signature observed" instead.
2. **Prescribe design changes** — "Add 2g at bridge" is design advice, not attention guidance.
3. **Assign quality scores** — "Tone quality: 8/10" implies measurement authority.
4. **Use mandatory language** — "Must fix", "Required action" implies authority to compel.
5. **Claim causal diagnosis** — "Cause is insufficient damping" asserts interpretive truth.
6. **Rank tonal quality** — "Better than baseline" implies comparative valuation.

### D4: Confidence Must Be Domain-Typed

Bare confidence values (`confidence: 0.85`) are ambiguous. All confidence values must
declare their domain:

| Domain | Meaning | May Appear In |
|--------|---------|---------------|
| `signal` | Signal detection confidence (SNR-based) | MEASUREMENT artifacts |
| `measurement` | Measurement quality confidence | MEASUREMENT artifacts |
| `interpretive` | Interpretation confidence | DECISION SUPPORT only |
| `recommendation` | Recommendation confidence | DECISION SUPPORT only |

Existing `confidence` fields in directives are implicitly `interpretive` until migrated.

### D5: Authority Metadata Required on Directives

Every `AttentionDirectiveV1` must carry explicit authority metadata:

```python
authority = AdvisoryAuthorityV1(
    authority_class=AuthorityClass.DECISION_SUPPORT,
    authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
    can_establish_truth=False,
    can_modify_measurement=False,
    can_enter_measurement_export=False,
)
```

This makes the directive's limitations machine-readable and auditable.

### D6: UI Must Not Conflate Guidance with Measurement

Guidance surfaces (cards, panels, toasts) must be visually distinct from measurement
results. Specifically:

- Do NOT use PASS/WARN/FAIL badges for guidance
- Do NOT use measurement-result colors (green/yellow/red) for recommendations
- Do NOT use "Result", "Verdict", or "Diagnosis" labels for guidance
- DO use "Guidance", "Advisory", "Review Suggested" labels

---

## Consequences

1. **AGE and WolfAdvisor** must attach `AdvisoryAuthorityV1` to all emitted directives.
2. **Existing confidence fields** remain for backward compatibility; new code should
   use typed confidence.
3. **CI guards** will scan DECISION SUPPORT modules for forbidden language patterns.
4. **Export tests** will verify advisory fields do not appear in measurement artifacts.
5. **UI renderers** must distinguish guidance from measurement in copy and styling.

---

## Enforcement

- `tap_tone_pi/agentic/contracts/advisory_authority.py` — defines authority types
- `tap_tone_pi/agentic/contracts/confidence_domain.py` — defines typed confidence
- `ci/check_guidance_language.py` — scans for forbidden guidance-as-truth language
- `tests/test_guidance_not_in_measurement_exports.py` — verifies export boundary

---

## References

- ADR-0009: Advisory Boundary — Measurement vs Decision Support Instrument Classes
- docs/AGE_CONSTITUTIONAL_CONTRACT.md — Capability matrix for guidance systems
- docs/MEASUREMENT_BOUNDARY.md — Canonical measurement scope statement
