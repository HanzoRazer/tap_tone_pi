# INSTRUMENT CLASS: MEASUREMENT
"""Phase 1 demo mode — synthetic tap tone for hardware-free testing.

Generates realistic multi-harmonic tap impulses for testing the analysis
pipeline without audio hardware. Useful for:
- CI/CD validation
- Developer testing without microphone
- Raspberry Pi initial setup verification

Usage:
    from tap_tone_pi.phase1.demo import generate_tap_impulse, run_demo

    # Generate synthetic audio
    audio = generate_tap_impulse(fundamental_hz=245.0)

    # Run full demo workflow
    run_demo(save_artifacts=True, output_dir="./demo_output")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class TapImpulseConfig:
    """Configuration for synthetic tap impulse generation."""

    fundamental_hz: float = 245.0
    harmonics: Sequence[tuple[float, float]] | None = None  # (freq_ratio, amplitude)
    sample_rate: int = 48000
    duration_s: float = 2.5
    decay_rate: float = 4.0  # Exponential decay constant
    noise_level: float = 0.02  # Background noise amplitude
    seed: int | None = None  # For reproducible generation


# Default harmonic structure for guitar plate tap
DEFAULT_HARMONICS: tuple[tuple[float, float], ...] = (
    (1.0, 1.0),  # Fundamental
    (2.0, 0.6),  # 2nd harmonic
    (3.0, 0.4),  # 3rd harmonic
    (4.0, 0.2),  # 4th harmonic
    (0.73, 0.3),  # Sub-harmonic resonance (typical cross-grain mode)
    (2.12, 0.25),  # Non-integer resonance (brace coupling)
)


def generate_tap_impulse(
    config: TapImpulseConfig | None = None,
    *,
    fundamental_hz: float = 245.0,
    sample_rate: int = 48000,
    duration_s: float = 2.5,
    decay_rate: float = 4.0,
    noise_level: float = 0.02,
    seed: int | None = None,
) -> np.ndarray:
    """Generate synthetic tap impulse audio.

    Creates a realistic multi-harmonic decaying impulse that mimics
    the acoustic response of a guitar plate tap.

    Args:
        config: TapImpulseConfig (overrides other args if provided)
        fundamental_hz: Fundamental frequency in Hz (typical: 200-350 for guitar)
        sample_rate: Sample rate in Hz
        duration_s: Duration in seconds
        decay_rate: Exponential decay rate (higher = faster decay)
        noise_level: Background noise amplitude (0-1)
        seed: Random seed for reproducibility

    Returns:
        Audio signal as float32 array in [-1, 1]
    """
    if config is not None:
        fundamental_hz = config.fundamental_hz
        sample_rate = config.sample_rate
        duration_s = config.duration_s
        decay_rate = config.decay_rate
        noise_level = config.noise_level
        seed = config.seed
        harmonics = config.harmonics or DEFAULT_HARMONICS
    else:
        harmonics = DEFAULT_HARMONICS

    rng = np.random.default_rng(seed)

    n_samples = int(sample_rate * duration_s)
    t = np.arange(n_samples) / sample_rate

    # Build harmonic series
    signal = np.zeros(n_samples, dtype=np.float64)
    for freq_ratio, amplitude in harmonics:
        freq = fundamental_hz * freq_ratio
        # Slight random phase variation for realism
        phase = rng.uniform(0, 2 * np.pi)
        signal += amplitude * np.sin(2 * np.pi * freq * t + phase)

    # Apply exponential decay envelope (characteristic of impulse response)
    decay_envelope = np.exp(-decay_rate * t / duration_s)
    signal *= decay_envelope

    # Add slight noise floor
    if noise_level > 0:
        noise = noise_level * rng.standard_normal(n_samples)
        signal += noise

    # Normalize to [-1, 1] with headroom
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal * (0.9 / peak)

    return signal.astype(np.float32)


def run_demo(
    *,
    fundamental_hz: float = 245.0,
    save_artifacts: bool = True,
    output_dir: str | Path = "demo_output",
    show_results: bool = True,
    seed: int | None = 42,
) -> dict:
    """Run the complete demo workflow.

    Generates synthetic audio, analyzes it, checks quality, and optionally
    saves artifacts. Demonstrates the full Phase 1 pipeline without hardware.

    Args:
        fundamental_hz: Fundamental frequency for synthetic audio
        save_artifacts: If True, save audio.wav, analysis.json, spectrum.csv
        output_dir: Directory for saved artifacts
        show_results: If True, print results to console
        seed: Random seed for reproducibility (None for random)

    Returns:
        Dictionary with analysis results and quality verdict
    """
    from tap_tone_pi.core.analysis import analyze_tap, analysis_to_json_dict
    from tap_tone_pi.core.quality_gate import check_quality, format_verdict_summary
    from tap_tone_pi.io.wav import write_wav_mono

    sample_rate = 48000
    duration_s = 2.5

    if show_results:
        print("=" * 60)
        print("TAP TONE PI — DEMO MODE")
        print("=" * 60)
        print()
        print("Generating synthetic tap impulse...")

    # Generate synthetic audio
    audio = generate_tap_impulse(
        fundamental_hz=fundamental_hz,
        sample_rate=sample_rate,
        duration_s=duration_s,
        seed=seed,
    )

    if show_results:
        print(f"  Fundamental: {fundamental_hz} Hz")
        print(f"  Duration: {duration_s}s @ {sample_rate} Hz")
        print(f"  Samples: {len(audio)}")
        print()
        print("Analyzing...")

    # Analyze
    analysis = analyze_tap(audio, sample_rate)

    # Quality check
    verdict = check_quality(analysis, sample_rate=sample_rate, audio=audio)

    if show_results:
        print()
        print("=" * 60)
        print("ANALYSIS RESULTS")
        print("=" * 60)
        print()
        print(f"Dominant Frequency: {analysis.dominant_hz:.2f} Hz")
        print(f"Expected:           {fundamental_hz:.2f} Hz")
        print()
        print(f"Detected Peaks (top {min(5, len(analysis.peaks))}):")
        for i, peak in enumerate(analysis.peaks[:5], 1):
            print(f"  {i}. {peak.freq_hz:7.2f} Hz  (mag: {peak.magnitude:.3f})")
        print()
        print(f"Confidence: {analysis.confidence:.2%}")
        print(f"RMS Level:  {analysis.rms:.4f}")
        print(f"Clipped:    {analysis.clipped}")
        print()
        print(format_verdict_summary(verdict))
        print()

    # Build result dict
    result = {
        "demo": True,
        "seed": seed,
        "fundamental_hz_expected": fundamental_hz,
        "sample_rate": sample_rate,
        "duration_s": duration_s,
        "analysis": analysis_to_json_dict(analysis),
        "quality": verdict.to_dict(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    # Save artifacts
    if save_artifacts:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"demo_{ts}"

        # WAV
        wav_path = out_path / f"{base}_audio.wav"
        write_wav_mono(wav_path, audio, sample_rate)

        # Analysis JSON
        json_path = out_path / f"{base}_analysis.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)

        # Spectrum CSV
        csv_path = out_path / f"{base}_spectrum.csv"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("frequency_hz,magnitude\n")
            for freq, mag in zip(
                analysis.spectrum_freq_hz.tolist(),
                analysis.spectrum_mag.tolist(),
            ):
                f.write(f"{freq},{mag}\n")

        result["artifacts"] = {
            "audio": str(wav_path),
            "analysis": str(json_path),
            "spectrum": str(csv_path),
        }

        if show_results:
            print("Artifacts saved:")
            print(f"  {wav_path}")
            print(f"  {json_path}")
            print(f"  {csv_path}")
            print()

    return result


__all__ = [
    "TapImpulseConfig",
    "DEFAULT_HARMONICS",
    "generate_tap_impulse",
    "run_demo",
]
