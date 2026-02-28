"""
Data schemas for Rub & Buzz detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any


class DefectType(Enum):
    """Types of mechanical defects."""

    RUB = "rub"  # Voice coil rubbing on pole piece
    BUZZ = "buzz"  # Loose component vibrating
    RATTLE = "rattle"  # Loose part rattling
    CHUFF = "chuff"  # Air leak (chuffing)
    CRACKLE = "crackle"  # Intermittent electrical/mechanical
    UNKNOWN = "unknown"


@dataclass
class DefectEvent:
    """A single detected defect event."""

    defect_type: DefectType
    time_s: float  # Time in recording where defect occurred
    frequency_hz: float  # Excitation frequency at that time
    severity: float  # 0-1 severity score
    duration_ms: float  # Event duration in milliseconds
    confidence: float  # Detection confidence 0-1

    # Optional details
    peak_amplitude: float = 0.0
    snr_db: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "defect_type": self.defect_type.value,
            "time_s": self.time_s,
            "frequency_hz": self.frequency_hz,
            "severity": self.severity,
            "duration_ms": self.duration_ms,
            "confidence": self.confidence,
            "peak_amplitude": self.peak_amplitude,
            "snr_db": self.snr_db,
            "details": self.details,
        }


@dataclass
class RubBuzzResult:
    """Result of rub & buzz analysis."""

    passed: bool
    defect_count: int
    events: List[DefectEvent] = field(default_factory=list)
    worst_severity: float = 0.0
    worst_frequency_hz: float = 0.0
    thd_plus_noise_percent: float = 0.0
    analysis_duration_s: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def has_defects(self) -> bool:
        """Check if any defects were found."""
        return self.defect_count > 0

    def get_events_by_type(self, defect_type: DefectType) -> List[DefectEvent]:
        """Get events of specific type."""
        return [e for e in self.events if e.defect_type == defect_type]

    def get_events_above_severity(self, threshold: float) -> List[DefectEvent]:
        """Get events above severity threshold."""
        return [e for e in self.events if e.severity >= threshold]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "defect_count": self.defect_count,
            "events": [e.to_dict() for e in self.events],
            "worst_severity": self.worst_severity,
            "worst_frequency_hz": self.worst_frequency_hz,
            "thd_plus_noise_percent": self.thd_plus_noise_percent,
            "analysis_duration_s": self.analysis_duration_s,
            "timestamp": self.timestamp,
        }


@dataclass
class DetectionConfig:
    """Configuration for defect detection."""

    # Threshold settings
    severity_threshold: float = 0.3  # Minimum severity to report
    confidence_threshold: float = 0.5  # Minimum confidence

    # Frequency-dependent thresholds
    # Format: [(freq_hz, threshold), ...]
    # Threshold is relative to fundamental amplitude
    thresholds_by_freq: List[tuple] = field(default_factory=list)

    # Time-domain settings
    min_event_duration_ms: float = 1.0  # Ignore shorter events
    max_event_duration_ms: float = 100.0  # Longer events are sustained defects
    event_merge_gap_ms: float = 5.0  # Merge events closer than this

    # Harmonic analysis
    max_harmonic: int = 10  # Check harmonics up to this order
    harmonic_tolerance_cents: float = 50.0  # Frequency tolerance for harmonic ID

    # Envelope settings
    envelope_smoothing_ms: float = 2.0  # Envelope smoothing time constant

    def __post_init__(self):
        # Set default frequency-dependent thresholds if not provided
        if not self.thresholds_by_freq:
            self.thresholds_by_freq = [
                (20, -30),  # dB below fundamental
                (100, -35),
                (500, -40),
                (2000, -45),
                (10000, -50),
                (20000, -55),
            ]

    def get_threshold_at_freq(self, freq_hz: float) -> float:
        """Get threshold at specific frequency via interpolation."""
        if not self.thresholds_by_freq:
            return -40.0

        # Find surrounding points
        thresholds = sorted(self.thresholds_by_freq)

        if freq_hz <= thresholds[0][0]:
            return thresholds[0][1]
        if freq_hz >= thresholds[-1][0]:
            return thresholds[-1][1]

        # Linear interpolation in log frequency
        import math

        for i in range(len(thresholds) - 1):
            f1, t1 = thresholds[i]
            f2, t2 = thresholds[i + 1]
            if f1 <= freq_hz <= f2:
                log_ratio = math.log10(freq_hz / f1) / math.log10(f2 / f1)
                return t1 + (t2 - t1) * log_ratio

        return -40.0


@dataclass
class SweepConfig:
    """Configuration for swept sine measurement."""

    start_freq_hz: float = 20.0
    end_freq_hz: float = 20000.0
    duration_s: float = 10.0
    sweep_type: str = "logarithmic"  # "linear" or "logarithmic"
    sample_rate: int = 48000
    amplitude: float = 0.8

    # Pre/post silence
    pre_silence_s: float = 0.5
    post_silence_s: float = 0.5

    def get_freq_at_time(self, time_s: float) -> float:
        """Calculate instantaneous frequency at given time."""

        # Adjust for pre-silence
        t = time_s - self.pre_silence_s
        if t < 0:
            return self.start_freq_hz
        if t > self.duration_s:
            return self.end_freq_hz

        if self.sweep_type == "logarithmic":
            # Logarithmic sweep: f(t) = f1 * (f2/f1)^(t/T)
            ratio = self.end_freq_hz / self.start_freq_hz
            return self.start_freq_hz * (ratio ** (t / self.duration_s))
        else:
            # Linear sweep: f(t) = f1 + (f2-f1) * t/T
            return self.start_freq_hz + (self.end_freq_hz - self.start_freq_hz) * (
                t / self.duration_s
            )

    def get_time_at_freq(self, freq_hz: float) -> float:
        """Calculate time at which sweep reaches given frequency."""
        import math

        if self.sweep_type == "logarithmic":
            ratio = self.end_freq_hz / self.start_freq_hz
            t = (
                self.duration_s
                * math.log(freq_hz / self.start_freq_hz)
                / math.log(ratio)
            )
        else:
            t = (
                self.duration_s
                * (freq_hz - self.start_freq_hz)
                / (self.end_freq_hz - self.start_freq_hz)
            )

        return t + self.pre_silence_s
