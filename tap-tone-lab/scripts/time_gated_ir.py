#!/usr/bin/env python3
"""
Time-Gated Impulse Response Extension for Tap Tone Lab

This script extends the roving-grid workflow with time-domain impulse response
analysis using deconvolution and time-gating to suppress room reflections.

Workflow:
1. Capture excitation signal (chirp) and response (reference + roving mics)
2. Deconvolve response by excitation → impulse response h(t)
3. Apply time gate to h(t) → h_g(t) (suppress late reflections)
4. FFT of h_g(t) → frequency response with reduced room contamination

Output artifacts:
    bundle/
    ├── excitation.json           # Excitation signal parameters
    ├── impulse/
    │   ├── ir_ref.npy            # Reference channel impulse response
    │   ├── ir_roving.npy         # Roving channel impulse response
    │   ├── ir_gated_ref.npy      # Time-gated reference IR
    │   ├── ir_gated_roving.npy   # Time-gated roving IR
    │   ├── gated_spectrum_ref.csv   # Freq response from gated IR (ref)
    │   └── gated_spectrum_roving.csv # Freq response from gated IR (roving)
    └── plots/
        ├── impulse_response.png  # Time-domain IR plot
        └── gated_spectrum.png    # Frequency response comparison

Usage:
    # Generate and save excitation chirp
    python scripts/time_gated_ir.py generate-chirp --out ./chirp.wav --fs 48000 --duration 3.0

    # Process captured audio with time-gating
    python scripts/time_gated_ir.py process \
        --audio ./capture/audio.wav \
        --excitation ./chirp.wav \
        --out ./capture \
        --gate-start-ms 5.0 \
        --gate-end-ms 100.0 \
        --window tukey \
        --write-plots

Reference: Extends Phase 3 roving-grid methodology (ADR-0007) with improved
frequency response estimation via time-domain gating.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.signal import chirp as generate_chirp_signal, correlate, tukey, hann, windows
from scipy.io import wavfile
from scipy.fft import rfft, rfftfreq
import matplotlib.pyplot as plt


def generate_chirp(fs: int, duration: float, f0: float, f1: float) -> np.ndarray:
    """Generate logarithmic chirp signal."""
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    signal = generate_chirp_signal(t, f0, duration, f1, method='logarithmic', phi=-90)
    return signal.astype(np.float32)


def deconvolve_ir(response: np.ndarray, excitation: np.ndarray) -> np.ndarray:
    """
    Deconvolve response by excitation using cross-correlation.
    Returns impulse response h(t).
    """
    # Normalize excitation energy
    exc_energy = np.sum(excitation ** 2)
    
    # Cross-correlate response with excitation
    ir = correlate(response, excitation, mode='same', method='fft')
    
    # Normalize by excitation energy
    ir = ir / exc_energy
    
    return ir


def apply_time_gate(ir: np.ndarray, fs: int, start_ms: float, end_ms: float, 
                    window_type: str = 'tukey') -> np.ndarray:
    """
    Apply time gate to impulse response to suppress late reflections.
    
    Args:
        ir: Impulse response array
        fs: Sample rate (Hz)
        start_ms: Gate start time (ms after peak)
        end_ms: Gate end time (ms after peak)
        window_type: 'tukey', 'hann', or 'rectangular'
    
    Returns:
        Time-gated impulse response
    """
    # Find peak (likely direct path arrival)
    peak_idx = np.argmax(np.abs(ir))
    
    # Convert ms to samples
    start_samples = int(start_ms * fs / 1000)
    end_samples = int(end_ms * fs / 1000)
    
    # Gate indices
    gate_start = max(0, peak_idx - start_samples)
    gate_end = min(len(ir), peak_idx + end_samples)
    gate_len = gate_end - gate_start
    
    # Create window
    if window_type == 'tukey':
        win = tukey(gate_len, alpha=0.25)
    elif window_type == 'hann':
        win = hann(gate_len)
    elif window_type == 'rectangular':
        win = np.ones(gate_len)
    else:
        raise ValueError(f"Unknown window type: {window_type}")
    
    # Apply gate
    ir_gated = np.zeros_like(ir)
    ir_gated[gate_start:gate_end] = ir[gate_start:gate_end] * win
    
    return ir_gated


def ir_to_spectrum(ir: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Convert impulse response to frequency spectrum via FFT."""
    spectrum = rfft(ir)
    freqs = rfftfreq(len(ir), 1/fs)
    magnitude = np.abs(spectrum)
    
    # Normalize to 0..1 range
    if np.max(magnitude) > 0:
        magnitude = magnitude / np.max(magnitude)
    
    return freqs, magnitude


