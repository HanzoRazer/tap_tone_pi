# INSTRUMENT CLASS: MEASUREMENT
"""Process variance evidence contracts (Dev Order 89B).

Process variance decomposition separates measurement variance from build
variance using the formula:

    σ²_total = σ²_measurement + σ²_build

where:
- σ_measurement comes from repeated measurements of a kept reference body
- σ_total comes from the cohort measurements
- σ_build is derived via subtraction (clamped to zero if negative)

No advisory semantics. No quality judgments. No recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import math


@dataclass(frozen=True)
class VarianceDecompositionV1:
    """Decomposed variance from σ_total into σ_measurement and σ_build.

    This is a pure computation result with audit trail.

    Attributes:
        sigma_total: Total observed standard deviation
        sigma_measurement: Measurement standard deviation (from reference body)
        sigma_build: Build standard deviation (computed)
        sigma_total_squared: σ²_total for audit
        sigma_measurement_squared: σ²_measurement for audit
        sigma_build_squared: σ²_build for audit (may be clamped)
        clamped_to_zero: Whether σ²_build was clamped (σ²_total < σ²_measurement)
        response_variable: Name of the response variable
        unit: Unit of measurement
    """

    schema_version: str = field(default="variance_decomposition_v1", init=False)
    sigma_total: float = 0.0
    sigma_measurement: float = 0.0
    sigma_build: float = 0.0
    sigma_total_squared: float = 0.0
    sigma_measurement_squared: float = 0.0
    sigma_build_squared: float = 0.0
    clamped_to_zero: bool = False
    response_variable: str = ""
    unit: str = ""
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "sigma_total": self.sigma_total,
            "sigma_measurement": self.sigma_measurement,
            "sigma_build": self.sigma_build,
            "sigma_total_squared": self.sigma_total_squared,
            "sigma_measurement_squared": self.sigma_measurement_squared,
            "sigma_build_squared": self.sigma_build_squared,
            "clamped_to_zero": self.clamped_to_zero,
            "response_variable": self.response_variable,
            "unit": self.unit,
            "epistemic_status": self.epistemic_status,
        }


@dataclass(frozen=True)
class ProcessVarianceEvidenceV1:
    """Process variance evidence from cohort and reference body measurements.

    This record documents the variance decomposition for an experiment,
    storing both the raw input values and the computed decomposition.

    Attributes:
        evidence_id: Unique identifier
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign containing cohort
        reference_body_id: Link to kept reference body
        response_variable: Name of the response variable analyzed
        unit: Unit of measurement
        cohort_values: Raw values from cohort measurements
        reference_values: Raw values from reference body repeats
        cohort_mean: Mean of cohort values
        cohort_std: Standard deviation of cohort values (σ_total)
        reference_mean: Mean of reference body values
        reference_std: Standard deviation of reference body values (σ_measurement)
        decomposition: Computed variance decomposition
        measurement_count_cohort: Number of cohort measurements
        measurement_count_reference: Number of reference measurements
        computed_at_utc: Computation timestamp
        notes: Additional notes
    """

    schema_version: str = field(default="process_variance_evidence_v1", init=False)
    evidence_id: str = ""
    experiment_design_id: str | None = None
    campaign_id: str | None = None
    reference_body_id: str | None = None
    response_variable: str = ""
    unit: str = ""
    cohort_values: tuple[float, ...] = ()
    reference_values: tuple[float, ...] = ()
    cohort_mean: float | None = None
    cohort_std: float | None = None
    reference_mean: float | None = None
    reference_std: float | None = None
    decomposition: VarianceDecompositionV1 | None = None
    measurement_count_cohort: int = 0
    measurement_count_reference: int = 0
    computed_at_utc: str | None = None
    notes: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "response_variable": self.response_variable,
            "unit": self.unit,
            "measurement_count_cohort": self.measurement_count_cohort,
            "measurement_count_reference": self.measurement_count_reference,
            "epistemic_status": self.epistemic_status,
        }
        if self.experiment_design_id is not None:
            d["experiment_design_id"] = self.experiment_design_id
        if self.campaign_id is not None:
            d["campaign_id"] = self.campaign_id
        if self.reference_body_id is not None:
            d["reference_body_id"] = self.reference_body_id
        if self.cohort_values:
            d["cohort_values"] = list(self.cohort_values)
        if self.reference_values:
            d["reference_values"] = list(self.reference_values)
        if self.cohort_mean is not None:
            d["cohort_mean"] = self.cohort_mean
        if self.cohort_std is not None:
            d["cohort_std"] = self.cohort_std
        if self.reference_mean is not None:
            d["reference_mean"] = self.reference_mean
        if self.reference_std is not None:
            d["reference_std"] = self.reference_std
        if self.decomposition is not None:
            d["decomposition"] = self.decomposition.to_dict()
        if self.computed_at_utc is not None:
            d["computed_at_utc"] = self.computed_at_utc
        if self.notes is not None:
            d["notes"] = self.notes
        return d


def decompose_variance(
    sigma_total: float,
    sigma_measurement: float,
    response_variable: str = "",
    unit: str = "",
) -> VarianceDecompositionV1:
    """Decompose total variance into measurement and build components.

    Computes:
        σ²_build = max(σ²_total - σ²_measurement, 0)
        σ_build = sqrt(σ²_build)

    If σ²_total < σ²_measurement, σ²_build is clamped to zero and
    the clamped_to_zero flag is set.

    Args:
        sigma_total: Total standard deviation (from cohort)
        sigma_measurement: Measurement standard deviation (from reference body)
        response_variable: Name of the response variable
        unit: Unit of measurement

    Returns:
        VarianceDecompositionV1 with computed values
    """
    sigma_total_squared = sigma_total ** 2
    sigma_measurement_squared = sigma_measurement ** 2

    # Compute σ²_build with clamping
    sigma_build_squared_raw = sigma_total_squared - sigma_measurement_squared
    clamped = sigma_build_squared_raw < 0
    sigma_build_squared = max(sigma_build_squared_raw, 0.0)
    sigma_build = math.sqrt(sigma_build_squared)

    return VarianceDecompositionV1(
        sigma_total=sigma_total,
        sigma_measurement=sigma_measurement,
        sigma_build=sigma_build,
        sigma_total_squared=sigma_total_squared,
        sigma_measurement_squared=sigma_measurement_squared,
        sigma_build_squared=sigma_build_squared,
        clamped_to_zero=clamped,
        response_variable=response_variable,
        unit=unit,
    )


def compute_process_variance_evidence(
    evidence_id: str,
    cohort_values: list[float] | tuple[float, ...],
    reference_values: list[float] | tuple[float, ...],
    response_variable: str,
    unit: str,
    *,
    experiment_design_id: str | None = None,
    campaign_id: str | None = None,
    reference_body_id: str | None = None,
    notes: str | None = None,
    timestamp_utc: str | None = None,
) -> ProcessVarianceEvidenceV1:
    """Compute process variance evidence from raw values.

    Computes statistics and variance decomposition from raw cohort
    and reference body measurement values.

    Args:
        evidence_id: Unique identifier
        cohort_values: Raw values from cohort measurements
        reference_values: Raw values from reference body repeats
        response_variable: Name of the response variable
        unit: Unit of measurement
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign
        reference_body_id: Link to reference body
        notes: Additional notes
        timestamp_utc: Computation timestamp (defaults to now)

    Returns:
        ProcessVarianceEvidenceV1 with computed statistics
    """
    if timestamp_utc is None:
        timestamp_utc = datetime.now(timezone.utc).isoformat()

    cohort_values = tuple(cohort_values)
    reference_values = tuple(reference_values)

    # Compute cohort statistics
    cohort_mean = None
    cohort_std = None
    if cohort_values:
        cohort_mean = sum(cohort_values) / len(cohort_values)
        if len(cohort_values) > 1:
            variance = sum((x - cohort_mean) ** 2 for x in cohort_values) / (len(cohort_values) - 1)
            cohort_std = math.sqrt(variance)
        else:
            cohort_std = 0.0

    # Compute reference statistics
    reference_mean = None
    reference_std = None
    if reference_values:
        reference_mean = sum(reference_values) / len(reference_values)
        if len(reference_values) > 1:
            variance = sum((x - reference_mean) ** 2 for x in reference_values) / (len(reference_values) - 1)
            reference_std = math.sqrt(variance)
        else:
            reference_std = 0.0

    # Compute decomposition if both are available
    decomposition = None
    if cohort_std is not None and reference_std is not None:
        decomposition = decompose_variance(
            sigma_total=cohort_std,
            sigma_measurement=reference_std,
            response_variable=response_variable,
            unit=unit,
        )

    return ProcessVarianceEvidenceV1(
        evidence_id=evidence_id,
        experiment_design_id=experiment_design_id,
        campaign_id=campaign_id,
        reference_body_id=reference_body_id,
        response_variable=response_variable,
        unit=unit,
        cohort_values=cohort_values,
        reference_values=reference_values,
        cohort_mean=cohort_mean,
        cohort_std=cohort_std,
        reference_mean=reference_mean,
        reference_std=reference_std,
        decomposition=decomposition,
        measurement_count_cohort=len(cohort_values),
        measurement_count_reference=len(reference_values),
        computed_at_utc=timestamp_utc,
        notes=notes,
    )
