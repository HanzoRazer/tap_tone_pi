# DO-108P — Commercial Excitation Output Stage / PCB Envelope

## Status

**COMPLETE — documents, candidate registration, utility and tests delivered.
The PCB layout gate closes `BLOCKED`, which is the expected outcome, not a
failure of this order.**

**Branch:** `feat/do-108p-excitation-output-stage`, cut independently from
`main`. DO-107B remains isolated and unmerged; nothing in this order depends on
its six commits, and none of them were pulled in.

## Objective

Establish the authoritative requirements for the commercial TTP excitation
output stage, and define the evidence required before a custom PCB is laid out.

This order **does not authorize PCB layout**, and deliberately ends with the
layout gate closed.

## Governing physical architecture

```text
TTP ANALYZER -> DAC / ANALOG OUTPUT -> INTERNAL POWER AMPLIFIER
             -> ELECTRODYNAMIC EXCITER -> LIGHT STINGER / CONTACT TIP
             -> GUITAR PLATE -> MICROPHONE -> ADC -> TTP ANALYZER
```

The amplifier is inside the TTP commercial stack. The expensive B&K / PCB
force-reference rig remains the research and reference configuration and is not
the baseline commercial architecture.

## Rulings this order was executed under

The original handoff proposed a parallel set of hardware documents with an
`EXC-*` candidate namespace and a second checker. Repository inspection found
that authority already exists, and the handoff was corrected before
implementation. The rulings, as given:

1. **Extend E1; do not create a parallel commercial hardware authority.** The
   existing identity register, BOM, four-axis model, datasheet manifest and
   checker own this physical role. No competing `EXC-*` namespace.
   `SHAKER-*` is awkward terminology for a commodity exciter; duplicate
   authority is worse, and renaming that namespace is a separate migration.
2. **Reuse the existing four independent axes.** No new
   `selection_status`/`bench_status` semantics overlapping E1. Candidates begin
   unselected, unacquired, compatibility unresolved, ownership per evidence.
   `SELECTION_DEFERRED` remains the governing selection ruling.
3. **Use the existing datasheet provenance policy.** Retrieve the
   manufacturer-hosted documents and digest the retrieved bytes. No second
   provenance mechanism; local copies are orientation, not identity.
4. **Do not create or cherry-pick `ANALYZER_CAPABILITY_MATRIX.md.`** It belongs
   to unmerged technical-manual work. Record the capability dependency locally
   and reconcile when that work lands.
5. **Enclosure state per physical truth.** No enclosure exists, so
   `ENCLOSURE_NOT_AVAILABLE_FOR_MEASUREMENT`, not `NOT_PERFORMED`. Missing
   enclosure measurement blocks the PCB gate only; the rest of the order
   proceeds.
6. **Branch from `main`.**
7. **Repository ADR convention wins:** `docs/ADR-0014-excitation-pcb-gate.md`,
   not a new `docs/decisions/` directory.
8. **Create the order record; repair bookkeeping conservatively.** Do not
   retroactively declare DO-107B merged because a working branch contains it.

Two corrections raised during grounding were also approved: load compatibility
covers both 4 Ω and 8 Ω rather than rewriting the VISATON candidate to match the
Dayton-derived requirement, and the drive-budget utility lives in `scripts/`
alongside the hardware-governance tools rather than in runtime excitation code.

## Authority relationship

```text
E1 HARDWARE SYSTEM
        │
        ├── identity register     <- component identity
        ├── BOM                   <- candidates / tiers / four axes
        ├── datasheet manifest    <- source provenance
        └── checker               <- governance enforcement
                 │
                 ▼
DO-108P SUPPORTING DOCUMENTS
        │
        ├── commercial architecture
        ├── amplifier requirements
        ├── enclosure constraints
        └── bench protocol
```

## What was delivered

**Extended (E1 authority):**

- `docs/hardware/TTP_E1_HARDWARE_BOM.md` — `COMMERCIAL_PROTOTYPE` tier,
  six candidate rows and their specification rows, tier-totals entry.