def persist_ir_artifacts(out_dir: Path, ir_ref: np.ndarray, ir_roving: np.ndarray,
                        ir_gated_ref: np.ndarray, ir_gated_roving: np.ndarray,
                        fs: int, gate_params: dict) -> None:
    """Write impulse response artifacts to disk."""
    impulse_dir = out_dir / "impulse"
    impulse_dir.mkdir(parents=True, exist_ok=True)
    
    # Save raw IRs
    np.save(impulse_dir / "ir_ref.npy", ir_ref)
    np.save(impulse_dir / "ir_roving.npy", ir_roving)
    
    # Save gated IRs
    np.save(impulse_dir / "ir_gated_ref.npy", ir_gated_ref)
    np.save(impulse_dir / "ir_gated_roving.npy", ir_gated_roving)
    
    # Compute and save spectra from gated IRs
    freqs_ref, mag_ref = ir_to_spectrum(ir_gated_ref, fs)
    freqs_rov, mag_rov = ir_to_spectrum(ir_gated_roving, fs)
    
    # CSV outputs
    with open(impulse_dir / "gated_spectrum_ref.csv", "w") as f:
        f.write("freq_hz,magnitude\n")
        for freq, mag in zip(freqs_ref, mag_ref):
            f.write(f"{freq:.2f},{mag:.6f}\n")
    
    with open(impulse_dir / "gated_spectrum_roving.csv", "w") as f:
        f.write("freq_hz,magnitude\n")
        for freq, mag in zip(freqs_rov, mag_rov):
            f.write(f"{freq:.2f},{mag:.6f}\n")
    
    # Save gate parameters
    gate_metadata = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "sample_rate": fs,
        "gate_start_ms": gate_params["start_ms"],
        "gate_end_ms": gate_params["end_ms"],
        "window_type": gate_params["window_type"],
    }
    (impulse_dir / "gate_params.json").write_text(json.dumps(gate_metadata, indent=2))


def plot_ir_and_spectrum(out_dir: Path, ir_ref: np.ndarray, ir_roving: np.ndarray,
                         ir_gated_ref: np.ndarray, ir_gated_roving: np.ndarray,
                         fs: int, max_hz: int = 2000) -> None:
    """Generate diagnostic plots for impulse response and gated spectrum."""
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    # Time vector
    t = np.arange(len(ir_ref)) / fs * 1000  # ms
    
    # Plot impulse responses
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), dpi=160)
    
    # Reference channel
    axes[0].plot(t, ir_ref, label='Raw IR', alpha=0.6, linewidth=0.8)
    axes[0].plot(t, ir_gated_ref, label='Gated IR', linewidth=1.2)
    axes[0].set_xlabel('Time (ms)')
    axes[0].set_ylabel('Amplitude')
    axes[0].set_title('Reference Channel Impulse Response')
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    
    # Roving channel
    axes[1].plot(t, ir_roving, label='Raw IR', alpha=0.6, linewidth=0.8)
    axes[1].plot(t, ir_gated_roving, label='Gated IR', linewidth=1.2)
    axes[1].set_xlabel('Time (ms)')
    axes[1].set_ylabel('Amplitude')
    axes[1].set_title('Roving Channel Impulse Response')
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(plots_dir / "impulse_response.png", dpi=160, bbox_inches='tight')
    plt.close()
    
    # Plot gated spectra
    freqs_ref, mag_ref = ir_to_spectrum(ir_gated_ref, fs)
    freqs_rov, mag_rov = ir_to_spectrum(ir_gated_roving, fs)
    
    # Limit to max_hz
    mask_ref = freqs_ref <= max_hz
    mask_rov = freqs_rov <= max_hz
    
    fig, ax = plt.subplots(figsize=(10, 4), dpi=160)
    ax.plot(freqs_ref[mask_ref], mag_ref[mask_ref], label='Reference', linewidth=1.2)
    ax.plot(freqs_rov[mask_rov], mag_rov[mask_rov], label='Roving', linewidth=1.2, alpha=0.8)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Normalized Magnitude')
    ax.set_title('Frequency Response from Gated Impulse Response')
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / "gated_spectrum.png", dpi=160, bbox_inches='tight')
    plt.close()


