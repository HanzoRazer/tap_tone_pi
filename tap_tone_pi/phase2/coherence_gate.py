# INSTRUMENT CLASS: MEASUREMENT
"""
Phase 2 Coherence Gate — Per-point quality checking.

Checks if the captured response has sufficient coherence at the
dominant frequency to be considered reliable. Low coherence indicates
unreliable data (noise, poor coupling, external interference).

Usage:
    from tap_tone_pi.phase2.coherence_gate import check_coherence, CoherenceResult

    result = check_coherence(
        capture_path="session/A1/capture.wav",
        reference_path="session/reference.wav",  # Optional
        threshold=0.7,
    )
    
    if result.passed:
        print(f"Good capture: γ² = {result.coherence:.2f}")
    else:
        print(f"Low coherence: γ² = {result.coherence:.2f}")
        print(f"Recommendation: {result.recommendation}")
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from scipy.signal import coherence as scipy_coherence, welch

from tap_tone_pi.io.wav import read_wav_mono


def _compute_fft_peaks(
    signal: np.ndarray,
    fs: float,
    *,
    n_peaks: int = 5,
    freq_min: float = 80.0,
    freq_max: float = 2000.0,
) -> List[Tuple[float, float]]:
    """Top spectral peaks (freq_hz, power) from Welch PSD."""
    n = len(signal)
    nperseg = min(4096, max(256, n // 4))
    if n < nperseg * 2:
        return []
    f, pxx = welch(signal, fs=fs, nperseg=nperseg)
    mask = (f >= freq_min) & (f <= freq_max)
    fm = f[mask]
    pm = pxx[mask]
    if len(pm) == 0:
        return []
    k = min(n_peaks, len(pm))
    idx = np.argpartition(pm, -k)[-k:]
    idx = idx[np.argsort(pm[idx])[::-1]]
    return [(float(fm[i]), float(pm[i])) for i in idx]


def _compute_coherence(
    x: np.ndarray,
    y: np.ndarray,
    fs: float,
    *,
    nperseg: int = 4096,
) -> Tuple[np.ndarray, np.ndarray]:
    """Welch coherence γ²(f) between two real signals."""
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    y = np.asarray(y, dtype=np.float64).reshape(-1)
    n = min(len(x), len(y))
    nseg = min(nperseg, max(128, n // 2))
    f, c = scipy_coherence(x[:n], y[:n], fs=fs, nperseg=nseg)
    return f, c


compute_fft_peaks = _compute_fft_peaks
compute_coherence = _compute_coherence


@dataclass
class CoherenceResult:
    """Result of coherence gate check."""
    
    # Pass/fail
    passed: bool
    
    # Coherence value at dominant frequency
    coherence: float
    
    # Dominant frequency where coherence was measured
    dominant_freq_hz: float
    
    # Threshold used
    threshold: float
    
    # Additional diagnostics
    mean_coherence: float = 0.0
    coherence_at_peaks: List[Tuple[float, float]] = None  # [(freq, coherence), ...]
    
    # Recommendation if failed
    recommendation: str = ""
    
    def __post_init__(self):
        if self.coherence_at_peaks is None:
            self.coherence_at_peaks = []
        
        if not self.passed and not self.recommendation:
            self._generate_recommendation()
    
    def _generate_recommendation(self) -> None:
        """Generate actionable recommendation based on coherence pattern."""
        if self.coherence < 0.3:
            self.recommendation = (
                "Very low coherence. Check: (1) microphone placement, "
                "(2) background noise, (3) tap strength and consistency."
            )
        elif self.coherence < 0.5:
            self.recommendation = (
                "Low coherence. Try: (1) move to quieter environment, "
                "(2) ensure firm microphone coupling, (3) tap harder."
            )
        elif self.coherence < self.threshold:
            self.recommendation = (
                f"Marginal coherence ({self.coherence:.2f} < {self.threshold:.2f}). "
                "Retry recommended. Minor adjustments may help."
            )


def check_coherence(
    capture_wav: Path,
    reference_wav: Optional[Path] = None,
    threshold: float = 0.7,
    freq_range_hz: Tuple[float, float] = (80.0, 2000.0),
    sample_rate: int = 44100,
    nperseg: int = 4096,
) -> CoherenceResult:
    """
    Check coherence of a capture against threshold.
    
    For Phase 2, we typically use auto-coherence (signal with itself
    after trigger detection) or cross-coherence with a reference mic.
    
    Args:
        capture_wav: Path to captured WAV file
        reference_wav: Optional path to reference WAV (for cross-coherence)
        threshold: Minimum acceptable coherence (default 0.7)
        freq_range_hz: Frequency range to analyze
        sample_rate: Expected sample rate
        nperseg: FFT segment size
    
    Returns:
        CoherenceResult with pass/fail and diagnostics
    """
    capture_path = Path(capture_wav)
    
    if not capture_path.exists():
        return CoherenceResult(
            passed=False,
            coherence=0.0,
            dominant_freq_hz=0.0,
            threshold=threshold,
            recommendation=f"Capture file not found: {capture_path}",
        )
    
    # Read capture
    signal, meta = read_wav_mono(capture_path)
    fs = meta.sample_rate
    
    if len(signal) < nperseg * 2:
        return CoherenceResult(
            passed=False,
            coherence=0.0,
            dominant_freq_hz=0.0,
            threshold=threshold,
            recommendation="Capture too short for coherence analysis.",
        )

    peaks = _compute_fft_peaks(
        signal,
        fs,
        n_peaks=5,
        freq_min=freq_range_hz[0],
        freq_max=freq_range_hz[1],
    )
    
    if not peaks:
        return CoherenceResult(
            passed=False,
            coherence=0.0,
            dominant_freq_hz=0.0,
            threshold=threshold,
            recommendation="No significant peaks found in capture.",
        )
    
    dominant_freq = peaks[0][0]  # (freq, magnitude) tuple
    
    # Compute coherence
    if reference_wav is not None:
        # Cross-coherence with reference
        ref_path = Path(reference_wav)
        if not ref_path.exists():
            return CoherenceResult(
                passed=False,
                coherence=0.0,
                dominant_freq_hz=dominant_freq,
                threshold=threshold,
                recommendation=f"Reference file not found: {ref_path}",
            )
        
        ref_signal, ref_meta = read_wav_mono(ref_path)
        
        # Ensure same length
        min_len = min(len(signal), len(ref_signal))
        signal = signal[:min_len]
        ref_signal = ref_signal[:min_len]
        
        freqs, coh = _compute_coherence(
            signal, ref_signal, fs, nperseg=nperseg
        )
    else:
        # Auto-coherence: split signal in half and compare
        half = len(signal) // 2
        sig1 = signal[:half]
        sig2 = signal[half : half * 2]

        freqs, coh = _compute_coherence(
            sig1, sig2, fs, nperseg=max(128, nperseg // 2)
        )
    
    # Find coherence at dominant frequency
    freq_idx = np.argmin(np.abs(freqs - dominant_freq))
    coherence_at_dominant = float(coh[freq_idx])
    
    # Mean coherence in frequency range
    freq_mask = (freqs >= freq_range_hz[0]) & (freqs <= freq_range_hz[1])
    mean_coh = float(np.mean(coh[freq_mask])) if np.any(freq_mask) else 0.0
    
    # Coherence at each peak
    coherence_at_peaks = []
    for freq, mag in peaks[:5]:
        idx = np.argmin(np.abs(freqs - freq))
        coherence_at_peaks.append((freq, float(coh[idx])))
    
    passed = coherence_at_dominant >= threshold
    
    return CoherenceResult(
        passed=passed,
        coherence=coherence_at_dominant,
        dominant_freq_hz=dominant_freq,
        threshold=threshold,
        mean_coherence=mean_coh,
        coherence_at_peaks=coherence_at_peaks,
    )


def check_coherence_from_arrays(
    signal: np.ndarray,
    reference: Optional[np.ndarray],
    sample_rate: int,
    threshold: float = 0.7,
    freq_range_hz: Tuple[float, float] = (80.0, 2000.0),
    nperseg: int = 4096,
) -> CoherenceResult:
    """
    Check coherence from numpy arrays (for use in capture loop).
    
    Args:
        signal: Captured audio signal
        reference: Optional reference signal
        sample_rate: Sample rate in Hz
        threshold: Minimum acceptable coherence
        freq_range_hz: Frequency range to analyze
        nperseg: FFT segment size
    
    Returns:
        CoherenceResult with pass/fail and diagnostics
    """
    fs = sample_rate
    
    if len(signal) < nperseg * 2:
        return CoherenceResult(
            passed=False,
            coherence=0.0,
            dominant_freq_hz=0.0,
            threshold=threshold,
            recommendation="Signal too short for coherence analysis.",
        )
    
    # Find dominant frequency
    peaks = _compute_fft_peaks(
        signal,
        fs,
        n_peaks=5,
        freq_min=freq_range_hz[0],
        freq_max=freq_range_hz[1],
    )

    if not peaks:
        return CoherenceResult(
            passed=False,
            coherence=0.0,
            dominant_freq_hz=0.0,
            threshold=threshold,
            recommendation="No significant peaks found.",
        )

    dominant_freq = peaks[0][0]

    if reference is not None:
        min_len = min(len(signal), len(reference))
        freqs, coh = _compute_coherence(
            signal[:min_len], reference[:min_len], fs, nperseg=nperseg
        )
    else:
        half = len(signal) // 2
        freqs, coh = _compute_coherence(
            signal[:half],
            signal[half : half * 2],
            fs,
            nperseg=max(128, nperseg // 2),
        )
    
    freq_idx = np.argmin(np.abs(freqs - dominant_freq))
    coherence_at_dominant = float(coh[freq_idx])
    
    freq_mask = (freqs >= freq_range_hz[0]) & (freqs <= freq_range_hz[1])
    mean_coh = float(np.mean(coh[freq_mask])) if np.any(freq_mask) else 0.0
    
    coherence_at_peaks = []
    for freq, mag in peaks[:5]:
        idx = np.argmin(np.abs(freqs - freq))
        coherence_at_peaks.append((freq, float(coh[idx])))
    
    passed = coherence_at_dominant >= threshold
    
    return CoherenceResult(
        passed=passed,
        coherence=coherence_at_dominant,
        dominant_freq_hz=dominant_freq,
        threshold=threshold,
        mean_coherence=mean_coh,
        coherence_at_peaks=coherence_at_peaks,
    )


def format_coherence_feedback(result: CoherenceResult, use_color: bool = True) -> str:
    """
    Format coherence result for terminal display.
    
    Args:
        result: CoherenceResult to format
        use_color: Whether to use ANSI colors
    
    Returns:
        Formatted string for display
    """
    # ANSI codes
    GREEN = "\033[32m" if use_color else ""
    YELLOW = "\033[33m" if use_color else ""
    RED = "\033[31m" if use_color else ""
    RESET = "\033[0m" if use_color else ""
    BOLD = "\033[1m" if use_color else ""
    
    if result.passed:
        status = f"{GREEN}{BOLD}PASS{RESET}"
        icon = "✓"
    elif result.coherence >= result.threshold * 0.8:
        status = f"{YELLOW}{BOLD}WARN{RESET}"
        icon = "!"
    else:
        status = f"{RED}{BOLD}FAIL{RESET}"
        icon = "✗"
    
    line1 = f"{icon} Coherence: γ² = {result.coherence:.3f} (threshold: {result.threshold:.2f}) [{status}]"
    line2 = f"  Dominant frequency: {result.dominant_freq_hz:.1f} Hz"
    
    lines = [line1, line2]
    
    if not result.passed and result.recommendation:
        lines.append(f"  → {result.recommendation}")
    
    return "\n".join(lines)


def demo():
    """Demo coherence gate with synthetic data."""
    import numpy as np
    
    fs = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(fs * duration))
    
    # Create test signals
    # Good coherence: clean sinusoid
    clean_signal = np.sin(2 * np.pi * 200 * t) * 0.5
    
    # Poor coherence: mostly noise
    noisy_signal = clean_signal * 0.1 + np.random.randn(len(t)) * 0.5
    
    print("Testing coherence gate with synthetic signals:\n")
    
    # Test 1: Clean signal (should pass)
    result1 = check_coherence_from_arrays(clean_signal, None, fs, threshold=0.7)
    print("Clean signal:")
    print(format_coherence_feedback(result1))
    print()
    
    # Test 2: Noisy signal (should fail)
    result2 = check_coherence_from_arrays(noisy_signal, None, fs, threshold=0.7)
    print("Noisy signal:")
    print(format_coherence_feedback(result2))


if __name__ == "__main__":
    demo()
