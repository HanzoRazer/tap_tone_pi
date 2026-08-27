# TTP Analyzer — Unified Electrical Stack BOM

**Revision:** 0.2 — incorporates the DO-104S review response. Anti-alias
requirement restated as a derivable specification rather than a component choice;
inertial-correction terminology fixed; RESEARCH_MINIMUM dynamic validity demoted
from finding to gate; +52 dB demoted from recommendation to prototype hypothesis;
balanced microphone path promoted to prototype requirement; the two instruments
separated. Earlier (0.1): initial consolidation.

**Document status:** Consolidated working list. **Not authoritative.**
**Repository status:** imported under DO-106 as a subordinate working
architecture. Nothing here selects a component or authorizes a purchase.
**Authority:** `TTP_HARDWARE_STACK.md` Rev 1.5 for design; `TTP_E1_HARDWARE_BOM.md`
for component status. Where this document and either of those disagree, they are
right and this is stale.
**Purpose:** put every electrically-connected item in one table so the level
budget, the grounding topology, and the ADC channel allocation can be reasoned
about together.

**Nothing here authorizes procurement.** Every `procurement_action` remains
`HOLD`. Rows marked `PROPOSED_NEW` do not exist in the canonical BOM and are this
document's recommendations, not selections.

---

## 0 · Two instruments, not one

> **Provenance note (DO-106, 2026-08-27).** `TTP_TEST_RIG_BOM.md` **is not
> present in this repository.** It is referenced below and in §7 as the source of
> the Base / Extended / Research tiering language, but no such file exists here
> and nothing else references it. No placeholder was created and no supersession
> notice was written into a document that does not exist.
>
> **The correction it carried survives its absence.** Two propositions are
> superseded, and they are restated here so they remain durable rather than
> depending on a document nobody can open:
>
> 1. **Out-of-band control is an unresolved measurement front-end requirement,
>    not a solved one.** The acquisition board carries no analog anti-aliasing in
>    its input path. The required attenuation is derived from T4 evidence, not
>    assumed. Tracked as **B-014**, open.
> 2. **A commanded DAC waveform is not an established exact phase reference.** No
>    manufacturer document establishes DAC-to-ADC sample lock, and vendor support
>    material states a latency always exists between playback and capture. T7
>    measures whether a per-session loopback calibration recovers one.
>
> If the Test Rig BOM is recovered later, both propositions are already superseded
> by this document and by
> [`TTP_E0_ADC_CHARACTERIZATION.md`](TTP_E0_ADC_CHARACTERIZATION.md). Its
> mechanical fixture content is **not** implicated.

The tiering language in `TTP_TEST_RIG_BOM.md` (Base / Extended / Research) and the
Phase 2B language here describe **two different instruments**. Collapsing them is
the terminology error most likely to contaminate the Phase I claim, so they are
separated and neither is a tier of the other.

| | **Analyzer** (prototype → product) | **E1 research rig** (Phase 2B) |
|---|---|---|
| Excitation | controlled contact excitation, level commanded | measured force, ch0 |
| Response | microphone | microphone, ch1 |
| ADC channels used | 1 | 2 |
| Force transducer | **none** | required |
| Legitimate outputs | frequencies, mode identification, mode shapes (relative), damping, repeatability | force-normalized transfer function, Pa/N |
| Role | the thing that ships | the metrology authority that validates what the Analyzer may claim |

**The expensive force chain is not part of the amateur product.** Its purpose is
to establish, once, what the cheaper instrument can legitimately assert. The
Phase I experiment is the Analyzer reproducing the research rig's results within
stated uncertainty — which requires both to exist, but only one to be
manufacturable.

Every requirement below is tagged to one or both.

---

## 1 · Unified electrical role table

`ownership` and `status` carried from the canonical BOM. `PROPOSED_NEW` marks rows
this document adds.

### 1.1 · Acquisition chain

