# NSF TTP Hardware Characterization Campaign — Operator Protocol

**Status: not executed.** No rig exists yet. This document is the procedure the
campaign will be run by, written and frozen before any instrument data is
collected so that the campaign is not analyzed by software shaped to fit its
own results (DO-103 §13).

Dev Order: `docs/dev_orders/DO-103_HARDWARE_MEASUREMENT_ARCHITECTURE.md`
Results: `docs/NSF_TTP_HARDWARE_CAMPAIGN_RESULTS.md`

---

## What this campaign is for

To find out whether a grounded contact-drive architecture — shaker, stinger,
measured force in, microphone response out — can produce stable, repeatable,
configuration-aware measurements **without silently perturbing the thing being
measured**.

It is not a calibration, not a comparison against a reference method, and not a
judgement about any instrument. Every number it produces describes this
instrument's agreement with itself under recorded conditions.

## What it may never claim

- That any measurement is accurate, calibrated, or laboratory-equivalent.
- That the measured quantity is mobility, accelerance, or receptance. It is
  acoustic pressure per unit measured force, `Pa/N`. The response sensor is a
  microphone, and a mechanical frequency-response function requires the response
  to be a mechanical motion of the structure.
- That a peak is an identified structural mode.
- That force is traceable. Force here is **measured**, which makes the
  excitation observable. Traceability is a separate chain that this campaign
  does not establish.

## The no-threshold rule

**No experiment in this campaign has a pass mark.**

There is no reciprocity tolerance and no minimum detectable mass. The campaign
exists to produce the evidence a future limit would have to be derived from, so
inventing the limit first would decide the question the experiment was built to
ask.

The practical consequence is a discipline: **do not adjust the rig until a
result looks better.** If a configuration produces a poor result, record it,
then change the configuration deliberately and record the change as a new
configuration with its own identity. The first result stays in the evidence.

---

## Before the first capture

### 1. Assemble and ground the rig

The shaker body is mechanically grounded to a mass independent of the specimen
support. The stinger connects the driver to the drive point through the force
transducer, so that the force reaching the specimen is the force being measured
and not the force leaving the driver.

Nothing in this step produces a measurement claim. Record what was built.

### 2. Record every identity

The rig is part of the measurement instrument. Swapping any part below changes
the mechanical path and is a **configuration change, not a repeat** — it needs a
new `rig_configuration_id`.

| Field | What it names |
| --- | --- |
| `rig_configuration_id` | The assembled combination as a whole |
| `excitation_device_id` | The shaker |
| `stinger_id` | The stinger, by length, material, and diameter |
| `contact_tip_id` | The tip in contact with the specimen |
| `fixture_id` | The mount holding the driver |
| `support_condition` | How the specimen is supported |
| `excitation_point` | Where the rig drives |

Anything not known is left unrecorded. It is never filled in with a plausible
value: the reports distinguish *unknown* from *observed*, and an invented value
destroys that distinction permanently.

### 3. Record the channels

Two channels, one of each role. The transfer quantity's unit is **derived** from
this pair rather than assumed, so getting it right is what makes `Pa/N` mean
anything.

| Field | Excitation channel | Response channel |
| --- | --- | --- |
| `quantity` | `force` | `acoustic_pressure` |
| `unit` | the unit the channel is scaled to | the unit the channel is scaled to |
| `sensor_id` | the force transducer | the microphone |
| `sensitivity_value` / `sensitivity_unit` | **as the chosen device states it** | as the chosen device states it |
| `calibration_traceability` | `TRACEABLE`, `NOMINAL`, or `UNKNOWN` | same |
| `calibration_reference` | required if `TRACEABLE` | required if `TRACEABLE` |

No sensitivity or unit is fixed in advance of choosing a transducer. When the
force transducer is selected, record its stated sensitivity **in the unit the
manufacturer states it in** — do not convert it into a unit this repository
picked first, and do not assume mV/N.

`NOMINAL` means a datasheet value taken on trust. `TRACEABLE` means an unbroken
chain to a standard and requires the certificate to be named. `UNKNOWN` is the
honest default and produces no finding anywhere in the software.

