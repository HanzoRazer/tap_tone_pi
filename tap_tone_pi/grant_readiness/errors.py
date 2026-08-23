# INSTRUMENT CLASS: MEASUREMENT
"""Stable error vocabulary for grant-readiness evidence (DO-102).

Every grant-readiness failure carries a stable ``NSF-*`` code so callers and
tests can assert on the code rather than on prose. Codes are grouped by the
layer that raises them:

  ``NSF-1xx``  capability audit (inventory authoring, evidence claims)
  ``NSF-2xx``  experiment definitions and experimental runs
  ``NSF-3xx``  descriptive statistics and reporting
  ``NSF-4xx``  evidence linkage and digests
  ``NSF-5xx``  hardware characterization campaign (DO-103)

Error context is always JSON-serializable and never contains a host path.
Repository-relative paths are permitted — they are evidence — but an absolute
path resolved on the machine that ran the audit is not.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class GrantReadinessErrorCode(str, Enum):
    """Stable identifiers for grant-readiness failures."""

    # -- Capability audit --------------------------------------------------
    INVALID_CAPABILITY_STATUS = "NSF-101"
    MISSING_IMPLEMENTATION_EVIDENCE = "NSF-102"
    CONTRADICTORY_CAPABILITY_CLAIM = "NSF-103"
    # DO-102 requires a rejection for a repeated capability but names no code
    # for it. Two entries sharing an identifier make the audit's own ordering
    # meaningless and let one claim shadow another.
    DUPLICATE_CAPABILITY_ID = "NSF-104"
    # An evidence path that does not resolve against the repository. Distinct
    # from NSF-102 (nothing declared at all) so a typo is not reported as an
    # undocumented capability.
    UNRESOLVED_EVIDENCE_PATH = "NSF-105"
    # A hardware-verification state outside the known vocabulary, including any
    # attempt to claim witnessed hardware execution DO-102 did not perform.
    INVALID_HARDWARE_VERIFICATION = "NSF-106"

    # -- Experiment and runs -----------------------------------------------
    INVALID_EXPERIMENT_DEFINITION = "NSF-201"
    INSUFFICIENT_REPEAT_COUNT = "NSF-202"
    DUPLICATE_RUN_ID = "NSF-203"
    SOURCE_ARTIFACT_MISSING = "NSF-204"
    INVALID_REJECTION_REASON = "NSF-205"
    # A run that belongs to a different experiment than the study it is being
    # collected into. Without this the study's own identity stops meaning
    # anything and its statistics mix measurement points.
    EXPERIMENT_ID_MISMATCH = "NSF-206"
    # A timestamp that is not an ISO-8601 UTC instant. Recorded conditions are
    # only evidence if the time they were recorded at is unambiguous.
    TIMESTAMP_NOT_UTC = "NSF-207"

    # -- Statistics and reporting ------------------------------------------
    INSUFFICIENT_VALID_MEASUREMENTS = "NSF-301"
    INCOMPATIBLE_MEASUREMENT_UNITS = "NSF-302"
    NON_FINITE_STATISTIC = "NSF-303"
    UNDEFINED_COEFFICIENT_OF_VARIATION = "NSF-304"
    # A report asked to present non-hardware data as hardware evidence, or a
    # study whose runs disagree with each other about their own origin. This is
    # the code behind DO-102's acceptance criterion that no generated report may
    # represent fixture or synthetic data as hardware evidence.
    EVIDENCE_ORIGIN_MISREPRESENTED = "NSF-305"
    # A HARDWARE origin claimed without the acquisition provenance DO-103 §5.4
    # requires. Distinct from NSF-305, which fires when a label contradicts the
    # contents it describes: this one fires when the label has nothing behind
    # it at all. Keeping them apart is what lets a reviewer tell a mislabelled
    # study from an unsubstantiated one.
    HARDWARE_PROVENANCE_INCOMPLETE = "NSF-306"
    # Hardware-origin data that is not part of a witnessed session. DO-103 §5.4
    # holds these as two different standards — every witnessed run is
    # hardware-origin, not every hardware-origin run is witnessed — and §10
    # promotes a capability only on the stricter one.
    HARDWARE_SESSION_NOT_WITNESSED = "NSF-307"
    # An acoustic-response transfer function named as a mechanical frequency
    # response. DO-103 §6.6: p/F is not mobility, accelerance, or receptance,
    # and the distinction is carried in the records rather than only the prose
    # so a later reader cannot lose it by reading the data instead.
    MECHANICAL_FRF_MISNAMED = "NSF-308"

    # -- Evidence linkage --------------------------------------------------
    # -- Hardware characterization campaign (DO-103) -----------------------
    # A campaign describes a physical arrangement and a plan; these codes fire
    # on what that description cannot support. None of them is a measurement
    # verdict: DO-103 §5.5 forbids inventing the acceptance figures this
    # campaign exists to produce evidence for, so nothing below compares an
    # observed value against a limit.
    CAMPAIGN_CONFIGURATION_INVALID = "NSF-501"
    # A run's campaign condition does not carry what its experiment kind needs
    # to be grouped: an attachment identity for E3, a point pair for E4, a
    # measured mass for E5.
    CAMPAIGN_CONDITION_INCOMPLETE = "NSF-502"
    # A reciprocity direction with no counterpart. One direction alone is a
    # measurement, not a reciprocity observation.
    RECIPROCITY_PAIR_INCOMPLETE = "NSF-503"
    # Two runs offered as a reciprocity pair that are not transposes of each
    # other. Distinct from NSF-503 so a mispaired run is not reported as a
    # missing one.
    RECIPROCITY_POINTS_MISMATCHED = "NSF-504"
    # A mass challenge carrying only its intended mass. DO-103 §4.7: the
    # nominal value may not stand in for the measured one.
    MASS_CHALLENGE_UNMEASURED = "NSF-505"
    # One challenge identifier used for two different measured masses, which
    # would make the grouping ambiguous and the delta meaningless.
    DUPLICATE_MASS_CHALLENGE = "NSF-506"
    # Loaded runs with no unloaded baseline to compare them against.
    MASS_BASELINE_MISSING = "NSF-507"
    # An external artifact reference that cannot identify what it points at.
    ARTIFACT_IDENTITY_INCOMPLETE = "NSF-508"
    # An artifact whose durable identity is a path on the machine that captured
    # it. The digest is the identity; a path is where a copy happened to sit.
    ARTIFACT_IDENTITY_NOT_PORTABLE = "NSF-509"
    # A channel claiming traceable calibration with nothing to trace it to.
    CALIBRATION_TRACEABILITY_UNSUPPORTED = "NSF-510"
    # A recorded stinger or contact-assembly mass that is not a mass. DO-103
    # §4.9 asked for these to be measured rather than estimated; a negative one
    # is a recording error, not a small mass.
    INVALID_CONTACT_ASSEMBLY_MASS = "NSF-511"
    # An acquisition order that cannot order anything: a repeated index, or one
    # that contradicts the clock. Either makes a drift observation unreadable.
    INVALID_RUN_SEQUENCE = "NSF-512"
    # A recorded frequency offset that its own nominal and actual frequencies do
    # not produce, or one recorded where they are unknown. A derived value that
    # can disagree with its sources is worse than no derived value: it reads as
    # corroboration while contradicting the evidence underneath it.
    FREQUENCY_OFFSET_NOT_DERIVED = "NSF-513"

    UNRESOLVED_EVIDENCE_REFERENCE = "NSF-401"
    EVIDENCE_DIGEST_MISMATCH = "NSF-402"


class GrantReadinessError(Exception):
    """Base class for every grant-readiness failure.

    Attributes:
        code: Stable ``NSF-*`` identifier.
        message: Human-readable description.
        context: JSON-serializable detail about the failure.
    """

    def __init__(
        self,
        code: GrantReadinessErrorCode,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{code.value}] {message}")
        self.code = code
        self.message = message
        self.context: dict[str, Any] = dict(context or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a deterministic dictionary."""
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.context:
            payload["context"] = {k: self.context[k] for k in sorted(self.context)}
        return payload


class CapabilityAuditError(GrantReadinessError):
    """A capability inventory or its evidence is not internally consistent."""


class ExperimentRecordError(GrantReadinessError):
    """An experiment definition or run record is unusable."""


class RepeatabilityStatisticsError(GrantReadinessError):
    """A descriptive statistic cannot be computed or cannot be published."""


class EvidenceLinkageError(GrantReadinessError):
    """An evidence reference does not resolve, or its digest disagrees."""


class HardwareCampaignError(GrantReadinessError):
    """A hardware campaign's configuration or grouping is unusable."""


__all__ = [
    "GrantReadinessErrorCode",
    "GrantReadinessError",
    "CapabilityAuditError",
    "ExperimentRecordError",
    "RepeatabilityStatisticsError",
    "EvidenceLinkageError",
    "HardwareCampaignError",
]
