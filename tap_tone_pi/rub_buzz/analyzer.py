# INSTRUMENT CLASS: MEASUREMENT
"""
High-level Rub & Buzz analysis workflow.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np

from .schemas import (
    DefectType,
    RubBuzzResult,
    DetectionConfig,
    SweepConfig,
)
from .detector import detect_rub_buzz, compute_thd_plus_noise
from .envelope import detect_transients


class RubBuzzAnalyzer:
    """
    High-level analyzer for rub and buzz detection.

    Provides a complete workflow for:
    1. Configuring detection parameters
    2. Analyzing swept sine responses
    3. Generating pass/fail results with details
    """

    def __init__(
        self,
        detection_config: Optional[DetectionConfig] = None,
        sweep_config: Optional[SweepConfig] = None,
        sample_rate: int = 48000,
    ):
        """
        Initialize analyzer.

        Args:
            detection_config: Detection parameters
            sweep_config: Sweep configuration
            sample_rate: Sample rate in Hz
        """
        self.detection_config = detection_config or DetectionConfig()
        self.sweep_config = sweep_config or SweepConfig()
        self.sample_rate = sample_rate

    def analyze(
        self,
        signal: np.ndarray,
        pass_threshold: float = 0.5,
    ) -> RubBuzzResult:
        """
        Analyze a signal for rub and buzz defects.

        Args:
            signal: Response signal array
            pass_threshold: Maximum severity to pass

        Returns:
            RubBuzzResult with verdict and details
        """
        start_time = time.time()

        # Detect defects
        events = detect_rub_buzz(
            signal,
            self.sweep_config,
            self.detection_config,
            self.sample_rate,
        )

        # Calculate overall THD+N at reference frequency
        # Use mid-sweep point as reference
        mid_time = self.sweep_config.pre_silence_s + self.sweep_config.duration_s / 2
        mid_freq = self.sweep_config.get_freq_at_time(mid_time)

        # Extract signal around mid-sweep
        mid_sample = int(mid_time * self.sample_rate)
        window_samples = int(0.1 * self.sample_rate)  # 100ms window
        start = max(0, mid_sample - window_samples // 2)
        end = min(len(signal), mid_sample + window_samples // 2)

        if end > start:
            thd_n = compute_thd_plus_noise(
                signal[start:end],
                mid_freq,
                self.sample_rate,
            )
        else:
            thd_n = 0.0

        # Determine pass/fail
        worst_severity = max((e.severity for e in events), default=0.0)
        worst_frequency = 0.0
        if events:
            worst_event = max(events, key=lambda e: e.severity)
            worst_frequency = worst_event.frequency_hz

        passed = worst_severity < pass_threshold

        analysis_duration = time.time() - start_time

        return RubBuzzResult(
            passed=passed,
            defect_count=len(events),
            events=events,
            worst_severity=worst_severity,
            worst_frequency_hz=worst_frequency,
            thd_plus_noise_percent=thd_n,
            analysis_duration_s=analysis_duration,
        )

    def analyze_file(
        self,
        filepath: Union[str, Path],
        pass_threshold: float = 0.5,
    ) -> RubBuzzResult:
        """
        Analyze a WAV file for rub and buzz defects.

        Args:
            filepath: Path to WAV file
            pass_threshold: Maximum severity to pass

        Returns:
            RubBuzzResult with verdict and details
        """
        from tap_tone_pi.io.wav import read_wav_mono

        filepath = Path(filepath)
        signal, meta = read_wav_mono(filepath)

        # read_wav_mono returns float32 in [-1, 1] and handles stereo
        signal = signal.astype(np.float64)

        # Update sample rate from file metadata
        self.sample_rate = meta.sample_rate

        return self.analyze(signal, pass_threshold)


def analyze_sweep_response(
    signal: np.ndarray,
    start_freq_hz: float = 20.0,
    end_freq_hz: float = 20000.0,
    duration_s: float = 10.0,
    sample_rate: int = 48000,
    severity_threshold: float = 0.3,
) -> RubBuzzResult:
    """
    Convenience function for analyzing a swept sine response.

    Args:
        signal: Response signal array
        start_freq_hz: Sweep start frequency
        end_freq_hz: Sweep end frequency
        duration_s: Sweep duration in seconds
        sample_rate: Sample rate in Hz
        severity_threshold: Minimum severity to report

    Returns:
        RubBuzzResult with verdict and details
    """
    sweep_config = SweepConfig(
        start_freq_hz=start_freq_hz,
        end_freq_hz=end_freq_hz,
        duration_s=duration_s,
        sample_rate=sample_rate,
    )

    detection_config = DetectionConfig(
        severity_threshold=severity_threshold,
    )

    analyzer = RubBuzzAnalyzer(
        detection_config=detection_config,
        sweep_config=sweep_config,
        sample_rate=sample_rate,
    )

    return analyzer.analyze(signal)


def quick_rub_buzz_check(
    signal: np.ndarray,
    sample_rate: int = 48000,
    excitation_freq_hz: Optional[float] = None,
) -> Tuple[bool, float, str]:
    """
    Quick pass/fail check for rub and buzz.

    Simplified interface for production testing.

    Args:
        signal: Response signal array
        sample_rate: Sample rate in Hz
        excitation_freq_hz: Known excitation frequency (if continuous tone)

    Returns:
        Tuple of (passed, worst_severity, description)
    """
    # If excitation frequency is known, use simple THD+N check
    if excitation_freq_hz is not None:
        thd_n = compute_thd_plus_noise(
            signal,
            excitation_freq_hz,
            sample_rate,
        )

        # THD+N thresholds
        if thd_n < 1.0:
            return True, 0.0, "Clean signal"
        elif thd_n < 3.0:
            return True, 0.3, f"Minor distortion: THD+N = {thd_n:.1f}%"
        elif thd_n < 10.0:
            return False, 0.6, f"Significant distortion: THD+N = {thd_n:.1f}%"
        else:
            return False, 1.0, f"Severe distortion: THD+N = {thd_n:.1f}%"

    # Otherwise, use transient detection
    transients = detect_transients(
        signal,
        sample_rate,
        threshold_factor=4.0,  # Higher threshold for quick check
        min_duration_ms=1.0,
        max_duration_ms=20.0,
    )

    if len(transients) == 0:
        return True, 0.0, "No transients detected"
    elif len(transients) < 3:
        severity = max(t.peak_amplitude for t in transients)
        return True, min(0.4, severity), f"Minor transients: {len(transients)} events"
    elif len(transients) < 10:
        severity = max(t.peak_amplitude for t in transients)
        return (
            False,
            min(0.7, severity),
            f"Multiple transients: {len(transients)} events",
        )
    else:
        return False, 1.0, f"Severe transient activity: {len(transients)} events"


def format_result(
    result: RubBuzzResult,
    verbose: bool = False,
) -> str:
    """
    Format analysis result as human-readable string.

    Args:
        result: RubBuzzResult to format
        verbose: Include detailed event list

    Returns:
        Formatted string
    """
    lines = []

    # Header
    status = "PASS" if result.passed else "FAIL"
    lines.append(f"Rub & Buzz Analysis: {status}")
    lines.append("")

    # Summary
    lines.append(f"Defects found: {result.defect_count}")
    lines.append(f"Worst severity: {result.worst_severity:.2f}")
    if result.worst_frequency_hz > 0:
        lines.append(f"Worst at: {result.worst_frequency_hz:.0f} Hz")
    lines.append(f"THD+N: {result.thd_plus_noise_percent:.2f}%")
    lines.append(f"Analysis time: {result.analysis_duration_s:.2f}s")

    # Event breakdown by type
    if result.events:
        lines.append("")
        lines.append("Defect breakdown:")
        for defect_type in DefectType:
            events = result.get_events_by_type(defect_type)
            if events:
                lines.append(f"  {defect_type.value}: {len(events)}")

    # Detailed event list
    if verbose and result.events:
        lines.append("")
        lines.append("Event details:")
        for i, event in enumerate(result.events[:20], 1):  # Limit to 20
            lines.append(
                f"  {i}. {event.defect_type.value} at {event.time_s:.2f}s "
                f"({event.frequency_hz:.0f} Hz) - severity: {event.severity:.2f}"
            )
        if len(result.events) > 20:
            lines.append(f"  ... and {len(result.events) - 20} more events")

    return "\n".join(lines)
