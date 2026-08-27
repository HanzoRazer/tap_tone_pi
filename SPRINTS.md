# SPRINTS.md — Backlog & Deferred Maintenance

A durable, lightweight backlog for **deferred work and maintenance** surfaced
during other tasks — the things that would otherwise evaporate as "noted as a
follow-up" in a review thread or chat. If it should be revisited but isn't being
done now, it goes here so it survives past the PR that surfaced it.

This is intentionally low-ceremony. When an item grows into real scoped work it
graduates to a dev order (`docs/dev_orders/`); until then it lives here.

---

## What belongs here (and what doesn't)

| Kind of thing | Where it goes | Why |
|---|---|---|
| Deferred **work** — a test gap, a maintenance chore, a conditional feature | **This file** | Real to-dos that aren't scheduled yet |
| A scoped, active development effort | `docs/dev_orders/` (+ `CURRENT.md`) | Has acceptance criteria and a sprint |
| An architectural **decision or property** ("this is how/why it works") | `docs/ADR-NNNN-*.md` or code/README | Not a to-do; documenting it as one is false backlog noise |
| An accepted **tradeoff** already documented in code/README | Leave it documented | Same — not open work |

Rule of thumb: if the honest description is *"someone should do X later,"* it
belongs here. If it's *"X works this way on purpose,"* it belongs in an ADR or a
docstring, **not** here.

---

## How to use

- **Add** an item with the next `B-NNN` id, a one-line summary, its origin, a
  category, a rough priority, and enough context to action it later (including
  any **trigger** that would make it worth doing).
- **Update** status as it moves: `open` → `in-progress` (link the dev order/PR)
  → `done` (link the merge) or `wontfix` (say why).
- **Graduate** anything substantial into a dev order and link it here rather than
  implementing straight from a backlog line.
- Keep design *decisions/properties* out — link the ADR/doc instead.

**Status:** `open` · `in-progress` · `done` · `wontfix`
**Priority:** `P1` (do soon) · `P2` (opportunistic) · `P3` (only if triggered)

---

## Backlog

### B-001 — Windows-specific server path-containment tests
- **Status:** open · **Priority:** P3 (triggered) · **Area:** `tap_tone_pi/server`
- **Origin:** PR #11 review (DO-98 data-root authorization).
- **Context:** `_safe_directory` containment relies on `Path.resolve()` +
  `is_relative_to`, which is platform-sound (different drives → not relative →
  HTTP 400), and CI runs on Ubuntu. There is no explicit coverage for
  Windows-only path shapes: drive-letter differences, UNC paths
  (`\\server\share`), case-insensitive comparisons, and junctions/reparse points.
- **Trigger:** promote to P1 and add tests if Windows becomes a **supported
  server deployment target** (not merely a dev environment).
- **Acceptance:** parametrized tests asserting containment/rejection for
  cross-drive, UNC, mixed-case, and junction-escape cases, guarded so they skip
  cleanly on non-Windows runners.

### B-002 — Export `output_dir` write-target authorization
- **Status:** open · **Priority:** P2 · **Area:** `tap_tone_pi/server`
- **Origin:** PR #11 review (DO-98). DO-98 governs **read** authorization only;
  filesystem-write authorization was explicitly out of scope
  (see the DO-98 note in `docs/dev_orders/CURRENT.md`).
- **Context:** `/export/{id}` takes an `output_dir` write target that is
  intentionally **not** confined to the data root (documented in README under
  "HTTP API server"). For untrusted callers this is a write-traversal surface;
  it is currently treated as trusted-operator input.
- **Decision needed:** whether writes should be confined to the data root, to a
  separate configurable **export root**, or remain unconstrained-by-design.
- **Acceptance:** an explicit, documented write-authorization policy plus tests
  for the chosen behavior — or a recorded decision to leave it unconstrained.

