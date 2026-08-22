# DO-103 — Hardware Measurement Architecture Campaign

## Status

**IN PROGRESS — Stage 3 and Stage 3b complete and frozen. Stages 1, 2, and
4–8 not started; they require hardware that does not yet exist.**

The handoff was reviewed, authorized, and merged as PR #25, which satisfies the
condition this section previously named. Stage 3 was then promoted on its own
(§13), ahead of DO-101B, because it is the one part of this order that is
time-order sensitive: it must exist before any instrument data is collected.

**What Stage 3 delivered.** The Phase 2 transfer-function ingestion path of
§5.1, and the provenance-derived `HARDWARE` claim of §5.4 —
`AcquisitionProvenanceV1` on every run, `NSF-306` refusing a hardware origin
that nothing backs, `NSF-307` holding *witnessed* apart from *hardware-origin*
as §5.4 requires, and `NSF-308` refusing a mechanical frequency-response name
over an acoustic pressure response per §6.6. The study schema gained an
additive optional `acquisition` block; the registry entry moved to 1.1.0. No
existing field changed meaning, and the Phase 1 path is untouched.

**What Stage 3b delivered.** The rest of the software the campaign needs,
written for the same reason and under the same rule: it exists before the rig,
so the campaign is not analyzed by code shaped to fit its results. Additive rig
identity on `ExcitationContextV1`, sensitivity and calibration-traceability
metadata on `AcquisitionChannelV1`, and `CampaignConditionV1` on every run —
which is how §9's ruling is honoured, since attachment identity, a reciprocity
point pair, and a measured added mass are exactly the meanings the DO-102
container cannot carry. On top of them, `hardware_campaign.py` groups the same
runs five different ways, `contracts/ttp_hardware_campaign_v1.schema.json`
persists the campaign accounting the studies cannot hold, and two scripts
assemble and then re-check the result. The study schema moved to registry 1.2.0;
no existing field changed meaning.

**What Stages 3 and 3b deliberately did not do.** They promoted no capability,
changed no capability status, produced no hardware evidence, and filled in no
part of the §8 risk table. Every hardware-dependent capability remains
`NOT_VERIFIED_ON_HARDWARE` and every study this repository can produce is still
`FIXTURE` or `SYNTHETIC`. Nothing in this order's acceptance criteria (§12) is
satisfied by the software alone: §12 criterion 4 requires a witnessed hardware
study, and there is none.

The five decisions in §5 are **resolved and recorded**. They are settled inputs
to implementation, not open questions: the measurement architecture does not get
reopened once work starts.

