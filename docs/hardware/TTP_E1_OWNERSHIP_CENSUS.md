# TTP E1 — Physical Ownership Census

**Status:** `PERFORMED`
**Dev Order:** DO-104O (framework) / DO-104R (intake, reconciliation, erratum)
**Current pass:** 2 — 2026-08-27
**Superseded pass:** 1 — 2026-08-27 (retained below; **contained a false absence**)
**Observer:** Ross Echols
**Observer role:** repository owner / bench operator
**Observation method:** `OPERATOR_ATTESTATION`

---

## Result (pass 2)

**One item is owned: a Raspberry Pi 5, 16 GB, in hand, purchased April 2025.**
Everything else required for E1 is `CONFIRMED_ABSENT`, and no bending-rig
hardware has been purchased.

## Pass 1 was wrong, and it is corrected by re-running rather than editing

Pass 1 recorded all ten categories as `CONFIRMED_ABSENT`. That was a **false
absence** on `HOST-001`: a Raspberry Pi 5 had been in hand since **April 2025**,
sixteen months before the attestation.

Pass 1 is retained below unedited. Its own text set this rule:

> **What would overturn this census:** finding any listed item. If a Raspberry Pi
> or a measurement microphone surfaces later, this document is wrong and must be
> re-run, not patched.

A Raspberry Pi is the example it named. Editing the cell would have destroyed the
only property that makes census evidence worth anything — that it records what
was actually said on a date. So pass 1 stands as the record of the 2026-08-27
attestation, and pass 2 supersedes it.

### Why it failed, recorded without euphemism

Pass 1 ran on `OPERATOR_ATTESTATION` — a statement about a bench rather than a
look at one. It was recorded as weaker evidence than
`DIRECT_PHYSICAL_INSPECTION` for exactly that reason, and it failed in the one
direction that matters. **A false absence is what authorizes a purchase.** Had
the DO-104S recommendation been ratified and acted on, this census would have
bought a second Raspberry Pi.

Nothing in the validator caught it, and nothing could have: every check verifies
that the document is internally consistent and does not claim more than it
records, and pass 1 was internally consistent and wrong. It was caught by one
further question about what had been purchased. That is the limit of what
document validation can do, and it is why `observation_method` is a recorded
field rather than an assumed one.

Tracked as **B-017**.

## Method

Pass 2 is a corrected operator attestation, informed by purchase history rather
than recall alone. It is **not** `DIRECT_PHYSICAL_INSPECTION`: no unit was
handled, measured, or read off a label during this pass. The Pi's RAM variant and
acquisition date come from the operator's knowledge of the purchase.

**What would overturn this census:** the same rule as before. Finding any item
recorded absent, or finding that the Pi differs from what is recorded here, makes
this document wrong and requires pass 3 rather than an edit.

## What was not inferred

Ownership was **not** derived from any source DO-104O §4.4 forbids —
documentation, repository configuration, device profiles or drivers, prior
selections, DO-104S recommendations, or purchase recommendations.

Pass 1 recorded one corroborating observation: every captured session under
`runs_phase2/` is `"synthetic": true` with `"device": null`. Pass 2 shows why
that was correctly labelled *consistent with* rather than *evidence for* — it
remains true, and a Pi was owned the whole time. Owning a host does not produce
captures. **The corroboration was sound and the conclusion it appeared to
support was false**, which is the general hazard of reasoning from repository
state to physical possession.

## Ownership vocabulary

DO-104R §6 names these `OWNED` / `NOT_OWNED` / `UNKNOWN`; the repository's
existing equivalents are used rather than synonyms:

| This repository | DO-104R §6 name | Means | Established by |
| --- | --- | --- | --- |
| `UNKNOWN` | `UNKNOWN` | Nobody has looked | the pre-census state |
| `CONFIRMED_PRESENT` | `OWNED` | A physical unit is possessed and identified | observation, with identity recorded |
| `CONFIRMED_ABSENT` | `NOT_OWNED` | A census looked and found no unit | someone who looked and did not find |

## Compatibility disposition

| Disposition | Means |
| --- | --- |
| `COMPATIBLE` | Owned, and its specification satisfies the E1 requirement for that role |
| `COMPATIBILITY_REQUIRES_VERIFICATION` | Owned, but a specification needed for the decision is unread |
| `INCOMPATIBLE` | Owned, and it fails a named requirement |
| `NOT_APPLICABLE` | Nothing owned, so nothing to assess |

---

## Census record — pass 2 (current)

| # | Category | BOM role | Ownership | Manufacturer | Model | Serial / asset ID | Qty | Condition | Location | Observation method | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Raspberry Pi 5 | HOST-001 | CONFIRMED_PRESENT | Raspberry Pi | Raspberry Pi 5 16GB | TTP-ASSET-001 | 1 | in hand, purchased 2025-04 | bench | OPERATOR_ATTESTATION | COMPATIBLE |
| 2 | HiFiBerry DAC+ ADC Pro | ADC-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 3 | OPA1612 preamp hardware | PREAMP-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 4 | Condenser / measurement microphone | MIC-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 5 | Audio power amplifier | AMP-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 6 | Speaker / Phase 2A driver | — (not an E1 BOM row) | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 7 | Force transducer / load cell | FORCE-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 8 | Force conditioner (IEPE/ICP or bridge) | PRECOND-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 9 | Shaker / exciter | SHAKER-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 10 | Stand / base / fixture hardware | STAND-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |

