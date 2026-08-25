# TTP E1 — Hardware Requirements

**Status:** requirements frozen; no product selected.
**Dev Order:** DO-104P; extended by DO-104S — E1 Hardware Selection, Procurement, and Bench Readiness

This document exists to be written *before* anyone looks at a product page.
DO-104P §10 Stage 0 is explicit about the order: freeze what each component has
to do, then search. Reversing it produces a bench of individually excellent
parts that cannot connect.

Related: [BOM](TTP_E1_HARDWARE_BOM.md) ·
[Interface matrix](TTP_E1_INTERFACE_MATRIX.md) ·
[Rationale](TTP_E1_HARDWARE_SELECTION_RATIONALE.md) ·
[Stack spec](TTP_HARDWARE_STACK.md)

---

## The requirement that cannot be traded away

**Measured force means measured force.**

DO-103 §4.2 settled this: drive voltage alone is insufficient, and every run
intended to contribute excitation evidence must preserve a measured force
channel. The cheap path — a surface exciter driven at a commanded level — fails
this, and no saving justifies it. If the budget cannot reach a real force
measurement, the correct outcome is to say so and stop, not to substitute
commanded voltage and call it excitation evidence.

Everything else here is negotiable. This is not.

## Architecture being equipped

Settled by DO-103 and DO-104, not reopened here:

```
rig base → stand → grounded shaker → force transducer → stinger → contact tip
                                                                       ↓
                                                             reference structure
                                                                       ↓
                                                                  microphone
```

Channel assignment for E1 (see [stack spec](TTP_HARDWARE_STACK.md) Rev 1.4,
Phase 2B):

| Channel | Carries | Path |
| --- | --- | --- |
| ch0 | measured force | transducer → IEPE conditioner → line level → ADC |
| ch1 | acoustic pressure | microphone → OPA1612 preamp + phantom → ADC |

The transfer quantity is acoustic pressure per unit measured force, `Pa/N`. It
is not mobility, accelerance, or receptance.

## The binding constraint: the existing ADC

The strongest part of the existing design is **simultaneous two-channel
acquisition on one sample clock**. Phase 2's transfer-function and coherence path
assumes it, and DO-104P §4.5 forbids software compensation for unsynchronized
devices. Preserving it is why the force chain conditions *into* the existing ADC
rather than replacing it.

That ADC sets hard electrical limits ([stack spec](TTP_HARDWARE_STACK.md) Stage 3):

| Parameter | Value | Consequence for selection |
| --- | --- | --- |
| Input range | ±3 V, AC-coupled | A conditioner outputting ±5 V or ±10 V full scale **needs attenuation or range selection**, designed in — not scaled away in software |
| Optimal region | 0.8–2.1 Vrms | Target the conditioner's expected working output into this window |
| Coupling | AC | Dynamic force only; no static preload readout from this path |
| Connector | RCA, unbalanced | Conditioner output must reach RCA without a ground loop |
| Channels | 2 | The force channel *consumes* ch0, which the legacy architecture used for a reference microphone |
| Bit depth / rate | 24-bit, 48/96 kHz | Sets the usable analysis band well above the region E1 cares about |

**The ch0 reassignment is the substantive architectural change in this order.**
It is not additive: E1 cannot run the legacy speaker-and-two-microphone
configuration and the contact-drive configuration at the same time on this ADC.

---

## Component requirements

Each table is written as *requirements*, with product identity deliberately
absent. `TBD` here means "not selected yet", never "unimportant".

### Force transducer — the highest-risk selection

| Requirement | Value / criterion |
| --- | --- |
| Measures | Dynamic force at the drive point |
| Type | IEPE/ICP preferred (baseline path A) |
| Sensitivity | Recorded in the unit the manufacturer states it in; not converted, not assumed |
| Range | Must cover the force the shaker delivers at E1 drive levels without clipping |
| Mounting | Threaded interface compatible with both shaker armature and stinger |
| Mass | Contributes to moving contact mass; low is better, and it is **measured, not assumed** |
| Conditioning | **Selected together with the sensor, never after** |
| Traceability | `UNKNOWN` unless a calibration certificate is supplied. Measured is not traceable |

### IEPE / ICP conditioner

