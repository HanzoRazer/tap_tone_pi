"""
Mode identification and isolation for damping analysis.

This module provides algorithms for identifying modal frequencies from
spectral data and isolating individual mode responses for damping extraction.

Mathematical Background:
------------------------
Modal identification seeks to find the natural frequencies, damping ratios,
and mode shapes from measured frequency response data. Key concepts:

1. Stabilization Diagram:
   - Fit models of increasing order
   - Track which poles remain stable (within tolerance)
   - Stable poles indicate physical modes vs. computational artifacts

2. Modal Assurance Criterion (MAC):
   - Measures similarity between mode shapes
   - MAC(φ_i, φ_j) = |φ_i^H φ_j|² / (|φ_i|² |φ_j|²)
   - MAC > 0.9 indicates same mode
   - MAC < 0.1 indicates distinct modes

3. Mode Isolation:
   - Bandpass filtering around mode frequency
   - Hilbert transform for envelope extraction
   - Critical for accurate damping measurement
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from scipy import signal
from scipy.optimize import curve_fit
from enum import Enum


class ModeConfidence(Enum):
    """Confidence level in mode identification."""
    HIGH = "high"           # Stable across multiple orders, clear peak
    MEDIUM = "medium"       # Some stability, reasonable peak
    LOW = "low"             # Unstable or weak peak
    COMPUTATIONAL = "computational"  # Likely numerical artifact


@dataclass
class ModeIdentificationResult:
    """
    Result of modal identification for a single mode.

    Attributes
    ----------
    frequency_hz : float
        Identified natural frequency in Hz.
    damping_ratio : float
        Estimated damping ratio (ζ) from pole location.
    amplitude : float
        Peak amplitude at this mode.
    phase_deg : float
        Phase at resonance in degrees.
    bandwidth_hz : float
        Half-power bandwidth (f2 - f1).
    quality_factor : float
        Q = f_n / bandwidth.
    confidence : ModeConfidence
        Confidence level in this identification.
    stability_count : int
        Number of model orders where this mode appeared stable.
    mac_values : Dict[int, float]
        MAC values relative to other identified modes.
    spectral_prominence : float
        How much this peak stands out from local background (dB).
    frequency_std : float
        Standard deviation of frequency estimates across orders.
    damping_std : float
        Standard deviation of damping estimates across orders.
    metadata : Dict[str, Any]
        Additional analysis metadata.
    """
    frequency_hz: float
    damping_ratio: float
    amplitude: float
    phase_deg: float
    bandwidth_hz: float
    quality_factor: float
    confidence: ModeConfidence
    stability_count: int = 0
    mac_values: Dict[int, float] = field(default_factory=dict)
    spectral_prominence: float = 0.0
    frequency_std: float = 0.0
    damping_std: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


def identify_modes(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    phase: Optional[np.ndarray] = None,
    min_prominence_db: float = 6.0,
    min_spacing_hz: float = 10.0,
    max_modes: int = 20,
    use_stabilization: bool = True,
    model_orders: Optional[List[int]] = None,
    frequency_tolerance: float = 0.02,
    damping_tolerance: float = 0.10,
) -> List[ModeIdentificationResult]:
    """
    Identify modal frequencies from frequency response data.

    Uses peak detection with optional stabilization diagram validation.

    Parameters
    ----------
    freqs : np.ndarray
        Frequency vector in Hz.
    magnitude : np.ndarray
        Magnitude response (linear, not dB).
    phase : np.ndarray, optional
        Phase response in radians.
    min_prominence_db : float
        Minimum peak prominence in dB to consider as mode.
    min_spacing_hz : float
        Minimum frequency spacing between modes.
    max_modes : int
        Maximum number of modes to identify.
    use_stabilization : bool
        If True, use stabilization diagram for validation.
    model_orders : List[int], optional
        Model orders to use for stabilization. Default: [4, 6, 8, 10, 12, 14, 16].
    frequency_tolerance : float
        Relative tolerance for frequency stability (default 2%).
    damping_tolerance : float
        Relative tolerance for damping stability (default 10%).

    Returns
    -------
    List[ModeIdentificationResult]
        List of identified modes, sorted by frequency.

    Mathematical Notes
    ------------------
    Peak detection uses scipy.signal.find_peaks with prominence threshold.

    Stabilization is checked by fitting rational polynomial models of
    increasing order and tracking which poles remain within tolerance:

        |f_n^(k) - f_n^(k+2)| / f_n^(k) < frequency_tolerance
        |ζ^(k) - ζ^(k+2)| / ζ^(k) < damping_tolerance

    A mode is considered stable if it appears consistently across
    multiple model orders.
    """
    if model_orders is None:
        model_orders = [4, 6, 8, 10, 12, 14, 16]

    # Convert magnitude to dB for peak detection
    mag_db = 20 * np.log10(np.maximum(magnitude, 1e-12))

    # Calculate minimum distance in samples
    freq_resolution = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    min_distance_samples = max(1, int(min_spacing_hz / freq_resolution))

    # Find peaks with prominence
    peak_indices, properties = signal.find_peaks(
        mag_db,
        prominence=min_prominence_db,
        distance=min_distance_samples,
    )

    if len(peak_indices) == 0:
        return []

    # Sort by prominence and take top max_modes
    prominences = properties['prominences']
    sorted_indices = np.argsort(prominences)[::-1][:max_modes]
    peak_indices = peak_indices[sorted_indices]
    prominences = prominences[sorted_indices]

    # Resort by frequency for output
    freq_order = np.argsort(freqs[peak_indices])
    peak_indices = peak_indices[freq_order]
    prominences = prominences[freq_order]

    results = []

    for i, (idx, prominence) in enumerate(zip(peak_indices, prominences)):
        peak_freq = freqs[idx]
        peak_amp = magnitude[idx]
        peak_phase = phase[idx] if phase is not None else 0.0

        # Estimate bandwidth using half-power method
        bandwidth, q_factor = _estimate_bandwidth(
            freqs, magnitude, idx, peak_freq
        )

        # Initial damping estimate from Q
        damping_ratio = 1.0 / (2.0 * q_factor) if q_factor > 0 else 0.05

        # Stabilization analysis if requested
        if use_stabilization:
            stability_info = _check_stabilization(
                freqs, magnitude, peak_freq, model_orders,
                frequency_tolerance, damping_tolerance
            )
            stability_count = stability_info['stability_count']
            freq_std = stability_info['frequency_std']
            damping_std = stability_info['damping_std']

            # Determine confidence based on stability
            if stability_count >= len(model_orders) - 2:
                confidence = ModeConfidence.HIGH
            elif stability_count >= len(model_orders) // 2:
                confidence = ModeConfidence.MEDIUM
            elif stability_count >= 2:
                confidence = ModeConfidence.LOW
            else:
                confidence = ModeConfidence.COMPUTATIONAL
        else:
            stability_count = 0
            freq_std = 0.0
            damping_std = 0.0
            # Confidence based on prominence alone
            if prominence > 20:
                confidence = ModeConfidence.HIGH
            elif prominence > 12:
                confidence = ModeConfidence.MEDIUM
            else:
                confidence = ModeConfidence.LOW

        result = ModeIdentificationResult(
            frequency_hz=float(peak_freq),
            damping_ratio=float(damping_ratio),
            amplitude=float(peak_amp),
            phase_deg=float(np.degrees(peak_phase)),
            bandwidth_hz=float(bandwidth),
            quality_factor=float(q_factor),
            confidence=confidence,
            stability_count=stability_count,
            spectral_prominence=float(prominence),
            frequency_std=float(freq_std),
            damping_std=float(damping_std),
            metadata={
                'peak_index': int(idx),
                'model_orders': model_orders if use_stabilization else [],
            }
        )
        results.append(result)

    # Compute MAC values between modes
    _compute_mac_matrix(results, freqs, magnitude)

    return results


def _estimate_bandwidth(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    peak_idx: int,
    peak_freq: float,
) -> Tuple[float, float]:
    """
    Estimate half-power bandwidth around a peak.

    Returns (bandwidth_hz, quality_factor).
    """
    peak_mag = magnitude[peak_idx]
    half_power_level = peak_mag / np.sqrt(2)

    # Search left for lower -3dB point
    f1 = peak_freq
    for i in range(peak_idx - 1, -1, -1):
        if magnitude[i] < half_power_level:
            # Linear interpolation
            if i + 1 < len(freqs):
                ratio = (half_power_level - magnitude[i]) / (magnitude[i+1] - magnitude[i] + 1e-12)
                f1 = freqs[i] + ratio * (freqs[i+1] - freqs[i])
            else:
                f1 = freqs[i]
            break

    # Search right for upper -3dB point
    f2 = peak_freq
    for i in range(peak_idx + 1, len(freqs)):
        if magnitude[i] < half_power_level:
            # Linear interpolation
            if i > 0:
                ratio = (half_power_level - magnitude[i-1]) / (magnitude[i] - magnitude[i-1] + 1e-12)
                f2 = freqs[i-1] + ratio * (freqs[i] - freqs[i-1])
            else:
                f2 = freqs[i]
            break

    bandwidth = f2 - f1
    q_factor = peak_freq / bandwidth if bandwidth > 0 else 100.0

    return bandwidth, q_factor


def _check_stabilization(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    target_freq: float,
    model_orders: List[int],
    freq_tol: float,
    damp_tol: float,
) -> Dict[str, Any]:
    """
    Check stability of a mode across different model orders.

    Uses polynomial rational function fitting to extract poles.
    """
    freq_estimates = []
    damping_estimates = []

    for order in model_orders:
        try:
            # Fit rational polynomial around target frequency
            pole_freq, pole_damping = _fit_local_pole(
                freqs, magnitude, target_freq, order
            )
            if pole_freq is not None:
                freq_estimates.append(pole_freq)
                damping_estimates.append(pole_damping)
        except Exception:
            continue

    if len(freq_estimates) < 2:
        return {
            'stability_count': 0,
            'frequency_std': float('inf'),
            'damping_std': float('inf'),
        }

    freq_estimates = np.array(freq_estimates)
    damping_estimates = np.array(damping_estimates)

    # Count stable occurrences
    stability_count = 0
    ref_freq = np.median(freq_estimates)
    ref_damp = np.median(damping_estimates)

    for f, d in zip(freq_estimates, damping_estimates):
        freq_stable = abs(f - ref_freq) / ref_freq < freq_tol
        damp_stable = abs(d - ref_damp) / (ref_damp + 1e-6) < damp_tol
        if freq_stable and damp_stable:
            stability_count += 1

    return {
        'stability_count': stability_count,
        'frequency_std': float(np.std(freq_estimates)),
        'damping_std': float(np.std(damping_estimates)),
        'frequency_estimates': freq_estimates.tolist(),
        'damping_estimates': damping_estimates.tolist(),
    }


def _fit_local_pole(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    target_freq: float,
    order: int,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Fit a local pole near target frequency using rational polynomial.

    The transfer function near a resonance can be approximated as:

        H(s) ≈ A / (s² + 2ζω_n s + ω_n²)

    From which we extract the pole location s = -ζω_n ± jω_n√(1-ζ²)
    """
    # Select frequency range around target
    bandwidth = target_freq * 0.3  # 30% bandwidth for fitting
    mask = (freqs >= target_freq - bandwidth) & (freqs <= target_freq + bandwidth)

    if np.sum(mask) < order + 2:
        return None, None

    local_freqs = freqs[mask]
    local_mag = magnitude[mask]

    # Normalize for numerical stability
    freq_norm = target_freq
    mag_norm = np.max(local_mag)

    f_scaled = local_freqs / freq_norm
    m_scaled = local_mag / mag_norm

    # Fit using single-DOF resonance model
    def resonance_model(f, f_n, zeta, A):
        omega = 2 * np.pi * f
        omega_n = 2 * np.pi * f_n
        denom = np.sqrt((omega_n**2 - omega**2)**2 + (2*zeta*omega_n*omega)**2)
        return A * omega_n**2 / denom

    try:
        # Initial guesses
        p0 = [1.0, 0.05, 1.0]
        bounds = ([0.5, 0.001, 0.01], [2.0, 0.5, 10.0])

        popt, _ = curve_fit(
            resonance_model, f_scaled, m_scaled,
            p0=p0, bounds=bounds, maxfev=1000
        )

        pole_freq = popt[0] * freq_norm
        pole_damping = popt[1]

        return pole_freq, pole_damping
    except Exception:
        return None, None


