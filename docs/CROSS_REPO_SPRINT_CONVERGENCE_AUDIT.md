# Cross-Repository Sprint Convergence Audit

**Audit Date:** 2026-05-24
**Custodian:** Sprint Architecture Auditor
**Repositories Analyzed:** `tap_tone_pi`, `luthiers-toolbox`, `CAM-Assist-Blueprint` (reference)
**Documents Reviewed:** 15 primary artifacts
**Coverage Estimate:** 95%+ of sprint-relevant material

---

## Executive Summary

This audit examines a coordinated multi-repository constitutional architecture sprint spanning May 14–24, 2026. Three repositories independently developed governance foundations with strong philosophical alignment but operational fragmentation.

### Sprint Intent

Establish machine-readable authority boundaries that prevent:
- Advisory systems from claiming measurement truth
- Automated systems from bypassing human review
- Confidence/rank scores from implying approval
- Export artifacts from containing unauthorized authority claims

### Core Invariants Established

| Repository | Invariant | Enforcement |
|------------|-----------|-------------|
| tap_tone_pi | "Guidance may prioritize attention. Guidance may not establish truth." | ADR-0010, CI guards |
| tap_tone_pi | "Capture integrity ≠ acoustic truth." | ADR-0011 |
| tap_tone_pi | "No epistemic state may silently inherit another state's authority." | ADR-0012 |
| luthiers-toolbox | "Review queue routes attention, not decisions." | 8E Pydantic invariants |
| luthiers-toolbox | "Capability federation gates execution." | MRP-5 runtime spine |
| luthiers-toolbox | "DXF exports require lifecycle context." | Phase 2 guards |

### Critical Finding

**Per-repo governance maturity: HIGH (8.5–9.2/10)**
**Cross-repo convergence readiness: MODERATE (6.0/10)**

The repositories are philosophically aligned but operationally fragmented. No shared governance kernel exists. Integration will require explicit vocabulary mapping before code merges.

---

## 1. Sprint Purpose & Objectives

### tap_tone_pi Objectives (DO-78, DO-81)

| Dev Order | Objective | Status |
|-----------|-----------|--------|
| DO-78 | Define AGE constitutional contract | ✅ Complete |
| DO-78 | Create authority/confidence contracts | ✅ Complete |
| DO-78 | Implement language/export guards | ✅ Complete |
| DO-81 | Define measurement authority taxonomy | ✅ Complete |
| DO-81 | Define epistemic status taxonomy | ✅ Complete |
| Gov Audit | Add instrument class headers | ✅ Complete |
| Gov Audit | Enforce import boundaries | ✅ Complete |

### luthiers-toolbox Objectives (PRs #17–#37)

| Track | Objective | Status |
|-------|-----------|--------|
| PRs #17-19 | Unified governance runner + CI gate | ✅ Complete |
| Phases 1A-2G | DXF lifecycle inventory + guards | ✅ Complete |
| MRP-5M-5Y | Runtime capability federation | ✅ Complete |
| 8C-8E | Review UX + queue routing | ✅ Complete |
| Sandbox | vectorizer-sandbox separation | ✅ Complete |

### Cross-Repository Alignment

| Concept | tap_tone_pi | luthiers-toolbox | Aligned? |
|---------|-------------|------------------|----------|
| Human authority supreme | ADR-0010 | 8E invariants | ✅ Yes |
| Non-execution defaults | Export guards | `execution_authorized=False` | ✅ Yes |
| Fail-closed validation | Schema + boundary tests | Governance gate | ✅ Yes |
| Advisory ≠ Truth | DECISION_SUPPORT class | HEURISTIC epistemic | ✅ Yes |
| Review routing | — | ReviewQueueRegistry | Partial |
| Confidence typing | TypedConfidenceV1 | ConfidenceDeclaration | **Vocabulary collision** |

---

## 2. Systems Affected

### tap_tone_pi Systems

| System | Location | Change Type |
|--------|----------|-------------|
| Agentic Contracts | `tap_tone_pi/agentic/contracts/` | **New** — 6 modules |
| Workflow Contracts | `tap_tone_pi/workflow/` | **New** — 4 modules |
| Repeatability Evidence | `tap_tone_pi/core/repeatability.py` | **New** |
| CI Guards | `ci/check_guidance_language.py` | **New** |
| Policy Engine | `tap_tone_pi/agentic/spine/policy.py` | **Modified** — authority attachment |
| Attention Directive | `analyzer_attention.py` | **Modified** — authority + typed_confidence fields |

