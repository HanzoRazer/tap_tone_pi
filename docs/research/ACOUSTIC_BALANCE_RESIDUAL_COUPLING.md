# Acoustic Balance — Residual Coupling (Deferred Research Methodology)

> **Status:** Deferred research concept. Lab/research layer only — **not** a
> Tap-Tone-Pi production feature.
>
> **Classification:** research-methodology note. It introduces no measurement
> artifacts, schemas, workflows, or advisory logic.
>
> **Do not implement in TTP.** See [Non-goals](#non-goals) and
> [Promotion criteria](#promotion-criteria).

---

## Purpose

Use empirical formula residuals and interaction terms to identify *possible*
hidden acoustic couplings.

> A luthiery formula may reveal hidden acoustic couplings through structured
> residuals and interaction terms, similar to how chemical side reactions are
> inferred from mass/energy balance non-closure.

This note captures the concept so it is not lost, while keeping unvalidated
theory out of TTP production code.

---

## Chemistry analogy

In reaction engineering, a mass or energy balance names the expected inputs and
outputs. When the balance does not *close* — the accounted-for quantities do not
sum the way the named channels predict — the non-closure is evidence of an
unnamed pathway (a side reaction, a loss term, an unmodeled species). The
balance itself does not identify the pathway; it only flags that one exists and
bounds its size.

The insight worth preserving: **non-closure is a signal, not a conclusion.**

---

## Acoustic interpretation

By analogy, with each mapping stated as a hypothesis rather than a fact:

- **Formula as spec sheet.** The empirical formula represents the named acoustic
  channels believed to govern a response.
- **Residual as non-closure.** Structured residuals beyond measurement
  uncertainty may indicate a missing variable, a coupling between variables, or
  an unmodeled response channel.
- **Interaction terms as coupling evidence.** Cross-terms in the fitted model
  may describe how two variables interact acoustically, beyond their independent
  contributions.
- **Measurement uncertainty as filter.** Residuals inside σ_measurement are
  treated as measurement noise, not new phenomena.

None of these steps identifies a specific physical coupling. They only flag that
residual structure exists and bound where to look.

---

## Required data

Before any balance-like analysis can be trusted:

1. **Controlled excitation / input-side accounting** (DO-90 / DO-91) — the input
   energy must be characterized, not assumed.
2. **Defined output response channels** — the named channels of the "spec sheet"
   must be explicit.
3. **Repeated measurement with a known σ_measurement** (repeatability evidence,
   DO-85) so residuals can be compared against noise.
4. **Covariate control** (DO-89C) so interaction terms are interpretable rather
   than confounded.

---

## Role of TTP

TTP's role is **data generation, not interpretation.**

- TTP produces the governed measurement data: controlled excitation records,
  response captures, cohort regression evidence, formula candidates, and
  validation envelopes.
- The lab/research layer interprets residual structure on top of that governed
  data.
- Only a matured measurement workflow — one that can be specified without
  speculative interpretation — returns to TTP.

TTP does not detect couplings, does not name side reactions, and does not promote
residual structure to an established acoustic claim.

---

## Non-goals

This artifact is a research-methodology note only. It does **not** introduce, and
must not be read as authorizing:

- a hidden mode detector
- a side reaction analyzer
- automatic coupling discovery
- a new TTP workflow
- a new schema
- a new regression engine
- a new advisory layer

No speculative acoustic statement in this note is an established fact. Every
coupling statement is a hypothesis to be tested against the promotion criteria
above.