### B-003 — Language policy for guided-laboratory operator prose
- **Status:** open · **Priority:** P2 · **Area:** `tap_tone_pi/guided_lab`, `ci`
- **Origin:** DO-100 (guided laboratory foundation).
- **Context:** `ci/check_guidance_language.py` scans `tap_tone_pi/agent`,
  `tap_tone_pi/agentic`, `tap_tone_pi/wolf`, and `analyzer/guidance` for
  authority-claiming language. `tap_tone_pi/guided_lab` is **not** in its scan
  roots, and DO-100 deliberately did not add it: guided-laboratory prose is
  procedural instruction rather than post-verdict advisory guidance, so its
  vocabulary and false-positive profile differ. The existing term list would
  fire on ordinary workflow wording — DO-100's own `verify_earlier_measurement`
  purpose and its `provisional`/`validation` phrasing are examples. Boundary
  language is currently covered by a workflow-specific test
  (`tests/test_guided_lab_plate_setup_workflow.py::TestBoundaryLanguage`),
  which asserts the absence of conclusion phrases such as "target thickness",
  "remove wood", and modal-identification claims.
- **Decision needed:** whether guided-laboratory operator prose warrants a
  dedicated language-policy scanner, an extension of the existing
  guidance-language check with a separate term list, or continued reliance on
  per-workflow tests.
- **Trigger:** a second or third shipped workflow, at which point per-workflow
  boundary tests start duplicating each other.
- **Acceptance:** a recorded decision, plus the scanner or the extension if one
  is chosen.

### B-004 — Migration path for persisted guided-laboratory sessions
- **Status:** open · **Priority:** P2 · **Area:** `tap_tone_pi/guided_lab`,
  `contracts`
- **Origin:** DO-100 (guided laboratory foundation).
- **Context:** `contracts/guided_lab_session_v1.schema.json` is now a published
  contract, and `GuidedLabSessionV1.from_dict` rejects any `schema_version`
  other than `guided_lab_session_v1` and any field it does not know. That is
  deliberate — a record this version cannot faithfully hold should fail loudly
  rather than load with pieces missing — but it means a `v2` leaves every `v1`
  record unreadable, and a session may only run against the exact workflow
  version it was started under. DO-100 shipped no migration tooling, and none
  is needed while one schema version and one workflow version exist.
- **Decision needed:** whether session records get a migration path (an
  upgrade function per version step, or a reader that accepts a range), whether
  workflow definitions get one independently, and what happens to an in-flight
  session when its workflow is superseded — carry on under the old definition,
  or refuse and require a fresh run.
- **Trigger:** the first `guided_lab_session_v2`, or the first
  `plate_measurement_setup` v2 — whichever comes first.
- **Acceptance:** a recorded decision, plus the upgrade path and its round-trip
  tests if one is chosen.

### B-005 — Reconcile overlapping UncertaintyBudget implementations
- **Status:** open · **Priority:** P2 · **Area:** `tap_tone_pi/uncertainty`,
  `tap_tone_pi/core`
- **Origin:** DO-101A (empirical model contract foundation).
- **Context:** the repository has two `UncertaintyBudget` types —
  `tap_tone_pi.uncertainty.budget.UncertaintyBudget` and
  `tap_tone_pi.core.statistics.UncertaintyBudget`. DO-101A deliberately did
  not choose either as the empirical canonical type; empirical contracts
  reference uncertainty only via opaque identifiers and a summary
  (`UncertaintyReference`). Embedding a budget into an empirical model before
  reconciliation would freeze the wrong authority.
- **Trigger:** before any empirical model (or DO-101B registry surface)
  embeds a canonical uncertainty budget object, or before a Dev Order needs
  a single shared budget type across packages.
- **Acceptance:** one recorded ownership decision (merge, adapt, or keep
  both with explicit roles), plus migration notes so empirical contracts can
  reference a stable budget identity without a third implementation.

### B-006 — Preliminary hardware campaign (deferred execution gate)
- **Status:** open · **Priority:** P1 (blocked on hardware) · **Area:**
  `tap_tone_pi/grant_readiness`, measurement
