"""
Wolf Beat Analysis - Physics-based coupled oscillator detection.

Implements peak-pair detection and beat frequency estimation based on
the two-oscillator wolf note model:

    f_beat = k_c / (2*pi*omega_0*sqrt(m_s*m_b))

When string frequency approaches a body resonance, mode splitting creates
two peaks (omega_-, omega_+). The beat frequency |f_+ - f_-| determines
the wolf "throb" rate.

Key criterion: splitting is audible/resolvable when:
    delta_f > (gamma_+ + gamma_-)

where gamma is the half-power bandwidth of each peak.

References:
    - Coupled oscillator eigenvalue analysis
    - Avoided crossing in near-degenerate systems
    - Wolf note physics in bowed string instruments

Usage:
    from tap_tone.analysis.wolf_beat import (
        find_peak_pairs,
        extract_linewidth,
        analyze_wolf_beat,
    )

    result = analyze_wolf_beat(frequencies, magnitude, phase)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
from scipy.signal import find_peaks
from scipy.optimize import curve_fit


# -----------------------------------------------------------------------------
# Data Structures
# -----------------------------------------------------------------------------


@dataclass
class PeakInfo:
    """Single resonance peak with extracted parameters."""

    freq_hz: float  # Center frequency
    amplitude: float  # Peak amplitude (linear or dB)
    phase_deg: float  # Phase at peak

    # Linewidth parameters
    gamma_hz: float  # Half-power bandwidth (FWHM/2)
    Q: float  # Quality factor = f / (2*gamma)

    # Fit quality
    fit_r_squared: float = 0.0  # Lorentzian fit R^2

    # Frequency indices
    idx: int = 0  # Index in frequency array
    idx_left: int = 0  # Left -3dB index
    idx_right: int = 0  # Right -3dB index


@dataclass
class PeakPair:
    """Candidate split doublet from coupled oscillator."""

    lower: PeakInfo  # Lower frequency peak (omega_-)
    upper: PeakInfo  # Upper frequency peak (omega_+)

    # Derived quantities
    center_freq_hz: float  # (f_+ + f_-) / 2  (approx body mode)
    delta_f_hz: float  # |f_+ - f_-| = beat frequency

    # Resolvability
    combined_linewidth_hz: float  # gamma_+ + gamma_-
    merge_ratio: float  # delta_f / combined_linewidth
    is_resolvable: bool  # merge_ratio > 1.0

    # Wolf severity estimate
    wolf_severity: str = "none"  # none / mild / moderate / severe

    # Coupling estimate (dimensionless)
    coupling_index: float = 0.0  # Relative coupling strength


@dataclass
class WolfBeatResult:
    """Complete wolf beat analysis result."""

    # Input metadata
    freq_range_hz: Tuple[float, float]
    n_frequencies: int

    # All detected peaks
    peaks: List[PeakInfo] = field(default_factory=list)

    # Candidate wolf pairs
    pairs: List[PeakPair] = field(default_factory=list)

    # Summary
    n_peaks: int = 0
    n_pairs: int = 0
    worst_wolf_freq_hz: Optional[float] = None
    worst_wolf_beat_hz: Optional[float] = None
    worst_wolf_severity: str = "none"

    # Provenance
    algorithm_version: str = "1.0.0"

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "schema_id": "wolf_beat_analysis_v1",
            "freq_range_hz": list(self.freq_range_hz),
            "n_frequencies": self.n_frequencies,
            "n_peaks": self.n_peaks,
            "n_pairs": self.n_pairs,
            "worst_wolf": {
                "center_freq_hz": self.worst_wolf_freq_hz,
                "beat_freq_hz": self.worst_wolf_beat_hz,
                "severity": self.worst_wolf_severity,
            }
            if self.worst_wolf_freq_hz
            else None,
            "peaks": [
                {
                    "freq_hz": p.freq_hz,
                    "amplitude": p.amplitude,
                    "Q": p.Q,
                    "gamma_hz": p.gamma_hz,
                }
                for p in self.peaks
            ],
            "pairs": [
                {
                    "lower_freq_hz": pr.lower.freq_hz,
                    "upper_freq_hz": pr.upper.freq_hz,
                    "center_freq_hz": pr.center_freq_hz,
                    "delta_f_hz": pr.delta_f_hz,
                    "merge_ratio": pr.merge_ratio,
                    "is_resolvable": pr.is_resolvable,
                    "severity": pr.wolf_severity,
                }
                for pr in self.pairs
            ],
            "algorithm_version": self.algorithm_version,
        }


# -----------------------------------------------------------------------------
# Peak Detection
# -----------------------------------------------------------------------------


def find_peaks_in_frf(
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    *,
    min_prominence: float = 0.1,
    min_distance_hz: float = 10.0,
    min_freq_hz: float = 50.0,
    max_freq_hz: float = 1000.0,
) -> List[int]:
    """
    Find resonance peaks in frequency response function.

    Args:
        frequencies: Frequency array (Hz)
        magnitude: Magnitude array (linear scale preferred)
        min_prominence: Minimum peak prominence (fraction of max)
        min_distance_hz: Minimum distance between peaks
        min_freq_hz: Lower frequency bound
        max_freq_hz: Upper frequency bound

    Returns:
        List of peak indices
    """
    # Handle empty input
    if len(magnitude) == 0 or len(frequencies) == 0:
        return []

    # Normalize magnitude
    mag = np.asarray(magnitude)
    max_mag = np.max(mag)
    if max_mag < 1e-12:
        return []
    mag_norm = mag / max_mag

    # Convert min_distance to samples
    df = frequencies[1] - frequencies[0] if len(frequencies) > 1 else 1.0
    min_distance_samples = max(1, int(min_distance_hz / df))

    # Find peaks
    peak_indices, properties = find_peaks(
        mag_norm,
        prominence=min_prominence,
        distance=min_distance_samples,
    )

    # Filter by frequency range
    valid_peaks = []
    for idx in peak_indices:
        f = frequencies[idx]
        if min_freq_hz <= f <= max_freq_hz:
            valid_peaks.append(idx)

    return valid_peaks


def extract_linewidth(
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    peak_idx: int,
    *,
    method: str = "half_power",
) -> Tuple[float, float, int, int]:
    """
    Extract linewidth (half-power bandwidth) of a peak.

    Args:
        frequencies: Frequency array
        magnitude: Magnitude array
        peak_idx: Index of peak
        method: "half_power" or "lorentzian_fit"

    Returns:
        (gamma_hz, Q, idx_left, idx_right)
        gamma_hz: Half-power bandwidth (FWHM/2)
        Q: Quality factor
        idx_left: Left -3dB index
        idx_right: Right -3dB index
    """
    mag = np.asarray(magnitude)
    freqs = np.asarray(frequencies)

    peak_mag = mag[peak_idx]
    peak_freq = freqs[peak_idx]

    # Half-power level (-3dB in linear scale = peak / sqrt(2))
    half_power = peak_mag / np.sqrt(2)

    # Find left crossing
    idx_left = peak_idx
    for i in range(peak_idx - 1, -1, -1):
        if mag[i] < half_power:
            idx_left = i
            break

    # Find right crossing
    idx_right = peak_idx
    for i in range(peak_idx + 1, len(mag)):
        if mag[i] < half_power:
            idx_right = i
            break

    # FWHM and gamma
    fwhm = freqs[idx_right] - freqs[idx_left]
    gamma = fwhm / 2.0

    # Quality factor
    Q = peak_freq / fwhm if fwhm > 0 else 100.0

    return gamma, Q, idx_left, idx_right


def _lorentzian(
    f: np.ndarray, f0: float, gamma: float, A: float, C: float
) -> np.ndarray:
    """Lorentzian lineshape for fitting."""
    return A / (1 + ((f - f0) / gamma) ** 2) + C


def extract_linewidth_lorentzian(
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    peak_idx: int,
    *,
    window_factor: float = 3.0,
) -> Tuple[float, float, float]:
    """
    Extract linewidth via Lorentzian fit.

    Args:
        frequencies: Frequency array
        magnitude: Magnitude array
        peak_idx: Index of peak
        window_factor: Fit window = window_factor * initial gamma estimate

    Returns:
        (gamma_hz, Q, r_squared)
    """
    mag = np.asarray(magnitude)
    freqs = np.asarray(frequencies)

    # Initial estimate via half-power
    gamma_init, Q_init, idx_l, idx_r = extract_linewidth(freqs, mag, peak_idx)

    # Define fit window
    window_width = window_factor * gamma_init * 2
    f0 = freqs[peak_idx]
    mask = np.abs(freqs - f0) < window_width

    if np.sum(mask) < 5:
        return gamma_init, Q_init, 0.0

    f_fit = freqs[mask]
    m_fit = mag[mask]

    # Initial parameters
    A_init = mag[peak_idx] - np.min(m_fit)
    C_init = np.min(m_fit)

    try:
        popt, _ = curve_fit(
            _lorentzian,
            f_fit,
            m_fit,
            p0=[f0, gamma_init, A_init, C_init],
            bounds=(
                [f0 - gamma_init, 0.1, 0, 0],
                [f0 + gamma_init, gamma_init * 10, A_init * 2, C_init * 2 + 0.01],
            ),
            maxfev=1000,
        )
        f0_fit, gamma_fit, A_fit, C_fit = popt

        # Compute R^2
        y_pred = _lorentzian(f_fit, *popt)
        ss_res = np.sum((m_fit - y_pred) ** 2)
        ss_tot = np.sum((m_fit - np.mean(m_fit)) ** 2)
        r_squared = 1 - (ss_res / (ss_tot + 1e-12))

        Q_fit = f0_fit / (2 * gamma_fit) if gamma_fit > 0 else Q_init

        return gamma_fit, Q_fit, r_squared

    except (RuntimeError, ValueError):
        return gamma_init, Q_init, 0.0


# -----------------------------------------------------------------------------
# Peak Pair Detection
# -----------------------------------------------------------------------------


def find_peak_pairs(
    peaks: List[PeakInfo],
    *,
    max_separation_hz: float = 50.0,
    min_separation_hz: float = 2.0,
    amplitude_ratio_max: float = 10.0,
) -> List[PeakPair]:
    """
    Find candidate split doublets (wolf pairs) from list of peaks.

    Coupled oscillator theory predicts near-equal amplitude peaks when
    damping is similar and coupling is moderate.

    Args:
        peaks: List of detected peaks
        max_separation_hz: Maximum frequency separation to consider
        min_separation_hz: Minimum separation (avoid single-peak artifacts)
        amplitude_ratio_max: Maximum amplitude ratio between peaks

    Returns:
        List of candidate PeakPair objects
    """
    pairs = []
    n = len(peaks)

    # Sort by frequency
    sorted_peaks = sorted(peaks, key=lambda p: p.freq_hz)

    for i in range(n - 1):
        for j in range(i + 1, n):
            lower = sorted_peaks[i]
            upper = sorted_peaks[j]

            delta_f = upper.freq_hz - lower.freq_hz

            # Check separation bounds
            if delta_f < min_separation_hz:
                continue
            if delta_f > max_separation_hz:
                break  # Sorted, so no more valid pairs for this i

            # Check amplitude ratio
            amp_ratio = max(lower.amplitude, upper.amplitude) / (
                min(lower.amplitude, upper.amplitude) + 1e-12
            )
            if amp_ratio > amplitude_ratio_max:
                continue

            # Compute derived quantities
            center_freq = (lower.freq_hz + upper.freq_hz) / 2
            combined_linewidth = lower.gamma_hz + upper.gamma_hz
            merge_ratio = delta_f / (combined_linewidth + 1e-12)
            is_resolvable = merge_ratio > 1.0

            # Classify severity
            severity = _classify_wolf_severity(merge_ratio, delta_f)

            # Coupling index estimate (dimensionless)
            # From: delta_f approx k_c / (omega_0 * sqrt(m_s*m_b))
            # Coupling index ~ delta_f * omega_0 / f_0^2 (normalized)
            _omega_0 = 2 * np.pi * center_freq
            coupling_index = delta_f / center_freq  # Simple normalized measure

            pair = PeakPair(
                lower=lower,
                upper=upper,
                center_freq_hz=center_freq,
                delta_f_hz=delta_f,
                combined_linewidth_hz=combined_linewidth,
                merge_ratio=merge_ratio,
                is_resolvable=is_resolvable,
                wolf_severity=severity,
                coupling_index=coupling_index,
            )
            pairs.append(pair)

    return pairs


def _classify_wolf_severity(merge_ratio: float, delta_f: float) -> str:
    """
    Classify wolf severity based on physics criteria.

    - Resolvable split (merge_ratio > 1) = audible beating
    - Beat frequency 1-4 Hz = "growl" (most annoying)
    - Beat frequency 4-10 Hz = "warble"
    - Beat frequency > 10 Hz = "roughness" (less objectionable)
    """
    if merge_ratio < 0.5:
        return "none"  # Peaks merged, no distinct beating

    if merge_ratio < 1.0:
        return "mild"  # Partially merged, subtle effect

    # Resolvable - classify by beat rate
    if delta_f < 1.0:
        return "mild"  # Very slow, barely perceptible
    elif delta_f < 4.0:
        return "severe"  # 1-4 Hz growl is most objectionable
    elif delta_f < 10.0:
        return "moderate"  # 4-10 Hz warble
    else:
        return "mild"  # Fast roughness, less prominent


# -----------------------------------------------------------------------------
# Main Analysis Function
# -----------------------------------------------------------------------------


def analyze_wolf_beat(
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    phase: Optional[np.ndarray] = None,
    *,
    min_freq_hz: float = 50.0,
    max_freq_hz: float = 500.0,
    peak_prominence: float = 0.1,
    max_pair_separation_hz: float = 50.0,
    use_lorentzian_fit: bool = True,
) -> WolfBeatResult:
    """
    Perform complete wolf beat analysis on frequency response data.

    This implements the physics-based approach:
    1. Detect resonance peaks in FRF
    2. Extract linewidth (gamma) and Q for each peak
    3. Find candidate split doublets (peak pairs)
    4. Compute resolvability criterion: delta_f > (gamma_+ + gamma_-)
    5. Classify wolf severity

    Args:
        frequencies: Frequency array (Hz)
        magnitude: Magnitude of transfer function (linear scale)
        phase: Phase of transfer function (degrees, optional)
        min_freq_hz: Lower frequency bound for analysis
        max_freq_hz: Upper frequency bound for analysis
        peak_prominence: Minimum prominence for peak detection
        max_pair_separation_hz: Maximum Hz separation for pair candidates
        use_lorentzian_fit: Use Lorentzian fit for linewidth (more accurate)

    Returns:
        WolfBeatResult with all detected peaks and pairs
    """
    frequencies = np.asarray(frequencies)
    magnitude = np.asarray(magnitude)

    if phase is not None:
        phase = np.asarray(phase)
    else:
        phase = np.zeros_like(magnitude)

    # Find peaks
    peak_indices = find_peaks_in_frf(
        frequencies,
        magnitude,
        min_prominence=peak_prominence,
        min_freq_hz=min_freq_hz,
        max_freq_hz=max_freq_hz,
    )

    # Extract peak info
    peaks = []
    for idx in peak_indices:
        if use_lorentzian_fit:
            gamma, Q, r_sq = extract_linewidth_lorentzian(frequencies, magnitude, idx)
            _, _, idx_l, idx_r = extract_linewidth(frequencies, magnitude, idx)
        else:
            gamma, Q, idx_l, idx_r = extract_linewidth(frequencies, magnitude, idx)
            r_sq = 0.0

        peak = PeakInfo(
            freq_hz=float(frequencies[idx]),
            amplitude=float(magnitude[idx]),
            phase_deg=float(phase[idx]),
            gamma_hz=gamma,
            Q=Q,
            fit_r_squared=r_sq,
            idx=idx,
            idx_left=idx_l,
            idx_right=idx_r,
        )
        peaks.append(peak)

    # Find pairs
    pairs = find_peak_pairs(
        peaks,
        max_separation_hz=max_pair_separation_hz,
        min_separation_hz=2.0,
    )

    # Sort pairs by severity
    severity_order = {"severe": 0, "moderate": 1, "mild": 2, "none": 3}
    pairs.sort(key=lambda p: (severity_order.get(p.wolf_severity, 4), -p.delta_f_hz))

    # Find worst wolf
    worst_freq = None
    worst_beat = None
    worst_severity = "none"

    if pairs:
        worst = pairs[0]
        worst_freq = worst.center_freq_hz
        worst_beat = worst.delta_f_hz
        worst_severity = worst.wolf_severity

    return WolfBeatResult(
        freq_range_hz=(float(min_freq_hz), float(max_freq_hz)),
        n_frequencies=len(frequencies),
        peaks=peaks,
        pairs=pairs,
        n_peaks=len(peaks),
        n_pairs=len(pairs),
        worst_wolf_freq_hz=worst_freq,
        worst_wolf_beat_hz=worst_beat,
        worst_wolf_severity=worst_severity,
    )


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------


def estimate_coupling_from_split(
    delta_f_hz: float,
    center_freq_hz: float,
    effective_mass_kg: float = 0.01,
) -> float:
    """
    Estimate coupling stiffness k_c from observed frequency split.

    From: delta_f = k_c / (2*pi*omega_0*sqrt(m_s*m_b))
    Assuming m_s ~ m_b = m:
        k_c = delta_f * 2*pi*omega_0 * m

    Args:
        delta_f_hz: Observed frequency split
        center_freq_hz: Center frequency (body mode)
        effective_mass_kg: Estimate of effective mass (default 10g)

    Returns:
        Estimated coupling stiffness k_c in N/m
    """
    omega_0 = 2 * np.pi * center_freq_hz
    k_c = delta_f_hz * 2 * np.pi * omega_0 * effective_mass_kg
    return k_c


def predict_wolf_severity_change(
    current_result: WolfBeatResult,
    mass_change_factor: float = 1.0,
    damping_change_factor: float = 1.0,
) -> str:
    """
    Predict how wolf severity would change with modifications.

    Based on physics:
    - Adding mass (wolf eliminator): reduces delta_f ~ 1/sqrt(m)
    - Adding damping: increases linewidth, promotes merging

    Args:
        current_result: Current analysis result
        mass_change_factor: New mass / old mass (>1 = heavier)
        damping_change_factor: New damping / old damping (>1 = more damped)

    Returns:
        Qualitative prediction string
    """
    if not current_result.pairs:
        return "No wolf pairs detected"

    worst = current_result.pairs[0]

    # New delta_f scales as 1/sqrt(mass)
    new_delta_f = worst.delta_f_hz / np.sqrt(mass_change_factor)

    # New linewidth scales with damping
    new_linewidth = worst.combined_linewidth_hz * damping_change_factor

    new_merge_ratio = new_delta_f / (new_linewidth + 1e-12)

    if new_merge_ratio < 0.5:
        return f"Peaks would MERGE (ratio {new_merge_ratio:.2f}) - wolf eliminated"
    elif new_merge_ratio < 1.0:
        return (
            f"Peaks would PARTIALLY MERGE (ratio {new_merge_ratio:.2f}) - wolf reduced"
        )
    elif new_merge_ratio < worst.merge_ratio:
        return f"Wolf REDUCED (ratio {new_merge_ratio:.2f} vs {worst.merge_ratio:.2f})"
    else:
        return f"Wolf UNCHANGED or worse (ratio {new_merge_ratio:.2f})"


# -----------------------------------------------------------------------------
# Dimensionless Avoided-Crossing Model
# -----------------------------------------------------------------------------


@dataclass
class AvoidedCrossingModel:
    """
    Dimensionless parametric model for coupled string-body oscillator.

    From the characteristic equation of the coupled system:
        λ±(ξ) = [1 + ξ² ± √((1 - ξ²)² + 4Ω²ξ²)] / 2

    Where:
        ξ = ωs/ωb   (string-to-body frequency ratio, detuning parameter)
        Ω² = κ²/(4ωb²mb)  (dimensionless coupling strength)
        λ = ω²/ωb²  (normalized eigenfrequency squared)

    At resonance (ξ = 1):
        Δλ = 2Ω  (minimum gap = coupling strength)

    The beat frequency in Hz:
        f_beat = (f_b / 2) * |√λ₊ - √λ₋|
    """

    omega_b_hz: float  # Body mode frequency (Hz)
    coupling_omega: float  # Dimensionless coupling Ω (0 to ~0.2)
    gamma_b_hz: float = 5.0  # Body mode linewidth (Hz)
    gamma_s_hz: float = 2.0  # String linewidth (Hz, typically < body)

    def eigenvalues(self, xi: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute normalized eigenvalues λ±(ξ).

        Args:
            xi: Array of detuning values ωs/ωb

        Returns:
            (lambda_minus, lambda_plus) arrays
        """
        xi = np.asarray(xi)
        omega_sq = self.coupling_omega**2

        # Discriminant
        term1 = (1 - xi**2) ** 2
        term2 = 4 * omega_sq * xi**2
        discriminant = np.sqrt(term1 + term2)

        # Eigenvalues
        sum_term = 1 + xi**2
        lambda_minus = (sum_term - discriminant) / 2
        lambda_plus = (sum_term + discriminant) / 2

        return lambda_minus, lambda_plus

    def frequencies_hz(self, xi: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute actual frequencies f± in Hz.

        Args:
            xi: Detuning values ωs/ωb

        Returns:
            (f_minus_hz, f_plus_hz) arrays
        """
        lambda_m, lambda_p = self.eigenvalues(xi)

        # f = f_b * √λ
        f_minus = self.omega_b_hz * np.sqrt(np.maximum(lambda_m, 0))
        f_plus = self.omega_b_hz * np.sqrt(np.maximum(lambda_p, 0))

        return f_minus, f_plus

    def beat_frequency_hz(self, xi: np.ndarray) -> np.ndarray:
        """
        Compute beat frequency |f₊ - f₋| in Hz.

        Args:
            xi: Detuning values

        Returns:
            Beat frequency array
        """
        f_m, f_p = self.frequencies_hz(xi)
        return np.abs(f_p - f_m)

    def min_split_hz(self) -> float:
        """
        Minimum split at resonance (ξ = 1).

        This is the "avoided crossing gap" = Ω * f_b
        """
        # At ξ=1: Δλ = 2Ω, so Δf ≈ Ω * f_b for small Ω
        return self.coupling_omega * self.omega_b_hz

    def is_resolvable_at(self, xi: float) -> bool:
        """
        Check if split is resolvable at given detuning.

        Criterion: Δf > (γ_b + γ_s)
        """
        beat = self.beat_frequency_hz(np.array([xi]))[0]
        combined_gamma = self.gamma_b_hz + self.gamma_s_hz
        return beat > combined_gamma

    def damping_collapse_threshold(self) -> float:
        """
        Find the ξ where the split equals the combined linewidth.

        Below this, the wolf becomes unresolvable (peaks merge).
        Returns the detuning ξ at threshold, or 0 if always merged.
        """
        combined_gamma = self.gamma_b_hz + self.gamma_s_hz
        min_split = self.min_split_hz()

        if min_split < combined_gamma:
            # Even at resonance, peaks are merged
            return 0.0

        # Binary search for threshold
        xi_vals = np.linspace(0.5, 1.5, 1000)
        beats = self.beat_frequency_hz(xi_vals)

        # Find where beat crosses combined_gamma
        above = beats > combined_gamma
        if np.all(above) or np.all(~above):
            return 1.0  # Threshold at resonance

        # Find first crossing
        crossings = np.where(np.diff(above.astype(int)) != 0)[0]
        if len(crossings) > 0:
            return float(xi_vals[crossings[0]])

        return 1.0

    def sweep_curve(
        self,
        xi_min: float = 0.7,
        xi_max: float = 1.3,
        n_points: int = 200,
    ) -> dict:
        """
        Generate full avoided-crossing curve data.

        Returns dict with:
            xi: detuning array
            f_minus: lower branch frequencies
            f_plus: upper branch frequencies
            beat_hz: beat frequencies
            resolvable: boolean array
            severity: severity classification array
        """
        xi = np.linspace(xi_min, xi_max, n_points)
        f_m, f_p = self.frequencies_hz(xi)
        beat = self.beat_frequency_hz(xi)

        combined_gamma = self.gamma_b_hz + self.gamma_s_hz
        resolvable = beat > combined_gamma
        merge_ratio = beat / (combined_gamma + 1e-12)

        severity = []
        for mr, bf in zip(merge_ratio, beat):
            severity.append(_classify_wolf_severity(mr, bf))

        return {
            "xi": xi.tolist(),
            "f_minus_hz": f_m.tolist(),
            "f_plus_hz": f_p.tolist(),
            "beat_hz": beat.tolist(),
            "merge_ratio": merge_ratio.tolist(),
            "resolvable": resolvable.tolist(),
            "severity": severity,
            "combined_gamma_hz": combined_gamma,
            "coupling_omega": self.coupling_omega,
            "omega_b_hz": self.omega_b_hz,
        }

    def to_dict(self) -> dict:
        """Serialize model parameters."""
        return {
            "omega_b_hz": self.omega_b_hz,
            "coupling_omega": self.coupling_omega,
            "gamma_b_hz": self.gamma_b_hz,
            "gamma_s_hz": self.gamma_s_hz,
            "min_split_hz": self.min_split_hz(),
            "damping_collapse_threshold_xi": self.damping_collapse_threshold(),
        }

    @classmethod
    def from_measurement(
        cls,
        pair: PeakPair,
        string_linewidth_hz: float = 2.0,
    ) -> "AvoidedCrossingModel":
        """
        Create model from measured peak pair.

        Args:
            pair: Detected wolf pair from analyze_wolf_beat()
            string_linewidth_hz: Estimated string linewidth

        Returns:
            AvoidedCrossingModel fitted to measurement
        """
        # Extract parameters
        omega_b = pair.center_freq_hz
        delta_f = pair.delta_f_hz

        # Estimate coupling: Ω ≈ Δf / f_b (at resonance)
        coupling_omega = delta_f / omega_b

        # Use measured body linewidth (average of pair)
        gamma_b = (pair.lower.gamma_hz + pair.upper.gamma_hz) / 2

        return cls(
            omega_b_hz=omega_b,
            coupling_omega=coupling_omega,
            gamma_b_hz=gamma_b,
            gamma_s_hz=string_linewidth_hz,
        )


def simulate_mass_addition(
    model: AvoidedCrossingModel,
    mass_factor: float,
) -> AvoidedCrossingModel:
    """
    Simulate effect of adding mass (wolf eliminator).

    Physics: Adding mass m' to effective mass m:
        - New coupling: Ω' = Ω / √(1 + m'/m) = Ω / √(mass_factor)
        - Body frequency: unchanged (mass is on string side)

    Args:
        model: Current avoided-crossing model
        mass_factor: 1 + (added_mass / effective_mass)

    Returns:
        New model with reduced coupling
    """
    new_coupling = model.coupling_omega / np.sqrt(mass_factor)

    return AvoidedCrossingModel(
        omega_b_hz=model.omega_b_hz,
        coupling_omega=new_coupling,
        gamma_b_hz=model.gamma_b_hz,
        gamma_s_hz=model.gamma_s_hz,
    )


def simulate_damping_increase(
    model: AvoidedCrossingModel,
    damping_factor: float,
) -> AvoidedCrossingModel:
    """
    Simulate effect of increasing damping.

    Physics: Adding damping increases linewidth proportionally.

    Args:
        model: Current avoided-crossing model
        damping_factor: Multiplier for linewidths

    Returns:
        New model with increased linewidths
    """
    return AvoidedCrossingModel(
        omega_b_hz=model.omega_b_hz,
        coupling_omega=model.coupling_omega,
        gamma_b_hz=model.gamma_b_hz * damping_factor,
        gamma_s_hz=model.gamma_s_hz * damping_factor,
    )