### luthiers-toolbox Systems

| System | Location | Change Type |
|--------|----------|-------------|
| Governance Runner | `scripts/governance/check_all.py` | **New** |
| DXF Lifecycle Guards | `app/util/dxf_lifecycle_guard.py` | **New** |
| Runtime Capabilities | `app/cam/runtime_capabilities/` | **New** — 6 modules |
| Review Queue | `app/cam/review_queue/` | **New** — 4 modules |
| Review UX | `app/cam/review_ux/` | **New** — 3 modules |
| Export Lifecycle Matrix | `docs/governance/EXPORT_LIFECYCLE_CLASSIFICATION_MATRIX.md` | **New** |

---

## 3. Major Changes Introduced

### Constitutional Documents

| Document | Repository | Purpose |
|----------|------------|---------|
| ADR-0010 | tap_tone_pi | Guidance authority boundary |
| ADR-0011 | tap_tone_pi | Measurement authority |
| ADR-0012 | tap_tone_pi | Epistemic status taxonomy |
| AGE_CONSTITUTIONAL_CONTRACT.md | tap_tone_pi | Capability matrix |
| EPISTEMIC_STATUS_MATRIX.md | tap_tone_pi | Developer quick reference |
| CROSS_REPO_AUTHORITY_CROSSWALK.md | luthiers-toolbox | Authority vocabulary mapping |
| IBG_BLOCKED_PROVENANCE_RATIFICATION_TIMELINE.md | luthiers-toolbox | Export governance timeline |
| MULTI_REPO_GOVERNANCE_CONVERGENCE_REPORT.md | luthiers-toolbox | Cross-repo audit |

### Contract Types

| Contract | Repository | Fields |
|----------|------------|--------|
| `AdvisoryAuthorityV1` | tap_tone_pi | authority_class, authority_scope, can_establish_truth, can_modify_measurement, can_enter_measurement_export |
| `TypedConfidenceV1` | tap_tone_pi | value, domain, source |
| `MeasurementWorkflowContractV1` | tap_tone_pi | workflow_id, required_repetitions, sample_rate_hz, fft_window, min_snr_db |
| `RepeatabilityEvidenceV1` | tap_tone_pi | repetitions_required/completed, frequency_mean/variance, passed_gate |
| `ReviewQueueItem` | luthiers-toolbox | queue_id, source_layer, priority, human_review_required, execution_authorized |
| `ReviewDecisionRecord` | luthiers-toolbox | decision_id, decision_type, reviewer_id, reviewed_at |
| `FederatedCapability` | luthiers-toolbox | capability_id, namespace, version, policies |

### Enforcement Mechanisms

| Mechanism | Repository | Behavior |
|-----------|------------|----------|
| `check_guidance_language.py` | tap_tone_pi | AST-based forbidden term detection |
| `test_guidance_not_in_measurement_exports.py` | tap_tone_pi | Export boundary validation |
| `test_ui_authority_boundary.py` | tap_tone_pi | UI framing validation |
| `test_constitutional_docs.py` | tap_tone_pi | Doctrine completeness |
| `check_all.py` | luthiers-toolbox | Unified governance runner |
| `validate_export_lifecycle_matrix.py` | luthiers-toolbox | DXF lifecycle validation |
| `assert_dxf_lifecycle_context()` | luthiers-toolbox | Guard before DXF save |

---

## 4. Risks Discovered

### Critical Risks

| Risk | Repository | Severity | Status |
|------|------------|----------|--------|
| 27 commits not pushed to origin | tap_tone_pi | **CRITICAL** | Reconstruction risk |
| IBG BLOCKED_PROVENANCE awaiting ratification | luthiers-toolbox | **HIGH** | 5 DXF save points gated |
| Parallel review queue implementations | Both | **HIGH** | Incompatible workflows |
| Confidence vocabulary collision | Both | **HIGH** | Authority inheritance risk |

### Moderate Risks

