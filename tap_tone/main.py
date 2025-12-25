from __future__ import annotations

import argparse
import sys

from .config import CaptureConfig, AnalysisConfig
from .capture import list_devices, record_audio
from .analysis import analyze_tap
from .storage import persist_capture
from .ui_simple import print_summary

def cmd_devices(_: argparse.Namespace) -> int:
    devs = list_devices()
    for d in devs:
        print(f'[{d["index"]}] {d["name"]} (in={d["max_input_channels"]}, out={d["max_output_channels"]})')
    return 0

def cmd_record(args: argparse.Namespace) -> int:
    cap_cfg = CaptureConfig(
        device=args.device,
        sample_rate=args.sample_rate,
        channels=args.channels,
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

    print_summary(args.label, res)

    persisted = persist_capture(
        out_dir=args.out,
        label=args.label,
        sample_rate=cap.sample_rate,
        audio=cap.audio,
        analysis=res,
    )
    print(f"Wrote: {persisted.capture_dir}")
    return 0

def cmd_live(args: argparse.Namespace) -> int:
    print("Live mode: press Ctrl+C to stop. Tap, wait, tap...")
    i = 0
    try:
        while True:
            i += 1
            label = args.label or f"live_{i:03d}"
            ns = argparse.Namespace(
                device=args.device,
                sample_rate=args.sample_rate,
                channels=args.channels,
                seconds=args.seconds,
                out=args.out,
                label=label,
            )
            rc = cmd_record(ns)
            if rc != 0:
                return rc
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tap-tone", description="Offline tap tone analyzer")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_dev = sub.add_parser("devices", help="List audio devices")
    p_dev.set_defaults(fn=cmd_devices)

    p_rec = sub.add_parser("record", help="Record one window and analyze")
    p_rec.add_argument("--device", type=int, default=None, help="Input device index (see devices)")
    p_rec.add_argument("--sample-rate", type=int, default=48000)
    p_rec.add_argument("--channels", type=int, default=1)
    p_rec.add_argument("--seconds", type=float, default=2.5)
    p_rec.add_argument("--out", type=str, required=True, help="Output directory root")
    p_rec.add_argument("--label", type=str, default=None, help="Tap point label")
    p_rec.set_defaults(fn=cmd_record)

    p_live = sub.add_parser("live", help="Loop record+analyze")
    p_live.add_argument("--device", type=int, default=None)
    p_live.add_argument("--sample-rate", type=int, default=48000)
    p_live.add_argument("--channels", type=int, default=1)
    p_live.add_argument("--seconds", type=float, default=2.5)
    p_live.add_argument("--out", type=str, required=True)
    p_live.add_argument("--label", type=str, default=None)
    p_live.set_defaults(fn=cmd_live)

    return p

def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    rc = args.fn(args)
    raise SystemExit(rc)

if __name__ == "__main__":
    main()
