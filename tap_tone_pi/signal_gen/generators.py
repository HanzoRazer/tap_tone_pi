"""
Signal generator functions.

All generators return numpy arrays with values in [-1, 1].
"""

from __future__ import annotations

import math
from typing import Optional, Union

import numpy as np

from .waveforms import (
    SignalConfig,
    SweepConfig,
    NoiseConfig,
    MultitoneConfig,
    ImpulseConfig,
    CombConfig,
    WaveformType,
    SweepType,
    NoiseType,
)


def _apply_fade(
    signal: np.ndarray,
    sample_rate: int,
    fade_in_ms: float,
    fade_out_ms: float,
) -> np.ndarray:
    """Apply fade in/out to signal to prevent clicks."""
    result = signal.copy()

    if fade_in_ms > 0:
        fade_in_samples = int(fade_in_ms * sample_rate / 1000)
        if fade_in_samples > 0:
            fade_in = np.linspace(0, 1, fade_in_samples)
            result[:fade_in_samples] *= fade_in

    if fade_out_ms > 0:
        fade_out_samples = int(fade_out_ms * sample_rate / 1000)
        if fade_out_samples > 0:
            fade_out = np.linspace(1, 0, fade_out_samples)
            result[-fade_out_samples:] *= fade_out

    return result


def generate_sine(
    config: Optional[SignalConfig] = None,
    *,
    frequency_hz: float = 1000.0,
    duration_s: float = 1.0,
    sample_rate: int = 48000,
    amplitude: float = 0.8,
    phase_deg: float = 0.0,
    fade_in_ms: float = 10.0,
    fade_out_ms: float = 10.0,
) -> np.ndarray:
    """
    Generate a pure sine wave.

    Args:
        config: SignalConfig (overrides other args if provided)
        frequency_hz: Frequency in Hz
        duration_s: Duration in seconds
        sample_rate: Sample rate in Hz
        amplitude: Peak amplitude (0-1)
        phase_deg: Starting phase in degrees
        fade_in_ms: Fade in duration
        fade_out_ms: Fade out duration

    Returns:
        Numpy array with sine wave samples
    """
    if config is not None:
        frequency_hz = config.frequency_hz
        duration_s = config.duration_s
        sample_rate = config.sample_rate
        amplitude = config.amplitude
        phase_deg = config.phase_deg
        fade_in_ms = config.fade_in_ms
        fade_out_ms = config.fade_out_ms

    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    phase_rad = phase_deg * math.pi / 180
    signal = amplitude * np.sin(2 * math.pi * frequency_hz * t + phase_rad)

    return _apply_fade(signal, sample_rate, fade_in_ms, fade_out_ms)


