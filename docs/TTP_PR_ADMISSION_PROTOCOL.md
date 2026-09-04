# TTP PR Admission / Evidence-Claim Protocol

**Working identifier:** `TTP-PR-ADMISSION-001`
**Scope maturity:** `TTP-LOCAL`
**Enforcement maturity:** `PROSE` — advisory. Nothing here is a required check.
**Owns:** nothing. It requires a pull request to report truthfully what the
repository's existing authorities already say.

---

## The governing principle

> **Do not increase the strength of a claim beyond the strength of the evidence
> supporting it.**

Two companions:

> A modeled, calculated, specified, simulated, or implemented capability does not
> silently inherit the authority of a physically measured or validated one.

> Absence of evidence is not evidence of physical absence unless the relevant
> population was actually observed.

## Why this exists now

For most of this repository's life, a green test suite was strong evidence that
the thing being built worked, because the thing being built was software and the
test exercised it. That is changing:

```text
CODE → ELECTRONICS → TRANSDUCER → MECHANICAL INTERFACE
     → WOODEN STRUCTURE → SENSOR → MEASUREMENT → SCIENTIFIC INFERENCE
```

A passing test loses power with every step down that chain. `pytest` cannot
observe whether a stinger touching a plate shifts its modes. The protocol exists
so that a pull request stays honest about which link it actually reached.

## What this protocol is not

It is **not a new source of scientific or hardware truth.** Every state it talks
about is already owned by something else, and those owners are listed in the
vocabulary map below. The relationship is one-directional:

```text
EXISTING TTP AUTHORITIES     own scientific / hardware / measurement state
            ↓
PR ADMISSION PROTOCOL        requires a PR to state those states truthfully
```

So it should catch a PR that turns `CANDIDATE` into `SELECTED` without a ruling.
It must not decide which amplifier TTP should select. It should catch a result
labelled `MEASURED` whose source is a datasheet calculation. It must not decide
whether the underlying model is correct.

## When it applies

It applies to a PR making a **material evidence-bearing claim** — one that
asserts something about measurement, uncertainty, hardware state, calibration,
acquisition, physical experiment, analyzer capability, or validation.

It does **not** apply to routine work: a refactor, a formatting pass, a typo, a
dependency bump, a test that exercises existing behaviour without asserting a new
capability. A green refactor needs no evidence dossier, and demanding one would
make the protocol something people route around.

The question to ask is not "did I touch hardware code" but **"does this PR make a
statement someone could later cite as evidence?"** If yes, it is in scope.

## Vocabulary: the authority map

**Do not invent vocabulary.** Every claim class below already has an owner. Use
that owner's words, spelled its way, and link to it.

