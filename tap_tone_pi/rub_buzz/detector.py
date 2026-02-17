"""
Core Rub & Buzz detection algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

import numpy as np
from scipy import signal as scipy_signal

from .schemas import DefectType, DefectEvent, DetectionConfig, SweepConfig
from .envelope import compute_envelope, detect_transients


@dataclass
class HarmonicAnalysis:
    """Result of harmonic analysis at a single frequency."""

    fundamental_hz: float
    fundamental_amplitude: float
    harmonics: List[Tuple[int, float, float]]  # (order, freq_hz, amplitude)
    thd_percent: float
    noise_floor_db: float
    non_harmonic_content_db: float  # Content not at harmonics

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "fundamental_hz": self.fundamental_hz,
            "fundamental_amplitude": self.fundamental_amplitude,
            "harmonics": [
                {"order": h[0], "freq_hz": h[1], "amplitude": h[2]}
                for h in self.harmonics
            ],
            "thd_percent": self.thd_percent,
            "noise_floor_db": self.noise_floor_db,
            "non_harmonic_content_db": self.non_harmonic_content_db,
        }


def analyze_harmonics(
    signal: np.ndarray,
    fundamental_hz: float,
    sample_rate: int = 48000,
    max_harmonic: int = 10,
    tolerance_cents: float = 50.0,
    fft_size: int = 0,
) -> HarmonicAnalysis:
    """
    Analyze harmonic content of a signal at a known fundamental.

    Args:
        signal: Input signal array
        fundamental_hz: Expected fundamental frequency
        sample_rate: Sample rate in Hz
        max_harmonic: Maximum harmonic order to analyze
        tolerance_cents: Frequency tolerance for harmonic identification
        fft_size: FFT size (0 = auto)

    Returns:
        HarmonicAnalysis result
    """
    if fft_size == 0:
        # Auto-size FFT for good frequency resolution
        fft_size = max(4096, 2 ** int(np.ceil(np.log2(len(signal)))))

    # Compute FFT
    if len(signal) < fft_size:
        signal = np.pad(signal, (0, fft_size - len(signal)))

    window = np.hanning(len(signal[:fft_size]))
    fft = np.fft.rfft(signal[:fft_size] * window)
    freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
    magnitudes = np.abs(fft)

    # Convert tolerance to frequency ratio
    tolerance_ratio = 2 ** (tolerance_cents / 1200)

    # Find harmonics
    harmonics = []
    total_harmonic_power = 0.0
    fundamental_amplitude = 0.0

    for h in range(1, max_harmonic + 1):
        target_freq = fundamental_hz * h
        if target_freq > sample_rate / 2:
            break

        # Find peak near target frequency
        freq_min = target_freq / tolerance_ratio
        freq_max = target_freq * tolerance_ratio
        mask = (freqs >= freq_min) & (freqs <= freq_max)

        if not np.any(mask):
            continue

        peak_idx = np.argmax(magnitudes * mask)
        peak_freq = freqs[peak_idx]
        peak_amp = magnitudes[peak_idx]

        harmonics.append((h, peak_freq, peak_amp))

        if h == 1:
            fundamental_amplitude = peak_amp
        else:
            total_harmonic_power += peak_amp ** 2

    # Calculate THD
    if fundamental_amplitude > 0:
        thd_percent = 100 * np.sqrt(total_harmonic_power) / fundamental_amplitude
    else:
        thd_percent = 0.0

    # Estimate noise floor (median of non-harmonic bins)
    # Create mask for harmonic bins
    harmonic_mask = np.zeros_like(magnitudes, dtype=bool)
    for h in range(1, max_harmonic + 1):
        target_freq = fundamental_hz * h
        freq_min = target_freq / tolerance_ratio
        freq_max = target_freq * tolerance_ratio
        harmonic_mask |= (freqs >= freq_min) & (freqs <= freq_max)

    non_harmonic = magnitudes[~harmonic_mask]
    if len(non_harmonic) > 0:
        noise_floor = np.median(non_harmonic)
        # Sum of non-harmonic content above noise floor
        non_harmonic_power = np.sum((non_harmonic[non_harmonic > noise_floor * 3]) ** 2)
        if fundamental_amplitude > 0:
            non_harmonic_content_db = 10 * np.log10(
                non_harmonic_power / (fundamental_amplitude ** 2) + 1e-10
            )
        else:
            non_harmonic_content_db = -100.0
        noise_floor_db = 20 * np.log10(noise_floor + 1e-10)
    else:
        noise_floor_db = -100.0
        non_harmonic_content_db = -100.0

    return HarmonicAnalysis(
        fundamental_hz=fundamental_hz,
        fundamental_amplitude=fundamental_amplitude,
        harmonics=harmonics,
        thd_percent=thd_percent,
        noise_floor_db=noise_floor_db,
        non_harmonic_content_db=non_harmonic_content_db,
    )


def compute_thd_plus_noise(
    signal: np.ndarray,
    fundamental_hz: float,
    sample_rate: int = 48000,
    bandwidth_hz: float = 20000.0,
) -> float:
    """
    Compute THD+N (Total Harmonic Distortion plus Noise).

    Args:
        signal: Input signal array
        fundamental_hz: Fundamental frequency
        sample_rate: Sample rate in Hz
        bandwidth_hz: Measurement bandwidth

    Returns:
        THD+N as percentage
    """
    # Compute FFT
    fft_size = max(4096, 2 ** int(np.ceil(np.log2(len(signal)))))
    if len(signal) < fft_size:
        signal = np.pad(signal, (0, fft_size - len(signal)))

    window = np.hanning(fft_size)
    fft = np.fft.rfft(signal[:fft_size] * window)
    freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
    power = np.abs(fft) ** 2

    # Find fundamental bin
    fund_idx = np.argmin(np.abs(freqs - fundamental_hz))
    fundamental_power = power[fund_idx]

    # Sum power in a few bins around fundamental
    bin_width = 5
    fund_start = max(0, fund_idx - bin_width)
    fund_end = min(len(power), fund_idx + bin_width)
    fundamental_power = np.sum(power[fund_start:fund_end])

    # Total power within bandwidth
    bandwidth_mask = freqs <= bandwidth_hz
    total_power = np.sum(power[bandwidth_mask])

    # THD+N = everything except fundamental
    noise_plus_distortion_power = total_power - fundamental_power

    if fundamental_power > 0:
        thd_n_percent = 100 * np.sqrt(noise_plus_distortion_power / fundamental_power)
    else:
        thd_n_percent = 100.0

    return thd_n_percent


def detect_rub_buzz(
    signal: np.ndarray,
    sweep_config: SweepConfig,
    detection_config: Optional[DetectionConfig] = None,
    sample_rate: int = 48000,
) -> List[DefectEvent]:
    """
    Detect rub and buzz events in a swept sine response.

    Args:
        signal: Response signal array
        sweep_config: Configuration of the excitation sweep
        detection_config: Detection parameters
        sample_rate: Sample rate in Hz

    Returns:
        List of DefectEvent objects
    """
    if detection_config is None:
        detection_config = DetectionConfig()

    events = []

    # Divide signal into analysis windows
    window_duration_ms = 50.0
    window_samples = int(window_duration_ms * sample_rate / 1000)
    hop_samples = window_samples // 2

    # Compute overall envelope for transient detection
    envelope = compute_envelope(signal, sample_rate)

    # Detect transients in envelope
    transients = detect_transients(
        signal,
        sample_rate,
        min_duration_ms=detection_config.min_event_duration_ms,
        max_duration_ms=detection_config.max_event_duration_ms,
        merge_gap_ms=detection_config.event_merge_gap_ms,
    )

    # Analyze each window for non-harmonic content
    n_windows = (len(signal) - window_samples) // hop_samples + 1

    for i in range(n_windows):
        start_sample = i * hop_samples
        end_sample = start_sample + window_samples

        if end_sample > len(signal):
            break

        window_signal = signal[start_sample:end_sample]

        # Get instantaneous frequency at this window
        window_time = (start_sample + window_samples // 2) / sample_rate
        inst_freq = sweep_config.get_freq_at_time(window_time)

        if inst_freq < 10 or inst_freq > sample_rate / 2:
            continue

        # Analyze harmonics
        harmonic_analysis = analyze_harmonics(
            window_signal,
            inst_freq,
            sample_rate,
            max_harmonic=detection_config.max_harmonic,
            tolerance_cents=detection_config.harmonic_tolerance_cents,
        )

        # Get threshold at this frequency
        threshold_db = detection_config.get_threshold_at_freq(inst_freq)

        # Check for non-harmonic content above threshold
        if harmonic_analysis.non_harmonic_content_db > threshold_db:
            severity = min(
                1.0,
                (harmonic_analysis.non_harmonic_content_db - threshold_db) / 20.0
            )

            if severity >= detection_config.severity_threshold:
                # Classify defect type based on characteristics
                defect_type = _classify_defect(
                    harmonic_analysis,
                    inst_freq,
                    envelope[start_sample:end_sample],
                )

                event = DefectEvent(
                    defect_type=defect_type,
                    time_s=window_time,
                    frequency_hz=inst_freq,
                    severity=severity,
                    duration_ms=window_duration_ms,
                    confidence=0.7,  # Base confidence
                    snr_db=harmonic_analysis.non_harmonic_content_db - harmonic_analysis.noise_floor_db,
                    details={
                        "thd_percent": harmonic_analysis.thd_percent,
                        "non_harmonic_db": harmonic_analysis.non_harmonic_content_db,
                    },
                )
                events.append(event)

    # Add transient-based events
    for transient in transients:
        transient_time = transient.peak_sample / sample_rate
        inst_freq = sweep_config.get_freq_at_time(transient_time)

        # Calculate severity from transient characteristics
        severity = min(1.0, transient.rise_rate * 10)

        if severity >= detection_config.severity_threshold:
            event = DefectEvent(
                defect_type=DefectType.RUB,  # Transients often indicate rub
                time_s=transient_time,
                frequency_hz=inst_freq,
                severity=severity,
                duration_ms=transient.duration_samples * 1000 / sample_rate,
                confidence=0.6,
                peak_amplitude=transient.peak_amplitude,
                details={"transient": True},
            )
            events.append(event)

    # Merge overlapping events
    events = _merge_events(events, merge_gap_s=0.02)

    # Update confidence based on consistency
    events = _update_confidence(events)

    return events


def _classify_defect(
    harmonic_analysis: HarmonicAnalysis,
    frequency_hz: float,
    envelope: np.ndarray,
) -> DefectType:
    """
    Classify defect type based on signal characteristics.

    Args:
        harmonic_analysis: Harmonic analysis result
        frequency_hz: Instantaneous frequency
        envelope: Envelope segment

    Returns:
        DefectType classification
    """
    # High THD often indicates mechanical contact (rub)
    if harmonic_analysis.thd_percent > 10:
        return DefectType.RUB

    # Intermittent envelope suggests buzz/rattle
    envelope_std = np.std(envelope)
    envelope_mean = np.mean(envelope)
    if envelope_std / (envelope_mean + 1e-10) > 0.5:
        return DefectType.BUZZ

    # Low frequency defects more likely rub, high frequency more likely buzz
    if frequency_hz < 500:
        return DefectType.RUB
    elif frequency_hz > 5000:
        return DefectType.BUZZ

    return DefectType.UNKNOWN


def _merge_events(
    events: List[DefectEvent],
    merge_gap_s: float = 0.02,
) -> List[DefectEvent]:
    """Merge events that are close in time."""
    if not events:
        return []

    # Sort by time
    sorted_events = sorted(events, key=lambda e: e.time_s)

    merged = [sorted_events[0]]
    for event in sorted_events[1:]:
        last = merged[-1]
        if event.time_s - last.time_s < merge_gap_s:
            # Merge: keep worse severity, combine duration
            if event.severity > last.severity:
                merged[-1] = DefectEvent(
                    defect_type=event.defect_type,
                    time_s=last.time_s,
                    frequency_hz=(last.frequency_hz + event.frequency_hz) / 2,
                    severity=event.severity,
                    duration_ms=last.duration_ms + event.duration_ms,
                    confidence=max(last.confidence, event.confidence),
                )
        else:
            merged.append(event)

    return merged


def _update_confidence(events: List[DefectEvent]) -> List[DefectEvent]:
    """Update confidence based on event patterns."""
    if len(events) < 2:
        return events

    # Events that repeat at similar frequencies have higher confidence
    freq_counts: Dict[int, int] = {}
    for event in events:
        freq_bin = int(event.frequency_hz / 50) * 50  # 50 Hz bins
        freq_counts[freq_bin] = freq_counts.get(freq_bin, 0) + 1

    updated = []
    for event in events:
        freq_bin = int(event.frequency_hz / 50) * 50
        if freq_counts[freq_bin] > 1:
            # Multiple events at similar frequency = higher confidence
            confidence_boost = min(0.3, 0.1 * freq_counts[freq_bin])
            event = DefectEvent(
                defect_type=event.defect_type,
                time_s=event.time_s,
                frequency_hz=event.frequency_hz,
                severity=event.severity,
                duration_ms=event.duration_ms,
                confidence=min(1.0, event.confidence + confidence_boost),
                peak_amplitude=event.peak_amplitude,
                snr_db=event.snr_db,
                details=event.details,
            )
        updated.append(event)

    return updated
