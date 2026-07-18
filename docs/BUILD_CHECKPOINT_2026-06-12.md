# Build Checkpoint — tap_tone_pi

**Timestamp:** 2026-06-12 @ 19:25 UTC
**Branch:** main
**Last Commit:** `c46da30` — fix: reclassify 4 modules from MEASUREMENT to DECISION SUPPORT

---

## Test Baseline

| Metric | Value |
|--------|-------|
| Tests collected | 2,770 |
| Tests passing | 2,769 |
| Tests failing | 1 (hardware-related) |
| Tests skipped | 52 |
| xfail | 1 |

**Known failure:** `test_cmd_measure_lists_events` — microphone clipping (hardware environment issue, not code defect)

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

---

## Measurement Legitimacy Stack

```
Build Session (DO-88)
    ↓
Experiment Campaign (DO-87)
    ↓
Experiment Revision (DO-87)
    ↓
Workflow Contract (DO-86)
    ↓
Workflow Execution Evidence (DO-86)
    ↓
Measurement Lineage (DO-87, extended DO-88)
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
├── build_session.py      (DO-88)
├── environment.py        (DO-88)
├── experiment_contracts.py (DO-87)
├── fixture.py            (DO-88)
├── lineage.py            (DO-87, DO-88)
└── measurement_links.py  (DO-87, DO-88)
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
| MeasurementLineageV1 | `measurement_lineage_v1` | `provenance/measurement_links.py` |
| MeasurementWorkflowContractV1 | `measurement_workflow_contract_v1` | `workflow/contracts.py` |
| WorkflowExecutionEvidenceV1 | `workflow_execution_evidence_v1` | `workflow/contracts.py` |
| RepeatabilityEvidenceV1 | `repeatability_evidence_v1` | `core/repeatability.py` |
| MeasurementValidityEnvelopeV1 | `measurement_validity_envelope_v1` | `core/repeatability.py` |

---

## Schema Files Updated

| File | Changes |
|------|---------|
| `contracts/phase2_ods_snapshot.schema.json` | Added DO-85, DO-86, DO-87, DO-88 optional blocks |

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

All blocks are additive. Historical exports remain valid.

---

## Governance Status

| Capability | Status |
|------------|--------|
| Calibration provenance | ✅ Complete |
| Confidence provenance | ✅ Complete |
| Uncertainty propagation | ✅ Complete (DO-84) |
| Repeatability evidence | ✅ Complete (DO-85) |
| Workflow provenance | ✅ Complete (DO-86) |
| Experimental provenance | ✅ Complete (DO-87) |
| Build context provenance | ✅ Complete (DO-88) |
| Advisory containment | ✅ Stable |
| Export legitimacy | ✅ Verified |

---

## Architectural Classification

All provenance modules:
```
INSTRUMENT CLASS: MEASUREMENT
```

No advisory semantics in provenance layer. All states are observational.

---

## Uncommitted Changes

| File | Status |
|------|--------|
| `tap_tone_pi/provenance/` | NEW (DO-87, DO-88) |
| `tap_tone_pi/workflow/validation.py` | NEW (DO-86) |
| `tap_tone_pi/core/repeatability.py` | MODIFIED (DO-85) |
| `tap_tone_pi/core/dsp.py` | MODIFIED (DO-84) |
| `tap_tone_pi/workflow/contracts.py` | MODIFIED (DO-86, DO-88) |
| `tap_tone_pi/provenance/measurement_links.py` | MODIFIED (DO-88) |
| `tap_tone_pi/provenance/experiment_contracts.py` | MODIFIED (DO-88) |
| `contracts/phase2_ods_snapshot.schema.json` | MODIFIED |
| `scripts/phase2/export_viewer_pack_v1.py` | MODIFIED |
| `docs/GOVERNANCE_AUDIT_HANDOFF.md` | MODIFIED |
| `docs/dev_orders/CURRENT.md` | MODIFIED |
| `docs/dev_orders/TTP_HEADLESS_TASKS.md` | NEW |
| `tests/test_repeatability.py` | NEW |
| `tests/test_workflow_contracts.py` | NEW |
| `tests/test_export_workflow_anchor.py` | NEW |
| `tests/test_experiment_contracts.py` | NEW |
| `tests/test_experiment_lineage.py` | NEW |
| `tests/test_experiment_export_anchor.py` | NEW |
| `tests/test_build_session.py` | NEW |

---

## Next Steps (Deferred)

| Gap | Description | Priority |
|-----|-------------|----------|
| DO-89 | Campaign lifecycle states (planned/active/paused/completed/archived) | Medium |
| — | Measurement campaign analytics (drift, trends, statistics) | Low |
| — | Environmental provenance aggregation | Low |

---

## Repository Maturity

Current classification:

```
Institutional Acoustic Measurement Platform
```

The repository has successfully crossed from "governed analyzer" into "governed acoustic R&D platform" with complete measurement legitimacy stack.

---

*Checkpoint created: 2026-06-12 @ 19:25*
*Document owner: Build checkpoint process*
