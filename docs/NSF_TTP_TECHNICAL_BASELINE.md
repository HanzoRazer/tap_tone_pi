# TTP Technical Baseline

What the TTP Analyzer currently implements, audited against repository
evidence.

**Machine-readable source:** `tap_tone_pi/grant_readiness/inventory.py`.
Regenerate the timestamped artifact with `python scripts/nsf_ttp_audit.py
--write` (writes to `out/nsf/`); check it without writing with `--check`.
`tests/test_nsf_capability_audit.py` fails if this document and the inventory
disagree.

---

## How to read a status

> **IMPLEMENTED** means the capability exists in the repository and is exercised
> by automated tests. It does not imply intended-hardware verification,
> calibrated accuracy, or external validation unless separately stated.

The other three states:

- **EXPERIMENTAL** — code exists, but coverage is indirect or incidental and no
  stability evidence supports relying on it.
- **PARTIAL** — some of the capability exists; a named part does not, or the
  code present would be read as claiming more than it delivers.
- **PLANNED** — declared intent, no implementation.

There is deliberately no "mostly done". Every capability carries exactly one
state, and a status with no explanation is rejected by the audit.

**Hardware verification is tracked separately from status.** A capability can be
IMPLEMENTED and unwitnessed on hardware at the same time; those are different
claims and this baseline never merges them.

---

## Summary

| Status | Count |
| --- | --- |
| IMPLEMENTED | 19 |
| EXPERIMENTAL | 2 |
| PARTIAL | 4 |
| PLANNED | 0 |
| **Total audited** | **25** |

**Hardware verification status:** None of the 25 audited capabilities has been
witnessed end-to-end on the intended TTP hardware configuration during DO-102.
Software implementation status and hardware verification are tracked
independently.

---

## IMPLEMENTED (19)

| Capability | Note |
| --- | --- |
| `wav_persistence` | Two readers exist; the one under test is `modes/_shared/wav_io.py`. |
| `tap_spectral_analysis` | Extracted peaks are spectral feature candidates, not identified structural modes. |
| `capture_quality_gate` | Emits pass/warn/fail against a versioned rule policy. Thresholds are workflow policy, not established performance limits. |
| `phase1_tap_workflow` | End-to-end path exercised by synthetic impulse generation. This is the ingestion surface for the preliminary experiment. |
| `phase2_ods_scanning` | Two archived sessions exist; neither contains repeated captures of a single point, so neither can serve as a repeatability dataset. |
| `transfer_function_coherence` | Deliberately outside the first study, which is Phase 1 only. |
| `calibration` | Limited to internal signal-chain consistency: loopback, reference tone, frequency-response compensation. **Not traceable calibration** and not evidence of external metrological validity. |
| `bending_stiffness_rig` | Archived runs exist under `out/bend_*`. Serial capture has simulator coverage in-repo. |
| `uncertainty_quantification` | GUM-conformant uncertainty machinery exists and is exercised. A populated and reviewed acoustic-chain uncertainty budget **does not yet exist**. |
| `repeatability_evidence` | Carries a DO-085 workflow acceptance gate. That threshold is workflow policy, is not an established performance limit, and is not an NSF success criterion. |
| `plate_dynamics_prediction` | Solver and mode-shape evaluation exist and are covered by tests. **Predicted-versus-measured agreement remains unestablished.** |
| `session_provenance` | Environmental fields are recorded as supplied. No temperature or humidity normalization exists anywhere in the pipeline. |
| `measurement_workflow_contracts` | Declares procedural requirements a legitimate measurement must meet. |
| `experiment_design` | Planning and variance-decomposition contracts exist. No executed campaign has populated them with hardware data. |
| `viewer_pack_export` | Two archived sessions fail viewer-pack validation on a missing `bending` key; documented baseline failures predating DO-102. |
| `guided_laboratory` | CLI-proven and deterministic. No persistence layer, no GUI, no adapter to the measurement workflow contracts yet. |
| `desktop_analyzer` | **Software UI only; the intended hardware workflow has not been witnessed.** |
| `http_api_server` | Read-only session and export endpoints beneath a configured data root. |
| `unified_cli` | Single argparse entry point. DO-102 adds scripts only, no subcommand. |

## EXPERIMENTAL (2)

**`damping_q_estimation`** — Covered only indirectly, through the
production-physics suite. No dedicated test module and no stability evidence
across repeats. See risk R7.

**`wolf_tone_detection`** — Detection only. The sibling `wolf_advisor` module is
classified DECISION SUPPORT and is outside the measurement inventory entirely.

## PARTIAL (4)

**`audio_capture`** — Software path implemented and exercised with simulated
input; the intended Pi and microphone acquisition chain has not been witnessed.
Recorded PARTIAL rather than IMPLEMENTED because IMPLEMENTED would read as *the
system can currently capture real measurements*, which this repository cannot
show. Note that `tap_tone_pi/capture/` holds only the bending rig's serial
capture; the audio path is `capture/__init__.py` plus `core/auto_trigger.py`.

