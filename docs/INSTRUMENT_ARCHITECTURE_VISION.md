# TTP Analyzer — Instrument Architecture Vision

**Status:** Position statement — informational, not normative
**Date:** 2026-08-01
**Revision:** 1.2 — separated implemented capability from architectural direction;
aligned status vocabulary with ADR-0012; corrected the repository-structure and
Laboratory Manual sections against the repository as it actually stands.
Earlier: 1.1 — added the Electrical / Hardware Stack section. 1.0 — initial.
**Related:** ADR-0001, ADR-0011, ADR-0012, `docs/hardware/TTP_HARDWARE_STACK.md`

---

## What this document is, and is not

This is a **position statement**. It records the architectural direction that has
emerged as the project matured, so that direction is legible to contributors and
stable across sessions.

It is **not an architectural decision record**. The ADR series lives at
`docs/ADR-NNNN-*.md` and currently runs to ADR-0012; nothing here supersedes,
amends, or carries the authority of any ADR. Where this document and an ADR
disagree, the ADR governs. Whether this material should be promoted into the ADR
series is an open question for the maintainer, not something this document
settles for itself.

It is also **not a roadmap**. Nothing here commits the project to a schedule, to
a specific implementation, or to building any particular hardware.

### Status vocabulary

ADR-0012 establishes a core invariant for measurement data:

> No epistemic state may silently inherit another state's authority.

The same discipline applies to architecture documents. A described architecture
must not silently inherit the authority of an implemented one. Every substantive
section below therefore carries one of three tags:

| Tag | Meaning |
|---|---|
| **Implemented** | Present in this repository today and exercised by tests. |
| **Direction** | Accepted architectural intent. Partially realized or not yet realized. |
| **Target** | A long-term aim. Not committed to, and not scheduled. |

An untagged statement is descriptive prose, not a capability claim.

---

## Executive summary

**Direction.**

The Tap-Tone-Pi (TTP) Analyzer began as a tap-tone analysis application. The
architectural direction the project has settled into is broader: a **low-cost
desktop acoustic measurement instrument** intended to serve education, laboratory
experimentation, workshop measurement, and specialized luthiery workflows through
one common measurement platform.

The objective is to make disciplined acoustic measurement practice reachable at a
price point accessible to students, schools, small workshops, and independent
researchers. That is the aim the architecture is organized around; it is not a
claim about validated performance.

---

## Architectural evolution

### Phase 1 — Tap tone analyzer

**Implemented.**

Original purpose:

```text
Capture a tap.
Perform FFT.
Display frequency content.
```

The application functioned primarily as a digital tap analyzer.

### Phase 2 — Governed measurement platform

**Implemented**, with the qualifications noted below.

Capability was added across calibration, provenance, experiment design, campaign
management, controlled excitation, transfer-function measurement, variance
characterization, cohort regression, and empirical-formula support. These exist
as modules in the repository — `tap_tone_pi/calibration/`, `excitation/`,
`provenance/`, `experiment/`, `phase2/`, `luthiery/` among others — and are
covered by the test suite.

What that establishes is that the *software* implements these concerns. It does
not by itself establish measurement performance of any assembled unit; see
"Calibration and repeatability" below.

### Phase 3 — Desktop acoustic measurement instrument

**Direction.**

The architectural direction is no longer software alone. The intended instrument
comprises defined hardware, calibration procedures, governed software,
laboratory protocols, experiment management, and reporting — with the software as
one subsystem among them.

The repository currently contains the software subsystem and the hardware
*specification*. It does not contain evidence of built, calibrated, validated
units, and this document should not be read as asserting any.

---

## Electrical / hardware stack

**Direction.** The stack below is specified; it is the reference configuration,
not a closed architecture, and alternate converters or modular arrangements are
not excluded.

The intended physical foundation is a four-stage electrical signal chain, with
the software running on top of it rather than replacing it.

```text
[Mic] → [OPA1612 balanced mic-pre] → [HiFiBerry DAC+ ADC] → [Raspberry Pi 5] → [tap_tone_pi DSP]
```

