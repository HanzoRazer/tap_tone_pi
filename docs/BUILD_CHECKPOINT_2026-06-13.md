# Build Checkpoint — tap_tone_pi

**Timestamp:** 2026-06-13 @ 12:13 UTC (updated post-commit)
**Branch:** main
**Last Commit:** `4ebce14` — docs: update codebase audit and remove obsolete SPRINTS.md
**Provenance Stack Status:** COMMITTED AND PUSHED

---

## Test Baseline

| Metric | Value |
|--------|-------|
| Tests collected | 2,828 |
| Tests passing | 2,827 |
| Tests failing | 1 (hardware-related) |
| Tests skipped | ~52 |
| xfail | 1 |

**Known failure:** `test_cmd_measure_lists_events` — microphone clipping (hardware environment issue, not code defect)

**New tests since last checkpoint:** 58 (DO-89)

---

## Completed Dev Orders

| Order | Description | Tests Added |
|-------|-------------|-------------|
| DO-001 | GUM uncertainty framework | — |
| DO-002 | Wood species data sourcing | — |
| DO-003 | Per-flitch wood database | — |
| DO-004 | Per-build instrument record schema | — |
| DO-005 | Analyzer GUI: Phase 2 results widget | — |
| DO-006 | Predicted-vs-measured comparison overlay | — |
| DO-008 | Build record auto-discovery + cleanup | — |
| DO-084 | Transfer function uncertainty propagation | 12 |
| DO-085 | Repeatability evidence + validity envelope | 24 |
| DO-086 | Workflow contracts + procedural provenance | 35 |
| DO-087 | Experimental provenance + campaign lineage | 50 |
| DO-088 | Build session + environmental provenance | 25 |
| DO-089 | Campaign lifecycle + measurement aggregation | 42 |

**Total tests added (DO-084 through DO-089):** 188

---

## Measurement Legitimacy Stack

```
Build Session (DO-88)
    ↓
Experiment Campaign (DO-87)
    ↓
Campaign Lifecycle State (DO-89)
    ↓
Experiment Revision (DO-87)
    ↓
Workflow Contract (DO-86)
    ↓
Workflow Execution Evidence (DO-86)
    ↓
Measurement Lineage (DO-87, extended DO-88)
    ↓
Measurement Set (DO-89)
    ↓
Measurement Set Summary (DO-89)
    ↓
Repeatability Evidence (DO-85)
    ↓
Measurement Validity Envelope (DO-85)
    ↓
Transfer Function Uncertainty (DO-84)
    ↓
Calibration Provenance
    ↓
Confidence Provenance
```

**Status:** Complete

---

## Provenance Package Structure

```
tap_tone_pi/provenance/
├── __init__.py
├── aggregation.py        (DO-89) — measurement set collection/summarization
├── build_session.py      (DO-88)
├── campaign_lifecycle.py (DO-89) — state transition helpers
├── environment.py        (DO-88)
├── experiment_contracts.py (DO-87, extended DO-89)
├── fixture.py            (DO-88)
├── lineage.py            (DO-87, DO-88)
├── measurement_links.py  (DO-87, DO-88)
└── measurement_set.py    (DO-89) — MeasurementSetV1, SummaryV1, LifecycleExportV1
```

---

## Key Contracts

| Contract | Schema Version | Location |
|----------|----------------|----------|
| BuildSessionV1 | `build_session_v1` | `provenance/build_session.py` |
| EnvironmentRecordV1 | `environment_record_v1` | `provenance/environment.py` |
| FixtureRecordV1 | `fixture_record_v1` | `provenance/fixture.py` |
| ExperimentCampaignV1 | `experiment_campaign_v1` | `provenance/experiment_contracts.py` |
| ExperimentRevisionV1 | `experiment_revision_v1` | `provenance/experiment_contracts.py` |
| CampaignLifecycleState | (enum) | `provenance/experiment_contracts.py` |
| MeasurementLineageV1 | `measurement_lineage_v1` | `provenance/measurement_links.py` |
| MeasurementSetV1 | `measurement_set_v1` | `provenance/measurement_set.py` |
| MeasurementSetSummaryV1 | `measurement_set_summary_v1` | `provenance/measurement_set.py` |
| CampaignLifecycleExportV1 | `campaign_lifecycle_v1` | `provenance/measurement_set.py` |
| MeasurementWorkflowContractV1 | `measurement_workflow_contract_v1` | `workflow/contracts.py` |
| WorkflowExecutionEvidenceV1 | `workflow_execution_evidence_v1` | `workflow/contracts.py` |
| RepeatabilityEvidenceV1 | `repeatability_evidence_v1` | `core/repeatability.py` |
| MeasurementValidityEnvelopeV1 | `measurement_validity_envelope_v1` | `core/repeatability.py` |

