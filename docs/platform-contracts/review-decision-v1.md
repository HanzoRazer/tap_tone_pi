# Review Decision Semantics (v1)

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository contract for review decision states

---

## Purpose

This document defines the review decision semantics used across the acoustic measurement and manufacturing ecosystem. Review decisions record human process — they do not automatically authorize implementation, execution, or machine output.

---

## Core Invariant

```
Review decisions record human process.
They do not automatically authorize implementation, execution, or machine output.
```

---

## Decision Types

Decision types represent the action a reviewer takes:

### acknowledge

Reviewer has seen the artifact and recorded awareness.

| Property | Value |
|----------|-------|
| Records review | Yes |
| Authorizes implementation | No |
| Authorizes execution | No |

### request_more_evidence

Reviewer requests additional information before proceeding.

| Property | Value |
|----------|-------|
| Records review | Yes |
| Authorizes implementation | No |
| Authorizes execution | No |

### defer

Reviewer defers decision to another reviewer or future review.

| Property | Value |
|----------|-------|
| Records review | Yes |
| Authorizes implementation | No |
| Authorizes execution | No |

### reject

Reviewer rejects the artifact for this review cycle.

| Property | Value |
|----------|-------|
| Records review | Yes |
| Authorizes implementation | No |
| Authorizes execution | No |

### mark_reviewed

Reviewer marks artifact as having completed review.

| Property | Value |
|----------|-------|
| Records review | Yes |
| Authorizes implementation | No |
| Authorizes execution | No |

### approve_for_downstream_review

Reviewer approves artifact to proceed to downstream review (not execution).

| Property | Value |
|----------|-------|
| Records review | Yes |
| Authorizes implementation | No |
| Authorizes execution | No |

---

## Resulting Status

After a decision, the artifact enters a pipeline status:

| Status | Description |
|--------|-------------|
| pending | Awaiting review decision |
| under_review | Currently being reviewed |
| needs_evidence | Blocked pending additional evidence |
| deferred | Deferred to another reviewer or time |
| rejected | Rejected, may be resubmitted |
| reviewed | Review complete, no further action in this gate |
| approved_downstream | Approved to proceed to downstream review |

---

## Decision Effects Table

| Decision Type | Records Review | Authorizes Implementation | Authorizes Execution | Resulting Status |
|---------------|:--------------:|:-------------------------:|:--------------------:|------------------|
| acknowledge | Yes | No | No | under_review |
| request_more_evidence | Yes | No | No | needs_evidence |
| defer | Yes | No | No | deferred |
| reject | Yes | No | No | rejected |
| mark_reviewed | Yes | No | No | reviewed |
| approve_for_downstream_review | Yes | No | No | approved_downstream |

---

## Invariants

1. **Review ≠ authorization.** Review approval does not grant measurement authority, establish truth, or upgrade epistemic status.

2. **Review ≠ validation.** Review approval means "may proceed through gate", not "is correct" or "is good".

3. **No execution authority.** No review decision authorizes machine execution. Execution requires separate, explicit authorization.

4. **No implementation authority.** No review decision authorizes implementation. Implementation requires separate process.

5. **Decision is scoped.** A decision applies to a specific artifact version at a specific gate.

6. **Modification invalidates.** Any modification to an approved artifact requires re-review.

---

## Typed Decision Structure

```json
{
  "decision_type": "mark_reviewed",
  "resulting_status": "reviewed",
  "human_review_recorded": true,
  "implementation_authorized": false,
  "execution_authorized": false,
  "machine_output_allowed": false,
  "reviewer_ref": "operator@example.com",
  "source_repo": "luthiers-toolbox",
  "local_decision_type": "ReviewDecisionRecord.REVIEWED"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| decision_type | string | Yes | The reviewer action taken |
| resulting_status | string | No | The pipeline status after this decision |
| human_review_recorded | boolean | Yes | Always true for valid decisions |
| implementation_authorized | boolean | Yes | Always false |
| execution_authorized | boolean | Yes | Always false |
| machine_output_allowed | boolean | Yes | Always false |
| reviewer_ref | string | No | Reviewer identifier |
| source_repo | string | No | Repository that recorded this decision |
| local_decision_type | string | No | Repository-local decision type for mapping |

---

## Cross-Repository Mapping

| Canonical Decision | tap_tone_pi | luthiers-toolbox | CAM-Assist |
|--------------------|-------------|------------------|------------|
| acknowledge | QualityVerdict.PENDING | UNDER_REVIEW | queued |
| request_more_evidence | N/A | REQUEST_EVIDENCE | needs_info |
| defer | N/A | DEFERRED | deferred |
| reject | QualityVerdict.FAIL | REJECTED | denied |
| mark_reviewed | QualityVerdict.PASS | REVIEWED | reviewed |
| approve_for_downstream_review | N/A | APPROVED_DOWNSTREAM | accepted |

---

## Integration Considerations

When artifacts cross repository boundaries:

1. **Map to common vocabulary.** Use this contract's decision types in cross-repo APIs.

2. **Preserve decision metadata.** Include original repository's decision record.

3. **Re-review at boundary.** Receiving repository may require its own review.

4. **No execution leakage.** Even approved_downstream does not authorize execution in receiving repo.

---

## Non-Goals

This contract does NOT:
- Authorize execution (that requires explicit Dev Order)
- Authorize implementation
- Allow machine output based on review alone
- Define specific review criteria
- Prescribe reviewer assignment
- Merge review systems automatically

---

## See Also

- [authority-v1](authority-v1.md)
- [confidence-v1](confidence-v1.md)
- [epistemic-status-v1](epistemic-status-v1.md)
- luthiers-toolbox: GOVERNANCE_RUNNER.md, 8E Queue
- CAM-Assist: Review Queue
