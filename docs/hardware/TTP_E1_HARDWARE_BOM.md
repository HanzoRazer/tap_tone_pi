# TTP E1 — Hardware Bill of Materials

**Status:** framework only. No component is procured. No component is owned.
**Dev Order:** DO-104P; tiered candidates added under DO-104S
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

## Tiered candidates (DO-104S)

The table above is the **canonical role table**: fourteen rows, one per component
class, each naming a slot in the measurement chain. It is unchanged by DO-104S
and remains what the identity register, the procurement status document and the
bench protocol are checked against.

The tables below are **candidate rows**. A candidate is a specific purchasable
product proposed to fill one role at one tier. Candidates are deliberately kept
in their own tables so that the identity and protocol machinery never comes to
depend on a vendor choice: a candidate can be swapped, repriced, or rejected
without touching the row that the register keys on.

### Tier vocabulary

| Tier | Means |
| --- | --- |
| `RESEARCH_MINIMUM` | The cheapest chain that still measures force, keeps the exciter grounded, and produces defensible evidence. Not a compromise on the measurement, only on grade |
| `PREFERRED_E1` | The preferred *technical* configuration for Phase I E1, judged on suitability, integration risk, traceability, lead time and cost together. Not "whatever fits a budget" — no budget ceiling is authorized |
| `REFERENCE_GRADE` | What the chain looks like when traceability and instrument grade are prioritized over cost |

A tier is **complete** when it supplies every mandatory role. Mandatory roles are
the twelve classes below; `attenuator` and `mic_preamp` are conditional and are
required only when a tier's own selections make them necessary.

```
host  adc_interface  microphone
force_transducer  force_conditioner
shaker  amplifier
stinger  contact_tip
stand_base  reference_structure  cabling
```

`mic_preamp` is required **only if that tier's microphone is phantom-powered**.
A CCP/IEPE microphone is conditioned by the ICP conditioner instead, and a tier
that chooses one legitimately has no preamp row. `attenuator` is required only
if that tier's force level budget overruns the ADC input window.

### Ownership after the census

Every candidate reads `CONFIRMED_ABSENT` as of the DO-104R census (2026-08-27).
Nothing in this chain is possessed. That is a finding, not the pre-census
`UNKNOWN` it replaces — and it is what makes `RECOMMEND_PURCHASE` legal for
these rows for the first time, since the validator requires established absence
before a purchase may be recommended. **Legal is not authorized**: every
`procurement_action` remains `HOLD` pending the human selection gate.

### Commercial observations

Price, stock and lead time are **observations with a date**, not component
attributes. `QUOTE_REQUIRED` means the manufacturer does not publish a list
price and a quotation is the only way to obtain one — it is not a missing value
and must never be read as zero. `UNKNOWN` means not yet established.