DO-102 is complete and merged (PR #22 → `3d2eb69`; closure PR #24). It built the
contracts, the audit, the repeatability analysis path, and the reporting, and
proved all of it against deterministic non-hardware fixtures. It executed no
hardware campaign, so every hardware-dependent capability is recorded
`NOT_VERIFIED_ON_HARDWARE` and every study the repository can currently produce
is labelled `FIXTURE` or `SYNTHETIC`.

This Dev Order is the deferred execution gate DO-102 named as `SPRINTS.md`
**B-006**. It is the order that produces the first witnessed hardware evidence.

---

## 1. Objective

Establish a grounded shaker-and-stinger excitation architecture, characterize it
before trusting it, and use it to produce the first witnessed hardware
measurement evidence for the TTP Analyzer — captured into the DO-102
grant-readiness contracts.

The order delivers five bounded experiments, in dependency order:

1. **Fixture and stinger characterization** — what the rig does on its own.
2. **Fixed-point repeatability** — the DO-102 bounded experiment, on hardware.
3. **Detach/reattach repeatability** — what the coupling contributes.
4. **Reciprocity** — an internal validity check that can fail.
5. **Deliberate mass-loading challenge** — a positive control that can fail.

And one governance outcome: capabilities move off `NOT_VERIFIED_ON_HARDWARE`
**only** where witnessed data exists, and only for what was actually exercised.

---

## 2. Measurement Principle

DO-102's central finding is that the repository can show a measurement agreeing
with itself and cannot show it agreeing with anything else. A reference method
(R10) remains inaccessible: none is owned, no partner is confirmed.

This order does not solve that. What it does instead is the next most valuable
thing available without a reference:

> **Replace an uncontrolled excitation with a characterized one, and add checks
> the system can fail.**

Experiments 1–3 reduce and quantify variability. Experiments 4 and 5 are
different in kind: reciprocity and mass-loading are **falsifiable internal
checks**. They do not require an external reference, and they can come out
wrong. A campaign that only ever produces tighter repeatability numbers is not
evidence of validity; a campaign that includes checks capable of failing, and
reports the result either way, is.

This is the honest upgrade DO-102's evidence hierarchy points at:

```text
existing capability → observed experiment → measured limitation
   → unresolved risk → Phase I research objective
```

---

## 3. Architectural Context

### Subsystem

```text
hardware / excitation
capture
measurement
evidence (DO-102 grant_readiness contracts)
```

### Upstream dependencies

- **DO-102** — `tap_tone_pi/grant_readiness/`: `ExcitationContextV1`,
  `PreliminaryExperimentDefinitionV1`, `PreliminaryExperimentRunV1`,
  `RepeatabilityStudyV1`, `EvidenceOrigin`, the audit, and the reporting. This
  order is the consumer those contracts were built for.
- **Existing excitation layer** — `tap_tone_pi/excitation/`:
  `ExcitationContractV1` describes driven electrical excitation (tone, stepped,
  sweep) through an output device. It is recorded `PARTIAL` in the DO-102
  inventory because it describes the superseded speaker-air approach; a driven
  shaker is the case it was *shaped* for even though the mechanism differs.
- **Capture** — `tap_tone_pi/capture/`, recorded `PARTIAL`: implemented in
  software, exercised only with simulated input.

### Downstream consumers

- The DO-102 capability audit and technical baseline, whose hardware-verification
  column this order is the only thing that can change.
- `NSF_TTP_PRELIMINARY_EXPERIMENT.md`, whose "Current execution status" section
  becomes false the moment this order runs.
- Phase I proposal drafting, which currently cannot cite a single hardware
  measurement.

### Constitutional boundary

This order **acquires and characterizes**. It does not interpret.

It may: excite, measure, record conditions, compute the DO-102 descriptive
statistics, report observed variation and observed discrepancy, and state what
each experiment does and does not establish.

It may not: grade an instrument, infer tone quality, prescribe a modification,
claim accuracy, claim calibration, claim laboratory equivalence, or attribute an
extracted spectral feature to a structural mode.

Note that this order introduces **physical hardware** to a repository that has
so far been software only. The measurement boundary is unchanged by that: the
software's job remains capture, deterministic summary, and structured evidence.

---

## 4. Scope

### In scope

1. A grounded shaker mount and stinger coupling, physically built.
2. Characterization of that rig's own dynamics before any instrument measurement.
3. The five experiments in §7.
4. Capture of every experiment into the DO-102 contracts with
   `EvidenceOrigin.HARDWARE`.
5. Witnessing records sufficient to justify a hardware-verified claim.
6. Promotion of specific capability statuses off `NOT_VERIFIED_ON_HARDWARE`,
   limited to what was exercised.
7. A `grant_readiness` ingestion path for the Phase 2 transfer-function result
   (§5.1), alongside the existing Phase 1 path, which is neither removed nor
   changed.
8. Validation tightening so a `HARDWARE` evidence claim is derived from
   acquisition provenance rather than declared by a caller (§5.4).
9. Honest reporting of which DO-102 risks this campaign touches and which it
   leaves untouched.

### Out of scope

- Reference-method comparison of any kind (R10 stays open).
- Calibrated-microphone procurement and acoustic traceability. The microphone is
  the response sensor (§5.3); qualifying it against an acoustic standard is a
  separate matter and is not attempted here.
- Any mechanical frequency-response function — mobility, accelerance,
  receptance. This campaign measures acoustic pressure per unit force (§6.6).
- Formal Gage R&R.
- Modal identification or mode-shape attribution.
- Environmental correction or normalization.
- Multi-instrument or multi-operator campaigns.
- Advisory logic, tone evaluation, design guidance.
- Luthier's Toolbox, MB Sound, Smart Guitar work.
- NSF submission.
- Any change to `tap_tone_pi/grant_readiness/` contract *semantics*. Additive
  fields may be justified; changing what an existing field means is not.

---

## 5. Resolved Decisions

These were genuine forks. Each is now settled. They are recorded here with their
reasoning so implementation does not relitigate them, and so a later reader can
see what was chosen and why.

### Measurement architecture, as resolved

```text
Grounded shaker
      ↓
measured force            ← §5.2
      ↓
light stinger / contact
      ↓
structure
      ↓
microphone response       ← §5.3
      ↓
Phase 2 transfer function + coherence   ← §5.1
      ↓
repeatability / reciprocity / perturbation evidence
      ↓
DO-102 evidence contracts
```

### 5.1 Ingestion path — **RESOLVED: Phase 2**

**Ruling.** Phase 2 is brought into scope. The contact-driver architecture is
fundamentally a driven input/output measurement, so the transfer function and
its coherence belong in the evidence chain rather than being reduced to Phase 1
peak scalars.

DO-102 excluded Phase 2 for sequencing — do not characterize two measurement
architectures at once. That reason expires here: a driven excitation is the case
Phase 2 exists for, and coherence is the per-frequency trust metric that makes
E1 and E4 interpretable. Reducing a driven measurement to scalar peaks would
discard the measurement's own quality indicator at exactly the moment the rig is
least trusted.

**Consequence.** `grant_readiness` gains an ingestion path for the Phase 2
transfer-function result alongside the existing `phase1_tap_analysis_v1` path.
The Phase 1 path is not removed and not changed.

**The change is to ingestion and evidence plumbing, not to the underlying Phase 2
DSP.** "Phase 2 is in scope" means the grant-readiness layer learns to *read* a
transfer-function result; the transfer-function and coherence layer itself is
used as it stands. No new signal processing is authorized by this order — see
§15, which says the same thing from the other direction.

### 5.2 Input force — **RESOLVED: measure it**

**Ruling.** Force is measured. A repeatable drive voltage alone is insufficient.

This is what lets E1 **address** R1 rather than merely narrowing it. An
unmeasured but repeatable drive reduces variability without ever quantifying the
input; a measured force makes the input a known quantity, which is the
precondition for a defensible transfer function.

**Consequence.** Force sensing at the drive point — an impedance head or in-line
force transducer — is a prerequisite of the campaign, not an optional
enhancement. The force channel is recorded as a measurement channel with its own
provenance.

### 5.3 Response sensor — **RESOLVED: microphone**

**Ruling.** The microphone is the primary response sensor.

An accelerometer would add mass to the plate while E5 is explicitly
investigating mass-loading sensitivity — the instrument would be perturbing the
exact quantity the experiment is designed to detect. The microphone is
non-contact and is the path the repository already has.

**Consequence — and this must not be blurred.** See §6.6. A microphone response
divided by a measured force is **not** mechanical mobility.

### 5.4 What makes a measurement witnessed — **RESOLVED: derived, not declared**

**Ruling.** A witnessed hardware acquisition requires an actual physical session
whose provenance is sufficient to distinguish it from fixture or synthetic data:

- hardware identifiers (shaker, force transducer, microphone, interface);
- acquisition configuration (sample rate, channel map, gain, drive parameters);
- experiment, session, and run identifiers;
- UTC timestamps;
- excitation and response channel identification;
- environmental observations where available, unknown where not;
- raw measurements retained, including from rejected runs;
- `evidence_origin` explicitly `HARDWARE`.

**The software derives the claim from the evidence record.** An operator must
not be able to turn fixture data into hardware evidence by choosing a label.

**Hardware origin and witnessed status are not the same thing, and the document
uses them as two different standards.** `EvidenceOrigin.HARDWARE` is an
*acquisition-origin classification*: this data came off physical instruments
rather than a fixture or a generator. A *witnessed session* is the stronger
governance condition — the provenance above, recorded, retained, and attributable
— and it is what §10 requires before a capability may be promoted. Every
witnessed run is hardware-origin; not every hardware-origin run is necessarily
part of a witnessed session. Where the two diverge, promotion follows the
stricter one.

This is a real change from DO-102, and it should be stated as such. Today
`EvidenceOrigin` is caller-supplied, guarded only by refusing `HARDWARE` for a
result marked `demo: true` and by requiring a study's runs to agree with its
label. That is necessary but not sufficient: nothing currently stops a caller
asserting `HARDWARE` over data that simply lacks a demo flag. DO-103 tightens
this so a `HARDWARE` claim fails validation unless the required acquisition
provenance is present. The tightening is additive and does not change what any
existing field means.

### 5.5 Reciprocity and mass loading — **RESOLVED: threshold-free**

**Ruling.** Both stay threshold-free in DO-103. No pass/fail boundary is
invented merely to close the campaign.

What is recorded instead:

- residuals;
- distributions;
- effect sizes;
- frequency-dependent behavior;
- coherence over the compared band;
- full experimental conditions and sample sizes.

Thresholds can be established later from observed measurement capability or from
an external requirement. Establishing one now would mean inventing the very
figure this campaign exists to produce the evidence for — the failure mode
DO-102 §4.11 was written to prevent.

---

## 6. Design Decisions

### 6.1 Characterize the rig before trusting it

E1 runs first and gates the rest. A stinger axial resonance, a mount compliance,
or a shaker suspension mode inside the measurement band will appear in every
subsequent measurement and will look exactly like a structural feature.

The deliverable of E1 is a stated **frequency band of validity** for the rig.
Every later experiment reports its results against that band, and any feature
outside it is reported as rig-suspect rather than silently included.

### 6.2 The stinger is a designed component, not a wire

A stinger transmits axial force while staying laterally compliant, so the shaker
does not impose a moment or a constraint on the structure. Too laterally stiff
and the rig becomes part of the boundary condition; too axially compliant and
the force is not delivered. Its length, diameter, material, and both end
attachments are measurement parameters and are recorded as such in
`ExcitationContextV1.contact_condition` and `fixture_id`.

### 6.3 Grounded means grounded

The shaker reacts against a mass path independent of the instrument and its
support. If the shaker's reaction returns through the same bench that supports
the specimen, the rig and the specimen are coupled and E4 in particular becomes
uninterpretable. Ground path is recorded and is part of what E1 characterizes.

### 6.4 Every run enters the DO-102 contracts unchanged

This order writes measurements into `PreliminaryExperimentRunV1` and
`RepeatabilityStudyV1` as they exist. If a driven measurement genuinely needs a
field those contracts lack, that is an additive change with its own
justification — not a re-interpretation of an existing field.

`ExcitationContextV1` already accommodates this architecture:

```python
ExcitationContextV1(
    excitation_method="shaker_stinger",
    excitation_device_id=...,      # the shaker
    excitation_point=...,          # where the stinger meets the structure
    contact_condition=...,         # stinger spec and both attachments
    fixture_id=...,                # mount and ground path
    excitation_contract_id=...,    # the drive signal, ExcitationContractV1
)
```

### 6.5 Promotion is per-capability and evidence-bound

Running E2 does not make the whole inventory hardware-verified. A capability
moves off `NOT_VERIFIED_ON_HARDWARE` only if it was actually exercised in a
witnessed session, and the audit note records which experiment did it.

The frozen-baseline drift test in `tests/test_nsf_capability_baseline.py` means
any status change must be made in both the inventory and the baseline, and will
fail loudly if made in only one. That is intended.

### 6.6 The measured quantity is acoustic, not mechanical mobility

This is the most important naming decision in the order, and getting it wrong
would quietly poison every later comparison.

With a measured force input and a **microphone** response, the transfer function
is:

```text
H(f) = p(f) / F(f)        acoustic pressure per unit input force,  Pa/N
```

That is an **acoustic-response transfer function relative to a measured force**.
DO-103 therefore initially characterizes the **coupled structural-acoustic
response** of the instrument in its measurement environment — the structure, its
radiation, and the room together.

It is **not** mechanical mobility. Mobility, and its relatives, require the
response quantity to be a mechanical motion of the structure:

| Name | Response quantity | Ratio |
| --- | --- | --- |
| Receptance / compliance | displacement | `x/F` (m/N) |
| Mobility | velocity | `v/F` (m·s⁻¹/N) |
| Accelerance / inertance | acceleration | `a/F` (m·s⁻²/N) |
| **This campaign** | **acoustic pressure** | **`p/F` (Pa/N)** |

**Rules that follow, and they are binding:**

1. No output of this order calls `p/F` mobility, accelerance, receptance, or
   any other mechanical frequency-response function.
2. The quantity is labelled with its units (`Pa/N`) wherever it is reported, and
   named as an acoustic-response transfer function relative to measured force.
3. Any observed feature is a feature of the **coupled** system. Attributing it
   to the structure alone requires evidence this order does not produce — the
   room and the radiation are inside the measurement.
4. This distinction is carried into the evidence records, not only the prose, so
   a later reader cannot lose it by reading the data instead of the document.
5. **Reported units do not imply traceable calibration.** `Pa/N` states what the
   quantity *is*, not that either channel is qualified against a standard. The
   microphone is not a calibrated reference and the force transducer's own
   qualification is not established by this order (§8, R1). A number with units
   is not a traceable number.

**Why it matters later.** Laboratory modal analysis reports mechanical FRFs.
When TTP is eventually compared against such a method (R10), comparing `p/F`
against `v/F` without stating the difference would be a category error that
makes agreement or disagreement equally meaningless. Recording the distinction
now is what keeps that future comparison honest.

It also sharpens what E5 tests: a mass added to the plate perturbs the
structure, and the microphone observes that perturbation *through* the radiation
and the room. A null result in E5 is therefore ambiguous between "the structure
did not change" and "the change did not reach the microphone" — and the order
must report it that way rather than resolving the ambiguity by assertion.

### 6.7 Failed and abandoned runs stay

DO-102's rejection accounting applies unchanged. A run lost to a detached
stinger, an overdriven amplifier, or a clipped channel is recorded with its
reason and counted. A campaign that reports only its successful sessions is not
evidence.

---

## 7. The Five Experiments

### E1 — Fixture and stinger characterization

**Question.** What does the rig do on its own, and over what band can it be
trusted?

**Method.** Drive the shaker with the stinger unattached, then attached to a
reference target of known simple behavior. Characterize shaker suspension
response, stinger axial and lateral modes, mount and ground compliance.

**Output.** A stated frequency band of validity, plus the identified rig
features outside or inside it.

**Gates.** Every subsequent experiment. E1 failing to produce a usable band is a
legitimate outcome and stops the campaign rather than being worked around.

### E2 — Fixed-point repeatability

**Question.** How much does a repeated measurement vary when nothing is
deliberately changed?

**Method.** The DO-102 bounded experiment, executed on hardware: one instrument,
one measurement point, one support condition, one sensor position, one operator,
one session. Repeated captures without touching the setup between them.

**Output.** The first `RepeatabilityStudyV1` with
`evidence_origin=EvidenceOrigin.HARDWARE`. This is the study
`NSF_TTP_PRELIMINARY_EXPERIMENT.md` was written to receive.

**Risks touched.** R5 (feature persistence), R7 (Q stability, if Q is extracted).

### E3 — Detach/reattach repeatability

**Question.** How much of the observed spread is the coupling rather than the
measurement?

**Method.** As E2, but the stinger is detached from the drive point and
reattached between runs, with nothing else changed.

**Output.** A second study. The difference between E3 and E2 spread is the
attachment's contribution, reported as an observed difference under the recorded
conditions — not as a corrected or subtracted term.

**Risks touched.** R1 (narrowed), R3 (attachment portion only — specimen support
is not varied here), R9 (partially; a full between-session question needs
separated sessions).

### E4 — Reciprocity

**Question.** Does the system report the same transfer between two points when
the drive and response are swapped?

**Method.** Drive at A, measure at B. Then drive at B, measure at A. Compare.

**Why it matters.** For a linear, time-invariant, reciprocal structure these
agree. It is an internal validity check that **requires no external reference**
— which is exactly the constraint this project is under while R10 stays open —
and it is capable of failing.

**Output.** The observed discrepancy with its conditions and sample size. Per
§5.5, reported, not graded.

**What a failure would mean.** Non-reciprocity indicates nonlinearity, a
time-varying setup, an ungrounded reaction path, or a coupling that is part of
the structure. Each is diagnostic and each is worth more than a tight
repeatability number.

### E5 — Deliberate mass-loading challenge

**Question.** Does the measurement respond to a change it must respond to?

**Method.** Add a known small mass at a known location. Measure. Remove it.
Measure again. Repeat.

**Why it matters.** A positive control. If adding mass does not move the
measurement, the measurement is not measuring the structure — and that finding
would invalidate more than any repeatability figure could establish. The return
to baseline on removal is as informative as the shift itself.

**Output.** The observed shift and the observed return, with conditions and
sample size. Per §5.5, reported, not graded.

**Risks touched.** R6 indirectly — a mass at a known location perturbs modes
predictably in *direction*, which is weak evidence toward feature attribution,
and must not be reported as identification.

---

## 8. Risk Coverage — honest mapping

What this campaign does and does not do to the DO-102 register. This table is
part of the deliverable, not a summary of it.

| Risk | Effect of this campaign |
| --- | --- |
| R1 excitation variability | **Addressed** by E1+E2+E3 with a **measured** force input (§5.2). The input becomes a known quantity rather than a repeatable unknown. Residual exposure is the force transducer's own qualification, which this order does not establish. |
| R2 sensor positioning | **Not addressed.** Sensor position is held fixed, not varied. |
| R3 support-condition variability | **Partially** — E3 covers the attachment. Specimen support is not varied. |
| R4 environmental influence | **Not addressed.** Conditions recorded, never corrected. |
| R5 spectral-feature persistence | **Addressed** by E2 across repeats. |
| R6 mode-identification uncertainty | **Weakly and indirectly** by E5, and weakened further by §6.6: the response is acoustic, so an observed feature belongs to the coupled structural-acoustic system rather than to the structure alone. Not identification. |
| R7 decay / Q stability | **Addressed** by E2, if Q is extracted. |
| R8 operator variability | **Not addressed.** Single operator by design. |
| R9 between-session repeatability | **Partially** by E3. Full between-session needs separated sessions with teardown. |
| R10 reference-method agreement | **Not addressed at all.** No reference is used. This remains the load-bearing open risk. |

Stating this plainly matters more than the results. A campaign that quietly
implies it resolved more than it did is worse for the proposal than one that
resolved less and said so.

---

## 9. Evidence Capture

Every experiment produces:

- every raw artifact, preserved — including from failed runs;
- one `PreliminaryExperimentDefinitionV1` with the full excitation, sensor,
  support, and environmental context;
- one `PreliminaryExperimentRunV1` per attempt, valid or rejected, with
  `evidence_origin=EvidenceOrigin.HARDWARE`;
- one study record in the DO-102 evidence model, with metrics, run accounting,
  and limitations;
- a witnessing record per §5.4.

### The evidence contracts were shaped for E2, and E1, E4, E5 do not fit cleanly

This needs saying plainly, because an implementer will hit it on day one and
should not have to decide it alone.

`RepeatabilityStudyV1` is the DO-102 evidence container, and it was shaped for
exactly one experiment design: **one instrument, one measurement point, repeated
captures**. That is E2. The other three strain the shape:

- **E1 characterizes the rig, not an instrument.** There is no instrument and no
  measurement point on the specimen. `PreliminaryExperimentDefinitionV1`
  requires both `instrument_id` and `measurement_point_id` as non-empty, so E1
  either records the rig as its own "instrument" — defensible, since that is
  literally what is under test — or needs a different record.
- **E4 compares a point *pair*.** `measurement_point_id` is singular. A
  reciprocity run is drive-at-A/measure-at-B, which is not one point.
- **E4 and E5 are not repeatability studies in plain English.** They are a
  symmetry check and a perturbation check. The container's name implies
  semantics they do not have.

**Ruling for implementation.** Use the DO-102 evidence model as the container
for all five experiments — a second parallel evidence model would be worse than
a slightly over-general name. Where a field genuinely cannot carry the meaning,
add an additive field with its own justification per §6.4; do **not** overload an
existing field to mean something new, and do **not** silently record E1's rig as
though it were the specimen without saying so in the record.

Whether the container should eventually be renamed or generalized is a real
question and is explicitly **deferred**, not answered here. Renaming a published
contract is a schema-versioning decision that belongs to its own order.

Reports are generated with the existing DO-102 builders. Because
`EvidenceOrigin.HARDWARE` is claimed, `validate_study_evidence_origin` and the
renderer will both refuse the study if any run in it is not hardware — which is
the guard working as designed, and is the intended failure mode if fixture data
is ever mixed into a hardware campaign.

---

## 10. Promotion Criteria

A capability moves off `NOT_VERIFIED_ON_HARDWARE` when **all** hold:

1. It was exercised end to end in a witnessed session per §5.4.
2. Its artifacts are preserved and referenced from the capability's
   `evidence_refs`.
3. The experiment that exercised it is named in the capability's `notes`.
4. The change is made in `inventory.py` **and** the frozen baseline together.
5. The generated audit and the technical baseline are regenerated.

Expected candidates, subject to what actually runs: `audio_capture` (currently
PARTIAL, simulated input only), `controlled_excitation` (currently PARTIAL,
superseded abstraction), `phase1_tap_workflow` or the Phase 2 path per §5.1,
`calibration`, and `repeatability_evidence`.

Not candidates on any outcome of this campaign: `desktop_analyzer`,
`http_api_server`, `unified_cli`, `plate_dynamics_prediction`,
`uncertainty_quantification`, and the other `NOT_APPLICABLE` entries. Those have
no hardware dependency to witness, and promoting them would be the exact
category error §6.5 is written to prevent.

---

## 11. Test Plan

Software changes in this order are expected to be small; the campaign is
execution, not construction. Whatever is added carries:

- contract tests for any additive field, matching the DO-102 conventions —
  frozen, no mutable defaults, strict deserialization, deterministic equality;
- ingestion tests for the path chosen in §5.1, including every rejection reason;
- boundary tests extending `tests/test_nsf_grant_readiness_boundary.py`, which
  must continue to pass unchanged in spirit: no DSP, no capture, no advisory
  logic inside `grant_readiness`;
- the drift test between `inventory.py` and the frozen baseline, which will fail
  by design on any one-sided status change;
- regression across the DO-102 suite, the empirical and radiation-ratio suites,
  and the full repository.

Baseline at authorship: two documented failures in `scripts/phase2/tests/`
(archived viewer packs missing a `bending` key), reproducing on base and outside
`tests/` collection.

---

## 12. Acceptance Criteria

DO-103 is complete only when:

1. The rig exists, is grounded, and its band of validity is stated (E1).
2. All five experiments are executed, or downstream experiments are explicitly
   and justifiably not executed because an earlier campaign gate failed. A
   failed E1 is a legitimate experimental result and stops downstream work
   rather than being engineered around — but see criterion 4: it does not by
   itself satisfy completion.
3. Every run — valid, rejected, abandoned — is recorded with its reason.
4. At least one `RepeatabilityStudyV1` carries
   `evidence_origin=EvidenceOrigin.HARDWARE` and validates. This is deliberate
   and interacts with criterion 2: a campaign that stops at a failed E1 has
   produced a real and reportable finding — the rig is unusable as built — but
   it has produced no hardware measurement evidence, so DO-103 is **not**
   complete. Such a campaign closes by revising this order or issuing a
   successor, not by declaring done.
5. Reciprocity and mass-loading results are reported with conditions and sample
   sizes, and **without** invented thresholds.
6. The risk-coverage table in §8 is filled in against what actually happened,
   including the risks left untouched.
7. Capability promotions satisfy every condition in §10, not a subset: exercised
   end to end in a witnessed session; artifacts preserved and referenced from
   the capability's `evidence_refs`; the exercising experiment named in the
   capability's `notes`; the change made in **both** `inventory.py` and the
   frozen baseline; and the audit and technical baseline regenerated.
8. No accuracy, calibration, laboratory-equivalence, or mode-identification
   claim appears anywhere in the outputs, and no output names the measured
   quantity as mobility, accelerance, or receptance (§6.6).
9. Every reported transfer function carries its units (`Pa/N`) and is identified
   as an acoustic response relative to measured force.
10. `NSF_TTP_PRELIMINARY_EXPERIMENT.md`'s execution-status section is updated to
    describe what was run.
11. Governance, schema, and full-suite gates pass; baseline failures are
    reclassified against the then-current `main`.
12. A reviewer can trace every numerical claim to source artifacts and to a
    witnessed session.

---

## 13. Rollout Order

**Stage 0 — Complete.** The five decisions in §5 are resolved and recorded in
this handoff. The measurement architecture is settled and is not reopened during
implementation.

**Stage 1 — Build and ground the rig.** Physical: shaker mount, ground path,
stinger, and force transducer at the drive point. No measurement claims.

**Stage 2 — E1, rig characterization.** Gates everything downstream. A rig with
no usable band stops the campaign.

**Stage 3 — Complete and frozen.** The Phase 2 ingestion path and the
provenance-derived HARDWARE claim, both written and tested **before** any
instrument data is collected, so the campaign is not analyzed by software
written to fit the data it produced.

Delivered as `tap_tone_pi/grant_readiness/phase2_experiment.py`,
`AcquisitionProvenanceV1` and `AcquisitionChannelV1` in `contracts.py`, the
`NSF-306` / `NSF-307` / `NSF-308` validators, and 108 tests across
`tests/test_nsf_hardware_provenance.py` and `tests/test_nsf_phase2_ingestion.py`.

Three implementation rulings were made and are recorded with the code rather
than left for the campaign to decide under pressure:

- **`captured_at` comes from the caller.** A Phase 2 document records when the
  analysis ran, not when the capture happened. Reusing one as the other would
  fabricate provenance.
- **Coherence must be present.** §5.1 chose Phase 2 because coherence travels
  with the transfer function. This is a presence requirement, not a threshold —
  no coherence value is compared against anything, per §5.5.
- **An out-of-range evaluation frequency is a rejected run.** Snapping to an
  edge bin would report a number from a frequency nobody asked about.

One boundary test changed with it. DO-102 asserted that `grant_readiness` never
mentions `phase2_ods_snapshot`; that was a proxy for "authors no existing
measurement schema", and the proxy stopped being right once §5.1 authorized
ingestion. The claim is now made directly — the contract is named only where it
is read, exactly once, as the identity a document is matched against — and the
substantive guards are unchanged: `tap_tone_pi.phase2` is still a forbidden
import and no DSP or capture call site is permitted.

**Deferred out of Stage 3, deliberately.** No capability entry was added for the
Phase 2 evidence path. Adding one would touch `inventory.py` and the frozen
baseline, which belongs with the §10 promotion work in Stage 8 rather than with
plumbing built before any campaign exists.

**Stage 3b — Complete and frozen.** The pre-hardware campaign software, on the
same rule as Stage 3: it lands before the rig so the campaign cannot be analyzed
by code written to fit it.

Delivered as additive fields on the DO-102 records — rig identity
(`stinger_id`, `contact_tip_id`, `rig_configuration_id`), channel sensitivity
and `CalibrationTraceability`, and `CampaignConditionV1` per run — plus
`tap_tone_pi/grant_readiness/hardware_campaign.py` for the E2–E5 groupings,
`GroupSpreadV1` / `AttachmentVariationV1` / `ReciprocityObservationV1` /
`MassLoadingObservationV1` for the comparisons no study record can hold, the
`NSF-5xx` error family, `contracts/ttp_hardware_campaign_v1.schema.json`,
`scripts/ttp_hardware_campaign.py`, the read-only
`scripts/ttp_hardware_campaign_check.py`, and
`docs/NSF_TTP_HARDWARE_CAMPAIGN_PROTOCOL.md`.

Four rulings are recorded with the code:

- **Between-attachment spread does not reuse the run-level metric.** Its samples
  are attachments, not runs, so it is a `GroupSpreadV1` that says so rather than
  a `RepeatabilityMetricV1` whose `source_run_ids` would name things that are
  not runs. That is §9's "add a field, do not overload one" applied to the
  statistics rather than to the records.
- **Every mass comparison needs at least two captures per group.** A delta
  between two single captures cannot be separated from the spread it sits in.
  This is a property of what can be computed, not a quality bar.
- **The artifact digest is the identity.** Raw audio stays outside the
  repository, so a locator that is an absolute host path is refused: the
  reference has to survive the file moving.
- **Traceability is claimed, never defaulted.** `CalibrationTraceability`
  defaults to `UNKNOWN`, and a `TRACEABLE` claim without a calibration reference
  is `NSF-510`. No sensor sensitivity or unit is assumed ahead of choosing a
  transducer.

The campaign record carries `CampaignExecutionStatus`, so §12 criterion 11 —
an experiment not executed because an earlier gate failed — is representable
rather than an absence a reader has to interpret. The repository's own campaign
document is `NOT_EXECUTED`.

**Stage 4 — E2, fixed-point repeatability.** The first hardware study.

**Stage 5 — E3, detach/reattach.**

**Stage 6 — E4, reciprocity.** The first experiment that can falsify.

**Stage 7 — E5, mass-loading challenge.**

**Stage 8 — Evidence, promotion, and reporting.** Promote only what was
witnessed, and only through the full §10 rule: attach preserved artifacts to
`evidence_refs`, name the exercising experiment in the capability's `notes`,
change `inventory.py` and the frozen baseline together, and regenerate the audit
and the technical baseline. Fill in §8 against what actually happened, including
the risks left untouched.

**Stage 9 — Verification and PR.** Governance gates (advisory boundary,
guidance language), schema validation, the DO-102 and empirical/radiation-ratio
suites, the full repository suite, and reclassification of baseline failures
against the then-current `main`.

---

## 14. Risks to This Order

**The rig has a resonance in band.** Likely, and E1 exists to find it. Control:
E1 gates the campaign; a band of validity is stated, not assumed.

**Reciprocity fails.** Possible, and it is a *result*. Control: report it. The
temptation to treat a failed internal check as a setup problem to be tuned away
until it passes is the single largest scientific-integrity risk in this order.

**Mass loading produces no detectable shift.** Also a result, and a serious one.
Control: report it; do not increase the mass until something moves and then
report only that.

**The acoustic transfer function gets called mobility.** The single likeliest
documentation failure, because `response/force` reads like an FRF and the
vocabulary is close at hand. Control: §6.6 states the rule, the units `Pa/N`
travel with the quantity, and the distinction is carried in the evidence records
rather than only the prose.

**Force is measured but the transducer is unqualified.** Measuring force makes
the input known relative to that transducer; it does not make it traceable.
Control: §8's R1 row states the residual exposure rather than reporting R1 as
fully closed.

**Scope creep into modal identification.** A shaker rig makes modal analysis
feel close. It is not in scope and cannot be, without a reference.

**Promotion overreach.** The pressure to mark capabilities hardware-verified
because a campaign ran is real. Control: §10's five conditions, plus the frozen
baseline drift test.

---

## 15. Constitutional Impact

**Subsystem:** hardware, excitation, capture, evidence
**Public API:** additive at most
**Schema:** additive at most; no existing field changes meaning
**Measurement:** new acquisition architecture; existing calculations unchanged
**Signal processing:** unchanged — the Phase 2 path (§5.1) uses the existing
transfer-function and coherence layer as-is; no new DSP is authorized
**Interpretation:** unchanged
**Advisory behavior:** unchanged
**Uncertainty:** observed variation extended to hardware; no budget claimed
**Evidence:** first hardware-origin records
**GUI / server:** unchanged
**Governance:** extended — first capability promotions off
`NOT_VERIFIED_ON_HARDWARE`
**Scientific validity:** improved by characterized excitation and two falsifiable
checks; reference validity (R10) untouched

---

## 16. Non-Goals

Reference-laboratory comparison; calibrated-reference traceability; modal
identification; Gage R&R; environmental correction; multi-instrument or
multi-operator campaigns; tone evaluation; design guidance; material ranking;
formula fitting; NSF submission; and any change to the meaning of an existing
DO-102 contract field.

---

## 17. Definition of Done

DO-103 is complete when the repository can answer, from witnessed evidence:

> What does the excitation rig itself do, and over what band?

> How much does a repeated measurement vary when nothing changes?

> How much of that variation is the coupling?

> Does the system report the same transfer when drive and response are swapped?

> Does the measurement respond to a deliberate, known change?

> Which capabilities can now honestly claim hardware verification — and which
> still cannot?

> Which DO-102 risks did this campaign move, and which did it leave exactly
> where they were?

And when the answer to the last question is written down even where it is
unflattering.

---

*Predecessor: DO-102 (COMPLETE, PR #22 → `3d2eb69`). Deferred gate:
`SPRINTS.md` B-006. Related: `docs/NSF_TTP_PRELIMINARY_EXPERIMENT.md`,
`docs/NSF_TTP_PHASE_I_TECHNICAL_RISKS.md`,
`docs/NSF_TTP_REFERENCE_VALIDATION_PLAN.md`.*
