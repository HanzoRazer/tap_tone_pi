# INSTRUMENT CLASS: MEASUREMENT
"""Grant-readiness evidence support (DO-102).

This package prepares a defensible, traceable answer to a small set of
questions: what the current prototype does, which capabilities are implemented
as opposed to experimental, partial, or planned, how much repeated measurements
of one point varied, which runs failed and why, and which technical
uncertainties remain unresolved.

It is an evidence-support package, not a grant-writing engine and not a
measurement engine. It consumes what the measurement pipeline already produced
and adds no signal processing of its own — no FFT, no capture, no peak picking,
and no change to any existing measurement output.

Two boundaries are load-bearing:

**Repeatability is not accuracy.** Nothing here converts observed spread into an
accuracy, calibration, or laboratory-equivalence claim. Agreement with a
reference method has not been established and cannot be inferred from repeated
observations of the same instrument by the same instrument.

**Fixture data is not hardware evidence.** Every run and study carries its
:class:`~.contracts.EvidenceOrigin`, and the report builders refuse to describe
anything but ``HARDWARE`` as hardware evidence. DO-103 §5.4 makes that claim
*derived* rather than declared: a ``HARDWARE`` run must carry the acquisition
provenance in :class:`~.contracts.AcquisitionProvenanceV1`, so an operator
cannot turn fixture data into hardware evidence by choosing a label. The
physical campaign is a separately witnessed execution gate that has not run,
and no study in this repository is hardware evidence today.

The public surface is the evidence vocabulary plus the ``audit``, ``experiment``,
``statistics``, ``validation``, ``report``, and ``pitch_source`` modules.
"""

from tap_tone_pi.grant_readiness.contracts import (
    AUDIT_SCHEMA_VERSION,
    KNOWN_ACQUISITION_QUANTITIES,
    KNOWN_EXCITATION_METHODS,
    MECHANICAL_FRF_NAMES,
    STUDY_SCHEMA_VERSION,
    AcquisitionChannelV1,
    AcquisitionProvenanceV1,
    AcquisitionRole,
    CapabilityEvidenceV1,
    CapabilityStatus,
    EnvironmentalContextV1,
    EvidenceOrigin,
    ExcitationContextV1,
    GrantReadinessAuditV1,
    HardwareVerification,
    ObservedFeatureV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    ReferenceMethodV1,
    ReferenceValidationPlanV1,
    RejectionReason,
    RepeatabilityMetricV1,
    RepeatabilityStudyV1,
    RiskStatus,
    TechnicalRiskV1,
)
from tap_tone_pi.grant_readiness.errors import (
    CapabilityAuditError,
    EvidenceLinkageError,
    ExperimentRecordError,
    GrantReadinessError,
    GrantReadinessErrorCode,
    RepeatabilityStatisticsError,
)

__all__ = [
    # Schema identities
    "AUDIT_SCHEMA_VERSION",
    "STUDY_SCHEMA_VERSION",
    "KNOWN_EXCITATION_METHODS",
    "KNOWN_ACQUISITION_QUANTITIES",
    "MECHANICAL_FRF_NAMES",
    # Vocabularies
    "CapabilityStatus",
    "HardwareVerification",
    "EvidenceOrigin",
    "AcquisitionRole",
    "RejectionReason",
    "RiskStatus",
    # Evidence records
    "CapabilityEvidenceV1",
    "GrantReadinessAuditV1",
    "EnvironmentalContextV1",
    "ExcitationContextV1",
    "PreliminaryExperimentDefinitionV1",
    "ObservedFeatureV1",
    "AcquisitionChannelV1",
    "AcquisitionProvenanceV1",
    "PreliminaryExperimentRunV1",
    "RepeatabilityMetricV1",
    "RepeatabilityStudyV1",
    "TechnicalRiskV1",
    "ReferenceMethodV1",
    "ReferenceValidationPlanV1",
    # Errors
    "GrantReadinessErrorCode",
    "GrantReadinessError",
    "CapabilityAuditError",
    "ExperimentRecordError",
    "RepeatabilityStatisticsError",
    "EvidenceLinkageError",
]
