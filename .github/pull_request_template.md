<!--
Routine work — refactor, formatting, typo, dependency bump, a test that
exercises existing behaviour — needs only Purpose, Scope and Validation. Delete
the evidence section.

Fill in the evidence section when this PR makes a material evidence-bearing
claim: measurement, uncertainty, hardware state, calibration, acquisition, a
physical experiment, an analyzer capability, or a validation claim.

The question is not "did I touch hardware code" but "does this PR make a
statement someone could later cite as evidence?"

See docs/TTP_PR_ADMISSION_PROTOCOL.md.
-->

## Purpose

## Scope

<!-- What changed, and what deliberately did not. -->

## Validation

<!-- Commands run and their results. Baseline and final test counts where relevant. -->

---

## Evidence claims

<!--
One block per material claim. Use the owning authority's vocabulary, spelled its
way — the map is in docs/TTP_PR_ADMISSION_PROTOCOL.md. Do not invent new state
words, and do not report a position on a single ladder: name the axis.

Mark a field n/a WITH A REASON rather than deleting it. A missing LIMITATION is
usually a claim whose limits were not considered.
-->

### CLAIM-1

- **Claim:**
  <!-- The narrowest proposition asserted. -->
- **Claim class:**
  <!-- e.g. software capability, hardware state, measured result, derived result,
       uncertainty result, architecture claim, experimental conclusion, validation claim -->
- **Source / instrument:**
  <!-- What produced the evidence: source trace, unit test, schema validation,
       manufacturer datasheet, ownership census, E0 test, scale reading,
       microphone capture, budget calculation, reference instrument. -->
- **Observation:**
  <!-- What was directly observed. Not what it means. -->
- **Provenance:**
  <!-- The owning authority's value: PROPOSED / ASSUMED / DATASHEET / DERIVED /
       MEASURED, or the appropriate vocabulary for this claim class. Name the
       authority if the word is ambiguous — "derived" exists in two of them. -->
- **Supported inference:**
- **Scope:**
  <!-- Exact hardware, specimen, file, route, test, frequency range, environment,
       commit, session, population or configuration examined. A negative claim is
       bounded to the population actually observed. -->
- **Limitation / blind spot:**
  <!-- What this evidence does NOT establish. -->
- **Unresolved condition:**
  <!-- What still prevents a stronger claim. -->
- **Falsifier:**
  <!-- What observation would invalidate, weaken, or upgrade this claim. -->
- **Evidence reference:**
  <!-- Where a reviewer can inspect or reproduce it. -->

---

## Authority states touched

<!-- Delete any row this PR does not touch. Report what the authority says, do
     not decide it here. -->

| State | Before | After | Authority that ruled it |
| --- | --- | --- | --- |
|  |  |  |  |

## Promotions

- [ ] No hardware state was promoted (`CANDIDATE` → `SELECTED`, `SELECTED` → `OWNED`, `UNKNOWN` → `CONFIRMED_ABSENT`, …) without the ruling that authorizes it
- [ ] No `DATASHEET` or `DERIVED` value is reported as `MEASURED`
- [ ] No `NOT_EXECUTED` record carries a result
- [ ] No fixture or synthetic data is described as hardware evidence
- [ ] No component rating is reported as a system requirement
- [ ] Universal claims (*never*, *all*, *proves*, *does not exist*) carry a bounded universe

## Physical experiment

<!-- Only for PRs introducing or reporting one. Delete otherwise. -->

- **Instrument:**
- **Specimen / system under test:**
- **What causes pass:**
- **Quantity actually observed:**
- **What pass supports:**
- **What pass does not support:**
- **Plausible confound / false positive:**
- **Control or falsifier that exposes it:**
- **Raw artifacts preserved:**
- **Provenance class of the result:**

---

## Admission state

- [ ] **DRAFT / INVESTIGATING** — claims not yet bounded
- [ ] **READY FOR REVIEW** — claims bounded to their evidence

<!--
Green tests do not by themselves make an evidence-bearing PR ready.

A passing software test does not establish a valid physical measurement.
A manufacturer specification does not become a measured TTP quantity without an
executed measurement. Commanded excitation is not measured mechanical input force.

Do not increase the strength of the claim beyond the strength of the evidence.
-->
