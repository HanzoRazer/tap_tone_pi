# TTP E1 — Interface Matrix

**Status:** requirements from DO-104P, resolved against candidates by DO-104S.
The architecture gate verdict is at the foot of this document.
**Dev Order:** DO-104P; interfaces resolved under DO-104S

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

## DO-104S — resolved interfaces for the preferred chain

The tables above state the interfaces as *requirements*, with connectors marked
`TBD` because nothing was selected. This section resolves them against actual
candidates. Every figure traces to a manufacturer document in
[the datasheet manifest](TTP_E1_DATASHEET_MANIFEST.json).

**This is the architecture gate.** DO-104S may not nominate a preferred
configuration unless the complete chain connects while preserving synchronized
force and microphone acquisition. What follows is the determination, including
the parts that do not resolve.

### Force chain — resolved

| From | To | Signal | Connector | Level | Verdict |
| --- | --- | --- | --- | --- | --- |
| 208C01 | 480C02 | IEPE on constant current | 10-32 coaxial jack → BNC jack | sensor needs 18–30 VDC at 2–20 mA; conditioner supplies 25–29 VDC at 2.0–3.2 mA | **Compatible.** Supply sits inside the sensor's window |
| 480C02 | ADC ch0 | Conditioned AC voltage, unity gain | BNC jack → RCA | 1.124 V pk (0.795 Vrms) at the exciter's full 10 N, against a 2.1 Vrms maximum | **Compatible, 2.6× headroom.** No attenuator required |
| ADC ch0 input gain | — | PGA in the ADC front end | — | −12 dB to +32 dB | **Covers the low end.** 0.5 N produces 56 mV, which the PGA lifts into the usable region |

`ATTEN-001` is **not required by this pairing** and stays in the BOM as a
conditional row. The transducer would only overrun the input at 26 N, and the
selected exciter cannot produce more than 10 N: the shaker sets the ceiling, not
the ADC. A larger exciter or a higher-sensitivity transducer brings the
attenuator back, which is why the row is kept rather than deleted.

### Excitation chain — resolved

| From | To | Signal | Connector | Level | Verdict |
| --- | --- | --- | --- | --- | --- |
| HiFiBerry DAC out | 2718 | Drive from `signal_gen` | RCA → BNC (rear input) | 2718 carries a built-in attenuator and continuously variable gain, 40 dB maximum | **Compatible.** The amplifier adapts to the DAC level rather than the reverse |
| 2718 | 4810 | Power drive | Speakon → two banana | 75 VA into 3 Ω; exciter is 3.5 Ω at 500 Hz, 1.8 A rms maximum | **Compatible, and manufacturer-paired.** The 2718 data explicitly instructs limiting output current to 1.8 A for the 4810 |
| 2718 | — | Passband | — | 10 Hz – 20 kHz ±0.5 dB | Sets the usable drive band. The exciter itself reaches DC–18 kHz; the amplifier is the narrower element |

The shaker/amplifier pairing is not an inference from two datasheets read side by
side — the amplifier's own product data names this exciter and states the current
limit for it. That is the "verified as a pair, not separately" requirement met by
the manufacturer rather than by us.

### Response chain — resolved

| From | To | Signal | Connector | Level | Verdict |
| --- | --- | --- | --- | --- | --- |
| M23 G2 | OPA1612 preamp | Microphone, phantom powered | XLR balanced | Microphone needs 24–48 V at 10 mA; preamp supplies 48 V phantom | **Compatible** |
| OPA1612 preamp | ADC ch1 | Unbalanced line | RCA | gain staged into the input window | **Compatible** — the legacy path already solves this |

**Reference grade takes a different route and it must not be conflated with this
one.** The GRAS 46AE is CCP-powered (4 mA at 24 V), cannot use the phantom
preamp at all, and is conditioned by the four-channel 482C05 alongside the force
sensor. In that configuration the OPA1612 stage is not in the chain.

### Mechanical — resolved on one thread standard

| From | To | Interface | Verdict |
| --- | --- | --- | --- |
| 4810 table | 208C01 | 10-32 UNF | **Match.** Exciter table thread and transducer thread are the same standard |
| 208C01 | stinger | 10-32 UNF female | **Match.** B&K supplies 10-32 stinger stock as a 4810 accessory |
| stinger | tip | fabricated, replaceable | Unresolved by design — the tip is fabricated and its geometry is an E1 variable |

No thread adapter is required anywhere in the drive train. That is recorded as a
finding: an adapter shown to be unnecessary is different from an adapter nobody
checked for.

### Cabling — enumerated, not assumed

The chain needs six interconnects, and none of them is silently absorbed into
"cabling":