def _compute_mac_matrix(
    modes: List[ModeIdentificationResult],
    freqs: np.ndarray,
    magnitude: np.ndarray,
) -> None:
    """
    Compute Modal Assurance Criterion between identified modes.

    MAC measures the correlation between mode shapes. For FRF-based
    identification with limited measurement points, we use the local
    spectral shape as a proxy for the mode shape.

    MAC(φ_i, φ_j) = |φ_i^H φ_j|² / (|φ_i|² |φ_j|²)

    Updates the mac_values dict in each ModeIdentificationResult.
    """
    for i, mode_i in enumerate(modes):
        mode_i.mac_values = {}

        # Extract local shape around mode i
        shape_i = _extract_local_shape(freqs, magnitude, mode_i.frequency_hz)

        for j, mode_j in enumerate(modes):
            if i == j:
                mode_i.mac_values[j] = 1.0
                continue

            # Extract local shape around mode j
            shape_j = _extract_local_shape(freqs, magnitude, mode_j.frequency_hz)

            # Compute MAC
            numerator = np.abs(np.vdot(shape_i, shape_j))**2
            denominator = np.vdot(shape_i, shape_i) * np.vdot(shape_j, shape_j)

            mac = numerator / (denominator + 1e-12)
            mode_i.mac_values[j] = float(mac)


