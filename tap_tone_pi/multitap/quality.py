# INSTRUMENT CLASS: DECISION SUPPORT
# Outputs from this module include actionable recommendations.
# They MUST NOT appear in viewer_pack_v1 or the provenance chain.
# See docs/ADR-0009-advisory-boundary.md
"""
Tap quality assessment for multi-tap analysis.

This module provides methods to assess and rank the quality of
individual taps in a multi-tap measurement session.

Quality factors considered:
- Signal-to-noise ratio (SNR)
- Coherence (if transfer function measurement)
- Peak amplitude and consistency
- Spectral cleanliness
- Consistency with other taps

The goal is to identify which taps should be prioritized or potentially
rejected, helping operators make informed decisions about measurement quality.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import numpy as np


class QualityLevel(Enum):
    """Quality classification for a tap."""

    EXCELLENT = "excellent"  # Use with high confidence
    GOOD = "good"  # Use normally
    ACCEPTABLE = "acceptable"  # Use with caution
    POOR = "poor"  # Consider rejection
    REJECT = "reject"  # Do not use


@dataclass
class TapQualityMetrics:
    """
    Comprehensive quality metrics for a single tap.

    Attributes
    ----------
    tap_index : int
        Zero-based tap index.
    overall_score : float
        Combined quality score (0-1).
    quality_level : QualityLevel
        Classification based on score.
    snr_db : float
        Signal-to-noise ratio.
    snr_score : float
        Normalized SNR score (0-1).
    peak_amplitude : float
        Maximum signal amplitude.
    amplitude_score : float
        Score based on amplitude consistency.
    spectral_cleanliness : float
        Score based on spectral quality.
    consistency_score : float
        Score based on agreement with other taps.
    coherence_mean : float
        Mean coherence (if applicable).
    issues : List[str]
        Identified quality issues.
    recommendations : List[str]
        Specific recommendations.
    """

    tap_index: int
    overall_score: float
    quality_level: QualityLevel
    snr_db: float
    snr_score: float
    peak_amplitude: float
    amplitude_score: float
    spectral_cleanliness: float
    consistency_score: float
    coherence_mean: float = 1.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


def score_to_level(score: float) -> QualityLevel:
    """Convert numeric score to quality level."""
    if score >= 0.9:
        return QualityLevel.EXCELLENT
    elif score >= 0.75:
        return QualityLevel.GOOD
    elif score >= 0.5:
        return QualityLevel.ACCEPTABLE
    elif score >= 0.25:
        return QualityLevel.POOR
    else:
        return QualityLevel.REJECT


def compute_snr_score(snr_db: float) -> float:
    """
    Convert SNR in dB to quality score.

    Scoring:
    - SNR > 40 dB: score = 1.0 (excellent)
    - SNR = 20 dB: score = 0.5
    - SNR = 10 dB: score = 0.25
    - SNR < 5 dB: score approaches 0
    """
    # Sigmoid-like mapping
    if snr_db >= 50:
        return 1.0
    elif snr_db <= 0:
        return 0.0
    else:
        # Map 10-40 dB to roughly 0.3-0.95
        return 0.05 + 0.95 / (1 + np.exp(-(snr_db - 20) / 8))


def compute_amplitude_score(
    amplitude: float,
    reference_amplitude: float,
    tolerance_fraction: float = 0.5,
) -> float:
    """
    Score based on amplitude consistency.

    Parameters
    ----------
    amplitude : float
        This tap's peak amplitude.
    reference_amplitude : float
        Expected or median amplitude.
    tolerance_fraction : float
        Fractional deviation considered acceptable.

    Returns
    -------
    float
        Score from 0-1.
    """
    if reference_amplitude <= 0:
        return 0.5  # Cannot evaluate

    ratio = amplitude / reference_amplitude

    # Penalize both low and high relative to reference
    if ratio < 1:
        deviation = 1 - ratio
    else:
        deviation = ratio - 1

    # Score decreases with deviation
    score = max(0, 1 - deviation / tolerance_fraction)
    return float(score)


def compute_consistency_score(
    value: float,
    all_values: np.ndarray,
    robust: bool = True,
) -> float:
    """
    Score based on consistency with other measurements.

    Parameters
    ----------
    value : float
        This tap's measurement value.
    all_values : np.ndarray
        All measurement values.
    robust : bool
        If True, use median and MAD instead of mean and std.

    Returns
    -------
    float
        Score from 0-1 (1 = perfectly consistent).
    """
    all_values = np.asarray(all_values)

    if len(all_values) < 3:
        return 0.8  # Not enough data to assess

    if robust:
        center = np.median(all_values)
        scale = np.median(np.abs(all_values - center))
        if scale < 1e-12:
            scale = np.std(all_values)
    else:
        center = np.mean(all_values)
        scale = np.std(all_values)

    if scale < 1e-12:
        return 1.0 if abs(value - center) < 1e-12 else 0.0

    # Normalized deviation
    z = abs(value - center) / scale

    # Score: 1 at z=0, drops off with increasing z
    # z=1 → ~0.7, z=2 → ~0.4, z=3 → ~0.15
    score = np.exp(-0.5 * z**2 / 4)  # Softer penalty than pure Gaussian

    return float(score)


def assess_tap_quality(
    tap_index: int,
    snr_db: float,
    peak_amplitude: float,
    measurement_value: float,
    all_values: np.ndarray,
    reference_amplitude: Optional[float] = None,
    coherence_mean: Optional[float] = None,
) -> TapQualityMetrics:
    """
    Comprehensive quality assessment for a single tap.

    Parameters
    ----------
    tap_index : int
        Zero-based tap index.
    snr_db : float
        Signal-to-noise ratio in dB.
    peak_amplitude : float
        Maximum signal amplitude.
    measurement_value : float
        Extracted measurement (frequency, damping, etc.).
    all_values : np.ndarray
        All measurements from session.
    reference_amplitude : float, optional
        Expected amplitude for scoring.
    coherence_mean : float, optional
        Mean coherence for transfer function.

    Returns
    -------
    TapQualityMetrics
        Complete quality assessment.
    """
    issues = []
    recommendations = []

    # SNR score
    snr_score = compute_snr_score(snr_db)
    if snr_score < 0.5:
        issues.append(f"Low SNR ({snr_db:.1f} dB)")
        recommendations.append("Increase tap force or reduce ambient noise")

    # Amplitude score
    if reference_amplitude is None:
        reference_amplitude = np.median(
            [peak_amplitude]
            if len(all_values) < 2
            else np.abs(all_values)  # Proxy if amplitude array not available
        )
        reference_amplitude = max(reference_amplitude, peak_amplitude * 0.5)

    amp_score = compute_amplitude_score(peak_amplitude, reference_amplitude)
    if amp_score < 0.5:
        if peak_amplitude < reference_amplitude:
            issues.append("Low tap amplitude")
            recommendations.append("Tap with more consistent force")
        else:
            issues.append("High tap amplitude (possible double-hit)")
            recommendations.append("Use gentler, controlled taps")

    # Consistency score
    consistency_score = compute_consistency_score(measurement_value, all_values)
    if consistency_score < 0.5:
        issues.append("Measurement inconsistent with other taps")
        recommendations.append("Review this tap for anomalies")

    # Spectral cleanliness (proxy from SNR)
    spectral_score = snr_score * 0.9 + 0.1  # Slight boost

    # Coherence contribution
    if coherence_mean is not None:
        coh_contribution = coherence_mean
        if coherence_mean < 0.7:
            issues.append(f"Low coherence ({coherence_mean:.2f})")
            recommendations.append("Check measurement setup")
    else:
        coh_contribution = 1.0

    # Overall score (weighted combination)
    weights = {
        "snr": 0.30,
        "amplitude": 0.20,
        "consistency": 0.25,
        "spectral": 0.15,
        "coherence": 0.10,
    }

    overall = (
        weights["snr"] * snr_score
        + weights["amplitude"] * amp_score
        + weights["consistency"] * consistency_score
        + weights["spectral"] * spectral_score
        + weights["coherence"] * coh_contribution
    )

    quality_level = score_to_level(overall)

    if quality_level == QualityLevel.REJECT:
        recommendations.insert(0, "Consider discarding this tap")
    elif quality_level == QualityLevel.POOR:
        recommendations.insert(0, "Use with caution - review data")

    return TapQualityMetrics(
        tap_index=tap_index,
        overall_score=float(overall),
        quality_level=quality_level,
        snr_db=float(snr_db),
        snr_score=float(snr_score),
        peak_amplitude=float(peak_amplitude),
        amplitude_score=float(amp_score),
        spectral_cleanliness=float(spectral_score),
        consistency_score=float(consistency_score),
        coherence_mean=float(coh_contribution),
        issues=issues,
        recommendations=recommendations,
    )


def rank_tap_quality(
    metrics_list: List[TapQualityMetrics],
) -> List[Tuple[int, float, QualityLevel]]:
    """
    Rank taps by quality score.

    Parameters
    ----------
    metrics_list : List[TapQualityMetrics]
        Quality metrics for all taps.

    Returns
    -------
    List[Tuple[int, float, QualityLevel]]
        List of (tap_index, score, level) sorted by score descending.
    """
    ranked = [(m.tap_index, m.overall_score, m.quality_level) for m in metrics_list]
    return sorted(ranked, key=lambda x: -x[1])


def suggest_tap_rejection(
    metrics_list: List[TapQualityMetrics],
    max_reject_fraction: float = 0.3,
    min_keep: int = 3,
) -> List[int]:
    """
    Suggest which taps to reject based on quality.

    Parameters
    ----------
    metrics_list : List[TapQualityMetrics]
        Quality metrics for all taps.
    max_reject_fraction : float
        Maximum fraction of taps to reject.
    min_keep : int
        Minimum number of taps to keep.

    Returns
    -------
    List[int]
        Indices of taps suggested for rejection.

    Notes
    -----
    This is a suggestion, not a mandate. The operator should review
    the recommended rejections before accepting them.
    """
    n_taps = len(metrics_list)
    max_reject = min(int(n_taps * max_reject_fraction), n_taps - min_keep)

    if max_reject <= 0:
        return []

    # Rank by quality (worst first)
    ranked = sorted(metrics_list, key=lambda m: m.overall_score)

    rejections: List[int] = []
    for m in ranked:
        if len(rejections) >= max_reject:
            break

        # Only suggest rejection for clearly poor taps
        if m.quality_level in [QualityLevel.REJECT, QualityLevel.POOR]:
            rejections.append(m.tap_index)

    return rejections


def quality_summary_report(
    metrics_list: List[TapQualityMetrics],
) -> Dict[str, Any]:
    """
    Generate summary report of tap quality across session.

    Parameters
    ----------
    metrics_list : List[TapQualityMetrics]
        Quality metrics for all taps.

    Returns
    -------
    Dict with summary statistics and recommendations.
    """
    if not metrics_list:
        return {"error": "No metrics provided"}

    n_taps = len(metrics_list)
    scores = [m.overall_score for m in metrics_list]

    # Count by level
    level_counts = {level: 0 for level in QualityLevel}
    for m in metrics_list:
        level_counts[m.quality_level] += 1

    # Aggregate issues
    all_issues = []
    for m in metrics_list:
        for issue in m.issues:
            all_issues.append((m.tap_index, issue))

    # Most common issues
    issue_types: Dict[str, int] = {}
    for _, issue in all_issues:
        issue_types[issue] = issue_types.get(issue, 0) + 1

    # Recommendations
    recommendations = []

    usable_fraction = (
        level_counts[QualityLevel.EXCELLENT]
        + level_counts[QualityLevel.GOOD]
        + level_counts[QualityLevel.ACCEPTABLE]
    ) / n_taps

    if usable_fraction < 0.7:
        recommendations.append(
            "Session quality is low. Consider re-measuring with improved setup."
        )

    if level_counts[QualityLevel.REJECT] > 0:
        recommendations.append(
            f"{level_counts[QualityLevel.REJECT]} tap(s) should be rejected."
        )

    snr_issues = sum(1 for m in metrics_list if m.snr_score < 0.5)
    if snr_issues > n_taps * 0.3:
        recommendations.append("Multiple taps have low SNR. Check ambient noise level.")

    return {
        "n_taps": n_taps,
        "mean_quality_score": float(np.mean(scores)),
        "min_quality_score": float(np.min(scores)),
        "max_quality_score": float(np.max(scores)),
        "level_counts": {level.value: count for level, count in level_counts.items()},
        "usable_fraction": float(usable_fraction),
        "n_issues_total": len(all_issues),
        "most_common_issues": sorted(issue_types.items(), key=lambda x: -x[1])[:3],
        "recommendations": recommendations,
        "suggested_rejections": suggest_tap_rejection(metrics_list),
    }
