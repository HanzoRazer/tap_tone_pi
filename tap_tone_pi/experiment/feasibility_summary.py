# INSTRUMENT CLASS: MEASUREMENT
"""Feasibility summary contracts for cohort studies (Dev Order 89B).

The feasibility summary reports process variance evidence at the cohort
level, including variance bands (low/medium/high) based on thresholds.

Variance bands use neutral language. No pass/fail, go/no-go, or
color-coded judgments.

No advisory semantics. No recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from tap_tone_pi.experiment.process_variance import VarianceDecompositionV1


@dataclass(frozen=True)
class VarianceBandThresholdsV1:
    """Thresholds defining variance bands.

    Bands are classified as:
    - "low": σ_build <= low_threshold
    - "medium": low_threshold < σ_build <= high_threshold
    - "high": σ_build > high_threshold

    Thresholds are expressed as percentages of the mean (CV-style).

    Attributes:
        low_threshold_pct: Upper bound for "low" band (e.g., 3.0 for 3%)
        high_threshold_pct: Upper bound for "medium" band (e.g., 10.0 for 10%)
        response_variable: Response variable these thresholds apply to
    """

    schema_version: str = field(default="variance_band_thresholds_v1", init=False)
    low_threshold_pct: float = 3.0
    high_threshold_pct: float = 10.0
    response_variable: str = ""
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "low_threshold_pct": self.low_threshold_pct,
            "high_threshold_pct": self.high_threshold_pct,
            "response_variable": self.response_variable,
            "epistemic_status": self.epistemic_status,
        }


@dataclass(frozen=True)
class FeasibilitySummaryV1:
    """Feasibility summary for a cohort study.

    Reports process variance evidence and variance band classification
    at the cohort level. Uses neutral language for bands.

    Attributes:
        summary_id: Unique identifier
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign
        response_variable: Response variable analyzed
        unit: Unit of measurement
        cohort_size: Number of specimens in cohort
        reference_measurement_count: Number of reference body measurements
        sigma_total: Total standard deviation
        sigma_measurement: Measurement standard deviation
        sigma_build: Build standard deviation
        cv_build_pct: Coefficient of variation for build (σ_build / mean * 100)
        variance_band: Classification ("low", "medium", "high")
        thresholds: Band thresholds used
        decomposition: Full variance decomposition
        computed_at_utc: Computation timestamp
        notes: Additional notes
    """

    schema_version: str = field(default="feasibility_summary_v1", init=False)
    summary_id: str = ""
    experiment_design_id: str | None = None
    campaign_id: str | None = None
    response_variable: str = ""
    unit: str = ""
    cohort_size: int = 0
    reference_measurement_count: int = 0
    cohort_mean: float | None = None
    sigma_total: float | None = None
    sigma_measurement: float | None = None
    sigma_build: float | None = None
    cv_build_pct: float | None = None
    variance_band: str | None = None
    thresholds: VarianceBandThresholdsV1 | None = None
    decomposition: VarianceDecompositionV1 | None = None
    computed_at_utc: str | None = None
    notes: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "summary_id": self.summary_id,
            "response_variable": self.response_variable,
            "unit": self.unit,
            "cohort_size": self.cohort_size,
            "reference_measurement_count": self.reference_measurement_count,
            "epistemic_status": self.epistemic_status,
        }
        if self.experiment_design_id is not None:
            d["experiment_design_id"] = self.experiment_design_id
        if self.campaign_id is not None:
            d["campaign_id"] = self.campaign_id
        if self.cohort_mean is not None:
            d["cohort_mean"] = self.cohort_mean
        if self.sigma_total is not None:
            d["sigma_total"] = self.sigma_total
        if self.sigma_measurement is not None:
            d["sigma_measurement"] = self.sigma_measurement
        if self.sigma_build is not None:
            d["sigma_build"] = self.sigma_build
        if self.cv_build_pct is not None:
            d["cv_build_pct"] = self.cv_build_pct
        if self.variance_band is not None:
            d["variance_band"] = self.variance_band
        if self.thresholds is not None:
            d["thresholds"] = self.thresholds.to_dict()
        if self.decomposition is not None:
            d["decomposition"] = self.decomposition.to_dict()
        if self.computed_at_utc is not None:
            d["computed_at_utc"] = self.computed_at_utc
        if self.notes is not None:
            d["notes"] = self.notes
        return d


def classify_variance_band(
    cv_build_pct: float,
    thresholds: VarianceBandThresholdsV1,
) -> str:
    """Classify variance into a band based on CV%.

    Args:
        cv_build_pct: Coefficient of variation for build (percentage)
        thresholds: Band thresholds

    Returns:
        Band classification: "low", "medium", or "high"
    """
    if cv_build_pct <= thresholds.low_threshold_pct:
        return "low"
    elif cv_build_pct <= thresholds.high_threshold_pct:
        return "medium"
    else:
        return "high"


def create_feasibility_summary(
    summary_id: str,
    response_variable: str,
    unit: str,
    cohort_mean: float,
    decomposition: VarianceDecompositionV1,
    cohort_size: int,
    reference_measurement_count: int,
    *,
    thresholds: VarianceBandThresholdsV1 | None = None,
    experiment_design_id: str | None = None,
    campaign_id: str | None = None,
    notes: str | None = None,
    timestamp_utc: str | None = None,
) -> FeasibilitySummaryV1:
    """Create a feasibility summary from variance decomposition.

    Computes CV% and classifies into variance band.

    Args:
        summary_id: Unique identifier
        response_variable: Response variable name
        unit: Unit of measurement
        cohort_mean: Mean value from cohort
        decomposition: Variance decomposition
        cohort_size: Number of specimens
        reference_measurement_count: Number of reference measurements
        thresholds: Band thresholds (defaults to 3%/10%)
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign
        notes: Additional notes
        timestamp_utc: Computation timestamp (defaults to now)

    Returns:
        FeasibilitySummaryV1 instance
    """
    if timestamp_utc is None:
        timestamp_utc = datetime.now(timezone.utc).isoformat()

    if thresholds is None:
        thresholds = VarianceBandThresholdsV1(
            low_threshold_pct=3.0,
            high_threshold_pct=10.0,
            response_variable=response_variable,
        )

    # Compute CV% for build variance
    cv_build_pct = None
    variance_band = None
    if cohort_mean != 0:
        cv_build_pct = (decomposition.sigma_build / abs(cohort_mean)) * 100
        variance_band = classify_variance_band(cv_build_pct, thresholds)

    return FeasibilitySummaryV1(
        summary_id=summary_id,
        experiment_design_id=experiment_design_id,
        campaign_id=campaign_id,
        response_variable=response_variable,
        unit=unit,
        cohort_size=cohort_size,
        reference_measurement_count=reference_measurement_count,
        cohort_mean=cohort_mean,
        sigma_total=decomposition.sigma_total,
        sigma_measurement=decomposition.sigma_measurement,
        sigma_build=decomposition.sigma_build,
        cv_build_pct=cv_build_pct,
        variance_band=variance_band,
        thresholds=thresholds,
        decomposition=decomposition,
        computed_at_utc=timestamp_utc,
        notes=notes,
    )