| Risk | Repository | Severity | Notes |
|------|------------|----------|-------|
| 13 language guard findings | tap_tone_pi | **MEDIUM** | Non-strict mode |
| 3 UI tests skip without PyQt6 | tap_tone_pi | **MEDIUM** | Test coverage gap |
| 8E in-memory queue | luthiers-toolbox | **MEDIUM** | Lost on restart |
| Missing handoffs (MRP 5C, 5D, 5I-5L) | luthiers-toolbox | **MEDIUM** | Reconstruction gap |

### Low Risks

| Risk | Notes |
|------|-------|
| No shared schema registry | Documentation-only alignment |
| Research layer vs governance layer distinction | Requires README banners |
| vectorizer-sandbox separation | Import gate CI present |

---

## 5. Technical Debt

### tap_tone_pi Technical Debt

| Item | Location | Priority |
|------|----------|----------|
| 13 guidance language findings | `agent/messages.py`, `message_spec.py` | P1 — cleanup before strict mode |
| Bare `confidence: float` deprecation | `AttentionDirectiveV1` | P2 — migration path defined |
| Epistemic status not in schemas | Doctrine-only | P2 — future DO |
| C3: Transfer function uncertainty | `core/dsp.py` | P2 — physics gap |
| C4: Hardcoded epsilon | `core/dsp.py` | P3 — numerical hygiene |

### luthiers-toolbox Technical Debt

| Item | Location | Priority |
|------|----------|----------|
| IBG provenance ratification | 5 blocked DXF saves | P0 — governance blocker |
| Missing MRP handoffs | 6 sprint gaps | P1 — reconstruction |
| `rank_score` → `confidence_value` naming | IBG workflow | P1 — authority semantics |
| Research 1A/1B/1C fragmentation | `docs/research/` | P2 — documentation |
| 8E ephemeral queue | Review routing | P2 — operational |

### Cross-Repository Technical Debt

| Item | Priority |
|------|----------|
| No shared authority vocabulary | P1 |
| No shared review decision semantics | P1 |
| No cross-repo contract tests | P2 |
| No shared schema registry | P2 |
| No integration API defined | P3 |

---

## 6. Governance Gaps

### Vocabulary Gaps

| Concept | tap_tone_pi | luthiers-toolbox | Gap |
|---------|-------------|------------------|-----|
| Authority class | `AuthorityClass` enum | `AuthorityState` enum | **Different values** |
| Confidence domain | `ConfidenceDomain` enum | `ConfidenceType` enum | **Different names** |
| Review decision | — | `DecisionType` enum | **tap_tone has no equivalent** |
| Epistemic status | 7 states in ADR-0012 | Lifecycle classes in matrix | **Mapping doc-only** |

### Enforcement Gaps

| Gap | Impact |
|-----|--------|
| tap_tone language guard non-strict | Guidance authority drift possible |
| No cross-repo CI | Integration bugs undetected |
| CAM→luthiers undefined | False integration assumptions |
| IBG export governance incomplete | Authority laundering risk |

### Documentation Gaps

| Gap | Repository |
|-----|------------|
| CAM-Assist integration spec | All |
| Unified review decision semantics | All |
| Cross-repo testing guide | All |
| Shared authority enum spec | All |

---

## 7. Reconstruction Risks

### Per-Repository Reconstruction

| Repository | Score | Notes |
|------------|-------|-------|
| tap_tone_pi | **9.2/10** | 12 ADRs, 2,596 tests, comprehensive handoffs |
| luthiers-toolbox | **8.5/10** | Strong governance, some handoff gaps |
| CAM-Assist-Blueprint | **8.0/10** | Clean order-per-branch, schema-focused |

### Cross-Repository Reconstruction

| Dimension | Score | Notes |
|-----------|-------|-------|
| Vocabulary alignment | **6/10** | Crosswalk doc exists, no code alignment |
| Schema compatibility | **5/10** | Incompatible ID formats, no shared registry |
| Integration path | **4/10** | No defined API or contract |
| Test coverage | **3/10** | No cross-repo tests |

### Knowledge Loss Hotspots

1. **tap_tone 27 unpushed commits** — Collaborators cannot see constitutional work
2. **Missing luthiers handoffs** — MRP 5C, 5D, 5I-5L gaps
3. **Research doc fragmentation** — Wave 1A/1B/1C cross-links may break
4. **CAM→luthiers integration** — No documented wire-up

