#!/usr/bin/env python3
"""
Chladni v1 — index (facts only)

Associates image files to frequencies (by filename tag like F0148.png) and
writes a chladni_run.json with environment + provenance.

Frequency Mismatch Policy (G.2):
  - Warn + keep if delta_hz > 0
  - FAIL if delta_hz > CHLADNI_FREQ_TOLERANCE_HZ (default 5.0 Hz)

Usage:
  python modes/chladni/index_patterns.py \
    --peaks-json out/RUN/chladni/peaks.json \
    --images out/RUN/chladni/F0148.png out/RUN/chladni/F0226.png \
    --plate-id J45_TOP_2025_12_31_A \
    --tempC 22.0 --rh 45.0 \
    --out out/RUN/chladni/chladni_run.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import time
from datetime import datetime, timezone
from typing import Iterable, List

# Frequency mismatch tolerance (Hz) - configurable via environment
CHLADNI_FREQ_TOLERANCE_HZ = float(os.getenv("CHLADNI_FREQ_TOLERANCE_HZ", "5.0"))


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: pathlib.Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_chladni_to_run_manifest(
    run_dir: str | pathlib.Path,
    *,
    wav_path: str | pathlib.Path,
    peaks_json_path: str | pathlib.Path,
    image_paths: Iterable[str | pathlib.Path],
    chladni_run_json_path: str | pathlib.Path,
    manifest_name: str = "manifest.json",
) -> pathlib.Path:
    """
    Append Chladni artifacts to the run-level manifest out/<RUN_ID>/manifest.json.

    Artifacts added (with SHA-256):
      - WAV microphone capture
      - peaks JSON (from peaks_from_wav)
      - each Chladni PNG image
      - chladni_run.json (the run index)

    If modes/_shared/emit_manifest.py exists and provides append/save utilities,
    those are used. Otherwise, this function maintains a minimal 'measurement_manifest'
    document with fields:
      { schema_id, schema_version, created_utc, artifacts: [ {path, sha256, artifact_type} ] }

    Returns:
      Path to the manifest.json that was written.
    """
    run_dir = pathlib.Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / manifest_name

    # Build entries (relative paths, deterministic order).
    # Artifact types are descriptive but remain "facts-only".
    def rel(p: str | pathlib.Path) -> str:
        return os.path.relpath(pathlib.Path(p), start=run_dir)

    images: List[pathlib.Path] = [pathlib.Path(p) for p in image_paths]
    entries = [
        {"path": rel(wav_path),             "sha256": _sha256_file(pathlib.Path(wav_path)),             "artifact_type": "chladni_wav"},
        {"path": rel(peaks_json_path),      "sha256": _sha256_file(pathlib.Path(peaks_json_path)),      "artifact_type": "chladni_peaks"},
        *[
            {"path": rel(ip),               "sha256": _sha256_file(ip),                                  "artifact_type": "chladni_image"}
            for ip in sorted(images, key=lambda x: x.name.lower())
        ],
        {"path": rel(chladni_run_json_path),"sha256": _sha256_file(pathlib.Path(chladni_run_json_path)),"artifact_type": "chladni_run"},
    ]

    # Try to use the shared manifest utility if it exists.
    try:
        from modes._shared import emit_manifest  # type: ignore

        # Load or initialize via shared utility if available.
        if manifest_path.exists():
            doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            doc = emit_manifest.new_manifest()  # expected to set schema_id/version/created_utc
        # Append entries without duplication.
        for e in entries:
            emit_manifest.append_entry(doc, e["path"], e["sha256"], e.get("artifact_type"))
        emit_manifest.save_manifest(doc, manifest_path)
        return manifest_path

    except Exception:
        # Fallback: minimal manifest writer (no dependency on emit_manifest).
        if manifest_path.exists():
            try:
                doc = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                doc = {}
        else:
            doc = {}

        # Initialize minimal manifest if missing.
        if not isinstance(doc, dict) or "schema_id" not in doc:
            doc = {
                "schema_id": "measurement_manifest",
                "schema_version": "1.0",
                "created_utc": _now_utc_iso(),
                "artifacts": [],
            }

        # Ensure artifacts list exists.
        arts = doc.get("artifacts")
        if not isinstance(arts, list):
            arts = []
            doc["artifacts"] = arts

        # Idempotent append: skip if same path already present (any SHA).
        existing_paths = {a["path"] for a in arts if isinstance(a, dict) and "path" in a}
        for e in entries:
            if e["path"] not in existing_paths:
                arts.append(e)

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return manifest_path


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def attach_pattern_record(rec: dict, detected_peaks_hz: list[float]) -> float:
    """
    Enrich pattern record with nearest detected peak and delta.
    Returns delta_hz for policy evaluation.
    """
    freq_hz = rec["freq_hz"]
    image_freq_tag_hz = rec.get("image_freq_tag_hz", freq_hz)
    
    # Find nearest detected peak
    nearest = None
    if detected_peaks_hz:
        nearest = float(min(detected_peaks_hz, key=lambda p: abs(p - freq_hz)))
    
    # Compute delta from image tag to nearest detected peak
    delta = abs(image_freq_tag_hz - (nearest if nearest is not None else freq_hz))
    
    rec["nearest_detected_hz"] = nearest
    rec["delta_hz"] = round(delta, 4)
    
    # Add warning if mismatch detected
    if delta > 0:
        rec.setdefault("_warnings", []).append(f"freq_mismatch: delta_hz={delta:.2f}")
    
    return delta


def finalize_run(chladni_run: dict, tolerance_hz: float = CHLADNI_FREQ_TOLERANCE_HZ) -> None:
    """
    Finalize chladni_run with policy checks.
    Raises SystemExit(2) if worst delta exceeds tolerance.
    """
    patterns = chladni_run.get("patterns", [])
    worst = max((p.get("delta_hz") or 0.0) for p in patterns) if patterns else 0.0
    
    # Record policy metadata
    chladni_run.setdefault("_policy", {})
    chladni_run["_policy"]["freq_tolerance_hz"] = tolerance_hz
    chladni_run["_policy"]["worst_delta_hz"] = worst
    
    # Check tolerance
    if worst > tolerance_hz:
        chladni_run.setdefault("_errors", []).append(
            f"max delta_hz {worst:.2f} exceeds tolerance {tolerance_hz:.2f}"
        )
        raise SystemExit(2)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Index Chladni pattern images to frequencies"
    )
    ap.add_argument("--peaks-json", required=True, help="Path to peaks.json")
    ap.add_argument(
        "--images", nargs="+", required=True, help="Image files (e.g., F0148.png)"
    )
    ap.add_argument("--plate-id", required=True, help="Plate identifier")
    ap.add_argument("--tempC", type=float, default=None, help="Temperature (C)")
    ap.add_argument("--rh", type=float, default=None, help="Relative humidity (pct)")
    ap.add_argument("--out", required=True, help="Output chladni_run.json path")
    ap.add_argument("--tolerance-hz", type=float, default=CHLADNI_FREQ_TOLERANCE_HZ,
                    help=f"Frequency mismatch tolerance (default: {CHLADNI_FREQ_TOLERANCE_HZ} Hz)")
    args = ap.parse_args()

    with open(args.peaks_json, "r", encoding="utf-8") as fp:
        peaks = json.load(fp)

    detected_peaks_hz = peaks.get("peaks_hz", [])
    patterns = []
    
    for img in args.images:
        name = pathlib.Path(img).name
        # Match F0148.png → 148 Hz, F1234.png → 1234 Hz
        m = re.search(r"F(\d+)", name)
        if not m:
            print(f"Warning: skipping {name} (no F<freq> pattern)")
            continue
        freq = int(m.group(1))
        rec = {
            "freq_hz": freq,
            "image_path": img,
            "image_sha256": sha256(img),
            "image_freq_tag_hz": freq,  # from filename
        }
        # Attach nearest peak and compute delta
        delta = attach_pattern_record(rec, detected_peaks_hz)
        if delta > 0:
            print(f"Warning: {name} freq_hz={freq} -> nearest_detected={rec['nearest_detected_hz']}, delta={delta:.2f} Hz")
        patterns.append(rec)

    run = {
        "schema_id": "chladni_run",
        "schema_version": "1.0",
        "artifact_type": "chladni_run",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "plate_id": args.plate_id,
        "environment": {
            "temp_C": args.tempC,
            "rh_pct": args.rh,
        },
        "excitation": {
            "mode": "external/unknown",  # measurement-only sandbox
        },
        "peaks_hz": detected_peaks_hz,
        "patterns": sorted(patterns, key=lambda x: x["freq_hz"]),
        "provenance": {
            "peaks_json_path": args.peaks_json,
            "peaks_sha256": sha256(args.peaks_json),
            "mic_wav_path": peaks.get("wav_path"),
            "mic_wav_sha256": peaks.get("wav_sha256"),
        },
    }

    # Apply frequency mismatch policy (may raise SystemExit(2))
    finalize_run(run, tolerance_hz=args.tolerance_hz)

    p = pathlib.Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fp:
        json.dump(run, fp, indent=2)

    print(f"Wrote {p} (patterns={len(run['patterns'])})")


if __name__ == "__main__":
    main()