**`controlled_excitation`** — `ExcitationContractV1` describes driven electrical
excitation (tone, stepped, sweep) through an output device: the speaker-air
approach the excitation architecture has since moved away from. The grounded
shaker and stinger contact drive is **not implemented**. DO-102's
`ExcitationContextV1` can record that arrangement, but recording a method is not
building it. Recorded PARTIAL so a software abstraction is not read as the
proposed excitation architecture having been delivered. See risk R1.

**`multitap_statistics`** — Aggregation helpers exist but no dedicated test
module covers them, and no workflow drives repeated taps end to end. This is the
nearest existing neighbour to the DO-102 experiment path.

**`chladni_pattern_indexing`** — The tests exercise the legacy `modes/chladni`
copy rather than the `tap_tone_pi.chladni` package this inventory names as
canonical. The duplication is real and unreconciled.

## PLANNED (0)

No capability currently carries PLANNED status.

---

## Supporting Scientific Infrastructure Landed After Initial Audit

Two items landed on `main` after this inventory was bounded. Both are real and
both are implemented. **Neither is counted as an instrument capability**, and
the denominator above stays at 25.

The distinction is deliberate. The inventory answers *what can the TTP Analyzer
presently do?* — capture, spectral analysis, calibration, uncertainty,
provenance, evidence export, guided laboratory, desktop analyzer. Counting
shared contract infrastructure alongside those would drift the baseline toward
*what technical infrastructure exists anywhere in the repository?*, which is a
weaker and less honest claim to put in front of a reviewer.

### `tap_tone_pi/empirical/` — shared empirical-model contract foundation

Implemented (DO-101A, PR #19). A shared contract layer for describing an
external scientific equation: `EmpiricalModelDefinitionV1`, inputs and outputs,
validity domain, evidence/measurement/calibration/uncertainty references, a
validation envelope, a stable `EMP-*` error vocabulary, pure validation, and
deterministic schema-strict serialization, with
`contracts/empirical_model_definition_v1.schema.json` registered.

Software and governance infrastructure. **No hardware implication**, and no
measurement is performed by it. Uncertainty is referenced by identifier only —
DO-101A deliberately declined to make either existing `UncertaintyBudget`
canonical, which is `SPRINTS.md` B-005 and is adjacent to this baseline's note
that no populated acoustic-chain uncertainty budget exists.

### `tonewood_radiation_ratio_v1` — cross-repository interoperability contract

Implemented (BR-045, PR #21). A governed cross-repository scientific contract
establishing formula identity, scale, units, and parity fixtures for the
Schelleng tonewood radiation ratio, with a published schema, a parity-checking
script, and a dedicated test module.

**Not a measurement capability.** It fixes what a number *means* across
repositories; it does not acquire, analyze, or qualify one. Its presence says
nothing about whether TTP can measure the quantities the formula consumes.

---

## Current evidence

- **Repository tests.** Every implementation and test path in the inventory
  resolves against the working tree; the audit fails if one does not. The
  DO-102 regression scope includes the supporting infrastructure landed after
  the initial audit — `tests/test_empirical_contracts.py`,
  `tests/test_empirical_luthiery_compat.py`, and
  `tests/test_radiation_ratio_contract.py` — so this baseline is verified
  against the repository as it actually exists, not as it stood when the
  inventory was bounded.
- **Archived measurement artifacts.** Two Phase 2 sessions under `runs_phase2/`
  and bending runs under `out/bend_*`. None contains repeated captures of a
  single point.
- **Preliminary repeatability study.** The contract and analysis path are proven
  against deterministic non-hardware fixtures. No hardware dataset exists.
- **Schemas.** Both DO-102 contracts validate strictly and are registered in
  `contracts/schema_registry.json`.

### Baseline test failures

Two failures reproduce against `main` at `9d58dd1` and are unrelated to this
work:

- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]`
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]`

Both fail on `manifest.contents missing required keys: ['bending']`. Both live
in `scripts/phase2/tests/`, outside `tests/`, so `pytest tests/` does not
collect them; reproduce with `pytest scripts/phase2/tests/`.

A third failure recorded in `docs/dev_orders/CURRENT.md`,
`test_advisory_in_calibration_is_error`, **no longer reproduces** — it passes,
re-verified against the rebased tree. That ledger entry is stale and is not
carried forward. PR #18 closed DO-100 but did not touch the baseline list, so
this correction belongs to DO-102 rather than duplicating upstream work.

---

## Unresolved technical risks

Ten open risks are recorded in `NSF_TTP_PHASE_I_TECHNICAL_RISKS.md`: excitation
variability, sensor positioning, support-condition variability, environmental
influence, spectral-feature persistence, mode-identification uncertainty,
decay/Q stability, operator variability, between-session repeatability, and
reference-method agreement.

None is closed. Closing any of them requires a hardware campaign that has not
run. R10 — reference-method agreement — would remain open even if the other nine
were settled; see `NSF_TTP_REFERENCE_VALIDATION_PLAN.md`.

---

## What this baseline does not establish

- No measurement accuracy, for any quantity, under any condition.
- No calibration in the metrological sense, and no traceability to any
  reference.
- No agreement with any accepted reference method.
- No attribution of an extracted spectral peak to a structural mode.
- No witnessed execution on the intended hardware.

Test coverage is evidence that code runs as written. It is not evidence that the
quantity computed is the physical quantity intended.
