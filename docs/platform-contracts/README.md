# Platform Contracts

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository vocabulary normalization

---

## Purpose

This directory contains shared vocabulary contracts for the acoustic measurement and manufacturing ecosystem. These contracts define common terminology, semantics, and schemas for concepts that span multiple repositories.

The contracts are **docs-first** — they establish shared vocabulary without requiring shared runtime packages. Repositories may implement these contracts using their own code, as long as they conform to the defined semantics.

---

## Contracts

| Contract | Description | Schema |
|----------|-------------|--------|
| [authority-v1](authority-v1.md) | Four authority classes (MEASUREMENT, PROVENANCE, DECISION_SUPPORT, INTERPRETIVE) | [authority-v1.schema.json](schemas/authority-v1.schema.json) |
| [confidence-v1](confidence-v1.md) | Four confidence domains (SIGNAL, MEASUREMENT, INTERPRETIVE, RECOMMENDATION) | [confidence-v1.schema.json](schemas/confidence-v1.schema.json) |
| [epistemic-status-v1](epistemic-status-v1.md) | Seven epistemic statuses (Observed, Derived, Estimated, Predicted, Heuristic, Operator-Annotated, Externally-Sourced) | [epistemic-status-v1.schema.json](schemas/epistemic-status-v1.schema.json) |
| [review-decision-v1](review-decision-v1.md) | Four review states (PENDING, APPROVED, REJECTED, BLOCKED) | [review-decision-v1.schema.json](schemas/review-decision-v1.schema.json) |

---

## Participating Repositories

| Repository | Primary Concern | Integration Status |
|------------|-----------------|-------------------|
| tap_tone_pi | Acoustic measurement | Source of truth for authority/epistemic contracts |
| luthiers-toolbox | Manufacturing governance | Implements review-decision, needs confidence alignment |
| CAM-Assist-Blueprint | DXF lifecycle | Needs authority/review-decision mapping |

---

## Schema Format

Schemas use JSON Schema draft 2020-12. Each schema includes:

- `$defs` for reusable type definitions
- Concrete artifact type definitions
- Invariant documentation

Schemas are normative — implementations must conform to schema validation.

---

## Versioning

Contracts follow semantic versioning:

- **Major** (v1 → v2): Breaking changes to semantics or schema
- **Minor** (v1.0 → v1.1): Additive changes (new optional fields)
- **Patch** (v1.0.0 → v1.0.1): Clarifications, typo fixes

Current version: **v1.0.0** (Draft)

---

## Integration Path

1. **Phase 1 (Current):** Docs-only vocabulary definition
2. **Phase 2:** Cross-repo schema validation in CI
3. **Phase 3:** Shared adapter libraries (optional)
4. **Phase 4:** Runtime integration APIs

---

## See Also

- tap_tone_pi: ADR-0010, ADR-0011, ADR-0012
- tap_tone_pi: EPISTEMIC_STATUS_MATRIX.md
- tap_tone_pi: AGE_CONSTITUTIONAL_CONTRACT.md
- CROSS_REPO_SPRINT_CONVERGENCE_AUDIT.md