- **Now defined as DO-103.** The handoff at
  `docs/dev_orders/DO-103_HARDWARE_MEASUREMENT_ARCHITECTURE.md` is merged and
  authorized, so this gate is a Dev Order rather than a backlog item. DO-103
  Stage 3 — the Phase 2 ingestion path and the provenance-derived `HARDWARE`
  claim — is complete and frozen ahead of the campaign. The gate itself stays
  **open**: Stage 3 built the path that will carry the evidence and produced
  none of it.
- **Origin:** DO-102 Stage 9, deferred by ruling rather than by oversight.
- **Context:** DO-102 built the contracts, the audit, the analysis path, and the
  reporting, and proved all of it against deterministic non-hardware fixtures.
  No hardware campaign was executed, so every hardware-dependent capability is
  recorded `NOT_VERIFIED_ON_HARDWARE` and every study the repository can
  currently produce is labelled `FIXTURE` or `SYNTHETIC`.
- **Trigger:** the Pi, microphone, and contact-drive setup are physically
  available together.
- **Acceptance:** the bounded experiment in
  `docs/NSF_TTP_PRELIMINARY_EXPERIMENT.md` executed and witnessed; every WAV,
  run record, failed run, and analysis result preserved; a study written with
  `--evidence-origin HARDWARE`; and the affected capabilities moved off
  `NOT_VERIFIED_ON_HARDWARE`. Synthetic or fixture data may not be substituted.

### B-007 — Reconcile the duplicated Chladni implementation
- **Status:** open · **Priority:** P2 · **Area:** `tap_tone_pi/chladni`,
  `modes/chladni`
- **Origin:** DO-102 capability audit, which recorded
  `chladni_pattern_indexing` PARTIAL for this reason.
- **Context:** `CLAUDE.md` and the capability inventory name
  `tap_tone_pi.chladni` as canonical, but `tests/test_chladni_policy.py` and
  `tests/test_chladni_pipeline_integration.py` exercise the legacy
  `modes/chladni` copy. Two implementations exist and the tested one is not the
  one documented as canonical. The same split affects WAV reading, where the
  reader under test is `modes/_shared/wav_io.py`.
- **Trigger:** any substantive change to Chladni indexing, or a decision to
  retire `modes/`.
- **Acceptance:** one canonical implementation, tests pointing at it, and the
  capability status revisited.

### B-008 — Dedicated coverage for damping/Q and multi-tap statistics
- **Status:** open · **Priority:** P2 · **Area:** `tap_tone_pi/damping`,
  `tap_tone_pi/multitap`
- **Origin:** DO-102 capability audit (`damping_q_estimation` EXPERIMENTAL,
  `multitap_statistics` PARTIAL).
- **Context:** both are covered only indirectly, through
  `tests/test_production_physics.py`. Neither has a dedicated test module, and
  no workflow drives repeated taps end to end. Damping is one of the quantities
  a luthier would most want, and its current status does not support reporting
  it as a measurement (risk R7).
- **Trigger:** either capability entering an NSF claim, or the hardware campaign
  producing repeated-tap data.
- **Acceptance:** dedicated test modules, and the statuses revisited against the
  new evidence.

### B-009 — E1 force-channel conditioning is unowned and unspecified
- **Status:** open · **Priority:** P1 · **Area:** `docs/hardware/`
- **Origin:** DO-104P hardware selection.
- **Context:** the E1 force chain needs a transducer *and* its conditioning
  selected together, and neither exists. The conditioner's output must land
  inside the HiFiBerry ADC's ±3 V window (0.8–2.1 Vrms optimal); a conditioner
  with ±5 V or ±10 V full scale needs an attenuator as its own BOM line rather
  than software scaling. Whether `ATTEN-001` exists at all is genuinely open
  until a conditioner is chosen.
- **Update (DO-104S, 2026-08-25):** the specification half is answered. A
  208C01 into a 480C02 puts 1.124 V peak into a 2.1 Vrms maximum at the
  recommended exciter's full force, so `ATTEN-001` is **not required by that
  pairing** and stays conditional rather than struck - a larger exciter brings
  it back. Both parts are `RECOMMENDED`, not `SELECTED`. The unowned half is
  untouched: ownership is `UNKNOWN` and no purchase is authorized.
