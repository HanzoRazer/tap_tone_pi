# TTP E1 — Procurement Authorization Record

**This document exists to record that no procurement is authorized.**

| Field | Value |
| --- | --- |
| `authorization_id` | `TTP-AUTH-001` |
| `authorization_date` | 2026-08-27 |
| `authorization_status` | **`DEFERRED`** |
| `selection_ruling` | **`SELECTION_DEFERRED`** |
| `authorizing_human` | Ross Echols, repository owner |
| `authorized_component_ids` | *(none)* |
| `held_component_ids` | every role except `HOST-001` |
| `use_owned_component_ids` | `HOST-001` |
| `quote_required_component_ids` | `FORCE-001`, `PRECOND-001`, `SHAKER-001`, `AMP-001`, `MIC-001` (reference tier), `STINGER-001` |
| `substitution_policy` | fail-closed; see below |
| `source_evidence_refs` | DO-104S market survey, DO-104R census pass 2, the architecture gate |

**A decision record, not a purchase receipt.** Nothing here orders, buys, or
receives anything.

---

## The ruling

> **`SELECTION_DEFERRED`** — awaiting authorization to proceed with construction
> of the physical TTP prototype Analyzer and displacement jig.

TTP hardware development is **paused**. The market research, the recommended E1
architecture, the ownership census and the software preparation are retained as
**engineering inputs only**. They do not constitute final hardware selection or
purchase authorization.

No analyzer hardware, excitation system, force-measurement chain, displacement
jig, or associated component is authorized for procurement or construction.

## Why the repository is ahead of the project

Three dev orders produced a sourced market survey, a cleared architecture gate, a
tiered BOM, a validated evidence chain and an ownership census. **None of that
required a physical instrument to exist, and none of it produced one.** The
documentation ran ahead of the build, which is a reasonable thing to have
happened and a bad thing to leave unmarked — a reader arriving at a hardened BOM
with a preferred configuration could easily conclude the project is mid-purchase.

It is not. It is paused before the first component.

## The next hardware milestone

**Prototype Analyzer + Displacement Jig Authorization.**

Not another research cycle, not another component comparison, and not another dev
order deciding which ADC to buy. When that authorization is given, the project
reviews the existing recommendations against **availability at that time** and
against prototype requirements, and only then turns research into a concrete
prototype BOM.

### What the prototype needs, and what it does not

Worth stating explicitly, because the repository's most hardened documents
describe a chain the prototype may not need. The E1 `TTP_E1_*` documents specify
the **contact-excitation and force-measurement** architecture. The prototype
milestone names an **Analyzer and a displacement jig** — a different and much
smaller list.

| Prototype element | Where it is specified |
| --- | --- |
| Host, ADC, preamp, microphone | `TTP_E1_HARDWARE_BOM.md` (host already owned) |
| Displacement jig — indicator, frame, supports, calibrated masses | **only** [`bending_rig_construction.md`](../handoffs/bending_rig_construction.md), which has never been a hardware specification |
| Shaker, amplifier, force transducer, force conditioner, stinger, contact tip | `TTP_E1_HARDWARE_BOM.md` — **quite possibly not needed for the prototype** |

Six of the fourteen E1 roles are the excitation chain, and they are the
quote-only, long-lead, expensive ones. **Whether the prototype includes them is
an open question for the authorization**, not something to be assumed from the
BOM's existence.

## State at the time of deferral

| Axis | State |
| --- | --- |
| Physical ownership | `HOST-001` `CONFIRMED_PRESENT` (Raspberry Pi 5 16 GB, `TTP-ASSET-001`); every other role and all jig hardware `CONFIRMED_ABSENT` |
| Compatibility | `HOST-001` `COMPATIBLE` on paper; everything else `NOT_APPLICABLE` — nothing owned to assess |
| Selection | `PREFERRED_E1` chain `RECOMMENDED`; **nothing `SELECTED`** |
| Campaign acquisition | nothing `ORDERED`, nothing `RECEIVED` |

## Substitution policy — fail closed

No substitution is pre-authorized. The one already known:

**The ADC may not be silently replaced.** The architecture gate was cleared
against the HiFiBerry DAC+ ADC Pro's published input specification. Its successor
does not publish that specification and has not been verified. Any substitution
changing input range, gain, coupling, sample architecture, channel count, or
simultaneous-acquisition assumptions **requires the architecture gate to be
re-run first**. B-015 stays open on that basis.

## What remains open, and is not closed by this deferral

- **B-014** — the ADC has no anti-aliasing filter in its input path. Deferring a
  purchase says nothing about aliasing. Closes on measurement or not at all.
- **B-015** — the recommended ADC is superseded by its vendor. Deferral does not
  make it available again; it makes the availability question *later*, which is
  precisely why the authorization must re-check the market.
- **B-016** — closed. A census was performed and corrected.
- **B-017** — census pass 1 produced a false absence. Open.

## Market data is perishable

Every price, stock level and lead time in the BOM carries `checked_date`
**2026-08-25**. Those are observations of a market on a day, not properties of
the components.

**They must be re-verified before any purchase**, however long this pause lasts.
This requirement is written rather than enforced by the validator: a rule that
failed on age would turn a dormant repository red for no reason, and a red check
nobody can act on is worse than no check.

The one market fact already known to be moving is B-015.

## What would change this record

A human authorization to build the prototype. At that point this document is
superseded by a new authorization record — not edited — on the same rule the
census follows: a decision record says what was decided on a date, and rewriting
it destroys the only thing it is good for.
