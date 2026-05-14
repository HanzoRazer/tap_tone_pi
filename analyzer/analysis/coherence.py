"""
Coherence analysis for measurement quality assessment.
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np
from scipy.signal import coherence as scipy_coherence


def compute_coherence(
    input_signal: np.ndarray,
    output_signal: np.ndarray,
    sample_rate: float,
    nperseg: int = 2048,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute coherence between input and output signals.

    Coherence measures how well the output is linearly related to the input
    at each frequency. Values range from 0 (no relationship) to 1 (perfect).

    Args:
        input_signal: Input (excitation) signal
        output_signal: Output (response) signal
        sample_rate: Sample rate in Hz
        nperseg: Segment length for spectral estimation

    Returns:
        Tuple of (frequencies, coherence)
    """
    return scipy_coherence(input_signal, output_signal, fs=sample_rate, nperseg=nperseg)


def analyze_coherence_quality(
    coherence: np.ndarray,
    frequencies: Optional[np.ndarray] = None,
    threshold: float = 0.9,
) -> Dict[str, Any]:
    """
    Analyze coherence data for measurement quality.

    Args:
        coherence: Array of coherence values
        frequencies: Optional frequency array
        threshold: Coherence threshold for "good" measurement (default 0.9)

    Returns:
        Dictionary with quality metrics
    """
    coherence = np.asarray(coherence)

    if len(coherence) == 0:
        return {
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std": 0.0,
            "pct_above_threshold": 0.0,
            "quality_grade": "F",
            "issues": ["No coherence data"],
        }

    mean_coh = float(np.mean(coherence))
    min_coh = float(np.min(coherence))
    max_coh = float(np.max(coherence))
    std_coh = float(np.std(coherence))
    pct_above = float(np.sum(coherence >= threshold) / len(coherence) * 100)

    # Quality grading
    issues = []

    if mean_coh >= 0.95:
        grade = "A"
    elif mean_coh >= 0.90:
        grade = "B"
    elif mean_coh >= 0.80:
        grade = "C"
        issues.append("Moderate coherence - some noise present")
    elif mean_coh >= 0.60:
        grade = "D"
        issues.append("Low coherence - significant noise or nonlinearity")
    else:
        grade = "F"
        issues.append("Very low coherence - measurement unreliable")

    # Check for specific issues
    if min_coh < 0.5:
        issues.append(f"Very low coherence regions detected (min={min_coh:.2f})")

    if std_coh > 0.2:
        issues.append("High coherence variability across frequency")

    if pct_above < 50:
        issues.append(f"Only {pct_above:.0f}% of frequencies above threshold")

    return {
        "mean": mean_coh,
        "min": min_coh,
        "max": max_coh,
        "std": std_coh,
        "pct_above_threshold": pct_above,
        "threshold": threshold,
        "quality_grade": grade,
        "issues": issues,
    }


def find_low_coherence_regions(
    frequencies: np.ndarray,
    coherence: np.ndarray,
    threshold: float = 0.7,
    min_width_hz: float = 20,
) -> list:
    """
    Find frequency regions with low coherence.

    These regions indicate unreliable measurements, possibly due to:
    - Noise
    - Nonlinear behavior
    - Modal nulls
    - Measurement artifacts

    Args:
        frequencies: Frequency array
        coherence: Coherence array
        threshold: Coherence threshold
        min_width_hz: Minimum region width to report

    Returns:
        List of (start_hz, end_hz, mean_coherence) tuples
    """
    frequencies = np.asarray(frequencies)
    coherence = np.asarray(coherence)

    below_threshold = coherence < threshold
    regions = []

    in_region = False
    start_idx = 0

    for i, below in enumerate(below_threshold):
        if below and not in_region:
            # Start of low coherence region
            in_region = True
            start_idx = i
        elif not below and in_region:
            # End of low coherence region
            in_region = False
            end_idx = i

            # Check if region is wide enough
            width = frequencies[end_idx] - frequencies[start_idx]
            if width >= min_width_hz:
                mean_coh = float(np.mean(coherence[start_idx:end_idx]))
                regions.append(
                    (
                        float(frequencies[start_idx]),
                        float(frequencies[end_idx]),
                        mean_coh,
                    )
                )

    # Handle region at end
    if in_region:
        width = frequencies[-1] - frequencies[start_idx]
        if width >= min_width_hz:
            mean_coh = float(np.mean(coherence[start_idx:]))
            regions.append(
                (float(frequencies[start_idx]), float(frequencies[-1]), mean_coh)
            )

    return regions


def suggest_improvements(quality_analysis: Dict[str, Any]) -> list:
    """
    Suggest measurement improvements based on quality analysis.

    Args:
        quality_analysis: Output from analyze_coherence_quality()

    Returns:
        List of improvement suggestions
    """
    suggestions = []
    grade = quality_analysis.get("quality_grade", "F")
    mean_coh = quality_analysis.get("mean", 0)
    pct_above = quality_analysis.get("pct_above_threshold", 0)

    if grade in ["D", "F"]:
        suggestions.append("Consider increasing averaging count (more taps)")
        suggestions.append(
            "Check microphone placement - too close or too far from specimen"
        )
        suggestions.append("Reduce background noise if possible")

    if mean_coh < 0.8:
        suggestions.append("Try different excitation point on specimen")
        suggestions.append("Ensure consistent tap force and location")

    if pct_above < 70:
        suggestions.append("Check for mechanical vibration or rattling")
        suggestions.append("Verify specimen is properly supported (minimal contact)")

    if quality_analysis.get("std", 0) > 0.15:
        suggestions.append(
            "Coherence varies widely - check for mode splitting or coupling"
        )

    if not suggestions:
        suggestions.append("Measurement quality is good - no improvements needed")

    return suggestions
