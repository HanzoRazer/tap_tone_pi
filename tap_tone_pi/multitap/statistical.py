# INSTRUMENT CLASS: MEASUREMENT
"""
Statistical analysis for multi-tap measurements.

This module provides robust statistical methods for analyzing
measurements from multiple taps on a specimen.

The multi-tap approach:
1. Perform N taps on the specimen
2. Extract measurements (frequency, damping, amplitude) from each
3. Apply quality checks and outlier detection
4. Compute weighted average with uncertainty
5. Verify convergence and report confidence intervals

Outlier Detection:
- Chauvenet's criterion: P(|x - μ| > |x_i - μ|) < 1/(2N)
- MAD (Median Absolute Deviation): |x - median| > k × MAD
- Grubbs' test: Max deviation normalized by std

The choice of method depends on the application:
- Chauvenet: Traditional, assumes normality
- MAD: Robust to asymmetric distributions
- Grubbs: Single outlier focus, good for small N
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import numpy as np
from scipy import stats


class OutlierMethod(Enum):
    """Method for outlier detection."""

    CHAUVENET = "chauvenet"
    MAD = "mad"  # Median Absolute Deviation
    GRUBBS = "grubbs"
    IQR = "iqr"  # Interquartile Range
    NONE = "none"


@dataclass
class TapMeasurement:
    """
    Single tap measurement with quality metadata.

    Attributes
    ----------
    tap_index : int
        Zero-based index of this tap.
    value : float
        Primary measurement value (e.g., frequency in Hz).
    uncertainty : float
        Uncertainty of this measurement.
    quality_score : float
        Quality metric (0-1, higher is better).
    is_outlier : bool
        Whether this tap was flagged as outlier.
    outlier_reason : str
        If outlier, reason for flagging.
    snr_db : float
        Signal-to-noise ratio in dB.
    coherence : float
        Mean coherence (if applicable).
    metadata : Dict
        Additional measurement metadata.
    """

    tap_index: int
    value: float
    uncertainty: float = 0.0
    quality_score: float = 1.0
    is_outlier: bool = False
    outlier_reason: str = ""
    snr_db: float = 40.0
    coherence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatisticalSummary:
    """
    Summary statistics for a set of measurements.

    Attributes
    ----------
    mean : float
        Arithmetic mean.
    std : float
        Sample standard deviation.
    median : float
        Median value.
    mad : float
        Median Absolute Deviation.
    sem : float
        Standard Error of the Mean.
    cv_percent : float
        Coefficient of Variation (%).
    range : Tuple[float, float]
        (min, max) range.
    iqr : float
        Interquartile range (Q3 - Q1).
    n_samples : int
        Number of samples.
    n_outliers : int
        Number of outliers detected.
    """

    mean: float
    std: float
    median: float
    mad: float
    sem: float
    cv_percent: float
    range: Tuple[float, float]
    iqr: float
    n_samples: int
    n_outliers: int = 0


@dataclass
class MultiTapResult:
    """
    Complete result of multi-tap statistical analysis.

    Attributes
    ----------
    final_value : float
        Best estimate of the measured quantity.
    standard_uncertainty : float
        Standard uncertainty u(x).
    expanded_uncertainty : float
        Expanded uncertainty U = k × u(x).
    coverage_factor : float
        Coverage factor k used.
    confidence_level : float
        Confidence level (e.g., 0.95).
    confidence_interval : Tuple[float, float]
        (lower, upper) bounds.
    measurements : List[TapMeasurement]
        All individual measurements.
    statistics : StatisticalSummary
        Summary statistics.
    convergence_achieved : bool
        Whether measurements converged.
    convergence_metric : float
        Quantitative convergence measure.
    weighting_method : str
        Method used for averaging.
    outlier_method : str
        Method used for outlier detection.
    n_taps_used : int
        Number of taps after outlier rejection.
    """

    final_value: float
    standard_uncertainty: float
    expanded_uncertainty: float
    coverage_factor: float
    confidence_level: float
    confidence_interval: Tuple[float, float]
    measurements: List[TapMeasurement]
    statistics: StatisticalSummary
    convergence_achieved: bool = True
    convergence_metric: float = 0.0
    weighting_method: str = "inverse_variance"
    outlier_method: str = "mad"
    n_taps_used: int = 0


def detect_outliers_chauvenet(
    values: np.ndarray,
    max_iterations: int = 3,
) -> np.ndarray:
    """
    Detect outliers using Chauvenet's criterion.

    A measurement is rejected if the probability of obtaining a
    deviation at least as large is less than 1/(2N), assuming
    normal distribution.

    Parameters
    ----------
    values : np.ndarray
        Array of measurements.
    max_iterations : int
        Maximum rejection iterations (to prevent over-rejection).

    Returns
    -------
    np.ndarray
        Boolean array, True for outliers.

    Notes
    -----
    Chauvenet's criterion:
        Reject x_i if P(|X - μ| ≥ |x_i - μ|) < 1/(2N)

    This is equivalent to:
        |x_i - mean| > σ × Φ⁻¹(1 - 1/(4N))

    where Φ⁻¹ is the inverse normal CDF.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n < 4:
        return np.zeros(n, dtype=bool)  # Too few for outlier detection

    outliers = np.zeros(n, dtype=bool)

    for _ in range(max_iterations):
        valid = ~outliers
        valid_values = values[valid]
        n_valid = len(valid_values)

        if n_valid < 4:
            break

        mean = np.mean(valid_values)
        std = np.std(valid_values, ddof=1)

        if std < 1e-12:
            break

        # Critical z-value for Chauvenet
        # P(reject) = 1/(2N), so we need Φ⁻¹(1 - 1/(4N))
        p_reject = 1 / (2 * n_valid)
        z_crit = stats.norm.ppf(1 - p_reject / 2)

        # Check all points
        z_scores = np.abs(values - mean) / std
        new_outliers = z_scores > z_crit

        if not np.any(new_outliers & ~outliers):
            break  # No new outliers found

        outliers = outliers | new_outliers

    return outliers