---

## 8. Unresolved Blockers

### tap_tone_pi Blockers

| Blocker | Status | Resolution |
|---------|--------|------------|
| Push 27 commits | **PENDING** | `git push origin main` |
| Enable strict language guard | **BLOCKED** | Requires 13-fix cleanup |

### luthiers-toolbox Blockers

| Blocker | Status | Resolution |
|---------|--------|------------|
| IBG provenance ratification | **BLOCKED** | Phase R1 governance session |
| Research spine restore | **PARTIAL** | 1A/1B restored; 1C pending |
| CAM A12 schema merge | **PENDING** | Merge `cam-a12-review-decision-record` to main |

### Cross-Repository Blockers

| Blocker | Status | Resolution |
|---------|--------|------------|
| Shared authority vocabulary | **NOT STARTED** | Phase 1 convergence |
| Integration API | **NOT STARTED** | Phase 2 convergence |
| Cross-repo CI | **NOT STARTED** | Phase 3 convergence |

---

## 9. Governance Compliance Assessment

### tap_tone_pi Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Instrument class headers | ✅ | All modules marked |
| Authority contracts | ✅ | `advisory_authority.py`, `confidence_domain.py` |
| Export boundary guards | ✅ | `test_guidance_not_in_measurement_exports.py` |
| Language guards | ⚠️ | Non-strict, 13 findings |
| Constitutional documentation | ✅ | ADR-0010, 0011, 0012 |
| Test coverage | ✅ | 2,596 tests, 139 new |

### luthiers-toolbox Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| CI-blocking governance | ✅ | `check_all.py` authority chain |
| DXF lifecycle guards | ✅ | 33 unit tests |
| Capability federation | ✅ | 72 tests, regression guard |
| Review queue invariants | ✅ | 70+ tests, 8E Pydantic |
| Export lifecycle matrix | ⚠️ | 5 BLOCKED_PROVENANCE rows |
| Vectorizer separation | ✅ | Import gate CI |

### Cross-Repository Compliance

| Requirement | Status | Notes |
|-------------|--------|-------|
| Vocabulary alignment | ⚠️ | Crosswalk doc-only |
| Schema compatibility | ❌ | No shared registry |
| Integration contracts | ❌ | Not defined |
| Cross-repo tests | ❌ | None exist |

---

## 10. Architectural Risk Assessment

### Highest-Impact Risks

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| 1 | Review queue duplication | Incompatible operator workflows | **HIGH** | Publish unified review routing spec |
| 2 | Confidence/authority collision | Auto-approval from ML/rank | **HIGH** | Mandate TypedConfidence pattern |
| 3 | IBG provenance gap | Authority laundering | **HIGH** | Complete R1 ratification |
| 4 | tap_tone unpushed | Knowledge loss | **CRITICAL** | Push immediately |
| 5 | No cross-repo tests | Integration bugs | **MEDIUM** | Phase 3 CI harmonization |

### Architecture Stability Assessment

| Dimension | tap_tone | luthiers | Cross-Repo |
|-----------|----------|----------|------------|
| Foundation stability | **HIGH** | **HIGH** | **LOW** |
| Contract maturity | **HIGH** | **MEDIUM** | **LOW** |
| Test coverage | **HIGH** | **MEDIUM** | **NONE** |
| Documentation | **HIGH** | **HIGH** | **MEDIUM** |

---

## 11. Sprint Convergence Roadmap

### Phase 0 — Stabilize Locally (Immediate)

| Action | Repository | Priority | Owner |
|--------|------------|----------|-------|
| Push 27 commits | tap_tone_pi | **P0** | Platform |
| Keep regression guard green | luthiers-toolbox | **P0** | Platform |
| Ratify IBG provenance timeline | luthiers-toolbox | **P0** | Governance |
| Restore research 1A/1B/1C | luthiers-toolbox | **P1** | Platform |

### Phase 1 — Vocabulary Convergence (Week 1-2)

| Action | Deliverable | Owner |
|--------|-------------|-------|
| Ratify crosswalk doc | Signed CROSS_REPO_AUTHORITY_CROSSWALK.md | All repo owners |
| Map epistemic status → lifecycle class | Updated crosswalk table | tap_tone + luthiers |
| Map review decisions | Decision effects matrix | luthiers + CAM |
| Clean 13 language findings | Strict guard enabled | tap_tone |

