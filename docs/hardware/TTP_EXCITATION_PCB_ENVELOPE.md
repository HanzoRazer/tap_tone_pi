# TTP Excitation PCB — Enclosure Envelope

**survey_status:** `ENCLOSURE_NOT_AVAILABLE_FOR_MEASUREMENT`
**Dev Order:** DO-108P
**Consequence:** PCB geometry is `UNRESOLVED`, and the layout gate in
[ADR-0014](../ADR-0014-excitation-pcb-gate.md) is `BLOCKED`.

---

## Why the status is what it is

There is no TTP Analyzer enclosure to measure. This is a stronger and more useful
statement than "the survey has not been performed", so it gets its own status
rather than borrowing that one.

The two states differ in what would change them:

| Status | Means | Cleared by |
| --- | --- | --- |
| `ENCLOSURE_NOT_AVAILABLE_FOR_MEASUREMENT` | No enclosure exists to put calipers on | an enclosure existing |
| `NOT_PERFORMED` | An enclosure exists; nobody has measured it | somebody measuring it |
| `PERFORMED` | Measured, with every dimension carrying a real value | — |

Recording this as `NOT_PERFORMED` would imply a case sitting on a bench waiting
for a tape measure, and would make the survey look like an afternoon's work
rather than a gate on hardware that does not exist.

### How that was established

Not by a census category — the [ownership census](TTP_E1_OWNERSHIP_CENSUS.md)
enumerates ten equipment categories and an enclosure is not among them, so
nobody has looked *for an enclosure* as such. It follows instead from the build
state the campaign records already carry:

```
Pi 5 (owned) -> ADC-001 -> characterize (E0) -> design AFE-001
   -> build Analyzer -> [an Analyzer enclosure could exist here]
        ^
        |
   blocked: ADC-001 is CONFIRMED_ABSENT, E0 is NOT EXECUTED
```

The Analyzer prototype has not been built, and an enclosure for an instrument
that does not exist cannot be measured. That is an inference from documented
state, and it is labelled as one.

**It is not a claim that no enclosure will ever be chosen.** If a candidate case
is selected ahead of the build — a stock extruded or ABS enclosure, say — then a
physical unit exists, this status becomes `NOT_PERFORMED`, and the table below
becomes an afternoon's work.

## The survey

Every row is measured, not inferred. **The developer must not take any dimension
from a photograph, a vendor drawing, or old CAD without physically
reconfirming it.** A vendor drawing describes the part the vendor ships; it does
not describe the case after a Pi, a HiFiBerry board, standoffs and a wiring loom
are inside it, and the usable volume is what this table is about.

| Parameter | Value | Method | Evidence |
| --- | ---: | --- | --- |
| usable board width | TBD | physical measurement | pending |
| usable board length | TBD | physical measurement | pending |
| maximum component height | TBD | physical measurement | pending |
| mounting locations | TBD | physical inspection | pending |
| keep-out zones | TBD | physical inspection | pending |
| Pi clearance | TBD | physical inspection | pending |
| HiFiBerry clearance | TBD | physical inspection | pending |
| connector edge access | TBD | physical inspection | pending |
| power entry | TBD | physical inspection | pending |
| ventilation | TBD | physical inspection | pending |
| internal cable routing | TBD | physical inspection | pending |
| distance to the microphone / ADC analog section | TBD | physical measurement | pending |

The last row is the one that is easy to record as an afterthought and expensive
to get wrong. A Class-D switching stage and an unfiltered 24-bit converter in one
box is a coexistence problem before it is a geometry problem — see
[the amplifier requirements](TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md), *EMI*.
The physical separation available is an input to that, and it is bounded by the
case rather than chosen by the designer.

## Rules this table is held to

**The survey is not complete while any dimension reads `TBD`.** A partially
measured envelope is not a small envelope; it is an unknown one, and a layout
started against it would be laid out against the rows that happened to be filled
in. `scripts/check_e1_hardware_bom.py` refuses a `PERFORMED` status with any
`TBD` remaining.

**Measured values carry their method.** "Physical measurement" and "physical
inspection" are different claims — one produces a number with a tolerance, the
other confirms that something is present and reachable — and the column stays
because the distinction survives into the layout decision.

**A dimension is not a requirement.** What fits is a constraint on the design;
what the design needs is the
[amplifier requirements](TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md) and the
measured drive envelope. Both must exist before the gate opens, and a small case
does not lower the required output power by a single milliwatt.

## What this blocks, and what it does not

Blocked: schematic capture, layout, Gerber generation, connector placement,
thermal design, and the final supply-rail choice.

Not blocked, and proceeding: the requirement statements, the candidate registry
in the [E1 BOM](TTP_E1_HARDWARE_BOM.md), the
[characterization protocol](TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md), the
drive-budget utility, and the bench qualification that follows. The absence of an
enclosure does not stop the work that determines what the enclosure must hold.