| local_id | class | role | ADC ch | Instrument | status | ownership |
|---|---|---|---|---|---|---|
| HOST-001 | host | Pi 5, carries the ADC, runs signal_gen + DSP | — | both | SELECTED | **CONFIRMED_PRESENT** (16 GB, TTP-ASSET-001) |
| ADC-001 | adc_interface | 2-ch converter; sets the binding electrical limit | both | both | SELECTED | CONFIRMED_ABSENT |
| MIC-001 | microphone | acoustic response | ch1 | both | TBD | CONFIRMED_ABSENT |
| PREAMP-001 | mic_preamp | mic gain, phantom, output topology per §3.3 | ch1 | both | SELECTED | CONFIRMED_ABSENT |
| FORCE-001 | force_transducer | drive-point force | ch0 | **E1 only** | TBD | CONFIRMED_ABSENT |
| PRECOND-001 | force_conditioner | sensor powering + conditioning | ch0 | **E1 only** | TBD | CONFIRMED_ABSENT |
| ATTEN-001 | attenuator | conditional — see §3.2 | ch0 | **E1 only** | TBD | CONFIRMED_ABSENT |

### 1.2 · Excitation chain (electrical portion)

| local_id | class | role | Instrument | status | ownership |
|---|---|---|---|---|---|
| AMP-001 | amplifier | drives the exciter from the Pi DAC output | both | TBD | CONFIRMED_ABSENT |
| SHAKER-001 | shaker | electrodynamic exciter | both | TBD | CONFIRMED_ABSENT |

### 1.3 · Power and interconnect

| local_id | class | role | status | ownership |
|---|---|---|---|---|
| PSU-HOST-001 | power | Pi 5 27 W USB-C | TBD | CONFIRMED_ABSENT |
| **PSU-PRE-001** | power | ±12 V bipolar rail for PREAMP-001 | `PROPOSED_NEW` | — |
| **PHANT-001** | power | 48 V phantom generation — topology **not selected**, see §5.3 | `PROPOSED_NEW` | — |
| CABLE-001 | cabling | sensor, RCA, XLR, drive | TBD | CONFIRMED_ABSENT |

### 1.4 · Proposed additions

| local_id | class | role | ADC ch | rationale |
|---|---|---|---|---|
| **AFE-001** | analog_front_end | **integrated design task**: out-of-band attenuation, power architecture, grounding, shielding — see §2 and §5.3 | both | closes B-014 |
| **ISO-001** | ground_isolation | RCA-level isolation, quantity per mains-referenced source | both | breaks the mains loop the topology creates |
| **REFMON-001** | drive_monitor | resistive divider, amp output → spare input | *Phase 1 only* | not applicable to 2A or 2B — no spare channel |

`LPF-001` / `LPF-002` from Rev 0.1 are **withdrawn as component rows** and absorbed
into `AFE-001`. Rev 0.1 named a solution before stating a requirement; §2 states
the requirement instead.

---

## 2 · Analog front-end requirement (replaces Rev 0.1's LPF rows)

> **The analog front end shall provide defined out-of-band attenuation ahead of
> the ADC sufficient to bound aliasing and RF/switching contamination over the
> declared measurement band. The filter response shall be characterized as part of
> the instrument transfer function.**

Order, corner frequency, stopband attenuation, in-band phase contribution, and
component tolerances are **derived from the declared analysis band**, not chosen in
advance. Rev 0.1's "multi-pole" was a conclusion stated without its premise.

Three distinct error mechanisms motivate this requirement and are **kept
separate**, because they have different magnitudes, different frequency
dependence, and different mitigations:

| Mechanism | What it does | Mitigation |
|---|---|---|
| **Aliasing of out-of-band analog content** | energy above the folding frequencies lands in-band and is unrecoverable | stopband attenuation |
| **RF susceptibility / nonlinear demodulation** | RF rectifies in the front end and appears as baseband offset or noise | shielding, cable discipline, input filtering |
| **Sampling aperture / clock jitter** | timing error becomes voltage error in proportion to dv/dt | bounded slew rate, which the filter provides as a *consequence* |

Rev 0.1 bundled these into one sentence and called the third "the one mechanism."
That was wrong: the third is real but subordinate, and with an adequate filter it
is not the binding term at audio frequencies.

### 2.1 · Inter-channel phase matching

For the E1 rig the measured quantity is a transfer function between ch0 and ch1.
**Filter phase common to both channels cancels; filter phase that differs between
them does not.** ch0 and ch1 must carry separately built filters — one follows a
conditioner, the other a preamp — so their phase mismatch appears directly in H(f)
as measurement error.

Two acceptable resolutions:

1. Phase-match the two paths by design and component tolerance, and state the
   residual mismatch as an uncertainty term.