def _extract_local_shape(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    center_freq: float,
    n_points: int = 21,
) -> np.ndarray:
    """Extract local spectral shape around a frequency."""
    bandwidth = center_freq * 0.15

    mask = (freqs >= center_freq - bandwidth) & (freqs <= center_freq + bandwidth)
    local_mag = magnitude[mask]

    # Resample to fixed number of points for consistent comparison
    if len(local_mag) < n_points:
        return np.pad(local_mag, (0, n_points - len(local_mag)), mode='edge')
    elif len(local_mag) > n_points:
        indices = np.linspace(0, len(local_mag) - 1, n_points).astype(int)
        return local_mag[indices]
    else:
        return local_mag


def isolate_mode_signal(
    signal_data: np.ndarray,
    sample_rate: float,
    mode_frequency: float,
    bandwidth_factor: float = 0.1,
    filter_order: int = 4,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Isolate a single mode from a broadband signal.

    Uses bandpass filtering followed by Hilbert transform for
    envelope extraction. Essential for accurate damping measurement.

    Parameters
    ----------
    signal_data : np.ndarray
        Time-domain signal containing multiple modes.
    sample_rate : float
        Sample rate in Hz.
    mode_frequency : float
        Center frequency of mode to isolate in Hz.
    bandwidth_factor : float
        Fractional bandwidth for filter (e.g., 0.1 = 10% of center freq).
    filter_order : int
        Order of Butterworth bandpass filter.

    Returns
    -------
    filtered_signal : np.ndarray
        Bandpass filtered signal containing primarily this mode.
    envelope : np.ndarray
        Amplitude envelope of the filtered signal.
    metadata : Dict
        Analysis metadata including filter parameters.

    Mathematical Notes
    ------------------
    The isolation process:

    1. Design Butterworth bandpass filter:
       f_low = f_n × (1 - bandwidth_factor)
       f_high = f_n × (1 + bandwidth_factor)

    2. Apply zero-phase filtering (filtfilt) to avoid phase distortion.

    3. Compute analytic signal via Hilbert transform:
       z(t) = x(t) + j×H{x(t)}

    4. Extract envelope:
       A(t) = |z(t)|

    For damping extraction, the envelope should decay as:
       A(t) = A_0 × exp(-ζω_n t)
    """
    nyquist = sample_rate / 2

    # Calculate filter frequencies
    bandwidth = mode_frequency * bandwidth_factor
    f_low = max(mode_frequency - bandwidth, 1.0)  # Avoid 0 Hz
    f_high = min(mode_frequency + bandwidth, nyquist * 0.95)

    # Normalize frequencies
    low_norm = f_low / nyquist
    high_norm = f_high / nyquist

    # Ensure valid frequency range
    if low_norm >= high_norm or high_norm >= 1.0:
        raise ValueError(
            f"Invalid filter frequencies: f_low={f_low:.1f} Hz, "
            f"f_high={f_high:.1f} Hz, nyquist={nyquist:.1f} Hz"
        )

    # Design Butterworth bandpass filter
    sos = signal.butter(
        filter_order, [low_norm, high_norm],
        btype='bandpass', output='sos'
    )

    # Apply zero-phase filtering
    filtered_signal = signal.sosfiltfilt(sos, signal_data)

    # Compute envelope via Hilbert transform
    analytic_signal = signal.hilbert(filtered_signal)
    envelope = np.abs(analytic_signal)

    # Compute instantaneous frequency for validation
    inst_phase = np.unwrap(np.angle(analytic_signal))
    inst_freq = np.gradient(inst_phase, 1/sample_rate) / (2 * np.pi)

    # Quality metrics
    mean_inst_freq = np.mean(inst_freq[len(inst_freq)//4:3*len(inst_freq)//4])
    freq_deviation = np.std(inst_freq[len(inst_freq)//4:3*len(inst_freq)//4])

    metadata = {
        'filter_type': 'butterworth_bandpass',
        'filter_order': filter_order,
        'f_low_hz': f_low,
        'f_high_hz': f_high,
        'bandwidth_hz': f_high - f_low,
        'bandwidth_factor': bandwidth_factor,
        'mean_instantaneous_freq_hz': float(mean_inst_freq),
        'instantaneous_freq_std_hz': float(freq_deviation),
        'freq_deviation_percent': float(100 * freq_deviation / mode_frequency),
        'signal_rms': float(np.sqrt(np.mean(filtered_signal**2))),
        'envelope_peak': float(np.max(envelope)),
    }

    return filtered_signal, envelope, metadata


def estimate_mode_count(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    frequency_range: Optional[Tuple[float, float]] = None,
    min_prominence_db: float = 3.0,
) -> Tuple[int, List[float]]:
    """
    Estimate the number of modes in a frequency range.

    Useful for setting model order in more sophisticated identification.

    Parameters
    ----------
    freqs : np.ndarray
        Frequency vector in Hz.
    magnitude : np.ndarray
        Magnitude response.
    frequency_range : Tuple[float, float], optional
        (f_min, f_max) to analyze. Default: full range.
    min_prominence_db : float
        Minimum peak prominence to count as mode.

    Returns
    -------
    n_modes : int
        Estimated number of modes.
    peak_frequencies : List[float]
        Frequencies of detected peaks.
    """
    if frequency_range is not None:
        mask = (freqs >= frequency_range[0]) & (freqs <= frequency_range[1])
        freqs = freqs[mask]
        magnitude = magnitude[mask]

    mag_db = 20 * np.log10(np.maximum(magnitude, 1e-12))

    peak_indices, properties = signal.find_peaks(
        mag_db, prominence=min_prominence_db
    )

    peak_frequencies = freqs[peak_indices].tolist()

    return len(peak_frequencies), peak_frequencies


def compute_modal_overlap(
    modes: List[ModeIdentificationResult],
) -> np.ndarray:
    """
    Compute modal overlap factors between identified modes.

    Modal overlap is defined as:
        M_ij = (ζ_i ω_i + ζ_j ω_j) / |ω_i - ω_j|

    High overlap (M > 0.3) indicates modes that are difficult to
    separate and may require more sophisticated analysis.

    Parameters
    ----------
    modes : List[ModeIdentificationResult]
        List of identified modes.

    Returns
    -------
    overlap_matrix : np.ndarray
        N×N matrix of overlap factors.
    """
    n = len(modes)
    overlap = np.zeros((n, n))

    for i in range(n):
        omega_i = 2 * np.pi * modes[i].frequency_hz
        zeta_i = modes[i].damping_ratio

        for j in range(n):
            if i == j:
                overlap[i, j] = np.inf  # Self-overlap is infinite
                continue

            omega_j = 2 * np.pi * modes[j].frequency_hz
            zeta_j = modes[j].damping_ratio

            freq_diff = abs(omega_i - omega_j)
            damping_sum = zeta_i * omega_i + zeta_j * omega_j

            overlap[i, j] = damping_sum / (freq_diff + 1e-12)

    return overlap