### Phase 2 — Contract Boundaries (Week 3-4)

| Action | Deliverable | Owner |
|--------|-------------|-------|
| Define `integration-v1` schema | JSON Schema spec | Platform |
| Add `epistemic_status` to luthiers artifacts | Additive field | luthiers |
| Deprecate bare `confidence` in tap_tone | Migration timeline | tap_tone |
| Merge CAM A12 schema | `review_decision_record.schema.json` on main | CAM |

### Phase 3 — CI Harmonization (Month 2)

| Action | Deliverable | Owner |
|--------|-------------|-------|
| Shared authority invariant tests | pytest module | Platform |
| Manifest drift detection | luthiers CI | luthiers |
| Strict language guard | tap_tone CI | tap_tone |
| Cross-repo integration tests | Contract test suite | Platform |

### Phase 4 — Runtime Integration (Month 3+, Gated)

| Action | Prerequisite | Owner |
|--------|--------------|-------|
| Review Router API | Crosswalk ratified | luthiers |
| IBG review package alignment | Provenance ratified | luthiers |
| tap_tone import markers | Schema updated | tap_tone |

### Convergence Milestones

| Milestone | Definition of Done |
|-----------|-------------------|
| **M1** | Crosswalk ratified by all owners |
| **M2** | All repos CI green on authority invariant tests |
| **M3** | CAM→luthiers integration spec (even if not implemented) |
| **M4** | IBG provenance unblocked in lifecycle matrix |

---

## 12. Recommended Immediate Actions

### P0 — Critical (Today)

| Action | Repository | Risk Addressed |
|--------|------------|----------------|
| `git push origin main` | tap_tone_pi | Reconstruction / collaboration |
| Verify governance gate green | luthiers-toolbox | Bypass vectors |

### P1 — High (This Week)

| Action | Repository | Risk Addressed |
|--------|------------|----------------|
| Clean 13 language findings | tap_tone_pi | Guidance authority |
| Schedule IBG R1 ratification | luthiers-toolbox | Export legitimacy |
| Restore full research spine | luthiers-toolbox | Documentation gaps |
| Ratify crosswalk with owners | All | Schema/semantic drift |

### P2 — Medium (Next Sprint)

| Action | Repository | Risk Addressed |
|--------|------------|----------------|
| Enable strict language guard | tap_tone_pi | Authority drift |
| CI manifest drift detection | luthiers-toolbox | Capability federation |
| Document CAM→luthiers as TBD | All | False assumptions |
| Add governance inventory entry for research | luthiers-toolbox | Fragmentation |

---

## 13. Long-Term Stabilization Recommendations

### Architecture Recommendations

1. **`platform-contracts` repository** — Shared schemas + invariant tests; consumers: all three repos
2. **Extract review routing** — Shared spec implemented once in luthiers, CLI adapters in CAM-Assist
3. **Unified provenance service** — Read-only lineage API for DXF + strategy + measurement imports
4. **Governance dashboard** — Aggregate CI results from all repos

### Domain Separation (Recommended)

| Repository | Domain | Boundaries |
|------------|--------|------------|
| tap_tone_pi | Acoustic measurement | No design advice, no execution |
| CAM-Assist-Blueprint | Strategy intent packaging | No G-code, no execution |
| luthiers-toolbox | Geometry/runtime/CAM prep | Execution gated by capability federation |
| vectorizer-sandbox | Cognition R&D | Must not feed spine without graduation |

### Governance Standards

1. Every repo maintains: README authority statement, governance index, CI entry script, sprint handoff
2. All persisted artifacts: `schema_version`, `record_type`, `authority` block, `provenance`
3. Confidence must use domain + value + source everywhere
4. Breaking changes require ADR or Dev Order record
5. Cross-repo changes require crosswalk update

---

## Appendix A: Document Index