| Stage | Element | Architectural role |
|---|---|---|
| 1 | Measurement microphone (SDC or dynamic, balanced XLR, 48V phantom) | Acoustic → electrical transduction |
| 2 | OPA1612 transparent preamp (3-position gain switch) | Low-noise, low-distortion gain staging into the ADC window |
| 3 | HiFiBerry DAC+ ADC Pro (24-bit, 2-channel, I²S) | Calibrated digitization; ch0 = reference, ch1 = roving (Phase 2) |
| 4 | Raspberry Pi 5 + tap_tone_pi | Signal generation, capture, DSP, provenance, export |

Two excitation modes share the one chain:

* **Phase 1 — impulse tap** (single channel): the operator taps the plate and the
  chain captures the free response.
* **Phase 2 — speaker-driven ODS** (two channel): the Pi is both source and sink,
  driving a speaker while capturing reference and roving mics, so the excitation
  level is known in software.

**Detailed reference.** The full electrical stack — component selection,
corrected gain-staging tables, calibration coverage, connector map, and the
prototype-vs-production BOM — is maintained in
[`docs/hardware/TTP_HARDWARE_STACK.md`](hardware/TTP_HARDWARE_STACK.md), which
describes itself as an authoritative design reference. This section is a summary;
that document governs the detail. When the two disagree, that document is
correct and this one is stale.

---

## Calibration and repeatability

This section is separated out because it carries the document's strongest claims,
and they need the most careful handling.

**Implemented:** a self-calibration loopback path (`signal_gen → DAC → preamp →
ADC → Pi`) exists in software at `tap_tone_pi/calibration/loopback.py`, alongside
frequency-response compensation, reference-tone handling, and calibration session
storage. Repeatability and uncertainty machinery exists under
`tap_tone_pi/bending/qa_lab_spec.py` (GUM) and in the repeatability and
variance modules.

**Direction:** that per-unit characterization is *applied to each assembled unit
before use*, bounding and recording amplitude offset, frequency response, latency,
and noise floor per unit. Per-unit calibration is the property the architecture
relies on to treat the platform as a measurement instrument rather than a
recording application — but it is a requirement the design is built around, not a
validated result this repository evidences.

**Not established here:** measurement accuracy figures, repeatability tolerances,
or validation criteria for any assembled unit. Where this document says
"repeatable" or "calibrated", read it as naming the property the architecture is
organized to support, not as a performance guarantee. Claims of that kind belong
with validation evidence, and should cite it.

---

## Instrument philosophy

**Direction.**

The TTP Analyzer is intended to support:

* repeatable measurement workflows
* provenance-aware data
* calibrated acquisition
* controlled excitation
* experiment documentation

It deliberately avoids making engineering recommendations or substituting for
scientific judgment. Its role is to measure and document, not to interpret. That
boundary is normative and is set by `docs/MEASUREMENT_BOUNDARY.md`, ADR-0009, and
ADR-0011 — not by this document.

---

## Desktop instrument tier

**Target.** These are intended use cases, not statements of readiness for
deployment in any of these settings.

The intended position is an affordable desktop acoustic measurement instrument
aimed at:

### Education

* technical colleges
* university laboratories
* STEM programs
* instrument-making schools
* classroom acoustic demonstrations

with students learning calibration, FFT analysis, transfer functions, experiment
documentation, repeatability, and uncertainty.

### Workshop

* individual luthiers
* repair shops
* prototype development
* small manufacturing environments

### Research

* controlled experimentation
* empirical model development
* repeatable measurement campaigns
* longitudinal studies

Whether the instrument is fit for any of these uses is a question for validation
evidence, not for this document.

---

## Core instrument platform

**Direction**, with most elements **Implemented** in software.

The core measurement platform is intentionally domain-neutral. The capability set
the architecture is organized around:

signal generation, FFT, spectral analysis, transfer functions, impulse response,
controlled excitation, calibration, dual-channel acquisition, experiment
management, provenance, measurement validation, and reporting.

Most of these exist as modules today. "Measurement validation" is the loosest
term in that list: the repository implements schema and contract validation, and
error-detection evidence around formula candidates — not validation of
measurement accuracy against a reference standard. The two should not be
conflated.

None of these capabilities are inherently specific to luthiery.

---

## Domain modules

**Direction.**

Specialized workflows are intended to be implemented as domain modules on the
core measurement platform — luthiery, material resonance studies, loudspeaker
characterization, general acoustics laboratories, mechanical vibration exercises.

Luthiery workflows are the primary reference implementation, and the only one
built. They are not the architectural definition of the platform.

---

## The Luthier Acoustics Laboratory

**Direction.**

