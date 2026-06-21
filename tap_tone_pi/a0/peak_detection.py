# INSTRUMENT CLASS: MEASUREMENT
"""A0 peak detection (DO-92).

Wraps tap_tone_pi.damping.modes for A0-specific peak detection.
Finds candidate peaks in the A0 frequency range and applies
selection methods.

No advisory semantics. No soundhole recommendations.
"""

from typing import List, Optional, Tuple

import numpy as np

from tap_tone_pi.a0.contracts import A0PeakCandidateV1, create_a0_peak_candidate
from tap_tone_pi.damping.modes import identify_modes, ModeConfidence


def find_a0_candidates(
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    *,
    frequency_range_hz: Tuple[float, float] = (70.0, 130.0),
    min_prominence_db: float = 6.0,
    max_candidates: int = 5,
) -> List[A0PeakCandidateV1]:
    """Find A0 candidate peaks in the specified frequency range.

    Uses tap_tone_pi.damping.modes.identify_modes for peak detection
    with half-power bandwidth and Q estimation.

    Args:
        frequencies: Frequency array in Hz
        magnitude: Magnitude array (linear, not dB)
        frequency_range_hz: Search range (default: 70-130 Hz)
        min_prominence_db: Minimum peak prominence
        max_candidates: Maximum candidates to return

    Returns:
        List of A0PeakCandidateV1, sorted by frequency
    """
    f_low, f_high = frequency_range_hz

    # Filter to frequency range
    mask = (frequencies >= f_low) & (frequencies <= f_high)
    if not np.any(mask):
        return []

    range_freqs = frequencies[mask]
    range_mag = magnitude[mask]

    # Use existing mode identification
    modes = identify_modes(
        range_freqs,
        range_mag,
        phase=None,
        min_prominence_db=min_prominence_db,
        min_spacing_hz=5.0,
        max_modes=max_candidates,
        use_stabilization=False,
    )

    # Convert to A0 candidates
    candidates = []
    for mode in modes:
        confidence_str = _confidence_to_string(mode.confidence)
        amplitude_db = 20 * np.log10(max(mode.amplitude, 1e-12))

        candidate = create_a0_peak_candidate(
            frequency_hz=mode.frequency_hz,
            amplitude_db=amplitude_db,
            bandwidth_hz=mode.bandwidth_hz,
            q_factor=mode.quality_factor,
            prominence_db=mode.spectral_prominence,
            confidence=confidence_str,
        )
        candidates.append(candidate)

    # Sort by frequency
    candidates.sort(key=lambda c: c.frequency_hz)

    return candidates


def select_candidate_by_method(
    candidates: List[A0PeakCandidateV1],
    method: str = "lowest_prominent_peak_in_range",
    *,
    min_prominence_db: float = 6.0,
) -> Optional[int]:
    """Select a candidate using the specified method.

    Available methods:
    - "lowest_prominent_peak_in_range": Lowest frequency peak above prominence threshold
    - "highest_amplitude": Peak with highest amplitude
    - "highest_q": Peak with highest Q factor

    Args:
        candidates: List of candidates
        method: Selection method
        min_prominence_db: Minimum prominence for "lowest_prominent" method

    Returns:
        Index of selected candidate, or None if no selection
    """
    if not candidates:
        return None

    if method == "lowest_prominent_peak_in_range":
        # Find lowest frequency peak that meets prominence threshold
        for i, c in enumerate(candidates):
            if c.prominence_db >= min_prominence_db:
                return i
        # Fall back to first candidate if none meet threshold
        return 0

    elif method == "highest_amplitude":
        # Peak with highest amplitude
        best_idx = 0
        best_amp = candidates[0].amplitude_db
        for i, c in enumerate(candidates[1:], 1):
            if c.amplitude_db > best_amp:
                best_amp = c.amplitude_db
                best_idx = i
        return best_idx

    elif method == "highest_q":
        # Peak with highest Q factor
        best_idx = 0
        best_q = candidates[0].q_factor
        for i, c in enumerate(candidates[1:], 1):
            if c.q_factor > best_q:
                best_q = c.q_factor
                best_idx = i
        return best_idx

    else:
        # Unknown method — return None
        return None


def _confidence_to_string(confidence: ModeConfidence) -> str:
    """Convert ModeConfidence enum to string."""
    if confidence == ModeConfidence.HIGH:
        return "high"
    elif confidence == ModeConfidence.MEDIUM:
        return "medium"
    elif confidence == ModeConfidence.LOW:
        return "low"
    else:
        return "low"