| Document | Repository | Path | Purpose |
|----------|------------|------|---------|
| ADR-0010 | tap_tone_pi | `docs/ADR-0010-guidance-authority-boundary.md` | AGE constitutional limits |
| ADR-0011 | tap_tone_pi | `docs/ADR-0011-measurement-authority.md` | Artifact authority |
| ADR-0012 | tap_tone_pi | `docs/ADR-0012-epistemic-status-taxonomy.md` | Data provenance states |
| AGE_CONSTITUTIONAL_CONTRACT | tap_tone_pi | `docs/AGE_CONSTITUTIONAL_CONTRACT.md` | Capability matrix |
| EPISTEMIC_STATUS_MATRIX | tap_tone_pi | `docs/EPISTEMIC_STATUS_MATRIX.md` | Quick reference |
| SPRINT_ARCHITECTURE_HANDOFF | tap_tone_pi | `docs/SPRINT_ARCHITECTURE_HANDOFF.md` | Sprint handoff |
| GOVERNANCE_AUDIT_HANDOFF | tap_tone_pi | `docs/GOVERNANCE_AUDIT_HANDOFF.md` | Four-axis audit |
| CROSS_REPO_AUTHORITY_CROSSWALK | luthiers-toolbox | `docs/governance/CROSS_REPO_AUTHORITY_CROSSWALK.md` | Vocabulary mapping |
| IBG_BLOCKED_PROVENANCE | luthiers-toolbox | `docs/governance/IBG_BLOCKED_PROVENANCE_RATIFICATION_TIMELINE.md` | Export governance |
| MULTI_REPO_GOVERNANCE_CONVERGENCE | luthiers-toolbox | `docs/MULTI_REPO_GOVERNANCE_CONVERGENCE_REPORT.md` | Cross-repo audit |
| SPRINT_ARCHITECTURE_HANDOFF | luthiers-toolbox | `docs/SPRINT_ARCHITECTURE_HANDOFF_2026-05-24.md` | Sprint handoff |

---

## Appendix B: Commit Summary

### tap_tone_pi (27 commits)

| Theme | Commits | Key Changes |
|-------|---------|-------------|
| Governance Audit | 10 | Instrument class headers, import boundaries |
| DO-78 (AGE Constitutional) | 7 | ADR-0010, authority contracts, guards |
| DO-81 (Measurement Authority) | 4 | ADR-0011, ADR-0012, matrix |
| Workflow Contracts | 3 | MeasurementWorkflowContractV1, registry |
| Repeatability | 1 | RepeatabilityEvidenceV1 |
| Documentation | 2 | Handoffs |

### luthiers-toolbox (66 commits, PRs #17-#37)

| Theme | PRs | Key Changes |
|-------|-----|-------------|
| Governance | #17-19 | Unified runner, inventory, blocking gate |
| Complexity Reduction | #24 | parse_dxf CC 50→19 |
| DXF Lifecycle | #34, #36 | Guards, DxfWriter contract |
| Capability Federation | #35, #37 | MRP-5 spine, regression guard |
| Review UX/Queue | 8C-8E | ReviewQueueItem, ReviewDecisionRecord |
| Sandbox Migration | #26-28 | vectorizer-sandbox separation |

---

## Appendix C: Schema Summary

### tap_tone_pi Schemas (20)

| Schema | Version | Purpose |
|--------|---------|---------|
| measurement_workflow_contract_v1 | v1 | Workflow definition |
| repeatability_evidence_v1 | v1 | Variance computation |
| viewer_pack_v1 | v1 | Export package |
| phase2_*.json (5) | v1 | ODS/grid |
| tap_peaks, moe_result, manifest | v1 | Measurement outputs |
| wood_flitch_record_v1 | v1 | Material tracking |
| instrument_build_record_v1 | v1 | Build tracking |
| session_timeline_v1 | v1 | Event timeline |

### luthiers-toolbox Models (Pydantic)

| Model | Module | Purpose |
|-------|--------|---------|
| ReviewQueueItem | review_queue.py | Queue routing |
| ReviewDecisionRecord | review_queue.py | Decision recording |
| FederatedCapability | runtime_capabilities/contracts.py | Capability definition |
| DxfLifecycleContext | dxf_lifecycle_guard.py | Export context |

---

## Appendix D: Test Summary

| Repository | Total Tests | New This Sprint | Governance Tests |
|------------|-------------|-----------------|------------------|
| tap_tone_pi | 2,596 | 139 | ~50 |
| luthiers-toolbox | 433+ | 200+ | 114+ |

---

*Audit completed: 2026-05-24*
*Next review trigger: First cross-repo integration Dev Order or IBG provenance ratification*
