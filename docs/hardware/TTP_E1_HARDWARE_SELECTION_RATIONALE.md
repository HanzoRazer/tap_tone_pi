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

## DO-104S market survey — sources, and what they establish

Everything from here down was gathered on **2026-08-25** against the United
States market in USD. It follows the source hierarchy the order sets: technical
claims trace to manufacturer documents, and only to manufacturer documents.
Distributor pages appear where they establish a *commercial* fact — current
price, stock, lead time — and nowhere else.

Eight manufacturer documents were retrieved as documents and are digested in
[the datasheet manifest](TTP_E1_DATASHEET_MANIFEST.json). The digest is over the
bytes actually served, not over a rendered or text-extracted version of them.
Sources that could not be retrieved that way are cited below as supporting
information and are deliberately absent from the manifest.

### The force-chain level budget

This is the calculation the whole order turns on, and it is computed from
retrieved datasheet figures rather than from catalogue impressions:

| Quantity | Value | Source |
| --- | --- | --- |
| 208C01 sensitivity | 500 mV/lb = **112.41 mV/N** | 208C01 spec sheet Rev K |
| 208C01 measurement range | ±10 lb = **±44.48 N** | 208C01 spec sheet Rev K |
| 208C01 output at its own full range | 44.48 N × 112.41 mV/N = **5.00 V pk** | derived |
| 4810 force rating | **10 N sine peak** | B&K BP 0232-16 |
| 208C01 output at the 4810 full force | 10 N × 112.41 mV/N = **1.124 V pk = 0.795 Vrms** | derived |
| HiFiBerry max input, unbalanced | **2.1 Vrms = 2.97 V pk** | HiFiBerry DAC+ ADC Pro datasheet |
| Headroom at the shaker maximum force | 2.97 / 1.124 = **2.6× (8.4 dB)** | derived |

**The shaker sets the ceiling, not the ADC.** The transducer would clip the ADC
at 26 N, and the exciter under consideration cannot produce more than 10 N. The
attenuator that DO-104P carried as `ATTEN-001` — reserved in case a conditioner
overran the input window — is not required by this pairing. It stays in the BOM
as a conditional line rather than being deleted, because a different exciter or
a higher-sensitivity transducer would bring it back.

The risk turns out to run the other way. At low drive the force signal is
*small*: 0.5 N of dynamic force is 56 mV peak, far below the input's useful
region. The HiFiBerry published **−12 dB to +32 dB input gain** covers that —
+32 dB lifts 40 mVrms to about 1.6 Vrms — which makes the programmable input
gain a load-bearing part of the force chain rather than a convenience.

### Where the noise actually comes from

| Contributor | Broadband noise | Referred to force |
| --- | --- | --- |
| 208C01 sensor, 1–10 kHz | 0.00045 N-rms stated directly | **450 µN** |
| 480C02 conditioner, 1–10 kHz, gain ×1 | 3.25 µV rms | 29 µN |
| HiFiBerry ADC (110 dB SNR typ. at 2.1 Vrms FS) | ≈6.6 µV rms | 59 µN |

The sensor own resolution is roughly an order of magnitude coarser than either
electronic contributor. **The acquisition path is not the limiting element in
the force chain** — which is the opposite of the concern DO-104P recorded, and
it is worth stating plainly because it removes the main reason to consider
replacing the ADC. These are datasheet figures combined arithmetically; the
installed noise floor is an E1 measurement and is not claimed here.

### Mechanical interface — an unusually clean match

The B&K 4810 fastening thread is **10-32 UNF**, and the PCB 208C01 is 10-32
female at both ends. The exciter, the transducer, and standard stinger stock
share one thread standard, so this pairing needs no adapter. That is recorded as
a finding rather than an assumption: an adapter that is genuinely unnecessary
must be shown to be unnecessary, not quietly omitted.

The 4810 electrical demand is modest — **3.5 Ω coil impedance at 500 Hz, 1.8 A
rms maximum input current**, so roughly 6.3 Vrms and about 11 W at full drive.
This matters for tiering: a 400 W laboratory shaker amplifier is very large
overkill for this exciter, and an amplifier decision can be made on coupling and
noise rather than on power.

### The synchronization question, answered narrowly

DO-104S was asked to verify rather than assume, and the verification changes the
claim that can be made.

