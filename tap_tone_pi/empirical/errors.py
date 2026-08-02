# INSTRUMENT CLASS: MEASUREMENT
"""Stable error vocabulary for the empirical model framework (DO-101A).

Every empirical-framework failure carries a stable ``EMP-*`` code so callers
and tests can assert on the code rather than on prose. Codes are grouped by
the layer that raises them:

  ``EMP-1xx``  model definition / contract problems (authoring errors)
  ``EMP-2xx``  serialization / payload problems
  ``EMP-3xx``  validation / linkage problems
  ``EMP-4xx``  compatibility / transport problems

Error context is always JSON-serializable and never contains a host path.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable


class EmpiricalErrorCode(str, Enum):
    """Stable identifiers for empirical framework failures."""

    # -- Definition errors -------------------------------------------------
    INVALID_MODEL_IDENTITY = "EMP-101"
    DUPLICATE_INPUT_NAME = "EMP-102"
    DUPLICATE_OUTPUT_NAME = "EMP-103"
    MISSING_INPUTS = "EMP-104"
    MISSING_OUTPUTS = "EMP-105"
    INVALID_VALIDITY_DOMAIN = "EMP-106"
    INVALID_ASSUMPTION = "EMP-107"
    INVALID_CALIBRATION_RECORD = "EMP-108"
    INVALID_EVIDENCE_REFERENCE = "EMP-109"
    INVALID_MEASUREMENT_LINK = "EMP-110"
    INVALID_UNCERTAINTY_REFERENCE = "EMP-111"
    ADVISORY_LANGUAGE_FORBIDDEN = "EMP-112"

    # -- Serialization errors ----------------------------------------------
    PAYLOAD_MALFORMED = "EMP-201"
    UNKNOWN_SCHEMA_VERSION = "EMP-202"
    TYPE_MISMATCH = "EMP-203"

    # -- Validation / linkage errors ---------------------------------------
    MODEL_VALIDATION_FAILED = "EMP-301"
    MISSING_REQUIRED_FIELD = "EMP-302"
    INVALID_VERSION = "EMP-303"

    # -- Compatibility / transport -----------------------------------------
    LUTHIERY_COMPAT_FAILED = "EMP-401"
    EMPIRICAL_UNAVAILABLE = "EMP-402"
    UNEXPECTED_FAILURE = "EMP-403"


class EmpiricalModelError(Exception):
    """Base class for every empirical-framework failure.

    Attributes:
        code: Stable ``EMP-*`` identifier.
        message: Human-readable description.
        context: JSON-serializable, path-free detail about the failure.
    """

    def __init__(
        self,
        code: EmpiricalErrorCode,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{code.value}] {message}")
        self.code = code
        self.message = message
        self.context: dict[str, Any] = dict(context or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a deterministic, path-free dictionary."""
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.context:
            payload["context"] = {k: self.context[k] for k in sorted(self.context)}
        return payload


class RegistryError(EmpiricalModelError):
    """Reserved for DO-101B registry failures; unused in DO-101A."""


class ValidationError(EmpiricalModelError):
    """A model definition or payload fails structural validation."""


def raise_for_findings(findings: Iterable[Any]) -> None:
    """Raise :class:`ValidationError` for the first finding, if any.

    The full finding list is carried in ``context['findings']``.
    """
    ordered = list(findings)
    if not ordered:
        return
    first = ordered[0]
    raise ValidationError(
        first.code,
        first.message,
        {"findings": [finding.to_dict() for finding in ordered]},
    )