| Claim class | Vocabulary | Owned by |
| --- | --- | --- |
| Input provenance | `PROPOSED` · `ASSUMED` · `DATASHEET` · `DERIVED` · `MEASURED` | `Provenance`, [`tap_tone_pi/uncertainty/acquisition/quantities.py`](../tap_tone_pi/uncertainty/acquisition/quantities.py) |
| Formula standing | `ESTABLISHED` · `CANDIDATE_SOURCE_FORMULA` | `FormulaStatus`, same file |
| Result availability | `AVAILABLE` · `UNAVAILABLE` | `ResultAvailability`, same file |
| Uncertainty evidence grade | boolean + blocking reasons | [`ACQUISITION_BUDGET_AUTHORITY.md`](ACQUISITION_BUDGET_AUTHORITY.md), `uncertainty/acquisition/contract.py` |
| Data epistemic status | Observed · Derived · Estimated · Predicted · Heuristic · Operator-Annotated · Externally-Sourced | [ADR-0012](ADR-0012-epistemic-status-taxonomy.md) |
| Artifact authority | capture / observational / derived classes | [ADR-0011](ADR-0011-measurement-authority.md) |
| Software capability maturity | `IMPLEMENTED` · `EXPERIMENTAL` · `PARTIAL` · `PLANNED` | `CapabilityStatus`, [`tap_tone_pi/grant_readiness/contracts.py`](../tap_tone_pi/grant_readiness/contracts.py) |
| Hardware verification | `VERIFIED_ON_HARDWARE` · `NOT_VERIFIED_ON_HARDWARE` · `NOT_APPLICABLE` | `HardwareVerification`, same file |
| Evidence origin | `HARDWARE` · `FIXTURE` · `SYNTHETIC` | `EvidenceOrigin`, same file |
| Experiment execution | `NOT_EXECUTED` · `EXECUTED` · `HALTED_AT_GATE` · `BLOCKED_BY_GATE` | `ExperimentOutcomeStatus`, same file |
| Campaign execution | `PREPARED` · `FIXTURE_EXECUTED` · `HARDWARE_EXECUTED` · `HALTED_AT_GATE` · `ABORTED` | `CampaignExecutionStatus`, same file |
| Calibration traceability | `TRACEABLE` · `NOMINAL` · `UNKNOWN` | `CalibrationTraceability`, same file |
| Hardware selection ladder | `TBD` · `SELECTED` · `ORDERED` · `RECEIVED` · `INSPECTED` · `BENCH_READY` · `REJECTED` | `STATUS_ORDER`, [`scripts/check_e1_hardware_bom.py`](../scripts/check_e1_hardware_bom.py) |
| Physical possession | `UNKNOWN` · `CONFIRMED_PRESENT` · `CONFIRMED_ABSENT` | `OWNERSHIP_STATES`, same file |
| Compatibility | `COMPATIBLE` · `COMPATIBILITY_REQUIRES_VERIFICATION` · `INCOMPATIBLE` · `NOT_APPLICABLE` | `COMPATIBILITY_DISPOSITIONS`, same file |
| Procurement action | `HOLD` · `VERIFY_POSSESSION` · `RECOMMEND_PURCHASE` · `USE_OWNED` · `NO_PURCHASE_REQUIRED` · `FABRICATE` · `REJECTED` | `PROCUREMENT_ACTIONS`, same file |
| Capability census axes | four independent axes | [ANALYZER_CAPABILITY_MATRIX.md](ANALYZER_CAPABILITY_MATRIX.md) |
| Risk standing | `OPEN` · `PARTIALLY_CHARACTERIZED` · `CLOSED` | `RiskStatus`, `grant_readiness/contracts.py` |

### These are axes, not one ladder

It is tempting to write the development of an instrument as a single chain —
calculated, implemented, specified, selected, owned, assembled, executed,
measured, validated. As a list of things that differ, that is correct. **As a
single status field it is wrong, and this repository has the counterexample
sitting in its own register.**

The Raspberry Pi 5 is `CONFIRMED_PRESENT` and is *not* `SELECTED`. It was bought
in April 2025, outside the campaign, while the human ruling is still
`SELECTION_DEFERRED`. On a linear ladder `OWNED` sits above `SELECTED`, so
recording the truth would require asserting a selection nobody made. The
[identity register](hardware/TTP_E1_HARDWARE_IDENTITY_REGISTER.md) spends a
section on exactly this and refuses `RECEIVED` for pre-owned hardware for the
same reason.

The same holds elsewhere: a bench surrogate amplifier can produce an `EXECUTED`
experiment without ever being `SELECTED`, and
[ANALYZER_CAPABILITY_MATRIX.md](ANALYZER_CAPABILITY_MATRIX.md) opens by saying
its four axes are independent.

**So a claim record names the axis and the value on it.** It never reports a
position on a single scale, and this protocol adds no such scale.

### Two authorities use the word "derived"

ADR-0012's `Derived` classifies a *value inside a measurement session* —
computed from `Observed` data by a documented algorithm. `Provenance.DERIVED`
classifies an *input to an acquisition budget* — calculated from named inputs and
a named relationship. They are different layers and neither is a typo for the
other. A claim record should say which one it means by naming the owner.

## Demonstrated claim boundaries

