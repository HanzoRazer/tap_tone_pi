# TTP E1 — Physical Ownership Census

**Status:** `NOT_PERFORMED`
**Dev Order:** DO-104O
**Base:** `d3ae3b6` (DO-104S merged as PR #29)
**Census date:** — (not yet conducted)
**Observer:** — (not yet conducted)

---

## This document does not close B-016

B-016 records that no physical ownership census has ever been run. **It stays
open until this file carries actual observations of actual equipment.** A form
populated with `UNKNOWN` is the form, not the census — DO-104O §4.9 says so
explicitly, and the validator will not accept an unperformed census as a closing
artifact.

Right now every row below reads `UNKNOWN` because nobody has looked yet. That is
the honest state, and it is exactly the state DO-104S ended in.

## What a census is, and what it may not be built from

The census is **observational**. Ownership comes from someone physically looking
at hardware and reading identity off it.

Ownership may **never** be derived from any of these, per DO-104O §4.4:

- documentation, including this repository's own design documents;
- repository configuration, a device profile, or an installed driver;
- a previous product selection or a DO-104S recommendation;
- a purchase recommendation;
- **a historical statement about what was owned, unless reconfirmed for this
  census.**

That last one is the easiest to violate and the most important. "I think I have
one of those somewhere" is not an observation. The question this document
answers is what is *on the bench, now, in hand.*

## Method

To be recorded when the census is performed. It should state:

- who conducted it;
- when;
- what was physically handled versus seen;
- what could not be located and why;
- where identity was read from (label, silkscreen, packaging, firmware readout);
- anything that was found but not expected.

## Ownership vocabulary

| Ownership | Means | Established by |
| --- | --- | --- |
| `UNKNOWN` | Nobody has looked | the pre-census state of every row |
| `OWNED` | A physical unit was observed and identified | direct observation, with identity recorded below |
| `NOT_OWNED` | A census was performed and found no unit | a search that looked and did not find |

`NOT_OWNED` is a **finding**, not a default. It requires that someone looked.

## Compatibility disposition

Recorded per role once ownership is known. An owned item is **not** assumed
suitable merely because it fills the same nominal role — DO-104O §3.2:

| Disposition | Means |
| --- | --- |
| `OWNED_AND_COMPATIBLE` | Owned, and its specification satisfies the E1 requirement for that role |
| `OWNED_REQUIRES_VERIFICATION` | Owned, but a specification needed for the E1 decision is unread or unknown |
| `OWNED_INCOMPATIBLE` | Owned, and it cannot satisfy the role — with the specific requirement it fails |
| `NOT_OWNED` | No unit |
| `UNKNOWN` | Not yet assessed |

---

## Census record

Ten categories, per DO-104O §3.1. Fill `manufacturer`, `model`, and
`serial_or_asset_id` **only from what is physically readable on the unit**.

| # | Category | BOM role | Ownership | Manufacturer | Model | Serial / asset ID | Qty | Condition | Location | Witnessed | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Raspberry Pi 5 | HOST-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 2 | HiFiBerry DAC+ ADC Pro | ADC-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 3 | OPA1612 preamp hardware | PREAMP-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 4 | Condenser microphone | MIC-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 5 | Audio power amplifier | AMP-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 6 | Speaker / Phase 2A driver | — (not an E1 BOM row) | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 7 | Force transducer / load cell | FORCE-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 8 | Force conditioner (IEPE/ICP or bridge) | PRECOND-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 9 | Shaker / exciter | SHAKER-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |
| 10 | Stand / base / fixture hardware | STAND-001 | UNKNOWN | — | — | — | — | — | — | NO | UNKNOWN |

### Location granularity

Record location at a granularity that distinguishes one unit from another
without becoming a security disclosure — `bench`, `parts drawer`, `storage`,
`in another build` are all sufficient. A street address is not wanted and must
not be recorded here.

## Equipment found that is not in the BOM

A census looks at what is there, not only at what was expected. Anything
relevant to the E1 chain that is owned but absent from the BOM belongs here —
a different microphone, an audio interface that is not a HiFiBerry, an amplifier
of unknown provenance. It may turn out to change a selection.

| Item | Manufacturer | Model | Serial / asset ID | Why it may matter to E1 |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Unresolved items

Anything that could not be found, could not be identified, or was found in a
state that prevents a disposition.

| Item | What blocked the observation | What would resolve it |
| --- | --- | --- |
| — | — | — |

## Evidence references

Photographs, packaging, invoices held outside the repository, or an existing
asset register may be referenced here. **No financial credentials, account
identifiers, or shipping addresses.** A reference names the evidence; it does
not reproduce it.

| Role | Evidence reference | Kind |
| --- | --- | --- |
| — | — | — |

---

## What this document will not do once filled

It will record possession. It will not record suitability beyond the recorded
disposition, it will not authorize a purchase, and it will not promote any
component's status. Selection is
[the rationale document](TTP_E1_HARDWARE_SELECTION_RATIONALE.md); authorization
is `TTP_E1_PROCUREMENT_AUTHORIZATION.md`; possession of a serialized unit is
[the identity register](TTP_E1_HARDWARE_IDENTITY_REGISTER.md).

Owning the recommended hardware would not close B-014, and owning the baseline
ADC would not close B-015.
