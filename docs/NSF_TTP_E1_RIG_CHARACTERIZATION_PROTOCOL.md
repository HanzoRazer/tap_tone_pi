# NSF TTP E1 — Rig Bring-Up and Characterization Protocol

**Status: not executed. No rig exists.** This is the bench procedure E1 will be
run by, written and frozen before the hardware is built.

Dev Order: DO-104 — E1 Hardware Bring-Up and Rig Characterization
Campaign protocol: `docs/NSF_TTP_HARDWARE_CAMPAIGN_PROTOCOL.md`
Results: `docs/NSF_TTP_E1_RIG_CHARACTERIZATION_RESULTS.md`

---

## 1. Objective

Find out whether the grounded shaker / force-transducer / stinger / microphone
chain can produce usable, provenance-complete Phase 2 transfer-function evidence
over **any** defensible frequency region.

E1 characterizes the **rig**. It does not measure an instrument, and it does not
measure repeatability — that is E2, and E2 does not begin unless E1 says it may.

**E1 is a gate.** "This rig cannot produce usable evidence" is a complete and
scientifically useful answer. It stops the campaign; it is not a reason to
adjust the rig until the numbers improve and then report only the improvement.

## 2. Hardware inventory

Record every component before assembly. **Nothing here is specified in advance** —
no shaker, amplifier, transducer, interface, microphone, stinger stock, or tip
geometry has been selected, and inventing a specification in this document would
be inventing evidence.

| Component | Record | Status |
| --- | --- | --- |
| Shaker | manufacturer, model, serial | TBD |
| Amplifier | manufacturer, model, serial | TBD |
| Force transducer | manufacturer, model, serial, native unit, sensitivity **and the unit the manufacturer states it in** | TBD |
| Audio interface | manufacturer, model, channel count, sample rate | TBD |
| Microphone | manufacturer, model, serial | TBD |
| Stinger stock | material, diameter, length | TBD |
| Contact tip | material, geometry | TBD |
| Rig base and stand | description | TBD |
| Reference structure | description, dimensions, material | TBD |

Every row that stays TBD at execution time is recorded as unknown. It is never
filled in with a plausible value: the reports distinguish *unknown* from
*observed*, and an invented value destroys that distinction permanently.

## 3. Rig assembly

Assemble in this order, and record the configuration as built:

```
rig base → stand → grounded shaker → force transducer → stinger → contact tip
```

The shaker body is grounded to a mass independent of the specimen support. **The
shaker's own mass must never ride on the structure being measured** — if it
does, the rig is part of the moving system and the measurement is of something
other than the specimen.

Assign a `rig_configuration_id` to the assembled combination. Swapping the
stinger, the tip, the fixture, or the support is a **configuration change, not a
repeat**, and needs a new id.

## 4. Sensor identification

For each of the force transducer and the microphone, record:

- `sensor_id`, manufacturer, model, serial or local id
- `native_unit` — the unit the channel is scaled to
- `sensitivity_value` and `sensitivity_unit` — **in the unit the device states
  it in.** Do not convert into a unit this repository picked first, and do not
  assume mV/N
- `calibration_traceability` — `TRACEABLE`, `NOMINAL`, or `UNKNOWN`
- `calibration_reference` — required if and only if `TRACEABLE`

`NOMINAL` is a datasheet value taken on trust. `UNKNOWN` is the honest default
and produces no finding anywhere in the software. **Measured force is not
traceable force**, and E1 establishes neither calibration nor traceability.

## 5. Stinger measurement

Weigh and measure the stinger before it is installed:

- `stinger_mass_g` — measured, on a stated instrument
- length, diameter, material

Record the instrument used for each measurement. DO-103 §4.9 refused to inherit
an approximate mass figure and asked for these to be measured instead; this is
where that happens.

## 6. Contact-tip measurement

- `contact_tip_mass_g` — measured
- `combined_contact_mass_g` — measured or estimated separately where practical
- tip geometry and material

**These are two different physical ideas, and the software will not check one
against the other.** `stinger_mass_g` and `contact_tip_mass_g` are physical
component masses. `combined_contact_mass_g` is the measured or estimated
effective mass participating at the specimen interface, and is **not required to
equal their arithmetic sum** — it may legitimately be lower than the sum of the
physical parts, because not all of a component participates in loading the
specimen. The only invariant enforced is that all three, when present, are
finite and non-negative.

## 7. Channel verification

Before the stinger touches anything:

- confirm the interface enumerates both channels
- confirm channel identity — which physical input is force, which is microphone
- confirm the sample rate the interface is actually running at
- confirm both channels respond to their own stimulus
- confirm the clipping point of each channel and stay below it

Record `interface_id`, `sample_rate_hz`, and the channel indices. The transfer
quantity's unit is **derived** from the channel pair, so an incorrectly
identified channel silently mislabels every result that follows.

## 8. Dry electrical test

Drive the amplifier with the shaker **disconnected from the specimen**.

- confirm the drive signal reaches the shaker
- observe the force channel with no contact — it should read essentially nothing,
  and anything else is a finding worth recording before proceeding
- observe the microphone channel for amplifier and room noise

## 9. Low-level mechanical drive test

Drive the shaker at low level, still free of the specimen. Observe and record:

- the force spectrum
- obvious fixture resonances
- obvious stinger resonances
- contact chatter or nonlinearity
- unexpected noise

**Record problems before addressing them.** If the stinger or fixture produces a
strong resonance, that resonance is E1 evidence. Do not notch it out to make the
campaign look clean — no signal-processing order authorizes that treatment.

## 10. Reference-body measurement

Establish contact with a **controlled reference body or sacrificial plate**, not
an instrument of value. DO-104 §4.10 is explicit about the order:

```
fixture / reference body → stable plate or panel → instrument, only after E1 passes
```

