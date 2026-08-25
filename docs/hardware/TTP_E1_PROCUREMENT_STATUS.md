# TTP E1 — Procurement Status

**Status:** three components design-selected (possession unconfirmed); no
component selected for purchase, ordered, or received. Physical ownership is
`UNKNOWN` for every component — no physical census has been performed.
**Dev Order:** DO-104P; ownership census added under DO-104S
**Last updated:** 2026-08-25

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

## Physical ownership census

**Every component below is `UNKNOWN`, and that is a finding, not a placeholder.**

DO-104S is a selection order executed before any physical inventory of the lab
has been performed. No component in this campaign has been established as
physically possessed, and this order deliberately does not guess. The census is
frozen at `UNKNOWN` and only a physical census may move it.

### Ownership vocabulary

Ownership is a statement about a physical object. It is not a statement about a
design, a document, a purchase, or a plan:

| Ownership | Means | Established by |
| --- | --- | --- |
| `UNKNOWN` | Physical possession has not been established | the initial state of every row |
| `CONFIRMED_PRESENT` | A physical unit has been identified and recorded | a physical census plus an identity-register entry carrying a serial or asset label |
| `CONFIRMED_ABSENT` | A physical census was performed and found no unit | a physical census that looked and did not find |

`UNKNOWN` means exactly one thing: **nobody has looked yet.** It does not mean
absent, it does not mean missing, and it does not mean not owned. The
distinction is load-bearing. A buy list generated from assumed absence would
duplicate equipment that may already sit on the bench, and the failure would
present as a procurement result rather than as the inference error it is.

### Census

| Component | BOM row | Ownership | Procurement action | Basis |
| --- | --- | --- | --- | --- |
| Raspberry Pi 5 | HOST-001 | UNKNOWN | HOLD | Design-selected in the stack specification; no physical evidence in the repository |
| HiFiBerry DAC+ ADC Pro | ADC-001 | UNKNOWN | HOLD | Design-selected; sets the binding electrical limit, so its physical presence matters more than most |
| OPA1612 mic preamp | PREAMP-001 | UNKNOWN | HOLD | Design-*specified* custom board; possession and existence are separate open questions |
| Condenser microphone | MIC-001 | UNKNOWN | HOLD | Never locked to a model in the stack specification |
| Audio power amplifier | AMP-001 | UNKNOWN | HOLD | Any amplifier already owned may not match the selected shaker; possession does not imply suitability |
| Speaker / Phase 2A driver | — | UNKNOWN | HOLD | Not an E1 BOM row. Carried here because a physical census will encounter it and its status must not be inferred from its absence from the BOM |
| Force transducer / load cell | FORCE-001 | UNKNOWN | HOLD | Highest-risk selection; unselected |
| IEPE / ICP conditioner | PRECOND-001 | UNKNOWN | HOLD | Selected with the transducer, never after |
| Shaker / exciter | SHAKER-001 | UNKNOWN | HOLD | Paired selection with the amplifier |
| Stand / base hardware | STAND-001 | UNKNOWN | HOLD | Fixture is part of the measurement chain |

The census covers the ten components named in the DO-104S ownership ruling. BOM
rows absent from it — `ATTEN-001`, `STINGER-001`, `TIP-001`, `REF-STRUCT-001`,
`CABLE-001` — are conditional or fabricated items whose possession question is
not meaningful until the chain around them is selected.

### What may not be derived from this table

These are the inference errors this census exists to prevent, and the validator
enforces the first of them:

- `UNKNOWN` → `BUY`. Unknown possession is a reason to *look*, not to purchase.
- `UNKNOWN` → `MISSING`, `NOT_OWNED`, or `ABSENT`. None of those were established.
- Ownership → selection tier. A `PREFERRED_E1` candidate may sit at `UNKNOWN`
  ownership with `procurement_action = HOLD` and nothing is contradictory about it.
- Vendor availability → `RECEIVED`. A distributor holding stock is a fact about
  the distributor.
- Selection → possession. A design selection is not a possession, which is the
  rule the whole BOM validator was built around.

### Procurement action vocabulary

Procurement action is independent of both ownership and selection tier:

| Action | Means |
| --- | --- |
| `HOLD` | No procurement action authorized. The state of every row in this order |
| `VERIFY_POSSESSION` | Resolve ownership by physical census before any purchase decision |
| `RECOMMEND_PURCHASE` | Recommended to a human for purchase authorization; not a purchase |
| `FABRICATE` | Made rather than bought |
| `REJECTED` | Ruled out; reason in the rationale document |

**No row in this order carries an action other than `HOLD`.** DO-104S is
authorized to recommend, not to buy, and the possession census has not run.

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