| Requirement | Value / criterion |
| --- | --- |
| Supplies | Constant current appropriate to the chosen sensor (commonly 2–20 mA at 18–30 V) |
| Output | AC-coupled voltage reaching the ADC inside ±3 V, ideally 0.8–2.1 Vrms |
| Gain / attenuation | Must have a usable setting for that window, **or** an explicit attenuator is added to the BOM as its own line item |
| Channels | 1 minimum |
| Noise floor | Below the ADC's own contribution at the working level |
| Connector | Sensor side per transducer; output side reaching RCA unbalanced |

### Shaker and amplifier — selected as one pair

| Requirement | Value / criterion |
| --- | --- |
| Architecture | **Grounded.** The shaker body must not ride on the specimen |
| Mounting | Rigid attachment to the stand, with a reaction path to the base |
| Armature interface | Accepts the force transducer, then the stinger |
| Force capability | Enough to excite a plate-scale reference structure at low level; excess is not a virtue |
| Frequency range | Comfortably beyond the intended E1 region where practical |
| Amplifier match | Impedance, voltage, and current compatible with the shaker — verified as a pair, not separately |
| Amplifier input | Accepts the existing DAC output level |

### Stinger and contact tip

| Requirement | Value / criterion |
| --- | --- |
| Effective moving mass | Low. Design target roughly **1–2 g**, provisional |
| Axial stiffness | Sufficient to transmit drive in the intended band |
| Lateral compliance | Deliberately low load transfer off-axis |
| Tip | Replaceable without replacing the shaker assembly, stable ID, documented geometry, measurable mass |
| Fabrication | May be fabricated rather than purchased; the design is still specified and identified |

**The 1–2 g figure is a design target from first-order analysis, not a
certification requirement** (DO-104P §4.7, DO-103 §4.9). The *measured* mass is
authoritative, and E1 characterizes what it actually does. Nothing in this
program treats 2 g as a pass mark.

### Microphone and preamp

| Requirement | Value / criterion |
| --- | --- |
| Type | Small-diaphragm condenser preferred |
| Power | 48 V phantom from the existing OPA1612 preamp stage |
| Output into ADC | 0.8–2.1 Vrms at working level after preamp gain |
| Traceability | `UNKNOWN` unless certified. E1 makes no calibrated-pressure claim |
| Reuse | Existing design path reused if the chosen microphone is genuinely compatible |

### Stand, base, and reference structure

| Requirement | Value / criterion |
| --- | --- |
| Base | Mass independent of the specimen support; carries the shaker reaction |
| Positioning | Vertical adjustment at minimum; lateral if practical |
| Cable management | Strain relief so cable tension does not load the drive point |
| Reference structure | Inexpensive, stable, replaceable, mechanically representative enough to exercise E1, and **not scientifically precious** |

### Host and acquisition

| Requirement | Value / criterion |
| --- | --- |
| Host | Raspberry Pi 5 per existing design |
| ADC | HiFiBerry DAC+ ADC Pro per existing design — 2 channels, one clock |
| Simultaneous capture | **Required.** Sequential force/response acquisition is not acceptable |
| Output path | Existing DAC drives the shaker amplifier in place of the legacy speaker |

---

## Cost tiers

No E1 hardware budget is authorized in this repository or its decision chain, so
this framework does not optimize toward a number nobody set. Selection carries
three tiers, and **Preferred E1 drives the recommendation** unless a ceiling is
imposed later.

| Tier | What it buys | What it risks |
| --- | --- | --- |
| **Research minimum** | The cheapest chain that still measures force honestly and preserves synchronized two-channel acquisition | Higher noise floor, coarser sensitivity, more of the observed variation attributable to the instrument |
| **Preferred E1** | Sensor, conditioner, and shaker quality appropriate to an NSF characterization campaign | Cost; possibly lead time |
| **Reference-grade candidate** | Shows what additional metrology quality would buy — priced for comparison, not assumed affordable | Cost well beyond the campaign's need |

The tiers differ in *quality*, never in whether force is measured. A tier that
drops force measurement is not a cheaper tier; it is a different and
unacceptable experiment.

## Lead time is a first-class criterion

Procurement is now on the critical path — the software side has been waiting
since the DO-104 pre-execution slice merged. Candidate research must record lead
time and stock status beside price and specification, and a part that is
excellent but unobtainable this quarter is not the preferred choice.

