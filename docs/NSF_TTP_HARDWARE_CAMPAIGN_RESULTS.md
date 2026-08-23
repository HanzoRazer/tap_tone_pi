# NSF TTP Hardware Characterization Campaign — Results

**Execution status: NOT EXECUTED — hardware unavailable.**

This document contains protocol and report structure only. No hardware-origin,
witnessed-session, repeatability, reciprocity, or mass-loading result has been
produced.

Dev Order: `docs/dev_orders/DO-103_HARDWARE_MEASUREMENT_ARCHITECTURE.md`
Protocol: `docs/NSF_TTP_HARDWARE_CAMPAIGN_PROTOCOL.md`

---

## Why this document exists before the campaign

The shape of a result is decided before the result, not after it. DO-103 §13
requires the ingestion path, the provenance rules, and the reporting structure
to exist before any instrument data is collected, so that the campaign is not
analyzed by software — or written up in a document — shaped to fit what it
produced.

Every section below is a heading with nothing under it. That is the accurate
state.

## How this document gets filled in

**Only from persisted evidence.** After execution, generate the campaign
documents and transcribe from them:

```bash
python scripts/ttp_hardware_campaign.py report \
    --config campaigns/<id>/campaign.json \
    --studies out/nsf/campaign \
    --artifacts campaigns/<id>/artifacts.json \
    --write

python scripts/ttp_hardware_campaign_check.py out/nsf/campaign
```

The campaign status is derived from what ran. `HARDWARE_EXECUTED` requires an
experiment carrying hardware-origin evidence; a rehearsal against fixture data
is `FIXTURE_EXECUTED` and is not a hardware campaign. This repository's campaign
is `PREPARED`.

No number in this document may be hand-entered, and no summary may be more
favourable than what `out/nsf/campaign/ttp_hardware_campaign.md` says. Every
figure carries the digest of the document it came from, so a reader can check.

---

## 1. Rig configuration as built

*Not executed.* No rig exists. When it does, this section records
`rig_configuration_id`, the shaker, stinger, contact tip, fixture, support
condition, and drive point — each marked observed or unknown.

## 2. Force input

*Not executed.* Records the force transducer, its channel, the unit it is scaled
to, its stated sensitivity in the unit the device states it in, and its
calibration traceability.

Force will be **measured**, which makes the excitation observable. It will not
be traceable unless a calibration reference is recorded, and this section must
say which of the two holds.

## 3. Acoustic response

*Not executed.* Records the microphone, its channel, position, and orientation.

The measured transfer quantity is acoustic pressure per unit measured force,
`Pa/N`. It is not mobility, accelerance, or receptance.

## 4. E1 — Rig and stinger characterization

*Not executed.* E1 is a gate: if the rig cannot produce usable measurement
evidence, the campaign stops here and that outcome is recorded as the result,
with the downstream experiments marked `BLOCKED_BY_GATE`.

## 5. E2 — Fixed-point repeatability

*Not executed.*

## 6. E3 — Detach/reattach repeatability

*Not executed.* Within-attachment and between-attachment variation are reported
separately and never combined.

## 7. E4 — Reciprocity

*Not executed.* Residuals will be reported with their conditions, sample sizes,
per-direction coherence, and both directions' evaluation frequencies with the
gap between them — and **without** an acceptance threshold on any of them.

## 8. E5 — Deliberate mass-loading challenge

*Not executed.* Measured masses only; deltas reported against an unloaded
baseline, and **without** an acceptance threshold.

## 9. Failed and abandoned runs

*Not executed.* Every attempt — valid, rejected, abandoned — will appear here
with its reason. Failed runs stay in the evidence.

## 10. Retained raw artifacts

*Not executed.* Raw audio is retained outside this repository and registered by
SHA-256 digest, byte count, media type, producing run, and a portable storage
locator.

## 11. Capability promotion

**No capability has been promoted.** Every hardware-dependent capability remains
`NOT_VERIFIED_ON_HARDWARE`, and every study this repository can currently produce
is `FIXTURE` or `SYNTHETIC`.

Promotion requires all of DO-103 §10: end-to-end execution in a witnessed
session, preserved artifacts referenced from `evidence_refs`, the exercising
experiment named in the capability's notes, `inventory.py` and the frozen
baseline changed together, and a regenerated audit that agrees. It is per
capability; one successful experiment upgrades nothing it did not exercise.

## 12. Technical risks

No risk is narrowed by this document. Excitation variability, sensor
positioning, support condition, environment, operator variability, and
between-session repeatability all remain exactly as open as
`docs/NSF_TTP_PHASE_I_TECHNICAL_RISKS.md` records them.

**R10 — agreement with an external reference method — remains entirely open**,
and nothing in this campaign can close it. Every figure it will produce compares
this instrument against itself.
