"""Deterministic synthetic audio generators for tap-tone / damping tests.

These produce signals in-memory (float32, ~[-1, 1]) with known ground truth, so
tests never depend on committed binary WAVs or on hardware. Spectra are computed
with the same Hanning-window rFFT the offline tap-tone analyzer uses, so fixture
spectra match the production peak/bandwidth path.

Decay convention (matches tap_tone_pi.damping): amplitude envelope
A(t) = A0 * exp(-t / tau); for a mode at f0, Q = pi * f0 * tau.
"""

from __future__ import annotations

import numpy as np
from numpy.fft import rfft, rfftfreq


def damped_sine(
    freq_hz: float,
    tau_s: float,
    sample_rate: int = 48_000,
    duration_s: float = 1.0,
    amplitude: float = 0.8,
    phase: float = 0.0,
    t_rise_s: float = 0.004,
) -> np.ndarray:
    """A single damped sinusoid with a realistic finite attack then exp decay.

    The envelope is A0 * (1 - exp(-t / t_rise)) * exp(-t / tau): a fast rise (like
    a physical tap onset, not an instantaneous step) followed by exponential decay
    with time constant tau. The finite attack places the envelope maximum just
    after onset so decay fitting sees the mode's decay, not a filter step
    transient. Set t_rise_s <= 0 for an idealized instantaneous onset.
    """
    n = int(round(duration_s * sample_rate))
    t = np.arange(n) / sample_rate
    decay = np.exp(-t / tau_s)
    attack = 1.0 if t_rise_s <= 0 else (1.0 - np.exp(-t / t_rise_s))
    env = amplitude * attack * decay
    sig = env * np.sin(2.0 * np.pi * freq_hz * t + phase)
    return sig.astype(np.float32)


def two_modes(
    freqs_hz: tuple[float, float],
    taus_s: tuple[float, float],
    amplitudes: tuple[float, float] = (0.6, 0.4),
    sample_rate: int = 48_000,
    duration_s: float = 1.0,
) -> np.ndarray:
    """Superposition of two damped sinusoids (separated or closely spaced)."""
    a = damped_sine(freqs_hz[0], taus_s[0], sample_rate, duration_s, amplitudes[0])
    b = damped_sine(freqs_hz[1], taus_s[1], sample_rate, duration_s, amplitudes[1])
    return (a + b).astype(np.float32)


def add_noise(signal: np.ndarray, snr_db: float, seed: int = 1234) -> np.ndarray:
    """Add deterministic white Gaussian noise at a target SNR (seeded)."""
    rng = np.random.default_rng(seed)
    sig_power = float(np.mean(signal.astype(np.float64) ** 2))
    if sig_power <= 0:
        return signal.astype(np.float32)
    noise_power = sig_power / (10.0 ** (snr_db / 10.0))
    noise = rng.normal(0.0, np.sqrt(noise_power), size=signal.shape)
    return (signal.astype(np.float64) + noise).astype(np.float32)


def clip(signal: np.ndarray, level: float = 0.3) -> np.ndarray:
    """Hard-clip the signal to +/- level (simulates an overdriven capture)."""
    return np.clip(signal, -abs(level), abs(level)).astype(np.float32)


def spectrum(signal: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """(freqs, linear magnitude) via mean-removed Hanning-window rFFT.

    Mirrors modes/tap_tone/offline_from_wav.analyze so fixture spectra match the
    production primary-extraction path.
    """
    y = signal.astype(np.float64)
    y = y - np.mean(y)
    window = np.hanning(len(y))
    mag = np.abs(rfft(window * y))
    freqs = rfftfreq(len(y), 1.0 / sample_rate)
    return freqs, mag


def dominant_peak_hz(signal: np.ndarray, sample_rate: int) -> float:
    """Frequency of the largest spectral peak (for seeding secondary analysis)."""
    freqs, mag = spectrum(signal, sample_rate)
    return float(freqs[int(np.argmax(mag))])