**What the manufacturer documentation establishes.** The HiFiBerry datasheet
states a *"low-jitter dual-domain clock for optimised clock decoupling from the
Raspberry Pi."* Read carefully, "dual-domain" refers to the two oscillator
families that serve the 44.1 kHz and 48 kHz sample-rate groups, and the sentence
is about isolating the board clocking from the Pi. **It does not state that the
DAC and the ADC are sample-locked to each other**, and no retrieved manufacturer
document does.

**What E1 actually requires.** §4.12 requires synchronized *force and microphone*
acquisition. Force and microphone are ch0 and ch1 of a single two-channel ADC,
sampled by one converter into one I²S stream. Their mutual synchronization is a
property of the converter, not an integration risk — it is structural, and it is
the requirement that binds.

**What must not be claimed.** Drive-to-response synchronization is a *different*
claim, it is not established by any document retrieved here, and vendor support
material states that a latency always exists between playback and capture. The
consequence for TTP is a constraint rather than a blocker: **the commanded DAC
signal may not be used as a phase reference.** E1 transfer functions are
response-over-*measured-force*, both channels of the same ADC, so nothing in the
intended measurement depends on drive-to-response sample alignment. Any future
analysis that would use the commanded waveform as a phase reference needs its
own architectural ruling and its own evidence.

This distinction is recorded because collapsing it would be an easy and
attractive error: "same board, so it must be synchronous" is exactly the kind of
inference this repository exists to refuse.

### The microphone powering conflict

Reference-grade measurement microphones and studio measurement microphones are
powered differently, and the difference cuts straight across the existing
architecture:

- **GRAS 46AE** — ½″ CCP free-field standard set, requiring **4 mA at 24 V CCP**.
  CCP is the same powering scheme as IEPE and CCLD.
- **Earthworks M23** — **24–48 V phantom at 10 mA**.

The existing TTP response path is an OPA1612 preamp supplying 48 V phantom. The
M23 drops into it. **The 46AE does not** — it needs constant-current powering,
which is the same conditioning family the force sensor needs. So a reference-grade
response microphone does not simply cost more; it *changes which box conditions
it*, and a multi-channel ICP conditioner such as the 482C05 would then serve both
the force sensor and the microphone while the OPA1612 phantom path goes unused.

That is an architecture consequence, not a shopping preference, and it is why the
tiers are compared as chains rather than as parts.

### Rejected during this survey, with reasons

| Candidate | Role considered | Rejected because |
| --- | --- | --- |
| Dayton Audio DAEX32EP-4 surface exciter | low-cost drive source | Mounts to the specimen with VHB adhesive and reacts against it. The requirement is a **grounded** exciter whose body does not ride on the specimen. It fails the architecture requirement, not the budget test — which is why it is rejected rather than tiered as a cheap option |
| Commanded DAC voltage as the force channel | measured force | Not a force measurement. Explicitly refused by §4.10 and by the requirements document |
| Reusing the Phase 2A reference microphone on ch0 | measured force | A microphone measures pressure. Relabelling it cannot make it a force channel |
| PCB 480C02 as the sole conditioner where gain is needed | force conditioning | Unity gain only (1:1, ±2%). Retained as a candidate where the level budget does not need gain; where it does, a gain-selectable conditioner or the ADC own input gain must supply it |
| The Modal Shop 2100E21-400 (400 W) | amplifier for a 4810-class exciter | 400 W into an exciter that draws about 11 W. Not wrong, but the power is unusable and the cost is not justified by the pairing. Retained only in the reference-grade tier, where a larger exciter would use it |

### What is not yet established

No preferred configuration is nominated in this section. Pricing for the
laboratory-instrumentation candidates is **quotation-based** — PCB, The Modal
Shop, Brüel & Kjær and GRAS do not publish list prices — so a genuine unit cost
for the preferred and reference tiers cannot be stated from public sources and is
recorded as unknown rather than estimated. Every figure above is a datasheet
figure or arithmetic on datasheet figures. None of it is a measurement, and none
of it establishes that this chain works.

---

## What none of this establishes

Datasheet figures are provenance for a nominal value: bandwidth, rated force,
sensitivity, mass, pinout. They do not establish installed-system behaviour.
Whether this chain produces usable evidence over any defensible band is E1's
question, and DO-104P closes before any part of it is answered.
