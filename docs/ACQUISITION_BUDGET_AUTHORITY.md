# Acquisition Budget Authority

**Dev Order:** DO-107A
**Package:** `tap_tone_pi/uncertainty/acquisition/`
**Contract:** `acquisition_budget_v1`
**Status:** authority established; integration (E0 adapter, session attachment,
Viewer Pack, CLI) is DO-107B.

---

## What this subsystem answers

> What limits this measurement, what uncertainty follows from those limits, and
> how large a physical difference must exist before the Analyzer can distinguish
> it?

It unifies converter noise, front-end noise, clock jitter, clock accuracy,
acquisition duration and resolution, sweep-rate constraints, physical
repeatability, dimensional uncertainty, propagated `E_L` uncertainty, and the
provenance of every input above.

The output is a persistent engineering artifact attached to a measurement
session — not a calculator reading.

## What it does not own

- the canonical definition of `E_L`;
- conventional propagated measurement uncertainty (see the ownership split below);
- tone-quality interpretation, wood grading, or any advisory judgement;
- procurement, excitation control, DSP acquisition loops;
- hardware pass/fail certification.

---

## Grounding report (DO-107A Commit 1)

DO-107 §10 Commit 1 carries a stop condition: *stop if an equivalent
acquisition-budget authority already exists.* It does not — but the overlap with
existing code is substantial enough to change the implementation boundary, and
this section records what was found so the reasoning survives.

### What already exists

`tap_tone_pi/uncertainty/` is 2,286 lines across six modules and already owns:

| Module | Owns | numpy? |
| --- | --- | --- |
| `budget.py` | GUM `UncertaintyBudget`, `UncertaintyComponent`, Type A/B sources, distributions | **yes** |
| `propagation.py` | `sensitivity_coefficients()`, `propagate_uncertainty()`, Monte Carlo, GUM assumption checks | **yes** |
| `stiffness.py` | `compute_tap_tone_moe_uncertainty()`, `compute_deflection_moe_uncertainty()` | no |
| `frequency.py` | `compute_frequency_resolution()`, `compute_frequency_uncertainty()`, `estimate_frequency_repeatability()` | no |
| `amplitude.py` | `compute_snr_uncertainty()`, `rms_to_dbfs()` | no |
| `formatters.py` | rendering | no |

### The exact-match finding

`uncertainty/stiffness.py::compute_tap_tone_moe_uncertainty()` documents itself as:

> For free-free beam: E ∝ f² × L⁴ × ρ / h²
> (ΔE/E)² = (2×Δf/f)² + (4×ΔL/L)² + (Δρ/ρ)² + (2×Δh/h)²

That is the same propagation as `acquisition_budget.py::modulus_budget()`, and
the same sensitivity coefficients (**2 / 4 / 1 / 2**) the DO-107 test plan
specifies. **It already exists and it is canonical.**

Consequence, per DO-107 §4.5: this subsystem's `ModulusBudget` is a **thin
adapter**. It presents that result in acquisition-budget vocabulary and does not
re-implement the equation. A delegation test pins that — if the adapter ever
computes the arithmetic itself, the test fails.

### Naming

DO-107 §5 originally proposed `acquisition/frequency.py` and
`acquisition/propagation.py`. Both names already exist one level up with
different responsibilities, and two `propagation.py` files in one package tree is
a trap: the wrong import eventually looks right. Renamed to
`frequency_budget.py` and `modulus.py`. Modules under `acquisition/` name the
acquisition-specific responsibility; `uncertainty/frequency.py`,
`stiffness.py` and `propagation.py` keep their existing semantic ownership.

---

## The stdlib boundary

DO-107 §4.10 requires the acquisition engine to run on the instrument without
NumPy or SciPy. `acquisition_budget.py` honors that — it imports only `json`,
`math`, `dataclasses`, `enum` and `typing`.

But **`uncertainty/budget.py` and `uncertainty/propagation.py` both import
numpy**, so naive reuse would smuggle a heavy dependency into a module advertised
as instrument-safe.

The boundary is therefore explicit:

```
stdlib acquisition core  →  adapter / conversion boundary  →  existing uncertainty subsystem
   (no numpy, ever)              (crosses the line)              (numpy permitted)
```

`AcquisitionBudgetV1` and everything required to compute it on the Pi import
without numpy. The modulus adapter bridges to the canonical `UncertaintyBudget`
authority **outside** that core boundary.

This is enforced by import-graph inspection rather than by grepping the new files
for `import numpy` — a transitive import through an innocent-looking module is
precisely the leak the constraint exists to prevent.

---

## Provenance is load-bearing

Every input carries one of:

| Provenance | Means |
| --- | --- |
| `PROPOSED` | A design-stage figure. Somebody's intention |
| `ASSUMED` | Taken as given without a cited source |
| `DATASHEET` | A manufacturer's nominal figure |
| `DERIVED` | Computed from other quantities in this record |
| `MEASURED` | Observed on this instrument |

Provenance is **not** collapsed to a generic source string, and it survives
serialization exactly. A utility may never invent missing provenance, convert
`UNKNOWN` to zero, substitute a proposed value for a measured one, fill missing
repeatability, or clear an evidence blocker.

## A budget is not an evidence grade

**These are separate objects and must stay separate.**

`AcquisitionBudgetV1` is the *analysis*. Evidence grade is a *property computed
from the provenance of the inputs a particular budget used.*

The same engine must be able to produce a genuinely useful design-stage budget
full of `PROPOSED` values while truthfully refusing to call that result
evidence-grade. That is what makes the tool usable before the hardware exists
without letting design intentions become measurement claims.

And when it does report evidence grade, the claim is narrow:

> Acquisition budget is internally evidence-complete for the inputs represented.

It does **not** mean laboratory validated, reference validated, production
certified, or NSF risk closed. It changes no hardware or capability status.

### Standing blockers

- **No default physical repeatability.** Missing `physical_repeatability_hz`
  blocks a full uncertainty claim, and the remaining frequency budget is labelled
  an *electronic lower bound* rather than an achieved precision.
- **`Q` stays provisional.** The profile's `Q = 50` is `PROPOSED`. Sweep limits
  carry that provenance through to their outputs.
- **B-014** — no anti-aliasing filter, unresolved.
- **AC-coupling corner** — unmeasured until E0 T3 runs.

## Error mechanisms stay separate

Aliasing, jitter/aperture, clock accuracy, front-end noise, converter noise and
physical repeatability are six distinct mechanisms and are never recombined into
one "ADC error" term. In particular, discrete spurs from a fractional-N clock are
**not** root-sum-squared as if they were Gaussian noise.

## Sweep limits are advisory

Modal time constant, half-power bandwidth, minimum dwell, maximum sweep rate and
minimum sweep time are computed and reported. **They do not drive the excitation
system.** Turning them into acquisition behavior is a successor order, and a
long computed sweep is a constraint result rather than a product requirement.

## The self-test margin is policy, not physics

The boot noise threshold is derived, but its margin is explicit and carries its
own provenance:

```
expected_noise_floor_dbfs   DERIVED
allowed_margin_db           POLICY / PROPOSED / MEASURED
fail_above_dbfs             DERIVED
```

The default 6 dB must not silently become a scientific constant.

## Profiles are examples

`TTP_ANALYZER_PROFILE()` and friends carry worked demonstration values. They are
fixtures, example builders and CLI presets — **clearly labelled non-evidence
defaults** unless populated from real session or E0 data.

---

## Relationship to E0

E0 is upstream. Measured converter noise, the AC-coupling corner, PGA behavior
and full-scale figures replace `PROPOSED` and `DATASHEET` inputs with `MEASURED`
ones, carrying that provenance into the budget.

DO-107 does **not** execute E0, fabricate an E0 value, or repair an invalid E0
record — it consumes records already validated by the E0 contract. A missing E0
field stays unresolved; there is no default.

E0 is `NOT EXECUTED` and `ADC-001` is `CONFIRMED_ABSENT`, so every converter
input today is `PROPOSED` or `DATASHEET`. That is why the design-stage budget
must work and must refuse evidence grade.

## Relationship to repeatability

Physical repeatability comes from measurement, not from this subsystem. Until
DO-105-class work supplies it, the frequency budget is electronic-only and says
so. Improving the clock while physical repeatability dominates must not change
the limiting-factor narrative — a test pins that.

## Ownership split with the existing uncertainty subsystem

**This is the decision B-005 was waiting for on its third-implementation
question, and it is recorded here rather than assumed:**

> `UncertaintyBudget` owns conventional propagated measurement uncertainty.
> `AcquisitionBudgetV1` owns acquisition-chain limiting-factor and error-budget
> analysis together with evidence provenance. Acquisition budgets may consume or
> reference canonical `UncertaintyBudget` results; **they do not replace or
> independently reproduce them.**

So `AcquisitionBudgetV1` is deliberately **not** a third `UncertaintyBudget`. It
is a different kind of object that composes one.

**`tap_tone_pi.uncertainty.budget` remains the canonical general
uncertainty-budget and propagation authority.**
`tap_tone_pi.core.statistics.UncertaintyBudget` is not, and should not acquire
new consumers. Corroborating evidence: `uncertainty/stiffness.py` already imports
from `.budget`, so the propagation path in use was already that one.