The Luthier Acoustics Laboratory is currently treated as a subsystem of the TTP
Analyzer rather than a separate product. This is an architectural position, not a
packaging or distribution commitment; how the project is eventually packaged
remains open.

Its intended purpose is to provide an environment for developing and documenting
measurement methods before they become production workflows. Intended contents
include a laboratory manual, protocol library, fixture specifications,
experimental workflows, research projects, deferred concepts, and a promotion
queue.

Of these, only the laboratory manual registry exists today (see below).

---

## Laboratory Manual

**Direction**, with the registry **Implemented** and its content empty.

The Laboratory Manual is intended to function as an operational companion to the
instrument rather than as product documentation alone — closer in role to the
procedures supplied with laboratory equipment than to a user guide.

Intended coverage: operating procedures, calibration procedures, laboratory
protocols, experiment workflows, fixture requirements, measurement theory, safety
considerations, and validation procedures.

**Current state.** DO-97 delivered the packaging and the read-only registry at
`tap_tone_pi/acoustic_lab/`, with a maturity label per entry
(`approved` / `provisional` / `deferred` / `superseded`). The manifest ships
**empty** — `"entries": []` — by design: no consolidated manual document exists
yet, and fabricating one was ruled out. The list above describes what the manual
is intended to cover, not what it contains.

---

## Repository structure

**Direction.** The tree below is illustrative of the intended separation. It is
not a mandated layout and does not authorize a reorganization; migrating toward
it would need its own dev order.

The TTP Analyzer is currently a single repository, and the separation described
in this document is architectural rather than repository-based.

```text
tap_tone_pi/

    hardware/            (proposed — does not exist)
    calibration/         (exists)
    measurement/         (proposed — does not exist; DSP currently lives in
                          phase2/, chladni/, damping/, multitap/, wolf/)
    excitation/          (exists)
    provenance/          (exists)
    experiment/          (exists)
    reporting/           (proposed — does not exist)

    acoustic_lab/        (exists — currently the manual registry only)
        laboratory_manual/       (proposed)
        protocols/               (proposed)
        fixtures/                (proposed)
        experimental_workflows/  (proposed)
        research_projects/       (proposed)
        deferred_concepts/       (proposed)
        promotion_queue/         (proposed)
```

The annotations are accurate as of this document's date and will drift. The
repository is the authority on its own layout.

---

## Promotion pipeline

**Direction.** This describes the intended maturation path. It is not an enforced
gate, and the validation criteria it refers to are not yet defined.

```text
Observation
    ↓
Hypothesis
    ↓
Experimental Protocol
    ↓
Fixture Definition
    ↓
Pilot Measurements
    ↓
Repeatability
    ↓
Statistical Characterization
    ↓
Measurement Workflow Specification
    ↓
Production Measurement Workflow
```

The intent is that only validated measurement workflows are promoted into the
production measurement namespaces. "Validated" is doing real work in that
sentence and is not yet defined anywhere: establishing the criteria, and whatever
enforces them, is outstanding.

---

## Separation of responsibilities

**Direction.** The architecture distinguishes three responsibilities. The
separation is intent; it is not structurally enforced by the codebase today.

### Acoustic Laboratory — *Discover*

Develops protocols, experiments, and measurement methods.

### Measurement Platform — *Measure*

Executes measurement workflows with calibration, provenance, and repeatability.

### Application Layer — *Apply*

Uses measurements for domain-specific engineering, design, or educational
purposes.

The boundary that *is* enforced — that this repository measures and does not
advise — is set by `docs/MEASUREMENT_BOUNDARY.md`, ADR-0009, and
`ci/no_logic_creep.yml`, and is stricter than the three-way split described here.

---

## Long-term vision

**Target.**

The TTP Analyzer is envisioned as an affordable desktop acoustic measurement
instrument that brings disciplined measurement practice — calibration,
provenance, repeatability, stated uncertainty — into classrooms, workshops, and
research environments.

Its intended value is not defined by a single application domain, but by the
quality and repeatability of the measurements it is built to produce. Specialized
domains, luthiery included, are intended as workflow packages on a common
measurement foundation.

This document records architectural direction without committing the project to
an implementation roadmap. It is offered as a reference point for future design
decisions, and as a check against drift away from the project's identity as a
measurement instrument. It carries no authority over the ADR series, the
measurement boundary, or any contract in `contracts/`.
