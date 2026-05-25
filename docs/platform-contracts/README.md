# Platform Contracts

**Version:** 1.0.0  
**Status:** Draft  
**Scope:** Cross-repository vocabulary normalization

---

## Purpose

This directory contains shared vocabulary contracts for the acoustic measurement and manufacturing ecosystem.

**Important:**

```
These contracts define vocabulary convergence only.
Runtime integration requires explicit Dev Orders.
```

The contracts are **docs-first** — they establish shared vocabulary without requiring shared runtime packages. Repositories may implement these contracts using their own code, as long as they conform to the defined semantics.

---

## Contracts

| Contract | Purpose | Schema |
|----------|---------|--------|
| [authority-v1](authority-v1.md) | Authority classes and non-authority flags | [authority-v1.schema.json](schemas/authority-v1.schema.json) |
| [confidence-v1](confidence-v1.md) | Domain-typed confidence | [confidence-v1.schema.json](schemas/confidence-v1.schema.json) |
| [epistemic-status-v1](epistemic-status-v1.md) | Observed/Derived/etc. data states | [epistemic-status-v1.schema.json](schemas/epistemic-status-v1.schema.json) |
| [review-decision-v1](review-decision-v1.md) | Human review decision semantics | [review-decision-v1.schema.json](schemas/review-decision-v1.schema.json) |

---

## Key Invariants

### Authority

Decision-support authority may route attention but may not establish truth.

### Confidence

No bare confidence in shared contracts — requires domain + value + source.

### Epistemic Status

Predicted cannot become observed. Heuristic cannot become measurement.

### Review Decision

Review decisions record human process. They do not automatically authorize implementation, execution, or machine output.

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

- Lowercase enum values for cross-repo compatibility
- Required fields for core invariants
- Optional mapping fields (`source_repo`, `local_*_type`)
- `$defs` for reusable type definitions

Schemas are normative — implementations must conform to schema validation.

---

## Non-Goals

These contracts do NOT:

- Create runtime adapters
- Merge review systems across repos
- Replace local enums automatically
- Authorize execution based on review
- Define specific thresholds or criteria

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
3. **Phase 3:** Shared adapter libraries (optional, requires Dev Order)
4. **Phase 4:** Runtime integration APIs (requires Dev Order)

---

## See Also

- tap_tone_pi: ADR-0010, ADR-0011, ADR-0012
- tap_tone_pi: EPISTEMIC_STATUS_MATRIX.md
- tap_tone_pi: AGE_CONSTITUTIONAL_CONTRACT.md
- CROSS_REPO_SPRINT_CONVERGENCE_AUDIT.md
