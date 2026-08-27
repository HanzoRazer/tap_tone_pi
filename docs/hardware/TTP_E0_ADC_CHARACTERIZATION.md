# TTP E0 — ADC Bench Characterization Protocol

**Purpose:** turn one $65 purchase into measured answers for four questions that
currently block the analog front-end design, and derive the `AFE-001` requirement
from evidence rather than assumption.

**Status:** `PREPARED` — **NOT EXECUTED.** No E0 measurement exists.
**Execution gate:** `ADC-001` physically received and identified in
[the identity register](TTP_E1_HARDWARE_IDENTITY_REGISTER.md). It is
`CONFIRMED_ABSENT` as of census pass 2, so this protocol cannot run.
**Output contract:** `e0_adc_characterization_v1` — see
`contracts/schemas/e0_adc_characterization.schema.json`.
**Checker:** `python scripts/ttp_e0_adc_check.py <result.json>`
**Dev Order:** DO-106 (integration). Acquisition tooling is **not** included; see
the successor order.

**Precondition:** `ADC-001` received and mounted on `HOST-001` (Pi 5 16 GB,
TTP-ASSET-001). Nothing else in the chain is required.

**Produces:** `e0_adc_characterization.json` plus captured WAVs, held as
**standalone external artifacts** identified from the result record by digest.

**Not a Phase 2 session.** An earlier draft called this the repository's first
session with `"synthetic": false` and `"device"` populated. That milestone belongs
to the first genuine *acquisition* using the Phase 2 session model — E0 involves
no plate, no microphone, and no acoustic measurement, and it must not manufacture
a Phase 2 session to claim it. Phase 2 ingestion is untouched by E0.

**Does not produce:** any acoustic measurement, any plate data, any component
selection.

---

## Equipment

| Item | Purpose | Owned? |
|---|---|---|
| Pi 5 + ADC-001 | device under test | Pi yes, ADC on purchase |
| 3.5 mm / RCA cable | DAC out → ADC in, loopback | trivial |
| Resistor pair, 1% | loopback attenuator, ~20:1 | trivial |
| Shorting plug, RCA | input-shorted noise floor | trivial |
| Second computer or phone | independent tone source for T4 | on hand |

No signal generator, no reference microphone, no preamp, no exciter. Everything
below is measured with the board driving itself or with a shorting plug.

---

## Tests

Each test states what it answers, the method, the recorded quantity, and the
document it unblocks.

### T1 · Input-shorted noise floor

**Answers:** the real noise floor, against the 110 dB SNR typical figure.
**Unblocks:** §3.3 gain architecture; every uncertainty claim downstream.

Short both inputs. Capture 60 s at each sample rate in {48, 96, 192} kHz and at
PGA settings {−12, 0, +16, +32} dB. Record RMS in dBFS, the spectrum, and any
discrete tones.

**Record:** noise floor per (fs, PGA) as a 3×4 table; identify and log the
frequency of every discrete spur. Spurs here are the board's own — anything found
later that is not in this table came from the front end.

**Pass condition:** none. This is characterization, not a gate.

### T2 · PGA gain accuracy and noise scaling

**Answers:** whether the PGA is usable as the auto-ranging element §3.3 proposes.
**Unblocks:** the fixed-analog-gain-plus-software-PGA architecture.

Loopback a −20 dBFS tone at 1 kHz through the attenuator. Step the PGA across its
full range. Record measured level change per step against nominal, and the noise
floor at each step.

**Record:** gain error vs setting; input-referred noise vs setting.

**Key question:** does input-referred noise stay flat as PGA rises? If it does,
the PGA is analog ahead of the modulator as assumed and software auto-ranging is
sound. If noise rises proportionally with gain, the PGA is partly digital and the
architecture in §3.3 needs revisiting.

### T3 · AC-coupling corner ★

**Answers:** §5.8, the unrecorded high-pass corner.
**Unblocks:** whether plate modes near 70 Hz carry usable phase.

Loopback a stepped sine sweep, 5 Hz to 500 Hz, logarithmic, at least 5 points per
octave below 100 Hz. Record amplitude and **phase** at each frequency.

**Record:** −3 dB corner; amplitude and phase error at 70, 80, 100, 200 Hz.

**Why phase matters more than amplitude.** A first-order high-pass at 20 Hz costs
only 0.3 dB at 70 Hz but contributes about 16° of phase lead. Amplitude error is
correctable; phase error corrupts modal identification and, in the E1 rig, appears
directly in H(f) unless both channels are matched — see §2.1.

**Note:** this test measures the DAC's coupling in series with the ADC's. If the
corner is high, repeat with an external source into the ADC alone to separate them.

### T4 · Out-of-band response and folding ★