### 4. Write the campaign configuration

```bash
$EDITOR campaigns/<campaign-id>/campaign.json
```

The configuration names the rig, the channels, and every planned experiment. It
is required by every command: nothing in this toolchain has a default
acquisition, because a campaign whose configuration was implied by a script's
defaults could not be reproduced or audited afterwards.

Validate it before capturing anything:

```bash
python scripts/ttp_hardware_campaign_check.py campaigns/<campaign-id>
```

---

## The five experiments, in order

Run them in order. Each later experiment assumes the earlier ones produced a
usable rig.

### E1 — Rig and stinger characterization *(gate)*

Characterize the excitation path before trusting anything measured through it:
stinger and contact-assembly mass, the usable frequency band, the force channel,
the response channel, and any obvious stinger or fixture resonance.

E1 records the **rig** as its subject, not an instrument. Set
`subject_is_rig: true` on the plan and name the rig in `instrument_id`; the
software refuses a rig-characterization experiment that does not declare this,
because a silent substitution would let a rig result read as a specimen result.

```bash
python scripts/ttp_hardware_campaign.py rig-check \
    --config campaigns/<id>/campaign.json \
    --experiment e1-rig \
    --runs campaigns/<id>/runs-e1.json \
    --evidence-origin HARDWARE --write
```

**E1 is a real gate.** If the rig cannot produce usable measurement evidence,
stop the campaign and report that. Record the downstream experiments as
`BLOCKED_BY_GATE` naming `e1-rig`, and set the campaign's own status to
`HALTED_AT_GATE`. A failed E1 is a legitimate experimental result about the
proposed architecture. Do not tune around it and erase the original finding.

### E2 — Fixed-point repeatability

Repeated captures at one point with the contact **never broken**. Give every run
the same `contact_configuration_id`: that is what says the contact held.

```bash
python scripts/ttp_hardware_campaign.py fixed-point --config ... --write
```

### E3 — Detach/reattach repeatability

The same point, captured across deliberate re-attachments. Detach the stinger
completely and remount it between blocks, and give **each attachment its own**
`contact_configuration_id`.

Capture at least two runs per attachment where practicable, and at least two
attachments. Within-attachment spread and between-attachment spread are reported
separately and are never averaged together — the difference between them is the
result.

```bash
python scripts/ttp_hardware_campaign.py reattach --config ... --write
```

### E4 — Reciprocity

Drive at A, measure at B. Then drive at B, measure at A. Record
`drive_point_id` and `response_point_id` on every run: the study's own
`measurement_point_id` is singular and cannot express a pair.

Every direction needs its counterpart. An unpaired direction is refused rather
than reported as half a result.

```bash
python scripts/ttp_hardware_campaign.py reciprocity --config ... --write
```

Each direction is its own capture and lands on its own frequency bin. The pair
record keeps both and derives the gap between them, so a reviewer can see
whether a residual spans two slightly different frequencies before reading the
residual itself. No limit is placed on that gap.

Report the residual. Do not grade it.

### E5 — Deliberate mass-loading challenge

Add known masses at a recorded location and re-measure. Suggested progression:
baseline (nothing added), then roughly 0.5 g, 2 g, and 5 g, plus a higher
challenge if the response warrants it.

**Weigh every mass and record the measured value.** `added_mass_g` is the
measured mass; `nominal_added_mass_g` is what you intended. The intended figure
never substitutes for the measured one, and every delta is computed from the
measured one.

Capture at least two runs per mass, including the baseline. A delta between two
single captures cannot be told apart from the spread of the measurement, and the
software refuses to report one.

```bash
python scripts/ttp_hardware_campaign.py mass-loading --config ... --write
```

Report the response. Do not grade it.

---

## During capture

### Every run records

- `run_id`, `captured_at` (ISO-8601, UTC, zero offset);
- `session_id` and `acquisition_id`;
- the retained raw artifact identifiers;
- `witnessed_by`, where a person attests to the session;
- the campaign condition for its experiment — attachment, point pair, or
  measured mass.

