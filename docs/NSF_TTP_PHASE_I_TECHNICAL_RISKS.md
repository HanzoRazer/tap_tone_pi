# Phase I Technical Risks

Each entry states what is known, what is not, and what would settle it. An open risk is not a defect; it is the reason Phase I research is needed.

## R1 — Excitation variability

- Status: OPEN

**What is known.** The repository records excitation declaratively (ExcitationContractV1 for driven sources) but holds no dataset of repeated excitations at a fixed point. Nothing separates the contribution of the tap from the contribution of the structure.

**What is unknown.** How much of the observed spread in a repeated measurement comes from the excitation rather than from the instrument or the analysis?

**Why Phase I needs it.** This bounds every other repeatability figure. A repeatability number that does not separate excitation variance is an upper bound on the method, not a property of the instrument.

**Proposed test.** Compare repeated manual taps against a driven source at the same point under the same support, and decompose the variance.

## R2 — Sensor and microphone positioning

- Status: OPEN

**What is known.** Sensor position is recorded as a free-text field on the experiment definition. No study varies it under control, and no positioning fixture exists.

**What is unknown.** How sensitive are the reported quantities to microphone position, and what positioning tolerance does a shop-usable procedure need?

**Why Phase I needs it.** Portability is the central claim. If the measurement is strongly position-dependent, a portable procedure needs a positioning constraint the current design does not have.

**Proposed test.** Deliberate displacement of the microphone in known increments, with repeated captures at each position.

## R3 — Support-condition variability

- Status: OPEN

**What is known.** Support condition is recorded as free text. Boundary conditions are known to dominate plate and body modes, and the repository holds no dataset varying them.

**What is unknown.** How much does re-seating the same specimen in nominally the same support change the measured result?

**Why Phase I needs it.** Between-session repeatability cannot be interpreted without it: a session-to-session difference and a re-seating difference are indistinguishable in the current evidence.

**Proposed test.** Repeated removal and replacement of one specimen in one support, measuring after each replacement.

## R4 — Environmental influence

- Status: OPEN

**What is known.** Temperature, relative humidity, and specimen moisture are recorded where supplied and are never corrected for. No dataset relates them to measured quantities.

**What is unknown.** How much do temperature, humidity, and specimen moisture move the measured quantities over the range a working shop actually sees?

**Why Phase I needs it.** Uncontrolled environment could be mistaken for analyzer error. Until it is characterized, no correction is defensible and none is applied.

**Proposed test.** Repeated measurement of one specimen across a recorded range of conditions, with environment recorded but not corrected.

## R5 — Spectral-feature persistence

- Status: OPEN

**What is known.** Peak extraction is implemented and tested against synthetic signals. No evidence establishes that the same spectral feature is detected across repeated captures of the same specimen.

**What is unknown.** Does peak detection identify the same feature across repeats, or does feature identity itself drift between captures?

**Why Phase I needs it.** If features are not stably identified, a frequency spread across repeats may be measuring detection instability rather than measurement variation.

**Proposed test.** Track feature correspondence across a repeated-capture set and report how often the dominant feature changes identity.

## R6 — Mode-identification uncertainty

- Status: OPEN

**What is known.** The Rayleigh-Ritz solver predicts mode shapes, and Phase 2 produces operational deflection shapes. Nothing in the repository establishes that an extracted peak corresponds to a predicted structural mode; peaks are recorded as feature candidates.

**What is unknown.** Under what conditions can an extracted spectral feature be attributed to a specific structural mode, and with what confidence?

**Why Phase I needs it.** Mode attribution is what would make the measurement useful for design decisions rather than only for comparison.

**Proposed test.** Compare extracted features against an accepted modal analysis of the same specimen.

## R7 — Decay and Q estimation stability

- Status: OPEN

**What is known.** Damping and Q estimation exist and are recorded EXPERIMENTAL: covered only indirectly by the production-physics suite, with no dedicated test module and no stability evidence across repeats.

**What is unknown.** How stable is an estimated Q across repeated captures, and how does that stability depend on excitation and signal-to-noise?

**Why Phase I needs it.** Damping is one of the quantities a luthier would most want. Its current status does not support reporting it as a measurement.

**Proposed test.** Repeated captures at controlled signal-to-noise, reporting the spread of estimated Q against a reference decay.

## R8 — Operator variability

- Status: OPEN

**What is known.** Operator identity is recorded on every experiment. The guided laboratory (DO-100) constrains procedure at the CLI. No dataset compares operators.

**What is unknown.** How much does the result change with the operator, and how much of that difference does a guided procedure remove?

**Why Phase I needs it.** A shop-floor instrument is used by whoever is present. Operator dependence bounds the usable claim.

**Proposed test.** The same bounded experiment executed by multiple operators, with and without the guided workflow.

## R9 — Between-session repeatability

- Status: OPEN

**What is known.** Session and campaign provenance is implemented. The DO-102 preliminary experiment is deliberately bounded to a single session, so it can say nothing about longer intervals.

**What is unknown.** How much does the measured result drift between sessions separated by hours, days, or a full teardown and setup?

**Why Phase I needs it.** Comparing an instrument before and after a modification is the core use case, and it is a between-session comparison.

**Proposed test.** Repeat the bounded experiment across separated sessions with full teardown between them.

## R10 — Reference-method agreement

- Status: OPEN

**What is known.** No comparison against any reference instrument or accredited laboratory has been performed. Calibration in this repository means internal signal-chain consistency, not traceability.

**What is unknown.** How closely does the system agree with an accepted reference method on the same specimen under the same conditions?

**Why Phase I needs it.** This is the difference between a repeatable instrument and a valid one. Every other risk can be settled and this one would still be open.

**Proposed test.** Side-by-side measurement against a calibrated reference chain; see the reference-validation plan.
