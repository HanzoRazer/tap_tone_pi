"""
Transfer function estimators with coherence calculation.

This module implements the three standard FRF estimators used in
structural dynamics and acoustics:

H1 Estimator: H1 = Gxy/Gxx
    - Minimizes noise in the output signal
    - Biased low when input has noise
    - Most common choice for impact testing

H2 Estimator: H2 = Gyy/Gyx
    - Minimizes noise in the input signal
    - Biased high when output has noise
    - Used when input excitation is noisy

Hv Estimator: Hv = sqrt(H1 × H2)
    - Geometric mean of H1 and H2
    - Unbiased estimate when SNR is known
    - Best choice when both signals have noise

The coherence function γ² provides a quality metric:
    γ² = |Gxy|² / (Gxx × Gyy)

For a perfect linear system with no noise, γ² = 1.
Coherence drops when:
    - Noise is present on input or output
    - System is nonlinear
    - System has changed during measurement
    - Leakage affects the measurement
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional
import numpy as np
from scipy import signal


@dataclass
class CoherenceResult:
    """
    Result of coherence calculation.

    Attributes
    ----------
    frequencies : np.ndarray
        Frequency vector in Hz.
    coherence : np.ndarray
        Coherence γ² at each frequency (0 to 1).
    mean_coherence : float
        Mean coherence over valid frequency range.
    min_coherence : float
        Minimum coherence in valid range.
    coherent_fraction : float
        Fraction of frequencies with coherence > threshold.
    problem_frequencies : np.ndarray
        Frequencies where coherence is low.
    quality_grade : str
        Overall quality: "excellent", "good", "acceptable", "poor"
    """

    frequencies: np.ndarray
    coherence: np.ndarray
    mean_coherence: float = 0.0
    min_coherence: float = 0.0
    coherent_fraction: float = 0.0
    problem_frequencies: np.ndarray = field(default_factory=lambda: np.array([]))
    quality_grade: str = "unknown"

    def get_coherence_at(self, freq: float) -> float:
        """Get coherence at specific frequency via interpolation."""
        return float(np.interp(freq, self.frequencies, self.coherence))


@dataclass
class TransferFunctionResult:
    """
    Result of transfer function estimation.

    Attributes
    ----------
    frequencies : np.ndarray
        Frequency vector in Hz.
    magnitude : np.ndarray
        |H(f)| magnitude response.
    phase : np.ndarray
        ∠H(f) phase response in radians.
    complex_frf : np.ndarray
        Complex H(f) = magnitude × exp(j×phase).
    coherence : CoherenceResult
        Coherence between input and output.
    estimator_used : str
        Which estimator was used ("H1", "H2", "Hv").
    n_averages : int
        Number of averages used.
    frequency_resolution : float
        Hz per spectral line.
    snr_estimate : np.ndarray
        Estimated SNR at each frequency (from coherence).
    magnitude_uncertainty : np.ndarray
        Uncertainty in magnitude (from coherence).
    phase_uncertainty : np.ndarray
        Uncertainty in phase (from coherence).
    """

    frequencies: np.ndarray
    magnitude: np.ndarray
    phase: np.ndarray
    complex_frf: np.ndarray
    coherence: CoherenceResult
    estimator_used: str = "H1"
    n_averages: int = 1
    frequency_resolution: float = 1.0
    snr_estimate: Optional[np.ndarray] = None
    magnitude_uncertainty: Optional[np.ndarray] = None
    phase_uncertainty: Optional[np.ndarray] = None

    @property
    def magnitude_db(self) -> np.ndarray:
        """Magnitude in dB."""
        return 20 * np.log10(np.maximum(self.magnitude, 1e-12))

    @property
    def phase_deg(self) -> np.ndarray:
        """Phase in degrees."""
        return np.degrees(self.phase)

    def get_value_at(self, freq: float) -> complex:
        """Get complex FRF value at specific frequency via interpolation."""
        mag = np.interp(freq, self.frequencies, self.magnitude)
        phs = np.interp(freq, self.frequencies, self.phase)
        return mag * np.exp(1j * phs)


def compute_auto_spectrum(
    signal_data: np.ndarray,
    sample_rate: float,
    n_fft: Optional[int] = None,
    window: str = "hann",
    detrend: str = "constant",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute auto-spectral density Gxx = E[X*(f) × X(f)].

    Parameters
    ----------
    signal_data : np.ndarray
        Time-domain signal.
    sample_rate : float
        Sample rate in Hz.
    n_fft : int, optional
        FFT length. Default: signal length.
    window : str
        Window function name.
    detrend : str
        Detrending: "constant" (remove mean), "linear", or False.

    Returns
    -------
    frequencies : np.ndarray
        Frequency vector in Hz.
    psd : np.ndarray
        Power spectral density (one-sided).
    """
    if n_fft is None:
        n_fft = len(signal_data)

    # Apply window
    win = signal.get_window(window, len(signal_data))
    win_factor = np.sum(win**2)

    # Detrend
    if detrend == "constant":
        signal_data = signal_data - np.mean(signal_data)
    elif detrend == "linear":
        signal_data = signal.detrend(signal_data, type="linear")

    # Apply window and FFT
    windowed = signal_data * win
    spectrum = np.fft.rfft(windowed, n=n_fft)

    # Compute PSD (one-sided)
    psd = np.abs(spectrum) ** 2 / (sample_rate * win_factor)
    # Double all except DC and Nyquist
    psd[1:-1] *= 2

    frequencies = np.fft.rfftfreq(n_fft, 1 / sample_rate)

    return frequencies, psd