- `docs/hardware/TTP_E1_HARDWARE_IDENTITY_REGISTER.md` — no new row, and the
  reasoning for that, plus the `SHAKER-002` rule if both architectures are ever
  possessed at once.
- `docs/hardware/TTP_E1_DATASHEET_MANIFEST.json` — four retrieved documents with
  digests over the manufacturer-served bytes.
- `scripts/check_e1_hardware_bom.py` — scoped tiers, tier-scope enforcement,
  datasheet coverage for the commercial tier, and DO-108P document validation.
- `tests/test_e1_hardware_bom.py` — existing whole-chain assumptions made
  explicit; new coverage for the scoped tier and the committed commercial rows.

**Created (supporting documents):**

- `docs/hardware/TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md`
- `docs/hardware/TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md`
- `docs/hardware/TTP_EXCITATION_PCB_ENVELOPE.md`
- `docs/hardware/TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md`
- `docs/ADR-0014-excitation-pcb-gate.md`
- `scripts/exciter_drive_budget.py`, `tests/test_exciter_drive_budget.py`

## Registered candidates

All under the existing role namespace. None selected, none owned, none priced.

| candidate | role | device | source |
| --- | --- | --- | --- |
| `SHAKER-CP-001` | `SHAKER-001` | Dayton Audio DAEX25CT-4 | manufacturer spec sheet, digest recorded |
| `SHAKER-CP-002` | `SHAKER-001` | Dayton Audio DAEX25FHE-4 | manufacturer spec sheet, digest recorded |
| `SHAKER-CP-003` | `SHAKER-001` | VISATON EX 30 S | manufacturer data sheet, digest recorded |
| `AMP-CP-001` | `AMP-001` | TI TPA3116D2 / TPA3118D2 family | SLOS708G, digest recorded |
| `STINGER-CP-001` | `STINGER-001` | fabricated | TTP architecture |
| `TIP-CP-001` | `TIP-001` | fabricated | TTP architecture |

All four retrieved documents were byte-identical to the operator's local copies,
recorded per entry as a cross-check rather than as identity.

## Acceptance

| Criterion | State |
| --- | --- |
| Excitation electrical requirements defined, with unmeasured values marked | met — every output figure reads `TBD_MEASURE` |
| Exciter candidates normalized, distinguishing specification from unknown | met — VISATON's absent BL/Mms/Fs stay absent |
| Mechanical/enclosure envelope specified | met — and recorded as physically unavailable |
| Bench characterization protocol defined | met — P0–P9, `NOT_EXECUTED` |
| Validation and arithmetic utility | met — checker extended, calculator added |
| PCB layout not begun | met — no schematic, no layout, no Gerbers |
| Layout gate verdict | `BLOCKED` |

## Explicitly out of scope, and untouched

Production schematic or layout; Gerber generation; procurement authorization;
final TPA3116D2 selection; final power-supply selection; B&K 4810 integration;
PCB 208C01 integration; dynamic force-channel implementation; brace mathematics;
`alpha_beta.py`; microphone preamp redesign; E0 execution; Viewer Pack changes;
agentic features; grant-writing changes.

`alpha_beta.py` is clean and committed on `main`, so the dirty-tree concern in
the original handoff no longer applies. It was not touched regardless; its
provenance is irrelevant to this order.

## What unlocks the next order

**DO-108B — TTP Excitation Bench Qualification** begins when there is one TTP
Analyzer, a temporary amplifier or prototype amp, at least the CT and FHE
exciters, a fixture, a stinger, a microphone and a representative plate. It
executes the characterization protocol and establishes the actual output
envelope.

**DO-108C — TTP Custom Excitation PCB Design** follows, and only then, with real
numbers for enclosure dimensions, load, required continuous and short-duration
output, supply, gain, hardware ceiling, EMI strategy and control lines.

DO-108P and DO-108B exist so those numbers are measured rather than invented.
