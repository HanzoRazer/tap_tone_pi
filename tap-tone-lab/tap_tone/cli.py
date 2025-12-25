from __future__ import annotations

import argparse

from .capture import list_devices, record_audio
from .analysis import analyze_tap
from .config import CaptureConfig, AnalysisConfig
from .storage import persist_capture


def cmd_devices(_: argparse.Namespace) -> int:
    for d in list_devices():
        print(f'[{d["index"]}] {d["name"]} (in={d["max_input_channels"]}, default_sr={d["default_samplerate"]})')
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    cap_cfg = CaptureConfig(
        device=args.device,
        sample_rate=args.sample_rate,
        channels=1,
        seconds=args.seconds,
    )
    an_cfg = AnalysisConfig()

    cap = record_audio(
        device=cap_cfg.device,
        sample_rate=cap_cfg.sample_rate,
        channels=cap_cfg.channels,
        seconds=cap_cfg.seconds,
    )

    res = analyze_tap(
        cap.audio,
        cap.sample_rate,
        highpass_hz=an_cfg.highpass_hz,
        peak_min_hz=an_cfg.peak_min_hz,
        peak_max_hz=an_cfg.peak_max_hz,
        peak_min_prominence=an_cfg.peak_min_prominence,
        peak_min_spacing_hz=an_cfg.peak_min_spacing_hz,
        max_peaks=an_cfg.max_peaks,
    )

    persisted = persist_capture(
        out_dir=args.out,
        label=args.label,
        sample_rate=cap.sample_rate,
        audio=cap.audio,
        analysis=res,
    )

    print(f"[OK] Wrote: {persisted.capture_dir}")
    if res.dominant_hz is not None:
        print(f"Dominant: {res.dominant_hz:.2f} Hz")
    print(f"RMS: {res.rms:.6f}  Clipped: {res.clipped}  Confidence: {res.confidence:.2f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tap-tone", description="Tap Tone Lab CLI (Phase 1)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_dev = sub.add_parser("devices", help="List audio devices")
    p_dev.set_defaults(fn=cmd_devices)

    p_rec = sub.add_parser("record", help="Record one tap window and analyze")
    p_rec.add_argument("--device", type=int, default=None, help="Input device index")
    p_rec.add_argument("--sample-rate", type=int, default=48000)
    p_rec.add_argument("--seconds", type=float, default=2.5)
    p_rec.add_argument("--out", type=str, required=True)
    p_rec.add_argument("--label", type=str, default=None)
    p_rec.set_defaults(fn=cmd_record)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(args.fn(args))
