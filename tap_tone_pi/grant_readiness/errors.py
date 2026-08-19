# INSTRUMENT CLASS: MEASUREMENT
"""Stable error vocabulary for grant-readiness evidence (DO-102).

Every grant-readiness failure carries a stable ``NSF-*`` code so callers and
tests can assert on the code rather than on prose. Codes are grouped by the
layer that raises them:

  ``NSF-1xx``  capability audit (inventory authoring, evidence claims)
  ``NSF-2xx``  experiment definitions and experimental runs
  ``NSF-3xx``  descriptive statistics and reporting
  ``NSF-4xx``  evidence linkage and digests

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


__all__ = [
    "GrantReadinessErrorCode",
    "GrantReadinessError",
    "CapabilityAuditError",
    "ExperimentRecordError",
    "RepeatabilityStatisticsError",
    "EvidenceLinkageError",
]