**B-005 is closed on this decision.** Its trigger fired and the ownership
decision it asked for has been made and recorded, which is its stated acceptance
— "keep both with explicit roles". Leaving it open after both had happened would
be bookkeeping theatre. Empirical contracts should reference budget identity
through `uncertainty.budget.UncertaintyBudget`.

## What the record can express

A contract-readiness inspection ran before publication, asking one question: can
the object model serialize what the engine actually knows, without lying or
losing state? Three gaps were found and closed; one apparent gap was recorded as
deliberate.

### Reportable quantities are not the same as contributors

`FrequencyBudget` reports bin width, estimator floor, clock error and physical
repeatability. It **separately** carries `combined_contributors` — a *sequence*,
duplicates preserved, each entry naming both the contributor slot and the
reportable quantity that filled it.

The two lists differ, and the difference is the finding. Under **B-021** the
`spectral_resolution` slot is filled by the estimator floor rather than the bin
width, so the estimator enters the combination twice and the bin width enters not
at all — while being reported as 0.25 Hz beside a combined figure of 0.0037 Hz.
Without the contributor sequence a reader would reasonably conclude the largest
listed quantity was included. It was not.

A mapping keyed by conceptual quantity would have collapsed the two estimator
entries and hidden this. An invariant test recomputes the root-sum-square from
the *serialized* contributors and requires equality with `combined_hz`, which is
the contract guarantee: **the combination contains these values and nothing
else.** When B-021 is repaired, the change appears as a different contributor
composition rather than as an unexplained movement in a number.

### `UNAVAILABLE` is a state, not an exception

`ModulusUnavailable` still exists for callers that want to fail loudly crossing
the dependency boundary, but it is never what gets serialized.
`modulus_budget_or_unavailable()` returns either a `ModulusBudget` or an
`UnavailableSection`, both carrying an `availability` discriminator.

An unavailable section carries a machine-readable `reason_code`, a specific
reason — *canonical uncertainty authority unavailable in the instrument-safe
environment*, not "computation failed" — and **no numeric field at all**. There
is nothing in it to mistake for a result, and nothing was fabricated.

### Formula authority is typed

`FormulaStatus` has two members and exists for one term. The estimator floor is
`CANDIDATE_SOURCE_FORMULA` and survives serialization and deserialization as a
typed value rather than a string minted inside `as_dict()`. It is a different
axis from `Provenance`, which records where a *number* came from rather than
whether the *formula* producing it is settled.

### Serialization is lossless

The round-trip test found `as_dict()` rounding values. **Rounding belongs to
report rendering, not to a contract payload**: a lossy record cannot round-trip
and cannot be recomputed from. Where the acquisition source rounds into a stored
field, that rounding stays — it is parity, not serialization loss.

### Computed outputs carry no input-style provenance — deliberately

`NoiseBudget`, `FrequencyBudget` and `ModulusBudget` hold plain floats with no
`Provenance` tag, and this is a design decision rather than an omission.

> Computed budget outputs do not carry independent input-style provenance. They
> are derived by definition. Evidence eligibility is determined from the
> provenance of their **inputs**, plus authority and status metadata attached to
> the **computation**.

Tagging every computed scalar `DERIVED` would add no information while diluting
the distinction that does matter — `MEASURED` against `DATASHEET` against
`PROPOSED` on the way in.

The second clause is not decoration. **B-022 shows input provenance alone is
insufficient**: a modulus result can rest on excellent inputs and still be
carrying an authority workaround. That is why `ModulusBudget` records
`component_authority` and `aggregation`, and why `FrequencyBudget` records
`estimator_floor_status`. Evidence grade must read both axes.

## Evidence grade, and an amended acceptance criterion

**Evidence-qualified inputs are necessary but not sufficient.** An otherwise
fully qualified budget remains non-evidence-grade while a blocking computation
condition is present.

DO-107 §8.G.49 originally expected that all-qualified inputs would produce an
evidence-grade budget. **Grounding discovered structural computation blockers the
order did not know existed**, so that criterion is empirically invalid as
written. It is replaced by two tests rather than by weakening the implementation:

1. Qualified inputs with B-020 and B-021 present → `evidence_grade = false`,
   carrying exactly those structural blockers.
2. A blocker-cleared composition → `evidence_grade = true`, proving the grading
   function is capable of returning true.

The second is not decoration. Without it, *"true is unreachable because the
scientific authorities are unresolved"* would be indistinguishable from *"true is
unreachable because we implemented a permanently-false grading function."*

### How each condition is classified, and why

