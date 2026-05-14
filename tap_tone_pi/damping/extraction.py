"""
Production-grade damping extraction with cross-validation.

Implements three methods:
1. Half-power bandwidth (frequency domain)
2. Logarithmic decrement (time domain)
3. Exponential curve fitting

Each method includes proper uncertainty quantification.
Cross-validation combines methods with inverse-variance weighting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from scipy import signal as scipy_signal
from scipy.optimize import curve_fit
from scipy.stats import t as t_distribution


@dataclass
class DampingResult:
    """Result of damping extraction for a single mode."""

    frequency_hz: float
    damping_ratio: float  # ζ (zeta)
    quality_factor: float  # Q = 1/(2ζ)
    decay_time_s: float  # τ = 1/(ζωn)
    decay_rate_nepers_per_s: float  # α = ζωn

    # Uncertainty
    damping_ratio_std: float
    confidence_level: float  # e.g., 0.95
    confidence_interval: Tuple[float, float]

    # Method details
    method_used: str
    halfpower_estimate: Optional[float]
    halfpower_uncertainty: Optional[float]
    logdec_estimate: Optional[float]
    logdec_uncertainty: Optional[float]
    curvefit_estimate: Optional[float]
    curvefit_uncertainty: Optional[float]

    # Quality flags
    methods_agree: bool  # Within tolerance
    n_methods_valid: int
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Export as dictionary."""
        return {
            "frequency_hz": self.frequency_hz,
            "damping_ratio": self.damping_ratio,
            "quality_factor": self.quality_factor,
            "decay_time_s": self.decay_time_s,
            "decay_rate_nepers_per_s": self.decay_rate_nepers_per_s,
            "damping_ratio_std": self.damping_ratio_std,
            "confidence_level": self.confidence_level,
            "confidence_interval": list(self.confidence_interval),
            "method_used": self.method_used,
            "individual_estimates": {
                "halfpower": {
                    "value": self.halfpower_estimate,
                    "uncertainty": self.halfpower_uncertainty,
                },
                "logdec": {
                    "value": self.logdec_estimate,
                    "uncertainty": self.logdec_uncertainty,
                },
                "curvefit": {
                    "value": self.curvefit_estimate,
                    "uncertainty": self.curvefit_uncertainty,
                },
            },
            "methods_agree": self.methods_agree,
            "n_methods_valid": self.n_methods_valid,
            "warnings": self.warnings,
        }

    def format_summary(self) -> str:
        """Format as human-readable string."""
        lines = [
            f"Mode at {self.frequency_hz:.1f} Hz:",
            f"  Damping ratio ζ = {self.damping_ratio:.4f} ± {self.damping_ratio_std:.4f}",
            f"  Quality factor Q = {self.quality_factor:.1f}",
            f"  Decay time τ = {self.decay_time_s * 1000:.1f} ms",
            f"  Method: {self.method_used} ({self.n_methods_valid} methods valid)",
        ]
        if not self.methods_agree:
            lines.append("  ⚠ Methods disagree - check data quality")
        for warning in self.warnings:
            lines.append(f"  ⚠ {warning}")
        return "\n".join(lines)


