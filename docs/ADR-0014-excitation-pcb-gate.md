# ADR-0014: Excitation PCB Layout Gate

**gate_verdict:** `BLOCKED`
**Status:** Accepted
**Date:** 2026-09-02
**Dev Order:** DO-108P
**Supersedes:** None
**Related:** ADR-0001 (measurement scope), ADR-0011 (measurement authority),
ADR-0012 (epistemic status taxonomy)

---

## Context

The TTP Analyzer can command a waveform and cannot deliver it into a plate. The
missing subsystem is a power amplifier and an electrodynamic exciter, and the
commercial intent is for the amplifier to live on a TTP board inside the
instrument rather than as a separate box on the operator's bench.

The pressure this ADR exists to resist is straightforward and familiar: the parts
are cheap, the reference designs are plentiful, and it is very easy to lay out a
board now. A 50 W Class-D module is a fifteen-minute schematic. What is *not*
available is any of the information that would make it the right board:

- No measured TTP enclosure — nobody has yet established whether a case even
  exists — so its outline, height, mounting, rails, keep-outs and the distance
  to the analog acquisition section are all unknown.
- No measurement of the drive an exciter actually needs to produce a usable
  modal response on a plate. The exciters' rated powers are tolerance figures,
  not requirements.
- No measurement of whether a switching stage can share an enclosure with a
  microphone preamp and an ADC that has no anti-aliasing filter.

A board designed without those is a board designed against assumptions, and the
assumptions would be invisible in the Gerbers. Someone reading the layout a year
later would find a 12 V rail and a 3 W ceiling and have no way to learn that both
were guesses.

## Decision

> **A custom excitation PCB may not enter schematic capture or layout design
> until the enclosure dimensions and the required electrical output envelope have
> been measured, or bounded by the bench characterization protocol.**

The gate has a verdict, recorded in this file's header and checked by
`scripts/check_e1_hardware_bom.py`. It is `BLOCKED`, and it may read
`READY_FOR_SCHEMATIC` only when every input below is satisfied by evidence.

### Gate inputs

| Input | State | Established by |
| --- | --- | --- |
| PCB envelope known | `UNRESOLVED` | [enclosure survey](hardware/TTP_EXCITATION_PCB_ENVELOPE.md) — `ENCLOSURE_EXISTENCE_NOT_VERIFIED`; nobody has looked for a case |
| DAC interface known | partial | manufacturer maximum 2.1 Vrms; output impedance not published |
| Power rail known | `UNRESOLVED` | enclosure survey |
| 4 Ω and 8 Ω load requirement confirmed | **yes** | manufacturer data for the three registered candidates |
| Minimum useful drive measured | `TBD_MEASURE` | [characterization protocol](hardware/TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md), `NOT_EXECUTED` |
| Maximum intended drive chosen | `TBD_MEASURE` | as above |
| Thermal requirement bounded | `TBD_MEASURE` | as above |
| EMI strategy chosen | `UNRESOLVED` | protocol step P9, then a design decision |

One input is satisfied, and it is worth noting which one: the load requirement.
It is satisfied because it came from manufacturer documents rather than from a
measurement, which is exactly what makes it available this early — and exactly
why it is the only one.

### Gate output

```text
READY_FOR_SCHEMATIC   every input above satisfied by evidence
BLOCKED               otherwise
```

Current verdict: **`BLOCKED`**.

## Consequences

**What is blocked.** Schematic capture, layout, Gerber generation, connector and
thermal design, final supply-rail selection, final amplifier part selection, and
any procurement authorization for the excitation stage.

**What is not blocked, and is proceeding.** The
[architecture](hardware/TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md), the
[amplifier requirements](hardware/TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md), the
candidate registry in the [E1 BOM](hardware/TTP_E1_HARDWARE_BOM.md), the
[characterization protocol](hardware/TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md),
and the drive-budget utility. DO-108P delivered all of these with the gate
closed, because defining what must be measured does not require having measured
it.

**Off-the-shelf amplifier boards remain available as bench surrogates.** Using
one to run the protocol is not a violation of this gate and does not select an
architecture. The gate governs *TTP's own board*, not what sits on a bench while
the measurements are taken.

**The gate closing is a normal outcome, not a failure of DO-108P.** Missing
enclosure dimensions and missing measured drive requirements are the expected
state at this point in the campaign. An order that produced a `READY_FOR_SCHEMATIC`
verdict from the evidence currently available would have produced it by
inventing something.

## Alternatives considered

**Lay out a general-purpose 50 W stage now and fit the enclosure later.** This is
the path the gate exists to refuse. It inverts the dependency — the board would
define the enclosure, the drive level and the thermal design, and the
measurements would become a formality performed against a board already
committed. It also oversizes by an unknown factor: nothing suggests a plate
measurement needs 50 W, and a larger output stage is a larger noise and EMI
source sitting next to an unfiltered converter.

**Bound the requirement from the exciters' rated power instead of measuring.**
Rejected. A 10 W or 24 W rating states what the device survives. Using it as a
requirement would make the amplifier specification a property of the exciter's
thermal limit rather than of the measurement, and would be an inference wearing
a manufacturer's number.

**Keep the amplifier external and skip the board entirely.** A legitimate product
decision, but not this one: the commercial architecture places the amplifier
inside the instrument, and that decision is recorded in the architecture document
rather than reopened here. This ADR governs when the board may be designed, not
whether it should exist.

## Compliance with the measurement boundary

This ADR authorizes no interpretation, no advisory logic and no design
optimization. It gates hardware work on evidence and records what evidence is
missing. The chain it governs carries no force channel, and nothing here creates
one: see
[the commercial excitation architecture](hardware/TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md)
§10 for what a commercial TTP run may and may not claim about its own excitation.