def generate_sweep(
    config: Optional[SweepConfig] = None,
    *,
    start_freq_hz: float = 20.0,
    end_freq_hz: float = 20000.0,
    duration_s: float = 5.0,
    sample_rate: int = 48000,
    amplitude: float = 0.8,
    sweep_type: Union[SweepType, str] = SweepType.LOGARITHMIC,
    fade_in_ms: float = 50.0,
    fade_out_ms: float = 50.0,
    pre_silence_ms: float = 100.0,
    post_silence_ms: float = 100.0,
) -> np.ndarray:
    """
    Generate a frequency sweep signal.

    Args:
        config: SweepConfig (overrides other args if provided)
        start_freq_hz: Starting frequency
        end_freq_hz: Ending frequency
        duration_s: Sweep duration (not including silence)
        sample_rate: Sample rate
        amplitude: Peak amplitude
        sweep_type: LINEAR, LOGARITHMIC, or CHIRP
        fade_in_ms: Fade in duration
        fade_out_ms: Fade out duration
        pre_silence_ms: Silence before sweep
        post_silence_ms: Silence after sweep

    Returns:
        Numpy array with sweep samples
    """
    if config is not None:
        start_freq_hz = config.start_freq_hz
        end_freq_hz = config.end_freq_hz
        duration_s = config.duration_s
        sample_rate = config.sample_rate
        amplitude = config.amplitude
        sweep_type = config.sweep_type
        fade_in_ms = config.fade_in_ms
        fade_out_ms = config.fade_out_ms
        pre_silence_ms = config.pre_silence_ms
        post_silence_ms = config.post_silence_ms

    if isinstance(sweep_type, str):
        sweep_type = SweepType(sweep_type)

    n_samples = int(sample_rate * duration_s)
    t = np.arange(n_samples) / sample_rate

    if sweep_type == SweepType.LINEAR:
        # Linear frequency sweep
        freq_rate = (end_freq_hz - start_freq_hz) / duration_s
        phase = 2 * math.pi * (start_freq_hz * t + 0.5 * freq_rate * t**2)
        sweep = amplitude * np.sin(phase)

    elif sweep_type == SweepType.LOGARITHMIC:
        # Logarithmic (exponential) frequency sweep
        # Frequency increases exponentially: f(t) = f0 * (f1/f0)^(t/T)
        ratio = end_freq_hz / start_freq_hz
        k = math.log(ratio) / duration_s
        phase = 2 * math.pi * start_freq_hz * (np.exp(k * t) - 1) / k
        sweep = amplitude * np.sin(phase)

    elif sweep_type == SweepType.CHIRP:
        # Exponential chirp (same as logarithmic but alternative implementation)
        from scipy.signal import chirp as scipy_chirp

        sweep = amplitude * scipy_chirp(
            t, start_freq_hz, duration_s, end_freq_hz, method="logarithmic"
        )

    else:
        raise ValueError(f"Unknown sweep type: {sweep_type}")

    # Apply fade
    sweep = _apply_fade(sweep, sample_rate, fade_in_ms, fade_out_ms)

    # Add silence padding
    pre_samples = int(pre_silence_ms * sample_rate / 1000)
    post_samples = int(post_silence_ms * sample_rate / 1000)

    result = np.concatenate(
        [np.zeros(pre_samples), sweep, np.zeros(post_samples)]
    )

    return result


def generate_chirp(
    start_freq_hz: float = 20.0,
    end_freq_hz: float = 20000.0,
    duration_s: float = 5.0,
    sample_rate: int = 48000,
    amplitude: float = 0.8,
) -> np.ndarray:
    """
    Generate a logarithmic chirp (convenience function).

    This is equivalent to generate_sweep with LOGARITHMIC type.
    """
    return generate_sweep(
        start_freq_hz=start_freq_hz,
        end_freq_hz=end_freq_hz,
        duration_s=duration_s,
        sample_rate=sample_rate,
        amplitude=amplitude,
        sweep_type=SweepType.LOGARITHMIC,
    )


def generate_noise(
    config: Optional[NoiseConfig] = None,
    *,
    noise_type: Union[NoiseType, str] = NoiseType.WHITE,
    duration_s: float = 1.0,
    sample_rate: int = 48000,
    amplitude: float = 0.5,
    seed: Optional[int] = None,
    highpass_hz: Optional[float] = None,
    lowpass_hz: Optional[float] = None,
    fade_in_ms: float = 10.0,
    fade_out_ms: float = 10.0,
) -> np.ndarray:
    """
    Generate noise signal.

    Args:
        config: NoiseConfig (overrides other args if provided)
        noise_type: WHITE, PINK, or BROWN
        duration_s: Duration in seconds
        sample_rate: Sample rate
        amplitude: RMS amplitude
        seed: Random seed for reproducibility
        highpass_hz: High-pass filter cutoff (optional)
        lowpass_hz: Low-pass filter cutoff (optional)
        fade_in_ms: Fade in duration
        fade_out_ms: Fade out duration

    Returns:
        Numpy array with noise samples
    """
    if config is not None:
        noise_type = config.noise_type
        duration_s = config.duration_s
        sample_rate = config.sample_rate
        amplitude = config.amplitude
        seed = config.seed
        highpass_hz = config.highpass_hz
        lowpass_hz = config.lowpass_hz
        fade_in_ms = config.fade_in_ms
        fade_out_ms = config.fade_out_ms

    if isinstance(noise_type, str):
        noise_type = NoiseType(noise_type)

    rng = np.random.default_rng(seed)
    n_samples = int(sample_rate * duration_s)

    if noise_type == NoiseType.WHITE:
        # White noise: flat spectrum
        noise = rng.standard_normal(n_samples)

    elif noise_type == NoiseType.PINK:
        # Pink noise: 1/f spectrum (3 dB/octave rolloff)
        # Use Voss-McCartney algorithm
        noise = _generate_pink_noise(n_samples, rng)

    elif noise_type == NoiseType.BROWN:
        # Brown noise: 1/f² spectrum (cumulative sum of white)
        white = rng.standard_normal(n_samples)
        noise = np.cumsum(white)
        # High-pass to remove DC drift
        noise = noise - np.mean(noise)

    else:
        raise ValueError(f"Unknown noise type: {noise_type}")

    # Apply bandlimiting if specified
    if highpass_hz is not None or lowpass_hz is not None:
        from scipy.signal import butter, sosfilt

        sos_filters = []

        if highpass_hz is not None and highpass_hz > 0:
            nyquist = sample_rate / 2
            hp_norm = min(highpass_hz / nyquist, 0.99)
            sos_hp = butter(4, hp_norm, btype="high", output="sos")
            sos_filters.append(sos_hp)

        if lowpass_hz is not None and lowpass_hz < sample_rate / 2:
            nyquist = sample_rate / 2
            lp_norm = min(lowpass_hz / nyquist, 0.99)
            sos_lp = butter(4, lp_norm, btype="low", output="sos")
            sos_filters.append(sos_lp)

        for sos in sos_filters:
            noise = sosfilt(sos, noise)

    # Normalize to target RMS amplitude
    current_rms = np.sqrt(np.mean(noise**2))
    if current_rms > 0:
        noise = noise * (amplitude / current_rms)

    # Clip to prevent overflow
    noise = np.clip(noise, -1.0, 1.0)

    return _apply_fade(noise, sample_rate, fade_in_ms, fade_out_ms)


