# Review Decision Semantics (v1)

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository contract for review decision states

---

## Purpose

This document defines the review decision states and their semantics across the acoustic measurement and manufacturing ecosystem. Review decisions determine whether artifacts may proceed through governance gates.

---

## Problem Statement

Parallel review queue implementations across repositories use incompatible terminology:

| Repository | Approved | Rejected | Pending |
|------------|----------|----------|---------|
| tap_tone_pi | N/A | N/A | N/A |
| luthiers-toolbox | `APPROVED` | `REJECTED` | `UNDER_REVIEW` |
| CAM-Assist | `accepted` | `denied` | `queued` |

This creates integration risk when artifacts cross repository boundaries.

---

## Review Decision States

### PENDING

Artifact has entered review queue but has not received a decision.

| Property | Value |
|----------|-------|
| May proceed | No |
| May be modified | Yes |
| May be withdrawn | Yes |
| Timeout behavior | Implementation-defined |

### APPROVED

Artifact has received positive review decision and may proceed.

| Property | Value |
|----------|-------|
| May proceed | Yes |
| May be modified | No (requires re-review) |
| May be withdrawn | Yes |
| Authority granted | None (approval ≠ authority) |

### REJECTED

Artifact has received negative review decision and may not proceed.

| Property | Value |
|----------|-------|
| May proceed | No |
| May be modified | Yes (for resubmission) |
| May be withdrawn | Yes |
| Feedback required | Implementation-defined |

### BLOCKED

Artifact is blocked from review for structural reasons (missing provenance, invalid authority).

| Property | Value |
|----------|-------|
| May proceed | No |
| May be modified | Yes |
| May be withdrawn | Yes |
| Unblock path | Resolve blocking condition |

---

## Invariants

1. **Approval ≠ authority.** Review approval does not grant measurement authority, establish truth, or upgrade epistemic status.

2. **Approval ≠ validation.** Review approval means "may proceed through gate", not "is correct" or "is good".

3. **Decision is binding for scope.** A decision applies to a specific artifact version at a specific gate.

4. **Modification invalidates approval.** Any modification to an approved artifact requires re-review.

5. **Blocked is not rejection.** BLOCKED indicates structural deficiency; REJECTED indicates review decision.

---

## Decision Metadata

```json
{
  "review_decision": {
    "state": "APPROVED",
    "reviewer": "operator@example.com",
    "timestamp": "2024-01-15T10:30:00Z",
    "gate": "export_legitimacy",
    "artifact_version": "abc123",
    "notes": "Optional reviewer notes"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| state | string | Yes | One of: PENDING, APPROVED, REJECTED, BLOCKED |
| reviewer | string | Conditional | Required for APPROVED/REJECTED |
| timestamp | ISO 8601 | Yes | Decision timestamp |
| gate | string | Yes | Gate identifier |
| artifact_version | string | Yes | Artifact hash or version |
| notes | string | No | Reviewer notes |

---

## Gate Types

Review decisions are scoped to specific gates:

| Gate | Description | Typical Scope |
|------|-------------|---------------|
| `export_legitimacy` | May artifact be exported | luthiers-toolbox |
| `measurement_validity` | Is measurement acceptable | tap_tone_pi |
| `production_release` | May artifact enter production | CAM-Assist |
| `archive_inclusion` | May artifact be archived | All |

---

## Cross-Repository Mapping

| State | tap_tone_pi | luthiers-toolbox | CAM-Assist |
|-------|-------------|------------------|------------|
| PENDING | `QualityVerdict.PENDING` | `UNDER_REVIEW` | `queued` |
| APPROVED | `QualityVerdict.PASS` | `APPROVED` | `accepted` |
| REJECTED | `QualityVerdict.FAIL` | `REJECTED` | `denied` |
| BLOCKED | N/A | `BLOCKED_PROVENANCE` | `blocked` |

---

## Integration Considerations

When artifacts cross repository boundaries:

1. **Map to common vocabulary.** Use this contract's state names in cross-repo APIs.

2. **Preserve decision metadata.** Include original repository's decision record.

3. **Re-review at boundary.** Receiving repository may require its own review.

4. **Respect blocked state.** BLOCKED artifacts should not be submitted to downstream review.

---

## Non-Goals

This contract does NOT:
- Define specific review criteria
- Prescribe reviewer assignment
- Define review UI
- Require review for all artifacts

---

## See Also

- [authority-v1](authority-v1.md)
- luthiers-toolbox: GOVERNANCE_RUNNER.md, 8E Queue
- CAM-Assist: Review Queue