| candidate_id | role_local_id | component_class | functional_chain | selection_tier | quantity | unit_cost_usd | extended_cost_usd | availability | lead_time | commercial_source | checked_date | procurement_action | ownership |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HOST-RM-001 | HOST-001 | host | synchronized_acquisition | RESEARCH_MINIMUM | 1 | 175.00 | 175.00 | IN_STOCK | ships from US reseller | PiShop.us | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| ADC-RM-001 | ADC-001 | adc_interface | synchronized_acquisition | RESEARCH_MINIMUM | 1 | 64.90 | 64.90 | IN_STOCK_SUPERSEDED | not stated | HiFiBerry direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| MIC-RM-001 | MIC-001 | microphone | response_acquisition | RESEARCH_MINIMUM | 1 | 59.98 | 59.98 | IN_STOCK | 71 on hand, restock 2026-08-21 | Parts Express | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| PREAMP-RM-001 | PREAMP-001 | mic_preamp | response_acquisition | RESEARCH_MINIMUM | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| FORCE-RM-001 | FORCE-001 | force_transducer | force_measurement | RESEARCH_MINIMUM | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | FUTEK direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| PRECOND-RM-001 | PRECOND-001 | force_conditioner | force_measurement | RESEARCH_MINIMUM | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | FUTEK direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| SHAKER-RM-001 | SHAKER-001 | shaker | contact_excitation | RESEARCH_MINIMUM | 1 | 1500.00 | 1500.00 | USED_MARKET_SINGLE_UNIT | UNKNOWN | Next Day Automation (used) | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| AMP-RM-001 | AMP-001 | amplifier | contact_excitation | RESEARCH_MINIMUM | 1 | UNKNOWN | UNKNOWN | USED_MARKET | UNKNOWN | used instrumentation market | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| STINGER-RM-001 | STINGER-001 | stinger | contact_excitation | RESEARCH_MINIMUM | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| TIP-RM-001 | TIP-001 | contact_tip | contact_excitation | RESEARCH_MINIMUM | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| STAND-RM-001 | STAND-001 | stand_base | mechanical_support | RESEARCH_MINIMUM | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| REF-RM-001 | REF-STRUCT-001 | reference_structure | mechanical_support | RESEARCH_MINIMUM | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| CABLE-RM-001 | CABLE-001 | cabling | interconnect | RESEARCH_MINIMUM | 1 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| HOST-PE-001 | HOST-001 | host | synchronized_acquisition | PREFERRED_E1 | 1 | 175.00 | 175.00 | IN_STOCK | ships from US reseller | PiShop.us | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| ADC-PE-001 | ADC-001 | adc_interface | synchronized_acquisition | PREFERRED_E1 | 1 | 64.90 | 64.90 | IN_STOCK_SUPERSEDED | not stated | HiFiBerry direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| MIC-PE-001 | MIC-001 | microphone | response_acquisition | PREFERRED_E1 | 1 | 549.00 | 549.00 | IN_STOCK | not stated | Sweetwater | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| PREAMP-PE-001 | PREAMP-001 | mic_preamp | response_acquisition | PREFERRED_E1 | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| FORCE-PE-001 | FORCE-001 | force_transducer | force_measurement | PREFERRED_E1 | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | PCB Piezotronics direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| PRECOND-PE-001 | PRECOND-001 | force_conditioner | force_measurement | PREFERRED_E1 | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | PCB Piezotronics direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| SHAKER-PE-001 | SHAKER-001 | shaker | contact_excitation | PREFERRED_E1 | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | Hottinger Bruel & Kjaer direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| AMP-PE-001 | AMP-001 | amplifier | contact_excitation | PREFERRED_E1 | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | Hottinger Bruel & Kjaer direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| STINGER-PE-001 | STINGER-001 | stinger | contact_excitation | PREFERRED_E1 | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | Hottinger Bruel & Kjaer direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| TIP-PE-001 | TIP-001 | contact_tip | contact_excitation | PREFERRED_E1 | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| STAND-PE-001 | STAND-001 | stand_base | mechanical_support | PREFERRED_E1 | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| REF-PE-001 | REF-STRUCT-001 | reference_structure | mechanical_support | PREFERRED_E1 | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| CABLE-PE-001 | CABLE-001 | cabling | interconnect | PREFERRED_E1 | 1 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| HOST-RG-001 | HOST-001 | host | synchronized_acquisition | REFERENCE_GRADE | 1 | 175.00 | 175.00 | IN_STOCK | ships from US reseller | PiShop.us | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| ADC-RG-001 | ADC-001 | adc_interface | synchronized_acquisition | REFERENCE_GRADE | 1 | 64.90 | 64.90 | IN_STOCK_SUPERSEDED | not stated | HiFiBerry direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| MIC-RG-001 | MIC-001 | microphone | response_acquisition | REFERENCE_GRADE | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | GRAS Sound & Vibration direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| FORCE-RG-001 | FORCE-001 | force_transducer | force_measurement | REFERENCE_GRADE | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | PCB Piezotronics direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| PRECOND-RG-001 | PRECOND-001 | force_conditioner | force_measurement | REFERENCE_GRADE | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | PCB Piezotronics direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| SHAKER-RG-001 | SHAKER-001 | shaker | contact_excitation | REFERENCE_GRADE | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | Hottinger Bruel & Kjaer direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| AMP-RG-001 | AMP-001 | amplifier | contact_excitation | REFERENCE_GRADE | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | Hottinger Bruel & Kjaer direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| STINGER-RG-001 | STINGER-001 | stinger | contact_excitation | REFERENCE_GRADE | 1 | QUOTE_REQUIRED | QUOTE_REQUIRED | QUOTE_REQUIRED | UNKNOWN | Hottinger Bruel & Kjaer direct | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| TIP-RG-001 | TIP-001 | contact_tip | contact_excitation | REFERENCE_GRADE | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| STAND-RG-001 | STAND-001 | stand_base | mechanical_support | REFERENCE_GRADE | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| REF-RG-001 | REF-STRUCT-001 | reference_structure | mechanical_support | REFERENCE_GRADE | 1 | UNKNOWN | UNKNOWN | FABRICATED | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |
| CABLE-RG-001 | CABLE-001 | cabling | interconnect | REFERENCE_GRADE | 1 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 2026-08-25 | HOLD | CONFIRMED_ABSENT |

