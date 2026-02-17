"""
Peak detection for spectrum analysis.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from scipy.signal import find_peaks as scipy_find_peaks


def find_spectrum_peaks(
    freq_hz: np.ndarray,
    magnitude: np.ndarray,
    coherence: Optional[np.ndarray] = None,
    min_prominence: float = 0.1,
    min_distance: int = 10,
    min_coherence: float = 0.5,
    max_peaks: int = 20,
) -> List[Dict[str, float]]:
    """
    Find peaks in spectrum data.

    Args:
        freq_hz: Array of frequency values (Hz)
        magnitude: Array of magnitude values
        coherence: Array of coherence values (optional)
        min_prominence: Minimum peak prominence (relative to surrounding)
        min_distance: Minimum distance between peaks (in samples)
        min_coherence: Minimum coherence to consider a peak valid
        max_peaks: Maximum number of peaks to return

    Returns:
        List of peak dictionaries with freq_hz, magnitude, coherence
    """
    freq_hz = np.asarray(freq_hz)
    magnitude = np.asarray(magnitude)

    if len(freq_hz) == 0 or len(magnitude) == 0:
        return []

    # Handle log scale by working with log magnitude
    log_mag = np.log10(magnitude + 1e-10)

    # Find peaks using scipy
    peak_indices, properties = scipy_find_peaks(
        log_mag, prominence=min_prominence, distance=min_distance
    )

    # Build peak list
    peaks = []
    for idx in peak_indices:
        peak = {
            "freq_hz": float(freq_hz[idx]),
            "magnitude": float(magnitude[idx]),
            "index": int(idx),
        }

        # Add coherence if available
        if coherence is not None and len(coherence) > idx:
            coh_val = float(coherence[idx])
            peak["coherence"] = coh_val

            # Skip peaks with low coherence
            if coh_val < min_coherence:
                continue

        peaks.append(peak)

    # Sort by magnitude (strongest first) and limit
    peaks.sort(key=lambda p: p["magnitude"], reverse=True)
    peaks = peaks[:max_peaks]

    # Re-sort by frequency for display
    peaks.sort(key=lambda p: p["freq_hz"])

    return peaks


class PeakDetector:
    """
    Configurable peak detector for spectrum analysis.
    """

    def __init__(
        self,
        min_prominence: float = 0.1,
        min_distance: int = 10,
        min_coherence: float = 0.5,
        max_peaks: int = 20,
        freq_range: Optional[tuple] = None,
    ):
        """
        Initialize peak detector.

        Args:
            min_prominence: Minimum peak prominence
            min_distance: Minimum distance between peaks (samples)
            min_coherence: Minimum coherence threshold
            max_peaks: Maximum peaks to return
            freq_range: Optional (min_hz, max_hz) to limit search
        """
        self.min_prominence = min_prominence
        self.min_distance = min_distance
        self.min_coherence = min_coherence
        self.max_peaks = max_peaks
        self.freq_range = freq_range

    def detect(
        self,
        freq_hz: np.ndarray,
        magnitude: np.ndarray,
        coherence: Optional[np.ndarray] = None,
    ) -> List[Dict[str, float]]:
        """
        Detect peaks in spectrum data.

        Args:
            freq_hz: Frequency array
            magnitude: Magnitude array
            coherence: Coherence array (optional)

        Returns:
            List of peak dictionaries
        """
        freq_hz = np.asarray(freq_hz)
        magnitude = np.asarray(magnitude)

        # Apply frequency range filter
        if self.freq_range:
            mask = (freq_hz >= self.freq_range[0]) & (freq_hz <= self.freq_range[1])
            freq_hz = freq_hz[mask]
            magnitude = magnitude[mask]
            if coherence is not None:
                coherence = np.asarray(coherence)[mask]

        return find_spectrum_peaks(
            freq_hz,
            magnitude,
            coherence,
            min_prominence=self.min_prominence,
            min_distance=self.min_distance,
            min_coherence=self.min_coherence,
            max_peaks=self.max_peaks,
        )

    def identify_modes(self, peaks: List[Dict[str, float]]) -> List[Dict[str, Any]]:
        """
        Attempt to identify resonance modes from peak frequencies.

        This is a simplified heuristic based on typical wood resonance patterns.

        Args:
            peaks: List of detected peaks

        Returns:
            Peaks with mode identification added
        """
        if not peaks:
            return peaks

        # Sort by frequency
        sorted_peaks = sorted(peaks, key=lambda p: p["freq_hz"])

        # Identify fundamental (lowest significant peak)
        fundamental_freq = sorted_peaks[0]["freq_hz"]

        for i, peak in enumerate(sorted_peaks):
            freq = peak["freq_hz"]
            ratio = freq / fundamental_freq

            # Simple mode identification
            if i == 0:
                peak["mode"] = "fundamental"
            elif 1.9 < ratio < 2.1:
                peak["mode"] = "2nd harmonic"
            elif 2.9 < ratio < 3.1:
                peak["mode"] = "3rd harmonic"
            elif 3.9 < ratio < 4.1:
                peak["mode"] = "4th harmonic"
            else:
                # Check for typical wood modes
                if 200 < freq < 400:
                    peak["mode"] = "cross-grain?"
                elif 400 < freq < 600:
                    peak["mode"] = "tap tone"
                else:
                    peak["mode"] = f"mode {i+1}"

        return sorted_peaks


def estimate_q_factor(
    freq_hz: np.ndarray, magnitude: np.ndarray, peak_freq: float, peak_mag: float
) -> float:
    """
    Estimate Q factor (quality factor) for a peak.

    Q = f0 / bandwidth_3dB

    Args:
        freq_hz: Frequency array
        magnitude: Magnitude array
        peak_freq: Peak frequency
        peak_mag: Peak magnitude

    Returns:
        Estimated Q factor
    """
    freq_hz = np.asarray(freq_hz)
    magnitude = np.asarray(magnitude)

    # Find -3dB points (half power)
    half_power = peak_mag / np.sqrt(2)

    # Find indices around peak
    peak_idx = np.argmin(np.abs(freq_hz - peak_freq))

    # Search left for -3dB point
    left_idx = peak_idx
    while left_idx > 0 and magnitude[left_idx] > half_power:
        left_idx -= 1

    # Search right for -3dB point
    right_idx = peak_idx
    while right_idx < len(magnitude) - 1 and magnitude[right_idx] > half_power:
        right_idx += 1

    # Calculate bandwidth
    bandwidth = freq_hz[right_idx] - freq_hz[left_idx]

    if bandwidth > 0:
        return peak_freq / bandwidth
    else:
        return 0.0