def extract_damping_halfpower(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    peak_freq: float,
    search_bandwidth_hz: float = 50.0,
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Extract damping using half-power bandwidth method.

    Q = f_n / (f_2 - f_1)
    ζ = 1 / (2Q)

    where f_1, f_2 are the -3dB points (half-power points).

    Args:
        freqs: Frequency array (Hz)
        magnitude: Magnitude spectrum (linear, not dB)
        peak_freq: Center frequency of mode (Hz)
        search_bandwidth_hz: Search range around peak

    Returns:
        (damping_ratio, uncertainty, details_dict)
    """
    details = {
        "method": "halfpower",
        "peak_freq_hz": peak_freq,
        "search_bandwidth_hz": search_bandwidth_hz,
    }

    # Find peak in search range
    mask = (freqs >= peak_freq - search_bandwidth_hz) & (
        freqs <= peak_freq + search_bandwidth_hz
    )

    if not np.any(mask):
        details["error"] = "No data in search range"
        return np.nan, np.nan, details

    local_freqs = freqs[mask]
    local_mag = magnitude[mask]

    # Find actual peak
    peak_idx = np.argmax(local_mag)
    peak_mag = local_mag[peak_idx]
    actual_peak_freq = local_freqs[peak_idx]

    details["actual_peak_freq_hz"] = float(actual_peak_freq)
    details["peak_magnitude"] = float(peak_mag)

    # Half power level
    half_power_level = peak_mag / np.sqrt(2)
    details["half_power_level"] = float(half_power_level)

    # Find lower -3dB point
    lower_idx = peak_idx
    while lower_idx > 0 and local_mag[lower_idx] > half_power_level:
        lower_idx -= 1

    # Interpolate for precise crossing
    if lower_idx > 0 and lower_idx < peak_idx:
        # Linear interpolation between points
        y1, y2 = local_mag[lower_idx], local_mag[lower_idx + 1]
        x1, x2 = local_freqs[lower_idx], local_freqs[lower_idx + 1]
        if y2 != y1:
            f1 = x1 + (half_power_level - y1) * (x2 - x1) / (y2 - y1)
        else:
            f1 = x1
    else:
        details["warning"] = "Lower -3dB point at edge of search range"
        f1 = local_freqs[0]

    # Find upper -3dB point
    upper_idx = peak_idx
    while upper_idx < len(local_mag) - 1 and local_mag[upper_idx] > half_power_level:
        upper_idx += 1

    if upper_idx < len(local_mag) - 1 and upper_idx > peak_idx:
        y1, y2 = local_mag[upper_idx - 1], local_mag[upper_idx]
        x1, x2 = local_freqs[upper_idx - 1], local_freqs[upper_idx]
        if y2 != y1:
            f2 = x1 + (half_power_level - y1) * (x2 - x1) / (y2 - y1)
        else:
            f2 = x2
    else:
        if "warning" not in details:
            details["warning"] = "Upper -3dB point at edge of search range"
        f2 = local_freqs[-1]

    details["f1_hz"] = float(f1)
    details["f2_hz"] = float(f2)

    # Calculate Q and damping
    bandwidth = f2 - f1
    details["bandwidth_hz"] = float(bandwidth)

    if bandwidth <= 0:
        details["error"] = "Invalid bandwidth (f2 <= f1)"
        return np.nan, np.nan, details

    Q = actual_peak_freq / bandwidth
    damping_ratio = 1.0 / (2.0 * Q)

    details["Q"] = float(Q)
    details["damping_ratio"] = float(damping_ratio)

    # Uncertainty from frequency resolution
    freq_resolution = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    details["freq_resolution_hz"] = float(freq_resolution)

    # Propagate uncertainty through Q calculation
    # u(bandwidth) comes from two interpolations
    u_bandwidth = freq_resolution * np.sqrt(2)
    u_Q = Q * (u_bandwidth / bandwidth)
    u_zeta = damping_ratio * (u_Q / Q)

    details["uncertainty"] = float(u_zeta)

    return damping_ratio, u_zeta, details


def extract_damping_logdec(
    signal: np.ndarray,
    sample_rate: int,
    peak_freq: float,
    bandwidth_hz: float = 20.0,
    min_cycles: int = 5,
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Extract damping using logarithmic decrement method.

    δ = (1/n) × ln(x_0 / x_n)
    ζ = δ / √(4π² + δ²)

    Uses Hilbert transform for envelope extraction and bandpass
    filtering to isolate single mode.

    Args:
        signal: Time-domain signal
        sample_rate: Sample rate (Hz)
        peak_freq: Mode frequency (Hz)
        bandwidth_hz: Bandpass filter bandwidth
        min_cycles: Minimum cycles for valid estimate

    Returns:
        (damping_ratio, uncertainty, details_dict)
    """
    details = {
        "method": "logdec",
        "peak_freq_hz": peak_freq,
        "bandwidth_hz": bandwidth_hz,
        "sample_rate": sample_rate,
    }

    # Design bandpass filter to isolate mode
    nyquist = sample_rate / 2
    low = (peak_freq - bandwidth_hz / 2) / nyquist
    high = (peak_freq + bandwidth_hz / 2) / nyquist

    # Clamp to valid range
    low = max(0.01, min(low, 0.98))
    high = max(low + 0.01, min(high, 0.99))

    details["filter_low_normalized"] = float(low)
    details["filter_high_normalized"] = float(high)

    try:
        b, a = scipy_signal.butter(4, [low, high], btype="band")
        filtered = scipy_signal.filtfilt(b, a, signal)
    except ValueError as e:
        details["error"] = f"Filter design failed: {e}"
        return np.nan, np.nan, details

    # Compute analytic signal via Hilbert transform
    analytic = scipy_signal.hilbert(filtered)
    envelope = np.abs(analytic)

    # Find envelope peaks (local maxima)
    # Distance between peaks should be approximately one period
    min_distance = int(sample_rate / peak_freq / 2)
    peak_indices, _peak_props = scipy_signal.find_peaks(
        envelope,
        distance=max(1, min_distance),
        height=np.max(envelope) * 0.05,  # At least 5% of max
    )

    details["n_envelope_peaks"] = len(peak_indices)

    if len(peak_indices) < min_cycles + 1:
        details["error"] = (
            f"Insufficient peaks ({len(peak_indices)} < {min_cycles + 1})"
        )
        return np.nan, np.nan, details

    # Get peak amplitudes
    peak_amplitudes = envelope[peak_indices]

    # Calculate log decrements between successive peaks
    log_decrements = []
    for i in range(len(peak_amplitudes) - 1):
        if peak_amplitudes[i + 1] > 0 and peak_amplitudes[i] > peak_amplitudes[i + 1]:
            delta = np.log(peak_amplitudes[i] / peak_amplitudes[i + 1])
            if delta > 0:  # Should be positive for decaying signal
                log_decrements.append(delta)

    details["n_valid_decrements"] = len(log_decrements)

    if len(log_decrements) < 3:
        details["error"] = f"Insufficient valid decrements ({len(log_decrements)} < 3)"
        return np.nan, np.nan, details

    # Statistics of log decrements
    delta_mean = np.mean(log_decrements)
    delta_std = np.std(log_decrements, ddof=1)
    delta_sem = delta_std / np.sqrt(len(log_decrements))

    details["delta_mean"] = float(delta_mean)
    details["delta_std"] = float(delta_std)
    details["delta_sem"] = float(delta_sem)

    # Convert to damping ratio
    # ζ = δ / √(4π² + δ²)
    denom = np.sqrt(4 * np.pi**2 + delta_mean**2)
    damping_ratio = delta_mean / denom

    # Propagate uncertainty
    # dζ/dδ = 4π² / (4π² + δ²)^(3/2)
    sensitivity = 4 * np.pi**2 / (4 * np.pi**2 + delta_mean**2) ** 1.5
    u_zeta = sensitivity * delta_sem

    details["damping_ratio"] = float(damping_ratio)
    details["uncertainty"] = float(u_zeta)
    details["sensitivity_coefficient"] = float(sensitivity)

    return damping_ratio, u_zeta, details


def extract_damping_curvefit(
    signal: np.ndarray,
    sample_rate: int,
    peak_freq: float,
    bandwidth_hz: float = 20.0,
    fit_duration_s: Optional[float] = None,
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Extract damping by fitting exponential decay to envelope.

    A(t) = A_0 × exp(-ζ × ω_n × t)

    Uses nonlinear least squares fitting with proper uncertainty
    from covariance matrix.

    Args:
        signal: Time-domain signal
        sample_rate: Sample rate (Hz)
        peak_freq: Mode frequency (Hz)
        bandwidth_hz: Bandpass filter bandwidth
        fit_duration_s: Duration to fit (None = auto)

    Returns:
        (damping_ratio, uncertainty, details_dict)
    """
    details = {
        "method": "curvefit",
        "peak_freq_hz": peak_freq,
        "bandwidth_hz": bandwidth_hz,
        "sample_rate": sample_rate,
    }

    # Design bandpass filter
    nyquist = sample_rate / 2
    low = (peak_freq - bandwidth_hz / 2) / nyquist
    high = (peak_freq + bandwidth_hz / 2) / nyquist

    low = max(0.01, min(low, 0.98))
    high = max(low + 0.01, min(high, 0.99))

    try:
        b, a = scipy_signal.butter(4, [low, high], btype="band")
        filtered = scipy_signal.filtfilt(b, a, signal)
    except ValueError as e:
        details["error"] = f"Filter design failed: {e}"
        return np.nan, np.nan, details

    # Compute envelope
    analytic = scipy_signal.hilbert(filtered)
    envelope = np.abs(analytic)

    # Find start of decay (peak of envelope)
    start_idx = np.argmax(envelope)
    details["decay_start_sample"] = int(start_idx)
    details["decay_start_s"] = float(start_idx / sample_rate)

    # Use data from peak onwards
    t = np.arange(len(envelope) - start_idx) / sample_rate
    y = envelope[start_idx:]

    # Normalize to start at 1
    y0 = y[0]
    if y0 <= 0:
        details["error"] = "Invalid envelope at decay start"
        return np.nan, np.nan, details

    y_norm = y / y0
    details["initial_amplitude"] = float(y0)

    # Determine fit duration
    if fit_duration_s is None:
        # Fit until signal drops to 1% or end of data
        valid_mask = y_norm > 0.01
        if np.sum(valid_mask) < 10:
            details["error"] = "Insufficient data above 1% threshold"
            return np.nan, np.nan, details
        fit_end_idx = np.where(valid_mask)[0][-1]
    else:
        fit_end_idx = min(int(fit_duration_s * sample_rate), len(t) - 1)

    t_fit = t[: fit_end_idx + 1]
    y_fit = y_norm[: fit_end_idx + 1]

    details["fit_duration_s"] = float(t_fit[-1])
    details["n_fit_points"] = len(t_fit)

    if len(t_fit) < 10:
        details["error"] = "Insufficient points for fitting"
        return np.nan, np.nan, details

    # Exponential decay model: A(t) = exp(-α × t)
    # where α = ζ × ω_n
    def decay_model(t, alpha):
        return np.exp(-alpha * t)

    try:
        omega_n = 2 * np.pi * peak_freq

        # Initial guess based on decay to 1/e
        # Find time to reach 1/e ≈ 0.368
        e_idx = np.searchsorted(-y_fit, -0.368)
        if e_idx < len(t_fit) and e_idx > 0:
            alpha_guess = 1.0 / t_fit[e_idx]
        else:
            # Assume Q ≈ 50 → ζ ≈ 0.01
            alpha_guess = 0.01 * omega_n

        p0 = [alpha_guess]
        bounds = (1e-6, omega_n)  # 0 < ζ < 1

        popt, pcov = curve_fit(
            decay_model,
            t_fit,
            y_fit,
            p0=p0,
            bounds=bounds,
            maxfev=10000,
        )

        alpha = popt[0]
        alpha_std = np.sqrt(pcov[0, 0])

        damping_ratio = alpha / omega_n
        u_zeta = alpha_std / omega_n

        details["alpha_nepers_per_s"] = float(alpha)
        details["alpha_std"] = float(alpha_std)
        details["damping_ratio"] = float(damping_ratio)
        details["uncertainty"] = float(u_zeta)

        # Goodness of fit
        y_pred = decay_model(t_fit, alpha)
        ss_res = np.sum((y_fit - y_pred) ** 2)
        ss_tot = np.sum((y_fit - np.mean(y_fit)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        details["r_squared"] = float(r_squared)

        if r_squared < 0.9:
            details["warning"] = f"Poor fit quality (R² = {r_squared:.3f})"

        return damping_ratio, u_zeta, details

    except (RuntimeError, ValueError) as e:
        details["error"] = f"Curve fitting failed: {e}"
        return np.nan, np.nan, details


def _collect_method_estimates(
    signal: np.ndarray,
    freqs: np.ndarray,
    magnitude: np.ndarray,
    sample_rate: int,
    peak_freq: float,
    bandwidth_hz: float,
) -> Tuple[
    List[float],
    List[float],
    List[str],
    List[str],
    float,
    float,
    float,
    float,
    float,
    float,
]:
    """Run all three damping extraction methods and collect warnings.

    Returns:
        (estimates, uncertainties, methods, warnings,
         zeta_hp, u_hp, zeta_ld, u_ld, zeta_cf, u_cf)
    """
    warnings: List[str] = []

    # Half-power bandwidth
    zeta_hp, u_hp, details_hp = extract_damping_halfpower(
        freqs,
        magnitude,
        peak_freq,
        search_bandwidth_hz=bandwidth_hz * 2,
    )
    if "warning" in details_hp:
        warnings.append(f"Half-power: {details_hp['warning']}")
    if "error" in details_hp:
        warnings.append(f"Half-power failed: {details_hp['error']}")

    # Log-decrement
    zeta_ld, u_ld, details_ld = extract_damping_logdec(
        signal,
        sample_rate,
        peak_freq,
        bandwidth_hz=bandwidth_hz,
    )
    if "warning" in details_ld:
        warnings.append(f"Log-dec: {details_ld['warning']}")
    if "error" in details_ld:
        warnings.append(f"Log-dec failed: {details_ld['error']}")

    # Curve-fit
    zeta_cf, u_cf, details_cf = extract_damping_curvefit(
        signal,
        sample_rate,
        peak_freq,
        bandwidth_hz=bandwidth_hz,
    )
    if "warning" in details_cf:
        warnings.append(f"Curve-fit: {details_cf['warning']}")
    if "error" in details_cf:
        warnings.append(f"Curve-fit failed: {details_cf['error']}")

    # Filter valid estimates
    estimates: List[float] = []
    uncertainties: List[float] = []
    methods: List[str] = []

    if np.isfinite(zeta_hp) and zeta_hp > 0 and np.isfinite(u_hp):
        estimates.append(zeta_hp)
        uncertainties.append(u_hp)
        methods.append("halfpower")

    if np.isfinite(zeta_ld) and zeta_ld > 0 and np.isfinite(u_ld):
        estimates.append(zeta_ld)
        uncertainties.append(u_ld)
        methods.append("logdec")

    if np.isfinite(zeta_cf) and zeta_cf > 0 and np.isfinite(u_cf):
        estimates.append(zeta_cf)
        uncertainties.append(u_cf)
        methods.append("curvefit")

    return (
        estimates,
        uncertainties,
        methods,
        warnings,
        zeta_hp,
        u_hp,
        zeta_ld,
        u_ld,
        zeta_cf,
        u_cf,
    )


def _weighted_average_and_agreement(
    estimates: List[float],
    uncertainties: List[float],
    methods: List[str],
    agreement_tolerance: float,
    confidence_level: float,
    warnings: List[str],
) -> Tuple[float, float, bool, str]:
    """Inverse-variance weighted average with agreement check and CI.

    Returns:
        (zeta_weighted, margin, methods_agree, method_label)
    """
    n_valid = len(estimates)

    # Inverse-variance weights
    weights = []
    for u in uncertainties:
        if u > 0:
            weights.append(1.0 / (u**2))
        else:
            weights.append(1.0)

    total_weight = sum(weights)
    zeta_weighted = sum(e * w for e, w in zip(estimates, weights)) / total_weight
    u_weighted = np.sqrt(1.0 / total_weight)

    # Check method agreement
    if n_valid >= 2:
        relative_spread = (max(estimates) - min(estimates)) / zeta_weighted
        methods_agree = relative_spread < agreement_tolerance
        if not methods_agree:
            warnings.append(
                f"Methods disagree: spread = {relative_spread * 100:.1f}% "
                f"(threshold = {agreement_tolerance * 100:.0f}%)"
            )
    else:
        methods_agree = True

    # Confidence interval margin
    if n_valid > 1:
        t_crit = t_distribution.ppf((1 + confidence_level) / 2, n_valid - 1)
        margin = t_crit * u_weighted
    else:
        margin = 2.0 * u_weighted

    # Method label
    if n_valid > 1:
        method_label = f"weighted_average({','.join(methods)})"
    else:
        method_label = methods[0]

    return zeta_weighted, margin, methods_agree, method_label


def extract_damping_crossvalidated(
    signal: np.ndarray,
    freqs: np.ndarray,
    magnitude: np.ndarray,
    sample_rate: int,
    peak_freq: float,
    confidence_level: float = 0.95,
    agreement_tolerance: float = 0.3,
    bandwidth_hz: float = 20.0,
) -> DampingResult:
    """
    Extract damping using multiple methods with cross-validation.

    Combines half-power, log-decrement, and curve-fit methods using
    inverse-variance weighted averaging. Flags disagreement between
    methods.

    Args:
        signal: Time-domain signal
        freqs: Frequency array (Hz) for spectrum
        magnitude: Magnitude spectrum (linear)
        sample_rate: Sample rate (Hz)
        peak_freq: Mode frequency (Hz)
        confidence_level: Confidence level for intervals (e.g., 0.95)
        agreement_tolerance: Maximum relative difference for agreement
        bandwidth_hz: Bandwidth for filtering

    Returns:
        DampingResult with cross-validated damping estimate
    """
    # Run all methods and collect valid estimates
    (
        estimates,
        uncertainties,
        methods,
        warnings,
        zeta_hp,
        u_hp,
        zeta_ld,
        u_ld,
        zeta_cf,
        u_cf,
    ) = _collect_method_estimates(
        signal,
        freqs,
        magnitude,
        sample_rate,
        peak_freq,
        bandwidth_hz,
    )

    # Per-method optional values for the result dataclass
    hp_est = zeta_hp if np.isfinite(zeta_hp) else None
    hp_unc = u_hp if np.isfinite(u_hp) else None
    ld_est = zeta_ld if np.isfinite(zeta_ld) else None
    ld_unc = u_ld if np.isfinite(u_ld) else None
    cf_est = zeta_cf if np.isfinite(zeta_cf) else None
    cf_unc = u_cf if np.isfinite(u_cf) else None

    n_valid = len(estimates)

    if n_valid == 0:
        return DampingResult(
            frequency_hz=peak_freq,
            damping_ratio=np.nan,
            quality_factor=np.nan,
            decay_time_s=np.nan,
            decay_rate_nepers_per_s=np.nan,
            damping_ratio_std=np.nan,
            confidence_level=confidence_level,
            confidence_interval=(np.nan, np.nan),
            method_used="none",
            halfpower_estimate=hp_est,
            halfpower_uncertainty=hp_unc,
            logdec_estimate=ld_est,
            logdec_uncertainty=ld_unc,
            curvefit_estimate=cf_est,
            curvefit_uncertainty=cf_unc,
            methods_agree=False,
            n_methods_valid=0,
            warnings=warnings + ["No valid damping estimates"],
        )

    # Weighted average, agreement check, confidence interval
    zeta_weighted, margin, methods_agree, method_used = _weighted_average_and_agreement(
        estimates,
        uncertainties,
        methods,
        agreement_tolerance,
        confidence_level,
        warnings,
    )

    ci_lower = max(0, zeta_weighted - margin)
    ci_upper = zeta_weighted + margin

    # Derived quantities
    omega_n = 2 * np.pi * peak_freq
    Q = 1.0 / (2.0 * zeta_weighted) if zeta_weighted > 0 else np.inf
    tau = (
        1.0 / (zeta_weighted * omega_n) if zeta_weighted > 0 and omega_n > 0 else np.inf
    )
    alpha = zeta_weighted * omega_n

    return DampingResult(
        frequency_hz=peak_freq,
        damping_ratio=zeta_weighted,
        quality_factor=Q,
        decay_time_s=tau,
        decay_rate_nepers_per_s=alpha,
        damping_ratio_std=np.sqrt(
            1.0 / sum(1.0 / (u**2) if u > 0 else 1.0 for u in uncertainties)
        ),
        confidence_level=confidence_level,
        confidence_interval=(ci_lower, ci_upper),
        method_used=method_used,
        halfpower_estimate=hp_est,
        halfpower_uncertainty=hp_unc,
        logdec_estimate=ld_est,
        logdec_uncertainty=ld_unc,
        curvefit_estimate=cf_est,
        curvefit_uncertainty=cf_unc,
        methods_agree=methods_agree,
        n_methods_valid=n_valid,
        warnings=warnings,
    )


def extract_all_modes_damping(
    signal: np.ndarray,
    freqs: np.ndarray,
    magnitude: np.ndarray,
    sample_rate: int,
    peak_frequencies: List[float],
    confidence_level: float = 0.95,
    bandwidth_hz: float = 20.0,
) -> List[DampingResult]:
    """
    Extract damping for multiple modes.

    Args:
        signal: Time-domain signal
        freqs: Frequency array (Hz)
        magnitude: Magnitude spectrum
        sample_rate: Sample rate (Hz)
        peak_frequencies: List of mode frequencies to analyze
        confidence_level: Confidence level for intervals
        bandwidth_hz: Bandwidth for filtering

    Returns:
        List of DampingResult, one per mode
    """
    results = []

    for peak_freq in peak_frequencies:
        result = extract_damping_crossvalidated(
            signal=signal,
            freqs=freqs,
            magnitude=magnitude,
            sample_rate=sample_rate,
            peak_freq=peak_freq,
            confidence_level=confidence_level,
            bandwidth_hz=bandwidth_hz,
        )
        results.append(result)

    return results