**Reference grade has no `mic_preamp` row, and that is correct.** Its microphone
is CCP-powered and is conditioned by the four-channel ICP conditioner that also
serves the force sensor. The 48 V phantom preamp is not in that chain at all.

### Candidate specifications and technical sources

Every technical claim here traces to a manufacturer document in
[the datasheet manifest](TTP_E1_DATASHEET_MANIFEST.json). Distributor pages
established the prices above and establish nothing below.

| spec_for | manufacturer | model | powering | key_specification | interface_to_adc | technical_source |
| --- | --- | --- | --- | --- | --- | --- |
| HOST-RM-001 | Raspberry Pi | Raspberry Pi 5 8GB | 5 V DC supply | 64-bit Pi OS, 40-pin GPIO carrying I2S | not applicable — carries the ADC | Raspberry Pi 5 product documentation |
| ADC-RM-001 | HiFiBerry | DAC+ ADC Pro | from Pi 40-pin header | 2.1 Vrms max unbalanced, -12 to +32 dB input gain, 44.1-192 kHz, 24-bit, 110 dB SNR, no anti-alias filter | is the ADC; ch0 force, ch1 microphone | HiFiBerry DAC+ ADC Pro datasheet |
| MIC-RM-001 | Dayton Audio | EMM-6 | 48 V phantom | Electret measurement microphone, per-unit calibration file keyed to serial number | via mic_preamp to ch1 | Dayton Audio EMM-6 product documentation |
| PREAMP-RM-001 | custom build | OPA1612 balanced mic preamp | mains or DC supply | 48 V phantom, unbalanced line out | RCA to ch1 | TTP stack specification Stage 2 |
| FORCE-RM-001 | FUTEK | LSB200 miniature S-Beam, 1 kgf class | bridge excitation from conditioner | Strain gauge, DC-capable, ships with calibration certificate. Capacity must be selected to cover the exciter's 10 N | via bridge conditioner to ch0 | FUTEK LSB200 product documentation |
| PRECOND-RM-001 | FUTEK | IAA100 | 5 or 10 VDC bridge excitation | Full-bridge strain gauge voltage amplifier, ±5 or ±10 VDC output, 256 DIP-selectable gain combinations, up to 25 kHz bandwidth | gain set to land inside 2.1 Vrms; DC blocked by the AC-coupled input | FUTEK IAA100 product documentation |
| SHAKER-RM-001 | Bruel & Kjaer | Type 4810 | mains via amplifier | 10 N sine peak, DC-18 kHz, 18 g moving mass, 3.5 ohm coil at 500 Hz, 1.8 A rms max, 10-32 UNF table thread | drive path only | B&K Mini-shaker Type 4810 Product Data BP 0232-16 |
| AMP-RM-001 | Bruel & Kjaer | Type 2718 | 120 V / 60 Hz mains | 75 VA into 3 ohm, 10 Hz-20 kHz ±0.5 dB, 40 dB gain, current limit 1-5 A rms; limit to 1.8 A for the 4810 | drive path only; input AC-coupled via 10 uF | B&K Power Amplifier Type 2718 Product Data BP-1928 |
| STINGER-RM-001 | fabricated | 10-32 threaded piano-wire stinger | none | Axially stiff, laterally compliant; mass measured not assumed | mechanical only | TTP E1 hardware requirements |
| TIP-RM-001 | fabricated | contact tip | none | Documented geometry, measurable mass, replaceable | mechanical only | TTP E1 hardware requirements |
| STAND-RM-001 | fabricated | grounded stand and base | none | Reaction path to base independent of specimen support | mechanical only | TTP E1 hardware requirements |
| REF-RM-001 | fabricated | plate-scale reference structure | none | Inexpensive, stable, replaceable | mechanical only | TTP E1 hardware requirements |
| CABLE-RM-001 | assorted | sensor, RCA, XLR and drive cabling | none | Per the interface matrix | carries every electrical interface | TTP E1 interface matrix |
| HOST-PE-001 | Raspberry Pi | Raspberry Pi 5 8GB | 5 V DC supply | As HOST-RM-001 | not applicable — carries the ADC | Raspberry Pi 5 product documentation |
| ADC-PE-001 | HiFiBerry | DAC+ ADC Pro | from Pi 40-pin header | As ADC-RM-001 | is the ADC; ch0 force, ch1 microphone | HiFiBerry DAC+ ADC Pro datasheet |
| MIC-PE-001 | Earthworks Audio | M23 G2 | 24-48 V phantom, 10 mA | Omnidirectional measurement microphone to 23 kHz | via mic_preamp to ch1 | Earthworks M23 datasheet |
| PREAMP-PE-001 | custom build | OPA1612 balanced mic preamp | mains or DC supply | As PREAMP-RM-001 | RCA to ch1 | TTP stack specification Stage 2 |
| FORCE-PE-001 | PCB Piezotronics | 208C01 | IEPE, 18-30 VDC at 2-20 mA | 112.41 mV/N, ±44.48 N range, 0.01 Hz to 36 kHz, 22.7 g, 10-32 female both ends, 1.05 kN/um stiffness, 0.45 mN broadband resolution | via ICP conditioner to ch0 | PCB 208C01 spec sheet Rev K |
| PRECOND-PE-001 | PCB Piezotronics | 480C02 | internal 9 V battery | Unity gain ±2%, 0.05 Hz to 500 kHz, 3.25 uV rms broadband noise, supplies 25-29 VDC at 2.0-3.2 mA | BNC out to RCA, ch0 | PCB 480C02 spec sheet Rev P |
| SHAKER-PE-001 | Bruel & Kjaer | Type 4810 | mains via amplifier | As SHAKER-RM-001 | drive path only | B&K Mini-shaker Type 4810 Product Data BP 0232-16 |
| AMP-PE-001 | Bruel & Kjaer | Type 2718 | 120 V / 60 Hz mains | As AMP-RM-001 | drive path only | B&K Power Amplifier Type 2718 Product Data BP-1928 |
| STINGER-PE-001 | Bruel & Kjaer | 10-32 UNF stinger stock, 50 mm | none | Supplied as an accessory family to the 4810; 10-32 UNF matches the transducer | mechanical only | B&K Mini-shaker Type 4810 Product Data BP 0232-16 |
| TIP-PE-001 | fabricated | contact tip | none | As TIP-RM-001 | mechanical only | TTP E1 hardware requirements |
| STAND-PE-001 | fabricated | grounded stand and base | none | As STAND-RM-001 | mechanical only | TTP E1 hardware requirements |
| REF-PE-001 | fabricated | plate-scale reference structure | none | As REF-RM-001 | mechanical only | TTP E1 hardware requirements |
| CABLE-PE-001 | assorted | sensor, RCA, XLR and drive cabling | none | Includes 10-32 coaxial to BNC sensor cable | carries every electrical interface | TTP E1 interface matrix |
| HOST-RG-001 | Raspberry Pi | Raspberry Pi 5 8GB | 5 V DC supply | As HOST-RM-001 | not applicable — carries the ADC | Raspberry Pi 5 product documentation |
| ADC-RG-001 | HiFiBerry | DAC+ ADC Pro | from Pi 40-pin header | As ADC-RM-001 | is the ADC; ch0 force, ch1 microphone | HiFiBerry DAC+ ADC Pro datasheet |
| MIC-RG-001 | GRAS Sound & Vibration | 46AE | CCP/IEPE, 4 mA at 24 V | 1/2 inch CCP free-field standard microphone set | via the ICP conditioner to ch1 — NOT via the phantom preamp | GRAS 46AE datasheet |
| FORCE-RG-001 | PCB Piezotronics | 208C01 with calibration certificate option | IEPE, 18-30 VDC at 2-20 mA | As FORCE-PE-001, ordered with a traceable calibration certificate | via ICP conditioner to ch0 | PCB 208C01 spec sheet Rev K |
| PRECOND-RG-001 | PCB Piezotronics | 482C05 | 120 V / 60 Hz mains | Four-channel ICP conditioner, unity gain ±1% at 500 Hz, ±10 V output, <0.1 Hz to >1000 kHz. Conditions force and the CCP microphone from one chassis | BNC out to RCA, ch0 and ch1 | PCB 482C05 manual Rev J |
| SHAKER-RG-001 | Bruel & Kjaer | Type 4810 | mains via amplifier | As SHAKER-RM-001. Not upgraded: 10 N already exceeds plate-scale need, and a larger exciter would worsen the level budget | drive path only | B&K Mini-shaker Type 4810 Product Data BP 0232-16 |
| AMP-RG-001 | Bruel & Kjaer | Type 2718 | 120 V / 60 Hz mains | As AMP-RM-001 | drive path only | B&K Power Amplifier Type 2718 Product Data BP-1928 |
| STINGER-RG-001 | Bruel & Kjaer | 10-32 UNF stinger stock, 50 mm | none | As STINGER-PE-001 | mechanical only | B&K Mini-shaker Type 4810 Product Data BP 0232-16 |
| TIP-RG-001 | fabricated | contact tip | none | As TIP-RM-001 | mechanical only | TTP E1 hardware requirements |
| STAND-RG-001 | fabricated | grounded stand and base | none | As STAND-RM-001 | mechanical only | TTP E1 hardware requirements |
| REF-RG-001 | fabricated | machined reference plate | none | Machined to documented geometry so the structure is reproducible rather than merely stable | mechanical only | TTP E1 hardware requirements |
| CABLE-RG-001 | assorted | sensor, RCA, XLR and drive cabling | none | As CABLE-PE-001 | carries every electrical interface | TTP E1 interface matrix |

