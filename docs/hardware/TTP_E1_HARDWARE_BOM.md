# TTP E1 — Hardware Bill of Materials

**Status:** framework only. No component is procured. No component is owned.
**Dev Order:** DO-104P
**Validator:** `python scripts/check_e1_hardware_bom.py`

This is the canonical BOM. Where any other document names a component, this file
is the authority; where they disagree, this file is right and the other is stale.

**A design selection is not a possession.** Three rows below are `SELECTED`
because the repository's authoritative
[stack specification](TTP_HARDWARE_STACK.md) chose them as a design — not
because anyone has one. The repository contains no evidence of any physical
acquisition: every captured session in `runs_phase2/` is marked
`"synthetic": true` with `"device": null`, or is the `DEMO` fixture. Nothing may
advance past `SELECTED` on the strength of a design document, and the validator
enforces that by requiring a real serial number or asset label in the
[identity register](TTP_E1_HARDWARE_IDENTITY_REGISTER.md) before `RECEIVED`.

## Status vocabulary

| Status | Means | Requires |
| --- | --- | --- |
| `TBD` | Not selected | — |
| `SELECTED` | A specific product is chosen on paper | manufacturer + model |
| `ORDERED` | Purchase placed | supplier |
| `RECEIVED` | Physically in hand | identity-register entry with serial or asset label |
| `INSPECTED` | Confirmed undamaged and correct | as `RECEIVED` |
| `BENCH_READY` | Interfaces resolved, mountable, powerable | as `INSPECTED`, no open blocker |
| `REJECTED` | Considered and ruled out | a reason in the rationale document |

## Bill of materials

| local_id | component_class | manufacturer | model | part_number | quantity | status | supplier | datasheet_ref | nominal_specification | required_interface | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HOST-001 | host | Raspberry Pi | Raspberry Pi 5 | TBD | 1 | SELECTED | TBD | TBD | 64-bit Pi OS; runs tap_tone_pi | I2S header to ADC | Design-selected in stack spec Stage 4. Not confirmed owned |
| ADC-001 | adc_interface | HiFiBerry | DAC+ ADC Pro | TBD | 1 | SELECTED | TBD | TBD | 2 ch, 24-bit, 48/96 kHz, ±3 V in, 0.8–2.1 Vrms optimal, AC-coupled, RCA | I2S to HOST-001; RCA in from PRECOND-001 and PREAMP-001 | Design-selected, stack spec Stage 3. **Sets the binding electrical limit for the force chain** |
| PREAMP-001 | mic_preamp | custom build | OPA1612 balanced mic preamp | TBD | 1 | SELECTED | TBD | TBD | Input-referred noise < 1 uV; 48 V phantom; unbalanced line out | XLR in from MIC-001; RCA out to ADC-001 ch1 | Design-specified in stack spec Stage 2. Board existence unconfirmed |
| MIC-001 | microphone | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Small-diaphragm condenser; approx -40 dBV/Pa | XLR to PREAMP-001 | Model never locked in the stack spec. Traceability UNKNOWN unless certified |
| FORCE-001 | force_transducer | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Dynamic force, IEPE/ICP preferred; range to cover shaker output | Thread to SHAKER-001 armature and STINGER-001; signal to PRECOND-001 | Highest-risk selection. Sensitivity recorded in the unit the maker states |
| PRECOND-001 | force_conditioner | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Constant current for FORCE-001; AC-coupled out within ±3 V | Sensor side per FORCE-001; RCA out to ADC-001 ch0 | **Selected with FORCE-001, never after.** Output window is the whole risk |
| ATTEN-001 | attenuator | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Passive attenuation into the ADC window | Between PRECOND-001 and ADC-001 ch0 | Required only if PRECOND-001 has no usable output setting. Kept as its own line rather than assumed away |
| SHAKER-001 | shaker | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Grounded mountable; force capability for a plate-scale reference body | Mount to STAND-001; armature to FORCE-001; drive from AMP-001 | Selected as a pair with AMP-001. Body must never ride on the specimen |
| AMP-001 | amplifier | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Impedance, voltage, current matched to SHAKER-001 | Input from HOST-001 DAC out; output to SHAKER-001 | Selected as a pair with SHAKER-001 |
| STINGER-001 | stinger | fabricated | TBD | TBD | 1 | TBD | TBD | TBD | Low effective moving mass, target approx 1–2 g provisional; axial stiff, laterally compliant | FORCE-001 thread to TIP-001 | May be fabricated. Measured mass is authoritative, not the target |
| TIP-001 | contact_tip | fabricated | TBD | TBD | 1 | TBD | TBD | TBD | Documented geometry; measurable mass; replaceable | Attaches to STINGER-001; contacts REF-STRUCT-001 | Tip changes during E1 are explicit configuration changes |
| STAND-001 | stand_base | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Mass independent of specimen support; vertical adjust; cable strain relief | Carries SHAKER-001 reaction to base | Fixture is part of the measurement chain and gets characterized in E1 |
| REF-STRUCT-001 | reference_structure | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Inexpensive, stable, replaceable, plate-scale | Driven by TIP-001; observed by MIC-001 | Deliberately not a finished instrument |
| CABLE-001 | cabling | TBD | TBD | TBD | 1 | TBD | TBD | TBD | Sensor, RCA, XLR, and drive cabling per interface matrix | Per [interface matrix](TTP_E1_INTERFACE_MATRIX.md) | Enumerated once interfaces are frozen |

## Required component classes

The validator requires one row for each of these. A missing class is a hole in
the chain, not an omission in a document:

```
host  adc_interface  mic_preamp  microphone
force_transducer  force_conditioner
shaker  amplifier
stinger  contact_tip
stand_base  reference_structure
cabling
```

`attenuator` is conditional: required only if the selected conditioner cannot
reach the ADC window on its own.

## What the legacy speaker path does not contribute

The stack specification's Phase 2A speaker driver is **not** in this BOM. E1 uses
the same DAC output to drive the shaker amplifier instead, and the two
configurations cannot share ch0 — see [stack spec](TTP_HARDWARE_STACK.md)
Rev 1.4. The speaker remains documented for provenance and is not procured,
retired, or claimed here.

## Open blockers

Tracked in [procurement status](TTP_E1_PROCUREMENT_STATUS.md). At the time of
writing, every blocker is the same one: no component past design selection, and
no authorized budget to change that.
