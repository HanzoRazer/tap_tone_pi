#!/usr/bin/env python3
"""
Tiny, hardware-free Chladni demo generator:
 - creates out/DEMO/chladni/capture.wav with two tones (148 Hz, 226 Hz)
 - creates placeholder images F0148.png and F0226.png (no image decoding needed)
 - runs peaks_from_wav.py and index_patterns.py
 - appends all artifacts to manifest.json
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

# Ensure repo root is in path for imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np

from modes._shared.wav_io import write_wav_mono
from modes.chladni.index_patterns import append_chladni_to_run_manifest

OUT = pathlib.Path("out/DEMO/chladni")
FS = 48000
DUR = 2.0
FREQS = [148.0, 226.0]


def synth():
    n = int(FS * DUR)
    t = np.arange(n, dtype=np.float32) / FS
    x = np.zeros_like(t)
    for f in FREQS:
        x += 0.2 * np.sin(2 * np.pi * f * t)
    # light fade to avoid clicks
    win = np.hanning(n)
    x = (x * win).astype(np.float32)
    return x / max(1.0, np.max(np.abs(x)))


def ensure_file(path: pathlib.Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) WAV
    wav_path = OUT / "capture.wav"
    x = synth()
    write_wav_mono(str(wav_path), x, FS)
    print(f"Wrote {wav_path}")

    # 2) Placeholder PNGs (we only hash; no decoding anywhere)
    image_paths = [OUT / "F0148.png", OUT / "F0226.png"]
    ensure_file(image_paths[0], b"PNG_PLACEHOLDER_0148")
    ensure_file(image_paths[1], b"PNG_PLACEHOLDER_0226")
    print(f"Wrote placeholder images: {[p.name for p in image_paths]}")

    # 3) Extract peaks
    peaks_path = OUT / "peaks.json"
    subprocess.run([
        sys.executable, "-m", "modes.chladni.peaks_from_wav",
        "--wav", str(wav_path),
        "--out", str(peaks_path),
        "--min-hz", "50",
        "--max-hz", "500",
    ], check=True)
    print(f"Wrote {peaks_path}")

    # 4) Index patterns
    chladni_run_path = OUT / "chladni_run.json"
    subprocess.run([
        sys.executable, "-m", "modes.chladni.index_patterns",
        "--peaks-json", str(peaks_path),
        "--images", str(image_paths[0]), str(image_paths[1]),
        "--plate-id", "DEMO_PLATE",
        "--tempC", "22.0",
        "--rh", "45.0",
        "--out", str(chladni_run_path),
    ], check=True)
    print(f"Wrote {chladni_run_path}")

    # 5) Append all artifacts to manifest
    manifest_path = append_chladni_to_run_manifest(
        OUT,
        wav_path=wav_path,
        peaks_json_path=peaks_path,
        image_paths=image_paths,
        chladni_run_json_path=chladni_run_path,
    )
    print(f"Updated manifest: {manifest_path}")

    # Show manifest contents
    with open(manifest_path) as f:
        manifest = json.load(f)
    print(f"\nManifest artifacts ({len(manifest.get('artifacts', []))}):")
    for art in manifest.get("artifacts", []):
        print(f"  - {art['path']} ({art['artifact_type']})")

    print("\nDemo complete!")


if __name__ == "__main__":
    main()
