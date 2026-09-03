# TTP Excitation Amplifier — Requirements

**Status:** requirements only. No amplifier is selected, and the required output
is unmeasured.
**Dev Order:** DO-108P
**Reference implementation family:** TPA3116D2 / TPA3118D2
**Selection status:** `CANDIDATE`
**Authority:** the [E1 BOM](TTP_E1_HARDWARE_BOM.md) owns the candidate row
(`AMP-CP-001`). This document states what that role must satisfy.

---

## How to read the values in this document

Three kinds of statement appear below, and they are not interchangeable:

| Marker | Means |
| --- | --- |
| *manufacturer* | Printed in a document in the [datasheet manifest](TTP_E1_DATASHEET_MANIFEST.json), traceable by digest |
| `TBD_MEASURE` | A number that must come from the bench, and has not been measured |
| *requirement* | A property this role must have, stated without a number where the number is unmeasured |

**No value here was inferred from a component rating.** The rule that governs
this whole document:

> The exciter's rated power is not the amplifier's required output power.

A 10 W or 24 W rating states what the exciter tolerates before damage. What the
amplifier must deliver is whatever produces usable modal SNR on a plate, and that
is a measurement. Sizing the output stage from the exciter's rating would
overbuild the board by an unknown factor and put the number in the schematic
before anyone had observed it.

## Electrical input

| Property | Value | Basis |
| --- | --- | --- |
| Channels | **1** excitation channel | requirement — the commercial chain drives one exciter |
| Source | TTP DAC / analog output | requirement |
| Maximum source level | 2.1 Vrms | *manufacturer* — HiFiBerry DAC+ ADC Pro datasheet, `sha256:4d3759da…` |
| Source output impedance | not stated by the manufacturer | *manufacturer* — the document is silent, and no value is assumed |
| Input topology | differential preferred, single-ended acceptable | requirement |
| Input coupling | AC-coupled | requirement — no DC offset may reach the voice coil |

The reference family accepts *differential and single-ended inputs*
(*manufacturer*, SLOS708G), so this requirement does not narrow the candidate
field.

One channel is the requirement, and it is worth being explicit that this is a
mono excitation path: the reference family is a stereo part, and using a stereo
device does not make the architecture two-channel.

## Load compatibility

| Property | Value | Basis |
| --- | --- | --- |
| Nominal load | **4 Ω and 8 Ω both required** | requirement |
| Minimum load | 4 Ω | requirement — set by the Dayton candidates |

The registered candidates are genuinely split: `DAEX25CT-4` and `DAEX25FHE-4` are
4 Ω nominal, `EX 30 S` is 8 Ω nominal (all *manufacturer*). The requirement
covers both rather than restating the odd one out to match. An amplifier that
only tolerated 4 Ω would silently eliminate a candidate before the bench had
compared them, which is a selection made by a specification instead of by
evidence.

The reference family supports 4 Ω BTL loads (*manufacturer*).

## Output range

| Property | Value |
| --- | --- |
| Minimum useful output voltage | `TBD_MEASURE` |
| Minimum useful output current | `TBD_MEASURE` |
| Required continuous output power | `TBD_MEASURE` |
| Required short-duration output power | `TBD_MEASURE` |
| Maximum intended drive | `TBD_MEASURE` |

Every row is a bench result, produced by
[the characterization protocol](TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md).
Until it runs, the required output envelope is unknown — not "small", not
"probably a few watts".

What can be said now without measuring anything is arithmetic, and it is only
arithmetic: at a given output voltage into a given load, the current and
electrical power follow from Ohm's law, and
[`scripts/exciter_drive_budget.py`](../../scripts/exciter_drive_budget.py)
computes them. That utility is a calculator, not evidence. It does not know what
voltage a plate measurement needs, and it says so.

## Gain

| Property | Value | Basis |
| --- | --- | --- |
| Gain | fixed or digitally configurable, deterministic | requirement |
| Analog volume potentiometer | **not required, and not wanted** | requirement |
| Gain recorded per run | required | requirement |

A knob on the drive path makes the excitation level an unrecorded operator
variable, which destroys run-to-run comparability for exactly the reason the
controlled-excitation work exists: to reduce process variance, not to add a new
source of it. Whatever gain the board has must be knowable by the Analyzer and
recordable in the run's provenance.

The reference family offers *selectable 20, 26, 32 or 36 dB gain, latched at
power-up* (*manufacturer*). Which value TTP needs depends on the measured drive
requirement and the 2.1 Vrms maximum source level, and is therefore
`TBD_MEASURE`.

## Power limit

| Property | Value |
| --- | --- |
| Hardware output ceiling | **required** |
| Ceiling value | `TBD_MEASURE` |

A hardware ceiling is required rather than preferred. The exciters under
consideration are small, and a software fault that commanded full scale into one
would damage it before an operator could react. The limit belongs in the analog
domain where a software failure cannot lift it.

The reference family provides a *programmable power limit* on the `PLIMIT` pin
(*manufacturer*), which is the mechanism this requirement asks for. Setting it
requires the measured maximum intended drive.

## Mute and shutdown