## Alternate force-chain paths

Path A is the baseline. The others are recorded so that a cost or availability
wall produces a *considered* substitution rather than an improvised one, and they
are not investigated equally.

| Path | Chain | When it becomes relevant |
| --- | --- | --- |
| **A — baseline** | IEPE transducer → constant-current conditioner → ADC ch0 | Default |
| B | Piezoelectric sensor → charge amplifier → ADC ch0 | IEPE conditioning unobtainable or disproportionate |
| C | Strain / load cell → instrumentation amplifier → ADC ch0 | Cost wall; note the bandwidth cost of this path |
| D | Replacement multi-channel measurement interface | Only if no conditioning path can reach the existing ADC safely |

Path D means abandoning the existing ADC and its proven synchronized capture, so
it carries the largest architectural cost and is the last resort.

**DO-104S determination.** Path A resolves against the existing ADC with 2.6x
headroom at the selected exciter's full force, so **Path D is not required**
and the existing acquisition architecture is retained. Path C was carried as
the research-minimum force chain, where a bridge conditioner's selectable gain
and a load cell's routine calibration certificate are real advantages, against
the bandwidth and added-mass costs this table already names. Path B was not
needed. See the [interface matrix](TTP_E1_INTERFACE_MATRIX.md) for the gate
verdict.

## Requirements added or corrected by DO-104S

Three of these came out of reading the acquisition board's own datasheet at a
level of detail DO-104P did not reach. They are added because the complete-chain
evaluation showed them to be necessary — not because a product would look better
against them.

### Correction — how the input window is stated

DO-104P recorded the ADC input as "±3 V" with an "optimal region" of
0.8–2.1 Vrms. The manufacturer's datasheet states **2.1 Vrms as the maximum
input voltage** for the unbalanced input, not as the top of a comfortable band.
The two figures are the same number in different units — 2.1 Vrms is 2.97 V peak
— so nothing about the selection changes, but the wording did imply that
somewhere above 2.1 Vrms was merely sub-optimal rather than over the limit.

**The requirement is: the conditioned force signal must stay below 2.1 Vrms
unbalanced at the highest force the selected exciter can produce.** A balanced
input option exists at 4.2 Vrms and is available if a future pairing needs the
headroom.

### New requirement — aliasing must be handled deliberately

The selected acquisition board states that it carries **no anti-aliasing filter
in the input path**, offered as a recording-bandwidth feature. For a measurement
instrument that is a property to design around rather than a benefit: energy
above Nyquist folds back into the analysis band instead of being rejected, and
it arrives indistinguishable from real content.

| Requirement | Value / criterion |
| --- | --- |
| Excitation bandwidth | Band-limited by the signal generator, with the limit recorded per run |
| Residual aliasing | Characterized during E1 rather than assumed negligible |
| External filtering | Permitted as a designed-in element if E1 shows it is needed; it becomes a BOM row if added, never an undocumented insertion |

The transducer's own 36 kHz upper limit helps at 96 kHz sampling but does not
bound broadband contact noise, so it is not a substitute for handling this.

### New requirement — the commanded signal is not a phase reference

Manufacturer documentation establishes that the board's clocking is decoupled
from the host. It does **not** establish that the DAC and the ADC are
sample-locked to one another, and vendor support material states that a latency
always exists between playback and capture.

| Requirement | Value / criterion |
| --- | --- |
| Phase reference | The **measured force channel**, never the commanded DAC waveform |
| Force-to-response synchronization | Preserved structurally by using both channels of one converter |
| Any analysis using the commanded waveform for phase | Requires its own architectural ruling and its own evidence |

This is a constraint rather than a blocker: E1's transfer function is response
over measured force, and both are channels of the same converter.

### New requirement — contact mass is weighed, not derived

The selected transducer's datasheet gives a total mass but does not break out
the specimen-side end mass that actually loads the drive point. E1 already
records `combined_contact_mass_g` as a measured field, and this confirms why it
must stay measured: the number needed for mass cancellation is not on any
datasheet and cannot be derived from one.

---

## What this document does not establish

Manufacturer specifications are provenance for a *nominal* figure. They do not
establish installed-system behaviour: bandwidth, noise, contact stability, and
usable band are E1's job, and DO-104P closes before any of them is claimed.