### Tier totals — partial, and labelled as such

Totals cover only the rows carrying a numeric price. Unpriced rows are **not**
counted as zero, and a total that omits them is not a tier cost:

| Tier | Priced rows | Partial total (USD) | Unpriced rows | Of which quotation-based |
| --- | --- | --- | --- | --- |
| `RESEARCH_MINIMUM` | 4 of 13 | **1,799.88** | 9 | 2 |
| `PREFERRED_E1` | 3 of 13 | **788.90** | 10 | 5 |
| `REFERENCE_GRADE` | 2 of 12 | **239.90** | 10 | 6 |

A refurbished PCB 480C02 was observed at $370.39 (WiAutomation, checked
2026-08-25). It is deliberately **not** in the preferred-tier total: that tier is
priced as new equipment, and a single refurbished unit from a reseller is a
different commercial fact. It is recorded here because it bounds what the
conditioner costs, not because it is the quoted price of the preferred chain.

**These are not tier costs and must not be quoted as such.** Every tier's
dominant cost — the force transducer and its conditioner, and for two tiers the
exciter and amplifier — sits in the unpriced group, because PCB Piezotronics,
Hottinger Brüel & Kjær, GRAS and FUTEK all quote rather than publish. A
meaningful tier cost requires quotations, and obtaining quotations is a
procurement activity that this order does not authorize.

The one exception worth noting: `RESEARCH_MINIMUM` shows a *higher* partial
total than `PREFERRED_E1`, purely because its exciter was found on the used
market with a public asking price while the preferred tier's identical exciter
is quotation-based when new. That is an artifact of what happens to be
published, and it is exactly why these totals cannot rank the tiers.

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
