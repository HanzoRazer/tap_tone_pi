# TTP E1 — Interface Matrix

**Status:** interfaces specified as requirements; no product-specific connector
resolved. **Dev Order:** DO-104P

The question this document answers is not "is each component good?" It is:

> Does the entire chain physically and electrically connect without an
> unresolved adapter, conditioning, synchronization, or mounting problem?

Three individually excellent products that cannot connect is the classic failure
mode this order exists to prevent.

Component identities are in the [BOM](TTP_E1_HARDWARE_BOM.md).

---

## Electrical interfaces

| From | To | Signal / interface | Connector | Units | Conditioning | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| HOST-001 DAC out | AMP-001 | Drive signal from `signal_gen` | TBD (RCA/3.5 mm) | V | none | Amplifier input range must accept the DAC's output level without clipping or requiring a boost stage |
| AMP-001 | SHAKER-001 | Power drive | TBD (binding post / speaker) | V, A | none | **Paired selection.** Impedance, voltage, and current mismatch can damage hardware or fail to excite |
| FORCE-001 | PRECOND-001 | IEPE/ICP sensor signal on constant current | TBD (10-32 coax / BNC typical) | mV or pC per unit force | **Constant current supply, 2–20 mA at 18–30 V typical** | Highest-risk interface in the order. Conditioning is part of sensor selection, never an afterthought |
| PRECOND-001 | ADC-001 ch0 | Conditioned AC voltage | RCA unbalanced | V | AC-coupled by conditioner | **Must land inside ±3 V, ideally 0.8–2.1 Vrms.** A ±5 V or ±10 V full-scale output needs ATTEN-001, designed in |
| ATTEN-001 | ADC-001 ch0 | Attenuated voltage | RCA unbalanced | V | passive divider | Only present if PRECOND-001 cannot reach the window itself. Must not introduce a ground loop |
| MIC-001 | PREAMP-001 | Microphone, phantom powered | XLR balanced | mV | **48 V phantom from PREAMP-001** | A microphone needing power the preamp cannot supply is a hard blocker |
| PREAMP-001 | ADC-001 ch1 | Unbalanced line | RCA | V | gain staged to 0.8–2.1 Vrms | Stack spec Stage 2 already solves this for the legacy path |
| ADC-001 | HOST-001 | Digital audio | I2S header | — | — | Internal to the Pi stack; already the selected design |

**The ADC is AC-coupled.** Only dynamic force reaches ch0. Static preload is a
procedural observation recorded by the operator, not a reading from this path.

## Mechanical interfaces

| From | To | Interface | Risk |
| --- | --- | --- | --- |
| STAND-001 | SHAKER-001 | Body mount, rigid | The shaker body must be grounded to the stand and must **never** ride on the specimen |
| SHAKER-001 armature | FORCE-001 | Threaded stud, TBD size | Thread mismatch between shaker armature and transducer is a common and avoidable blocker |
| FORCE-001 | STINGER-001 | Threaded, TBD size | Same |
| STINGER-001 | TIP-001 | Replaceable attachment | Tip must change without disturbing the shaker assembly; each change is a configuration change |
| TIP-001 | REF-STRUCT-001 | Contact, preload TBD | Contact condition is a procedural variable, recorded per run and never assumed identical |
| MIC-001 | STAND-001 or separate | Mount, position, orientation | Geometry recorded; E1 does not require it frozen, E2 does |
| STAND-001 | bench/base | Reaction path | Base mass independent of the specimen support |
| cabling | all | Strain relief | Cable tension must not load the drive point — a slow, invisible source of drift |

## Acquisition and synchronization

| Requirement | Status | Note |
| --- | --- | --- |
| Simultaneous force and response capture | **Required** | Phase 2's transfer-function and coherence path assumes it |
| Shared sample clock | **Required** | Satisfied by using both channels of one ADC |
| Channel count | 2 | ch0 force, ch1 microphone — see the reassignment below |
| Sample rate | 48 or 96 kHz | Existing configuration |
| Bit depth | 24 | Existing configuration |
| Software compensation for unsynchronized devices | **Not authorized** | DO-104P §4.5 |

### The ch0 reassignment

| Configuration | ch0 | ch1 |
| --- | --- | --- |
| Phase 2A — legacy speaker ODS | reference microphone | roving microphone |
| Phase 2B — DO-104 contact drive | **force transducer via conditioner** | **microphone response** |

These are mutually exclusive on a two-channel ADC. E1 runs 2B.

## Orphan check

Every component must appear on both sides of at least one interface, or it is
either unnecessary or unconnectable. Current state — every row resolves, but
almost all connectors are `TBD` because nothing is selected:

| Component | Upstream | Downstream | Resolved |
| --- | --- | --- | --- |
| HOST-001 | ADC-001 (I2S) | AMP-001 (DAC out) | interfaces known |
| ADC-001 | PRECOND-001, PREAMP-001 | HOST-001 | **limits known — this is the constraint** |
| PREAMP-001 | MIC-001 | ADC-001 ch1 | interfaces known |
| MIC-001 | — | PREAMP-001 | needs a model |
| FORCE-001 | SHAKER-001 armature | PRECOND-001 | needs a model |
| PRECOND-001 | FORCE-001 | ADC-001 ch0 (± ATTEN-001) | needs a model |
| SHAKER-001 | AMP-001, STAND-001 | FORCE-001 | needs a model |
| AMP-001 | HOST-001 | SHAKER-001 | needs a model |
| STINGER-001 | FORCE-001 | TIP-001 | needs a design |
| TIP-001 | STINGER-001 | REF-STRUCT-001 | needs a design |
| STAND-001 | bench | SHAKER-001 | needs a design |
| REF-STRUCT-001 | TIP-001 | MIC-001 (acoustically) | needs selection |

## Blocking-issue checklist

These are procurement blockers, not runtime errors. Each must be closed before
the corresponding component reaches `BENCH_READY`:

- [ ] force transducer chosen **without** a compatible conditioner
- [ ] conditioner output exceeding ±3 V with no attenuation designed in
- [ ] microphone requiring power the preamp cannot supply
- [ ] fewer than two simultaneous channels anywhere in the chain
- [ ] shaker and amplifier electrically mismatched
- [ ] shaker armature thread incompatible with the transducer
- [ ] no stinger mounting interface
- [ ] no contact-tip design
- [ ] no reference structure available
