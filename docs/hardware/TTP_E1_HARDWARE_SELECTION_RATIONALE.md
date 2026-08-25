# TTP E1 — Hardware Selection Rationale

**Status:** rationale for the *architecture*; no product selected.
**Dev Order:** DO-104P

This document exists so that a later reader can tell engineering selection from
product marketing. For each component: what it has to do, what it must at
minimum satisfy, what was chosen and why, what else was considered, and what
remains unresolved.

Where "Selected" reads `TBD`, no product has been chosen and none is implied.

---

## Force chain — transducer, conditioner, and the ADC window

**Required function.** Measure the dynamic force actually delivered into the
drive point, so that the transfer quantity has a measured input rather than a
commanded one.

**Minimum requirements.** Dynamic force measurement; range covering the
shaker's output at E1 levels; threaded mounting compatible with both the shaker
armature and the stinger; low mass; a conditioning path landing inside the
ADC's ±3 V window.

**Selected.** `TBD`. The architecture is settled — path A, IEPE/ICP transducer
into a constant-current conditioner into ch0 of the existing ADC.

**Why this architecture.** The strongest property of the existing design is
simultaneous two-channel acquisition on a single sample clock, which Phase 2's
transfer-function and coherence path assumes. Conditioning the force signal
*into* that ADC preserves it. Replacing the ADC to get a "proper" DAQ would
trade a proven synchronized capture for an unproven one, which is the wrong
trade at this stage.

**Alternatives considered.**

| Path | Why not the baseline |
| --- | --- |
| B — piezoelectric + charge amplifier | Viable, and relevant if IEPE conditioning proves unobtainable or disproportionate. Charge amps add their own calibration and cabling sensitivities |
| C — strain / load cell + instrumentation amplifier | Cheapest credible force measurement, but bandwidth is typically the casualty, and E1 needs the band more than it needs the saving |
| D — replacement multi-channel interface | Last resort. Abandons the existing ADC and its proven synchronized capture, so the architectural cost exceeds the problem it solves |

**What was explicitly rejected.** Driving a surface exciter at a commanded
level and treating drive voltage as the input. DO-103 §4.2 forbids it, and it is
the specific failure mode a cost ceiling would push toward. Measured force means
measured force; a cheaper tier may have a worse sensor, never no sensor.

**Unresolved concern.** The conditioner's output window. A conditioner with
±5 V or ±10 V full scale needs attenuation designed in as a BOM line item
(`ATTEN-001`), not corrected by software scaling. Until a specific conditioner
is chosen, whether `ATTEN-001` exists is genuinely open.

**E1 risk affected.** Force-channel risk, and the "measured is not traceable"
boundary — traceability stays `UNKNOWN` unless a certificate arrives with the
sensor.

---

## Shaker and amplifier

**Required function.** Deliver controlled mechanical excitation to the drive
point through the force transducer, with the shaker body grounded.

**Minimum requirements.** Grounded mounting; rigid reaction path to the base;
armature accepting the transducer; enough force to excite a plate-scale
reference body at low level; amplifier matched on impedance, voltage, and
current.

**Selected.** `TBD`, as a **pair**. Selecting a shaker without solving its
amplifier is how hardware gets damaged.

**Why grounded.** DO-103 §4.2 and DO-104P §4.1 fix this. A bonded exciter that
rides on the specimen becomes part of the moving system, and the measurement
stops being of the specimen. The shaker's mass must sit on the stand.

**Alternatives considered.** Bonded surface exciters and speaker-air excitation
are both out of scope for this order and are not reopened. The legacy speaker
path remains documented for provenance (see stack spec Phase 2A) and is not part
of this BOM.

**Unresolved concern.** Whether the existing DAC output level can drive the
chosen amplifier's input without an intermediate stage. That is an interface
question, tracked in the [matrix](TTP_E1_INTERFACE_MATRIX.md).

**E1 risk affected.** Excitation variability (R1), and fixture behaviour if the
stand and shaker mounting contribute resonances.

---

## Stinger and contact tip

**Required function.** Transmit axial drive from the transducer into the
specimen while adding as little moving mass and as little lateral load as
possible.

**Minimum requirements.** Low effective moving mass; sufficient axial
stiffness; low lateral load transfer; a replaceable, identified tip with
documented geometry and measurable mass.