`TTP-ASSET-001` is a **locally assigned asset label**, not a serial number. The
unit's manufacturer serial has not been read. Assigning a local label is
permitted by DO-104O §4.5 and DO-104R §3.4; inventing a serial is not, and none
was invented. The real serial can be added whenever the unit is next handled.

### Why the Pi is `COMPATIBLE` and not merely present

The documented requirement for `HOST-001` is a 64-bit Pi OS running
`tap_tone_pi`, with the 40-pin GPIO header carrying I²S to the ADC board. The
40-pin header is identical across Raspberry Pi 5 RAM variants, so the interface
that matters to this measurement chain is unaffected by the variant difference.

**The owned unit is 16 GB; the DO-104S candidates were priced at 8 GB.** The
owned unit exceeds the specification rather than missing it. The market evidence
is *not* rewritten to match — the candidates record what was priced, this record
records what is owned, and the difference is stated instead of being smoothed
away.

This disposition is a paper judgement about specifications, exactly like the
DO-104S architecture gate. **It is not a demonstration that the board works**;
nothing has been powered, mounted, or captured.

## Displacement-jig hardware

Pass 1 covered only the ten E1 categories, so bending-rig hardware was outside
its scope and its ownership was `UNKNOWN` rather than absent. Pass 2 extends the
scope and resolves it.

| Category | Ownership | Observation method |
| --- | --- | --- |
| Dial indicator (Mitutoyo ID-C 543-861 or equivalent) | CONFIRMED_ABSENT | OPERATOR_ATTESTATION |
| USB Input Tool / serial interface for the indicator | CONFIRMED_ABSENT | OPERATOR_ATTESTATION |
| T-slot aluminium extrusion, brackets, hardware | CONFIRMED_ABSENT | OPERATOR_ATTESTATION |
| Ground steel plate, hardened drill rod, loading roller | CONFIRMED_ABSENT | OPERATOR_ATTESTATION |
| OIML class M1 calibrated mass set | CONFIRMED_ABSENT | OPERATOR_ATTESTATION |
| Strain-gauge load cell + HX711 (optional path) | CONFIRMED_ABSENT | OPERATOR_ATTESTATION |

**No bending-rig hardware has been purchased.** These categories have no E1 BOM
role because the displacement jig has never had a hardware specification in this
repository — see
[the construction guide](../handoffs/bending_rig_construction.md), which is an
engineering input rather than an authorized build.

## Equipment found that is not in the BOM

**None.** No alternate audio interface, microphone, amplifier, sensor, or fixture
was reported in either pass.

| Item | Manufacturer | Model | Serial / asset ID | Why it may matter to E1 |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Unresolved items

| Item | What blocked the observation | What would resolve it |
| --- | --- | --- |
| Raspberry Pi manufacturer serial | Unit not handled during this pass | Read the label; add it beside `TTP-ASSET-001` |

---

## Census record — pass 1 (2026-08-27, SUPERSEDED)

**Retained unedited. Row 1 is known to be false.** Kept because a census records
what was attested on a date, and rewriting that would leave no way to see that an
attestation can be wrong.

| # | Category | BOM role | Ownership | Observation method | Disposition |
| --- | --- | --- | --- | --- | --- |
| 1 | Raspberry Pi 5 | HOST-001 | ~~CONFIRMED_ABSENT~~ **FALSE — owned since 2025-04** | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 2 | HiFiBerry DAC+ ADC Pro | ADC-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 3 | OPA1612 preamp hardware | PREAMP-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 4 | Condenser / measurement microphone | MIC-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 5 | Audio power amplifier | AMP-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 6 | Speaker / Phase 2A driver | — | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 7 | Force transducer / load cell | FORCE-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 8 | Force conditioner | PRECOND-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 9 | Shaker / exciter | SHAKER-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 10 | Stand / base / fixture hardware | STAND-001 | CONFIRMED_ABSENT | OPERATOR_ATTESTATION | NOT_APPLICABLE |

Nine of ten rows survived pass 2 unchanged.

---

## What this census settles

**Settles:** B-016 stays closed — a census was performed, and correcting it does
not un-perform it. One role is filled by owned hardware and needs no purchase.
Bending-rig hardware is established absent rather than unknown.

**Does not settle:**

- **Selection.** Owning a Pi does not select it. `HOST-001` was already
  `DESIGN_SELECTED` in the stack specification, and the human selection ruling is
  `SELECTION_DEFERRED` — see
  [procurement authorization](TTP_E1_PROCUREMENT_AUTHORIZATION.md).
- **Campaign acquisition.** The Pi was bought in April 2025, outside this
  campaign. It was never `ORDERED` and is not `RECEIVED` by it. Possession sits
  on its own axis in [the identity register](TTP_E1_HARDWARE_IDENTITY_REGISTER.md);
  the acquisition ladder is untouched.
- **B-014.** Owning a host says nothing about the ADC's missing anti-aliasing
  filter.
- **B-015.** The ADC is still absent, still superseded by its vendor, and still
  must be acquired.