- **Trigger:** an authorized E1 hardware budget.
- **Acceptance:** `FORCE-001` and `PRECOND-001` reach `SELECTED` with a resolved
  output window, and `ATTEN-001` is either specified or struck.

### B-010 — OPA1612 preamp board existence unconfirmed
- **Status:** open · **Priority:** P2 · **Area:** `docs/hardware/`
- **Origin:** DO-104P inventory.
- **Context:** the authoritative stack specification *specifies* the OPA1612
  balanced mic preamp in detail but names no product, and the repository holds no
  evidence the board was ever built. If it has not been, E1 needs it fabricated
  or substituted, and that is a lead-time item nobody has costed.
- **Trigger:** hardware inventory confirmation.
- **Acceptance:** `PREAMP-001` reaches `RECEIVED` with an asset label, or a
  fabrication task is scoped.

### B-011 — Microphone model was never locked
- **Status:** open · **Priority:** P2 · **Area:** `docs/hardware/`
- **Origin:** DO-104P inventory.
- **Context:** the stack specification gives microphone *requirements* (SDC,
  48 V phantom, approx −40 dBV/Pa) but never selected a model, which the BOM now
  records honestly as `TBD` rather than implying a choice exists. Traceability
  stays `UNKNOWN` unless a calibrated microphone is procured, and E1 makes no
  calibrated-pressure claim either way.
- **Update (DO-104S, 2026-08-25):** an Earthworks M23 G2 is `RECOMMENDED` for
  the preferred tier and a GRAS 46AE for reference grade. The two are not
  interchangeable: the 46AE is CCP-powered and cannot use the OPA1612 phantom
  stage at all, so choosing it moves the microphone onto the force conditioner.
  Traceability remains `UNKNOWN` for both unless a certificate is supplied.
- **Trigger:** E1 procurement.
- **Acceptance:** `MIC-001` reaches `SELECTED`.

### B-012 — `schema-registry-guard` workflow has been red since at least 2026-08-12
- **Status:** open · **Priority:** P2 · **Area:** `.github/workflows/`
- **Origin:** observed while merging PR #27.
- **Context:** the workflow has failed on every push back to at least `b0adc53`,
  reports its own file path as its name (which is what GitHub does when a
  workflow file cannot be parsed), and is explicitly excluded from pre-commit's
  `check-yaml`. It predates all DO-102/103/104 work and no order touched it. A
  permanently red check that nobody reads is worse than no check.
- **Trigger:** whichever order owns CI hygiene.
- **Acceptance:** the workflow parses and passes, or is removed with a reason.

### B-013 — Nine CLI tests failed at `caa4d18` and no longer reproduce
- **Status:** open · **Priority:** P3 · **Area:** `tests/test_cli_*`
- **Origin:** baseline classification during DO-104.
- **Context:** `test_cli_list_directive_events`, `test_cli_measure_agent_output`,
  and `test_cli_measure_ftue_wiring` failed in a clean worktree at `caa4d18` and
  passed on every run after the DO-103 merge. Something is order- or
  state-dependent, which means the baseline classification cited in PR #26 is
  less stable than it read.
- **Trigger:** any order touching the CLI, or a recurrence.
- **Acceptance:** the flakiness is explained or the tests are made deterministic.

---

**Not pre-authorized.** Formal Gage R&R, environmental characterization, a
reference-laboratory campaign, and standardized excitation hardware are all
named in DO-102 as out of scope. They become backlog items only if measured
evidence calls for them — not because a grant narrative would like to cite them.

---

### B-014 — The E1 ADC has no anti-aliasing filter in its input path

- **Status:** open · **Priority:** P1 · **Area:** `docs/hardware/`, `tap_tone_pi/capture/`
- **Origin:** DO-104S, reading the HiFiBerry datasheet at the level the force
  chain needed.
