# TTP Commercial Excitation Architecture

**Status:** architecture definition. No excitation hardware exists.
**Dev Order:** DO-108P
**Authority:** supporting document. The
[E1 hardware BOM](TTP_E1_HARDWARE_BOM.md) and
[identity register](TTP_E1_HARDWARE_IDENTITY_REGISTER.md) remain the authority on
component identity, candidates and possession. This file explains the commercial
architecture those records now carry a tier for; it does not enumerate hardware
of its own.

---

## 1. Purpose

The TTP Analyzer can command a waveform. It cannot, today, put that waveform into
a plate: nothing in the repository converts a DAC output into mechanical
excitation, and no such component is possessed. This document freezes the
physical chain a commercial TTP would use to close that gap, so that a future
custom board is designed around the TTP enclosure and the measured requirement of
a specific exciter rather than around a generic audio amplifier.

It defines an architecture. It measures nothing, selects nothing, and authorizes
no purchase.

## 2. Governing signal chain

```text
TTP ANALYZER
     │  commanded waveform
     ▼
DAC / ANALOG OUTPUT
     ▼
INTERNAL POWER AMPLIFIER
     ▼
ELECTRODYNAMIC EXCITER
     ▼
LIGHT STINGER / CONTACT TIP
     ▼
GUITAR PLATE
     ▼
MICROPHONE / RESPONSE SENSOR
     ▼
ADC
     ▼
TTP ANALYZER
```

The amplifier sits **inside** the commercial stack, between the DAC and the
exciter. A commercial TTP does not presume a standalone external amplifier on the
operator's bench.

Every stage above is either software that exists or hardware that does not. The
boundary between those two facts is the subject of §4 and §5.

## 3. Commercial versus reference architecture

The repository already describes a contact-excitation chain, and it is not this
one. Phase 2B in the
[stack specification](TTP_HARDWARE_STACK.md) and the E1 campaign target a
grounded mini-shaker driving a force transducer, so that input force is
*measured* rather than assumed. That is the research and reference configuration,
and it stays.

| | Reference / research (E1) | Commercial (this document) |
| --- | --- | --- |
| Exciter | Grounded mini-shaker, instrument grade | Inexpensive electrodynamic exciter |
| Amplifier | External laboratory power amplifier | Internal TTP stage, ultimately on a TTP board |
| Input force | Measured by a force transducer in the drive path | **Not measured. Not inferred.** |
| Response sensor | Microphone | Microphone |
| Purpose | Characterize the instrument chain itself | Deliver repeatable excitation in a product |

The two are not competing selections of the same thing, and the commercial tier
must never be read as a cheaper version of the reference chain. It is a
*different chain that answers a different question*, and the difference is
exactly one channel: the reference chain measures the force it applies, and the
commercial chain does not.

This is why the commercial candidates live in the E1 BOM under their own tier
rather than in a separate document. One authority enumerates components; the tier
carries the distinction.

## 4. Existing TTP software capability

Waveform emission is implemented and needs nothing from this order:

| Capability | Where | State |
| --- | --- | --- |
| Waveform synthesis — sine, sweep, chirp, noise, impulse, multitone, comb | [`tap_tone_pi/signal_gen/generators.py`](../../tap_tone_pi/signal_gen/generators.py) | implemented |
| Declarative excitation contract, stepped and swept emission | [`tap_tone_pi/excitation/`](../../tap_tone_pi/excitation/) | implemented |
| Output-side source characterization record | `SourceCharacterizationRecordV1` | implemented |
| Amplitude guardrails on the commanded level | `tap_tone_pi.excitation.amplitude` | implemented |
| Excitation → measurement linkage and response pairing | `ExcitationMeasurementLinkV1`, `ExcitationResponsePairV1` | implemented |

### Capability dependency, recorded here rather than asserted elsewhere

Three capability states matter to this architecture:

```text
controlled waveform emission     = implemented
controlled physical excitation   = external physical transducer required
measured dynamic input force     = absent from the commercial path
```

These are recorded in this document deliberately. A repository-wide analyzer
capability matrix is being written under separate, unmerged work; when it lands,
these three lines are what it must reconcile with. Importing a fragment of that
document here to hold three rows would fork an authority that does not exist yet
on this branch.

## 5. The missing physical subsystem