2. Characterize the mismatch and correct it in analysis.

Either is acceptable. Neither happening by accident is not. This is a requirement
on `AFE-001` and does not apply to the single-channel Analyzer.

---

## 3 · Level budget

Computed from candidate specifications against the Rev 1.5 ADC limits. **These are
arithmetic, not measurements.**

### 3.1 · Force channel (ch0) — E1 rig only

ADC ceiling: 2.1 Vrms unbalanced = 2.97 V peak, at 0 dB PGA.

| Quantity | PREFERRED_E1 (PCB 208C01 + 480C02) |
|---|---|
| Sensitivity | 112.41 mV/N |
| Conditioner gain | unity |
| Force at ADC clip, 0 dB PGA | **26.4 N peak** |
| SHAKER-001 (B&K 4810) maximum | 10 N peak |
| Signal at shaker maximum | 1.124 V peak = 0.795 Vrms |
| **Headroom at shaker maximum** | **8.4 dB** |
| ~0.5 N peak plate drive | 39.7 mVrms → 1.58 Vrms at +32 dB PGA |
| ~0.05 N peak plate drive | 4.0 mVrms → 158 mVrms at +32 dB PGA |

**ATTEN-001 is not required at PREFERRED_E1.** The exciter cannot drive the force
channel into the ceiling — 10 N against a 26.4 N clip point. The row stays as a
conditional class; the preferred tier can be declared complete without it.

**The force channel's risk is low signal, not clipping.** This confirms Rev 1.5:
the −12 to +32 dB PGA is load-bearing, and at plate-scale drive the +32 dB setting
is the operating point rather than an option.

Noise: the 480C02's 3.25 µVrms refers to roughly **29 µN** at the transducer; the
ADC's floor at +32 dB PGA refers to roughly **1.5 µN**. Neither limits. The
limiting noise will be mechanical and acoustic, which is correct.

### 3.2 · Force channel, RESEARCH_MINIMUM

The FUTEK IAA100 outputs ±5 or ±10 VDC full-scale — **up to 7.07 Vrms, 3.4× the
ADC ceiling.** This chain *can* overrun the window, protected only by correct DIP
selection among 256 combinations. **ATTEN-001 is genuinely conditional here**, and
the DIP setting is a calibration-record item because it is not observable in
software.

### 3.3 · Microphone channel (ch1) — both instruments

The Rev 1.5 connector map specifies **RCA, unbalanced**, so the ADC's 4.2 Vrms
balanced ceiling is currently unavailable and 2.1 Vrms is the operative limit.

| Switch | Total gain | At 85 dB SPL | Margin to 2.1 Vrms |
|---|---|---|---|
| LOW | +39 dB | 320 mVrms | +16.3 dB |
| MID | +52 dB | 1.37 Vrms | **+3.7 dB** |
| HIGH | +61 dB | 4.0 Vrms | **−5.6 dB — clips** |

| Switch | Total gain | At 75 dB SPL | Margin to 2.1 Vrms |
|---|---|---|---|
| MID | +52 dB | 0.42 Vrms | +14.0 dB |
| HIGH | +61 dB | 1.22 Vrms | **+4.7 dB** |

**PROTOTYPE REQUIREMENT — balanced input granularity.** The ADC accepts balanced
input on its 6-pin connector. Balanced operation would raise MID/85 dB from 3.7 dB
of margin to 9.7 dB. Whether one channel can run balanced while the other carries
unbalanced RCA from the conditioner is **unknown and must be measured on the ADC
prototype.** Do not design the production preamp output topology until it is
answered.

**Gain architecture — prototype this, do not freeze it.** The switch spans 22 dB
across three positions; the PGA spans 44 dB under software control and is analog
ahead of the modulator, so it carries no noise penalty against the switch. LOW
never lands in either worked SPL case. The architecture to prototype is **fixed
analog gain plus software-controlled PGA with auto-ranging.**

**+52 dB is a prototype hypothesis, not a production constant.** Two SPL examples
do not establish the required instrument dynamic range. Before fixing analog gain,
characterize: quietest expected plate response; loudest expected sweep response;
microphone sensitivity tolerance; preamp output and noise; PGA noise and overload
behaviour; required overload margin.

---

## 4 · Channel allocation

