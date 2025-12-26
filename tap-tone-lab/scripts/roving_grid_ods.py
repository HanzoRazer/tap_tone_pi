#!/usr/bin/env python3
"""
Phase 3 Prototype: Roving-Grid Operational Deflection Shape (ODS) Mapper

This script implements speaker-driven roving-microphone measurements to produce
spatial wolf-note maps. It is a RESEARCH PROTOTYPE, not production code.

Usage:
    python scripts/roving_grid_ods.py --grid grid.json --out ./phase3_session --units mm

Grid JSON format:
    {
      "points": [
        {"label": "A1", "x": 0, "y": 50},
        {"label": "A2", "x": 50, "y": 50},
        ...
      ]
    }

Coordinates:
    - Default units: mm (origin at bridge center)
    - Optional: --units in (converts to mm internally)

Output artifacts:
    session/
    ├── grid.json              # Grid definition with computed x_mm, y_mm
    ├── wolf_map.json          # Per-point localization indices
    ├── wolf_map.png           # Spatial heatmap
    └── points/
        ├── point_A1/
        │   ├── audio.wav      # 2-channel: [reference, roving]
        │   ├── analysis.json  # Transfer function, coherence
        │   └── spectrum.csv   # freq_hz, H_mag, coherence, phase_deg
        └── ...

Reference: docs/ADR-0007-phase3-roving-grid-ods.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import sounddevice as sd
from scipy.signal import coherence, csd
from scipy.io import wavfile
import matplotlib.pyplot as plt

MM_PER_INCH = 25.4

def parse_grid(path: str, units: str) -> dict:
    """Load grid JSON and convert coordinates to mm."""
    grid = json.loads(Path(path).read_text())
    scale = 1.0 if units == "mm" else MM_PER_INCH
    for p in grid["points"]:
        p["x_mm"] = p["x"] * scale
        p["y_mm"] = p["y"] * scale
    return grid


def record_2ch(fs: int, duration: float, device: int | None) -> tuple[np.ndarray, np.ndarray]:
    """Record 2-channel audio: (reference, roving)."""
    sd.default.samplerate = fs
    if device is not None:
        sd.default.device = (device, None)
    
    audio = sd.rec(int(fs * duration), channels=2, blocking=True, dtype='float32')
    return audio[:, 0], audio[:, 1]


def analyze_transfer(ref: np.ndarray, rov: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute transfer function H_ir(f) = G_ir / G_rr, coherence, phase."""
    # Coherence
    f, coh = coherence(rov, ref, fs=fs, nperseg=4096)
    
    # Cross-spectral density
    f_csd, Gir = csd(rov, ref, fs=fs, nperseg=4096)
    
    # Auto-spectral density (reference)
    _, Grr = csd(ref, ref, fs=fs, nperseg=4096)
    
    # Transfer function
    H = Gir / Grr
    H_mag = np.abs(H)
    H_phase = np.angle(H, deg=True)
    
    return f, coh, H_mag, H_phase


def localization_index(H_mag: np.ndarray) -> float:
    """Compute localization index: max / mean."""
    return float(np.max(H_mag) / np.mean(H_mag))


def persist_point(out_dir: Path, label: str, ref: np.ndarray, rov: np.ndarray, fs: int,
                  f: np.ndarray, coh: np.ndarray, H_mag: np.ndarray, H_phase: np.ndarray,
                  loc_idx: float) -> None:
    """Write per-point artifacts: audio.wav, analysis.json, spectrum.csv."""
    point_dir = out_dir / "points" / f"point_{label}"
    point_dir.mkdir(parents=True, exist_ok=True)
    
    # audio.wav (2-channel int16)
    audio_2ch = np.column_stack([ref, rov])
    audio_int16 = (audio_2ch * 32767).astype(np.int16)
    wavfile.write(point_dir / "audio.wav", fs, audio_int16)
    
    # analysis.json
    analysis = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "sample_rate": fs,
        "localization_index": loc_idx,
        "coherence_mean": float(np.mean(coh)),
        "coherence_min": float(np.min(coh)),
        "coherence_max": float(np.max(coh)),
    }
    (point_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
    
    # spectrum.csv
    with open(point_dir / "spectrum.csv", "w") as fout:
        fout.write("freq_hz,H_mag,coherence,phase_deg\n")
        for i in range(len(f)):
            fout.write(f"{f[i]:.2f},{H_mag[i]:.6f},{coh[i]:.4f},{H_phase[i]:.2f}\n")


def main():
    ap = argparse.ArgumentParser(description="Phase 3: Roving-grid ODS mapper (PROTOTYPE)")
    ap.add_argument("--grid", required=True, help="Grid JSON file (points with x, y coords)")
    ap.add_argument("--out", required=True, help="Output session directory")
    ap.add_argument("--units", choices=["mm", "in"], default="mm", help="Input coordinate units (default: mm)")
    ap.add_argument("--fs", type=int, default=48000, help="Sample rate (default: 48000)")
    ap.add_argument("--seconds", type=float, default=6.0, help="Capture duration per point (default: 6.0)")
    ap.add_argument("--device", type=int, default=None, help="Input device index (see sounddevice.query_devices())")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    
    # Load grid
    grid = parse_grid(args.grid, args.units)
    print(f"Loaded {len(grid['points'])} grid points from {args.grid}")
    
    # Copy grid with computed mm coordinates
    (out / "grid.json").write_text(json.dumps(grid, indent=2))
    
    # Roving measurement loop
    results = []
    for pt in grid["points"]:
        label = pt["label"]
        x_mm = pt["x_mm"]
        y_mm = pt["y_mm"]
        
        input(f"\n[Point {label}] Move roving mic to ({x_mm:.1f}, {y_mm:.1f}) mm and press ENTER...")
        
        print(f"Recording {args.seconds}s at {args.fs} Hz...")
        ref, rov = record_2ch(args.fs, args.seconds, args.device)
        
        print("Analyzing transfer function...")
        f, coh, H_mag, H_phase = analyze_transfer(ref, rov, args.fs)
        
        loc_idx = localization_index(H_mag)
        
        print(f"  Localization index: {loc_idx:.2f}, Coherence mean: {np.mean(coh):.3f}")
        
        persist_point(out, label, ref, rov, args.fs, f, coh, H_mag, H_phase, loc_idx)
        
        results.append({
            "label": label,
            "x_mm": x_mm,
            "y_mm": y_mm,
            "localization_index": loc_idx,
            "coherence_mean": float(np.mean(coh)),
        })
    
    # Write wolf map
    (out / "wolf_map.json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote wolf_map.json with {len(results)} points")
    
    # Plot spatial heatmap
    xs = [r["x_mm"] for r in results]
    ys = [r["y_mm"] for r in results]
    zs = [r["localization_index"] for r in results]
    
    plt.figure(figsize=(10, 8))
    sc = plt.scatter(xs, ys, c=zs, s=120, cmap="inferno", edgecolors="white", linewidth=0.5)
    plt.colorbar(sc, label="Localization Index")
    plt.title("Wolf Region Map (Phase 3 ODS)")
    plt.xlabel("x (mm)")
    plt.ylabel("y (mm)")
    plt.grid(alpha=0.3)
    plt.axis("equal")
    plt.savefig(out / "wolf_map.png", dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote wolf_map.png")
    
    print(f"\n✅ Phase 3 roving-grid session complete: {out}")


if __name__ == "__main__":
    main()