def compute_cross_spectrum(
    signal_x: np.ndarray,
    signal_y: np.ndarray,
    sample_rate: float,
    n_fft: Optional[int] = None,
    window: str = "hann",
    detrend: str = "constant",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute cross-spectral density Gxy = E[X*(f) × Y(f)].

    The cross-spectrum is complex-valued and contains phase information.

    Parameters
    ----------
    signal_x : np.ndarray
        Input (reference) time-domain signal.
    signal_y : np.ndarray
        Output (response) time-domain signal.
    sample_rate : float
        Sample rate in Hz.
    n_fft : int, optional
        FFT length. Default: signal length.
    window : str
        Window function name.
    detrend : str
        Detrending method.

    Returns
    -------
    frequencies : np.ndarray
        Frequency vector in Hz.
    csd : np.ndarray
        Complex cross-spectral density.
    """
    if len(signal_x) != len(signal_y):
        raise ValueError("Signals must have same length")

    if n_fft is None:
        n_fft = len(signal_x)

    # Apply window
    win = signal.get_window(window, len(signal_x))
    win_factor = np.sum(win**2)

    # Detrend
    if detrend == "constant":
        signal_x = signal_x - np.mean(signal_x)
        signal_y = signal_y - np.mean(signal_y)
    elif detrend == "linear":
        signal_x = signal.detrend(signal_x, type="linear")
        signal_y = signal.detrend(signal_y, type="linear")

    # Apply window and FFT
    X = np.fft.rfft(signal_x * win, n=n_fft)
    Y = np.fft.rfft(signal_y * win, n=n_fft)

    # Cross-spectrum: X* × Y
    csd = np.conj(X) * Y / (sample_rate * win_factor)
    csd[1:-1] *= 2  # One-sided adjustment

    frequencies = np.fft.rfftfreq(n_fft, 1 / sample_rate)

    return frequencies, csd


def compute_coherence(
    signal_x: np.ndarray,
    signal_y: np.ndarray,
    sample_rate: float,
    n_fft: Optional[int] = None,
    n_overlap: Optional[int] = None,
    window: str = "hann",
    n_averages: int = 1,
    coherence_threshold: float = 0.8,
) -> CoherenceResult:
    """
    Compute coherence function γ²(f) = |Gxy|² / (Gxx × Gyy).

    Coherence indicates the linear relationship between input and output:
    - γ² = 1.0: Perfect linear relationship (no noise)
    - γ² = 0.0: No linear relationship
    - 0 < γ² < 1: Partial correlation (noise, nonlinearity, or leakage)

    Parameters
    ----------
    signal_x : np.ndarray
        Input (reference) signal.
    signal_y : np.ndarray
        Output (response) signal.
    sample_rate : float
        Sample rate in Hz.
    n_fft : int, optional
        FFT length for each segment.
    n_overlap : int, optional
        Overlap between segments. Default: n_fft//2.
    window : str
        Window function name.
    n_averages : int
        Expected number of averages (for quality assessment).
    coherence_threshold : float
        Threshold for "acceptable" coherence.

    Returns
    -------
    CoherenceResult
        Complete coherence analysis result.
    """
    if len(signal_x) != len(signal_y):
        raise ValueError("Signals must have same length")

    if n_fft is None:
        n_fft = min(len(signal_x), 4096)

    if n_overlap is None:
        n_overlap = n_fft // 2

    # Use scipy.signal.coherence for robust Welch-based calculation
    frequencies, coherence = signal.coherence(
        signal_x,
        signal_y,
        fs=sample_rate,
        nperseg=n_fft,
        noverlap=n_overlap,
        window=window,
    )

    # Clip to valid range (numerical errors can push slightly outside [0, 1])
    coherence = np.clip(coherence, 0.0, 1.0)

    # Quality metrics
    # Exclude DC and very low frequencies
    valid_mask = frequencies > (sample_rate / n_fft * 2)

    if np.any(valid_mask):
        valid_coh = coherence[valid_mask]
        mean_coh = float(np.mean(valid_coh))
        min_coh = float(np.min(valid_coh))
        coherent_frac = float(np.mean(valid_coh > coherence_threshold))

        # Find problem frequencies
        problem_mask = valid_mask & (coherence < coherence_threshold)
        problem_freqs = frequencies[problem_mask]
    else:
        mean_coh = 0.0
        min_coh = 0.0
        coherent_frac = 0.0
        problem_freqs = np.array([])

    # Quality grade
    if mean_coh > 0.95 and min_coh > 0.8:
        grade = "excellent"
    elif mean_coh > 0.85 and min_coh > 0.6:
        grade = "good"
    elif mean_coh > 0.7 and min_coh > 0.4:
        grade = "acceptable"
    else:
        grade = "poor"

    return CoherenceResult(
        frequencies=frequencies,
        coherence=coherence,
        mean_coherence=mean_coh,
        min_coherence=min_coh,
        coherent_fraction=coherent_frac,
        problem_frequencies=problem_freqs,
        quality_grade=grade,
    )


def estimate_h1(
    Gxy: np.ndarray,
    Gxx: np.ndarray,
) -> np.ndarray:
    """
    H1 estimator: H1 = Gxy / Gxx

    Minimizes noise contribution from output signal.
    Biased low when input has noise.

    Parameters
    ----------
    Gxy : np.ndarray
        Cross-spectral density (complex).
    Gxx : np.ndarray
        Input auto-spectral density (real, positive).

    Returns
    -------
    np.ndarray
        Complex H1 estimate.
    """
    return Gxy / np.maximum(Gxx, 1e-30)


def estimate_h2(
    Gyy: np.ndarray,
    Gxy: np.ndarray,
) -> np.ndarray:
    """
    H2 estimator: H2 = Gyy / Gyx = Gyy / conj(Gxy)

    Minimizes noise contribution from input signal.
    Biased high when output has noise.

    Parameters
    ----------
    Gyy : np.ndarray
        Output auto-spectral density (real, positive).
    Gxy : np.ndarray
        Cross-spectral density (complex).

    Returns
    -------
    np.ndarray
        Complex H2 estimate.
    """
    Gyx = np.conj(Gxy)
    return Gyy / np.maximum(np.abs(Gyx), 1e-30) * np.exp(1j * np.angle(Gxy))


def estimate_hv(
    H1: np.ndarray,
    H2: np.ndarray,
) -> np.ndarray:
    """
    Hv estimator: Hv = sqrt(H1 × H2)

    Geometric mean of H1 and H2. Unbiased when noise characteristics
    are known. Best choice when both input and output have noise.

    Parameters
    ----------
    H1 : np.ndarray
        H1 estimate (complex).
    H2 : np.ndarray
        H2 estimate (complex).

    Returns
    -------
    np.ndarray
        Complex Hv estimate.
    """
    # Geometric mean of magnitudes, average of phases
    mag_v = np.sqrt(np.abs(H1) * np.abs(H2))
    phase_v = (np.angle(H1) + np.angle(H2)) / 2
    return mag_v * np.exp(1j * phase_v)


def estimate_transfer_function(
    signal_input: np.ndarray,
    signal_output: np.ndarray,
    sample_rate: float,
    n_fft: Optional[int] = None,
    n_overlap: Optional[int] = None,
    window: str = "hann",
    estimator: str = "H1",
    detrend: str = "constant",
    compute_uncertainty: bool = True,
) -> TransferFunctionResult:
    """
    Estimate transfer function with coherence and uncertainty.

    This is the main entry point for FRF estimation. It computes
    the transfer function using the specified estimator and provides
    quality metrics from coherence.

    Parameters
    ----------
    signal_input : np.ndarray
        Input (excitation) signal - e.g., force from impact hammer.
    signal_output : np.ndarray
        Output (response) signal - e.g., acceleration from accelerometer.
    sample_rate : float
        Sample rate in Hz.
    n_fft : int, optional
        FFT length for each segment. Default: min(signal_length, 4096).
    n_overlap : int, optional
        Overlap between segments. Default: n_fft // 2.
    window : str
        Window function: "hann", "hamming", "blackman", "flattop", etc.
    estimator : str
        Estimator to use: "H1" (default), "H2", or "Hv".
    detrend : str
        Detrending: "constant" (remove mean), "linear", or False.
    compute_uncertainty : bool
        If True, compute uncertainty bounds from coherence.

    Returns
    -------
    TransferFunctionResult
        Complete FRF result with coherence and uncertainty.

    Example
    -------
    >>> # Impact test: hammer force and accelerometer response
    >>> force = np.random.randn(8192)  # Input
    >>> accel = np.random.randn(8192)  # Output
    >>> result = estimate_transfer_function(force, accel, 44100)
    >>> print(f"Mean coherence: {result.coherence.mean_coherence:.2f}")
    """
    if len(signal_input) != len(signal_output):
        raise ValueError("Input and output signals must have same length")

    if n_fft is None:
        n_fft = min(len(signal_input), 4096)

    if n_overlap is None:
        n_overlap = n_fft // 2

    # Use scipy.signal.csd for Welch method with proper averaging
    freqs, Gxy = signal.csd(
        signal_input,
        signal_output,
        fs=sample_rate,
        nperseg=n_fft,
        noverlap=n_overlap,
        window=window,
        detrend=detrend,
        return_onesided=True,
    )

    _, Gxx = signal.welch(
        signal_input,
        fs=sample_rate,
        nperseg=n_fft,
        noverlap=n_overlap,
        window=window,
        detrend=detrend,
        return_onesided=True,
    )

    _, Gyy = signal.welch(
        signal_output,
        fs=sample_rate,
        nperseg=n_fft,
        noverlap=n_overlap,
        window=window,
        detrend=detrend,
        return_onesided=True,
    )

    # Compute coherence
    coherence_result = compute_coherence(
        signal_input,
        signal_output,
        sample_rate,
        n_fft=n_fft,
        n_overlap=n_overlap,
        window=window,
    )

    # Compute H1 and H2
    H1_est = estimate_h1(Gxy, Gxx)
    H2_est = estimate_h2(Gyy, Gxy)

    # Select estimator
    if estimator.upper() == "H1":
        H = H1_est
    elif estimator.upper() == "H2":
        H = H2_est
    elif estimator.upper() == "HV":
        H = estimate_hv(H1_est, H2_est)
    else:
        raise ValueError(f"Unknown estimator: {estimator}. Use 'H1', 'H2', or 'Hv'.")

    magnitude = np.abs(H)
    phase = np.angle(H)

    # Number of averages (approximate from segment count)
    n_segments = (len(signal_input) - n_overlap) // (n_fft - n_overlap)
    n_averages = max(1, n_segments)

    # Uncertainty from coherence (if requested)
    snr_est = None
    mag_uncertainty = None
    phase_uncertainty = None

    if compute_uncertainty:
        gamma_sq = coherence_result.coherence

        # SNR estimate from coherence: SNR = γ²/(1-γ²)
        snr_est = gamma_sq / np.maximum(1 - gamma_sq, 1e-10)

        # Normalized random error in |H|:
        # ε|H| = sqrt((1-γ²) / (2×n×γ²))
        mag_uncertainty = magnitude * np.sqrt(
            (1 - gamma_sq) / np.maximum(2 * n_averages * gamma_sq, 1e-10)
        )

        # Phase uncertainty (radians):
        # σ_φ = sqrt((1-γ²) / (2×n×γ²))
        phase_uncertainty = np.sqrt(
            (1 - gamma_sq) / np.maximum(2 * n_averages * gamma_sq, 1e-10)
        )

    freq_resolution = freqs[1] - freqs[0] if len(freqs) > 1 else sample_rate / n_fft

    return TransferFunctionResult(
        frequencies=freqs,
        magnitude=magnitude,
        phase=phase,
        complex_frf=H,
        coherence=coherence_result,
        estimator_used=estimator.upper(),
        n_averages=n_averages,
        frequency_resolution=freq_resolution,
        snr_estimate=snr_est,
        magnitude_uncertainty=mag_uncertainty,
        phase_uncertainty=phase_uncertainty,
    )
