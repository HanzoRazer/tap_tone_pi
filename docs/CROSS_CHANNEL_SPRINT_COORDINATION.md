# Cross-Channel Sprint Coordination

**Date:** 2026-05-24
**Purpose:** Prevent duplicate work across sprint channels
**Scope:** tap_tone_pi, luthiers-toolbox, CAM-Assist-Blueprint

---

## Executive Summary

All three repositories have completed their local constitutional architecture. Cross-repo vocabulary contracts exist. **No channel should begin runtime integration or IBG unblocking until R1 ratification session.**

| Repository | Local Governance | Platform Contracts | Runtime Integration |
|------------|------------------|-------------------|---------------------|
| tap_tone_pi | **Complete** | **Complete** (source of truth) | Not started |
| luthiers-toolbox | **Complete** | **Complete** (compatibility layer) | Not started |
| CAM-Assist-Blueprint | **Complete** | Aligned | Not started |

---

## Work Completed by Channel

### tap_tone_pi (Source of Truth)

| Item | Status | Commit/PR |
|------|--------|-----------|
| DO-78 AGE Constitutional Contract (7 PRs) | **Done** | `00f82ec`–`3ab85b3` |
| DO-81 Measurement Authority ADRs (4 PRs) | **Done** | `6c3603c`–`42483ba` |
| Phase 0 Language Cleanup | **Done** | `b1b6689` |
| Phase 1 Platform Contracts (4 specs + 4 schemas) | **Done** | `458bda2`–`3ef56d5` |
| Guidance language guard (strict CI) | **Done** | Active |
| Constitutional docs tests (18) | **Done** | Pass |
| Platform contracts tests (40) | **Done** | Pass |

**Authoritative Artifacts:**
- `docs/platform-contracts/authority-v1.md` + schema
- `docs/platform-contracts/confidence-v1.md` + schema
- `docs/platform-contracts/epistemic-status-v1.md` + schema
- `docs/platform-contracts/review-decision-v1.md` + schema
- `docs/ADR-0011-measurement-authority.md`
- `docs/ADR-0012-epistemic-status-taxonomy.md`

### luthiers-toolbox (Compatibility Layer)

| Item | Status | Commit/PR |
|------|--------|-----------|
| Constitutional import (9 files from tap_tone) | **Done** | — |
| Cross-repo governance audit (16+ docs) | **Done** | — |
| ConfidenceEnvelopeV1 (wraps TypedConfidenceV1) | **Done** | `f7d851b3` |
| ProvenanceAttachmentDraft (IBG substrate) | **Done** | `93da8fab` |
| AuthorityMetadata (cross-repo normalization) | **Done** | `93da8fab` |
| Convergence contracts tests (72) | **Done** | Pass |
| candidate_rank → typed confidence migration | **Done** | — |
| Epistemic status schema spec | **Done** | — |

**Authoritative Artifacts:**
- `services/api/app/governance/confidence_envelope.py`
- `services/api/app/governance/provenance_attachment.py`
- `services/api/app/governance/authority_metadata.py`
- `docs/governance/CROSS_REPO_CONFIDENCE_ENVELOPE_V1.md`
- `docs/governance/IBG_PROVENANCE_ATTACHMENT_SPEC.md`

### CAM-Assist-Blueprint (Non-Execution Pipeline)

| Item | Status | Commit/PR |
|------|--------|-----------|
| 13 dev orders (A0–A12) | **Done** | `86a76d7` |
| 12 PRs merged | **Done** | — |
| 11 CLI scripts | **Done** | — |
| 3 JSON schemas | **Done** | — |
| 236 tests | **Done** | Pass |
| Authority model enforced | **Done** | — |
| Non-execution invariant | **Done** | — |

**Authoritative Artifacts:**
- `schemas/strategy.schema.json`
- `schemas/strategy_package_manifest.schema.json`
- `schemas/review_decision_record.schema.json`

---

## Work NOT Done (By Design)

### Blocked on R1 Ratification Session

| Item | Repository | Blocker |
|------|------------|---------|
| IBG BLOCKED_PROVENANCE (5 paths) | luthiers-toolbox | Requires R1 ratification |
| IBG DXF export unblocking | luthiers-toolbox | Requires R1 ratification |
| DXF lifecycle promotion | luthiers-toolbox | Requires provenance wiring |
| ProvenanceAttachmentDraft → production | luthiers-toolbox | Requires R1 ratification |

**IBG Blocked Paths (DO NOT UNBLOCK):**
```
body_contour_solver.py:777   BLOCKED_PROVENANCE
body_contour_solver.py:808   BLOCKED_PROVENANCE
arc_reconstructor.py:1116    BLOCKED_PROVENANCE
arc_reconstructor.py:1279    BLOCKED_PROVENANCE
arc_reconstructor.py:1303    BLOCKED_PROVENANCE
```

### Deferred (Requires Dev Order)

| Item | Repository | Reason |
|------|------------|--------|
| `confidence: float` migration | tap_tone_pi | Awaiting cross-repo consensus |
| Runtime adapters | All | Requires explicit Dev Order |
| Cross-repo CI integration | All | Requires platform coordination |
| Shared schema registry | All | Requires governance session |
| Queue unification (8E + CAM) | luthiers-toolbox | Incompatible semantics |
| Package restructure to `contracts/` | luthiers-toolbox | Noted as pending |

### Explicitly Out of Scope

