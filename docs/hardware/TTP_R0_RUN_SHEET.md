# TTP R0 — Bench Run Sheet

A **bench worksheet**, not a hardware specification and not evidence. It records
what is actually present at the bench at execution time.

> **Do not fill physical fields from design intent, memory, drawings, nominal
> values, or future plans. Record only the configuration actually present at the
> bench. Leave unavailable facts blank, or mark them unknown where the evidence
> contract requires a value. Do not write placeholder `0`, `N/A`, estimated
> numbers, or nominal dimensions.**

This sheet directs the operator to the existing procedure and tooling; it does
not duplicate or replace
[`TTP_PROTOTYPE_BENCH_PROTOCOL.md`](TTP_PROTOTYPE_BENCH_PROTOCOL.md) (R0 section).
Execution is gated on `TTP-AUTH-002` being granted (procurement) and measurement
being authorized — see Block 1.

---

## Block 1 — authorization check

```text
TTP-AUTH-002 status:
R0 procurement complete:
hardware received:
measurement execution authorized:
operator:
date/time:
```

**Stop** if measurement authorization has not actually been granted. A blank or
`PREPARED_NOT_AUTHORIZED` status here means R0 does not execute.

---

## Block 2 — input device identity

Populate **only** from the actually connected device. Do not pre-fill any value
(including sample rate) from a product page — record what the connected system
reports.

```text
manufacturer:
model:
serial number / physical identifier:
USB descriptor:
TTP device id/index:
input device name reported by OS:
sample rate:
channel count:
gain setting if exposed:
```

---

## Block 3 — physical specimen

Descriptive facts only, from the actual item on the bench.

```text
specimen_id:
description:
material/species if actually known:
physical condition:
```

Optional measured facts (leave blank unless actually measured):

```text
length:
width:
thickness:
mass:
```

These are not required. Do not populate them from drawings or nominal values.

---

## Block 4 — actual bench configuration

Describe what is physically set up. No placeholder values.

```text
support condition:
tap implement actually used:
tap location mark/description:
microphone placement description:
orientation description:
```

Optional measured positions (leave blank unless actually measured):

```text
microphone distance:
support spacing:
tap-point coordinates:
```

Blank is valid. Do not invent distances, spacings, or coordinates.

---

## Block 5 — TTP preflight

Use the already-established tool path (no new pass/fail thresholds).

```bash
ttp devices
ttp preflight
```

Record what is observed:

```text
selected device:
sample rate observed:
channel count observed:
quiet capture completed:
clipping observed:
hum/interference noted:
device reset/dropout:
operator notes:
```

---

## Block 6 — R0 capture sequence

Capture through the existing path:

```bash
ttp record --device <actual-device>
```

For each run, record:

```text
run_id:
timestamp:
raw audio path:
analysis path:
spectrum path:
quality-check path:
status:
halt reason, if any:
```

Expected artifacts from the existing path:

```text
audio.wav
analysis.json
spectrum.csv
quality_check.json
session provenance
```

The raw `audio.wav` is retained and linked to the run (Block 7). R0 evidence is
never analysis-only: an executed hardware run without a retained raw capture is
not R0 evidence.

---

## Block 7 — prototype evidence record

After capture, prepare a `ttp_prototype_run.json` and validate it read-only.
Reuse the existing contract and checker; do **not** create a new schema or a new
checker.

Required R0 semantic state (structural guidance only — do **not** fabricate
`run_id`, `specimen_id`, `input_device_id`, `sample_rate_hz`, timestamps,
artifact hashes, or `evidence_origin` before execution):

```json
{
  "stage": "R0",
  "status": "EXECUTED",
  "excitation": {
    "excitation_mode": "MANUAL",
    "excitation_method": "manual_tap"
  },
  "response": {
    "response_path": "MICROPHONE"
  },
  "force": {
    "measured_force_claimed": false
  }
}
```

R0 constraints the checker enforces:

- `stage: R0`, `excitation_mode: MANUAL`, `response_path: MICROPHONE`,
  `force.measured_force_claimed: false`.
- R0 may **not** carry commanded-excitation provenance, a commanded amplitude, or
  an output/amplifier/exciter chain.
- Only `HARDWARE`-origin evidence may be `witnessed`.

Validate:

```bash
python scripts/ttp_prototype_check.py <run.json>
```

### If a run is halted

A run stopped at a bench gate is **retained, not deleted**. Record it with:

```text
status: HALTED_AT_GATE   (or BLOCKED_BY_GATE)
halt_reason: <what actually happened>
```

Keep any raw capture already taken. The checker treats a well-formed halted run
with a `halt_reason` as internally consistent.

---

## Note on `ttp_prototype_run_v1` and premature records

`ttp_prototype_run_v1` requires identity fields (`run_id`, `generated_at`,
`stage`, `specimen_id`, `status`, `excitation`, `response`, `force`, `artifacts`,
`limitations`), and `response` requires `input_device_id` and `sample_rate_hz`.

Therefore **do not** create an executable `ttp_prototype_run_v1` fixture with
fabricated values (e.g. `SPECIMEN-TBD`, `USB-MIC-TBD`, an assumed `sample_rate_hz`,
or nominal dimensions) merely to have a "prepared R0 record." Until the real
specimen and device identities exist, this run sheet stays documentation only.
The schema is not loosened for this purpose.
