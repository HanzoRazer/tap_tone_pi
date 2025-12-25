#!/usr/bin/env python3
"""
repeatability_run.py

Runs N Phase-1 captures and reports repeatability metrics.

Outputs:
- takes.json (summary + per-take results)
- individual capture_<ts>/ folders via tap_tone.storage.persist_capture
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from tap_tone.capture import record_audio
from tap_tone.analysis import analyze_tap
from tap_tone.config import CaptureConfig, AnalysisConfig
from tap_tone.storage import persist_capture


def _mad(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = sorted(xs)[len(xs) // 2]
    dev = [abs(x - m) for x in xs]
    return sorted(dev)[len(dev) // 2]


def main() -> None:
    ap = argparse.ArgumentParser(description="Repeatability run (Phase 1).")
    ap.add_argument("--device", type=int, default=None)
    ap.add_argument("--sample-rate", type=int, default=48000)
    ap.add_argument("--seconds", type=float, default=2.5)
    ap.add_argument("--takes", type=int, default=10)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--label", type=str, default="repeatability")
    ap.add_argument("--pause", type=float, default=0.5, help="Seconds pause between takes")
    args = ap.parse_args()

    out_root = Path(args.out).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    cap_cfg = CaptureConfig(device=args.device, sample_rate=args.sample_rate, channels=1, seconds=args.seconds)
    an_cfg = AnalysisConfig()

    results: list[dict[str, Any]] = []
    doms: list[float] = []
    confs: list[float] = []
    clipped_count = 0

    import time

    for i in range(1, args.takes + 1):
        print(f"[{i}/{args.takes}] Recording...")
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
            out_dir=str(out_root),
            label=f"{args.label}_take_{i:03d}",
            sample_rate=cap.sample_rate,
            audio=cap.audio,
            analysis=res,
        )

        r = {
            "take": i,
            "capture_dir": str(persisted.capture_dir),
            "dominant_hz": res.dominant_hz,
            "rms": res.rms,
            "clipped": res.clipped,
            "confidence": res.confidence,
            "top_peaks_hz": [p.freq_hz for p in res.peaks[:5]],
        }
        results.append(r)

        if res.dominant_hz is not None:
            doms.append(float(res.dominant_hz))
        confs.append(float(res.confidence))
        if res.clipped:
            clipped_count += 1

        print(
            f"  dominant={res.dominant_hz} Hz  rms={res.rms:.6f} clipped={res.clipped} conf={res.confidence:.2f}"
        )
        time.sleep(max(0.0, float(args.pause)))

    summary: dict[str, Any] = {
        "takes": args.takes,
        "device": args.device,
        "sample_rate": args.sample_rate,
        "seconds": args.seconds,
        "label": args.label,
        "dominant_hz": {
            "count": len(doms),
            "mean": mean(doms) if doms else None,
            "stdev": pstdev(doms) if len(doms) > 1 else 0.0,
            "mad": _mad(doms) if doms else None,
            "min": min(doms) if doms else None,
            "max": max(doms) if doms else None,
        },
        "confidence": {
            "mean": mean(confs) if confs else None,
            "min": min(confs) if confs else None,
            "max": max(confs) if confs else None,
        },
        "clipping": {"count": clipped_count, "rate": clipped_count / float(args.takes)},
    }

    out_json = out_root / "takes.json"
    out_json.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")

    print("")
    print("[OK] Repeatability summary")
    print(json.dumps(summary, indent=2))
    print(f"[OK] Wrote {out_json}")


if __name__ == "__main__":
    main()
