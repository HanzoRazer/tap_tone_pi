#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any, Dict, List, Tuple

import numpy as np
from numpy.fft import rfft, rfftfreq
from scipy.signal import find_peaks

# Canonical WAV I/O
from modes._shared.wav_io import read_wav_mono

ANALYSIS_VERSION = "tap_tone_offline_v1"


def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def analyze(
    y: np.ndarray, sr: int, n_peaks: int = 6
) -> Tuple[np.ndarray, np.ndarray, List[Tuple[float, float]]]:
    """
    Analyze audio and extract top N peaks.

    Returns:
        freqs, Y (magnitude spectrum), sorted peaks [(freq_hz, amplitude), ...]
    """
    y = y.astype(np.float64)
    y = y - np.mean(y)
    N = len(y)

    window = np.hanning(N)
    Y = np.abs(rfft(window * y))
    freqs = rfftfreq(N, 1 / sr)

    # Threshold: 8% of max magnitude
    thresh = np.max(Y) * 0.08
    peaks, _ = find_peaks(Y, height=thresh, distance=20)

    # Get top N by magnitude
    idx = np.argsort(Y[peaks])[::-1][:n_peaks]
    top_peaks = sorted(
        [(float(freqs[peaks[i]]), float(Y[peaks[i]])) for i in idx],
        key=lambda x: x[0],
    )

    return freqs, Y, top_peaks


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline tap-tone analysis from WAV file")
    ap.add_argument("--wav", required=True, help="Path to WAV file")
    ap.add_argument("--peaks", type=int, default=6, help="Number of peaks to extract")
    ap.add_argument(
        "--labels",
        nargs="*",
        default=[],
        help="Peak labels (A0 T11 B11 ...). If omitted, use p1, p2, ...",
    )
    ap.add_argument("--outfile", required=True, help="Output JSON path")
    ap.add_argument(
        "--secondary",
        action="store_true",
        help="Also run optional secondary peak analysis (bandwidth/decay/Q) on a selected peak",
    )
    ap.add_argument(
        "--peak-id",
        default="p1",
        help="Peak label to characterize when --secondary is set (default: p1)",
    )
    ap.add_argument(
        "--secondary-out",
        default=None,
        help="Output JSON path for the secondary_peak_analysis_v1 artifact (default: alongside --outfile)",
    )
    a = ap.parse_args()

    # Read WAV using canonical layer
    wav_path = pathlib.Path(a.wav)
    y, meta = read_wav_mono(wav_path)
    sr = meta.sample_rate
    source_wav_sha256 = _sha256_file(wav_path)

    # Analyze
    freqs, Y, top = analyze(y, sr, a.peaks)

    # Build labels dict
    labels: Dict[str, Any] = {}
    for i, (f, amp) in enumerate(top):
        name = a.labels[i] if i < len(a.labels) else f"p{i + 1}"
        labels[name] = {"freq_hz": round(f, 2), "amp": round(float(amp), 2)}

    # Write JSON. Provenance fields are additive; the historical fields are kept
    # unchanged so existing consumers continue to work when --secondary is omitted.
    pathlib.Path(a.outfile).parent.mkdir(parents=True, exist_ok=True)
    with open(a.outfile, "w", encoding="utf-8") as f:
        json.dump(
            {
                "artifact_type": "tap_tone",
                "sample_rate": int(sr),
                "duration_s": round(len(y) / sr, 3),
                "peaks": labels,
                "source_wav": a.wav,
                "source_wav_sha256": source_wav_sha256,
                "analysis_version": ANALYSIS_VERSION,
            },
            f,
            indent=2,
        )

    print(f"Wrote {a.outfile}")

    # Optional, non-blocking secondary characterization of one selected peak. A
    # failure here never affects the primary result above.
    if a.secondary:
        _run_secondary(
            y=y,
            sr=int(sr),
            freqs=freqs,
            magnitude=Y,
            labels=labels,
            peak_id=a.peak_id,
            source_wav_sha256=source_wav_sha256,
            outfile=a.outfile,
            secondary_out=a.secondary_out,
        )


def _run_secondary(
    *,
    y: np.ndarray,
    sr: int,
    freqs: np.ndarray,
    magnitude: np.ndarray,
    labels: Dict[str, Any],
    peak_id: str,
    source_wav_sha256: str,
    outfile: str,
    secondary_out: str | None,
) -> None:
    if peak_id not in labels:
        print(
            f"[secondary] peak id {peak_id!r} not among detected peaks "
            f"{sorted(labels)}; skipping secondary analysis (primary result unaffected)."
        )
        return

    # Imported lazily so the primary path keeps its lean import surface.
    from tap_tone_pi.damping.secondary_peak_analysis import analyze_secondary_peak

    peak_freq = float(labels[peak_id]["freq_hz"])
    try:
        record = analyze_secondary_peak(
            signal=y,
            sample_rate=sr,
            freqs=freqs,
            magnitude=magnitude,
            peak_frequency_hz=peak_freq,
            peak_id=peak_id,
            source_wav_sha256=source_wav_sha256,
        )
    except Exception as exc:  # noqa: BLE001 - secondary analysis must never crash primary
        print(
            f"[secondary] analysis error ({type(exc).__name__}: {exc}); primary result unaffected."
        )
        return

    out_path = (
        pathlib.Path(secondary_out)
        if secondary_out
        else pathlib.Path(outfile).with_name("secondary_peak_analysis.json")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record.to_dict(), f, indent=2)
    print(f"Wrote {out_path} (status={record.status})")


if __name__ == "__main__":
    main()
