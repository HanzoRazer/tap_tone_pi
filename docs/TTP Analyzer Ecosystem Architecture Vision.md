Here's a consolidated architectural summary that captures the shift in vision and should serve as an architectural decision record for the project.

I would treat this as a foundational document rather than another sprint artifact.

# TTP Analyzer Ecosystem Architecture Vision

**Status:** Architectural Position Statement
**Revision:** 1.1 — added Electrical / Hardware Stack section (architectural summary; references the canonical hardware spec)
**Purpose:** Capture the evolution of the Tap-Tone-Pi Analyzer into a desktop acoustic measurement instrument and define the constitutional relationship between its subsystems.

---

# Executive Summary

The Tap-Tone-Pi (TTP) Analyzer has evolved beyond its original concept as a tap-tone analysis application.

It is now architected as a **low-cost desktop acoustic measurement instrument** capable of supporting education, laboratory experimentation, workshop measurements, and specialized luthiery workflows through a common measurement platform.

The architectural objective is to provide laboratory-style acoustic measurement capability at a price point accessible to students, schools, small workshops, and independent researchers.

---

# Architectural Evolution

## Phase 1 — Tap Tone Analyzer

Original purpose:

```text
Capture a tap.

Perform FFT.

Display frequency content.
```

The application functioned primarily as a digital tap analyzer.

---

## Phase 2 — Scientific Measurement Platform

As the project matured, additional capabilities were introduced:

* calibration
* provenance
* repeatability
* experiment design
* campaign management
* controlled excitation
* transfer function measurement
* variance characterization
* cohort regression
* empirical formula support
* formula validation

The software transitioned from an analyzer into a governed measurement platform.

---

## Phase 3 — Desktop Acoustic Measurement Instrument

The current architectural vision is no longer simply software.

The TTP Analyzer is a complete measurement instrument consisting of:

* defined hardware
* calibration procedures
* governed software
* laboratory protocols
* experiment management
* reporting

The software is one subsystem of the instrument.

---

# Electrical / Hardware Stack

The physical foundation of the instrument is a defined four-stage electrical
signal chain. The software runs *on top of* this stack; it does not replace it.

```text
[Mic] → [OPA1612 balanced mic-pre] → [HiFiBerry DAC+ ADC] → [Raspberry Pi 5] → [tap_tone_pi DSP]
```

| Stage | Element | Architectural role |
|---|---|---|
| 1 | Measurement microphone (SDC or dynamic, balanced XLR, 48V phantom) | Acoustic → electrical transduction |
| 2 | OPA1612 transparent preamp (3-position gain switch) | Low-noise, low-distortion gain staging into the ADC window |
| 3 | HiFiBerry DAC+ ADC Pro (24-bit, 2-channel, I²S) | Calibrated digitization; ch0 = reference, ch1 = roving (Phase 2) |
| 4 | Raspberry Pi 5 + tap_tone_pi | Signal generation, capture, DSP, provenance, export |

Two excitation modes share this one chain:

* **Phase 1 — impulse tap** (single channel): the operator taps the plate and the
  chain captures the free response.
* **Phase 2 — speaker-driven ODS** (two channel): the Pi is both source and sink,
  driving a speaker while capturing reference and roving mics, so the excitation
  level is known in software.

A self-calibration loopback (`signal_gen → DAC → preamp → ADC → Pi`) characterizes
each unit before use, bounding and recording amplitude offset, frequency response,
latency, and noise floor per unit. This per-unit calibration is what makes the
platform a *measurement instrument* rather than a recording application.

**Canonical specification.** The full electrical stack — component selection,
corrected gain-staging tables, calibration coverage, connector map, and the
prototype-vs-production BOM — is maintained in
[`docs/hardware/TTP_HARDWARE_STACK.md`](hardware/TTP_HARDWARE_STACK.md). This
section is the architectural summary; that document is authoritative for detail.

---

# Instrument Philosophy

The TTP Analyzer is intended to provide:

