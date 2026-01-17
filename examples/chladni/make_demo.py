#!/usr/bin/env python3
from __future__ import annotations
"""
Tiny, hardware-free Chladni demo generator:
 - creates out/DEMO/chladni/capture.wav with two tones (148 Hz, 226 Hz)
 - creates placeholder images F0148.png and F0226.png (no image decoding needed)
"""
import os
import pathlib
import sys

# Ensure repo root is in path for imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np

from modes._shared.wav_io import write_wav_mono

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
    x = synth()
    write_wav_mono(str(OUT / "capture.wav"), x, FS)
    # 2) Placeholder PNGs (we only hash; no decoding anywhere)
    ensure_file(OUT / "F0148.png", b"PNG_PLACEHOLDER_0148")
    ensure_file(OUT / "F0226.png", b"PNG_PLACEHOLDER_0226")
    print(f"Demo written under {OUT}")


if __name__ == "__main__":
    main()
