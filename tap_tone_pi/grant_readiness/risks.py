# INSTRUMENT CLASS: MEASUREMENT
"""Phase I technical risks and reference-validation pathways (DO-102).

The risk register is the honest half of the grant case. Each entry states what
the repository can currently show, what it cannot, and what would settle the
question. None of them is closed, because closing one requires a hardware
campaign that has not run.

The reference-validation plan records prospective comparison methods. No
comparison has been performed, no partner is confirmed, and unknown fields stay
``TBD`` rather than being filled with a plausible guess.
"""

from __future__ import annotations

from tap_tone_pi.grant_readiness.contracts import (
    ReferenceMethodV1,
    ReferenceValidationPlanV1,
    RiskStatus,
    TechnicalRiskV1,
)

TECHNICAL_RISKS: tuple[TechnicalRiskV1, ...] = (
    TechnicalRiskV1(
        risk_id="R1",
        title="Excitation variability",
        current_evidence=(
            "The repository records excitation declaratively "
            "(ExcitationContractV1 for driven sources) but holds no dataset of "
            "repeated excitations at a fixed point. Nothing separates the "
            "contribution of the tap from the contribution of the structure."
        ),
        unresolved_question=(
            "How much of the observed spread in a repeated measurement comes "
            "from the excitation rather than from the instrument or the "
            "analysis?"
        ),
        phase_i_relevance=(
            "This bounds every other repeatability figure. A repeatability "
            "number that does not separate excitation variance is an upper "
            "bound on the method, not a property of the instrument."
        ),
        proposed_validation_method=(
            "Compare repeated manual taps against a driven source at the same "
            "point under the same support, and decompose the variance."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R2",
        title="Sensor and microphone positioning",
        current_evidence=(
            "Sensor position is recorded as a free-text field on the "
            "experiment definition. No study varies it under control, and no "
            "positioning fixture exists."
        ),
        unresolved_question=(
            "How sensitive are the reported quantities to microphone position, "
            "and what positioning tolerance does a shop-usable procedure need?"
        ),
        phase_i_relevance=(
            "Portability is the central claim. If the measurement is strongly "
            "position-dependent, a portable procedure needs a positioning "
            "constraint the current design does not have."
        ),
        proposed_validation_method=(
            "Deliberate displacement of the microphone in known increments, "
            "with repeated captures at each position."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R3",
        title="Support-condition variability",
        current_evidence=(
            "Support condition is recorded as free text. Boundary conditions "
            "are known to dominate plate and body modes, and the repository "
            "holds no dataset varying them."
        ),
        unresolved_question=(
            "How much does re-seating the same specimen in nominally the same "
            "support change the measured result?"
        ),
        phase_i_relevance=(
            "Between-session repeatability cannot be interpreted without it: a "
            "session-to-session difference and a re-seating difference are "
            "indistinguishable in the current evidence."
        ),
        proposed_validation_method=(
            "Repeated removal and replacement of one specimen in one support, "
            "measuring after each replacement."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R4",
        title="Environmental influence",
        current_evidence=(
            "Temperature, relative humidity, and specimen moisture are "
            "recorded where supplied and are never corrected for. No dataset "
            "relates them to measured quantities."
        ),
        unresolved_question=(
            "How much do temperature, humidity, and specimen moisture move the "
            "measured quantities over the range a working shop actually sees?"
        ),
        phase_i_relevance=(
            "Uncontrolled environment could be mistaken for analyzer error. "
            "Until it is characterized, no correction is defensible and none "
            "is applied."
        ),
        proposed_validation_method=(
            "Repeated measurement of one specimen across a recorded range of "
            "conditions, with environment recorded but not corrected."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R5",
        title="Spectral-feature persistence",
        current_evidence=(
            "Peak extraction is implemented and tested against synthetic "
            "signals. No evidence establishes that the same spectral feature is "
            "detected across repeated captures of the same specimen."
        ),
        unresolved_question=(
            "Does peak detection identify the same feature across repeats, or "
            "does feature identity itself drift between captures?"
        ),
        phase_i_relevance=(
            "If features are not stably identified, a frequency spread across "
            "repeats may be measuring detection instability rather than "
            "measurement variation."
        ),
        proposed_validation_method=(
            "Track feature correspondence across a repeated-capture set and "
            "report how often the dominant feature changes identity."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R6",
        title="Mode-identification uncertainty",
        current_evidence=(
            "The Rayleigh-Ritz solver predicts mode shapes, and Phase 2 "
            "produces operational deflection shapes. Nothing in the repository "
            "establishes that an extracted peak corresponds to a predicted "
            "structural mode; peaks are recorded as feature candidates."
        ),
        unresolved_question=(
            "Under what conditions can an extracted spectral feature be "
            "attributed to a specific structural mode, and with what "
            "confidence?"
        ),
        phase_i_relevance=(
            "Mode attribution is what would make the measurement useful for "
            "design decisions rather than only for comparison."
        ),
        proposed_validation_method=(
            "Compare extracted features against an accepted modal analysis of "
            "the same specimen."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R7",
        title="Decay and Q estimation stability",
        current_evidence=(
            "Damping and Q estimation exist and are recorded EXPERIMENTAL: "
            "covered only indirectly by the production-physics suite, with no "
            "dedicated test module and no stability evidence across repeats."
        ),
        unresolved_question=(
            "How stable is an estimated Q across repeated captures, and how "
            "does that stability depend on excitation and signal-to-noise?"
        ),
        phase_i_relevance=(
            "Damping is one of the quantities a luthier would most want. Its "
            "current status does not support reporting it as a measurement."
        ),
        proposed_validation_method=(
            "Repeated captures at controlled signal-to-noise, reporting the "
            "spread of estimated Q against a reference decay."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R8",
        title="Operator variability",
        current_evidence=(
            "Operator identity is recorded on every experiment. The guided "
            "laboratory (DO-100) constrains procedure at the CLI. No dataset "
            "compares operators."
        ),
        unresolved_question=(
            "How much does the result change with the operator, and how much "
            "of that difference does a guided procedure remove?"
        ),
        phase_i_relevance=(
            "A shop-floor instrument is used by whoever is present. Operator "
            "dependence bounds the usable claim."
        ),
        proposed_validation_method=(
            "The same bounded experiment executed by multiple operators, with "
            "and without the guided workflow."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R9",
        title="Between-session repeatability",
        current_evidence=(
            "Session and campaign provenance is implemented. The DO-102 "
            "preliminary experiment is deliberately bounded to a single "
            "session, so it can say nothing about longer intervals."
        ),
        unresolved_question=(
            "How much does the measured result drift between sessions "
            "separated by hours, days, or a full teardown and setup?"
        ),
        phase_i_relevance=(
            "Comparing an instrument before and after a modification is the "
            "core use case, and it is a between-session comparison."
        ),
        proposed_validation_method=(
            "Repeat the bounded experiment across separated sessions with full "
            "teardown between them."
        ),
        status=RiskStatus.OPEN,
    ),
    TechnicalRiskV1(
        risk_id="R10",
        title="Reference-method agreement",
        current_evidence=(
            "No comparison against any reference instrument or accredited "
            "laboratory has been performed. Calibration in this repository "
            "means internal signal-chain consistency, not traceability."
        ),
        unresolved_question=(
            "How closely does the system agree with an accepted reference "
            "method on the same specimen under the same conditions?"
        ),
        phase_i_relevance=(
            "This is the difference between a repeatable instrument and a "
            "valid one. Every other risk can be settled and this one would "
            "still be open."
        ),
        proposed_validation_method=(
            "Side-by-side measurement against a calibrated reference chain; "
            "see the reference-validation plan."
        ),
        status=RiskStatus.OPEN,
    ),
)


REFERENCE_METHODS: tuple[ReferenceMethodV1, ...] = (
    ReferenceMethodV1(
        method="Calibrated measurement microphone",
        measurement_compared="Absolute sound pressure level and frequency response",
        access_status="Not owned; commercially available",
        potential_partner="TBD",
        required_preparation=(
            "Procurement, a documented calibration certificate, and a "
            "comparison procedure at a fixed position"
        ),
        phase_i_role=(
            "Establishes whether the current signal chain's frequency response "
            "is flat enough for the reported quantities"
        ),
    ),
    ReferenceMethodV1(
        method="Accelerometer",
        measurement_compared="Surface acceleration at the measurement point",
        access_status="Not owned",
        potential_partner="TBD",
        required_preparation=(
            "Procurement, mounting method that does not mass-load a thin "
            "plate, and a synchronized acquisition path"
        ),
        phase_i_role=(
            "Cross-checks the acoustic measurement against a direct mechanical "
            "one, separating room effects from structural response"
        ),
    ),
    ReferenceMethodV1(
        method="Instrumented impact hammer",
        measurement_compared="Input force spectrum and transfer function",
        access_status="Not owned",
        potential_partner="TBD",
        required_preparation=(
            "Procurement and a force-window procedure; also closes R1 by "
            "measuring the excitation rather than assuming it"
        ),
        phase_i_role=(
            "Turns an uncontrolled tap into a measured input, which is the "
            "precondition for a defensible transfer function"
        ),
    ),
    ReferenceMethodV1(
        method="Laboratory modal analyzer",
        measurement_compared="Identified modal frequencies, shapes, and damping",
        access_status="No access arranged",
        potential_partner="TBD — university or commercial vibration laboratory",
        required_preparation=(
            "Access agreement, a shared specimen, and an agreed comparison "
            "protocol defined before any measurement is taken"
        ),
        phase_i_role=(
            "The only path that addresses R6: whether an extracted feature is "
            "a structural mode"
        ),
    ),
    ReferenceMethodV1(
        method="Scanning laser vibrometry",
        measurement_compared="Full-field surface velocity and operational shapes",
        access_status="No access arranged",
        potential_partner="TBD",
        required_preparation=(
            "Access agreement and specimen preparation; non-contact, so it "
            "avoids the mass-loading problem an accelerometer introduces"
        ),
        phase_i_role=(
            "Reference for Phase 2 operational deflection shapes, which the "
            "first study deliberately excludes"
        ),
    ),
)


REFERENCE_VALIDATION_NOTES: tuple[str, ...] = (
    "No comparison against any of these methods has been performed. Every "
    "entry is prospective.",
    "No partner is confirmed. Fields recorded TBD are unknown, not pending.",
    "Access to a reference method is a precondition for any accuracy claim. "
    "Until one is arranged, this project can report repeatability and nothing "
    "beyond it.",
)


def build_reference_validation_plan(
    *, plan_id: str, generated_at: str
) -> ReferenceValidationPlanV1:
    """Return the prospective reference-validation plan."""
    return ReferenceValidationPlanV1(
        plan_id=plan_id,
        generated_at=generated_at,
        methods=REFERENCE_METHODS,
        notes=REFERENCE_VALIDATION_NOTES,
    )


__all__ = [
    "TECHNICAL_RISKS",
    "REFERENCE_METHODS",
    "REFERENCE_VALIDATION_NOTES",
    "build_reference_validation_plan",
]
