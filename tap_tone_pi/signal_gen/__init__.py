"""
Signal generation module for Tap Tone Pi.

Provides configurable test signal generation for:
- Calibration verification
- System testing
- Acoustic measurements
"""

from .generators import (
    generate_sine,
    generate_sweep,
    generate_chirp,
    generate_noise,
    generate_impulse,
    generate_multitone,
    generate_comb,
)
from .waveforms import (
    WaveformType,
    SweepType,
    NoiseType,
    SignalConfig,
    SweepConfig,
    NoiseConfig,
    MultitoneConfig,
)
from .writer import (
    write_wav,
    write_raw,
    read_wav,
    signal_to_int16,
    normalize_signal,
)

__all__ = [
    # Generators
    "generate_sine",
    "generate_sweep",
    "generate_chirp",
    "generate_noise",
    "generate_impulse",
    "generate_multitone",
    "generate_comb",
    # Types
    "WaveformType",
    "SweepType",
    "NoiseType",
    "SignalConfig",
    "SweepConfig",
    "NoiseConfig",
    "MultitoneConfig",
    # Writers
    "write_wav",
    "write_raw",
    "read_wav",
    "signal_to_int16",
    "normalize_signal",
]
