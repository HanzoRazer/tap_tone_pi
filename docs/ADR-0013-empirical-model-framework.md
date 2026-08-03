# ADR-0013: Empirical Model Framework as Shared Metadata Authority

**Status:** Accepted (DO-101A)
**Date:** 2026-08-03
**Context:** Tap Tone Pi Analyzer / scientific equation metadata
**Decision Drivers:** Single authority for formula identity and evidence linkage; preserve existing equation implementations; avoid a third uncertainty budget; keep advisory/measurement boundaries intact

---

## Context

DO-94/DO-95 proved formula-target, evidence-link, and validation-envelope
contracts inside `tap_tone_pi/luthiery/`. Those contracts are already
domain-agnostic in substance, but living only under luthiery made every new
scientific equation area invent parallel metadata.

Separately, the repository already has two `UncertaintyBudget`
implementations (`tap_tone_pi.uncertainty.budget` and
`tap_tone_pi.core.statistics`). A greenfield empirical package that embedded
a third budget type would deepen that split.

## Decision

1. Introduce `tap_tone_pi/empirical/` as the **shared metadata authority** for
   empirical scientific models: identity (`model_id` + `version`), assumptions,
   input/output declarations, validity domain, measurement links, evidence
   references, calibration history, and a neutral uncertainty *reference*.
2. Treat DO-101 as a **generalization** of capabilities already proven in
   `luthiery/`, not a parallel subsystem. Move
   `FormulaValidationEnvelopeV1` / `validate_formula_candidate` into empirical
   and re-export them from luthiery so existing imports and serialized
   `schema_version` values remain stable.
3. Represent uncertainty as `UncertaintyReference`
   (`uncertainty_model_id` / `uncertainty_record_id` / `uncertainty_summary`).
   Do **not** migrate or reconcile the two existing budgets in DO-101A.
4. Keep mathematical implementations, measurements, laboratory workflows, and
   advisory logic outside this package. Models reference equations and
   evidence; they do not own them.
5. Publish additive schema
   `contracts/empirical_model_definition_v1.schema.json` and enforce
   schema-strict Python loaders for persistence boundaries.

## Alternatives considered

* **Keep all contracts in `luthiery/`** — Rejected: forces non-luthiery science
  to import a domain package, or to duplicate authorities.
* **Embed a full UncertaintyBudget in empirical contracts** — Rejected: creates
  a third budget type before grounding which of the two existing ones is
  public/canonical.
* **Greenfield rewrite of formula targets with breaking schema versions** —
  Rejected: unnecessary compatibility risk for DO-94/DO-95 artifacts.

## Consequences

### Positive

* One place for formula/model identity, validity, and evidence linkage.
* Luthiery becomes a domain consumer with stable imports.
* Future evidence sources (laboratory datasets, literature, MB Sound corpora)
  can attach without redesigning equation modules.

### Negative / costs

* Construction paths differ: dataclass constructors remain dumb containers;
  factories/loaders enforce validity. Callers that bypass builders can hold
  invalid objects until validation is run.
* Loaders are stricter than older permissive construction. Envelope payloads
  without `schema_version` are unsupported by
  `formula_validation_envelope_from_dict`.
* Advisory-language scanning rejects broad terms (`good`/`bad`/…) in model
  prose; free-text domain strings projected into assumptions can fail
  unexpectedly if they contain forbidden tokens.

## Non-goals

* Model registry and `ttp empirical` CLI (DO-101B)
* External corpus ingestion
* UncertaintyBudget reconciliation
* Calculator / equation modifications
* Advisory recommendations or material ranking

## References

* `docs/EMPIRICAL_MODEL_FRAMEWORK.md`
* `docs/ADR-0001-measurement-scope.md`
* `docs/ADR-0009-advisory-boundary.md`
* `docs/ADR-0011-measurement-authority.md`
* DO-94 / DO-95 luthiery formula contracts
* DO-101A implementation branch `cursor/do-101a-empirical-contract-foundation-b1ad`
