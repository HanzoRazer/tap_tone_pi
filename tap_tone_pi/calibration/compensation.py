# INSTRUMENT CLASS: MEASUREMENT
"""
Compensation curves for calibrated measurements.

Applies frequency-dependent corrections based on loopback calibration data.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from scipy.interpolate import interp1d

from .loopback import FrequencyResponsePoint


@dataclass
class CompensationCurve:
    """
    Frequency-dependent compensation curve.

    Stores inverse of measured system response for correction.
    """

    # Curve data
    frequencies_hz: np.ndarray = field(default_factory=lambda: np.array([]))
    correction_db: np.ndarray = field(default_factory=lambda: np.array([]))
    correction_phase_deg: np.ndarray = field(default_factory=lambda: np.array([]))

    # Metadata
    device_index: int = 0
    device_name: str = ""
    created_at: str = ""

    # Interpolators (built on demand)
    _mag_interp: Optional[interp1d] = field(default=None, repr=False)
    _phase_interp: Optional[interp1d] = field(default=None, repr=False)

    def __post_init__(self):
        """Build interpolators after initialization."""
        self._build_interpolators()

    def _build_interpolators(self):
        """Build interpolation functions for correction lookup."""
        if len(self.frequencies_hz) < 2:
            return

        # Use linear interpolation with extrapolation for edges
        self._mag_interp = interp1d(
            self.frequencies_hz,
            self.correction_db,
            kind="linear",
            bounds_error=False,
            fill_value=(self.correction_db[0], self.correction_db[-1]),
        )

        self._phase_interp = interp1d(
            self.frequencies_hz,
            self.correction_phase_deg,
            kind="linear",
            bounds_error=False,
            fill_value=(self.correction_phase_deg[0], self.correction_phase_deg[-1]),
        )

    def get_correction_at_freq(self, freq_hz: float) -> Tuple[float, float]:
        """
        Get magnitude and phase correction at specific frequency.

        Args:
            freq_hz: Frequency in Hz

        Returns:
            Tuple of (magnitude_correction_db, phase_correction_deg)
        """
        if self._mag_interp is None or self._phase_interp is None:
            return 0.0, 0.0

        mag_corr = float(self._mag_interp(freq_hz))
        phase_corr = float(self._phase_interp(freq_hz))

        return mag_corr, phase_corr

    def get_corrections_at_freqs(
        self, frequencies_hz: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get corrections for array of frequencies.

        Args:
            frequencies_hz: Array of frequencies in Hz

        Returns:
            Tuple of (magnitude_corrections_db, phase_corrections_deg)
        """
        if self._mag_interp is None or self._phase_interp is None:
            return np.zeros_like(frequencies_hz), np.zeros_like(frequencies_hz)

        mag_corr = self._mag_interp(frequencies_hz)
        phase_corr = self._phase_interp(frequencies_hz)

        return mag_corr, phase_corr

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "frequencies_hz": self.frequencies_hz.tolist(),
            "correction_db": self.correction_db.tolist(),
            "correction_phase_deg": self.correction_phase_deg.tolist(),
            "device_index": self.device_index,
            "device_name": self.device_name,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CompensationCurve":
        """Create from dictionary."""
        curve = cls(
            frequencies_hz=np.array(d.get("frequencies_hz", [])),
            correction_db=np.array(d.get("correction_db", [])),
            correction_phase_deg=np.array(d.get("correction_phase_deg", [])),
            device_index=d.get("device_index", 0),
            device_name=d.get("device_name", ""),
            created_at=d.get("created_at", ""),
        )
        curve._build_interpolators()
        return curve


def build_compensation_curve(
    frequency_response: List[FrequencyResponsePoint],
    device_index: int = 0,
    device_name: str = "",
    smoothing_octaves: float = 0.0,
    max_correction_db: float = 12.0,
) -> CompensationCurve:
    """
    Build compensation curve from loopback frequency response.

    The compensation curve is the inverse of the measured response,
    so applying it to measurements cancels out system coloration.

    Args:
        frequency_response: Measured frequency response points from loopback test
        device_index: Device index for metadata
        device_name: Device name for metadata
        smoothing_octaves: Smoothing width in octaves (0 = no smoothing)
        max_correction_db: Maximum correction magnitude (clips extremes)

    Returns:
        CompensationCurve ready for application
    """
    from datetime import datetime

    if not frequency_response:
        return CompensationCurve(
            device_index=device_index,
            device_name=device_name,
            created_at=datetime.now().isoformat(),
        )

    # Extract arrays from frequency response
    frequencies = np.array([p.freq_hz for p in frequency_response])
    magnitudes = np.array([p.magnitude_db for p in frequency_response])
    phases = np.array([p.phase_deg for p in frequency_response])

    # Compute correction (inverse of response)
    # If system boosts +3dB at 1kHz, we need to apply -3dB correction
    correction_db = -magnitudes

    # Normalize so average correction is 0dB
    # This preserves overall level while correcting frequency response shape
    correction_db -= np.mean(correction_db)

    # Clip extreme corrections
    correction_db = np.clip(correction_db, -max_correction_db, max_correction_db)

    # Phase correction (inverse of measured phase deviation)
    # Subtract linear phase component (latency) to get just response phase
    if len(frequencies) > 1:
        # Fit linear phase (group delay)
        phase_slope = np.polyfit(frequencies, phases, 1)[0]
        linear_phase = phase_slope * frequencies
        phase_deviation = phases - linear_phase
        correction_phase = -phase_deviation
    else:
        correction_phase = -phases

    # Apply smoothing if requested
    if smoothing_octaves > 0:
        correction_db = _smooth_in_octaves(
            frequencies, correction_db, smoothing_octaves
        )
        correction_phase = _smooth_in_octaves(
            frequencies, correction_phase, smoothing_octaves
        )

    curve = CompensationCurve(
        frequencies_hz=frequencies,
        correction_db=correction_db,
        correction_phase_deg=correction_phase,
        device_index=device_index,
        device_name=device_name,
        created_at=datetime.now().isoformat(),
    )

    return curve


