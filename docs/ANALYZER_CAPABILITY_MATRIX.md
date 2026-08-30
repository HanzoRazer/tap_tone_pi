# TTP Analyzer — Capability Matrix

**Status:** census only. **Dev Order:** TTP-TECH-MANUAL-001, Commit 1.

This document records **what the analyzer can actually do today**, established by
reading the repository rather than by reading its documentation. It is the hard
gate for TTP-TECH-MANUAL-001: no operator workflow is written until the
capability behind it appears here with a maturity classification and a hardware
disposition.

**This is not a manual and not a procedure.** It tells a reader what exists and
how far it has been established. It does not tell anyone how to measure
anything. Operator instructions live in
[the Analyzer User Guide](ANALYZER_USER_GUIDE.md); governed laboratory
procedures live in the packaged
[Laboratory Manual](../tap_tone_pi/acoustic_lab/manual/README.md) and nowhere
else.

---

## The axes are independent

Four different questions get asked about any capability, and they have four
different answers. Collapsing them is the failure this document exists to
prevent.

| Axis | Vocabulary | Answers the question |
|---|---|---|
| **Capability maturity** | `IMPLEMENTED` · `EXPERIMENTAL` · `PLANNED` · `EXTERNAL` | Does the software exist? |
| **Epistemic status** of outputs | [ADR-0012](ADR-0012-epistemic-status-taxonomy.md): Observed · Derived · Estimated · Predicted · Heuristic · Operator-Annotated · Externally-Sourced | What kind of claim is the output? |
| **Laboratory manual status** | `approved` · `provisional` · `deferred` · `superseded` | Has a procedure earned governance? |
| **Hardware disposition** | E1 register: `CONFIRMED_PRESENT` · `CONFIRMED_ABSENT`; or **not tracked** | Does the equipment exist? |

Only the first is new. The others are the repository's existing vocabularies,
reused rather than re-coined.

### The invariant

> **`IMPLEMENTED` does not imply `approved`.**

Working code is not a validated procedure. A fully functional, well-tested
analysis module may have **no approved laboratory procedure at all**, and that
is a normal state rather than a defect.

This is not a new rule. It is [ADR-0012](ADR-0012-epistemic-status-taxonomy.md)'s
core invariant — *"No epistemic state may silently inherit another state's
authority"* — applied to a further axis. Implementation authority, epistemic
authority, procedural authority and physical availability are four
authorities, and none of them confers another.

The corollary matters just as much: **hardware absence does not lower capability
maturity.** Software that is `IMPLEMENTED` stays `IMPLEMENTED` when the rig to
exercise it does not exist. What changes is whether an operator can run it
today, which is why executability is recorded separately below.

### Maturity definitions

| Value | Means |
|---|---|
| `IMPLEMENTED` | Module exists in the package and is exercised by the test suite. **Coverage depth is not asserted** — it ranges from one importing test module to ten. Says nothing about hardware, procedure or validation |
| `EXPERIMENTAL` | Exists but is under evaluation, carries an open authority question, or is explicitly marked provisional in its own source |
| `PLANNED` | Architecturally established and referenced by shipped contracts, but not implemented |
| `EXTERNAL` | Belongs to another system. TTP may consume or hand off, but does not own it |

---

## Capability census

`Reach` records how an operator gets at a capability: `CLI` for a `ttp`
subcommand, `GUI` for the desktop analyzer, `LIB` for importable-only.
A `LIB`-only capability is not operator-facing today whatever its maturity.