**Answers:** the actual attenuation above Nyquist, which is what §2 must be
derived from.
**Unblocks:** `AFE-001` order, corner, and stopband — the whole filter design.

Drive the ADC from an **independent source** (the DAC cannot generate above its
own Nyquist). Inject single tones at frequencies above fs/2 and record where they
appear in the captured spectrum and at what amplitude relative to the input.

At fs = 48 kHz, test at minimum: 25, 30, 40, 48, 96, 150, 200 kHz — extended as
far as the available source reaches.

> **Execution prerequisite — source capability.** The equipment table lists a
> phone or second computer as the independent source. Consumer audio hardware does
> not reach 200 kHz, and this protocol does not name a signal generator.
>
> **Every requested frequency above the independently verified bandwidth of the
> available source is `BLOCKED_BY_SOURCE_CAPABILITY`.** That state is recorded in
> the result and enforced by the checker: a frequency the source cannot generate
> may not be recorded as measured, and its absence may not be silently dropped.
>
> The requested frequency set is **not** reduced to match available equipment, and
> no signal-generator model is invented here. A partial T4 is a partial T4, and
> B-014 stays open on the untested range.

**Record:** for each injected frequency, the apparent in-band frequency and the
attenuation in dB. This table *is* the B-014 evidence.

**How the result drives the design.** The required stopband attenuation of
`AFE-001` is set by the worst-case out-of-band energy expected at the input minus
the acceptable in-band contamination, evaluated at the frequencies this table
shows fold most strongly. Without T4, filter order is a guess.

### T5 · Balanced input granularity ★

**Answers:** §3.3, whether one channel can run balanced while the other runs
unbalanced.
**Unblocks:** the production preamp output topology, and 6 dB of microphone
headroom.

Inspect the ALSA mixer controls for input-mode selection. Determine whether the
control is per-channel or global. Then verify physically: drive the 6-pin balanced
connector on one channel and RCA on the other simultaneously, and confirm both
capture correctly.

**Record:** the control name and scope; measured full-scale input on each path.

**If per-board rather than per-channel:** the E1 rig cannot use the balanced mic
path, because ch0 needs unbalanced from the conditioner. The Analyzer, being
single-channel, still can. Record which instrument the answer applies to.

### T6 · Full-scale input verification

**Answers:** whether 2.1 Vrms unbalanced and 4.2 Vrms balanced are real on this
board.
**Unblocks:** the entire §3 level budget, which is currently arithmetic on a
vendor number.

Drive the input through the attenuator with increasing level until clipping is
detected in the capture. Record the input voltage at 0.1% THD and at hard clip,
on both unbalanced and balanced paths.

**Record:** measured maximum input, both paths, against the specified 2.1 / 4.2
Vrms.

### T7 · Loopback latency and stream offset

**Answers:** the magnitude and stability of the `sd.playrec()` offset.
**Unblocks:** whether Phase 1 can use a commanded reference at all; quantifies
what 2B avoids by measuring force.

Emit an impulse or chirp through the DAC, loop back to the ADC, and cross-correlate
commanded against captured. Repeat 50 times with stream restarts between runs.

**Record:** mean offset in samples; standard deviation across runs; whether the
offset is constant within a session.

**Interpretation.** If the offset is constant within a session and only varies
between sessions, a per-session loopback calibration recovers a usable phase
reference for Phase 1. If it varies run to run, it does not, and Rev 1.5's
statement stands unqualified.

★ = the four tests that produce the answers §6 of the BOM claims this purchase buys.

---

## Output record

```
e0_adc_characterization.json
  device            board identity, driver, kernel, overlay
  noise_floor       T1 table, dBFS by (fs, PGA)
  spurs             T1 discrete tones, Hz and dBFS
  pga               T2 gain error and input-referred noise by setting
  coupling          T3 corner, amplitude and phase at 70/80/100/200 Hz
  out_of_band       T4 injected vs apparent frequency, attenuation dB
  balanced_scope    T5 control name, per-channel or global, measured FS
  full_scale        T6 measured max input, both paths
  loopback          T7 mean offset, stddev, within-session stability
  provenance        date, operator, ambient T and RH, source equipment
```

Every field is `measured`. There are no `proposed` values in this file — that is
the point of the exercise.

---

## What this does not settle

- Nothing about microphones, preamps, exciters, or force transducers.
- Nothing about acoustic performance. No plate is involved.
- Not a selection ruling on ADC-001. A board that characterizes badly is evidence
  for reopening the choice, and T4 in particular could justify revisiting B-015
  against the successor.

## Stopping point

E0 is complete when the JSON above exists with every field measured. The next
document is the `AFE-001` design, and it should open by citing T3, T4, and T6
rather than by proposing a filter.