---

## Campaign Lifecycle States (DO-89)

```
planned ──→ active ──→ completed ──→ archived
   │          │            │
   │          ├──→ paused ─┤
   │          │            │
   │          └──→ aborted ┘
   │                  │
   └──→ archived ←────┘
```

Valid transitions enforced via `ValueError`. No advisory semantics — completed means procedurally completed, not successful.

---

## Schema Files Updated

| File | Changes |
|------|---------|
| `contracts/phase2_ods_snapshot.schema.json` | Added DO-89: campaign_lifecycle, measurement_set, measurement_set_summary |

---

## Export Integration

`scripts/phase2/export_viewer_pack_v1.py` now includes optional blocks for:

- `repeatability` (DO-85)
- `measurement_validity_envelope` (DO-85)
- `workflow_contract` (DO-86)
- `workflow_execution` (DO-86)
- `experiment_campaign` (DO-87)
- `experiment_revision` (DO-87)
- `measurement_lineage` (DO-87, extended DO-88)
- `build_session` (DO-88)
- `environment_record` (DO-88)
- `fixture_record` (DO-88)
- `campaign_lifecycle` (DO-89)
- `measurement_set` (DO-89)
- `measurement_set_summary` (DO-89)

All blocks are additive. Historical exports remain valid.

---

## Governance Status

| Capability | Status |
|------------|--------|
| Calibration provenance | Complete |
| Confidence provenance | Complete |
| Uncertainty propagation | Complete (DO-84) |
| Repeatability evidence | Complete (DO-85) |
| Workflow provenance | Complete (DO-86) |
| Experimental provenance | Complete (DO-87) |
| Build context provenance | Complete (DO-88) |
| Campaign lifecycle | Complete (DO-89) |
| Measurement aggregation | Complete (DO-89) |
| Advisory containment | Stable |
| Export legitimacy | Verified |

---

## Architectural Classification

All provenance modules:
```
INSTRUMENT CLASS: MEASUREMENT
```

No advisory semantics in provenance layer. All states are observational.

---

## Commit History (This Sprint)

8 commits pushed to `origin/main`:

| Commit | Description |
|--------|-------------|
| `4ebce14` | docs: update codebase audit and remove obsolete SPRINTS.md |
| `8ce759c` | docs: update governance audit and sprint documentation |
| `2a9e30f` | feat: integrate provenance stack into schema and export pipeline |
| `21bc45c` | feat: add campaign lifecycle state and measurement set aggregation (DO-89) |
| `e06cdb8` | feat: add build session and environmental provenance (DO-88) |
| `57fbce7` | feat: add experimental provenance and measurement campaign lineage (DO-87) |
| `2e724e2` | feat: add workflow measurement contracts and procedural provenance (DO-86) |
| `f8456ef` | feat: add transfer function uncertainty and repeatability evidence (DO-84, DO-85) |

---

## Future Roadmap

### Deferred Capability: Acoustic Excitation Framework

See `docs/ROADMAP_ACOUSTIC_EXCITATION.md`

| Order | Description | Status |
|-------|-------------|--------|
| DO-90 | Acoustic Excitation Framework Foundation | Planned |
| DO-91 | Excitation Provenance & Transfer Function Workflow | Planned |
| DO-92 | MainBodyAirResonanceWorkflowV1 | Planned |
| DO-93 | FlatPlateResonanceWorkflowV1 | Planned |
| DO-94 | ModalParticipationMappingWorkflowV1 | Planned |
| DO-95 | Soundhole Placement Research Workflow | Planned |

---

## Repository Maturity

Current classification:

```
Institutional Acoustic Measurement Platform
```

The repository has successfully crossed from "governed analyzer" into "governed acoustic R&D platform" with complete measurement legitimacy stack (DO-84 through DO-89).

---

*Checkpoint created: 2026-06-13 @ 12:13*
*Document owner: Build checkpoint process*