| Capability | Canonical implementation | Maturity | Reach | Output epistemic status | Manual status |
|---|---|---|---|---|---|
| Audio capture and device selection | `tap_tone_pi/gui/`, `core/auto_trigger.py` | `IMPLEMENTED` | CLI `devices`, `live` | Observed | none |
| FFT / spectral analysis | `chladni/peaks_from_wav.py` | `IMPLEMENTED` | CLI `peaks`, GUI | Derived | none |
| Peak / resonance identification | `chladni/peaks_from_wav.py`, `a0/peak_detection.py` | `IMPLEMENTED` | CLI `peaks`, GUI | Derived | none |
| Frequency tolerance policy | `chladni/policy.py` | `IMPLEMENTED` | LIB | Derived | none |
| Chladni pattern indexing | `chladni/index_patterns.py` | `IMPLEMENTED` | CLI `chladni`, GUI | Derived | none |
| Transfer function / FRF | `transfer_function/` (5 files, ~1970 lines) | `IMPLEMENTED` | GUI (Bode), LIB | Derived | none |
| Coherence | `phase2/coherence_gate.py`, `transfer_function/quality.py` | `IMPLEMENTED` | CLI `phase2`, GUI | Derived | none |
| Damping / Q estimation | `damping/modes.py`, `damping/extraction.py` | `IMPLEMENTED` | LIB | Derived | none |
| ODS / roving-grid scanning | `phase2/`, `scripts/phase2/` | `IMPLEMENTED` | CLI `phase2` | Derived | none |
| Wolf-tone detection | `wolf/wolf_beat.py` | `IMPLEMENTED` | LIB | Derived | none |
| Controlled excitation — stepped sweep | `excitation/stepped_sweep.py` | `IMPLEMENTED` | LIB | Observed | none |
| Controlled excitation — known tone | `excitation/known_tone.py` | `IMPLEMENTED` | LIB | Observed | none |
| Excitation source characterization | `excitation/source_characterization.py` | `IMPLEMENTED` | LIB | Derived | none |
| Signal generation | `signal_gen/generators.py`, `waveforms.py` | `IMPLEMENTED` | LIB | Observed | none |
| Bending stiffness / MOE | `bending/` (7 files, ~3978 lines) | `IMPLEMENTED` | CLI `bending` | Derived | none |
| GUM uncertainty budgets | `uncertainty/` (7 files, ~2523 lines) | `IMPLEMENTED` | LIB | Estimated | none |
| Acquisition uncertainty budget | `uncertainty/acquisition/` | `EXPERIMENTAL` | LIB | Estimated | none |
| Multi-tap statistics | `multitap/` (4 files, ~1817 lines) | `IMPLEMENTED` | LIB | Derived | none |
| Rayleigh–Ritz plate solver | `design/rayleigh_ritz.py` | `IMPLEMENTED` | LIB | Predicted | none |
| Orthotropic thickness calculation | `design/thickness_calculator.py` | `IMPLEMENTED` | LIB | Predicted | none |
| Inverse material solving | `design/inverse_solver.py` | `IMPLEMENTED` | LIB | Estimated | none |
| Mode shape rendering | `design/mode_shape_render.py` | `IMPLEMENTED` | LIB | Predicted | none |
| Coupled two-oscillator model | `design/coupled_2osc.py` | `IMPLEMENTED` | LIB | Predicted | none |
| Helmholtz / A0 air mode | `a0/` (4 files) | `IMPLEMENTED` | LIB | Predicted | none |
| Calibration — loopback | `calibration/loopback.py` | `IMPLEMENTED` | LIB | Observed | none |
| Calibration — reference tone | `calibration/reference_tone.py` | `IMPLEMENTED` | LIB | Observed | none |
| FR compensation | `calibration/compensation.py` | `IMPLEMENTED` | LIB | Derived | none |
| Material / wood database | `materials/wood_db.py` | `IMPLEMENTED` | LIB | Externally-Sourced | none |
| Build records | `materials/build_record.py`, `provenance/build_session.py` | `IMPLEMENTED` | LIB | Operator-Annotated | none |
| Provenance and environment capture | `provenance/` (10 files, ~1882 lines) | `IMPLEMENTED` | LIB | Observed | none |
| Empirical model framework | `empirical/` (8 files, ~2108 lines) | `IMPLEMENTED` | LIB | Estimated | none |
| Experiment planning | `experiment/` (12 files, ~2547 lines) | `IMPLEMENTED` | LIB | Predicted | none |
| Session indexing and browsing | `cli/`, `gui/session_browser.py` | `IMPLEMENTED` | CLI `sessions`, `index`, `last` | Observed | none |
| Viewer Pack export | `viewer_pack/`, `scripts/phase2/` | `IMPLEMENTED` | LIB | Derived | none |
| Laboratory Manual viewer | `analyzer/widgets/laboratory_manual_view.py` | `IMPLEMENTED` | GUI | — | registry empty |

**Every row reads `none` under manual status.** `manual_manifest.json` registers
zero entries, deliberately, and this order does not change that. No capability
in this repository currently has a governed laboratory procedure.

---

## Findings requiring separate review

Recorded here rather than acted on. Neither is resolved by this order, and
neither is ratified by continuing to exist.

### F-1 — Wood property grading in the User Guide

[ANALYZER_USER_GUIDE.md](ANALYZER_USER_GUIDE.md) carries a **Wood Property
Grading** section. [ADR-0009](ADR-0009-advisory-boundary.md) names
`analyzer/analysis/wood_properties.py` as an **advisory-class** module,
alongside `wolf/wolf_advisor.py` and `AnalyzerGuidanceEngine`, and both of those
modules sit outside the `# INSTRUMENT CLASS:` marker scheme that the 219
measurement modules and 35 decision modules carry.

