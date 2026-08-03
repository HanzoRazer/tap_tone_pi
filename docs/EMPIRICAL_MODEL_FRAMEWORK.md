# Empirical Model Framework

**Status:** DO-101A foundation (contracts, validation, serialization, luthiery migration)
**Package:** `tap_tone_pi/empirical/`
**Follow-on:** DO-101B — registry and CLI inspection surface

---

## Philosophy

Every scientific equation in the Tap Tone Pi Analyzer should be able to exist as
an **empirical model**: metadata that carries assumptions, measurement linkage,
validity domain, uncertainty references, calibration history, and evidence
references — without replacing the mathematical implementation.

This package owns **empirical model metadata**. It does **not** own:

- mathematical implementations
- measurements
- laboratory workflows
- advisory logic or interpretation
- evidence acquisition

Equations stay where they already live. Models *reference* them.

---

## Architecture

```text
tap_tone_pi/luthiery/   (proven formula targets / links / envelopes)
        ↓ generalize shared contracts
tap_tone_pi/empirical/  (domain-agnostic empirical model authority)
        ↓
luthiery becomes a domain consumer (re-exports + adapters)
```

DO-101 is a **generalization** of capabilities already proven in
`tap_tone_pi/luthiery/`, not a parallel authority.

| Concern | Authority after DO-101A |
|---|---|
| Formula / model identity | `EmpiricalModelDefinitionV1.model_id` + `version` |
| Evidence references | `EvidenceReference` (empirical); luthiery links adapt into it |
| Validity domains | `ValidityDomain` (empirical); envelope ranges project onto it |
| Validation envelopes | `FormulaValidationEnvelopeV1` (lives in empirical; re-exported by luthiery) |
| Uncertainty metadata | `UncertaintyReference` only — **no third UncertaintyBudget** |

---

## Uncertainty ruling

The repository already has two `UncertaintyBudget` implementations:

- `tap_tone_pi.uncertainty.budget.UncertaintyBudget`
- `tap_tone_pi.core.statistics.UncertaintyBudget`

DO-101A does **not** migrate or reconcile them, and does **not** import either
as the canonical empirical type. Empirical contracts carry:

```text
uncertainty_model_id
uncertainty_record_id
uncertainty_summary
```

Reconciliation of the two budgets is a separate follow-up.

---

## Lifecycle

1. **Author** via `build_model(...)` (or project one from a luthiery formula
   target via `empirical.luthiery_compat`). Direct dataclass construction is a
   dumb container — validity is not enforced at `__init__`.
2. **Validate** with `empirical.validation.validate_model` (pure; no I/O).
3. **Serialize** with `to_dict` / `from_dict`. Loaders are schema-strict:
   required fields must be present, unknown keys are rejected, whitespace-only
   identifiers fail, and `empirical_model_from_dict` runs semantic validation
   by default (`validate=False` opts out).
4. **Clone** with `clone_model(..., validate=True)`. Overriding `model_id` or
   `version` authors a *new* published identity; it does not rewrite history.
5. **Register / inspect** — DO-101B (`ttp empirical list|show|validate`).

Published `(model_id, version)` pairs never change meaning once published.

---

## Evidence model

Evidence remains external. Models hold `EvidenceReference` records
(identifiers, kind, optional citation/URI/formula ids). They never duplicate
measurement payloads, viewer packs, or laboratory procedure text.

Future evidence sources (MB Sound corpora, laboratory datasets, certified
references, TTP Analyzer measurements) populate these references in later
dev orders. DO-101A ingests **no** external datasets.

---

## Luthiery compatibility

| Existing symbol | After DO-101A |
|---|---|
| `LuthieryFormulaTargetV1` | Unchanged in `luthiery`; adapter → `EmpiricalModelDefinitionV1` |
| `LuthieryFormulaEvidenceLinkV1` | Unchanged; adapter → `EvidenceReference` |
| `FormulaValidationEnvelopeV1` | Defined in `empirical.contracts`; re-exported from `luthiery` |
| `validate_formula_candidate` | Implemented in `empirical.formula_validation`; re-exported |
| `validate_formula_candidate_from_evidence` | Remains in `luthiery` (needs DO-89C + target types) |

Serialized luthiery `schema_version` strings and field sets are unchanged.

---

## Advisory boundary

The framework records assumptions, uncertainty references, and validity. It
never evaluates whether a specimen is good or bad, never ranks materials, and
never recommends construction changes. Validation rejects forbidden advisory
terms in model prose.

---

## Non-goals (DO-101A)

- Model registry and `ttp empirical` CLI (DO-101B)
- MB Sound / corpus ingestion
- Calibration fitting, regression, statistical analysis
- Calculator or equation modifications
- Guided-lab workflow integration
- Viewer-pack schema changes beyond additive empirical contract registration
