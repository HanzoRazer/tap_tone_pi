# NSF Project Pitch — Source Material

**This is not a submission.** It is repository evidence organized under the four
Project Pitch headings, for a human to draft from. Market and team sections are
deliberately empty.

**Machine-readable source:** regenerate with
`python scripts/nsf_ttp_build_pitch_source.py --write` (writes
`out/nsf/ttp_pitch_source.json` and `.md`). Pass `--study` to cite a
repeatability study.

**Working frame:** Portable Structural-Acoustic Measurement Platform for
Instrument Manufacturing and Research

**Central Phase I question:**

> Can an affordable, portable measurement system produce repeatable,
> uncertainty-qualified, reference-valid structural-acoustic measurements of
> stringed instruments under realistic shop conditions?

The repository can currently address the first term. It cannot address the
third. That gap is the proposal.

---

## 1. Technology Innovation

Evidence-backed. Every statement below cites a capability, an audit, or a study.

**A working prototype exists.** Of 25 audited instrument-level capabilities, 19
are IMPLEMENTED with code and tests, 2 are EXPERIMENTAL, 4 are PARTIAL, and 0
are PLANNED.
→ `NSF_TTP_TECHNICAL_BASELINE.md`

**The analysis path is end-to-end and contract-governed.** WAV persistence,
spectral analysis with peak extraction, a clipping and low-signal quality gate,
structured session provenance, and evidence export. Structured results validate
against versioned JSON schemas in a registry with declared ownership, and
reanalysis of the same inputs is deterministic.
→ `capability:wav_persistence`, `capability:tap_spectral_analysis`,
`capability:capture_quality_gate`, `capability:session_provenance`,
`capability:viewer_pack_export`, `capability:measurement_workflow_contracts`

**Uncertainty machinery is present rather than aspirational.** GUM-conformant
budgets and propagation, plus a repeatability evidence contract predating this
work. A populated acoustic-chain budget does not yet exist.
→ `capability:uncertainty_quantification`, `capability:repeatability_evidence`

**A guided workflow spine constrains operator procedure deterministically.**
This is the mechanism by which a portable instrument can be used consistently by
a non-specialist, and it is the lever against operator variability (R8).
→ `capability:guided_laboratory`

**Acquisition and excitation are honestly incomplete.** The audio path is
implemented in software and exercised only with simulated input; the intended Pi
and microphone acquisition chain has not been witnessed. The excitation code
describes driven electrical excitation through an output device — the
speaker-air approach now superseded — while the grounded shaker and stinger
contact drive is not built. Both are recorded PARTIAL.
→ `capability:audio_capture`, `capability:controlled_excitation`

**No capability has been witnessed on the intended hardware:** 0 of 25. Stated
plainly because a reviewer would otherwise assume otherwise.
→ `NSF_TTP_TECHNICAL_BASELINE.md`

**A bounded repeatability experiment is defined and its analysis path is proven
end to end** against deterministic non-hardware fixtures, with every statistic
traceable to the runs that produced it and every rejected run accounted for.
This is not hardware evidence.
→ `NSF_TTP_PRELIMINARY_EXPERIMENT.md`

---

## 2. Technical Objectives and Challenges

Each unresolved question below is a candidate Phase I objective. None is closed,
and **none has a success threshold attached** — DO-102 deliberately sets no
target repeatability or agreement figure, because the baseline observations that
would justify one do not exist yet. Inventing a number to satisfy a proposal
form would be the exact failure this evidence layer is built to prevent.

Repeatability and accuracy are distinguished throughout. Observed spread
describes agreement of the method with itself; agreement with an accepted
reference is unestablished and cannot be inferred from it.

| Risk | Unresolved question |
| --- | --- |
| R1 | How much of observed spread comes from the excitation rather than the instrument? |
| R2 | How sensitive is the result to microphone position, and what tolerance does a shop procedure need? |
| R3 | How much does re-seating the same specimen in the same support change the result? |
| R4 | How much do temperature, humidity, and moisture move the result across a working shop's range? |
| R5 | Does peak detection identify the same feature across repeats, or does feature identity drift? |
| R6 | When can an extracted feature be attributed to a structural mode, and with what confidence? |
| R7 | How stable is an estimated Q across repeats, and how does that depend on excitation and SNR? |
| R8 | How much does the result change with the operator, and how much does a guided procedure remove? |
| R9 | How much does the result drift between sessions separated by hours, days, or a teardown? |
| R10 | How closely does the system agree with an accepted reference method? |

Full statements of what is known, what is unknown, and what would settle each:
`NSF_TTP_PHASE_I_TECHNICAL_RISKS.md`.

**R10 is the load-bearing one.** Every other risk could be settled and the
system would still be a repeatable instrument of unknown validity. The pathway
that would close it — which reference method, in what order, under what
protocol — is in `NSF_TTP_REFERENCE_VALIDATION_PLAN.md`. No comparison has been
performed, no partner is confirmed, and no reference instrument is owned.

---

## 3. Market Opportunity

**Not generated.** No market claim is derivable from this repository, and none
has been invented. Every field below requires human input:

- `customer_segments` — [HUMAN INPUT REQUIRED]
- `customer_discovery_status` — [HUMAN INPUT REQUIRED]
- `market_size_evidence` — [HUMAN INPUT REQUIRED]
- `competing_approaches` — [HUMAN INPUT REQUIRED]
- `pricing_model` — [HUMAN INPUT REQUIRED]
- `commercialization_path` — [HUMAN INPUT REQUIRED]

Customer discovery, market-size modeling, and pricing are explicit DO-102
non-goals. A placeholder that survives to submission is a missing answer, which
is the correct failure mode; a fabricated one would not be detectable.

---

## 4. Company and Team

**Not generated.** Every field below requires human input:

- `principal_investigator` — [HUMAN INPUT REQUIRED]
- `relevant_technical_experience` — [HUMAN INPUT REQUIRED]
- `domain_expertise` — [HUMAN INPUT REQUIRED]
- `advisors_and_collaborators` — [HUMAN INPUT REQUIRED]
- `company_status` — [HUMAN INPUT REQUIRED]

---

## Drafting notes

Three things this material should not be allowed to become in drafting:

1. **A feature list.** The evidence hierarchy runs existing capability →
   observed experiment → measured limitation → unresolved risk → Phase I
   objective. Repository features are the starting point, not the argument.
2. **An accuracy claim.** Nothing here supports one. If a draft sentence
   contains "accurate to", "calibrated", or "validated against", it is not
   supported by this repository.
3. **A hardware claim.** No capability has been witnessed on the intended
   configuration. Any sentence implying a demonstrated shop-floor measurement is
   unsupported until the deferred hardware campaign runs.

---

*Related: `NSF_TTP_TECHNICAL_BASELINE.md`,
`NSF_TTP_PRELIMINARY_EXPERIMENT.md`, `NSF_TTP_PHASE_I_TECHNICAL_RISKS.md`,
`NSF_TTP_REFERENCE_VALIDATION_PLAN.md`.*