def detect_outliers_mad(
    values: np.ndarray,
    threshold: float = 3.5,
) -> np.ndarray:
    """
    Detect outliers using Median Absolute Deviation (MAD).

    MAD is more robust than standard deviation for asymmetric
    distributions and doesn't require normality assumption.

    Parameters
    ----------
    values : np.ndarray
        Array of measurements.
    threshold : float
        Number of MADs from median to flag as outlier.
        Default 3.5 corresponds to ~3σ for normal data.

    Returns
    -------
    np.ndarray
        Boolean array, True for outliers.

    Notes
    -----
    Modified Z-score:
        M_i = 0.6745 × (x_i - median) / MAD

    The constant 0.6745 makes MAD consistent with σ for normal data.
    Outlier if |M_i| > threshold.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n < 4:
        return np.zeros(n, dtype=bool)

    median = np.median(values)
    mad = np.median(np.abs(values - median))

    if mad < 1e-12:
        # All values essentially identical
        return np.zeros(n, dtype=bool)

    # Modified z-score (0.6745 makes MAD ~ σ for normal distribution)
    modified_z = 0.6745 * (values - median) / mad

    return np.abs(modified_z) > threshold


def detect_outliers_grubbs(
    values: np.ndarray,
    alpha: float = 0.05,
) -> np.ndarray:
    """
    Detect single outlier using Grubbs' test.

    Tests whether the maximum deviation from mean is significantly
    larger than expected.

    Parameters
    ----------
    values : np.ndarray
        Array of measurements.
    alpha : float
        Significance level.

    Returns
    -------
    np.ndarray
        Boolean array, True for outliers (at most one).
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n < 4:
        return np.zeros(n, dtype=bool)

    outliers = np.zeros(n, dtype=bool)

    mean = np.mean(values)
    std = np.std(values, ddof=1)

    if std < 1e-12:
        return outliers

    # Find maximum deviation
    deviations = np.abs(values - mean)
    max_idx = np.argmax(deviations)
    G = deviations[max_idx] / std

    # Critical value for Grubbs' test
    t_crit = stats.t.ppf(1 - alpha / (2 * n), n - 2)
    G_crit = ((n - 1) / np.sqrt(n)) * np.sqrt(t_crit**2 / (n - 2 + t_crit**2))

    if G > G_crit:
        outliers[max_idx] = True

    return outliers