def _generate_pink_noise(n_samples: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate pink noise using the Voss-McCartney algorithm.

    This is an efficient algorithm that produces good quality 1/f noise.
    """
    # Number of octaves for the algorithm
    n_rows = 16

    # Initialize with white noise
    rows = rng.standard_normal((n_rows, n_samples))

    # Apply the Voss-McCartney algorithm
    pink = np.zeros(n_samples)
    running_sum = np.zeros(n_rows)

    for i in range(n_samples):
        # Update octaves based on bit patterns
        for j in range(n_rows):
            if (i + 1) % (2**j) == 0:
                running_sum[j] = rows[j, i]

        pink[i] = np.sum(running_sum)

    return pink


def generate_impulse(
    config: Optional[ImpulseConfig] = None,
    *,
    duration_s: float = 1.0,
    sample_rate: int = 48000,
    amplitude: float = 1.0,
    impulse_time_ms: float = 100.0,
) -> np.ndarray:
    """
    Generate an impulse (Dirac delta approximation).

    Args:
        config: ImpulseConfig (overrides other args)
        duration_s: Total duration
        sample_rate: Sample rate
        amplitude: Peak amplitude
        impulse_time_ms: Time of impulse from start

    Returns:
        Numpy array with impulse
    """
    if config is not None:
        duration_s = config.duration_s
        sample_rate = config.sample_rate
        amplitude = config.amplitude
        impulse_time_ms = config.impulse_time_ms

    n_samples = int(sample_rate * duration_s)
    impulse_sample = int(impulse_time_ms * sample_rate / 1000)

    signal = np.zeros(n_samples)
    if 0 <= impulse_sample < n_samples:
        signal[impulse_sample] = amplitude

    return signal


def generate_multitone(
    config: Optional[MultitoneConfig] = None,
    *,
    frequencies_hz: Optional[list] = None,
    relative_amplitudes: Optional[list] = None,
    phases_deg: Optional[list] = None,
    duration_s: float = 1.0,
    sample_rate: int = 48000,
    amplitude: float = 0.8,
    random_phases: bool = False,
    fade_in_ms: float = 10.0,
    fade_out_ms: float = 10.0,
) -> np.ndarray:
    """
    Generate a multitone signal (sum of sine waves).

    Args:
        config: MultitoneConfig (overrides other args)
        frequencies_hz: List of frequencies
        relative_amplitudes: Relative amplitude of each tone (normalized)
        phases_deg: Phase of each tone in degrees
        duration_s: Duration
        sample_rate: Sample rate
        amplitude: Peak amplitude of combined signal
        random_phases: Use random phases (reduces crest factor)
        fade_in_ms: Fade in
        fade_out_ms: Fade out

    Returns:
        Numpy array with multitone signal
    """
    if config is not None:
        frequencies_hz = config.frequencies_hz
        relative_amplitudes = config.relative_amplitudes
        phases_deg = config.phases_deg
        duration_s = config.duration_s
        sample_rate = config.sample_rate
        amplitude = config.amplitude
        random_phases = config.random_phases
        fade_in_ms = config.fade_in_ms
        fade_out_ms = config.fade_out_ms

    if frequencies_hz is None:
        frequencies_hz = [100.0, 1000.0, 10000.0]

    n_tones = len(frequencies_hz)

    # Set up relative amplitudes
    if relative_amplitudes is None:
        rel_amps = np.ones(n_tones)
    else:
        rel_amps = np.array(relative_amplitudes)

    # Normalize relative amplitudes
    rel_amps = rel_amps / np.sum(rel_amps)

    # Set up phases
    if phases_deg is None:
        if random_phases:
            phases = np.random.uniform(0, 2 * math.pi, n_tones)
        else:
            phases = np.zeros(n_tones)
    else:
        phases = np.array(phases_deg) * math.pi / 180

    # Generate time array
    n_samples = int(sample_rate * duration_s)
    t = np.arange(n_samples) / sample_rate

    # Sum all tones
    signal = np.zeros(n_samples)
    for i, freq in enumerate(frequencies_hz):
        signal += rel_amps[i] * np.sin(2 * math.pi * freq * t + phases[i])

    # Scale to target peak amplitude
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal * (amplitude / peak)

    return _apply_fade(signal, sample_rate, fade_in_ms, fade_out_ms)


def generate_comb(
    config: Optional[CombConfig] = None,
    *,
    fundamental_hz: float = 100.0,
    n_harmonics: int = 20,
    duration_s: float = 1.0,
    sample_rate: int = 48000,
    amplitude: float = 0.8,
    rolloff_db_per_octave: float = 0.0,
    fade_in_ms: float = 10.0,
    fade_out_ms: float = 10.0,
) -> np.ndarray:
    """
    Generate a comb signal (fundamental + harmonics).

    This is useful for testing harmonic analysis and pitch detection.

    Args:
        config: CombConfig (overrides other args)
        fundamental_hz: Fundamental frequency
        n_harmonics: Number of harmonics to include
        duration_s: Duration
        sample_rate: Sample rate
        amplitude: Peak amplitude
        rolloff_db_per_octave: Amplitude rolloff per octave (0 = flat)
        fade_in_ms: Fade in
        fade_out_ms: Fade out

    Returns:
        Numpy array with comb signal
    """
    if config is not None:
        fundamental_hz = config.fundamental_hz
        n_harmonics = config.n_harmonics
        duration_s = config.duration_s
        sample_rate = config.sample_rate
        amplitude = config.amplitude
        rolloff_db_per_octave = config.rolloff_db_per_octave
        fade_in_ms = config.fade_in_ms
        fade_out_ms = config.fade_out_ms

    # Generate frequencies (harmonics)
    frequencies = [fundamental_hz * (i + 1) for i in range(n_harmonics)]

    # Filter out frequencies above Nyquist
    nyquist = sample_rate / 2
    frequencies = [f for f in frequencies if f < nyquist]

    if not frequencies:
        raise ValueError(
            f"No valid harmonics: fundamental {fundamental_hz} Hz with {n_harmonics} "
            f"harmonics all exceed Nyquist ({nyquist} Hz)"
        )

    # Calculate relative amplitudes with rolloff
    rel_amps = []
    for i, freq in enumerate(frequencies):
        if rolloff_db_per_octave == 0:
            rel_amps.append(1.0)
        else:
            # Calculate octaves above fundamental
            octaves = math.log2(freq / fundamental_hz)
            db_reduction = rolloff_db_per_octave * octaves
            rel_amps.append(10 ** (-db_reduction / 20))

    # Use multitone generator
    return generate_multitone(
        frequencies_hz=frequencies,
        relative_amplitudes=rel_amps,
        duration_s=duration_s,
        sample_rate=sample_rate,
        amplitude=amplitude,
        random_phases=False,  # Aligned phases for comb
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
    )
