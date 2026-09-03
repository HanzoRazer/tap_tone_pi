# TTP Exciter Power Characterization — Bench Protocol

**execution_status:** `NOT_EXECUTED`
**Status:** protocol defined. No step below has been performed and no value
below exists.
**Dev Order:** DO-108P defines it; a successor bench order executes it.
**Prerequisite hardware:** none of it is possessed — see the
[ownership census](TTP_E1_OWNERSHIP_CENSUS.md).

---

## Purpose

> Determine the minimum electrical drive required for reliable modal excitation,
> before sizing the custom power stage.

This is the primary PCB-sizing experiment. Every `TBD_MEASURE` in
[the amplifier requirements](TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md) is an
output of this protocol, and the layout gate stays `BLOCKED` until they exist.

## What it may and may not claim

The protocol measures **electrical drive** and **acoustic response**. It records
them as two separate things and never divides one by the other to produce a
force.

| Quantity | Claimable | How |
| --- | --- | --- |
| Commanded waveform and level | yes | the Analyzer emitted it |
| Amplifier output Vrms, Irms, electrical power | yes | measured at the amplifier terminals |
| Modal SNR, identified frequencies, repeatability | yes | measured on the response channel |
| `BL × I` motor-force scale | as a **scale only** | arithmetic on a manufacturer BL |
| Force delivered to the plate | **no** | there is no force channel |

`BL × I` is not force at the specimen. The bond, stinger, tip, preload and the
plate's own mechanical impedance all sit between the motor and the plate, and
none of them is characterized.
[`scripts/exciter_drive_budget.py`](../../scripts/exciter_drive_budget.py)
prints that caveat on every invocation, and no step below may restate the number
without it.

## Identity requirements

A level that produced a good result is meaningless without knowing what produced
it. Every energized step records, without exception:

```text
exciter identity      SHAKER-001 / SHAKER-002 ... plus manufacturer and model
stinger identity      STINGER-001 ... asset label, geometry, measured mass
tip identity          TIP-001 ... asset label, geometry, measured mass
amplifier identity    AMP-001 ... plus the surrogate board's own identity
amplifier gain        the actual configured gain, in dB
plate identity        REF-STRUCT-001 or the specimen's own ID
microphone identity   MIC-001 ... plus its calibration reference if any
```

Masses are **measured, not target**. A stinger designed for 1.5 g that came off
the bench at 2.3 g is a 2.3 g stinger, and the modal result depends on the real
one.

## Test sequence

Each step is a gate on the next. A step that cannot be completed stops the
sequence and gets recorded as stopped; it is not skipped.

| # | Step | Purpose | Energized |
| --- | --- | --- | --- |
| **P0** | Electrical checkout into a dummy load | Confirm the amplifier produces what is commanded, into a known resistor, before anything mechanical is attached | yes |
| **P1** | Exciter free-air checkout | Confirm the exciter moves and is undamaged, uncoupled | yes |
| **P2** | Fixture and stinger mechanical checkout | Confirm the exciter body is fixture-supported and only the stinger reaches the plate | no |
| **P3** | Plate contact, amplifier off | Establish whether merely touching the stinger to the plate shifts the modes | no |
| **P4** | Low-level excitation | Find the lowest drive producing any identifiable modal response | yes |
| **P5** | Stepped amplitude sweep | Map response against drive across the usable range | yes |
| **P6** | Repeatability | Re-run fixed points, re-seating between runs, to separate drive effects from setup effects | yes |
| **P7** | Thermal drift | Hold drive and observe whether exciter heating moves the result | yes |
| **P8** | Distortion and spectral contamination | Look for harmonics and intermodulation the drive stage introduced | yes |
| **P9** | EMI interaction with the ADC and microphone | Command silence, energize the stage, and measure the acquisition path | yes |

Two of these are frequently omitted from bench work of this kind and are
mandatory here.

**P3 runs with the amplifier off, and it is not a formality.** A tap-tone
measurement is taken on a plate that a stinger is touching. If contact alone
shifts the modes, every subsequent number is a measurement of the plate plus the
stinger, and the size of that shift is a property the commercial product has to
live with. The baseline is a tap response with nothing touching the plate,
compared against a tap response with the stinger in contact at working preload.

**P9 is the one that decides whether the architecture works at all.** The
commercial premise is a switching amplifier inside the same enclosure as a
microphone preamp and an ADC with no anti-aliasing filter. If the drive stage
raises the noise floor or plants tones in the acquisition path, no amount of
board layout later recovers it, and the finding belongs before the layout rather
than after.

## Recorded quantities, per energized level

Electrical and mechanical quantities are recorded in separate columns and never
combined:

```text
--- commanded ---
commanded waveform (type, frequency or sweep parameters)
commanded DAC level
--- drive-side electrical, measured ---
amplifier gain (dB, configured)
supply voltage (V)
output Vrms
output Irms                          where a current measurement is available
estimated electrical power           derived from the two above; marked derived
--- identity ---
exciter / stinger / tip / amplifier / plate / microphone identity
preload                              method and value, or "not controlled"
--- response-side, measured ---
modal SNR
identified frequencies
repeatability across runs
--- conditions ---
temperature (ambient, and exciter body where measurable)
fault state                          from FAULTZ or equivalent, per step
```

`estimated electrical power` is marked derived because it is: it comes from the
measured voltage and either the measured current or the nominal impedance. A
nominal 4 Ω exciter is not 4 Ω at every frequency, and a power computed from
nominal impedance carries that error.

**`fault state` is recorded per step, including when it is clean.** A protection
event partway through a sweep changes what that sweep means, and "no fault
recorded" is only informative if the field is always filled.

## Acceptance criteria for the successor bench order

The bench order is complete when it can answer these, with evidence:

```text
What minimum Vrms produces usable modal SNR?
What minimum electrical power is required?
What amplitude range remains repeatable?
Does exciter heating change the result?
Does the Class-D stage contaminate the ADC or microphone path?
Does merely touching the stinger to the plate shift the modes?
How sensitive is the result to preload?
Which exciter gives the best response per unit electrical drive?
Does DAEX25FHE-4's higher BL provide a practical advantage?
Does DAEX25CT-4's lower moving mass provide a practical advantage?
```

The last two are **empirical questions, not datasheet conclusions.** The FHE has
roughly 2.4 times the BL and roughly 1.25 times the moving mass of the CT
(*manufacturer* values, [BOM](TTP_E1_HARDWARE_BOM.md)). Which of those dominates
on a light wooden plate is not derivable from those two numbers, and a protocol
that answered them from the datasheet would not have needed a bench.

## What executing this protocol does not do

It does not select an exciter, select an amplifier, authorize a purchase, or open
the PCB layout gate on its own. It produces the measured envelope that
[ADR-0014](../ADR-0014-excitation-pcb-gate.md) requires; the enclosure survey is
a separate input, and the gate needs both.
