# TTP E1 — Physical Ownership Census

**Status:** `PERFORMED`
**Dev Order:** DO-104O (framework) / DO-104R (intake and reconciliation)
**Base:** `d3ae3b6` (DO-104S merged as PR #29)
**Census date:** 2026-08-27
**Observer:** Ross Echols
**Observer role:** repository owner / bench operator
**Observation method:** `OPERATOR_ATTESTATION`

---

## Result

**No E1-relevant hardware is possessed. All ten required categories are
`CONFIRMED_ABSENT`.**

This is a complete census with a negative result, which is a finding rather than
an empty form. "Inspected and absent" and "never looked" are different states,
and every row below is the former.

## Method, and its limits

The operator was asked to establish possession for the ten required categories
and reported that none of the equipment exists. That is an **attestation**, not a
hands-on inventory conducted item by item: no unit was handled, because there
were no units to handle.

`OPERATOR_ATTESTATION` is recorded rather than `DIRECT_PHYSICAL_INSPECTION`
deliberately. The distinction is not pedantry — a negative attestation is
answered by the absence of a thing, and absence cannot be photographed or
serialised. A reader should know that the evidence here is the operator's
statement about their own bench, which is the appropriate and only available
evidence for a negative result.

**What would overturn this census:** finding any listed item. If a Raspberry Pi
or a measurement microphone surfaces later, this document is wrong and must be
re-run, not patched.

## What was not inferred

Ownership was **not** derived from any of the sources DO-104O §4.4 forbids —
documentation, repository configuration, device profiles or drivers, prior
selections, DO-104S recommendations, or purchase recommendations.

One corroborating observation is recorded as **consistent with** this result
without being evidence for it: every captured session under `runs_phase2/` is
`"synthetic": true` with `"device": null`, or the `DEMO` fixture. No real capture
has ever happened in this repository. That agrees with owning no acquisition
hardware, but agreement is not proof, and the census rests on the attestation.

## Ownership vocabulary

DO-104R §6 names these `OWNED` / `NOT_OWNED` / `UNKNOWN` and instructs using
existing repository equivalents rather than minting synonyms. The repository
already carries this axis from DO-104S, so those terms are used here:

| This repository | DO-104R §6 name | Means | Established by |
| --- | --- | --- | --- |
| `UNKNOWN` | `UNKNOWN` | Nobody has looked | the pre-census state |
| `CONFIRMED_PRESENT` | `OWNED` | A physical unit was observed and identified | direct observation with identity recorded |
| `CONFIRMED_ABSENT` | `NOT_OWNED` | A census was performed and found no unit | someone who looked and did not find |

`CONFIRMED_ABSENT` is a **finding**. It is never a default for an item that went
unmentioned.

## Compatibility disposition

| Disposition | Means |
| --- | --- |
| `COMPATIBLE` | Owned, and its specification satisfies the E1 requirement for that role |
| `COMPATIBILITY_REQUIRES_VERIFICATION` | Owned, but a specification needed for the decision is unread |
| `INCOMPATIBLE` | Owned, and it fails a named requirement |
| `NOT_APPLICABLE` | Nothing is owned, so there is nothing to assess |

Every row below is `NOT_APPLICABLE`. **Compatibility reconciliation has an empty
subject set** — there is no owned equipment to reconcile against the E1
architecture, so DO-104R §3.5 has nothing to evaluate.

---

## Census record

| # | Category | BOM role | Ownership | Manufacturer | Model | Serial / asset ID | Qty | Condition | Location | Observation method | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Raspberry Pi 5 | HOST-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 2 | HiFiBerry DAC+ ADC Pro | ADC-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 3 | OPA1612 preamp hardware | PREAMP-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 4 | Condenser / measurement microphone | MIC-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 5 | Audio power amplifier | AMP-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 6 | Speaker / Phase 2A driver | — (not an E1 BOM row) | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 7 | Force transducer / load cell | FORCE-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 8 | Force conditioner (IEPE/ICP or bridge) | PRECOND-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 9 | Shaker / exciter | SHAKER-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |
| 10 | Stand / base / fixture hardware | STAND-001 | CONFIRMED_ABSENT | — | — | — | 0 | — | — | OPERATOR_ATTESTATION | NOT_APPLICABLE |

No serial number or asset identifier was fabricated for any row. There is
nothing to identify.

## Equipment found that is not in the BOM

**None.** No alternate audio interface, microphone, amplifier, sensor, or
fixture was reported.

| Item | Manufacturer | Model | Serial / asset ID | Why it may matter to E1 |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

This table is empty as a result, not as an omission. DO-104R §3.6 exists because
an owned alternate could change the architecture decision; none exists, so the
DO-104S recommendation faces no competing hardware.

## Unresolved items

**None.** No category was left in `UNKNOWN`.

| Item | What blocked the observation | What would resolve it |
| --- | --- | --- |
| — | — | — |

## Evidence references

The evidence is the operator attestation recorded in this document's header. No
photographs, invoices, or external asset registers were supplied, and none is
needed to record an absence.

---

## What this census does and does not settle

**Settles:** B-016. A census was performed. The finding is that no E1-relevant
hardware is possessed.

**Does not settle:**

- **Selection.** Nothing owned means nothing to prefer over the DO-104S
  recommendation, but the recommendation still requires an explicit human
  ruling. `CONFIRMED_ABSENT` does not produce `SELECTED`.
- **Purchase authorization.** The census makes a purchase recommendation
  *legal* for the first time — the validator requires `CONFIRMED_ABSENT` before
  `RECOMMEND_PURCHASE` — but legal is not authorized, and DO-104R §4.8 forbids
  creating authorization here. Every procurement action stays `HOLD`.
- **B-014.** The ADC anti-aliasing finding is untouched. Not owning the board
  says nothing about aliasing.
- **B-015.** The ADC supersession is untouched, and is now more pressing rather
  than less: the recommended board must be *acquired*, and it is the one the
  vendor has superseded.