`witnessed_by` is what separates *hardware-origin* from *witnessed*. Hardware
origin says the data came off physical instruments; a witnessed session says the
provenance is recorded, retained, and attributable to someone. Capability
promotion follows the stricter one, and it is never inferred.

### Environmental conditions

Record temperature and relative humidity where a reading is available. They are
recorded, never corrected for. An unavailable reading stays unknown.

### When a capture fails

Record it as a rejected run with its reason. Do not delete it and do not
re-number the sequence. A rejected run keeps its identity, its artifacts, and
its provenance; it is excluded from the statistics and included in the
accounting, and the run count in every report reflects what was actually
attempted.

Unusable stinger resonance, insufficient coherence, contact variability, poor
reciprocity, excessive perturbation, and a failed force or response channel are
all valid outcomes. None of them is a reason to delete a run.

---

## Evidence preservation

Raw audio is **not** committed to this repository (`.gitignore` excludes
`*.wav`). Every raw measurement is retained outside it and registered by content:

| Field | Meaning |
| --- | --- |
| `artifact_id` | How runs refer to it |
| `sha256` | **The durable identity.** Computed over the file's bytes |
| `byte_count`, `media_type` | What it is |
| `capture_run_id` | The run that produced it |
| `storage_locator` | Where a copy may currently be found — portable, not a workstation path |
| `local_path_hint` | Optional, explicitly ephemeral |

The digest is the authority, not the path. An artifact reference must survive
the file being moved to another machine, so an absolute host path is refused as
a storage locator.

Register the artifacts, then verify the whole campaign:

```bash
python scripts/ttp_hardware_campaign.py report \
    --config campaigns/<id>/campaign.json \
    --studies out/nsf/campaign \
    --artifacts campaigns/<id>/artifacts.json \
    --write

python scripts/ttp_hardware_campaign_check.py out/nsf/campaign
```

The campaign's status is derived from what actually ran rather than stated:

| Status | Means |
| --- | --- |
| `PREPARED` | A configuration exists and nothing has been run against it |
| `FIXTURE_EXECUTED` | The path was rehearsed against fixture or synthetic data |
| `HARDWARE_EXECUTED` | At least one experiment ran against hardware-origin evidence |
| `HALTED_AT_GATE` | A gating experiment stopped the campaign |
| `ABORTED` | The campaign was abandoned for a reason that was not a gate |

`FIXTURE_EXECUTED` and `HARDWARE_EXECUTED` are deliberately different words. A
rehearsal proves the path works and is not a hardware campaign, and nothing lets
one be recorded as the other: `--execution-status` may state one, and a stated
status the outcomes contradict is refused.

Each executed experiment also records the origin of the study it produced and
whether that study met the witnessed standard. Both are read off the study, and
the checker re-derives both from the studies on disk — a summary that could
drift from what it summarizes would be worse than no summary at all.

The checker is read-only. It reports a failing campaign and never repairs one:
an automatic fix would change evidence to match a claim, which is the failure
mode this whole chain exists to prevent.

---

## After the campaign

1. Populate `docs/NSF_TTP_HARDWARE_CAMPAIGN_RESULTS.md` **only from persisted
   evidence**. No hand-entered numbers, and no favourable summary that the
   documents do not produce.
2. Fill in the DO-103 §8 risk table against what actually happened, including
   the risks the campaign left untouched.
3. Promote a capability off `NOT_VERIFIED_ON_HARDWARE` only when **all** of
   DO-103 §10 holds: exercised end to end in a witnessed session, artifacts
   preserved and referenced from `evidence_refs`, the exercising experiment
   named in the capability's notes, `inventory.py` and the frozen baseline
   changed together, and the audit and technical baseline regenerated.
   Promotion is per capability. One successful experiment does not upgrade
   anything it did not exercise.
4. R10 — agreement with an external reference method — **remains open**. Nothing
   in this campaign can close it, because every figure in it compares this
   instrument against itself.
