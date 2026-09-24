# TTP Prototype Bench Protocol (TTP-PROTOTYPE-001)

An operator procedure for the first closed measurement loop. Written for use at
the bench, not as architecture prose.

> **Authorization.** This protocol is prepared in advance. Executing it requires
> the separate physical authorization described in
> [TTP-PROTOTYPE-001](../dev_orders/TTP-PROTOTYPE-001_FIRST_CLOSED_MEASUREMENT_LOOP.md);
> the governing physical gate is DO-104O. Do not run these steps until that
> authorization exists.

Every run is recorded as a `ttp_prototype_run_v1` document and checked with:

```bash
python scripts/ttp_prototype_check.py <run.json>      # or a directory
```

The checker is read-only. It never repairs a record and never promotes
hardware. Record what happened; let the checker tell you whether the record is
internally truthful.

General rules, every stage:
- Record the actual device identities (input, output, microphone, amplifier,
  exciter, coupling) as you connect them — not from the datasheet, from the bench.
- Save the raw capture. A number with no retained bytes is not evidence.
- A commanded amplitude is an electrical setting, never a measured force.
- If anything on the **stop list** happens, stop that test and record why.

---

## R0 — Real-material acquisition (manual tap)

Manual tap on a real wood specimen; microphone response through the ADC.

1. **Enumerate the input device.** Confirm TTP sees the microphone/ADC, the
   sample rate, and the channel count. Record the actual input device id.
2. **Quiet capture.** Capture ambient/quiet input. Record RMS/noise floor,
   clipping state, obvious hum/interference, sample continuity. Invent no
   pass/fail threshold beyond what existing authority already defines.
3. **Manual tap.** Tap the marked location repeatedly with a consistent striker.
   For each tap: detect the transient, save the audio, compute the analysis,
   save provenance.
4. **Repeatability.** Several repeated taps at the same location. Compare the
   dominant peak, secondary peaks, gross variation, and quality state. Make no
   claim of calibrated force.

Record each run as `stage: R0`, `excitation_mode: MANUAL`. R0 must not carry a
commanded amplitude, emission provenance, or a controlled-excitation chain.

---

## R1 — Known added-mass challenge

Same specimen and fixed measurement geometry; a known mass deliberately added.

Sequence: baseline → mass m1 → mass m2 → mass m3 → optional unload/retest.

For each step record: specimen id, **measured** added mass (weigh it; do not use
the label alone), attachment position, microphone position, support condition,
peak frequency, quality result, and the raw capture.

Primary question: does the measured modal response shift consistently with
deliberate added mass beyond ordinary repeated-measurement variability?
Secondary question: can local effective modal-mass sensitivity begin to be
estimated from the measured slope? Do not force-fit the perturbation equation
outside its small-perturbation range.

Record each run as `stage: R1`, `excitation_mode: MANUAL`, with an `added_mass`
carrying the measured `added_mass_g` (`> 0`).

---

## R2 — Controlled excitation loop

TTP-commanded waveform through DAC → amplifier → exciter → specimen; microphone
response.

- **R2-01 DAC → amplifier electrical sanity.** Before touching a valuable plate:
  confirm the expected waveform is present, gain control works, there is no DC
  offset, and no uncontrolled startup transient. Use bench instrumentation if
  available.
- **R2-02 Amplifier → exciter bench test.** On a sacrificial mounting surface,
  starting at minimum output: confirm the exciter operates, does not overheat,
  no mechanical chatter, no amplifier fault, and amplitude responds monotonically
  to commanded level. Rated power is not required power.
- **R2-03 First plate excitation.** Couple the exciter with the provisional
  interface. Record attachment mass, attachment geometry, drive location,
  microphone location, commanded amplitude, and the frequency/sweep definition.
  Capture the response.
- **R2-04 Repeatability.** Repeat identical excitation without moving hardware.
  Ask only whether the same configuration and command produce a sufficiently
  similar observed response. Invent no tolerance.
- **R2-05 Detach/reattach.** Remove and reinstall the interface. Keep
  within-attachment and between-attachment variation separate.
- **R2-06 Roving microphone.** Keep excitation fixed; move the microphone across
  marked grid positions. No sensor mass changes; configuration id stays stable.
- **R2-07 Secondary drive location.** Only after fixed-driver mapping works, move
  the driver to identify modes suppressed by a nodal blind spot. Do not densely
  rove the exciter.

Record each run as `stage: R2`, `excitation_mode: COMMANDED`, with
`emission_provenance` (an `emitted_signal_id`) and the `output_device_id` the
signal was emitted through. Measured force is **not** claimed unless a force
chain is independently recorded.

### Amplifier/exciter characterization

Where equipment allows, record: supply voltage, idle current, drive current,
output voltage, gain setting, commanded amplitude, exciter impedance/rating,
temperature, clipping onset, fault behavior, and usable amplitude range. The
result is not "we need an N-watt amplifier"; it is "this specimen/exciter
combination required approximately X electrical drive to reach the usable
measurement range under these conditions" — the input to the custom-PCB
decision.

---

## Shutdown / emergency stop

- Command minimum output, then stop the emission.
- Power down the amplifier before disturbing the exciter or coupling.
- Let the exciter cool before handling if it ran warm.
- Leave the specimen and fixture undisturbed until the raw capture is saved.

### Stop list

Stop the affected test immediately if: the amplifier or exciter overheats; there
is audible mechanical damage; the adhesive/coupling begins to detach; the ADC
clips repeatedly; the output contains unexpected DC; the Pi or audio device
resets; signal routing is uncertain; specimen damage becomes plausible; a device
identity cannot be established; or results are being produced without saved raw
evidence.

**Do not work around a failed physical gate by weakening a software check.**

---

## What to record when something fails

A failed run is evidence, not an embarrassment to delete. Record it as a
`ttp_prototype_run_v1` document with `status: HALTED_AT_GATE` (or
`BLOCKED_BY_GATE`) and a `halt_reason` saying what happened. Keep any raw capture
that was taken. Then run the checker — a well-formed halted run is internally
consistent and is retained as part of the campaign's history.
