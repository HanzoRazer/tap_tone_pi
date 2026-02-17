"""
CLI commands for signal generation.

Usage:
    ttp generate sine --freq 1000 --duration 1.0 --output test.wav
    ttp generate sweep --start 20 --end 20000 --duration 5.0 --output sweep.wav
    ttp generate noise --type pink --duration 10.0 --output pink.wav
    ttp generate impulse --output impulse.wav
    ttp generate multitone --freqs 100,1000,10000 --output multi.wav
    ttp generate comb --fundamental 110 --harmonics 20 --output comb.wav
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_generate_sine(args) -> int:
    """Generate sine wave."""
    from tap_tone_pi.signal_gen import generate_sine, write_wav

    print(f"Generating {args.frequency:.1f} Hz sine wave...")
    print(f"  Duration: {args.duration:.2f} s")
    print(f"  Sample rate: {args.sample_rate} Hz")
    print(f"  Amplitude: {args.amplitude:.2f}")

    signal = generate_sine(
        frequency_hz=args.frequency,
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=args.amplitude,
        phase_deg=args.phase,
    )

    output_path = write_wav(
        signal,
        args.output,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )

    print(f"Written: {output_path}")
    print(f"  Samples: {len(signal)}")
    return 0


def cmd_generate_sweep(args) -> int:
    """Generate frequency sweep."""
    from tap_tone_pi.signal_gen import generate_sweep, write_wav, SweepType

    sweep_type = SweepType(args.type)
    print(f"Generating {sweep_type.value} sweep {args.start}-{args.end} Hz...")
    print(f"  Duration: {args.duration:.2f} s")
    print(f"  Sample rate: {args.sample_rate} Hz")

    signal = generate_sweep(
        start_freq_hz=args.start,
        end_freq_hz=args.end,
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=args.amplitude,
        sweep_type=sweep_type,
    )

    output_path = write_wav(
        signal,
        args.output,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )

    print(f"Written: {output_path}")
    print(f"  Samples: {len(signal)}")
    return 0


def cmd_generate_noise(args) -> int:
    """Generate noise signal."""
    from tap_tone_pi.signal_gen import generate_noise, write_wav, NoiseType

    noise_type = NoiseType(args.type)
    print(f"Generating {noise_type.value} noise...")
    print(f"  Duration: {args.duration:.2f} s")
    print(f"  Sample rate: {args.sample_rate} Hz")
    print(f"  RMS amplitude: {args.amplitude:.2f}")

    signal = generate_noise(
        noise_type=noise_type,
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=args.amplitude,
        seed=args.seed,
        highpass_hz=args.highpass,
        lowpass_hz=args.lowpass,
    )

    output_path = write_wav(
        signal,
        args.output,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )

    print(f"Written: {output_path}")
    print(f"  Samples: {len(signal)}")
    return 0


def cmd_generate_impulse(args) -> int:
    """Generate impulse signal."""
    from tap_tone_pi.signal_gen import generate_impulse, write_wav

    print(f"Generating impulse at {args.time:.1f} ms...")
    print(f"  Duration: {args.duration:.2f} s")
    print(f"  Sample rate: {args.sample_rate} Hz")

    signal = generate_impulse(
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=args.amplitude,
        impulse_time_ms=args.time,
    )

    output_path = write_wav(
        signal,
        args.output,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )

    print(f"Written: {output_path}")
    print(f"  Samples: {len(signal)}")
    return 0


def cmd_generate_multitone(args) -> int:
    """Generate multitone signal."""
    from tap_tone_pi.signal_gen import generate_multitone, write_wav

    # Parse comma-separated frequencies
    frequencies = [float(f.strip()) for f in args.freqs.split(",")]

    print(f"Generating multitone with {len(frequencies)} frequencies...")
    print(f"  Frequencies: {frequencies}")
    print(f"  Duration: {args.duration:.2f} s")
    print(f"  Sample rate: {args.sample_rate} Hz")

    signal = generate_multitone(
        frequencies_hz=frequencies,
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=args.amplitude,
        random_phases=args.random_phases,
    )

    output_path = write_wav(
        signal,
        args.output,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )

    print(f"Written: {output_path}")
    print(f"  Samples: {len(signal)}")
    return 0


def cmd_generate_comb(args) -> int:
    """Generate comb signal (fundamental + harmonics)."""
    from tap_tone_pi.signal_gen import generate_comb, write_wav

    print(f"Generating comb with {args.harmonics} harmonics...")
    print(f"  Fundamental: {args.fundamental:.1f} Hz")
    print(f"  Rolloff: {args.rolloff:.1f} dB/octave")
    print(f"  Duration: {args.duration:.2f} s")

    signal = generate_comb(
        fundamental_hz=args.fundamental,
        n_harmonics=args.harmonics,
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=args.amplitude,
        rolloff_db_per_octave=args.rolloff,
    )

    output_path = write_wav(
        signal,
        args.output,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )

    print(f"Written: {output_path}")
    print(f"  Samples: {len(signal)}")
    return 0


def add_generate_subcommand(subparsers) -> None:
    """Add the generate subcommand and its sub-subcommands."""
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate test signals",
        description="Generate various test signals for calibration and testing.",
    )

    gen_sub = gen_parser.add_subparsers(dest="gen_cmd", help="Signal type")

    # Common arguments
    def add_common_args(parser, default_output: str):
        parser.add_argument(
            "-o", "--output",
            type=str,
            default=default_output,
            help=f"Output WAV file (default: {default_output})",
        )
        parser.add_argument(
            "-d", "--duration",
            type=float,
            default=1.0,
            help="Duration in seconds (default: 1.0)",
        )
        parser.add_argument(
            "-r", "--sample-rate",
            type=int,
            default=48000,
            help="Sample rate in Hz (default: 48000)",
        )
        parser.add_argument(
            "-a", "--amplitude",
            type=float,
            default=0.8,
            help="Peak amplitude 0-1 (default: 0.8)",
        )
        parser.add_argument(
            "--bit-depth",
            type=int,
            choices=[16, 24],
            default=16,
            help="Bit depth (default: 16)",
        )

    # Sine subcommand
    sine_parser = gen_sub.add_parser(
        "sine",
        help="Generate sine wave",
    )
    add_common_args(sine_parser, "sine.wav")
    sine_parser.add_argument(
        "-f", "--frequency",
        type=float,
        default=1000.0,
        help="Frequency in Hz (default: 1000)",
    )
    sine_parser.add_argument(
        "--phase",
        type=float,
        default=0.0,
        help="Starting phase in degrees (default: 0)",
    )
    sine_parser.set_defaults(func=cmd_generate_sine)

    # Sweep subcommand
    sweep_parser = gen_sub.add_parser(
        "sweep",
        help="Generate frequency sweep",
    )
    add_common_args(sweep_parser, "sweep.wav")
    sweep_parser.set_defaults(duration=5.0)  # Longer default for sweeps
    sweep_parser.add_argument(
        "--start",
        type=float,
        default=20.0,
        help="Start frequency in Hz (default: 20)",
    )
    sweep_parser.add_argument(
        "--end",
        type=float,
        default=20000.0,
        help="End frequency in Hz (default: 20000)",
    )
    sweep_parser.add_argument(
        "-t", "--type",
        choices=["linear", "logarithmic", "chirp"],
        default="logarithmic",
        help="Sweep type (default: logarithmic)",
    )
    sweep_parser.set_defaults(func=cmd_generate_sweep)

    # Noise subcommand
    noise_parser = gen_sub.add_parser(
        "noise",
        help="Generate noise signal",
    )
    add_common_args(noise_parser, "noise.wav")
    noise_parser.set_defaults(amplitude=0.5)  # Lower default for noise
    noise_parser.add_argument(
        "-t", "--type",
        choices=["white", "pink", "brown"],
        default="white",
        help="Noise type (default: white)",
    )
    noise_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    noise_parser.add_argument(
        "--highpass",
        type=float,
        default=None,
        help="High-pass filter frequency in Hz",
    )
    noise_parser.add_argument(
        "--lowpass",
        type=float,
        default=None,
        help="Low-pass filter frequency in Hz",
    )
    noise_parser.set_defaults(func=cmd_generate_noise)

    # Impulse subcommand
    impulse_parser = gen_sub.add_parser(
        "impulse",
        help="Generate impulse signal",
    )
    add_common_args(impulse_parser, "impulse.wav")
    impulse_parser.add_argument(
        "--time",
        type=float,
        default=100.0,
        help="Impulse time in ms from start (default: 100)",
    )
    impulse_parser.set_defaults(func=cmd_generate_impulse)

    # Multitone subcommand
    multi_parser = gen_sub.add_parser(
        "multitone",
        help="Generate multitone signal",
    )
    add_common_args(multi_parser, "multitone.wav")
    multi_parser.add_argument(
        "--freqs",
        type=str,
        default="100,1000,10000",
        help="Comma-separated frequencies in Hz (default: 100,1000,10000)",
    )
    multi_parser.add_argument(
        "--random-phases",
        action="store_true",
        help="Use random phases to reduce crest factor",
    )
    multi_parser.set_defaults(func=cmd_generate_multitone)

    # Comb subcommand
    comb_parser = gen_sub.add_parser(
        "comb",
        help="Generate comb signal (harmonics)",
    )
    add_common_args(comb_parser, "comb.wav")
    comb_parser.add_argument(
        "-f", "--fundamental",
        type=float,
        default=110.0,
        help="Fundamental frequency in Hz (default: 110)",
    )
    comb_parser.add_argument(
        "-n", "--harmonics",
        type=int,
        default=20,
        help="Number of harmonics (default: 20)",
    )
    comb_parser.add_argument(
        "--rolloff",
        type=float,
        default=0.0,
        help="Amplitude rolloff in dB/octave (default: 0, flat)",
    )
    comb_parser.set_defaults(func=cmd_generate_comb)

    # Set handler for generate without subcommand
    def show_generate_help(args):
        gen_parser.print_help()
        return 1

    gen_parser.set_defaults(func=show_generate_help)
