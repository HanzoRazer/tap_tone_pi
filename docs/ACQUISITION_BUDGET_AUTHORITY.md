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

**B-005 is narrowed, not closed.** Its acceptance asks for an ownership decision
between the two *existing* `UncertaintyBudget` implementations —
`tap_tone_pi.uncertainty.budget` and `tap_tone_pi.core.statistics` — and the
decision above does not answer that. Closing it on this evidence would be
declaring victory over a different question.

One observation is contributed toward it: `uncertainty/stiffness.py` imports from
`.budget`, so `uncertainty.budget.UncertaintyBudget` is de facto canonical for
propagation. That is evidence for whoever resolves B-005, not a ruling by this
order.

## Downstream

Attachment to sessions, Viewer Pack export, the engineering CLI and the E0
adapter are **DO-107B**, built only after this contract is published and
reviewed. Downstream code should not be written against a contract that may still
change in review.