| Item | Repository | Reason |
|------|------------|--------|
| G-code generation | CAM-Assist | Out of scope |
| luthiers-toolbox API integration | CAM-Assist | Out of scope |
| vectorizer-sandbox modifications | luthiers-toolbox | Separate repo |
| Production semantic consensus | All | Out of scope |

---

## Vocabulary Alignment Status

### Authority Classes (6 values)

| Canonical | tap_tone_pi | luthiers-toolbox | CAM-Assist | Aligned |
|-----------|-------------|------------------|------------|---------|
| measurement | AuthorityClass.MEASUREMENT | LIFECYCLE_GOVERNED | N/A | ✓ |
| provenance | AuthorityClass.PROVENANCE | artifact.provenance | source_spec_id | ✓ |
| decision_support | AuthorityClass.DECISION_SUPPORT | Review UX | Review packet | ✓ |
| interpretive | AuthorityClass.INTERPRETIVE | candidate.prediction | strategy intent | ✓ |
| operator | Operator sovereignty | ReviewDecisionRecord | A12 decision | ✓ |
| external | Externally-Sourced | imported DXF | source_spec_id | ✓ |

### Confidence Domains (6 values)

| Canonical | tap_tone_pi | luthiers-toolbox | Aligned |
|-----------|-------------|------------------|---------|
| signal | ConfidenceDomain.SIGNAL | N/A | ✓ |
| measurement | ConfidenceDomain.MEASUREMENT | ConfidenceEnvelopeV1 | ✓ |
| interpretive | ConfidenceDomain.INTERPRETIVE | ConfidenceEnvelopeV1 | ✓ |
| recommendation | ConfidenceDomain.RECOMMENDATION | advisory confidence | ✓ |
| historical | N/A | provenance confidence | ✓ |
| ranking | N/A | rank_score (wrapped) | ✓ |

### Epistemic Statuses (7 values)

| Canonical | All Repos | Aligned |
|-----------|-----------|---------|
| observed | Implemented | ✓ |
| derived | Implemented | ✓ |
| estimated | Implemented | ✓ |
| predicted | Implemented | ✓ |
| heuristic | Implemented | ✓ |
| operator_annotated | Implemented | ✓ |
| externally_sourced | Implemented | ✓ |

### Review Decision Types (6 values)

| Canonical | tap_tone_pi | luthiers-toolbox | CAM-Assist | Aligned |
|-----------|-------------|------------------|------------|---------|
| acknowledge | QualityVerdict.PENDING | UNDER_REVIEW | queued | ✓ |
| request_more_evidence | N/A | REQUEST_EVIDENCE | needs_info | ✓ |
| defer | N/A | DEFERRED | deferred | ✓ |
| reject | QualityVerdict.FAIL | REJECTED | denied | ✓ |
| mark_reviewed | QualityVerdict.PASS | REVIEWED | reviewed | ✓ |
| approve_for_downstream_review | N/A | APPROVED_DOWNSTREAM | accepted | ✓ |

---

## Test Coverage Summary

| Repository | Governance Tests | Status |
|------------|------------------|--------|
| tap_tone_pi | 119 | Pass |
| luthiers-toolbox | 72 (convergence) + 37 (constitutional) | Pass |
| CAM-Assist-Blueprint | 236 | Pass |

---

## What Each Channel Should NOT Do

### tap_tone_pi Channel

- **DO NOT** migrate `confidence: float` fields yet
- **DO NOT** implement runtime adapters
- **DO NOT** create cross-repo CI until platform coordinates

### luthiers-toolbox Channel

- **DO NOT** unblock IBG BLOCKED_PROVENANCE paths
- **DO NOT** ratify R1 provenance without governance session
- **DO NOT** wire ProvenanceAttachmentDraft to DXF export
- **DO NOT** replace existing ConfidenceDeclaration model
- **DO NOT** replace existing rank_score fields

### CAM-Assist-Blueprint Channel

- **DO NOT** integrate with luthiers-toolbox API
- **DO NOT** unify queue with 8E (incompatible semantics)
- **DO NOT** generate G-code or production artifacts

---

## Next Steps (Cross-Channel)

| Priority | Action | Owner | Blocker |
|----------|--------|-------|---------|
| P0 | Schedule R1 ratification session | Governance | — |
| P0 | Merge luthiers PR #38 | Reviewer | — |
| P1 | Document rank_score vs confidence_value | luthiers | — |
| P2 | Package normalization to `contracts/` | luthiers | D1-D4 decisions |
| P2 | Cross-repo schema validation CI | Platform | R1 complete |
| P3 | Shared adapter libraries | Platform | Dev Order |

---

## Invariants (All Channels Must Enforce)

```
Decision-support authority may route attention but may not establish truth.
No bare confidence in shared contracts — requires domain + value + source.
Predicted cannot become observed. Heuristic cannot become measurement.
Review decisions do not authorize implementation, execution, or machine output.
IBG provenance remains BLOCKED until R1 ratification.
```

---

## Contact / Questions

- **tap_tone_pi state:** See `docs/RECONSTRUCTION_SPRINT_AUDIT.md`
- **luthiers-toolbox state:** See `docs/audits/CROSS_REPO_GOVERNANCE_NORMALIZATION_1A_AUDIT.md`
- **CAM-Assist state:** See luthiers-toolbox `RECONSTRUCTION_SPRINT_AUDIT_2026-05-24.md`

---

*Generated: 2026-05-24*
*Purpose: Cross-channel sprint coordination*