| Property | Value |
| --- | --- |
| Mute under Analyzer control | required |
| Shutdown under Analyzer control | required |
| State at power-up | muted | 

Muting at power-up is a requirement rather than a nicety: the drive path is
mechanically coupled to the specimen, and a transient at power-up is a physical
event on the plate, not a noise in a speaker.

The reference family carries `MUTE` and `SDZ` pins (*manufacturer*). Whether they
reach the Pi as GPIO, and on which pins, is a board-level decision that belongs
to the layout order and is unresolved here.

## Fault indication

| Property | Value |
| --- | --- |
| Fault state readable by the Analyzer | required |
| Fault state recorded in run provenance | required |

A fault that occurred during a capture changes what that capture means. If the
output stage entered protection partway through a sweep, the run's excitation was
not what the contract says was commanded, and the record must be able to say so.

The reference family exposes `FAULTZ`, *high in normal operation and low in a
fault condition*, and integrates over-voltage, under-voltage, over-temperature,
DC-detect and short-circuit protection with error reporting (*manufacturer*).

## Supply

| Property | Value |
| --- | --- |
| Supply voltage | `TBD_MEASURE` — bounded below by the required output, above by the enclosure's available rails |
| Available rails in the TTP enclosure | `UNRESOLVED` — see [PCB envelope](TTP_EXCITATION_PCB_ENVELOPE.md) |
| Supply topology | single supply preferred | 

The reference family operates from a *single 4.5 V to 26 V supply*
(*manufacturer*), so this requirement is satisfiable across a wide range. Which
point in that range TTP uses cannot be chosen before both the enclosure survey
and the drive measurement exist: one bounds what is available, the other bounds
what is needed.

## Thermal

| Property | Value |
| --- | --- |
| Continuous dissipation | `TBD_MEASURE` |
| Heatsinking | `UNRESOLVED` — depends on dissipation and enclosure ventilation |
| Ambient range | commercial indoor laboratory use | 

Thermal drift is not only a component-survival question here. The protocol asks
whether exciter heating changes the measured result, and if it does, the thermal
design of the drive stage becomes a measurement requirement rather than a
reliability one.

## EMI

| Property | Value |
| --- | --- |
| Coexistence with the ADC and microphone front end in one enclosure | **required** |
| Output filtering | full LC output filter expected; final topology `UNRESOLVED` |
| Demonstrated non-contamination | `TBD_MEASURE` |

This is the requirement most likely to be underestimated. A Class-D stage
switching at hundreds of kilohertz shares an enclosure with a microphone preamp
and a 24-bit ADC that has *no anti-aliasing filter in its input path* — a
property already established for `ADC-001` and recorded against open blocker
B-014. Switching residue above the audio band is exactly the kind of energy an
unfiltered converter can fold back down.

"Filter-free" in the reference family's own title refers to speaker-drive
applications and is not a claim that this system needs no filter. Whether the
stage contaminates the acquisition path is a measurement, and the protocol makes
it a numbered step rather than an assumption.

## Measurement compatibility

| Property | Value |
| --- | --- |
| Excitation identity recorded per run | required |
| Commanded level recorded per run | required — already implemented |
| Amplifier gain recorded per run | required |
| Measured output Vrms recorded where available | required |
| Input force recorded | **prohibited — no force channel exists** |

The last row is a requirement in the negative, and it is the one that must
survive every later revision of this document. No run on the commercial chain may
record, derive, or present an input force. See
[the commercial excitation architecture](TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md)
§10.

## PCB envelope

| Property | Value |
| --- | --- |
| Board outline | `UNRESOLVED` |
| Maximum component height | `UNRESOLVED` |
| Mounting | `UNRESOLVED` |
| Separation from the analog acquisition section | required; distance `UNRESOLVED` |

All of it waits on the [enclosure survey](TTP_EXCITATION_PCB_ENVELOPE.md). For
scale only, and explicitly not as a layout input: the reference family's package
body is *11.00 mm × 6.20 mm* (*manufacturer*, 32-pin HTSSOP). The IC is not the
constraint; the supply, filtering, connectors and thermal path are, and none of
them has been sized.

## Unresolved requirements

Everything below is open, and DO-108P closes none of it:

```text
required output voltage, current and power        TBD_MEASURE
maximum intended drive and the hardware ceiling   TBD_MEASURE
gain setting                                      TBD_MEASURE
supply voltage                                    TBD_MEASURE
thermal dissipation and heatsinking               TBD_MEASURE / UNRESOLVED
output filter topology                            UNRESOLVED
EMI coexistence with the ADC and microphone AFE   TBD_MEASURE
DAC source output impedance                       not published by the manufacturer
enclosure envelope, rails, mounting, keep-outs    UNRESOLVED
amplifier selection                               CANDIDATE - no ruling
exciter selection                                 SELECTION_DEFERRED - unchanged
```

**The reference family is a candidate, not a selection.** TPA3116D2 / TPA3118D2
is credible and its published control surface matches these requirements
closely. That is a reason to keep it in front of the bench, not a reason to write
it into a schematic. Selection happens after the measurements above exist.
