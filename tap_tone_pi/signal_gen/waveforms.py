"""
Waveform types and configuration for signal generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class WaveformType(Enum):
    """Basic waveform types."""

    SINE = "sine"
    SQUARE = "square"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    IMPULSE = "impulse"


class SweepType(Enum):
    """Sweep signal types."""

    LINEAR = "linear"
    LOGARITHMIC = "logarithmic"
    CHIRP = "chirp"  # Exponential chirp


class NoiseType(Enum):
    """Noise signal types."""

    WHITE = "white"
    PINK = "pink"  # 1/f noise
    BROWN = "brown"  # 1/f² noise (Brownian)


@dataclass
class SignalConfig:
    """Configuration for basic signal generation."""

    sample_rate: int = 48000
    duration_s: float = 1.0
    amplitude: float = 0.8  # Peak amplitude (0-1)
    frequency_hz: float = 1000.0
    phase_deg: float = 0.0
    waveform: WaveformType = WaveformType.SINE

    # Fade in/out to reduce clicks
    fade_in_ms: float = 10.0
    fade_out_ms: float = 10.0

    @property
    def num_samples(self) -> int:
        """Total number of samples."""
        return int(self.sample_rate * self.duration_s)

    @property
    def phase_rad(self) -> float:
        """Phase in radians."""
        import math

        return self.phase_deg * math.pi / 180


@dataclass
class SweepConfig:
    """Configuration for sweep signal generation."""

    sample_rate: int = 48000
    duration_s: float = 5.0
    amplitude: float = 0.8
    start_freq_hz: float = 20.0
    end_freq_hz: float = 20000.0
    sweep_type: SweepType = SweepType.LOGARITHMIC

    # Fade in/out
    fade_in_ms: float = 50.0
    fade_out_ms: float = 50.0

    # Silence padding
    pre_silence_ms: float = 100.0
    post_silence_ms: float = 100.0

    @property
    def num_samples(self) -> int:
        """Total number of samples including padding."""
        pre = int(self.pre_silence_ms * self.sample_rate / 1000)
        post = int(self.post_silence_ms * self.sample_rate / 1000)
        sweep = int(self.sample_rate * self.duration_s)
        return pre + sweep + post

    @property
    def sweep_samples(self) -> int:
        """Number of samples for sweep portion only."""
        return int(self.sample_rate * self.duration_s)


@dataclass
class NoiseConfig:
    """Configuration for noise signal generation."""

    sample_rate: int = 48000
    duration_s: float = 1.0
    amplitude: float = 0.5  # RMS amplitude
    noise_type: NoiseType = NoiseType.WHITE
    seed: Optional[int] = None  # For reproducibility

    # Bandlimiting
    highpass_hz: Optional[float] = None
    lowpass_hz: Optional[float] = None

    # Fade
    fade_in_ms: float = 10.0
    fade_out_ms: float = 10.0

    @property
    def num_samples(self) -> int:
        """Total number of samples."""
        return int(self.sample_rate * self.duration_s)


@dataclass
class MultitoneConfig:
    """Configuration for multitone signal generation."""

    sample_rate: int = 48000
    duration_s: float = 1.0
    amplitude: float = 0.8  # Peak amplitude of combined signal

    # Frequencies and relative amplitudes
    frequencies_hz: List[float] = field(default_factory=lambda: [100.0, 1000.0, 10000.0])
    relative_amplitudes: Optional[List[float]] = None  # If None, equal amplitudes
    phases_deg: Optional[List[float]] = None  # If None, random or zero phases

    # Phase options
    random_phases: bool = False  # Use random phases to reduce crest factor

    # Fade
    fade_in_ms: float = 10.0
    fade_out_ms: float = 10.0

    @property
    def num_samples(self) -> int:
        """Total number of samples."""
        return int(self.sample_rate * self.duration_s)


@dataclass
class ImpulseConfig:
    """Configuration for impulse signal generation."""

    sample_rate: int = 48000
    duration_s: float = 1.0
    amplitude: float = 1.0  # Peak amplitude

    # Impulse timing
    impulse_time_ms: float = 100.0  # Time of impulse from start

    # Pre/post silence
    pre_silence_ms: float = 100.0
    post_silence_ms: float = 500.0

    @property
    def num_samples(self) -> int:
        """Total number of samples."""
        return int(self.sample_rate * self.duration_s)


@dataclass
class CombConfig:
    """Configuration for comb filter test signal (harmonics)."""

    sample_rate: int = 48000
    duration_s: float = 1.0
    amplitude: float = 0.8
    fundamental_hz: float = 100.0
    n_harmonics: int = 20

    # Amplitude rolloff
    rolloff_db_per_octave: float = 0.0  # 0 = flat, 3 = pink-ish

    # Fade
    fade_in_ms: float = 10.0
    fade_out_ms: float = 10.0

    @property
    def num_samples(self) -> int:
        """Total number of samples."""
        return int(self.sample_rate * self.duration_s)
