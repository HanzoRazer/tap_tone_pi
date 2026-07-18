# INSTRUMENT CLASS: MEASUREMENT
"""Transfer function result contract for provenance (DO-91).

TransferFunctionResultV1 is the provenance-aware wrapper for TF results,
including H(f), coherence summary, and uncertainty summary with full
lineage to excitation-response pairs.

This wraps the numerical TransferFunctionResult from estimators.py
with schema versioning and provenance linkage.

No advisory semantics. No quality judgments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class CoherenceSummaryV1:
    """Summary of coherence quality for export.

    This is a serializable summary, not the full coherence array.
    """

    mean_coherence: float
    min_coherence: float
    max_coherence: float
    coherent_fraction: float  # Fraction above threshold (e.g., 0.8)
    coherence_threshold: float
    frequency_range_hz: Tuple[float, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean_coherence": self.mean_coherence,
            "min_coherence": self.min_coherence,
            "max_coherence": self.max_coherence,
            "coherent_fraction": self.coherent_fraction,
            "coherence_threshold": self.coherence_threshold,
            "frequency_range_hz": list(self.frequency_range_hz),
        }


@dataclass(frozen=True)
class UncertaintySummaryV1:
    """Summary of transfer function uncertainty.

    Derived from coherence and averaging.
    """

    mean_relative_uncertainty: float  # Relative uncertainty (0-1)
    max_relative_uncertainty: float
    num_averages: int
    uncertainty_method: str  # "coherence_based", "bootstrap", etc.

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean_relative_uncertainty": self.mean_relative_uncertainty,
            "max_relative_uncertainty": self.max_relative_uncertainty,
            "num_averages": self.num_averages,
            "uncertainty_method": self.uncertainty_method,
        }


@dataclass(frozen=True)
class TransferFunctionResultV1:
    """Provenance-aware transfer function result.

    This contract wraps numerical TF results with schema versioning
    and provenance linkage for export to viewer packs.

    For full frequency-domain arrays, reference the underlying
    numerical result via result_data_path. This contract stores
    summaries to avoid duplicating large arrays.

    Attributes:
        result_id: Unique identifier
        excitation_response_pair_id: Link to the source pair
        estimator_used: Which estimator (H1/H2/Hv)
        frequency_range_hz: (low, high) frequency range
        num_frequency_bins: Number of frequency bins
        peak_magnitude: Maximum |H(f)|
        peak_frequency_hz: Frequency of peak magnitude
        coherence_summary: Summary of coherence quality
        uncertainty_summary: Summary of uncertainty
        computed_at_utc: Computation timestamp
        result_data_path: Path to full numerical result (optional)
    """

    schema_version: str = field(default="transfer_function_result_v1", init=False)
    result_id: str = ""
    excitation_response_pair_id: str = ""
    estimator_used: str = "H1"
    frequency_range_hz: Tuple[float, float] = (0.0, 0.0)
    num_frequency_bins: int = 0
    peak_magnitude: float = 0.0
    peak_frequency_hz: float = 0.0
    coherence_summary: Optional[CoherenceSummaryV1] = None
    uncertainty_summary: Optional[UncertaintySummaryV1] = None
    computed_at_utc: str = ""
    result_data_path: Optional[str] = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "excitation_response_pair_id": self.excitation_response_pair_id,
            "estimator_used": self.estimator_used,
            "frequency_range_hz": list(self.frequency_range_hz),
            "num_frequency_bins": self.num_frequency_bins,
            "peak_magnitude": self.peak_magnitude,
            "peak_frequency_hz": self.peak_frequency_hz,
            "computed_at_utc": self.computed_at_utc,
            "epistemic_status": self.epistemic_status,
        }

        if self.coherence_summary is not None:
            d["coherence_summary"] = self.coherence_summary.to_dict()
        if self.uncertainty_summary is not None:
            d["uncertainty_summary"] = self.uncertainty_summary.to_dict()
        if self.result_data_path is not None:
            d["result_data_path"] = self.result_data_path

        return d


def create_transfer_function_result(
    result_id: str,
    excitation_response_pair_id: str,
    estimator_used: str,
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    coherence: Optional[np.ndarray] = None,
    *,
    coherence_threshold: float = 0.8,
    num_averages: int = 1,
    result_data_path: Optional[str] = None,
    computed_at_utc: Optional[str] = None,
) -> TransferFunctionResultV1:
    """Create a transfer function result from numerical arrays.

    Args:
        result_id: Unique identifier
        excitation_response_pair_id: Link to source pair
        estimator_used: Estimator name (H1/H2/Hv)
        frequencies: Frequency array in Hz
        magnitude: |H(f)| magnitude array
        coherence: Optional coherence array
        coherence_threshold: Threshold for coherent fraction
        num_averages: Number of averages used
        result_data_path: Path to full numerical result
        computed_at_utc: Computation timestamp (defaults to now)

    Returns:
        TransferFunctionResultV1 instance
    """
    if computed_at_utc is None:
        computed_at_utc = datetime.now(timezone.utc).isoformat()

    # Compute frequency range
    freq_low = float(frequencies[0]) if len(frequencies) > 0 else 0.0
    freq_high = float(frequencies[-1]) if len(frequencies) > 0 else 0.0

    # Find peak
    if len(magnitude) > 0:
        peak_idx = int(np.argmax(magnitude))
        peak_magnitude = float(magnitude[peak_idx])
        peak_frequency_hz = float(frequencies[peak_idx])
    else:
        peak_magnitude = 0.0
        peak_frequency_hz = 0.0

    # Compute coherence summary
    coherence_summary = None
    if coherence is not None and len(coherence) > 0:
        coherent_mask = coherence >= coherence_threshold
        coherence_summary = CoherenceSummaryV1(
            mean_coherence=float(np.mean(coherence)),
            min_coherence=float(np.min(coherence)),
            max_coherence=float(np.max(coherence)),
            coherent_fraction=float(np.mean(coherent_mask)),
            coherence_threshold=coherence_threshold,
            frequency_range_hz=(freq_low, freq_high),
        )

    # Compute uncertainty summary from coherence
    uncertainty_summary = None
    if coherence is not None and len(coherence) > 0 and num_averages > 0:
        # Uncertainty from coherence: σ_H/|H| ≈ sqrt((1-γ²)/(2*n*γ²))
        # where n is number of averages
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_unc = np.sqrt((1 - coherence) / (2 * num_averages * coherence))
            rel_unc = np.where(np.isfinite(rel_unc), rel_unc, 1.0)

        uncertainty_summary = UncertaintySummaryV1(
            mean_relative_uncertainty=float(np.mean(rel_unc)),
            max_relative_uncertainty=float(np.max(rel_unc)),
            num_averages=num_averages,
            uncertainty_method="coherence_based",
        )

    return TransferFunctionResultV1(
        result_id=result_id,
        excitation_response_pair_id=excitation_response_pair_id,
        estimator_used=estimator_used,
        frequency_range_hz=(freq_low, freq_high),
        num_frequency_bins=len(frequencies),
        peak_magnitude=peak_magnitude,
        peak_frequency_hz=peak_frequency_hz,
        coherence_summary=coherence_summary,
        uncertainty_summary=uncertainty_summary,
        computed_at_utc=computed_at_utc,
        result_data_path=result_data_path,
    )


def create_transfer_function_result_from_estimator(
    result_id: str,
    excitation_response_pair_id: str,
    tf_result: "TransferFunctionResult",
    *,
    num_averages: int = 1,
    coherence_threshold: float = 0.8,
    result_data_path: Optional[str] = None,
    computed_at_utc: Optional[str] = None,
) -> TransferFunctionResultV1:
    """Create a transfer function result from an estimator result.

    Args:
        result_id: Unique identifier
        excitation_response_pair_id: Link to source pair
        tf_result: TransferFunctionResult from estimators.py
        num_averages: Number of averages used
        coherence_threshold: Threshold for coherent fraction
        result_data_path: Path to full numerical result
        computed_at_utc: Computation timestamp (defaults to now)

    Returns:
        TransferFunctionResultV1 instance
    """
    # Get coherence array from CoherenceResult if available
    coherence = None
    if tf_result.coherence is not None:
        coherence = tf_result.coherence.coherence

    return create_transfer_function_result(
        result_id=result_id,
        excitation_response_pair_id=excitation_response_pair_id,
        estimator_used=tf_result.estimator_used,
        frequencies=tf_result.frequencies,
        magnitude=tf_result.magnitude,
        coherence=coherence,
        coherence_threshold=coherence_threshold,
        num_averages=num_averages,
        result_data_path=result_data_path,
        computed_at_utc=computed_at_utc,
    )
