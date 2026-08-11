# TTP Reference Validation Plan

**Status:** prospective. No comparison against any reference method has been
performed, and no partner is confirmed.

This document records how TTP *could* later be compared against an accepted
reference. It is the pathway that would turn a repeatable instrument into a
valid one. Nothing here has happened.

Machine-readable source: `tap_tone_pi/grant_readiness/risks.py`
(`REFERENCE_METHODS`).

---

## Why this document exists

The repository can currently show that a measurement agrees with itself. It
cannot show that it agrees with anything else.

Calibration in this repository means **internal signal-chain consistency** —
loopback, reference tone, frequency-response compensation. It does not mean
traceability to a calibrated acoustic standard, and no traceability is claimed
anywhere in the codebase or in any generated report.

This is technical risk **R10**, and it is the one risk that would remain open
even if every other risk were closed.

---

## Prospective comparison methods

Fields recorded `TBD` are unknown, not pending. No partner has been approached.

### Calibrated measurement microphone

| Field | Value |
| --- | --- |
| Measurement compared | Absolute sound pressure level and frequency response |
| Access status | Not owned; commercially available |
| Potential partner | TBD |
| Required preparation | Procurement, a documented calibration certificate, and a comparison procedure at a fixed position |
| Phase I role | Establishes whether the current signal chain's frequency response is flat enough for the reported quantities |

### Accelerometer

| Field | Value |
| --- | --- |
| Measurement compared | Surface acceleration at the measurement point |
| Access status | Not owned |
| Potential partner | TBD |
| Required preparation | Procurement, a mounting method that does not mass-load a thin plate, and a synchronized acquisition path |
| Phase I role | Cross-checks the acoustic measurement against a direct mechanical one, separating room effects from structural response |

### Instrumented impact hammer

| Field | Value |
| --- | --- |
| Measurement compared | Input force spectrum and transfer function |
| Access status | Not owned |
| Potential partner | TBD |
| Required preparation | Procurement and a force-window procedure |
| Phase I role | Turns an uncontrolled tap into a measured input, which is the precondition for a defensible transfer function. Also closes R1 by measuring the excitation rather than assuming it |

### Laboratory modal analyzer

| Field | Value |
| --- | --- |
| Measurement compared | Identified modal frequencies, shapes, and damping |
| Access status | No access arranged |
| Potential partner | TBD — university or commercial vibration laboratory |
| Required preparation | Access agreement, a shared specimen, and a comparison protocol agreed **before** any measurement is taken |
| Phase I role | The only path that addresses R6: whether an extracted feature is a structural mode |

### Scanning laser vibrometry

| Field | Value |
| --- | --- |
| Measurement compared | Full-field surface velocity and operational shapes |
| Access status | No access arranged |
| Potential partner | TBD |
| Required preparation | Access agreement and specimen preparation. Non-contact, so it avoids the mass-loading problem an accelerometer introduces |
| Phase I role | Reference for Phase 2 operational deflection shapes, which the first study deliberately excludes |

---

## Sequencing

The methods are not interchangeable and answer different questions. A defensible
order:

1. **Instrumented hammer** first. It measures the excitation, which bounds
   every repeatability figure the project can otherwise produce (R1). It is also
   the cheapest of the five and is owned outright once bought.
2. **Calibrated microphone** second. It qualifies the existing signal chain
   without changing the measurement architecture.
3. **Accelerometer** third, as a cross-check that separates the room from the
   structure.
4. **Laboratory modal analyzer** once 1–3 have made the TTP measurement
   defensible enough to be worth a laboratory's time. Approaching a partner
   before that wastes the access.
5. **Laser vibrometry** last, and only if Phase 2 operational shapes become part
   of the claim.

Steps 1–3 are procurement. Steps 4–5 are relationships, and the long lead time
is the access agreement rather than the measurement.

---

## Protocol requirements

Whenever a comparison is eventually run, these hold:

- The comparison protocol is agreed and written **before** any measurement is
  taken. A protocol chosen after seeing the data is not a comparison.
- The same specimen, the same measurement point, the same support condition,
  and the same session, or the difference is a confound rather than a result.
- Environmental conditions are recorded for both instruments and corrected for
  neither.
- Disagreement is reported. A comparison that only gets published when it
  agrees is not evidence.
- Reference-method uncertainty is stated. Agreement within the reference's own
  uncertainty is not agreement to better than that.

---

## What would count as a result

A comparison would let the project state, for the first time, a bounded
difference between a TTP measurement and an accepted reference on the same
specimen under stated conditions — with the reference's own uncertainty
attached.

It would **not** establish accuracy in general, across instruments, across
conditions, or across operators. Those are separate questions and each needs its
own evidence.

---

## Current status

No comparison has been performed. No partner is confirmed. No reference
instrument is owned.

Access to a reference method is a precondition for any accuracy claim. Until one
is arranged, this project can report repeatability and nothing beyond it.

---

*Related: `NSF_TTP_PHASE_I_TECHNICAL_RISKS.md` (R10),
`NSF_TTP_PRELIMINARY_EXPERIMENT.md`.*
