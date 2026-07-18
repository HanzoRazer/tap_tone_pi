# INSTRUMENT CLASS: MEASUREMENT
"""Phase 2 DSP: Transfer function and coherence computation.

This module provides the core DSP functions for two-channel ODS
(Operational Deflection Shape) analysis.

Migration
---------
    # Old import (deprecated)
    from scripts.phase2.dsp import compute_transfer_and_coherence, TFResult

    # New import (v2.0.0+)
    from tap_tone_pi.core.dsp import compute_transfer_and_coherence, TFResult
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

import numpy as np
import scipy
from scipy.signal import csd, welch


# Provenance constants for reproducibility audit trail
DSP_ALGO_VERSION = "1.0.0"
DSP_ALGO_ID = "phase2_transfer_coherence"

WindowName = Literal["hann", "hamming", "blackman", "boxcar"]


def get_dsp_provenance() -> Dict[str, str]:
    """Return provenance metadata for DSP computations."""
    return {
        "algo_id": DSP_ALGO_ID,
        "algo_version": DSP_ALGO_VERSION,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
    }


@dataclass(frozen=True)
class TFResult:
    """Transfer function computation result with uncertainty bounds.

    Uncertainty is computed from coherence and averaging count using
    the formula: σ_H / |H| = √[(1 - γ²) / (2 × n × γ²)]

    where n is the number of averages (segments).
    """

    freq_hz: np.ndarray
    H: np.ndarray  # complex transfer function roving/reference
    H_mag: np.ndarray  # |H|
    H_phase_deg: np.ndarray  # angle(H) in degrees
    coherence: np.ndarray  # gamma^2
    pxx: np.ndarray  # ref PSD
    pyy: np.ndarray  # rov PSD
    # Uncertainty bounds (C3 fix: physics-based uncertainty from coherence)
    # Optional for backward compatibility with existing tests
    H_mag_uncertainty: np.ndarray | None = None  # σ_|H| - standard error of magnitude
    H_phase_uncertainty_deg: np.ndarray | None = None  # σ_φ - standard error of phase
    n_averages: int = 1  # number of spectral averages


def _adaptive_epsilon(data: np.ndarray, min_eps: float | None = None) -> float:
    """
    Compute adaptive epsilon for numerical stability (C4 fix).

    Instead of hardcoded 1e-18, we scale epsilon to the data magnitude
    and dtype precision. This prevents both:
    - Numerical instability (eps too small for data)
    - Unnecessary clipping (eps too large)

    Args:
        data: Array used in denominator (e.g., Pxx for H = Pxy/Pxx)
        min_eps: Optional minimum epsilon (uses dtype eps if None)

    Returns:
        Adaptive epsilon value
    """
    dtype_eps = (
        np.finfo(data.dtype).eps if np.issubdtype(data.dtype, np.floating) else 1e-7
    )
    min_eps = min_eps if min_eps is not None else dtype_eps  # type: ignore[assignment]

    # Scale to ~10 orders of magnitude below data maximum
    data_scale = np.abs(data).max() * 1e-10 if data.size > 0 else dtype_eps

    return float(max(min_eps, data_scale))


def transfer_magnitude_uncertainty_from_coherence(
    coherence: np.ndarray,
    n_averages: int,
    *,
    coherence_floor: float = 1e-12,
) -> np.ndarray:
    """
    Compute relative magnitude uncertainty from coherence (Bendat & Piersol).

    Formula: σ_H / |H| = sqrt((1 - γ²) / (2 · n_avg · γ²))

    This is the standard result for the normalized random error of the
    transfer function magnitude estimate.

    Args:
        coherence: Coherence values (γ²). Will be clamped to [floor, 1.0].
        n_averages: Effective number of independent averages. Must be >= 1.
            NOTE: For overlapping Welch segments, this should be the effective
            DOF, not the raw segment count. If raw segment count is used with
            overlap, the uncertainty is underestimated (optimistic bias).
        coherence_floor: Minimum coherence to prevent divide-by-zero.

    Returns:
        Relative uncertainty array (σ_H / |H|), same shape as coherence.
    """
    if n_averages < 1:
        raise ValueError(f"n_averages must be >= 1, got {n_averages}")

    # Clamp coherence to [floor, 1.0] on BOTH ends
    # - Below floor: prevents divide-by-zero
    # - Above 1.0: finite-sample/floating-point effects can produce γ² > 1.0,
    #   which would cause (1 - γ²) < 0 and sqrt to produce nan
    coh_safe = np.clip(coherence, coherence_floor, 1.0)

    # Bendat & Piersol formula for relative magnitude uncertainty
    rel_uncertainty = np.sqrt((1.0 - coh_safe) / (2.0 * n_averages * coh_safe))

    return rel_uncertainty.astype(np.float32)


def transfer_phase_uncertainty_from_coherence(
    coherence: np.ndarray,
    n_averages: int,
    *,
    coherence_floor: float = 1e-12,
) -> np.ndarray:
    """
    Compute phase uncertainty from coherence in radians (Bendat & Piersol).

    Formula: σ_φ ≈ sqrt((1 - γ²) / (2 · n_avg · γ²))  [radians]

    IMPORTANT: This is a SEPARATE Bendat & Piersol derivation from the magnitude
    formula. The numerical equivalence to the relative magnitude error is a
    coincidence of the small-error regime, NOT a shared derivation.

    DO NOT refactor to share implementation with transfer_magnitude_uncertainty_from_coherence.
    A future refinement to one formula (bias correction, higher-order term, windowing
    factor) must NOT propagate to the other.

    Validity: This is a small-error approximation, meaningful for moderate-to-high
    coherence (roughly σ_φ < 0.5 rad). At very low coherence, the linear approximation
    breaks down - interpret as "phase is unreliable" rather than a precise uncertainty.

    Args:
        coherence: Coherence values (γ²). Will be clamped to [floor, 1.0].
        n_averages: Effective number of independent averages. Must be >= 1.
            NOTE: For overlapping Welch segments, this should be the effective
            DOF, not the raw segment count. If raw segment count is used with
            overlap, the uncertainty is underestimated (optimistic bias).
        coherence_floor: Minimum coherence to prevent divide-by-zero.

    Returns:
        Phase uncertainty in radians, same shape as coherence.
    """
    if n_averages < 1:
        raise ValueError(f"n_averages must be >= 1, got {n_averages}")

    # Clamp coherence to [floor, 1.0] on BOTH ends
    # - Below floor: prevents divide-by-zero
    # - Above 1.0: finite-sample/floating-point effects can produce γ² > 1.0,
    #   which would cause (1 - γ²) < 0 and sqrt to produce nan
    coh_safe = np.clip(coherence, coherence_floor, 1.0)

    # Bendat & Piersol formula for phase standard deviation (radians)
    # This is a SEPARATE derivation - do not merge with magnitude function
    phase_uncertainty_rad = np.sqrt((1.0 - coh_safe) / (2.0 * n_averages * coh_safe))

    return phase_uncertainty_rad.astype(np.float32)


def _compute_tf_uncertainty(
    coherence: np.ndarray, n_averages: int, H_mag: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute transfer function uncertainty (internal helper, backward compatibility).

    Uses the separate magnitude and phase uncertainty functions per Dev Order 84.

    Args:
        coherence: Coherence (gamma^2) array
        n_averages: Number of spectral averages (see note on effective DOF)
        H_mag: Transfer function magnitude |H|

    Returns:
        (magnitude_uncertainty, phase_uncertainty_deg) arrays

    Note:
        n_averages here is the raw segment count from Welch averaging with 50% overlap.
        For Hann window with 50% overlap, this produces an OPTIMISTIC uncertainty
        estimate because overlapping segments are correlated. The effective number
        of independent averages is lower than the segment count.
        See: Welch (1967), Bendat & Piersol Ch. 8, Harris window survey.
    """
    # Relative magnitude uncertainty
    rel_uncertainty = transfer_magnitude_uncertainty_from_coherence(
        coherence, n_averages
    )

    # Absolute magnitude uncertainty
    mag_uncertainty = rel_uncertainty * H_mag

    # Phase uncertainty (radians, then convert to degrees for backward compat)
    phase_uncertainty_rad = transfer_phase_uncertainty_from_coherence(
        coherence, n_averages
    )
    phase_uncertainty_deg = phase_uncertainty_rad * (180.0 / np.pi)

    return mag_uncertainty.astype(np.float32), phase_uncertainty_deg.astype(np.float32)