Whether grading *wood* falls inside
[MEASUREMENT_BOUNDARY.md](MEASUREMENT_BOUNDARY.md) — which prohibits grading
*instruments* — is a live question this census does not answer.

**Disposition:** preserved unchanged. Its continued presence is not a new
scientific endorsement, and reorganizing the guide around it must not be read as
one. Flagged as **existing operator-guide content requiring separate boundary
review**.

### F-2 — Hardware availability is unestablished outside the E1 register

The [E1 hardware census](hardware/TTP_E1_HARDWARE_BOM.md) established ownership
for **E1 roles only**. One role is `CONFIRMED_PRESENT` (a Raspberry Pi 5);
every other E1 role is `CONFIRMED_ABSENT` with procurement on `HOLD`.

That census does not speak to ordinary equipment. Basic tap analysis needs *a*
microphone and *an* audio input, not *the E1* microphone, and no register
records whether such equipment is on hand. **Absence from the E1 register is not
evidence of absence**, and it is equally not evidence of presence.

**Disposition:** executability for workflows depending on untracked general
equipment is recorded below as `UNRESOLVED`, not as `NO`. Establishing it
requires the same kind of physical observation DO-104R required, which only the
operator can supply.

---

## Executability

Software maturity and hardware disposition combine into one operator-facing
question: **can this be performed today?** Per D-10 as amended, a workflow that
cannot be performed gets a gap record here and **no operator chapter**.

| Candidate workflow | Software | Required hardware | Executable today | Disposition |
|---|---|---|---|---|
| Basic Tap Analysis | `IMPLEMENTED` | microphone + audio input, **not tracked** | `UNRESOLVED` (F-2) | Chapter authorized once equipment is established |
| Spatial Modal Analysis (ODS) | `IMPLEMENTED` | 2-channel input + roving fixture, **not tracked** | `UNRESOLVED` (F-2) | As above |
| Material Characterization — bending | `IMPLEMENTED` | bending rig, dial indicator, load cell, **not tracked** | `UNRESOLVED` (F-2) | As above |
| Plate prediction (Rayleigh–Ritz, thickness, inverse) | `IMPLEMENTED` | **none** — computation only | **YES** | Chapter authorized |
| Assembled-instrument modelling (A0, coupled modes) | `IMPLEMENTED` | none for prediction; measurement needs capture | **YES** for prediction | Chapter authorized, prediction scope only |
| Controlled *contact* modal analysis | `IMPLEMENTED` | E1 shaker, stinger, force transducer, conditioner — all `CONFIRMED_ABSENT`, procurement `HOLD` | **NO** | **Gap record only. No chapter.** |
| Research and calibration | `IMPLEMENTED` | loopback needs an audio interface, **not tracked** | `UNRESOLVED` (F-2) | Partially authorized; computation-only parts executable |
| Empirical build record | `IMPLEMENTED` | none — records and models | **YES** | Chapter authorized |

### Gap record — controlled contact modal analysis

```
Controlled Modal Analysis (contact excitation)
    software support:    IMPLEMENTED
                         excitation/stepped_sweep.py, known_tone.py,
                         source_characterization.py, transfer_function/,
                         phase2/coherence_gate.py
    required hardware:   absent (E1 chain, procurement on HOLD)
    executable workflow: NO
    governed procedure:  none
    disposition:         capability/gap record only
```

The software is genuinely there and genuinely capable. What is absent is the
physical chain, and no operator chapter may describe performing a measurement
the equipment cannot perform. When the hardware exists and a procedure has
actually been developed, that procedure may enter the governed Laboratory Manual
at whatever status its evidence supports — which is a separate action with its
own evidentiary burden, not a consequence of this document.

**Absolute mobility is not claimed anywhere.** Transfer-function mathematics
existing does not establish a calibrated force measurement chain, and no
force measurement chain exists to calibrate.

---

## What this census did not establish

- Whether any workflow marked `UNRESOLVED` is executable. That needs a physical
  observation, not a repository reading.
- Whether the wood property grading section belongs inside the measurement
  boundary (F-1).
- Any procedure. Nothing here is validated, and nothing here is approved.
- Anything about systems outside this repository. The Luthier Acoustics
  Laboratory retains empirical research authority; this document neither
  describes nor constrains it.
