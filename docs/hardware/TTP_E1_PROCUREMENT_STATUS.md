# TTP E1 — Procurement Status

**Status:** three components design-selected (possession unconfirmed); no
component selected for purchase, ordered, or received. Physical ownership is
`UNKNOWN` for every component — no physical census has been performed.
**Dev Order:** DO-104P; ownership census added under DO-104S
**Last updated:** 2026-08-27 (DO-104R census pass 2 — erratum)

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

**Superseded by DO-104R census pass 2 (2026-08-27).** One item is owned — a
Raspberry Pi 5 16 GB, in hand since April 2025. Every component below is
now `CONFIRMED_ABSENT`: a census was performed and found no E1-relevant
hardware in possession. The `UNKNOWN` that this section originally recorded was
the honest pre-census state; it has been resolved by observation, not by
inference. The vocabulary and the anti-inference rules below still govern.

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
| Raspberry Pi 5 16 GB | HOST-001 | CONFIRMED_PRESENT | USE_OWNED | Owned since 2025-04, outside this campaign. Asset `TTP-ASSET-001`; never ORDERED, not RECEIVED by this campaign |
| HiFiBerry DAC+ ADC Pro | ADC-001 | CONFIRMED_ABSENT | HOLD | Design-selected; sets the binding electrical limit, so its physical presence matters more than most |
| OPA1612 mic preamp | PREAMP-001 | CONFIRMED_ABSENT | HOLD | Design-*specified* custom board; possession and existence are separate open questions |
| Condenser microphone | MIC-001 | CONFIRMED_ABSENT | HOLD | Never locked to a model in the stack specification |
| Audio power amplifier | AMP-001 | CONFIRMED_ABSENT | HOLD | Any amplifier already owned may not match the selected shaker; possession does not imply suitability |
| Speaker / Phase 2A driver | — | CONFIRMED_ABSENT | HOLD | Not an E1 BOM row. Carried here because a physical census will encounter it and its status must not be inferred from its absence from the BOM |
| Force transducer / load cell | FORCE-001 | CONFIRMED_ABSENT | HOLD | Highest-risk selection; unselected |
| IEPE / ICP conditioner | PRECOND-001 | CONFIRMED_ABSENT | HOLD | Selected with the transducer, never after |
| Shaker / exciter | SHAKER-001 | CONFIRMED_ABSENT | HOLD | Paired selection with the amplifier |
| Stand / base hardware | STAND-001 | CONFIRMED_ABSENT | HOLD | Fixture is part of the measurement chain |

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
| `USE_OWNED` | Filled by hardware already possessed; requires ownership `CONFIRMED_PRESENT` |
| `NO_PURCHASE_REQUIRED` | Nothing to buy for this role; requires ownership `CONFIRMED_PRESENT` |
| `FABRICATE` | Made rather than bought |
| `REJECTED` | Ruled out; reason in the rationale document |

**Every row carries `HOLD` except `HOST-001`, which carries `USE_OWNED`.**
That one exception is not a procurement decision — it records that the role is
already filled and therefore has nothing to procure. DO-104S is
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

## DO-104S procurement recommendation

This section is the human-readable procurement decision package. It is
deliberately **separate from the ownership census above**, and neither one may
be derived from the other.

### The recommendation