def compute_transfer_and_coherence(
    x_ref: np.ndarray,
    x_rov: np.ndarray,
    fs: int,
    *,
    nperseg: int = 4096,
    noverlap: int | None = None,
    window: WindowName = "hann",
    fmin_hz: float = 30.0,
    fmax_hz: float = 2000.0,
) -> TFResult:
    """Compute transfer function and coherence between reference and roving signals.

    Now includes uncertainty bounds derived from coherence and averaging count
    (C3 fix: physics-based uncertainty propagation).

    Args:
        x_ref: Reference channel signal (fixed mic)
        x_rov: Roving channel signal (measurement mic)
        fs: Sample rate in Hz
        nperseg: FFT segment length
        noverlap: Overlap samples (default: nperseg // 2)
        window: Window function name
        fmin_hz: Minimum frequency to include
        fmax_hz: Maximum frequency to include

    Returns:
        TFResult with transfer function, coherence, spectra, and uncertainty bounds
    """
    x_ref = np.asarray(x_ref, dtype=np.float32).reshape(-1)
    x_rov = np.asarray(x_rov, dtype=np.float32).reshape(-1)
    n = min(x_ref.size, x_rov.size)
    x_ref = x_ref[:n]
    x_rov = x_rov[:n]

    if noverlap is None:
        noverlap = nperseg // 2

    # Compute number of averages (for uncertainty calculation)
    step = nperseg - noverlap
    n_averages = max(1, (n - nperseg) // step + 1)

    # Cross-spectrum and autospectra
    f, Pxy = csd(
        x_rov,
        x_ref,
        fs=fs,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        scaling="density",
    )
    _, Pxx = welch(
        x_ref,
        fs=fs,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        scaling="density",
    )
    _, Pyy = welch(
        x_rov,
        fs=fs,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        scaling="density",
    )

    # C4 fix: Adaptive epsilon instead of hardcoded 1e-18
    eps_pxx = _adaptive_epsilon(Pxx)
    eps_product = _adaptive_epsilon(Pxx * Pyy)

    # Transfer function (roving/reference)
    H = Pxy / (Pxx + eps_pxx)

    # Coherence gamma^2 = |Pxy|^2 / (Pxx * Pyy)
    coh = (np.abs(Pxy) ** 2) / ((Pxx * Pyy) + eps_product)
    coh = np.clip(coh, 0.0, 1.0)  # Coherence must be in [0, 1]

    # Band limit
    mask = (f >= fmin_hz) & (f <= fmax_hz)
    f2 = f[mask].astype(np.float32)
    H2 = H[mask].astype(np.complex64)
    coh2 = coh[mask].astype(np.float32)
    Pxx2 = Pxx[mask].astype(np.float32)
    Pyy2 = Pyy[mask].astype(np.float32)

    mag = np.abs(H2).astype(np.float32)
    ph = (np.angle(H2) * (180.0 / np.pi)).astype(np.float32)

    # C3 fix: Compute uncertainty bounds from coherence
    mag_uncertainty, phase_uncertainty = _compute_tf_uncertainty(coh2, n_averages, mag)

    return TFResult(
        freq_hz=f2,
        H=H2,
        H_mag=mag,
        H_phase_deg=ph,
        coherence=coh2,
        pxx=Pxx2,
        pyy=Pyy2,
        H_mag_uncertainty=mag_uncertainty,
        H_phase_uncertainty_deg=phase_uncertainty,
        n_averages=n_averages,
    )


def nearest_bin(freqs: np.ndarray, target_hz: float) -> int:
    """Find index of frequency bin nearest to target."""
    freqs = np.asarray(freqs, dtype=np.float32)
    return int(np.argmin(np.abs(freqs - float(target_hz))))
