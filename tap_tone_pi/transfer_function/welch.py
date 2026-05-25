# INSTRUMENT CLASS: MEASUREMENT
"""
Welch method spectral estimation with configurable parameters.

The Welch method divides the signal into overlapping segments, applies
a window to each segment, computes the FFT, and averages the results.

Advantages:
- Reduces variance of spectral estimates
- Trades frequency resolution for reduced variance
- Provides consistent results for stationary signals

The method is named after Peter D. Welch who published it in 1967.

Key parameters:
- Segment length (nperseg): Determines frequency resolution
- Overlap (noverlap): Typically 50-75% of segment length
- Window: Reduces spectral leakage

Trade-offs:
- Longer segments → better frequency resolution
- More segments → better variance reduction
- More overlap → more effective averages (but diminishing returns)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np
from scipy import signal


@dataclass
class WelchResult:
    """
    Result of Welch spectral estimation.

    Attributes
    ----------
    frequencies : np.ndarray
        Frequency vector in Hz.
    spectrum : np.ndarray
        Power spectral density (real for auto, complex for cross).
    n_segments : int
        Number of segments averaged.
    frequency_resolution : float
        Hz per spectral line.
    effective_averages : float
        Effective independent averages (accounting for overlap).
    window_used : str
        Window function name.
    nperseg : int
        Samples per segment.
    noverlap : int
        Samples of overlap.
    """

    frequencies: np.ndarray
    spectrum: np.ndarray
    n_segments: int = 1
    frequency_resolution: float = 1.0
    effective_averages: float = 1.0
    window_used: str = "hann"
    nperseg: int = 0
    noverlap: int = 0


def welch_spectrum(
    signal_data: np.ndarray,
    sample_rate: float,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    window: str = "hann",
    detrend: str = "constant",
    scaling: str = "density",
) -> WelchResult:
    """
    Compute power spectral density using Welch's method.

    Parameters
    ----------
    signal_data : np.ndarray
        Time-domain signal.
    sample_rate : float
        Sample rate in Hz.
    nperseg : int, optional
        Length of each segment. Default: min(256, signal_length).
    noverlap : int, optional
        Number of points to overlap. Default: nperseg // 2.
    window : str
        Window function to use.
    detrend : str
        Detrending: "constant" (remove mean), "linear", or False.
    scaling : str
        "density" for V²/Hz, "spectrum" for V².

    Returns
    -------
    WelchResult
        Power spectral density result.

    Example
    -------
    >>> fs = 44100
    >>> t = np.arange(fs) / fs
    >>> x = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine
    >>> result = welch_spectrum(x, fs, nperseg=4096)
    """
    n = len(signal_data)

    if nperseg is None:
        nperseg = min(256, n)

    if noverlap is None:
        noverlap = nperseg // 2

    # Compute using scipy.signal.welch
    frequencies, psd = signal.welch(
        signal_data,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        window=window,
        detrend=detrend,
        scaling=scaling,
        return_onesided=True,
    )

    # Calculate segment count
    step = nperseg - noverlap
    n_segments = (n - noverlap) // step

    # Effective averages (accounting for overlap correlation)
    overlap_fraction = noverlap / nperseg
    effective_averages = n_segments * (1 - overlap_fraction) + overlap_fraction

    freq_resolution = (
        frequencies[1] - frequencies[0]
        if len(frequencies) > 1
        else sample_rate / nperseg
    )

    return WelchResult(
        frequencies=frequencies,
        spectrum=psd,
        n_segments=n_segments,
        frequency_resolution=freq_resolution,
        effective_averages=effective_averages,
        window_used=window,
        nperseg=nperseg,
        noverlap=noverlap,
    )


def welch_cross_spectrum(
    signal_x: np.ndarray,
    signal_y: np.ndarray,
    sample_rate: float,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    window: str = "hann",
    detrend: str = "constant",
) -> WelchResult:
    """
    Compute cross-spectral density using Welch's method.

    The cross-spectrum is complex-valued and contains phase information
    relating the two signals.

    Parameters
    ----------
    signal_x : np.ndarray
        First (reference) signal.
    signal_y : np.ndarray
        Second (response) signal.
    sample_rate : float
        Sample rate in Hz.
    nperseg : int, optional
        Length of each segment.
    noverlap : int, optional
        Number of points to overlap.
    window : str
        Window function to use.
    detrend : str
        Detrending method.

    Returns
    -------
    WelchResult
        Complex cross-spectral density result.
    """
    if len(signal_x) != len(signal_y):
        raise ValueError("Signals must have same length")

    n = len(signal_x)

    if nperseg is None:
        nperseg = min(256, n)

    if noverlap is None:
        noverlap = nperseg // 2

    # Compute using scipy.signal.csd
    frequencies, csd = signal.csd(
        signal_x,
        signal_y,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        window=window,
        detrend=detrend,
        return_onesided=True,
    )

    # Calculate segment count
    step = nperseg - noverlap
    n_segments = (n - noverlap) // step

    overlap_fraction = noverlap / nperseg
    effective_averages = n_segments * (1 - overlap_fraction) + overlap_fraction

    freq_resolution = (
        frequencies[1] - frequencies[0]
        if len(frequencies) > 1
        else sample_rate / nperseg
    )

    return WelchResult(
        frequencies=frequencies,
        spectrum=csd,
        n_segments=n_segments,
        frequency_resolution=freq_resolution,
        effective_averages=effective_averages,
        window_used=window,
        nperseg=nperseg,
        noverlap=noverlap,
    )


@dataclass
class WelchFRFResult:
    """
    Result of Welch-based transfer function estimation.

    Attributes
    ----------
    frequencies : np.ndarray
        Frequency vector in Hz.
    H1 : np.ndarray
        H1 estimator (complex).
    H2 : np.ndarray
        H2 estimator (complex).
    Hv : np.ndarray
        Hv estimator (complex).
    coherence : np.ndarray
        Coherence function γ².
    Gxx : np.ndarray
        Input auto-spectrum.
    Gyy : np.ndarray
        Output auto-spectrum.
    Gxy : np.ndarray
        Cross-spectrum.
    n_averages : int
        Number of segments averaged.
    frequency_resolution : float
        Hz per spectral line.
    """

    frequencies: np.ndarray
    H1: np.ndarray
    H2: np.ndarray
    Hv: np.ndarray
    coherence: np.ndarray
    Gxx: np.ndarray
    Gyy: np.ndarray
    Gxy: np.ndarray
    n_averages: int = 1
    frequency_resolution: float = 1.0


def welch_transfer_function(
    signal_input: np.ndarray,
    signal_output: np.ndarray,
    sample_rate: float,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    window: str = "hann",
    detrend: str = "constant",
) -> WelchFRFResult:
    """
    Compute all transfer function estimators using Welch's method.

    Returns H1, H2, Hv, and coherence all computed from the same
    Welch-averaged spectral estimates.

    Parameters
    ----------
    signal_input : np.ndarray
        Input (excitation) signal.
    signal_output : np.ndarray
        Output (response) signal.
    sample_rate : float
        Sample rate in Hz.
    nperseg : int, optional
        Length of each segment.
    noverlap : int, optional
        Number of points to overlap.
    window : str
        Window function to use.
    detrend : str
        Detrending method.

    Returns
    -------
    WelchFRFResult
        All estimators and spectral quantities.

    Example
    -------
    >>> result = welch_transfer_function(force, accel, 44100, nperseg=2048)
    >>> # Compare H1 and H2 to assess noise location
    >>> if np.mean(np.abs(result.H1)) < np.mean(np.abs(result.H2)):
    ...     print("Noise primarily on input")
    ... else:
    ...     print("Noise primarily on output")
    """
    if len(signal_input) != len(signal_output):
        raise ValueError("Signals must have same length")

    n = len(signal_input)

    if nperseg is None:
        nperseg = min(1024, n)

    if noverlap is None:
        noverlap = nperseg // 2

    # Compute all spectral quantities
    frequencies, Gxx = signal.welch(
        signal_input,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        window=window,
        detrend=detrend,
    )

    _, Gyy = signal.welch(
        signal_output,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        window=window,
        detrend=detrend,
    )

    _, Gxy = signal.csd(
        signal_input,
        signal_output,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        window=window,
        detrend=detrend,
    )

    # Compute estimators
    # H1 = Gxy / Gxx
    H1 = Gxy / np.maximum(Gxx, 1e-30)

    # H2 = Gyy / Gyx = Gyy × exp(j×angle(Gxy)) / |Gxy|
    Gyx = np.conj(Gxy)
    H2 = Gyy / np.maximum(np.abs(Gyx), 1e-30) * np.exp(1j * np.angle(Gxy))

    # Hv = sqrt(H1 × H2)
    Hv_mag = np.sqrt(np.abs(H1) * np.abs(H2))
    Hv_phase = (np.angle(H1) + np.angle(H2)) / 2
    Hv = Hv_mag * np.exp(1j * Hv_phase)

    # Coherence: γ² = |Gxy|² / (Gxx × Gyy)
    coherence = np.abs(Gxy) ** 2 / np.maximum(Gxx * Gyy, 1e-30)
    coherence = np.clip(coherence, 0.0, 1.0)

    # Segment count
    step = nperseg - noverlap
    n_segments = (n - noverlap) // step

    freq_resolution = (
        frequencies[1] - frequencies[0]
        if len(frequencies) > 1
        else sample_rate / nperseg
    )

    return WelchFRFResult(
        frequencies=frequencies,
        H1=H1,
        H2=H2,
        Hv=Hv,
        coherence=coherence,
        Gxx=Gxx,
        Gyy=Gyy,
        Gxy=Gxy,
        n_averages=n_segments,
        frequency_resolution=freq_resolution,
    )


def optimal_welch_parameters(
    signal_length: int,
    sample_rate: float,
    target_frequency_resolution: Optional[float] = None,
    target_variance_reduction: Optional[float] = None,
    overlap_fraction: float = 0.5,
) -> Dict[str, Any]:
    """
    Calculate optimal Welch parameters for given requirements.

    You can specify either target frequency resolution or target variance
    reduction, not both (they trade off against each other).

    Parameters
    ----------
    signal_length : int
        Total samples available.
    sample_rate : float
        Sample rate in Hz.
    target_frequency_resolution : float, optional
        Desired frequency resolution in Hz.
    target_variance_reduction : float, optional
        Desired variance reduction factor (e.g., 4.0 for 4× lower variance).
    overlap_fraction : float
        Overlap as fraction of segment length (default 0.5 = 50%).

    Returns
    -------
    Dict with:
        - nperseg: Recommended segment length
        - noverlap: Recommended overlap
        - n_segments: Expected number of segments
        - effective_averages: Effective independent averages
        - actual_freq_resolution: Resulting frequency resolution
        - actual_variance_reduction: Resulting variance reduction
    """
    if (
        target_frequency_resolution is not None
        and target_variance_reduction is not None
    ):
        raise ValueError(
            "Specify only one of target_frequency_resolution or target_variance_reduction"
        )

    if target_frequency_resolution is not None:
        # nperseg = fs / freq_resolution
        nperseg = int(sample_rate / target_frequency_resolution)
    elif target_variance_reduction is not None:
        # Need n_eff averages for variance_reduction factor
        # n_eff ≈ (signal_length - noverlap) / (nperseg - noverlap) × (1 - overlap_fraction)
        # For fixed signal_length, more segments → smaller nperseg
        n_eff_needed = target_variance_reduction
        # Approximate: n_segments ≈ signal_length / (nperseg × (1 - overlap_fraction))
        # n_eff ≈ n_segments × (1 - overlap_fraction) + overlap_fraction
        # Solve for nperseg
        nperseg = int(signal_length / (n_eff_needed / (1 - overlap_fraction)))
    else:
        # Default: balance resolution and variance
        nperseg = min(signal_length // 4, 4096)

    # Enforce reasonable bounds
    nperseg = max(64, min(nperseg, signal_length))
    # Make power of 2 for FFT efficiency
    nperseg = int(2 ** np.ceil(np.log2(nperseg)))
    nperseg = min(nperseg, signal_length)

    noverlap = int(nperseg * overlap_fraction)

    # Calculate resulting metrics
    step = nperseg - noverlap
    n_segments = max(1, (signal_length - noverlap) // step)
    effective_averages = n_segments * (1 - overlap_fraction) + overlap_fraction

    actual_freq_resolution = sample_rate / nperseg
    actual_variance_reduction = (
        effective_averages  # Variance reduced by factor of n_eff
    )

    return {
        "nperseg": nperseg,
        "noverlap": noverlap,
        "n_segments": n_segments,
        "effective_averages": float(effective_averages),
        "actual_freq_resolution": float(actual_freq_resolution),
        "actual_variance_reduction": float(actual_variance_reduction),
    }