def _smooth_in_octaves(
    frequencies: np.ndarray, values: np.ndarray, octave_width: float
) -> np.ndarray:
    """
    Apply smoothing with octave-based window.

    Args:
        frequencies: Frequency array
        values: Values to smooth
        octave_width: Smoothing width in octaves

    Returns:
        Smoothed values
    """
    smoothed = np.zeros_like(values)

    for i, f in enumerate(frequencies):
        if f <= 0:
            smoothed[i] = values[i]
            continue

        # Define octave-based window
        f_low = f / (2 ** (octave_width / 2))
        f_high = f * (2 ** (octave_width / 2))

        # Find points in window
        mask = (frequencies >= f_low) & (frequencies <= f_high)

        if np.any(mask):
            # Triangular weighting within window
            log_freqs = np.log2(frequencies[mask] / f)
            weights = 1 - np.abs(log_freqs) / (octave_width / 2)
            weights = np.maximum(weights, 0)

            if np.sum(weights) > 0:
                smoothed[i] = np.average(values[mask], weights=weights)
            else:
                smoothed[i] = values[i]
        else:
            smoothed[i] = values[i]

    return smoothed


def apply_compensation(
    frequencies_hz: np.ndarray,
    magnitude_db: np.ndarray,
    compensation: CompensationCurve,
    apply_phase: bool = False,
    phase_deg: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Apply compensation curve to measurement.

    Args:
        frequencies_hz: Frequency array of measurement
        magnitude_db: Magnitude array in dB
        compensation: Compensation curve to apply
        apply_phase: Whether to also apply phase correction
        phase_deg: Phase array in degrees (required if apply_phase=True)

    Returns:
        Tuple of (corrected_magnitude_db, corrected_phase_deg or None)
    """
    # Get corrections at measurement frequencies
    mag_corr, phase_corr = compensation.get_corrections_at_freqs(frequencies_hz)

    # Apply magnitude correction
    corrected_magnitude = magnitude_db + mag_corr

    # Apply phase correction if requested
    corrected_phase = None
    if apply_phase and phase_deg is not None:
        corrected_phase = phase_deg + phase_corr

    return corrected_magnitude, corrected_phase


def apply_compensation_to_spectrum(
    spectrum: np.ndarray,
    sample_rate: int,
    compensation: CompensationCurve,
) -> np.ndarray:
    """
    Apply compensation to complex spectrum (FFT result).

    This applies both magnitude and phase correction in the frequency domain.

    Args:
        spectrum: Complex FFT result (rfft output)
        sample_rate: Sample rate in Hz
        compensation: Compensation curve to apply

    Returns:
        Corrected complex spectrum
    """
    # Generate frequency array for spectrum
    n_bins = len(spectrum)
    frequencies = np.fft.rfftfreq(2 * (n_bins - 1), 1.0 / sample_rate)

    # Get corrections
    mag_corr_db, phase_corr_deg = compensation.get_corrections_at_freqs(frequencies)

    # Convert dB correction to linear multiplier
    mag_multiplier = 10 ** (mag_corr_db / 20.0)

    # Convert phase correction to radians
    phase_corr_rad = np.deg2rad(phase_corr_deg)

    # Apply corrections
    # magnitude * exp(j * phase) = complex multiplier
    correction = mag_multiplier * np.exp(1j * phase_corr_rad)

    return spectrum * correction


def estimate_uncertainty_with_compensation(
    base_uncertainty_db: float,
    compensation: CompensationCurve,
    freq_hz: float,
) -> float:
    """
    Estimate measurement uncertainty including compensation effects.

    Compensation adds some uncertainty due to:
    - Interpolation between calibration points
    - Time-varying system response
    - Temperature/humidity changes since calibration

    Args:
        base_uncertainty_db: Base measurement uncertainty in dB
        compensation: Applied compensation curve
        freq_hz: Measurement frequency in Hz

    Returns:
        Total estimated uncertainty in dB
    """
    # Get correction magnitude at this frequency
    correction_db, _ = compensation.get_correction_at_freq(freq_hz)

    # Larger corrections = more uncertainty
    # Assume 10% of correction magnitude as additional uncertainty
    correction_uncertainty = abs(correction_db) * 0.1

    # Find nearest calibration points and estimate interpolation error
    freq_array = compensation.frequencies_hz
    if len(freq_array) > 1:
        # Find spacing around this frequency
        idx = np.searchsorted(freq_array, freq_hz)
        if 0 < idx < len(freq_array):
            spacing_ratio = (freq_array[idx] - freq_array[idx - 1]) / freq_hz
            # Wider spacing = more interpolation uncertainty
            interp_uncertainty = spacing_ratio * 0.5  # Rough estimate
        else:
            interp_uncertainty = 0.5  # Edge extrapolation penalty
    else:
        interp_uncertainty = 1.0  # No calibration data

    # Combine uncertainties (RSS)
    total_uncertainty = np.sqrt(
        base_uncertainty_db**2 + correction_uncertainty**2 + interp_uncertainty**2
    )

    return float(total_uncertainty)
