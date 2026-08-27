# TTP E1 — Hardware Identity Register

**Status:** one component possessed (`HOST-001`, pre-owned, outside this
campaign). No component has been *received* by this campaign, so no component
carries a campaign acquisition record. Possession and acquisition are separate
axes and this register now carries both.
**Dev Order:** DO-104P; deliberately unchanged by DO-104S

This register is the authority on **what is physically in hand**. The
[BOM](TTP_E1_HARDWARE_BOM.md) records what is *chosen*; this file records what
exists. A component cannot reach `RECEIVED` in the BOM without a row here
carrying a real serial number or asset label, and
`scripts/check_e1_hardware_bom.py` enforces exactly that.

The distinction is not bureaucratic. Three components are `SELECTED` in the BOM
because the repository's authoritative
[stack specification](TTP_HARDWARE_STACK.md) chose them as a *design*. A design
document naming a Raspberry Pi 5 is not a Raspberry Pi 5.

## Register

| local_id | component_class | manufacturer | model | serial_number | asset_label | received_date | inspection_status | ownership_status | observed_at | observed_by | observation_method | datasheet_sha256 | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HOST-001 | host | Raspberry Pi | Raspberry Pi 5 16GB | TBD | TTP-ASSET-001 | TBD | NOT_RECEIVED | CONFIRMED_PRESENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | Owned since 2025-04, outside this campaign: never ORDERED, not RECEIVED by it. Possession is on the ownership axis; the acquisition ladder is untouched. Local asset label, not a serial - the manufacturer serial has not been read |
| ADC-001 | adc_interface | HiFiBerry | DAC+ ADC Pro | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | Design-selected only. Ownership unconfirmed |
| PREAMP-001 | mic_preamp | custom build | OPA1612 balanced mic preamp | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | Design-specified; board existence unconfirmed |
| MIC-001 | microphone | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | Model never locked |
| FORCE-001 | force_transducer | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | — |
| PRECOND-001 | force_conditioner | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | — |
| SHAKER-001 | shaker | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | — |
| AMP-001 | amplifier | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | — |
| STINGER-001 | stinger | fabricated | TBD | n/a | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | n/a | Fabricated parts carry an asset label rather than a serial |
| TIP-001 | contact_tip | fabricated | TBD | n/a | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | n/a | Same |
| STAND-001 | stand_base | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | TBD | — |
| REF-STRUCT-001 | reference_structure | TBD | TBD | n/a | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | n/a | Asset label; a plate has no serial |
| CABLE-001 | cabling | TBD | TBD | n/a | TBD | TBD | NOT_RECEIVED | CONFIRMED_ABSENT | 2026-08-27 | Ross Echols | OPERATOR_ATTESTATION | n/a | — |

## Census outcome and the observation axis (DO-104R pass 2, 2026-08-27)

The census found **one owned item**: a Raspberry Pi 5 16 GB, in hand since April
2025. See [the census](TTP_E1_OWNERSHIP_CENSUS.md), including why pass 1 recorded
it as absent.

**The deferred observation columns land here.** They were designed to let a
pre-owned item be recorded as possessed while remaining unselected and never
ordered, and were held back on the reasoning that adding a schema for data that
does not exist is worse than waiting. The first owned asset has arrived, and it
is exactly that shape.

| Column group | Meaning | Applies to |
| --- | --- | --- |
| `serial_number`, `asset_label` | Which physical unit this is | any possessed item |
| `received_date`, `inspection_status` | **Campaign acquisition** — what this project ordered and took delivery of | items acquired *by this campaign* |
| `ownership_status`, `observed_at`, `observed_by`, `observation_method` | **Possession** — what is physically held, however it got here | any item, including pre-owned |

The two groups are **not** interchangeable, and the Pi is why. It was bought in
April 2025 for the analyzer, outside this campaign entirely. It was never
`ORDERED` and it is not `RECEIVED` by this campaign — so `received_date` stays
`TBD` and `inspection_status` stays `NOT_RECEIVED`, while `ownership_status`
reads `CONFIRMED_PRESENT`. Both statements are true at once. Collapsing them
into one column would force a choice between claiming an order that never
happened and denying possession that plainly exists.

`RECEIVED` is deliberately **not** used for pre-owned hardware. It sits above
`SELECTED` on the acquisition ladder, so using it here would silently assert a
selection nobody has made — and the human selection ruling is
`SELECTION_DEFERRED`.

**`TTP-ASSET-001` is a locally assigned asset label, not a serial number.** The
manufacturer serial has not been read; `serial_number` stays `TBD`. Assigning a
local label is permitted; inventing a serial is not, and none was invented.

### Still not built: the orphan-rule inversion

DO-104R also locks an inversion of the register's orphan invariant, so the
register may carry observed assets no BOM row references. **Still not needed.**
The Pi maps cleanly to `HOST-001`, and no equipment outside the BOM was found. So
`check_register` keeps its stricter one-to-one rule and goes on catching a
mistyped `local_id`. It lands with the first unmapped observed asset, on the same
reasoning that governed these columns.

## Why DO-104S did not touch this register

DO-104S selected hardware and recommended a configuration. It deliberately added
nothing here, and the omission is the point rather than an oversight.

This register is the authority on **what is physically in hand**. Nothing is in
hand. Writing a recommended manufacturer and model into these rows would put
design identity into the one document whose entire purpose is to record physical
identity, and the distinction between the two is what stops a design document
from being read later as evidence of possession.

The recommendation lives in the
[procurement status](TTP_E1_PROCUREMENT_STATUS.md) and the
[selection rationale](TTP_E1_HARDWARE_SELECTION_RATIONALE.md). The digests of
the datasheets behind it live in the
[datasheet manifest](TTP_E1_DATASHEET_MANIFEST.json). Rows here stay `TBD` and
`NOT_RECEIVED` until something arrives and someone reads a serial number off it.

## Inspection status vocabulary

| Status | Means |
| --- | --- |
| `NOT_RECEIVED` | Not in hand |
| `RECEIVED_UNINSPECTED` | Arrived, not yet checked |
| `INSPECTED_OK` | Model confirmed, undamaged, accessories present |
| `INSPECTED_PROBLEM` | Arrived with a defect or wrong model — see notes and procurement status |

## Rules

**A serial number is never invented before receipt.** `TBD` on an unreceived
component is correct and stays that way; a placeholder that looks like a serial
is worse than an empty field because it survives into evidence.

**Fabricated parts carry an asset label instead of a serial.** A stinger has no
manufacturer serial, but it still needs a durable identity — E1 may build several,
and "the stinger" will not be unambiguous by the third one.

**Local IDs are permanent.** If `FORCE-001` is rejected and replaced, the
replacement is `FORCE-002`. Reusing an ID silently rewrites the history of every
run that referenced it.

**Datasheet digests belong here and in the manifest.** The register records the
digest of the datasheet that was current at receipt; the
[manifest](TTP_E1_DATASHEET_MANIFEST.json) records where it came from and when.

## Relationship to measurement evidence

These local IDs are what the campaign records use. `SHAKER-001` becomes
`excitation_device_id`, `STINGER-001` becomes `stinger_id`, `FORCE-001` becomes
the excitation channel's `sensor_id`, `REF-STRUCT-001` becomes
`reference_structure_id`. The IDs must exist before the first capture, because
provenance recorded against an unnamed component cannot be traced back to a
physical object.