- **Context:** the vendor states there is no anti-aliasing filter in the input
  path and offers it as a recording-bandwidth feature. For a measurement
  instrument it means energy above Nyquist folds back into the analysis band and
  arrives indistinguishable from real content. This is a property of the board
  already in the design, so it applies to Phase 2A captures too — not only to the
  E1 force chain that surfaced it. The transducer's own 36 kHz limit helps at
  96 kHz but does not bound broadband contact noise.
- **Not affected by the DO-104R census (2026-08-27).** Not owning the board says
  nothing about whether aliasing is acceptable. This closes only on measurement.
- **DO-106 (2026-08-27) built the evidence path, and did not close this.** E0's
  T4 produces the folding table a filter requirement is *derived from*; deriving
  it is a separate document and a human's judgement. The checker is explicitly
  forbidden from closing this item, and a test asserts that a T4 section existing
  is not an aliasing answer. Closes only when a front end exists and is measured.
- **Trigger:** E1 bench work, or any claim about usable bandwidth.
- **Acceptance:** excitation bandwidth is limited and recorded per run, the
  residual is characterized by measurement rather than assumed negligible, and
  external filtering is either shown unnecessary or added as its own BOM row.

### B-015 — The design-baseline ADC is superseded by its vendor

- **Status:** open · **Priority:** P2 · **Area:** `docs/hardware/`
- **Origin:** DO-104S market research.
- **Context:** HiFiBerry describes the DAC+ ADC Pro as superseded by the DAC2
  ADC Pro and available in larger quantities for OEM customers on request. It is
  still purchasable at $64.90 (checked 2026-08-25). The whole E1 level budget and
  the architecture gate verdict rest on the DAC+'s published input specification;
  the successor does not publish one on its product page and was not verified.
- **Made more pressing by the DO-104R census (2026-08-27).** The board is not
  owned, so it must be acquired — and it is the one the vendor has superseded.
  There is no unit in hand to use while the successor is evaluated.
- **DO-106 (2026-08-27) imported a lead, not evidence.** The stack BOM §5.7
  records that distributors identify the successor's converters as a PCM5122 and
  PCM1863, which would move the input characteristics into a TI datasheet and
  make the architecture gate re-runnable against a manufacturer document. It is
  distributor-sourced and does not meet the datasheet-manifest standard. **A lead
  for closing this item, not a closure.** E0 characterizing the current board
  badly would be a reason to revisit the successor, not to assume it.
- **Trigger:** procurement, or the DAC+ becoming unobtainable.
- **Acceptance:** either the DAC+ is procured while available, or the successor's
  input specification is obtained and the E1 architecture gate is re-run against
  it before any substitution.

### B-016 — No physical possession census has ever been run

- **Status:** **closed** (2026-08-27, DO-104R) · **Priority:** P1 · **Area:** `docs/hardware/`
- **Closed by:** the census in
  [`TTP_E1_OWNERSHIP_CENSUS.md`](docs/hardware/TTP_E1_OWNERSHIP_CENSUS.md),
  performed 2026-08-27 by operator attestation. All ten required categories
  resolved to `CONFIRMED_ABSENT`: no E1-relevant hardware is possessed. The
  finding this item recorded was "no census performed"; a census has now been
  performed. **Corrected 2026-08-27 by pass 2**, which found a false absence on
  `HOST-001` — see B-017. Correcting a census does not un-perform it, so this
  stays closed; the reliability of the *method* is B-017's problem, not this
  item's. No category was left `UNKNOWN`, so there is no residual possession
  question to carry forward.
- **Origin:** DO-104S ownership census, which recorded ten components as
  `UNKNOWN` because that is what is actually known.
- **Context:** `UNKNOWN` means nobody has looked, not that a component is absent,
  and the validator refuses `RECOMMEND_PURCHASE` against it for that reason. Four
  items are the ones a working audio bench most plausibly already has — the host,
  the ADC board, a microphone, and an amplifier — so a purchase order built from
  the DO-104S recommendation before the census could duplicate them.
