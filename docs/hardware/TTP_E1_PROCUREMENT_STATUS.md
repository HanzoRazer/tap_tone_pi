# TTP E1 — Procurement Status

**Status:** three components design-selected (possession unconfirmed); no
component selected for purchase, ordered, or received.
**Dev Order:** DO-104P
**Last updated:** 2026-08-24

Procurement state lives here and **not** in any scientific result document. A
result document says what was measured; this one says what is on order. Mixing
them lets a shipping delay read as an experimental finding.

## Status

| Component | Selection status | Order status | ETA | Received | Inspection result | Blocking issue |
| --- | --- | --- | --- | --- | --- | --- |
| HOST-001 host | DESIGN_SELECTED | NOT_ORDERED | — | No | — | Ownership unconfirmed — design selection is not possession |
| ADC-001 adc_interface | DESIGN_SELECTED | NOT_ORDERED | — | No | — | Ownership unconfirmed |
| PREAMP-001 mic_preamp | DESIGN_SPECIFIED | NOT_ORDERED | — | No | — | Board existence unconfirmed; may need fabrication |
| MIC-001 microphone | NOT_SELECTED | NOT_ORDERED | — | No | — | Model never locked in the stack specification |
| FORCE-001 force_transducer | NOT_SELECTED | NOT_ORDERED | — | No | — | **Blocks everything.** Must be selected with its conditioner |
| PRECOND-001 force_conditioner | NOT_SELECTED | NOT_ORDERED | — | No | — | Output must reach the ADC's ±3 V window; may require ATTEN-001 |
| ATTEN-001 attenuator | CONDITIONAL | NOT_ORDERED | — | No | — | Needed only if PRECOND-001 cannot reach the window itself |
| SHAKER-001 shaker | NOT_SELECTED | NOT_ORDERED | — | No | — | Paired selection with AMP-001 |
| AMP-001 amplifier | NOT_SELECTED | NOT_ORDERED | — | No | — | Paired selection with SHAKER-001; must accept the DAC output level |
| STINGER-001 stinger | NOT_SELECTED | NOT_ORDERED | — | No | — | Fabrication design unresolved; thread depends on FORCE-001 |
| TIP-001 contact_tip | NOT_SELECTED | NOT_ORDERED | — | No | — | Geometry unresolved |
| STAND-001 stand_base | NOT_SELECTED | NOT_ORDERED | — | No | — | Design unresolved |
| REF-STRUCT-001 reference_structure | NOT_SELECTED | NOT_ORDERED | — | No | — | Not identified |
| CABLE-001 cabling | NOT_SELECTED | NOT_ORDERED | — | No | — | Enumerated once interfaces are frozen |

## Selection status vocabulary

Deliberately distinct from the BOM's status ladder, because "the design names
it" and "we have one" are different facts:

| Status | Means |
| --- | --- |
| `NOT_SELECTED` | No product chosen |
| `CONDITIONAL` | Needed only if another selection makes it necessary |
| `DESIGN_SELECTED` | Chosen in an authoritative repository design document; **not** owned |
| `DESIGN_SPECIFIED` | Design describes it but no product identity exists (e.g. a custom board) |
| `SELECTED` | A specific purchasable product chosen for this campaign |
| `REJECTED` | Ruled out; reason recorded in the rationale document |

## The dominant blocker

Every row reduces to one fact: **no E1 hardware budget is authorized**, and the
force chain cannot be selected without one, because the force chain is the part
where cost pressure would push toward abandoning force measurement altogether.

DO-104P deliberately does not invent a ceiling. Selection carries three tiers —
research minimum, preferred E1, and reference-grade candidate — and the preferred
tier drives the recommendation until a ceiling is imposed.

## Critical path

Procurement is now the critical path. The software side has been ready since the
DO-104 pre-execution slice merged, and every remaining acceptance criterion in
DO-104E needs a physical component that does not exist.

Consequence for the next pass: **lead time is a first-class selection
criterion**, ranked beside price and specification. A part that is excellent and
unobtainable this quarter is not the preferred choice.

## Substitution log

No substitutions. When one occurs, DO-104P §4.13 requires it recorded here
*before* bench use, never silently:

| Planned | Replacement | Reason | Affected interface | Review disposition |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |
