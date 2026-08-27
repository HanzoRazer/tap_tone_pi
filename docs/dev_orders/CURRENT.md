# Active Dev Order

**Current:** DO-104O — E1 Physical Ownership Reconciliation and Procurement
Authorization Gate (**BLOCKED AT THE HUMAN SELECTION GATE**). Its child
execution slice **DO-104R — Ownership Census Intake and Reconciliation is
COMPLETE**: the census was performed on 2026-08-27 and found no E1-relevant
hardware in possession. All ten required categories are `CONFIRMED_ABSENT`,
compatibility reconciliation ran with an empty subject set, and B-016 is closed.
Engineering stops here — the next decision is a human ruling, not a commit
**Next:** the human hardware-selection ruling — `SELECTED`,
`ALTERNATE_SELECTED`, `SELECTION_DEFERRED`, or `RESEARCH_REQUIRED`. Only after
that ruling does DO-104O resume for selection ratification and procurement
authorization. Purchase, receipt, assembly and E1 measurement follow in that
order, none of them yet
**Queued:** DO-105 — E2 Fixed-Point Repeatability (BLOCKED on the E1 gate);
DO-101B — Empirical Registry and Inspection Surface (NOT STARTED)
**Previous:** DO-103 Stages 3 and 3b — Phase 2 ingestion, the
provenance-derived HARDWARE claim, and the campaign software for E1–E5
(COMPLETE, merged as PR #26)

## DO-104 — E1 bring-up, pre-execution

The rig does not exist. No shaker, amplifier, force transducer, interface,
microphone, stinger stock, or tip has been selected, and none is specified in
code or documentation: an invented specification would be invented evidence.

**What landed before the bench work**, on the rule that an evidence-loss defect
must be fixed before the data exists:

- `stinger_mass_g`, `contact_tip_mass_g`, and a separately measured
  `combined_contact_mass_g` on the rig's excitation record. DO-103 §4.9 asked
  for these to be *measured* rather than estimated, and until now there was
  nowhere numeric to put them;
- `reference_structure_id` on the experiment definition. E1 records the rig in
  `instrument_id`, so the body under the stinger had no field at all;
- `sequence_index` on every run, with elapsed-from-first derived. Warm-up,
  contact creep, and transducer drift are only visible in sequence, and
  reconstructing that order later by sorting timestamps is a guess;
- the nominal frequency each run asked for, kept beside the bin that answered
  with the signed offset derived — the same defect that was fixed for
  reciprocity, in the other experiment.

The study schema moved to registry 1.3.0 and the campaign schema to 1.1.0. Both
additive; no existing field changed meaning.

**Deliberately deferred to DO-105:** per-run configuration-constancy
enforcement. During E1 the rig is *supposed* to change — stingers, tips, and
preload are the variables under characterization — so a validator demanding that
every run share one configuration would fight E1's purpose. It belongs to E2,
where the configuration is frozen by definition, and it lands before E2's first
capture.

**Two rules locked rather than left to be reopened:**

- `stinger_mass_g` and `contact_tip_mass_g` are physical component masses;
  `combined_contact_mass_g` is the measured or estimated effective mass
  participating at the specimen interface and is **not** required to equal their
  arithmetic sum. It may legitimately be lower. The only invariant is that all
  three, when present, are finite and non-negative — the software will not check
  one against the others.
- Acquisition order is authoritative as explicitly recorded by
  `sequence_index`; `captured_at` remains separately preserved evidence. A
  disagreement is **reported, not silently repaired** — neither is sorted into
  agreement with the other, because the disagreement may itself be the finding.

**A process change came out of this too.** An end-to-end evidence-path run is
now a mandatory pre-merge gate for every hardware-facing increment, held by
`tests/test_hardware_campaign_evidence_path.py`:
`manifest → ingestion → run → study → campaign → report → checker`, with at
least one rejected run traversing it. Unit tests missed a dropped
`sequence_index` twice; the dry run caught it both times. CLAUDE.md rule 11
records it.

**Not started:** the rig, E1 itself, any capability promotion, and any line of
the risk table.

## DO-104P — hardware selection and procurement

The selection framework exists; no component is selected, ordered, or owned.

**What the repository could establish about ownership.** Nothing. Every captured
session under `runs_phase2/` is `"synthetic": true` with `"device": null`, or the
`DEMO` fixture — so the repository holds no evidence of any physical acquisition
and cannot say what hardware exists. The three components the authoritative stack
specification names (Pi 5, HiFiBerry DAC+ ADC Pro, OPA1612 preamp) are recorded
as **design-selected, ownership unconfirmed**, and
`scripts/check_e1_hardware_bom.py` refuses to let any of them advance to
`RECEIVED` without a serial number or asset label in the identity register. A
design document naming a Raspberry Pi 5 is not a Raspberry Pi 5.

**The architectural finding.** The stack specification and the measurement
architecture had diverged: Phase 2 was documented as speaker-driven with ch0 as a
*reference microphone*, while DO-103/DO-104 need ch0 to carry *measured force*.
Those are mutually exclusive on a two-channel ADC. The specification is now
Revision 1.4, splitting Phase 2A (legacy speaker ODS, retained for provenance)
from Phase 2B (contact drive, the NSF target), with an explicit channel map. The
speaker-distortion-rejected-by-coherence argument is now scoped to 2A only —
in 2B the shaker, transducer, stinger, and tip are mechanically in series with the
specimen, so a stinger resonance is a real feature of the measured system rather
than something coherence removes.

**Force-channel architecture, path A.** IEPE/ICP transducer into a
constant-current conditioner into ch0 of the existing ADC. That preserves the
strongest property of the existing design — simultaneous two-channel acquisition
on one sample clock, which Phase 2's transfer-function path assumes. The
conditioner's output must land inside the ADC's ±3 V window (0.8–2.1 Vrms
optimal); a larger full-scale output needs attenuation designed in as its own BOM
line, not scaled away in software. Paths B (charge amp), C (load cell) and D
(replacement interface) are recorded as alternates, not investigated equally.

**No budget is invented.** Selection carries three tiers — research minimum,
preferred E1, reference-grade candidate — with preferred E1 driving the
recommendation until a ceiling is imposed. The tiers differ in sensor quality,
never in whether force is measured: a cheap exciter driven at a commanded level
is not a cheaper tier, it is a different and unacceptable experiment.

**Deliberately not done:** product selection. Current availability, pricing,
conditioning requirements, mounting threads, and lead time matter too much here
for stale product knowledge, so candidate research is a separate web-researched
pass over complete functional chains — force, drive, and response — rather than
isolated parts.
**Previous:** DO-102 — NSF TTP Grant-Readiness Evidence Foundation (COMPLETE)
**Deferred evidence gate:** `SPRINTS.md` B-006 — witnessed hardware measurement
campaign, now formally defined as DO-103

## DO-103 Stage 3 — promoted, and only Stage 3

`docs/dev_orders/DO-103_HARDWARE_MEASUREMENT_ARCHITECTURE.md` is merged and
authorized, which satisfies the condition its Status section names and makes
B-006 a defined Dev Order rather than a backlog gate. **What is promoted is
Stage 3 alone**, not the order as a whole.

Stage 3 is promoted ahead of DO-101B on sequencing, not merit. It is
time-order sensitive in a way DO-101B is not: DO-103 §13 requires the ingestion
path and the provenance-derived HARDWARE claim to be written and tested
**before** any instrument data is collected, so the campaign is not analyzed by
software written to fit the data it produced. DO-101B improves discoverability
of empirical models and is unblocked whenever it is resumed; nothing about it
degrades by waiting, and it is better defined once the provenance semantics
below are settled.

**In scope for Stage 3:**

- a Phase 2 transfer-function ingestion path in `tap_tone_pi/grant_readiness/`,
  alongside — not replacing — the existing `phase1_tap_analysis_v1` path (§5.1);
- acquisition provenance recorded per run, and the `HARDWARE` claim **derived**
  from it rather than accepted as a caller's label (§5.4);
- negative tests that a false `HARDWARE` claim cannot be made to validate;
- freezing both before the physical campaign begins.

### Stage 3 outcome

All four in-scope items landed. `tap_tone_pi/grant_readiness/phase2_experiment.py`
reads the persisted Phase 2 transfer document as a document — no DSP, no import
of the Phase 2 package or of anything under `scripts/`. `AcquisitionProvenanceV1`
carries what a physical session can attest and a fixture cannot, and `NSF-306`
refuses a `HARDWARE` origin nothing backs, which closes the gap DO-102 left:
until now a caller could assert `HARDWARE` over any data that merely lacked a
demo flag. `NSF-307` keeps *witnessed* as the stricter standard §10 promotes on,
and `NSF-308` refuses a mechanical frequency-response name over an acoustic
pressure response (§6.6). 108 new tests, most of them negative.

The study schema gained an additive optional `acquisition` block on runs and its
registry entry moved to 1.1.0. No existing field changed meaning; the Phase 1
path is untouched.

One boundary test was rewritten with justification: DO-102's "the package never
mentions `phase2_ods_snapshot`" was a proxy for "authors no existing measurement
schema", and §5.1 made the proxy wrong while leaving the claim true. It is now
asserted directly, and the substantive guards — forbidden imports, no DSP, no
capture — are unchanged.

**Not in scope for Stage 3, and not started by it:** Stages 1, 2, and 4–8 —
building and grounding the rig, E1–E5, capability promotion off
`NOT_VERIFIED_ON_HARDWARE`, and the §8 risk-coverage fill-in. Those need
hardware that does not yet exist. No capability status changes in Stage 3, and
no study in this repository becomes hardware evidence by it.

## DO-103 Stage 3b — the rest of the pre-hardware software

Stage 3b finishes the software the campaign needs, on Stage 3's rule and for
Stage 3's reason: it exists before the rig, so no part of the campaign is
analyzed by code shaped to fit what the campaign produced.

**In scope for Stage 3b:**

- additive rig identity, channel sensitivity and calibration traceability, and a
  per-run `CampaignConditionV1` — the three meanings §9 says the DO-102
  container cannot carry (an attachment, a point pair, a measured mass);
- `hardware_campaign.py`: the E2–E5 groupings, reciprocity pairing and
  residuals, mass-loading deltas, and the campaign record;
- `contracts/ttp_hardware_campaign_v1.schema.json` and the study schema's
  additive bump to registry 1.2.0;
- `scripts/ttp_hardware_campaign.py` and the read-only
  `scripts/ttp_hardware_campaign_check.py`;
- `docs/NSF_TTP_HARDWARE_CAMPAIGN_PROTOCOL.md`, and a results document that says
  `NOT EXECUTED` because it is.

### Stage 3b outcome

247 new tests across five files, plus structural guards added to the
boundary suite, weighted toward the negative cases: an unmeasured mass, a
reciprocity direction with no transpose, a host path offered as an artifact
identity, a traceability claim with nothing behind it, a campaign that says
executed with nothing executed. The `NSF-5xx` family carries them and every code
in it is exercised.

Review added two changes before the software was called done, both of the
"cannot be fixed after data exists" kind. A reciprocity pair now records **both**
directions' evaluation frequencies and derives the gap, so an asymmetry is
visible in the pair rather than only inside the two runs. And the campaign status
no longer uses one word for two situations: `FIXTURE_EXECUTED` and
`HARDWARE_EXECUTED` are separate states, per-experiment outcomes have their own
vocabulary, each executed outcome summarizes its study's origin and witnessed
status, and the checker re-derives both from the studies and reports any
disagreement.

Two things it deliberately does not contain. There is **no acceptance threshold
anywhere** — not for reciprocity, not for mass loading — which a boundary test
now asserts structurally against the module's own definitions rather than its
prose. And **no capability is promoted**: the campaign report states what its
evidence would support and says plainly that promotion is a separate,
per-capability decision it does not make. The repository's campaign document is
`NOT_EXECUTED`, every study it can produce is still `FIXTURE` or `SYNTHETIC`,
and R10 remains open.

**Not in scope for Stage 3b, and not started by it:** the physical stages. No
rig was built, no experiment was run, no capability status changed, and no line
of the §8 risk table was filled in.

DO-101B remains **queued, not displaced or cancelled** — it was deferred behind
DO-102 because NSF readiness was time-sensitive on the August path, not because
it was deprioritized on the merits, and it is deferred again here for the
ordering reason above. It has not been resumed, so its promotion still belongs
to its own first docs/status commit.

> **DO-101A — Empirical Model Framework Foundation (COMPLETE)**
>
> Merged as **PR #19** → `main` merge commit
> `5793309cd268e7a2fe0ad92c5384cdae547e224c` (branch
> `cursor/do-101a-empirical-contract-foundation-b1ad`, tip feature commit
> `b71ab4b`). Framework ownership is documented at
> `docs/EMPIRICAL_MODEL_FRAMEWORK.md` and `docs/ADR-0013-empirical-model-framework.md`.
>
> **Delivered:** `tap_tone_pi/empirical/` shared contract layer
> (`EmpiricalModelDefinitionV1`, inputs/outputs, validity domain, evidence /
> measurement / calibration / uncertainty references, validation envelope);
> stable `EMP-*` error vocabulary; pure validation; deterministic
> schema-strict serialization; `contracts/empirical_model_definition_v1.schema.json`
> plus `schema_registry.json` entry; luthiery compatibility adapters and
> re-exports so existing luthiery imports and serialized payloads remain
> unchanged. Uncertainty is referenced only
> (`uncertainty_model_id` / `uncertainty_record_id` / `uncertainty_summary`) —
> no third `UncertaintyBudget`. Overlapping budget implementations are
> deferred as `SPRINTS.md` **B-005**.
>
> **Deliberate non-goals (remain for DO-101B / later):** empirical registry
> discovery, `ttp empirical` CLI, registry-entry schema, MB Sound / corpus
> ingestion, calibration fitting, calculator changes, advisory logic, and
> uncertainty-budget reconciliation.
>
> DO-101A **COMPLETE**. Full DO-101 is **not** complete until DO-101B also
> lands. DO-101B is **not** promoted in this closure — promotion belongs to
> DO-101B's first docs/status commit.

> **DO-102 — NSF TTP Grant-Readiness Evidence Foundation (COMPLETE)**
>
> **Merged as PR #22** → `main` merge commit `3d2eb69`, carrying the eight-commit
> series `0f29691`…`8d0036d` plus one review-fix commit `16ac80d`. Branch
> `feat/do-102-nsf-ttp-grant-readiness`, base `9d58dd1`. DO-102 **COMPLETE**.
>
> **Review findings, both real and both fixed before merge** (`16ac80d`):
> - `report._guard_origin` reimplemented the evidence-origin invariant instead of
>   delegating to `validate_study_evidence_origin`, and the duplicate had already
>   drifted from the original *within the same PR*: the renderer refused a
>   HARDWARE label over non-hardware runs but let a FIXTURE label over a hardware
>   run through, which the validator rejected. The renderer now delegates, so
>   both directions are refused by one rule rather than two copies of it.
> - `RepeatabilityStudyV1.from_dict` silently ignored the persisted derived
>   counts (`valid_run_count`, `rejected_run_count`, `rejection_counts`) rather
>   than checking them, so a payload whose counts contradicted its runs loaded
>   without complaint. It now rejects the contradiction; canonical `to_dict`
>   payloads still round-trip.
> - The `report.py` docstring overclaimed. Its wording guarantee covers the
>   module's own generated prose; caller-supplied free text — limitations,
>   identifiers — is rendered verbatim. No prohibited-phrase filter was added,
>   deliberately: a legitimate limitation such as "not validated against a
>   reference" must stay expressible.
>
> **Verification at merge:** full suite 4517 passed / 2 failed (both documented
> baseline, in `scripts/phase2/tests/`, reproducing on base); NSF focused suite
> 660 passed on merged `main`; capability audit clean; advisory boundary clean
> in `--strict`.
>
> **Implementation branch:** `feat/do-102-nsf-ttp-grant-readiness`, rebased onto
> `main` at `9d58dd1` (base SHA) after DO-101A (PR #19/#20) and BR-045 (PR #21)
> landed. **Predecessor:** DO-101A (COMPLETE). **Queued behind this order:**
> DO-101B.
>
> The series was originally cut from `e2247a9` plus a local DO-100 closure
> commit. That closure was redundant — DO-100 had already been closed upstream
> by **PR #18** — so it was dropped in the rebase and PR #18 is authoritative.
> This branch carries eight commits and no lifecycle work but its own.
>
> **Objective:** convert the repository into a defensible evidence base for one
> focused R&D question — whether an affordable, portable measurement system can
> produce repeatable, uncertainty-qualified, reference-valid structural-acoustic
> measurements under realistic shop conditions. Grant-readiness *evidence*, not
> grant prose and not a feature sprint. **NSF submission is not part of this
> order.**
>
> ### Revised hardware clause
>
> DO-102 establishes the contracts, audit tooling, repeatability-analysis path,
> and grant-readiness reporting needed for the preliminary experiment. Because
> no hardware campaign is executed in this order, the repository must record the
> relevant capability as `NOT_VERIFIED_ON_HARDWARE`, and all tests using fixture
> or synthetic data must identify that data as non-hardware evidence. The
> physical repeatability campaign remains a separately witnessed execution
> stage.
>
> ### Corrected acceptance criteria
>
> Acceptance Criterion 5 of the original handoff — "At least one real
> experimental dataset can be represented by the new contract" — is **replaced**
> by:
>
> > The contract and analysis path are proven against deterministic
> > non-hardware fixtures, and the system can ingest a real hardware dataset
> > without schema or architecture changes once the campaign is executed.
>
> And a criterion is **added**:
>
> > No generated report may represent fixture or synthetic data as hardware
> > evidence.
>
> Stage 9 moves from "required in this sprint" to a **deferred execution gate —
> Preliminary Hardware Campaign**: it begins only when the Pi, microphone, and
> contact-drive setup are physically available, produces the first witnessed
> hardware dataset, and updates the grant-readiness evidence from
> `NOT_VERIFIED_ON_HARDWARE` to observed status.
>
> ### Delivered
>
> `tap_tone_pi/grant_readiness/` — contracts, `NSF-*` error vocabulary, pure
> validation, descriptive statistics, the declared capability inventory, the
> repository audit, the Phase 1 repeatability analysis path, deterministic
> reporting, the risk register, and the Project Pitch source builder.
> `contracts/nsf_grant_readiness_audit_v1.schema.json` and
> `contracts/ttp_preliminary_repeatability_study_v1.schema.json`, registered
> under a new `grant-readiness-team` owner without reorganizing the registry.
> Three scripts under `scripts/`; no `ttp nsf` CLI namespace. Five documents
> under `docs/NSF_TTP_*.md`. Generated artifacts go to `out/nsf/`, which is
> already gitignored.
>
> **Structural guarantees, not documented intentions:**
> - `RepeatabilityMetricV1` has no acceptance flag, threshold, or verdict field.
>   The DO-085 gate stays in `core.repeatability`; a study cross-references that
>   evidence by identifier and never inherits it.
> - Every run and study carries an `EvidenceOrigin` with no default. Only
>   `HARDWARE` answers `is_hardware_evidence`, both report builders refuse to
>   render a mislabelled study (`NSF-305`), and a result marked `demo: true`
>   cannot be recorded as `HARDWARE`.
> - `ExcitationContextV1` records the mechanical arrangement generically.
>   `manual_tap` is one value among `instrumented_hammer`, `shaker_stinger`, and
>   `acoustic_drive`; the default is `unspecified`; an unlisted method is
>   recorded verbatim. Compatible with the grounded shaker/stinger architecture
>   without implementing it.
> - Statistics delegate mean, sample SD (Bessel, n−1), CV, and range to
>   `core.statistics.compute_repeatability`. The zero-mean CV sentinel of `0.0`
>   is refused (`NSF-304`) rather than published.
> - Rejected runs are counted, never summarized. Rejection reasons come from the
>   quality gate's own rule identifiers, not from inference.
> - `tests/test_nsf_capability_baseline.py` was written before the package
>   existed and the production inventory must match it entry for entry, so the
>   audit cannot be rewritten to agree with itself.
> - The capability denominator stays at **25**. The empirical model framework
>   (DO-101A) and the tonewood radiation-ratio contract (BR-045) landed after
>   the inventory was bounded. Both are recorded in the technical baseline under
>   *Supporting Scientific Infrastructure Landed After Initial Audit* and added
>   to the regression scope, but neither is counted as an instrument capability:
>   counting shared contract infrastructure would drift the baseline from "what
>   can the analyzer presently do" toward "what infrastructure exists anywhere in
>   the repository", which is the weaker claim.
> - The deferred hardware campaign is tracked as `SPRINTS.md` **B-006**; the
>   Chladni duplication as **B-007**; damping and multi-tap coverage as **B-008**.
>
> ### Ratified capability inventory
>
> 25 instrument-level capabilities: **19 IMPLEMENTED, 2 EXPERIMENTAL, 4 PARTIAL,
> 0 PLANNED, 0 hardware-verified.**
>
> `audio_capture` and `controlled_excitation` are recorded PARTIAL by human
> ratification. The audio path is exercised only with simulated input, and
> `ExcitationContractV1` describes driven electrical excitation through an
> output device — the speaker-air approach since superseded — while the grounded
> shaker and stinger contact drive is not built. `desktop_analyzer` stays
> IMPLEMENTED with an explicit *software UI only; intended hardware workflow not
> witnessed* note.
>
> **Hardware verification status:** none of the 25 audited capabilities has been
> witnessed end-to-end on the intended TTP hardware configuration during DO-102.
> Software implementation status and hardware verification are tracked
> independently.
>
> ### Deviations from the handoff, all deliberate
>
> `RejectionReason` adds `QUALITY_GATE_REJECTED`, because the Phase 1 contract
> emits a bare `fail` verdict and inferring clipping or a low signal from it
> would invent a cause the evidence does not support. The metric field the
> handoff calls `range` is `range_value`, matching
> `core.statistics.RepeatabilityMetrics` rather than shadowing a builtin. Six
> error codes the handoff requires rejections for but names no code for are
> added: `NSF-104` (duplicate capability ID), `NSF-105` (unresolved evidence
> path), `NSF-106` (invalid hardware verification), `NSF-206` (experiment ID
> mismatch), `NSF-207` (non-UTC timestamp), `NSF-305` (evidence origin
> misrepresented). `EvidenceOrigin`, `ExcitationContextV1`, and `inventory.py`
> are additions the handoff does not name; each exists to make a DO-102 rule
> structural rather than documented.
>
> ### Baseline test failures
>
> Two reproduce against `main` at `9d58dd1` and are unrelated to this work:
> `test_validate_viewer_pack_v1_real_sessions` on
> `runs_phase2/session_20260101T234237Z` and `…235209Z`, both failing on
> `manifest.contents missing required keys: ['bending']`. Both live in
> `scripts/phase2/tests/`, outside `tests/`, so `pytest tests/` does not collect
> them.
>
> The third entry the ledger carried, `test_advisory_in_calibration_is_error`,
> **passes** — re-verified against the rebased tree. It is stale and is not
> carried forward; the "Pre-existing test failures (baseline)" section below is
> corrected accordingly. PR #18 closed DO-100 but did not touch that list, so
> this correction is DO-102's and not a duplicate of upstream work.
>
> ### Not done, deliberately
>
> No hardware campaign. No capture mode on any DO-102 script. No Phase 2
> coherence in the first study — that would create a second measurement
> architecture before the first is characterized. No Gage R&R, no environmental
> correction, no reference-laboratory contact, no customer discovery, no budget,
> no submission.
>
> **Next, and not part of this order:** the preliminary hardware campaign
> (`SPRINTS.md` B-006) is the deferred execution gate that turns this evidence
> layer into hardware evidence. Until it runs and is witnessed, every capability
> stays `NOT_VERIFIED_ON_HARDWARE` and every study this repository can produce is
> labelled `FIXTURE` or `SYNTHETIC`.

> **DO-100 — Guided Digital Laboratory Foundation (COMPLETE)**
>
> Merged as **PR #16** → `main` merge commit
> `6ca0105ecc3535dfeeb13f565df92b62ccc105ab` (branch
> `feat/do-100-guided-digital-laboratory`, feature commit
> `f398f52b498da4a2d17607e7856a683d18efe7db`). Authoritative handoff remains
> at `docs/dev_orders/DO-100_GUIDED_DIGITAL_LABORATORY.md` (placed via PR #15).
>
> **Delivered:** `tap_tone_pi/guided_lab/` (contracts, error vocabulary, pure
> definition validation, deterministic engine, builder-intent catalog, thin
> CLI); reference workflow `plate_measurement_setup` v1 (19 nodes, 21
> transitions); `contracts/guided_lab_session_v1.schema.json` plus
> `schema_registry.json` entry; `guided-lab` on the unified CLI with isolated
> registration so a guided-laboratory defect cannot stop unrelated `ttp`
> commands.
>
> **Deliberate non-goals (remain for later orders):** session persistence
> layer, GUI, server endpoint, workflow-version migration, and an adapter
> between `tap_tone_pi.guided_lab` and existing `tap_tone_pi.workflow`
> measurement contracts.
>
> DO-100 **COMPLETE**.

> **DO-99 — Server Authorization Observability & Diagnostics (COMPLETE)**
>
> Depends on **PR #10** + **PR #11** (both merged to `main`). Branches from `main`
> (`fix/server-authz-observability`). **Diagnostics only — no authorization
> decision changes; all DO-98 tests pass unchanged.**
>
> **Scope:** make the filesystem-authorization layer observable without exposing
> host paths — structured events + a status endpoint.
>
> **Delivered:**
> - `tap_tone_pi.server.authz` logger emits one path-free `AuthorizationEvent`
>   per authorization call (frozen dataclass via `extra=`): allowed→DEBUG,
>   OUTSIDE_ROOT/SYMLINK_ESCAPE→WARNING, INVALID_ROOT/PATH_RESOLUTION_FAILURE→ERROR.
> - `OUTSIDE_ROOT` vs `SYMLINK_ESCAPE` distinguished by a diagnostic-only lexical
>   check (decision unchanged); `INVALID_ROOT` emitted at `create_app` before the
>   `ValueError` re-raises; `PATH_RESOLUTION_FAILURE` emitted then original
>   exception re-raised unchanged (no HTTP conversion).
> - `_safe_directory(directory, *, endpoint, input_role)`; fields `endpoint`,
>   `input_role`, `request_path_type` kept separate.
> - `GET /server/status` → `policy_version="filesystem-auth-v2"`, `configured`,
>   `root_digest=sha256(root)[:12]`, `started_at`; no host-path disclosure.
> - No raw request/resolved/root path or exception text ever logged (only an
>   exception class name where relevant).
>
> Commit sequence on branch: `521d39d` (tests), `c21b37b` (implementation),
> `986d6e5` (docs).
> Merged as **PR #13** → `main` merge commit
> `ec9f93a362249cee037766c06e767b38c1a4b1e0` (branch
> `fix/server-authz-observability`). A review follow-up merged as **PR #14**
> (`fix/do99-review-followup`). DO-99 **COMPLETE**.

> **DO-98 — COMPLETE**
>
> Merged as **PR #11** → `main` commit `79c2d36` (branch
> `fix/server-data-root-authorization`, off `d8010dd`).
> Replaced the fixed `Path.cwd()` anchor with a configurable data root and unified
> containment for relative *and* absolute request paths across `/grids`,
> `/sessions`, `/sessions/{id}`, and `/export/{id}` reads. `--data-root` on
> `ttp server` (env-bridged for `uvicorn --reload`, non-contaminating).
> Full CI green on 3.10/3.11 at merge; the deferred `output_dir` write policy and
> Windows path tests are tracked in `SPRINTS.md` (B-001/B-002).
>
> **Scope:** replace the fixed `Path.cwd()` authorization anchor with an explicit
> configurable server data root, and unify containment so **relative and
> absolute** request paths must both resolve beneath it. Closes the absolute-path
> gap PR #10 intentionally left, while preserving external data directories
> (authorized by configuring the root).
>
> **Delivered:**
> - `create_app(*, data_root=None)`; precedence `arg > TTP_SERVER_DATA_ROOT > cwd`;
>   invalid configured root fails at creation; resolved root on `app.state.data_root`.
> - Unified `_safe_directory` (post-resolution `is_relative_to` containment for
>   relative *and* absolute; `..` and symlink escapes rejected).
> - `--data-root` on `ttp server`, bridged to the import-string app via the env
>   var (preserves `uvicorn --reload`), non-contaminating for direct unit tests.
> - The four `/grids`/`/sessions` endpoint tests reconstructed with an explicit
>   `data_root`; new authorization, precedence, symlink, and CLI tests.
> - README "HTTP API server" section documents the policy.
>
> **Verification commands:**
> ```bash
> python -m pytest -q tests/test_server_path_traversal.py tests/test_server_app.py
> python -m ruff check tap_tone_pi/server/app.py tests/test_server_path_traversal.py tests/test_server_app.py
> python -m ruff format --check tap_tone_pi/server/app.py tests/test_server_path_traversal.py tests/test_server_app.py
> ```
> Full `pre-commit run --all-files` + `pytest -q` + the CI 3.10/3.11 matrix gate merge.
>
> Commit sequence on branch: `c8d1cd8` (tests), `1519870` (implementation), docs (this).
> PR/merge reference to be recorded on completion.

> **DO-97 — COMPLETE**
>
> Final corrective commit:
> `c7c22741bfc087a8acaee34254c4ad9b4b985960`
>
> **Verification summary**
> - Focused verification passed (`tests/test_laboratory_manual_registry.py`,
>   `tests/test_laboratory_manual_view.py`, `tests/test_manual_packaging.py`).
> - Wheel packaging verified (real build + isolated `--target` install).
> - Installed-resource verification passed (import origin is the installed wheel,
>   not the checkout; packaged manifest + README load via the public registry API).
> - Boundary validation passed (advisory-boundary + analyzer-isolation checks).
> - Compile validation passed.
> - Ruff checks on touched files passed.
>
> Comparison against base commit
> `7b555ee74a521d8086e4182d16c726ca2015baef`
> confirmed that DO-97G introduced no new CI failures. Repository-wide CI failures
> remain and are tracked separately as baseline conditions (they reproduce on base
> and touch no DO-97 file).
>
> **Final adjudication:** COMPLETE WITH DOCUMENTED BASELINE FAILURES.
>
> The corrective work is a single commit (`c7c2274`) on top of the six original
> DO-97 commits (97A–97F); history was not rewritten. Corrections delivered:
> reject scalar `applies_to`; enforce complete + acyclic supersession; replace
> private `_coerce_status` with public `parse_manual_status`; `Traversable`-native
> resource access (`resolve_manual_entry_resource`) with `resolve_manual_entry_path`
> reduced to a truthful filesystem-only shim; desktop viewer distinguishes
> empty / unavailable / invalid-manifest / missing-document states and cannot crash
> on a bad manifest. Production code is frozen at `c7c2274`; PR #9 is ready for
> final merge review.

> **DO-97 note:** the handoff listed a DO-96 "Laboratory manifest and registry"
> and an existing `tap_tone_pi/acoustic_lab/` package as dependencies. Neither
> existed in the repo, and DO-96 appears nowhere in history. DO-97 was
> implemented self-contained (see `docs/ARCHITECTURE_BASELINE_M4.md` §13). The
> manifest ships **empty** by design — no consolidated Laboratory Manual
> document exists yet, and fabricating one was prohibited. `analyzer/` full
> desktop-installer packaging remains a separate out-of-scope task.

> **Note on DO-94 numbering:** the commits `6b74304` / `8255c8e` are tagged
> "(DO-94)" but implement *pressure response mapping* — a non-goal of this
> dev order. This DO-94 (Luthiery Formula Target Mapping) is a distinct work
> item that reuses the same number. Its commits are labeled
> "luthiery formula target" for disambiguation.

## Sprint Summary

DO-001 through DO-008, and DO-084 through DO-089 completed. The tap_tone_pi modal mapping toolchain now has:

| Dev Order | Description | Status |
|---|---|---|
| DO-001 | GUM uncertainty framework | COMPLETED |
| DO-002 | Wood species data sourcing | COMPLETED |
| DO-003 | Per-flitch wood database | COMPLETED |
| DO-004 | Per-build instrument record schema | COMPLETED |
| DO-005 | Analyzer GUI: Phase 2 results widget | COMPLETED |
| DO-006 | Predicted-vs-measured comparison overlay | COMPLETED |
| DO-008 | Build record auto-discovery + cleanup | COMPLETED |
| DO-084 | Transfer function uncertainty propagation | COMPLETED |
| DO-085 | Repeatability evidence and measurement validity envelope | COMPLETED |
| DO-086 | Workflow measurement contracts and procedural provenance | COMPLETED |
| DO-087 | Experimental provenance and measurement campaign lineage | COMPLETED |
| DO-088 | Build session and environmental provenance | COMPLETED |
| DO-089 | Campaign lifecycle state and measurement set aggregation | COMPLETED |
| DO-089A | Experiment design contract and cohort planning framework | COMPLETED |
| DO-089B | Process variance evidence and feasibility summary | COMPLETED |
| DO-089C | Covariate-aware cohort regression | COMPLETED |
| DO-097 | Laboratory Manual packaging & desktop access | COMPLETED |
| DO-098 | Server data-root authorization | COMPLETED |
| DO-099 | Server authorization observability & diagnostics | COMPLETED |
| DO-100 | Guided Digital Laboratory Foundation | COMPLETED |
| DO-101A | Empirical Model Framework Foundation (contracts & migration) | COMPLETED |

## Pre-existing test failures (baseline)

2 failures, both in `scripts/phase2/tests/`, verified reproducing against
`main` at `9d58dd1` and re-verified against `main` at `b0adc53` during DO-103
Stage 3:
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]` — missing 'bending' key
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]` — missing 'bending' key

These are documented baseline failures, not introduced by any current sprint.
They live outside `tests/`, so `pytest tests/` does not collect them; reproduce
with `pytest scripts/phase2/tests/`.

**Corrected at DO-102:** a third entry, `test_advisory_in_calibration_is_error`,
was listed here as a baseline failure. It passes, re-verified against the
rebased tree. The entry is stale and has been removed rather than carried
forward into the NSF documentation.

## Daily log

### 2026-08-19 (DO-103 Stage 3)
- Promoted DO-103 Stage 3 as Current in its own docs/status commit; DO-101B
  stays queued, deferred on sequencing rather than merit
- Added `AcquisitionProvenanceV1` / `AcquisitionChannelV1` and derived the
  `HARDWARE` claim from them (`NSF-306`), with witnessed held separate as the
  stricter §10 standard (`NSF-307`) and `p/F` refused a mechanical FRF name
  (`NSF-308`)
- Added the Phase 2 transfer-function ingestion path alongside — not in place
  of — the Phase 1 path
- Study schema additive-only (`acquisition` on runs); registry entry 1.1.0
- Rewrote one boundary test whose "never mentions the schema" proxy stopped
  matching its own claim once §5.1 authorized ingestion
- 108 new tests; full suite green apart from the two documented baseline
  failures, re-verified reproducing on `main` at `b0adc53`
- Promoted no capability, produced no hardware evidence, changed no status

### 2026-08-11 (DO-102 closure)
- Recorded PR #22 merge (`3d2eb69`) and closed DO-102 as Previous/Complete
- Recorded the two review defects fixed in `16ac80d` before merge
- Left Current empty; promoted nothing
- DO-101B stays queued and unresumed; promotion belongs to its own commit
- Preliminary hardware campaign remains deferred as `SPRINTS.md` B-006, a
  backlog gate rather than an authorized order

### 2026-08-04 (DO-101A closure)
- Recorded PR #19 merge (`5793309`) and closed DO-101A as Previous/Complete
- Left Current empty pending DO-101B docs/status promotion (binding sequence)
- Recorded uncertainty-budget reconciliation as `SPRINTS.md` B-005

### 2026-08-02 (DO-101A promotion)
- Promoted DO-101A to Current after DO-100 closure
- Scope: empirical contracts + luthiery migration foundation (no registry CLI)

### 2026-08-02 (DO-100 closure)
- Recorded PR #16 merge (`6ca0105`) and closed DO-100 as Previous/Complete
- Left Current empty pending DO-101A docs/status promotion (binding sequence)

### 2026-06-27 (DO-95)
- DO-95 PR 95A: FormulaValidationEnvelopeV1 contract (`tap_tone_pi/luthiery/formula_validation.py`)
- DO-95 PR 95B: validate_formula_candidate() scalar helper + validate_formula_candidate_from_evidence() overload
- DO-95 PR 95C: optional formula_validation_envelope schema block
- DO-95 PR 95D: additive export integration in export_viewer_pack_v1.py
- DO-95 PR 95E: tests/test_luthiery_formula_validation.py (13 tests)
- DO-95 PR 95F: docs reconciliation + package exports
- DO-95 complete — error-detection evidence around formula candidates; no pass/fail or advisory language

### 2026-06-27 (DO-94)
- DO-94 PR 94A: LuthieryFormulaDomain, LuthieryFormulaTargetV1, LuthieryFormulaEvidenceLinkV1 contracts (`tap_tone_pi/luthiery/formula_targets.py`)
- DO-94 PR 94B: create_luthiery_formula_target(), link_formula_candidate_to_target() helpers
- DO-94 PR 94C: optional luthiery_formula_target / luthiery_formula_evidence_link schema blocks
- DO-94 PR 94D: additive export integration in export_viewer_pack_v1.py
- DO-94 PR 94E: tests/test_luthiery_formula_targets.py (13 tests)
- DO-94 PR 94F: docs reconciliation (CURRENT.md, GOVERNANCE_AUDIT_HANDOFF.md)
- DO-94 complete — declarative luthiery formula target layer; no advisory logic

### 2026-06-19
- DO-89C Stage A: RegressionInputV1, RegressionCoefficientV1 contracts
- DO-89C Stage B: CohortRegressionEvidenceV1 contract
- DO-89C Stage C: FormulaCandidateEvidenceV1 contract
- DO-89C Stage D: fit_linear_cohort_regression() OLS helper
- DO-89C Stage E: create_formula_candidate_evidence() helper
- DO-89C Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-89C Stage G: Audit reconciliation
- DO-89C complete — 23 tests

- DO-89B Stage A: ReferenceBodyRecordV1 contract
- DO-89B Stage B: VarianceDecompositionV1 and decompose_variance()
- DO-89B Stage C: ProcessVarianceEvidenceV1 and compute_process_variance_evidence()
- DO-89B Stage D: VarianceBandThresholdsV1 and classify_variance_band()
- DO-89B Stage E: FeasibilitySummaryV1 and create_feasibility_summary()
- DO-89B Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-89B Stage G: Audit reconciliation
- DO-89B complete — 35 tests

### 2026-06-18
- DO-89A Stage A: Response variable and MIE contracts
- DO-89A Stage B: Covariate definition contract
- DO-89A Stage C: Randomization plan contract
- DO-89A Stage D: Baseline rebuild plan contract
- DO-89A Stage E: ExperimentDesignV1 governing object
- DO-89A Stage F: Design validation evidence
- DO-89A Stage G: Campaign linkage (experiment_design_id)
- DO-89A Stage H: Schema additions to phase2_ods_snapshot.schema.json
- DO-89A Stage I: Export integration in export_viewer_pack_v1.py
- DO-89A Stage J: Audit reconciliation
- DO-89A complete — 37 tests

### 2026-06-12
- DO-089 Stage A: CampaignLifecycleState enum and campaign lifecycle fields (7 tests)
- DO-089 Stage B: State transition helpers with validation (14 tests)
- DO-089 Stage C: MeasurementSetV1 and MeasurementSetSummaryV1 dataclasses (10 tests)
- DO-089 Stage D: Collection and aggregation helpers (7 tests)
- DO-089 Stage E: CampaignLifecycleExportV1 export block (4 tests)
- DO-089 Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-089 Stage G: Export integration in export_viewer_pack_v1.py
- DO-089 Stage H: Audit reconciliation (GOVERNANCE_AUDIT_HANDOFF.md, CURRENT.md)
- DO-089 complete — 42 tests

### 2026-07-16
- DO-97 (97A): Laboratory Manual contracts + empty manifest + canonical READMEs
- DO-97 (97B): Read-only path-safe manual registry (importlib.resources)
- DO-97 (97C): Desktop Help → Laboratory Manual read-only view
- DO-97 (97D): Package-data config; manifest + README verified in built wheel
- DO-97 (97E): 54 tests — contracts, negative, packaging, boundary, GUI
- DO-97 (97F): Reconciled M4 baseline, README, CURRENT.md
- DO-97 complete — 54 new tests, empty manifest by design

### 2026-05-03
- DO-008 Stage A: Doc reconciliation — no-op (no prediction.py refs found)
- DO-008 Stage B: PyQt6 dependency declaration (1 test)
- DO-008 Stage C: Build record auto-discovery (11 tests)
- DO-008 Stage D: View menu opt-out toggle (3 tests)
- DO-008 complete — 15 new tests

### 2026-05-02
- DO-001, DO-002, DO-003, DO-004 completed
- DO-005 Stage A: Phase 2 session loader (26 tests)
- DO-005 Stage B: Heatmap rendering primitive (20 tests)
- DO-005 Stage C: Phase 2 results widget (15 tests)
- DO-005 Stage D: Main window integration (8 tests)
- DO-006 Stage E: Comparison mode + prediction loader (20 tests)
- Sprint complete — 89 tests across all stages