* repeatable measurements
* provenance-aware data
* calibrated acquisition
* controlled excitation
* experiment documentation

It intentionally avoids making engineering recommendations or replacing scientific judgment.

Its role is to measure and document—not to speculate.

---

# Desktop Instrument Tier

The TTP Analyzer occupies a unique position.

It is designed as an affordable desktop acoustic measurement instrument suitable for:

## Education

* technical colleges
* university laboratories
* STEM programs
* instrument-making schools
* classroom acoustic demonstrations

Students learn:

* calibration
* FFT analysis
* transfer functions
* experiment documentation
* repeatability
* uncertainty

---

## Workshop

Suitable for:

* individual luthiers
* repair shops
* prototype development
* small manufacturing environments

---

## Research

Supports:

* controlled experimentation
* empirical model development
* repeatable measurement campaigns
* longitudinal studies

---

# Core Instrument Platform

The core measurement platform is intentionally domain-neutral.

It provides capabilities such as:

* signal generation
* FFT
* spectral analysis
* transfer functions
* impulse response
* controlled excitation
* calibration
* dual-channel acquisition
* experiment management
* provenance
* measurement validation
* reporting

None of these capabilities are inherently specific to luthiery.

---

# Domain Modules

Specialized workflows are implemented as domain modules built on the core measurement platform.

Examples include:

* Luthiery
* Material resonance studies
* Loudspeaker characterization
* General acoustics laboratories
* Mechanical vibration exercises

The luthiery workflows remain the primary reference implementation but are not the architectural definition of the platform.

---

# The Luthier Acoustics Laboratory

The Luthier Acoustics Laboratory is **not a separate product**.

It is a major subsystem of the TTP Analyzer.

Its purpose is to provide an environment for developing and documenting measurement methods before they become production workflows.

Typical contents include:

* laboratory manual
* protocol library
* fixture specifications
* experimental workflows
* research projects
* deferred concepts
* promotion queue

---

# Laboratory Manual

The Laboratory Manual is considered part of the instrument.

Its role is comparable to laboratory procedures supplied with professional scientific equipment.

The manual documents:

* operating procedures
* calibration procedures
* laboratory protocols
* experiment workflows
* fixture requirements
* measurement theory
* safety considerations
* validation procedures

It is not merely product documentation.

It is an operational component of the instrument.

---

# Repository Structure

The TTP Analyzer remains a single repository.

Recommended high-level organization:

```text
tap_tone_pi/

    hardware/
    calibration/
    measurement/
    excitation/
    provenance/
    experiment/
    reporting/

    acoustic_lab/
        laboratory_manual/
        protocols/
        fixtures/
        experimental_workflows/
        research_projects/
        deferred_concepts/
        promotion_queue/
```

The separation is architectural rather than repository-based.

---

# Promotion Pipeline

Experimental concepts mature through the following stages:

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

Only validated measurement workflows are promoted into the production measurement namespaces.

---

# Constitutional Separation

The project maintains three distinct responsibilities.

## Acoustic Laboratory

Mission:

> Discover.

Develops protocols, experiments, and measurement methods.

---

## Measurement Platform

Mission:

> Measure.

Executes validated workflows with calibration, provenance, and repeatability.

---

## Application Layer

Mission:

> Apply.

Uses validated measurements for domain-specific engineering, design, or educational purposes.

---

# Long-Term Vision

The TTP Analyzer is envisioned as an affordable desktop acoustic measurement instrument that brings laboratory-quality measurement practices into classrooms, workshops, and research environments.

Its value is not defined by a single application domain, but by the quality and repeatability of the measurements it produces.

Specialized domains—including luthiery—are implemented as workflow packages on top of a common scientific measurement foundation.

This document captures the architectural direction without committing you to a specific implementation roadmap, while preserving the principles that have emerged as the project matured. It can serve as a reference point for future design decisions and help prevent the project from drifting away from its core identity as a desktop acoustic measurement instrument.