- **Trigger:** before any E1 purchase.
- **Acceptance:** every census row moves to `CONFIRMED_PRESENT` or
  `CONFIRMED_ABSENT`, with present items carrying identity-register entries.
  **Met.** All ten are `CONFIRMED_ABSENT`; no item is present, so no
  identity-register entry was required or created.

### B-017 — The ownership census produced a false absence

- **Status:** open · **Priority:** P1 · **Area:** `docs/hardware/`
- **Origin:** DO-104R census pass 2, 2026-08-27.
- **Context:** pass 1 attested all ten categories `CONFIRMED_ABSENT`. A Raspberry
  Pi 5 had been in hand since April 2025 — sixteen months. The pass ran on
  `OPERATOR_ATTESTATION`, a statement about a bench rather than a look at one,
  and failed in the one direction that matters: **a false absence is what
  authorizes a purchase.** Had the recommendation been ratified and acted on,
  this would have bought a second Pi.
- **Why no check caught it:** every validator check verifies that the document is
  internally consistent and claims no more than it records. Pass 1 was internally
  consistent and wrong. This is the limit of document validation, and it is why
  `observation_method` is a recorded field rather than an assumed one — the
  weaker evidence was labelled as weaker, and the label turned out to be earned.
- **Trigger:** before any census result is used to authorize a purchase.
- **Acceptance:** the census that gates a purchase decision is performed by
  `DIRECT_PHYSICAL_INSPECTION` — someone handling and reading each item — rather
  than by attestation, or the attestation is corroborated against purchase
  records. Recording the method is not sufficient on its own; the method has to
  be adequate to the decision resting on it.

### B-018 — E0 acquisition integration does not exist

- **Status:** open · **Priority:** P1 · **Area:** `scripts/`, `tap_tone_pi/capture/`
- **Origin:** DO-106, which deliberately shipped no `ttp_e0_adc.py`.
- **Context:** DO-106 provides the E0 protocol, evidence contract, schema,
  checker and results stub. It provides **no way to take the measurements.** The
  existing primitives cover part of the protocol — `calibration.loopback` already
  does sweep generation, latency measurement and frequency response, which
  reaches T3 and T7 — but T1's (fs × PGA) noise grid, T2's gain error and
  input-referred noise, T4's external-source injection, T5's ALSA mixer
  inspection and T6's THD and clip detection have no canonical utility behind
  them.
- **Why it was not half-built:** a command implementing three of seven tests
  would look operational and not be. DO-106 §8 permits splitting exactly this.
- **Trigger:** before E0 is executed, unless the operator intends to run all
  seven tests by hand and assemble the record manually — which is legitimate and
  the checker validates it either way.
- **Acceptance:** a thin orchestration surface covering T1–T7 that delegates
  acquisition and DSP to canonical utilities, or an explicit ruling that E0 is
  run manually. Building a second acquisition engine is not acceptance.

## Not backlog — recorded here only so they aren't mistaken for open items

These are **design properties / accepted tradeoffs**, documented in code/README;
they are not to-dos.

- **`resolve()`-based containment is filesystem-dependent.** Checking containment
  *after* resolving is exactly what defeats symlink escapes; the consequence
  (outcomes depend on live filesystem layout) is inherent and intended.
  Documented in `_safe_directory` and README.
- **CLI `--data-root` bridges through a process-global env var
  (`TTP_SERVER_DATA_ROOT`).** Required so `uvicorn --reload`'s re-imported app
  sees the configured root; mutation is scoped to the run and restored after, and
  bounded by CLI env-restore tests. Accepted design (DO-98).
- **Radiation-ratio interoperability contract (BR-045).** Synchronized with
  Luthier’s Toolbox via `contracts/tonewood_radiation_ratio_v1.json`
  (`tonewood_radiation_ratio` v1, `unscaled_si_derived`, scale factor 1.0).
  Current Tap Tone Pi implementation conforms to V1; no production numerical
  correction was required. BR-043 / BR-044 were Toolbox-side scale defects and
  are not attributed to Tap Tone Pi. See
  `docs/RADIATION_RATIO_INTEROPERABILITY.md`.