Record:

- `reference_structure_id` — the body under the stinger. Note that a
  rig-characterization experiment records the **rig** in `instrument_id` with
  `subject_is_rig: true`, so the body being driven is named in
  `reference_structure_id` instead. Neither substitutes for the other
- contact point, tip, and approach
- preload method, if any
- support configuration
- microphone position, distance, and orientation
- whether contact remained continuous, and whether slipping or chatter occurred

Contact condition is a **procedural variable**, not an assumption. Do not
silently assume identical contact across attempts.

## 11. Frequency sweep procedure

Acquire driven measurements across the proposed frequency region using the
existing Phase 2 path. E1 introduces no new signal processing.

```bash
python scripts/ttp_hardware_campaign.py rig-check \
    --config campaigns/<id>/campaign.json \
    --experiment e1-rig \
    --runs campaigns/<id>/runs-e1.json \
    --evidence-origin HARDWARE --write
```

Every run records:

- `run_id` and `sequence_index` — **the acquisition order as acquired.**
  Reconstructing it later by sorting timestamps is a guess: two captures a
  second apart can be logged out of order, and a re-run keeps its original clock
  time
- `captured_at` in UTC

  **Order and clock are independent evidence.** `sequence_index` is
  authoritative for acquisition order; `captured_at` is separately preserved.
  Where they disagree the contradiction is *reported and left standing* — never
  sorted into agreement, and neither one treated as the truth the other must
  match. That disagreement may itself be the finding: a capture, clock, import,
  or operator problem.
- the nominal frequency asked for, and the actual bin that answered — both are
  recorded, with the signed offset between them derived. The offset is
  **verified against those two frequencies whenever a run is read back**: a
  document claiming an offset its own frequencies do not produce is refused,
  and an offset recorded without both sources is refused rather than read as
  zero
- force and response channel identities
- session and acquisition ids
- retained raw artifact ids
- `witnessed_by`
- environmental conditions where a reading is available

## 12. Artifact retention

Raw audio is **not** committed to this repository. Every raw measurement is
retained outside it and registered by content:

| Field | Meaning |
| --- | --- |
| `artifact_id` | How runs refer to it |
| `sha256` | **The durable identity** |
| `byte_count` | Size in bytes |
| `media_type` | What it is |
| `kind` | Why it exists |
| `capture_run_id` | The run that produced it |
| `storage_locator` | Where a copy may currently be found — portable |
| `local_path_hint` | Optional, explicitly ephemeral |

**The digest is the identity, not the path.** A storage locator may point at
external or local storage, but an absolute workstation path is refused as an
identity — the reference has to survive the file moving to another machine. A
local path may be kept as ephemeral acquisition metadata and nothing more.

## 13. Failure and abort procedure

Record the attempt as a rejected run with its reason. Do not delete it and do
not renumber the sequence — a rejected run keeps its identity, its artifacts,
its provenance, and its place in the acquisition order.

Any of these is a legitimate E1 outcome, not a reason to hide a run:

```
unusable stinger resonance     force-channel failure
insufficient coherence         response-channel failure
contact chatter or slipping    operator abort
fixture resonance              artifact-integrity failure
```

## 14. Usable-band assessment

Identify a candidate usable frequency region **from observed evidence**:

- a stable force channel
- a stable microphone channel
- finite transfer values
- available coherence
- absence of obvious fixture or stinger domination
- repeatable excitation response during bring-up

**Do not invent a numeric coherence cutoff or residual threshold in order to
call the rig acceptable.** The report shows the underlying observations, and a
reader judges the band from them. If no defensible region exists, say so — that
is the honest E1 result and it halts the campaign.

The band is an **E1 result**, not a predeclared property of the rig. E2 inherits
it by reference to this witnessed E1 evidence rather than copying an
independently typed frequency range that could drift out of agreement with the
evidence it came from.

## 15. Witnessing requirements

A witnessed hardware session for DO-104 requires all of:

- a named operator (`witnessed_by`)
- physical hardware identifiers
- acquisition timestamps
- retained raw source artifacts
- digests over those artifacts
- experiment and run ids
- force and response channel identities
- provenance sufficient for `EvidenceOrigin.HARDWARE` to **derive**

A second human observer is **not** required at this stage. *Witnessed* means a
human-attested physical session backed by machine evidence — not a label. A
later certified-laboratory protocol may impose a stronger rule; this one does
not, and does not pretend to.

The software derives all of it. No caller asserts witnessed status, and
`ttp_hardware_campaign_check.py` re-derives it from the studies on disk.

## 16. Go / no-go disposition

Validate the evidence chain before interpreting anything:

```bash
python scripts/ttp_hardware_campaign_check.py <campaign-dir>
```

If provenance or artifact integrity fails, fix the **evidence** problem. Do not
quietly drop the offending runs.

Then record an explicit disposition in the results document, chosen from what
the evidence supports:

| Disposition | Campaign status | Means |
| --- | --- | --- |
| Proceed to E2 | `HARDWARE_EXECUTED` | A usable band was identified |
| Proceed with a limited band | `HARDWARE_EXECUTED` | A narrower region is defensible; E2 inherits only that region |
| Halt — rig redesign required | `HALTED_AT_GATE` | No defensible region exists |
| Abort — hardware failure | `ABORTED` | The chain could not be brought up at all |

A halt is a result. The next order after a halt is rig redesign, **not**
repeatability testing.

Finally: E1 promotes no capability by itself. Each candidate must independently
satisfy the DO-103 §10 rule — exercised end to end in a witnessed session,
artifacts preserved and referenced, the experiment named in the capability's
notes, inventory and frozen baseline changed together, and the audit
regenerated. And R10, agreement with an external reference method, remains
entirely open: nothing in E1 can touch it.