def weighted_average(
    values: np.ndarray,
    weights: Optional[np.ndarray] = None,
    uncertainties: Optional[np.ndarray] = None,
) -> Tuple[float, float]:
    """
    Compute weighted average and its uncertainty.

    If uncertainties are provided, uses inverse-variance weighting.
    Otherwise uses provided weights or equal weighting.

    Parameters
    ----------
    values : np.ndarray
        Measurement values.
    weights : np.ndarray, optional
        Explicit weights. Ignored if uncertainties provided.
    uncertainties : np.ndarray, optional
        Uncertainties for inverse-variance weighting.

    Returns
    -------
    Tuple[float, float]
        (weighted_mean, uncertainty_of_mean)

    Notes
    -----
    Inverse-variance weighting:
        w_i = 1 / u_i²
        mean = Σ(w_i × x_i) / Σ(w_i)
        u(mean) = 1 / √(Σ(w_i))
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n == 0:
        return np.nan, np.nan

    if n == 1:
        unc = uncertainties[0] if uncertainties is not None else 0.0
        return float(values[0]), float(unc)

    if uncertainties is not None:
        uncertainties = np.asarray(uncertainties, dtype=float)
        # Avoid division by zero
        uncertainties = np.maximum(uncertainties, 1e-12)
        weights = 1.0 / uncertainties**2
    elif weights is not None:
        weights = np.asarray(weights, dtype=float)
    else:
        weights = np.ones(n)

    # Normalize weights
    weights = weights / np.sum(weights)

    weighted_mean = np.sum(weights * values)

    # Uncertainty of weighted mean
    if uncertainties is not None:
        # Inverse-variance case
        sum_inv_var = np.sum(1.0 / uncertainties**2)
        uncertainty = 1.0 / np.sqrt(sum_inv_var)
    else:
        # General weighted case - use weighted standard error
        weighted_var = np.sum(weights * (values - weighted_mean) ** 2)
        # Effective sample size
        n_eff = 1.0 / np.sum(weights**2)
        uncertainty = np.sqrt(weighted_var / max(1, n_eff - 1))

    return float(weighted_mean), float(uncertainty)


def compute_confidence_interval(
    values: np.ndarray,
    confidence_level: float = 0.95,
    weights: Optional[np.ndarray] = None,
) -> Tuple[float, float, float, float]:
    """
    Compute confidence interval for the mean.

    Parameters
    ----------
    values : np.ndarray
        Measurement values.
    confidence_level : float
        Desired confidence level (e.g., 0.95 for 95%).
    weights : np.ndarray, optional
        Weights for weighted statistics.

    Returns
    -------
    Tuple containing:
        - mean: Point estimate
        - sem: Standard error of mean
        - lower: Lower confidence bound
        - upper: Upper confidence bound
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n < 2:
        mean = values[0] if n == 1 else np.nan
        return mean, np.nan, np.nan, np.nan

    if weights is not None:
        mean, sem = weighted_average(values, weights=weights)
        # Use effective sample size for t-distribution
        weights = np.asarray(weights) / np.sum(weights)
        n_eff = 1.0 / np.sum(weights**2)
        dof = max(1, n_eff - 1)
    else:
        mean = np.mean(values)
        sem = np.std(values, ddof=1) / np.sqrt(n)
        dof = n - 1

    # t-value for confidence interval
    alpha = 1 - confidence_level
    t_value = stats.t.ppf(1 - alpha / 2, dof)

    margin = t_value * sem
    lower = mean - margin
    upper = mean + margin

    return float(mean), float(sem), float(lower), float(upper)