Every rule below exists because this repository actually got it wrong, or
actually had to draw the line. **Rules without a demonstrated example are not
encoded here.**

### Datasheet is not measurement

`Provenance` separates `DATASHEET` from `MEASURED` as distinct enum members, and
[ACQUISITION_BUDGET_AUTHORITY.md](ACQUISITION_BUDGET_AUTHORITY.md) states that a
budget full of `PROPOSED` values can be genuinely useful while truthfully
refusing to call itself evidence-grade. A value *calculated from* a manufacturer
specification is `DERIVED`, never `MEASURED`.

### A rated component figure is not a system requirement

An exciter rated 24 W states what the device tolerates. It does not state what
TTP must deliver. *(Established under DO-108P; at the time of writing that order
is open as PR #39 and not merged to `main`.)*

### Commanded excitation is not applied force

`validate_measured_force` in the E1 checker refuses a drive-side component filed
against the measured-force role, with the reason recorded in the code:
*commanded excitation is not a force measurement.* Knowing the waveform the
Analyzer emitted establishes nothing about the mechanical force entering a plate.

### Software implemented is not physically demonstrated

`CapabilityStatus.IMPLEMENTED` and `HardwareVerification.VERIFIED_ON_HARDWARE`
are separate fields precisely so one cannot imply the other, and
`validate_no_unwitnessed_hardware_claim` refuses a `VERIFIED_ON_HARDWARE` claim
while the campaign is deferred.

### Fixture data is not hardware evidence

`EvidenceOrigin` separates `HARDWARE` from `FIXTURE` and `SYNTHETIC`, and the
`grant_readiness` package makes the `HARDWARE` claim *derived* from acquisition
provenance rather than declared — an operator cannot relabel fixture data into
hardware evidence.

### Absence from a register is not physical absence

The ownership census separates `UNKNOWN` from `CONFIRMED_ABSENT`, and the checker
records why: *UNKNOWN means nobody has looked; it does not mean absent.*
`RECOMMEND_PURCHASE` is refused against `UNKNOWN` ownership for that reason.

### Canonical is not defect-free, and parity is not correctness

`FormulaStatus.CANDIDATE_SOURCE_FORMULA` exists because an implementation can be
the repository's canonical one and still be wrong. **B-022** is the case: the
canonical MOE authority double-applies its sensitivity coefficients. A parity
test proves two implementations agree; it says nothing about whether either is
right.

### A model is not validated by executing

**B-020** is the clearest example this repository owns. `session_diff.py` labels a
heuristic as a Cramér–Rao lower bound. DO-107M investigated it, established the
implemented form is `sqrt(2)` conservative under TTP's power convention — and
still **refused closure**, because both candidate bounds assume constant
amplitude across the record while a tap tone is a freely decaying mode. The
computation ran fine. The claim was still stronger than the evidence.

### An unmerged branch is not the repository

Recorded because it happened during the authoring of this protocol. A test
written on 2026-09-02 asserted that `docs/ANALYZER_CAPABILITY_MATRIX.md` *does
not exist*, when the true and much narrower claim was that it was not on that
branch at that moment. The file has since merged to `main` via commit `6c5366f`.
A universal negative about the repository was written from a single branch's
view, and the population changed underneath it.

The lesson generalises: **bound a negative to the population you observed.**

## Universal claims

Words like *never*, *nothing*, *always*, *all modes*, *all plates*, *no
hardware*, *does not exist*, *cannot*, *proves*, *validated*, *accurate* require
a bounded universe or an authority that covers one.

| Prefer | Over |
| --- | --- |
| not found in the censused acquisition path | does not exist |
| not observed in 25 repeated captures | never occurs |
| supports the hypothesis | proves the model |
| not present on `main` as of `<sha>` | not in the repository |

A note on the last row: *"TTP has no force measurement"* is a false universal —
the bending subsystem measures force. *"No dynamic force channel was found in
`contracts/` during the declared census"* is true and useful.

## The claim record

For each material claim, a PR should be able to answer this chain. The
[pull request template](../.github/pull_request_template.md) carries it.

```text
CLAIM ID
CLAIM                    the narrowest proposition asserted
CLAIM CLASS              which row of the vocabulary map above
SOURCE / INSTRUMENT      what produced the evidence
OBSERVATION              what was directly observed
PROVENANCE               the owning authority's value, spelled its way
SUPPORTED INFERENCE      what the observation supports
SCOPE                    hardware, specimen, file, route, frequency range,
                         environment, commit, session, population examined
LIMITATION / BLIND SPOT  what the evidence does not establish
UNRESOLVED CONDITION     what still prevents a stronger claim
FALSIFIER                what observation would invalidate or upgrade it
EVIDENCE REFERENCE       where a reviewer can inspect or reproduce it
```

Fields that genuinely do not apply are marked `n/a` **with a reason**, not
deleted. A missing `LIMITATION` is usually a claim whose limits were not
considered rather than one that has none.

## Measurement contract for experiments

A PR introducing a physical or simulated experiment should declare:

```text
INSTRUMENT
SPECIMEN / SYSTEM UNDER TEST
WHAT CAUSES PASS
QUANTITY ACTUALLY OBSERVED
WHAT PASS SUPPORTS
WHAT PASS DOES NOT SUPPORT
PLAUSIBLE FALSE POSITIVE OR CONFOUND
CONTROL / FALSIFIER THAT EXPOSES IT
RAW ARTIFACTS PRESERVED
PROVENANCE CLASS OF THE RESULT
```

Existing examples to ground against:
[the E0 characterization contract](hardware/TTP_E0_ADC_CHARACTERIZATION.md), the
[E1 rig protocol](NSF_TTP_E1_RIG_CHARACTERIZATION_PROTOCOL.md), and the
acquisition budget's provenance handling. None of their exact structures is
universal; take the shape that fits the experiment.

### Physical experiments

A physical-experiment PR distinguishes specimen state, fixture state, hardware
configuration, software version, environment, raw observation, derived result,
and interpretation.

For longitudinal wood experiments, construction states — joined plate,
thicknessing pass, braces installed, brace carve state, body attachment, bridge
installation — are **recorded conditions, not verdicts.** Recording that braces
were installed says nothing about whether the result was good.

## Hardware PRs

A hardware PR is review-ready when it makes clear what is specified, what is
candidate, what is selected, what is owned, what is absent, what is assembled,
what was tested, and what remains untested.

Two promotions to watch for, both real:

```text
TPA31xx = candidate/reference family    must NOT become
TTP production amplifier = TPA3116D2    without the selection gate

DAEX25FHE-4 rated at 24 W               must NOT become
TTP requires a 24 W amplifier
```

## Synthetic fixtures

A synthetic fixture must be unmistakable. `EvidenceOrigin.SYNTHETIC` exists for
this, sessions under `runs_phase2/` carry `"synthetic": true`, and the report
builders refuse to describe anything but `HARDWARE` as hardware evidence. A new
fixture that could be mistaken for a bench capture, a calibration result, or a
production session needs a discriminator before it lands.

## Admission states

```text
DRAFT / INVESTIGATING     work in progress, claims not yet bounded
READY FOR REVIEW          claims bounded to their evidence
```

A PR is **not** ready for review merely because:

```text
pytest green · pre-commit green · schemas valid · working tree clean · checker green
```

Those establish that the software does what it was written to do. For
evidence-bearing work, readiness also requires that material claims are
identified, evidence sources are named, observation is separated from inference,
provenance is explicit, scope is bounded, known limitations are visible,
unresolved evidence states remain unresolved, and no hardware or scientific
authority was silently promoted.

**A PR may be ready for review with its central question unanswered.** DO-108P is
the worked example: architecture specified, candidates registered, datasheets
verified, requirements documented, tests green — and enclosure unmeasured, exciter
unqualified, required power unmeasured, EMI uncharacterized. Documentation work
`PASS`; PCB evidence gate `BLOCKED`. Both statements are true at once, and a
protocol that forced them into one verdict would have produced a false one.

## What automation may and may not do

A checker may verify **form**:

```text
claim identifier present · claim class present · source/instrument present
observation present · scope present · limitation present · falsifier present
evidence reference present · provenance value is legal for its authority
a NOT_EXECUTED record carries no measured result
a synthetic record is visibly synthetic
```

A checker may **not** decide:

```text
whether an equation is scientifically correct
whether a transducer is suitable
whether a mode identification is physically valid
whether a conclusion follows from the dataset
whether a brace modification is good
whether an uncertainty model is authoritative
```

Those are review questions. Automating them would move the original problem into
the checker: a machine making claims stronger than its evidence supports.

### What is automated today

One thing, and only because it is objective: the vocabulary map above is checked
against the live enums by
[`tests/test_pr_admission_protocol.py`](../tests/test_pr_admission_protocol.py).
If `Provenance`, `CapabilityStatus`, `EvidenceOrigin`, `HardwareVerification`,
`ExperimentOutcomeStatus`, or the E1 checker's constants change, this document
fails the test rather than silently going stale. That makes the reuse mechanical
instead of aspirational.

**No PR body is parsed, no CI workflow is added, and no required check is
changed.** A PR body is not in the repository, so a local checker cannot read
one, and reaching for the GitHub API to fetch it would expand enforcement well
past what this increment authorizes.

## Enforcement and scope maturity

The two axes move independently:

```text
SCOPE:        LOCAL → CANDIDATE → GENERAL          currently LOCAL
ENFORCEMENT:  PROSE → OBSERVATIONAL → ADVISORY → BLOCKING   currently PROSE
```

Advancing enforcement requires evidence that the discipline works, not that
people complied with it. The measure:

```text
CLAIM-CORRECTION RATE

  evidence-bearing PRs requiring post-review correction
  because claim strength exceeded evidence
  ÷ evidence-bearing PRs reviewed
```

Counted by hand while the number is small. No analytics infrastructure is built
for this, and **process compliance is not the same as engineering
effectiveness** — a repository where every template is filled in and claims still
outrun evidence has satisfied the form and failed the point.

## Grounding report

Recorded as required before construction.

### Substantially equivalent mechanism?

**None found.** `grant_readiness` is the closest — it validates capability
claims, refuses unwitnessed hardware claims, and separates fixture from hardware
evidence — but it governs **run, study and campaign records**, not pull requests.
The E1 checker governs **hardware documents**. `advisory_boundary_guard`,
`guidance_language_guard` and `no_logic_creep` are PR-level CI gates but police
the measurement boundary, not claim strength. No PR-readiness or claim-record
mechanism exists.

### Siting

No `docs/governance/` exists and none was created — inventing a governance root
is a stop condition. This document sits at `docs/` root beside the other
authority documents (`ACQUISITION_BUDGET_AUTHORITY.md`, `BOUNDARY_RULES.md`,
`MEASUREMENT_BOUNDARY.md`). The claim record goes to the standard GitHub
location. `CONTRIBUTING.md` already owns a *Pull Requests* section and gains a
pointer rather than a copy.

No ADR was written. This is process discipline, not an architectural decision
about the instrument — and the next ADR number is contested by open PR #39.

### Overlap risks accepted

- **"Derived" is overloaded** across ADR-0012 and `Provenance`. Documented above
  rather than renamed; renaming either would edit an authority this protocol does
  not own.
- **The capability matrix's four axes** overlap this document's axis discussion.
  Deliberate: it is cited as the owner, not restated.
- **This document could go stale** against the enums it maps. That is the one
  risk automation addresses.

### Deliberately left to reviewer judgment

Whether a claim is "material"; whether a stated limitation is the *right*
limitation; whether a falsifier would actually falsify; whether an inference
follows from its observation. All four are semantic, and a machine deciding them
would be the failure this protocol names.