1. 10-32 coaxial plug → BNC — sensor to conditioner
2. BNC → RCA — conditioner output to ADC ch0
3. RCA → BNC — DAC output to amplifier input
4. Speakon → banana — amplifier output to exciter
5. XLR — microphone to preamp
6. RCA — preamp output to ADC ch1

### Synchronization — the determination

| Claim | Status | Basis |
| --- | --- | --- |
| Force and microphone are sample-synchronous with each other | **Established, structurally** | They are ch0 and ch1 of one two-channel converter in one I²S stream. Synchronization is a property of the converter, not of the integration |
| DAC output and ADC capture are sample-locked | **NOT established** | The datasheet says "low-jitter dual-domain clock" about decoupling from the Pi. No retrieved manufacturer document states DAC/ADC sample-lock, and vendor support material states a latency always exists between playback and capture |
| Software compensation for unsynchronized devices | **Not authorized** | DO-104P §4.5, unchanged |

**What E1 binds on is the first row, and it holds.** The transfer function is
response over *measured force*, both channels of the same converter, so nothing
in the intended measurement depends on drive-to-response alignment.

**Constraint carried forward:** the commanded DAC signal may not be used as a
phase reference. Any analysis that would use the commanded waveform that way
needs its own architectural ruling and its own evidence.

---

## Architecture gate — verdict

**The gate passes.** A complete contact-excitation, measured-force,
microphone-response chain can be assembled around the existing HiFiBerry
acquisition architecture without replacing the ADC, adding an asynchronous DAQ,
introducing an independent clock, or reinterpreting commanded excitation as
measured force.

The finding that decides it is the level budget, and it inverts the risk DO-104P
recorded. The concern was a conditioner output too large for the input window.
The measured reality of the pairing is a signal comfortably *inside* it, with the
programmable input gain covering the low end — and, referred to force, an
acquisition path whose noise contribution sits roughly an order of magnitude
below the transducer's own resolution. The ADC is not the weak element in the
force chain.

### What passing does not mean

It means these components connect on paper, at datasheet values, with the
adapters listed above. It does not mean the chain works. Installed noise floor,
usable band, coherence, mass-loading error and drift are E1 measurements, and
none of them is claimed here.

### Open risks recorded rather than resolved

| # | Risk | Why it is not a blocker | What closes it |
| --- | --- | --- | --- |
| R1 | Drive-to-response sample alignment is not established | E1 does not need it; force and microphone are synchronous with each other | An architectural ruling, if any future analysis wants the commanded waveform as a phase reference |
| R2 | **The ADC has no anti-aliasing filter in the input path** — the vendor states this as a bandwidth feature | Content above Nyquist folds back rather than being rejected. At 96 kHz the transducer's own 36 kHz limit helps, but broadband contact noise is not bounded by it | Band-limited excitation plus an E1 measurement characterizing the residual, or external anti-alias filtering designed in |
| R3 | The baseline DAC+ ADC Pro is **superseded by its vendor**, described as available in larger quantities for OEM customers on request | Still purchasable at $64.90 and its input specifications are verified | Either procuring while available, or verifying the DAC2 ADC Pro's input specifications, which are **not** published on its product page and are not verified here |
| R4 | Mass cancellation. The 208C01 is 22.7 g overall, and the datasheet does not break out the specimen-side end mass that loads the measurement | E1 already records `combined_contact_mass_g` as a measured quantity | Weighing the assembled contact mass during E1 rather than estimating it |
| R5 | AC coupling means no static preload readout on ch0 | Known and accepted since DO-104P | Preload stays a procedural observation recorded by the operator |
| R6 | The reference-grade response path abandons the OPA1612 preamp entirely | Only affects the reference tier | A separate decision if that tier is ever procured |

R2 is the one that deserves attention beyond this order. It is a
measurement-integrity property of the selected ADC rather than a procurement
problem, and it was not visible in DO-104P because the input path had not been
read at this level of detail.

## Blocking-issue checklist — current state

- [x] force transducer chosen **without** a compatible conditioner — closed; selected as a pair
- [x] conditioner output exceeding the input window with no attenuation designed in — closed; 2.6× headroom, attenuator not needed
- [x] microphone requiring power the preamp cannot supply — closed for the preferred tier; the reference tier deliberately uses a different conditioning route
- [x] fewer than two simultaneous channels anywhere in the chain — closed; two channels of one converter
- [x] shaker and amplifier electrically mismatched — closed; manufacturer-paired with a stated current limit
- [x] shaker armature thread incompatible with the transducer — closed; 10-32 UNF throughout
- [ ] no stinger mounting interface — thread resolved, stinger design still fabricated
- [ ] no contact-tip design — open
- [ ] no reference structure available — open

The three that remain open are all fabrication tasks rather than procurement
blockers, and none of them gates the purchase decision.

