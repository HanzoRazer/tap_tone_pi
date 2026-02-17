"""
Quality metrics for transfer function measurements.

This module provides functions to assess measurement quality and
calculate uncertainty bounds from coherence data.

Key relationships:

SNR from Coherence:
    SNR = γ² / (1 - γ²)

This assumes noise is uncorrelated and the system is linear.
At γ² = 0.5, SNR ≈ 1 (0 dB).
At γ² = 0.9, SNR = 9 (9.5 dB).
At γ² = 0.99, SNR = 99 (20 dB).

Normalized Random Error in |H|:
    ε|H| = sqrt((1 - γ²) / (2 × n × γ²))

where n is the number of averages.

Required Averages for Target Error:
    n = (1 - γ²) / (2 × γ² × ε²)

Phase Uncertainty:
    σ_φ = sqrt((1 - γ²) / (2 × n × γ²))   [radians]
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
import numpy as np


def estimate_snr_from_coherence(
    coherence: np.ndarray,
) -> np.ndarray:
    """
    Estimate signal-to-noise ratio from coherence.

    The relationship SNR = γ²/(1-γ²) assumes:
    - Noise is uncorrelated with signal
    - System is linear
    - Sufficient averaging for stable coherence estimate

    Parameters
    ----------
    coherence : np.ndarray
        Coherence values γ² (must be in [0, 1]).

    Returns
    -------
    np.ndarray
        Estimated SNR (linear, not dB).

    Example
    -------
    >>> gamma_sq = np.array([0.5, 0.9, 0.99])
    >>> snr = estimate_snr_from_coherence(gamma_sq)
    >>> print(snr)  # [1.0, 9.0, 99.0]
    """
    # Clip to valid range to avoid division issues
    coherence = np.clip(coherence, 0.0, 0.9999)
    return coherence / (1 - coherence)


def snr_to_db(snr_linear: np.ndarray) -> np.ndarray:
    """Convert linear SNR to decibels."""
    return 10 * np.log10(np.maximum(snr_linear, 1e-12))


def uncertainty_from_coherence(
    coherence: np.ndarray,
    n_averages: int,
    magnitude: Optional[np.ndarray] = None,
) -> Dict[str, np.ndarray]:
    """
    Calculate uncertainty bounds from coherence and averaging.

    Parameters
    ----------
    coherence : np.ndarray
        Coherence values γ² at each frequency.
    n_averages : int
        Number of averages used in measurement.
    magnitude : np.ndarray, optional
        |H(f)| magnitude for absolute uncertainty calculation.

    Returns
    -------
    Dict containing:
        - relative_magnitude_error: ε|H| / |H| as fraction
        - absolute_magnitude_error: ε|H| (if magnitude provided)
        - phase_error_rad: σ_φ in radians
        - phase_error_deg: σ_φ in degrees
        - snr_linear: Estimated SNR
        - snr_db: Estimated SNR in dB

    Example
    -------
    >>> gamma_sq = np.array([0.8, 0.9, 0.95])
    >>> unc = uncertainty_from_coherence(gamma_sq, n_averages=10)
    >>> print(f"Phase error (deg): {unc['phase_error_deg']}")
    """
    coherence = np.clip(coherence, 1e-6, 0.9999)
    n = max(1, n_averages)

    # Relative error in |H|: sqrt((1-γ²) / (2×n×γ²))
    relative_error = np.sqrt((1 - coherence) / (2 * n * coherence))

    # Phase error (same formula, in radians)
    phase_error_rad = np.sqrt((1 - coherence) / (2 * n * coherence))
    phase_error_deg = np.degrees(phase_error_rad)

    # SNR estimation
    snr_linear = coherence / (1 - coherence)
    snr_db = 10 * np.log10(np.maximum(snr_linear, 1e-12))

    result = {
        "relative_magnitude_error": relative_error,
        "phase_error_rad": phase_error_rad,
        "phase_error_deg": phase_error_deg,
        "snr_linear": snr_linear,
        "snr_db": snr_db,
    }

    if magnitude is not None:
        result["absolute_magnitude_error"] = relative_error * magnitude

    return result


def required_averages_for_error(
    coherence: float,
    target_relative_error: float,
) -> int:
    """
    Calculate required averages to achieve target error.

    Parameters
    ----------
    coherence : float
        Expected coherence γ² (0 to 1).
    target_relative_error : float
        Target relative error ε|H|/|H| (e.g., 0.05 for 5%).

    Returns
    -------
    int
        Minimum number of averages required.

    Example
    -------
    >>> n = required_averages_for_error(0.9, 0.05)  # 5% error, 0.9 coherence
    >>> print(n)  # 11
    """
    if coherence <= 0 or coherence >= 1:
        raise ValueError("Coherence must be in (0, 1)")

    if target_relative_error <= 0:
        raise ValueError("Target error must be positive")

    # n = (1 - γ²) / (2 × γ² × ε²)
    n = (1 - coherence) / (2 * coherence * target_relative_error**2)
    return max(1, int(np.ceil(n)))


@dataclass
class QualityAssessment:
    """
    Comprehensive quality assessment for a transfer function measurement.

    Attributes
    ----------
    overall_grade : str
        Letter grade: "A" (excellent) to "F" (failed).
    coherence_grade : str
        Quality of coherence.
    snr_grade : str
        Quality of signal-to-noise ratio.
    averaging_adequate : bool
        Whether averaging is sufficient.
    recommendations : list
        Specific recommendations for improvement.
    metrics : dict
        Detailed quality metrics.
    """
    overall_grade: str
    coherence_grade: str
    snr_grade: str
    averaging_adequate: bool
    recommendations: list
    metrics: dict


def validate_measurement_quality(
    coherence: np.ndarray,
    frequencies: np.ndarray,
    n_averages: int,
    min_frequency: float = 20.0,
    max_frequency: Optional[float] = None,
    coherence_threshold: float = 0.8,
    target_error: float = 0.10,
) -> QualityAssessment:
    """
    Comprehensive quality validation for FRF measurement.

    Parameters
    ----------
    coherence : np.ndarray
        Coherence values γ² at each frequency.
    frequencies : np.ndarray
        Frequency vector in Hz.
    n_averages : int
        Number of averages used.
    min_frequency : float
        Lower frequency bound of interest.
    max_frequency : float, optional
        Upper frequency bound of interest. Default: max(frequencies).
    coherence_threshold : float
        Minimum acceptable coherence.
    target_error : float
        Target relative error for adequacy assessment.

    Returns
    -------
    QualityAssessment
        Comprehensive quality assessment with recommendations.
    """
    if max_frequency is None:
        max_frequency = frequencies[-1]

    # Select valid frequency range
    mask = (frequencies >= min_frequency) & (frequencies <= max_frequency)
    valid_coherence = coherence[mask]
    valid_freqs = frequencies[mask]

    if len(valid_coherence) == 0:
        return QualityAssessment(
            overall_grade="F",
            coherence_grade="F",
            snr_grade="F",
            averaging_adequate=False,
            recommendations=["No valid frequency data in specified range"],
            metrics={},
        )

    # Coherence statistics
    mean_coh = float(np.mean(valid_coherence))
    min_coh = float(np.min(valid_coherence))
    median_coh = float(np.median(valid_coherence))
    coherent_fraction = float(np.mean(valid_coherence >= coherence_threshold))

    # SNR statistics
    snr = estimate_snr_from_coherence(valid_coherence)
    mean_snr_db = float(10 * np.log10(np.mean(snr)))
    min_snr_db = float(10 * np.log10(np.min(snr)))

    # Error statistics
    rel_error = np.sqrt((1 - valid_coherence) / (2 * n_averages * valid_coherence))
    mean_error = float(np.mean(rel_error))
    max_error = float(np.max(rel_error))

    # Coherence grading
    if mean_coh >= 0.95 and min_coh >= 0.80:
        coherence_grade = "A"
    elif mean_coh >= 0.85 and min_coh >= 0.60:
        coherence_grade = "B"
    elif mean_coh >= 0.75 and min_coh >= 0.40:
        coherence_grade = "C"
    elif mean_coh >= 0.60:
        coherence_grade = "D"
    else:
        coherence_grade = "F"

    # SNR grading
    if mean_snr_db >= 20 and min_snr_db >= 10:
        snr_grade = "A"
    elif mean_snr_db >= 15 and min_snr_db >= 5:
        snr_grade = "B"
    elif mean_snr_db >= 10 and min_snr_db >= 0:
        snr_grade = "C"
    elif mean_snr_db >= 5:
        snr_grade = "D"
    else:
        snr_grade = "F"

    # Averaging adequacy
    averaging_adequate = max_error <= target_error

    # Overall grade (weighted combination)
    grade_values = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    overall_score = (
        0.5 * grade_values[coherence_grade] +
        0.3 * grade_values[snr_grade] +
        0.2 * (4 if averaging_adequate else 1)
    )

    if overall_score >= 3.5:
        overall_grade = "A"
    elif overall_score >= 2.5:
        overall_grade = "B"
    elif overall_score >= 1.5:
        overall_grade = "C"
    elif overall_score >= 0.5:
        overall_grade = "D"
    else:
        overall_grade = "F"

    # Recommendations
    recommendations = []

    if not averaging_adequate:
        needed = required_averages_for_error(median_coh, target_error)
        recommendations.append(
            f"Increase averaging from {n_averages} to {needed} for {target_error*100:.0f}% error target"
        )

    if min_coh < 0.6:
        # Find problem frequencies
        problem_mask = mask & (coherence < 0.6)
        if np.any(problem_mask):
            problem_freqs = frequencies[problem_mask]
            recommendations.append(
                f"Low coherence at frequencies around: {problem_freqs[:3]} Hz. "
                "Check for leakage, nonlinearity, or external noise."
            )

    if coherent_fraction < 0.8:
        recommendations.append(
            f"Only {coherent_fraction*100:.0f}% of frequencies have γ² > {coherence_threshold}. "
            "Consider reviewing measurement setup."
        )

    if mean_snr_db < 10:
        recommendations.append(
            f"Mean SNR is {mean_snr_db:.1f} dB. Increase excitation level or reduce noise."
        )

    if len(recommendations) == 0:
        recommendations.append("Measurement quality is acceptable for most applications.")

    metrics = {
        "mean_coherence": mean_coh,
        "min_coherence": min_coh,
        "median_coherence": median_coh,
        "coherent_fraction": coherent_fraction,
        "mean_snr_db": mean_snr_db,
        "min_snr_db": min_snr_db,
        "mean_relative_error": mean_error,
        "max_relative_error": max_error,
        "n_averages": n_averages,
        "frequency_range": (min_frequency, max_frequency),
        "n_frequency_bins": len(valid_freqs),
    }

    return QualityAssessment(
        overall_grade=overall_grade,
        coherence_grade=coherence_grade,
        snr_grade=snr_grade,
        averaging_adequate=averaging_adequate,
        recommendations=recommendations,
        metrics=metrics,
    )


def coherence_diagnostic(
    coherence: np.ndarray,
    frequencies: np.ndarray,
    threshold: float = 0.7,
) -> Dict[str, Any]:
    """
    Diagnose likely causes of low coherence.

    Parameters
    ----------
    coherence : np.ndarray
        Coherence values.
    frequencies : np.ndarray
        Frequency vector.
    threshold : float
        Threshold below which coherence is considered problematic.

    Returns
    -------
    Dict with diagnostic information.
    """
    problem_mask = coherence < threshold
    problem_freqs = frequencies[problem_mask]
    n_problems = len(problem_freqs)

    diagnosis = {
        "n_problem_frequencies": n_problems,
        "problem_fraction": float(np.mean(problem_mask)),
        "problem_frequencies": problem_freqs,
        "likely_causes": [],
    }

    if n_problems == 0:
        diagnosis["likely_causes"].append("No significant coherence problems")
        return diagnosis

    # Look for patterns
    freq_spacing = np.diff(frequencies)[0] if len(frequencies) > 1 else 1.0

    # Check for broadband low coherence
    if np.mean(problem_mask) > 0.5:
        diagnosis["likely_causes"].append(
            "Broadband low coherence: Check excitation level, "
            "sensor placement, or external noise"
        )

    # Check for periodic pattern (suggests leakage or harmonic issue)
    if len(problem_freqs) > 3:
        spacings = np.diff(problem_freqs)
        if np.std(spacings) / (np.mean(spacings) + 1e-6) < 0.2:
            avg_spacing = np.mean(spacings)
            diagnosis["likely_causes"].append(
                f"Periodic low coherence at ~{avg_spacing:.1f} Hz spacing: "
                "May indicate harmonic distortion or leakage"
            )

    # Check for low-frequency problems
    low_freq_problems = problem_freqs[problem_freqs < 100]
    if len(low_freq_problems) > len(problem_freqs) * 0.3:
        diagnosis["likely_causes"].append(
            "Low coherence concentrated at low frequencies: "
            "Check for DC offset, mechanical coupling, or insufficient excitation"
        )

    # Check for high-frequency problems
    nyquist = frequencies[-1]
    high_freq_problems = problem_freqs[problem_freqs > nyquist * 0.8]
    if len(high_freq_problems) > len(problem_freqs) * 0.3:
        diagnosis["likely_causes"].append(
            "Low coherence at high frequencies: "
            "May indicate aliasing, sensor bandwidth limits, or insufficient energy"
        )

    # Check for notch patterns (anti-resonances)
    if 0.1 < np.mean(problem_mask) < 0.3:
        diagnosis["likely_causes"].append(
            "Isolated low-coherence frequencies: "
            "May be structural anti-resonances or force spectrum notches"
        )

    if len(diagnosis["likely_causes"]) == 0:
        diagnosis["likely_causes"].append(
            "Inconclusive pattern: Review measurement setup systematically"
        )

    return diagnosis