| Configuration | ch0 | ch1 | Spare |
|---|---|---|---|
| Phase 1 — impulse tap | microphone | unused | ch1 |
| Phase 2A — speaker ODS | reference mic | roving mic | none |
| **Phase 2B — contact drive** | **conditioned force** | **microphone** | **none** |
| **Analyzer (product)** | **microphone** | unused | ch1 |

**Two channels is an architectural ceiling, not a BOM constraint.** Any third
electrical signal — drive monitor, second response point, temperature, drive-point
accelerometer — requires a different converter. §5.6 shows this ceiling has a
consequence nobody has costed.

---

## 5 · Project notes

Advisory. Nothing here is a selection and nothing here has been measured.

### 5.1 · Phase 2B already solves the sample-lock problem

Rev 1.5 is right that `sd.playrec()` gives no phase reference. In 2B it does not
matter: excitation is measured on ch0 and both quantities are channels of one
converter, so their relative timing is intrinsic to the capture. The architecture
contains the fix.

Phase 1 has a spare channel and could carry `REFMON-001`. Phase 2A cannot. Neither
can 2B. **`TTP_TEST_RIG_BOM.md` is stale on this point** — it claims the shared
codec makes DAC-to-ADC phase "exact." That sentence should be struck.

### 5.2 · B-014 will not be resolved by changing boards

The absence of an input anti-aliasing filter is stated by the vendor as a
recording-bandwidth feature, and the same line appears in the successor board's
documentation. Substituting the DAC2 ADC Pro does not close B-014.

Consequence specific to this instrument: the excitation is band-limited in
software, which protects ch0. **It does not protect ch1.** The microphone hears the
room, and room noise is not band-limited.

**`TTP_TEST_RIG_BOM.md` is stale here too** — it states that a sigma-delta
converter needs no external anti-alias filter and advises against adding one. That
is the opposite of §2 and of B-014, and it should be struck.

### 5.3 · Power architecture and front-end filtering are one task

Producing 48 V phantom from ±12 V requires a boost converter — a switching supply
inside the enclosure, adjacent to the lowest-noise stage, generating exactly the
out-of-band energy §2 exists to attenuate.

**Do not select the phantom topology in isolation.** Grounding, switching spectrum,
shielding, filter placement, and preamp noise are coupled, and choosing any one
first constrains the others silently. This is why the filter rows and the power
rows are folded into `AFE-001` as a single design task.

Candidate topologies, unranked pending that task: a separate linear 48 V rail; a
boost converter with a defined and recorded switching frequency, filtered and
shielded; an external commercial phantom supply.

A preamp with no power supply row is a hole in the chain, not an omission in a
document.

### 5.4 · The 480C02's battery is a grounding asset

Count the mains references in the 2B topology: shaker amplifier, conditioner (if
mains-powered), Pi supply, preamp supply, any bench instrument. They meet at
**unbalanced RCA inputs** — the topology most vulnerable to loop currents.

The PREFERRED_E1 conditioner (480C02) runs on an internal 9 V battery and is
galvanically isolated from mains. The REFERENCE_GRADE conditioner (482C05) is
mains-powered and four-channel. On grounding alone the preferred tier is quieter,
and the reference tier's traceability advantage carries a grounding cost that
belongs in the rationale rather than on the bench.

### 5.5 · RESEARCH_MINIMUM dynamic validity — GATE, not finding

> `RESEARCH_MINIMUM dynamic validity: UNVERIFIED — requires mounted transducer /
> stinger resonance and usable-band evidence before the tier is called complete.`

**Supported:** the FUTEK LSB200's suitability for dynamic modal force measurement
has not been established. The IAA100's 25 kHz figure is the amplifier's, not the
sensor's mounted mechanical bandwidth.

**Not supported:** that it fails the required bandwidth.

Evidence needed: mounted natural frequency, and mass relative to the 208C01's
22.7 g against a shaker with 18 g of moving mass. Note also that the AC-coupled ADC
discards the LSB200's DC capability, which is its main advantage over IEPE.

This is a falsifiable question, not a rejection of the inexpensive architecture.

### 5.6 · Force-at-sensor versus force-at-specimen correction

*(Rev 0.1 called this "mass cancellation." That term is borrowed from
impedance-head practice and is misleading here.)*

