# TTP E0 — ADC Characterization Results

```text
STATUS: NOT EXECUTED

ADC-001 has not been characterized.
No E0 measurements are recorded.
No AFE-001 filter requirement has been derived.
B-014 remains open.
```

**Dev Order:** DO-106 (infrastructure only)
**Protocol:** [`TTP_E0_ADC_CHARACTERIZATION.md`](TTP_E0_ADC_CHARACTERIZATION.md)
**Contract:** `e0_adc_characterization_v1`
**Checker:** `python scripts/ttp_e0_adc_check.py <result.json>`

---

## Why this file is empty

`ADC-001` is `CONFIRMED_ABSENT` in
[the ownership census](TTP_E1_OWNERSHIP_CENSUS.md). The board has not been
purchased, so it cannot be mounted, so E0 cannot run.

**Nothing here is pre-populated with expected values.** No noise floor, no
coupling corner, no folding table, no full-scale figure. Those are the outputs
of a bench session that has not happened, and writing plausible numbers into
this file would produce exactly the artefact this whole document set exists to
prevent — a specification that reads as a measurement.

The contract enforces the same thing from the other side: a record marked
`PREPARED` that carries any observation is refused.

## What has to happen first

```text
ADC-001 acquired
        ↓
identity recorded in the register
        ↓
mounted on the owned Pi 5 (HOST-001, TTP-ASSET-001)
        ↓
T1–T7 executed
        ↓
e0_adc_characterization.json written
        ↓
checker green for truthfulness
        ↓
T3, T4 and T6 evidence reviewed by a human
        ↓
AFE-001 requirements derived
```

The gate is the first line. Nothing below it can start early, and no step in it
is a software task.

## The acquisition tooling does not exist yet

DO-106 deliberately shipped **no** `ttp_e0_adc.py`. The existing primitives cover
part of E0 — `tap_tone_pi.calibration.loopback` already does sweep generation,
latency measurement and frequency response, which reaches T3 and T7 — but T1's
noise grid, T2's gain and input-referred noise, T4's external-source injection,
T5's mixer inspection and T6's THD and clip detection have no canonical utility
behind them.

A command implementing three of seven tests would look operational and not be.
So the acquisition integration is recorded as the successor development order
rather than half-built here.

**When E0 runs, its captures will be taken by whatever the successor order
provides, or by hand.** Either way the result record is the contract above and
the checker is the gate.

## Where the result will live

`e0_adc_characterization.json` plus its WAVs are **standalone artifacts**. They
are not a Phase 2 session, they do not enter Phase 2 ingestion, and E0 will not
manufacture a session record to claim the repository's first `"synthetic": false`
capture — that milestone belongs to the first genuine acoustic acquisition, which
involves a plate and a microphone and is not this.

Captures are referenced from the result by SHA-256, and the checker verifies the
digest wherever the bytes are reachable.

## What an executed E0 will and will not settle

**Will settle:** the real noise floor against the 110 dB SNR typical figure;
whether the PGA is usable as an auto-ranging element; the AC-coupling corner and
its phase cost near 70 Hz; how far out-of-band energy actually folds; whether
the balanced input is per-channel or board-wide; whether 2.1 / 4.2 Vrms are real
on this board; and how stable the `playrec` offset is.

**Will not settle:**

- **B-014.** T4 produces the evidence a filter requirement is derived *from*.
  Deriving it is the next document, and it is a human's judgement, not an output
  of the checker. B-014 stays open until a front end exists and is measured.
- **B-015.** A board that characterizes badly is evidence for *reopening* the
  choice, not for closing the supersession question. T4 in particular could
  justify revisiting the successor.
- **Selection.** E0 is not a selection ruling on `ADC-001`. The human ruling
  remains `SELECTION_DEFERRED`.
- **Anything acoustic.** No plate, no microphone, no modal result.