| Condition | Blocks | Reasoning |
| --- | --- | --- |
| Input provenance, repeatability, B-014, coupling corner | **yes** | The source's own evidence rules |
| `section_unavailable` | **yes** | A budget missing a section it was asked for cannot claim a complete result |
| **B-021** contributor composition | **yes** | The frequency aggregate knowingly draws the estimator candidate twice. Evidence grade is a statement about the *validity of the computation*, not about whether a known defect happens to be small for today's inputs |
| **B-020** provisional formula | **yes** | The expression was deliberately not called a Cramér–Rao bound because its authority and convention are unresolved. Calling a budget containing it evidence-grade would contradict that decision. Its tiny numerical contribution does not change its epistemic status |
| **B-022** aggregate workaround | **no — advisory** | Materially different. The acquisition result does **not** reproduce the bad canonical aggregate: it takes component construction and sensitivities from the canonical authority and performs a correct generic RSS over them, and parity independently confirms agreement with the source calculator. What is unresolved is that the repository's nominal canonical aggregate disagrees. That is **authority debt**, not a mathematical defect in the emitted number |

Repairing B-022 will remove the advisory condition and let the adapter become
genuinely canonical **without changing the acquisition value**. That is the test
of the classification, and it is why B-022 sits on the other side of the line
from B-020 and B-021.

### The resulting state

```
perfect hypothetical instrument + current mathematics
        → B-020 blocking, B-021 blocking, B-022 advisory
        → evidence_grade = false

qualified inputs + a composition with no blocking condition
        → evidence_grade = true
```

**B-020 and B-021 are not remediated to unlock publication.** Their discovery is
evidence produced by this order, not a failure of it.

## Frequency uncertainty — a four-way authority map

The 984-line census of the acquisition source found a pre-existing conflict here,
so the boundaries are stated explicitly rather than left to be inferred.

| Owner | Owns | Status |
| --- | --- | --- |
| `uncertainty/frequency.py::compute_frequency_resolution()` | FFT bin resolution | canonical; **delegated to**, not reimplemented |
| `uncertainty/frequency.py::compute_frequency_uncertainty()` | the existing empirical session-level frequency uncertainty | unchanged, callers not redirected, coefficients not reinterpreted |
| `uncertainty/acquisition/frequency_budget.py` | the **chain-level acquisition frequency budget** | new authority (this order) |
| `core/session_diff.py` | a production heuristic | untouched; conflict recorded as **B-020** |

The chain-level budget is the only one that accounts for clock accuracy and
physical repeatability, which are the terms that change what an operator does.
It answers: *what limits the trustworthy frequency measurement in this
instrument?* — bin resolution (delegated), an estimator term, clock-accuracy
scale error, session repeatability, their combination, and the provenance of each.

### The estimator term is a candidate, not a certified CRB

`core/session_diff.py` computes `f / (2 × 10^(SNR_dB/20))` and calls it *"the
Cramer-Rao lower bound for frequency estimation"*, while its own comment above
calls it a rule of thumb. The acquisition source carries a different expression
based on record length and sample count.

**This subsystem does not claim to have the correct one.** Its estimator term is
carried as an *estimator-floor candidate — source formula*, faithful to the
acquisition source for parity purposes, with its authority status explicit. It is
**not** labelled a Cramér–Rao lower bound in code, tests, or here.

The reason is a real unresolved question rather than caution for its own sake:
the newer acquisition mathematics material carries an acknowledged factor-of-two
and SNR-convention discrepancy around exactly this expression, and it marks itself
not source-verified. Promoting either expression now — merely because one looks
more textbook — would settle by appearance instead of by derivation. **B-020**
holds that reconciliation, and deliberately prescribes no replacement equation.

## Material arriving after this order was written

`patch-02-acquisition.patch` and `TTP_ACQUISITION_MATHEMATICS.md` arrived while
this order was stopped at its grounding questions. They are archived under
[`docs/reference/acquisition/deferred/`](reference/acquisition/deferred/) and
**none of their content is implemented here** — not the new equations, the T4
retargeting, the jitter regression, or the Smart Guitar conclusions.

The mathematics document marks itself *"Not yet source-verified"* and lists an
unresolved CRLB discrepancy, a force-correction question and coverage-factor work
among its open items. This order publishes the first `acquisition_budget_v1`
contract, and a published contract is the point after which downstream code is
written against it. Shaping it with propositions their own author flagged as
unverified is the one sequencing mistake most expensive to undo.

They belong to a successor reconciliation order.

## Downstream

Attachment to sessions, Viewer Pack export, the engineering CLI and the E0
adapter are **DO-107B**, built only after this contract is published and
reviewed. Downstream code should not be written against a contract that may still
change in review.