def cmd_generate_chirp(args: argparse.Namespace) -> int:
    """Generate and save logarithmic chirp excitation signal."""
    signal = generate_chirp(args.fs, args.duration, args.f0, args.f1)
    
    # Save as WAV (int16)
    signal_int16 = (signal * 32767).astype(np.int16)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(out_path, args.fs, signal_int16)
    
    # Save metadata
    meta = {
        "type": "log_chirp",
        "sample_rate": args.fs,
        "duration_s": args.duration,
        "freq_range_hz": [args.f0, args.f1],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = out_path.parent / "excitation.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    
    print(f"✅ Generated chirp: {out_path}")
    print(f"   Metadata: {meta_path}")
    print(f"   {args.f0}-{args.f1} Hz, {args.duration}s @ {args.fs} Hz")
    
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    """Process captured audio with time-gated impulse response analysis."""
    audio_path = Path(args.audio)
    exc_path = Path(args.excitation)
    out_dir = Path(args.out)
    
    # Load audio (2-channel: reference, roving)
    fs_audio, audio = wavfile.read(audio_path)
    if audio.ndim != 2 or audio.shape[1] != 2:
        print(f"❌ Audio must be 2-channel (reference, roving). Got shape: {audio.shape}")
        return 1
    
    audio = audio.astype(np.float32) / 32767.0
    ref_response = audio[:, 0]
    rov_response = audio[:, 1]
    
    # Load excitation
    fs_exc, excitation = wavfile.read(exc_path)
    if fs_exc != fs_audio:
        print(f"❌ Sample rate mismatch: audio={fs_audio} Hz, excitation={fs_exc} Hz")
        return 1
    
    excitation = excitation.astype(np.float32)
    if excitation.ndim > 1:
        excitation = excitation[:, 0]  # Use first channel if stereo
    excitation = excitation / 32767.0 if np.max(np.abs(excitation)) > 1.0 else excitation
    
    print(f"Processing audio: {audio_path.name}")
    print(f"  Sample rate: {fs_audio} Hz")
    print(f"  Duration: {len(ref_response) / fs_audio:.2f}s")
    print(f"  Excitation: {exc_path.name} ({len(excitation) / fs_exc:.2f}s)")
    
    # Deconvolve to get impulse responses
    print("Deconvolving...")
    ir_ref = deconvolve_ir(ref_response, excitation)
    ir_roving = deconvolve_ir(rov_response, excitation)
    
    # Apply time gate
    print(f"Applying time gate: {args.gate_start_ms}-{args.gate_end_ms} ms ({args.window} window)")
    ir_gated_ref = apply_time_gate(ir_ref, fs_audio, args.gate_start_ms, args.gate_end_ms, args.window)
    ir_gated_roving = apply_time_gate(ir_roving, fs_audio, args.gate_start_ms, args.gate_end_ms, args.window)
    
    # Persist artifacts
    gate_params = {
        "start_ms": args.gate_start_ms,
        "end_ms": args.gate_end_ms,
        "window_type": args.window,
    }
    persist_ir_artifacts(out_dir, ir_ref, ir_roving, ir_gated_ref, ir_gated_roving, fs_audio, gate_params)
    
    print(f"✅ Wrote impulse artifacts to {out_dir / 'impulse'}")
    
    # Generate plots if requested
    if args.write_plots:
        print("Generating plots...")
        plot_ir_and_spectrum(out_dir, ir_ref, ir_roving, ir_gated_ref, ir_gated_roving, 
                            fs_audio, max_hz=args.plot_max_hz)
        print(f"✅ Wrote plots to {out_dir / 'plots'}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Time-gated impulse response analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # generate-chirp command
    gen = subparsers.add_parser("generate-chirp", help="Generate logarithmic chirp excitation")
    gen.add_argument("--out", required=True, help="Output WAV path")
    gen.add_argument("--fs", type=int, default=48000, help="Sample rate (default: 48000)")
    gen.add_argument("--duration", type=float, default=3.0, help="Duration in seconds (default: 3.0)")
    gen.add_argument("--f0", type=float, default=30, help="Start frequency (default: 30 Hz)")
    gen.add_argument("--f1", type=float, default=2000, help="End frequency (default: 2000 Hz)")
    gen.set_defaults(func=cmd_generate_chirp)
    
    # process command
    proc = subparsers.add_parser("process", help="Process audio with time-gated IR analysis")
    proc.add_argument("--audio", required=True, help="Input 2-channel audio WAV (reference, roving)")
    proc.add_argument("--excitation", required=True, help="Excitation chirp WAV")
    proc.add_argument("--out", required=True, help="Output directory for artifacts")
    proc.add_argument("--gate-start-ms", type=float, default=5.0, help="Gate start (ms before peak, default: 5.0)")
    proc.add_argument("--gate-end-ms", type=float, default=100.0, help="Gate end (ms after peak, default: 100.0)")
    proc.add_argument("--window", choices=["tukey", "hann", "rectangular"], default="tukey", 
                     help="Gate window type (default: tukey)")
    proc.add_argument("--write-plots", action="store_true", help="Generate diagnostic plots")
    proc.add_argument("--plot-max-hz", type=int, default=2000, help="Max frequency for plots (default: 2000)")
    proc.set_defaults(func=cmd_process)
    
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
