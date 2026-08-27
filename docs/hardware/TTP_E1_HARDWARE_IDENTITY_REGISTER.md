# TTP E1 — Hardware Identity Register

**Status:** empty. No component has been received, so no component has an
identity beyond its reserved local ID. As of the DO-104R census (2026-08-27)
no component is possessed either, which is now an established finding rather
than an open question.
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

| local_id | component_class | manufacturer | model | serial_number | asset_label | received_date | inspection_status | datasheet_sha256 | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HOST-001 | host | Raspberry Pi | Raspberry Pi 5 | TBD | TBD | TBD | NOT_RECEIVED | TBD | Design-selected only. Ownership unconfirmed |
| ADC-001 | adc_interface | HiFiBerry | DAC+ ADC Pro | TBD | TBD | TBD | NOT_RECEIVED | TBD | Design-selected only. Ownership unconfirmed |
| PREAMP-001 | mic_preamp | custom build | OPA1612 balanced mic preamp | TBD | TBD | TBD | NOT_RECEIVED | TBD | Design-specified; board existence unconfirmed |
| MIC-001 | microphone | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | TBD | Model never locked |
| FORCE-001 | force_transducer | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | TBD | — |
| PRECOND-001 | force_conditioner | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | TBD | — |
| SHAKER-001 | shaker | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | TBD | — |
| AMP-001 | amplifier | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | TBD | — |
| STINGER-001 | stinger | fabricated | TBD | n/a | TBD | TBD | NOT_RECEIVED | n/a | Fabricated parts carry an asset label rather than a serial |
| TIP-001 | contact_tip | fabricated | TBD | n/a | TBD | TBD | NOT_RECEIVED | n/a | Same |
| STAND-001 | stand_base | TBD | TBD | TBD | TBD | TBD | NOT_RECEIVED | TBD | — |
| REF-STRUCT-001 | reference_structure | TBD | TBD | n/a | TBD | TBD | NOT_RECEIVED | n/a | Asset label; a plate has no serial |
| CABLE-001 | cabling | TBD | TBD | n/a | TBD | TBD | NOT_RECEIVED | n/a | — |

## Census outcome (DO-104R, 2026-08-27)

The physical ownership census was performed and found **no E1-relevant hardware
in possession**. See [the census](TTP_E1_OWNERSHIP_CENSUS.md).

**No rows were added and no columns were added**, and both omissions are
deliberate.

No rows, because this register records physical objects and no physical object
exists. A row asserting the absence of a thing would be a row about nothing.

No columns, because the DO-104R model locks an observation axis for this
register — `ownership_status`, `observed_at`, `observed_by`,
`observation_method` — designed to let a *pre-owned* item be `OWNED` while
remaining unselected and never ordered. With nothing owned, those columns would
have no data in them, and adding a schema for data that does not exist is the
error this project deliberately avoided when it held the state-model work until
after the census. **The columns land with the first owned asset, not before.**

The same applies to the orphan invariant. DO-104R inverts it so the register may
carry observed assets no BOM row references. That inversion exists to hold
unmapped observed assets; none was found, so `check_register` keeps its stricter
one-to-one rule and continues to catch a mistyped `local_id`. The looser rule is
recorded here as pending, not implemented.

Every row therefore remains `TBD` and `NOT_RECEIVED`, and now does so on
evidence rather than on absence of information.

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