def check_convergence(
    values: np.ndarray,
    min_samples: int = 5,
    cv_threshold: float = 0.02,
    stability_window: int = 3,
) -> Tuple[bool, float, str]:
    """
    Check if measurements have converged to stable estimate.

    Convergence criteria:
    1. Minimum number of samples reached
    2. Coefficient of variation below threshold
    3. Running mean is stable (not trending)

    Parameters
    ----------
    values : np.ndarray
        Measurement values in chronological order.
    min_samples : int
        Minimum samples before convergence possible.
    cv_threshold : float
        Maximum CV (as fraction) for convergence.
    stability_window : int
        Samples to check for stability.

    Returns
    -------
    Tuple containing:
        - converged: bool
        - convergence_metric: float (lower is better)
        - message: str describing status
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n < min_samples:
        return False, 1.0, f"Need {min_samples} samples, have {n}"

    mean = np.mean(values)
    std = np.std(values, ddof=1)

    if abs(mean) < 1e-12:
        cv = std  # Use absolute std if mean ≈ 0
    else:
        cv = std / abs(mean)

    if cv > cv_threshold:
        return (
            False,
            cv,
            f"CV = {cv * 100:.1f}% exceeds {cv_threshold * 100:.1f}% threshold",
        )

    # Check stability of running mean
    if n >= stability_window + 2:
        recent_means = [
            np.mean(values[: i + 1]) for i in range(n - stability_window, n)
        ]
        recent_change = (
            np.std(recent_means) / abs(mean)
            if abs(mean) > 1e-12
            else np.std(recent_means)
        )

        if recent_change > cv_threshold / 2:
            return (
                False,
                cv,
                f"Running mean still changing ({recent_change * 100:.1f}%)",
            )

    return True, cv, "Converged"


def compute_statistics(
    values: np.ndarray,
    outlier_mask: Optional[np.ndarray] = None,
) -> StatisticalSummary:
    """
    Compute comprehensive statistics for a measurement set.

    Parameters
    ----------
    values : np.ndarray
        All measurement values.
    outlier_mask : np.ndarray, optional
        Boolean mask, True for outliers.

    Returns
    -------
    StatisticalSummary
        Complete statistical summary.
    """
    values = np.asarray(values, dtype=float)

    if outlier_mask is not None:
        n_outliers = np.sum(outlier_mask)
        valid_values = values[~outlier_mask]
    else:
        n_outliers = 0
        valid_values = values

    n = len(valid_values)

    if n == 0:
        return StatisticalSummary(
            mean=np.nan,
            std=np.nan,
            median=np.nan,
            mad=np.nan,
            sem=np.nan,
            cv_percent=np.nan,
            range=(np.nan, np.nan),
            iqr=np.nan,
            n_samples=0,
            n_outliers=n_outliers,
        )

    mean = float(np.mean(valid_values))
    std = float(np.std(valid_values, ddof=1)) if n > 1 else 0.0
    median = float(np.median(valid_values))
    mad = float(np.median(np.abs(valid_values - median)))
    sem = std / np.sqrt(n) if n > 0 else np.nan

    if abs(mean) > 1e-12:
        cv_percent = 100 * std / abs(mean)
    else:
        cv_percent = np.nan

    q1, q3 = np.percentile(valid_values, [25, 75]) if n >= 4 else (np.nan, np.nan)
    iqr = q3 - q1 if not np.isnan(q1) else np.nan

    return StatisticalSummary(
        mean=mean,
        std=std,
        median=median,
        mad=mad,
        sem=sem,
        cv_percent=float(cv_percent),
        range=(float(np.min(valid_values)), float(np.max(valid_values))),
        iqr=float(iqr) if not np.isnan(iqr) else 0.0,
        n_samples=n,
        n_outliers=n_outliers,
    )


def analyze_multi_tap(
    measurements: List[TapMeasurement],
    outlier_method: OutlierMethod = OutlierMethod.MAD,
    weighting: str = "inverse_variance",
    confidence_level: float = 0.95,
    check_convergence_flag: bool = True,
) -> MultiTapResult:
    """
    Complete statistical analysis of multi-tap measurements.

    Parameters
    ----------
    measurements : List[TapMeasurement]
        List of individual tap measurements.
    outlier_method : OutlierMethod
        Method for outlier detection.
    weighting : str
        "inverse_variance", "quality", or "equal".
    confidence_level : float
        Confidence level for intervals.
    check_convergence_flag : bool
        Whether to check convergence.

    Returns
    -------
    MultiTapResult
        Complete analysis result.

    Example
    -------
    >>> taps = [
    ...     TapMeasurement(0, 440.1, 0.5, 0.95),
    ...     TapMeasurement(1, 440.3, 0.4, 0.98),
    ...     TapMeasurement(2, 439.8, 0.6, 0.92),
    ...     TapMeasurement(3, 445.0, 1.0, 0.60),  # Outlier
    ...     TapMeasurement(4, 440.0, 0.5, 0.96),
    ... ]
    >>> result = analyze_multi_tap(taps)
    >>> print(f"f = {result.final_value:.2f} ± {result.expanded_uncertainty:.2f} Hz")
    """
    n_taps = len(measurements)

    if n_taps == 0:
        raise ValueError("No measurements provided")

    values = np.array([m.value for m in measurements])
    uncertainties = np.array([m.uncertainty for m in measurements])
    qualities = np.array([m.quality_score for m in measurements])

    # Outlier detection
    if outlier_method == OutlierMethod.CHAUVENET:
        outlier_mask = detect_outliers_chauvenet(values)
    elif outlier_method == OutlierMethod.MAD:
        outlier_mask = detect_outliers_mad(values)
    elif outlier_method == OutlierMethod.GRUBBS:
        outlier_mask = detect_outliers_grubbs(values)
    elif outlier_method == OutlierMethod.IQR:
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        outlier_mask = (values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)
    else:
        outlier_mask = np.zeros(n_taps, dtype=bool)

    # Update measurement objects
    for i, m in enumerate(measurements):
        m.is_outlier = bool(outlier_mask[i])
        if m.is_outlier:
            m.outlier_reason = f"Flagged by {outlier_method.value}"

    # Get valid data
    valid_mask = ~outlier_mask
    valid_values = values[valid_mask]
    valid_uncertainties = uncertainties[valid_mask]
    valid_qualities = qualities[valid_mask]

    n_valid = len(valid_values)

    # Compute weights
    if weighting == "inverse_variance":
        weights = 1.0 / np.maximum(valid_uncertainties**2, 1e-12)
    elif weighting == "quality":
        weights = valid_qualities
    else:
        weights = np.ones(n_valid)

    # Weighted average
    if weighting == "inverse_variance":
        final_value, std_unc = weighted_average(
            valid_values, uncertainties=valid_uncertainties
        )
    else:
        final_value, std_unc = weighted_average(valid_values, weights=weights)

    # Statistics
    statistics = compute_statistics(values, outlier_mask)

    # Confidence interval
    _, _, ci_lower, ci_upper = compute_confidence_interval(
        valid_values, confidence_level, weights
    )

    # Coverage factor (from t-distribution)
    dof = max(1, n_valid - 1)
    alpha = 1 - confidence_level
    k = float(stats.t.ppf(1 - alpha / 2, dof))

    expanded_unc = k * std_unc

    # Convergence check
    if check_convergence_flag and n_valid >= 3:
        converged, conv_metric, _ = check_convergence(valid_values)
    else:
        converged = n_valid >= 3
        conv_metric = (
            statistics.cv_percent / 100 if not np.isnan(statistics.cv_percent) else 1.0
        )

    return MultiTapResult(
        final_value=final_value,
        standard_uncertainty=std_unc,
        expanded_uncertainty=expanded_unc,
        coverage_factor=k,
        confidence_level=confidence_level,
        confidence_interval=(ci_lower, ci_upper),
        measurements=measurements,
        statistics=statistics,
        convergence_achieved=converged,
        convergence_metric=conv_metric,
        weighting_method=weighting,
        outlier_method=outlier_method.value,
        n_taps_used=n_valid,
    )