| Role | Recommended product | Selection status | Ownership | Procurement action |
| --- | --- | --- | --- | --- |
| FORCE-001 force_transducer | PCB Piezotronics 208C01 | RECOMMENDED | CONFIRMED_ABSENT | HOLD |
| PRECOND-001 force_conditioner | PCB Piezotronics 480C02 | RECOMMENDED | CONFIRMED_ABSENT | HOLD |
| SHAKER-001 shaker | Brüel & Kjær Type 4810 | RECOMMENDED | CONFIRMED_ABSENT | HOLD |
| AMP-001 amplifier | Brüel & Kjær Type 2718 | RECOMMENDED | CONFIRMED_ABSENT | HOLD |
| MIC-001 microphone | Earthworks M23 G2 | RECOMMENDED | CONFIRMED_ABSENT | HOLD |
| ADC-001 adc_interface | HiFiBerry DAC+ ADC Pro | DESIGN_SELECTED, retained | CONFIRMED_ABSENT | HOLD |
| HOST-001 host | owned: Raspberry Pi 5 16GB; candidate priced as Raspberry Pi 5 8GB | DESIGN_SELECTED, retained | CONFIRMED_PRESENT | USE_OWNED |
| PREAMP-001 mic_preamp | OPA1612 design | DESIGN_SPECIFIED, retained | CONFIRMED_ABSENT | HOLD |
| STINGER-001 stinger | B&K 10-32 UNF stinger stock, 50 mm, or fabricated | RECOMMENDED | CONFIRMED_ABSENT | HOLD |
| TIP-001 contact_tip | fabricated | NOT_SELECTED | CONFIRMED_ABSENT | HOLD |
| STAND-001 stand_base | fabricated | NOT_SELECTED | CONFIRMED_ABSENT | HOLD |
| REF-STRUCT-001 reference_structure | fabricated | NOT_SELECTED | CONFIRMED_ABSENT | HOLD |
| ATTEN-001 attenuator | none — not required by the recommended pairing | CONDITIONAL | CONFIRMED_ABSENT | HOLD |
| CABLE-001 cabling | six interconnects enumerated in the interface matrix | RECOMMENDED | CONFIRMED_ABSENT | HOLD |

**`RECOMMENDED` is a new status and it is deliberately weaker than `SELECTED`.**
It means DO-104S would choose this product and has shown the chain it sits in
connects. It does not mean the campaign has chosen it — that ratification is a
human decision.

**Every action is `HOLD`, including for the recommended items.** Two independent
reasons, either of which is sufficient: no budget is authorized, and no physical
census has been performed. The validator enforces the second one directly —
`RECOMMEND_PURCHASE` requires ownership `CONFIRMED_ABSENT`, and nothing here is
established as absent.

### The next action is not a purchase

The correct next step is **`VERIFY_POSSESSION`**: a physical census of the bench
that moves each row from `UNKNOWN` to `CONFIRMED_PRESENT` or `CONFIRMED_ABSENT`.
Until that runs, a purchase order built from this table could duplicate
equipment already owned — most plausibly the host, the ADC board, the
microphone, or an amplifier, which are the four items a working audio bench is
most likely to already have.

Only after the census can a purchase be recommended, and only for rows that came
back `CONFIRMED_ABSENT`.

### What a decision-maker still does not have

| Missing | Why it is missing | How to get it |
| --- | --- | --- |
| A total cost | PCB, Hottinger Brüel & Kjær, GRAS and FUTEK quote rather than publish | Request quotations — a procurement activity this order does not authorize |
| Lead times for the instrument-grade items | Same reason | Same |
| A physical inventory | No census has been performed | Run the census |
| Confidence that the ADC will remain available | The recommended board is superseded by its vendor | Decide between procuring while available and verifying the successor's input specification |

### Substitution rules carried forward

The one substitution that must **not** be made silently is the ADC. The
architecture gate was cleared against the DAC+ ADC Pro's published input
specification. Its successor does not publish that specification on its product
page and it was not verified here, so swapping boards invalidates the gate
verdict until the gate is re-run. That is recorded in the substitution log
below, in advance, because the supersession is already known.


## Substitution log

No substitutions. When one occurs, DO-104P §4.13 requires it recorded here
*before* bench use, never silently:

| Planned | Replacement | Reason | Affected interface | Review disposition |
| --- | --- | --- | --- | --- |
| HiFiBerry DAC+ ADC Pro | HiFiBerry DAC2 ADC Pro | Vendor supersession; the DAC+ is described as available in larger quantities for OEM customers on request | ADC input window and gain range — the whole force-chain level budget | **Not authorized.** The gate was cleared against the DAC+ published input specification. The successor does not publish one on its product page and it was not verified here, so this substitution requires the architecture gate to be re-run first |