The transducer measures force at its **sensing plane**. Everything below that plane
— the lower half of the transducer, the stinger, the contact tip — must itself be
accelerated, so the sensed force is not the force delivered to the specimen. To
first order:

```
F_specimen ≈ F_sensor − m_downstream · a
```

subject to sign convention and to the assumption that the downstream assembly
behaves as a rigid lumped mass in the applicable band. **Above that band the
stinger/tip/transducer assembly is itself a dynamic system and simple mass
subtraction is inadequate** — a dynamic calibration or transfer correction is then
required. The frequency at which the lumped approximation fails is an E1
deliverable, not an assumption.

The canonical BOM's instinct to record stinger and tip mass as *measured, not
assumed* is right. The missing piece is that those masses are an **input to a
correction**, not merely a record.

**Unlisted consequence.** Applying the correction requires `a` — acceleration at
the drive point. In Phase 2B there is no accelerometer: ch0 is force, ch1 is the
microphone, and §4 shows there is no third channel. So the correction **cannot be
applied with the current channel allocation.** Three options, none free:

1. Keep m_downstream small enough that the uncorrected error stays below the
   uncertainty claim, and prove that bound.
2. Bound the error analytically from measured masses and an estimated response, and
   carry it as an uncertainty term rather than a correction.
3. Add a channel — a converter change, not a BOM addition.

This is the clearest example of the §4 ceiling having a cost that has not been
priced. It also gives the E5 mass-loading work a defined scientific role.

### 5.7 · B-015 is partly closable from a primary source

The successor board's converters are identified by distributors as a PCM5122 DAC
and PCM1863 ADC. If confirmed, the input electrical characteristics live in TI's
PCM1863 datasheet rather than HiFiBerry's product page, and the architecture gate
can be re-run against a manufacturer document. The successor retains balanced
XLR/TRS input, so §3.3's opportunity survives substitution.

**Distributor-sourced. Does not meet the datasheet-manifest standard.** A lead for
closing B-015, not evidence.

### 5.8 · Verification items with no cost

- **AC-coupling corner.** Not recorded anywhere. Plate modes run to roughly 70 Hz;
  a corner above 20 Hz produces measurable phase error at the lowest and most
  diagnostically useful modes.
- **Balanced input granularity.** Per-channel or per-board (§3.3).

Both are answerable on the ADC prototype in an afternoon and unknowable until the
board exists.

---

## 6 · Build order

The Pi is the only owned item and it is the *last* stage in the chain. Working
backward:

```
Pi 5 (owned)
  → ADC-001 prototype
    → characterize ADC (E0)
      → design AFE-001 (filtering + power + grounding, one task)
        → build Analyzer (single channel, no force)
          → build displacement / reference jig
            → only then authorize the E1 force rig
```

**ADC-001 is the first rational purchase.** One item, roughly $65, and it converts
the AC-coupling corner, the balanced-input question, the real noise floor, and the
B-014 filter requirements from unknowable to measured.

**The prototype evaluation must include B-014 characterization.** It is not enough
to prove that audio goes in. The bench must characterize the board well enough to
*derive* the `AFE-001` requirement in §2 — otherwise filter design begins from
assumption again. Protocol in `TTP_E0_ADC_CHARACTERIZATION.md`.

Everything expensive sits behind that one purchase, and this sequence is
considerably simpler than the governance language accumulated around it while
preserving the discipline that language exists to enforce.

---

## 7 · Change log

| Rev | Date | Change |
|---|---|---|
| 0.1 | 2026-08-27 | Initial consolidation from Rev 1.5 and the DO-104R census. Level-budget arithmetic, four proposed electrical rows, project notes |
| 0.2 | 2026-08-27 | DO-104S review response incorporated. §0 separates Analyzer from E1 rig. §2 replaces the LPF component rows with a derivable requirement and separates three error mechanisms Rev 0.1 conflated; §2.1 adds inter-channel phase matching. §3.3 promotes the balanced path to a prototype requirement and demotes +52 dB to a hypothesis. §5.3 folds power and filtering into one `AFE-001` task. §5.5 demoted to a gate. §5.6 renamed and extended with the drive-point acceleration consequence. §6 adds B-014 characterization to the prototype stub. Records `TTP_TEST_RIG_BOM.md` as stale in two areas |