Everything between the DAC connector and the plate is absent. The
[ownership census](TTP_E1_OWNERSHIP_CENSUS.md) established that directly: one
component is possessed in this whole campaign, a Raspberry Pi 5, and it is the
host. `AMP-001` and `SHAKER-001` are both `CONFIRMED_ABSENT`.

So the commercial excitation path is, at the time of writing, **software that can
emit into nothing**. That is not a defect in the software. It is the reason
DO-108P exists.

## 6. Amplifier role

The amplifier converts a line-level commanded waveform into the voltage and
current an electrodynamic exciter needs. Its requirements are stated in
[TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md](TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md).

Two rules govern it, and both are about not inventing numbers:

**The exciter's rated power is not the amplifier's requirement.** A 24 W exciter
rating states what the device tolerates, not what a plate measurement needs. The
required output is a bench result, obtained by
[the characterization protocol](TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md),
and it stays `TBD_MEASURE` until that experiment runs.

**Off-the-shelf amplifier boards are bench surrogates.** They are legitimate for
obtaining the measurement; they are not the production architecture, and using
one does not select it.

## 7. Exciter role

An inexpensive electrodynamic exciter is bonded or clamped to the drive point and
converts amplifier current into a reciprocating motor force. Three candidates are
registered in the BOM under the `COMMERCIAL_PROTOTYPE` tier. None is selected.

The important epistemic point about these devices: their published frequency
responses are **panel responses, not device responses**. Both Dayton sheets state
that the response shown was measured with the exciter adhered off-centre to a
12 × 12 × ½ inch foam-core board, and that the actual response depends on the
driven surface. A guitar plate is not that board. Those curves therefore
establish comparability between the candidates and nothing about behaviour on a
soundboard.

`BL × I` is a **motor-force scale**, not force delivered to the specimen. The
mechanical path — bond, stinger, tip, preload, and the plate's own impedance —
sits between the motor and the plate, and none of it is characterized.
[`scripts/exciter_drive_budget.py`](../../scripts/exciter_drive_budget.py)
computes that scale and says so on every invocation.

## 8. Stinger and contact-tip role

Preferably the exciter body is fixture-supported and only the stinger, tip, or
bonded interface touches the plate. The purpose is the same as in the reference
chain: keep the exciter's mass and reaction off the specimen, so that the
structure being measured is the plate rather than the plate plus an exciter.

Stinger and tip are fabricated parts. They carry asset labels, documented
geometry, and measured mass — measured, because a target mass is a design
intention and the modal result depends on the real one.

Whether merely touching the stinger to the plate shifts the modes is an open
empirical question, and the protocol asks it directly.

## 9. Response sensor role

The microphone remains the baseline response sensor, for one reason: it adds no
attached mass. An accelerometer on a light plate loads the structure it is
measuring, and the commercial architecture does not accept that trade by default.

The response side of the commercial chain is otherwise identical to the existing
Phase 1 and Phase 2 acquisition path and is unchanged by this order.

## 10. Evidence boundaries

The governing distinction:

> **Commanded waveform is known; electrical output can be characterized;
> mechanical force at the plate is not presumed known.**

Which yields three claim classes, and they may not be traded for one another:

| Claim | Status in the commercial path |
| --- | --- |
| "The analyzer commanded this waveform" | Known — it is what the software emitted |
| "The amplifier produced this Vrms into this load" | Characterizable — by measuring the output |
| "This much force entered the plate" | **Unsupported.** No force channel exists |

A commercial TTP measurement may therefore record its drive as commanded level
and, once measured, as electrical output. It may not record an input force, and
no transfer function computed on this chain may be presented as force-normalized.

## 11. Open hardware gates

| Gate | State | Closed by |
| --- | --- | --- |
| Enclosure envelope known | `UNRESOLVED` | physical measurement — [PCB envelope](TTP_EXCITATION_PCB_ENVELOPE.md) |
| Available power rails confirmed | `UNRESOLVED` | enclosure survey |
| DAC output characteristics confirmed | manufacturer maximum only | E0 / bench measurement |
| Required exciter drive measured or bounded | `UNRESOLVED` | [characterization protocol](TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md) |
| Amplifier family selected | `CANDIDATE` | a later selection ruling |
| Exciter selected | `SELECTION_DEFERRED` | the human selection gate, unchanged by this order |
| PCB schematic and layout | **`BLOCKED`** | [ADR-0014](../ADR-0014-excitation-pcb-gate.md) |

No gate above is closed by this document, and DO-108P does not attempt to close
any of them.