**Selected.** `TBD`, fabricated rather than purchased is expected.

**Why fabricated.** The design space is small, the parts are simple, and the
mass target matters more than any commercial feature. A fabricated stinger is
also easier to iterate during E1, which is a phase where the rig is *supposed*
to change.

**On the mass target.** Roughly 1–2 g is a design target carried forward from
first-order analysis. It is **not** a certification requirement and no test
anywhere treats it as a pass mark — DO-103 §4.9 removed exactly that inherited
figure, and DO-104 records the *measured* masses instead. The three recorded
masses are independent quantities: the component masses describe the hardware,
and `combined_contact_mass_g` is the effective mass participating at the
specimen interface, which may legitimately be lower than their sum.

**Unresolved concern.** Thread compatibility with whichever transducer is
chosen, and whether a tip geometry can be made repeatable enough that contact
condition is a recorded variable rather than a dominant one. E3 exists to expose
the latter; E1 only has to show the rig works at all.

**E1 risk affected.** Contact risk, structural-perturbation risk, and the
stinger-resonance observation E1 is explicitly required to record rather than
notch out.

---

## Microphone and preamplifier

**Required function.** Acquire the acoustic response with a non-contact sensor.

**Minimum requirements.** Small-diaphragm condenser preferred; 48 V phantom
from the existing preamp; output reaching 0.8–2.1 Vrms into the ADC after gain.

**Selected.** Preamp architecture is design-selected (OPA1612, stack spec
Stage 2). Microphone model is `TBD` — the stack specification never locked one,
which the BOM now records honestly rather than implying a choice exists.

**Why a microphone rather than an accelerometer.** DO-103 §4.3: an accelerometer
adds local mass, and E5 exists specifically to measure the effect of added mass.
Introducing a mass-loading response sensor in the same campaign would confound
the perturbation being measured with the instrument measuring it.

**Unresolved concern.** Traceability. Without a calibrated microphone the
pressure magnitude is not laboratory-traceable, and every report says so. This
order does not procure calibration.

**E1 risk affected.** Response-channel risk — specifically that room and air
behaviour may obscure the structural response, which is a limitation to record
rather than correct.

---

## Host and acquisition

**Required function.** Generate the drive signal and capture both channels
simultaneously on one clock.

**Minimum requirements.** Two simultaneous input channels; shared sample clock;
48 kHz or better; an output path for drive.

**Selected.** Raspberry Pi 5 and HiFiBerry DAC+ ADC Pro, both **design-selected
in the stack specification and not confirmed owned**.

**Why keep them.** They already satisfy the hardest requirement — synchronized
two-channel capture — and the existing software is built around them. The E1
change is what ch0 *carries*, not the acquisition device.

**Unresolved concern.** Whether the physical Pi and ADC exist. The repository
contains no evidence of any physical capture: every session in `runs_phase2/` is
`"synthetic": true` with `"device": null`, or the `DEMO` fixture. That is why
these rows sit at `SELECTED` and cannot advance without an identity-register
entry.

**E1 risk affected.** Evidence-integrity risk. A design mistaken for a
possession is exactly how a campaign discovers on bench day that it has nothing
to bench.

---

## Stand, base, and reference structure

**Required function.** Ground the shaker, carry its reaction away from the
specimen, and present a structure worth driving that nobody minds damaging.

**Minimum requirements.** Base mass independent of the specimen support;
vertical adjustment; cable strain relief; a reference body that is inexpensive,
stable, replaceable, and plate-scale.

**Selected.** `TBD`.

**Why a reference body first.** DO-104P §4.10 and DO-104 §4.10 both order it: a
sacrificial plate before any finished instrument. E1 characterizes the rig, and
the first structure under a new shaker is the wrong place for something
valuable.

**Unresolved concern.** Fixture resonance. The stand is part of the measurement
chain and will contribute; E1 records what it contributes rather than assuming
it away.

**E1 risk affected.** Fixture risk, and the scientific-integrity risk of tuning
the stand until results look clean without recording what the earlier
configuration showed.

---

## What none of this establishes

Datasheet figures are provenance for a nominal value: bandwidth, rated force,
sensitivity, mass, pinout. They do not establish installed-system behaviour.
Whether this chain produces usable evidence over any defensible band is E1's
question, and DO-104P closes before any part of it is answered.
