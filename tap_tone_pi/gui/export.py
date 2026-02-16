#!/usr/bin/env python3
"""Viewer pack export for GUI sessions.

Exports a GUI measurement session to viewer_pack_v1 format.

GUI session structure:
    out/<run_id>/
        <point_id>/
            attempt_001/
                audio.wav
                analysis.json
                quality_check.json

Output viewer_pack_v1 structure:
    viewer_pack_v1/
        viewer_pack.json (manifest)
        audio/points/<point_id>.wav
        spectra/points/<point_id>/spectrum.csv
        spectra/points/<point_id>/analysis.json
        meta/session_meta.json
        validation_report.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import ZipFile, ZIP_DEFLATED

# Optional: spectrum generation from audio
try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def sha256_file(p: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    """Compute SHA-256 hash of bytes."""
    return hashlib.sha256(b).hexdigest()


def utc_now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ExportResult:
    """Result of viewer pack export."""
    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    point_count: int = 0
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def _find_best_attempt(point_dir: Path) -> Optional[Path]:
    """Find the best attempt in a point directory.

    Prefers PASS > WARN > FAIL. Within same verdict, uses latest attempt.
    """
    attempts = sorted([d for d in point_dir.iterdir() if d.is_dir() and d.name.startswith("attempt_")])
    if not attempts:
        return None

    # Score attempts: PASS=3, WARN=2, FAIL=1, no verdict=0
    def score_attempt(attempt_dir: Path) -> tuple[int, str]:
        qc_path = attempt_dir / "quality_check.json"
        if qc_path.exists():
            try:
                with open(qc_path) as f:
                    qc = json.load(f)
                verdict = qc.get("verdict", "FAIL")
                if verdict == "PASS":
                    return (3, attempt_dir.name)
                elif verdict == "WARN":
                    return (2, attempt_dir.name)
                else:
                    return (1, attempt_dir.name)
            except (json.JSONDecodeError, OSError):
                pass
        return (0, attempt_dir.name)

    # Sort by score (descending), then by name (descending for latest)
    scored = [(score_attempt(a), a) for a in attempts]
    scored.sort(key=lambda x: (x[0][0], x[0][1]), reverse=True)

    return scored[0][1] if scored else None


def _generate_spectrum_csv(audio_path: Path, analysis_path: Path, output_path: Path) -> bool:
    """Generate spectrum.csv from audio and analysis.

    Returns True if successful, False otherwise.
    """
    if not HAS_NUMPY:
        return False

    try:
        from scipy.io import wavfile

        sr, audio = wavfile.read(str(audio_path))

        # Convert to float
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0

        # Mono
        if audio.ndim > 1:
            audio = audio[:, 0]

        # FFT
        n = len(audio)
        freqs = rfftfreq(n, 1.0 / sr)
        spectrum = np.abs(rfft(audio)) / n

        # Limit to reasonable range (20 Hz - 5000 Hz)
        mask = (freqs >= 20) & (freqs <= 5000)
        freqs = freqs[mask]
        spectrum = spectrum[mask]

        # Write CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["freq_hz", "H_mag"])
            for freq, mag in zip(freqs, spectrum):
                writer.writerow([f"{freq:.2f}", f"{mag:.8f}"])

        return True
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return False


def export_gui_session(
    session_dir: Path,
    output_dir: Optional[Path] = None,
    as_zip: bool = True,
) -> ExportResult:
    """Export a GUI session to viewer_pack_v1 format.

    Args:
        session_dir: Path to the session directory (out/<run_id>/)
        output_dir: Output directory (default: same as session_dir)
        as_zip: If True, create a ZIP file; if False, create directory

    Returns:
        ExportResult with success status and output path
    """
    session_dir = Path(session_dir).resolve()

    if not session_dir.exists():
        return ExportResult(success=False, error=f"Session not found: {session_dir}")

    if output_dir is None:
        output_dir = session_dir.parent
    else:
        output_dir = Path(output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create pack directory
    pack_root = output_dir / f"{session_dir.name}_viewer_pack"
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []
    files: List[Dict[str, Any]] = []
    point_ids: List[str] = []

    def add_file(src: Path, relpath: str, kind: str) -> None:
        dst = pack_root / relpath
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        files.append({
            "relpath": relpath.replace("\\", "/"),
            "sha256": sha256_file(dst),
            "bytes": dst.stat().st_size,
            "kind": kind,
        })

    # Find all points
    for item in sorted(session_dir.iterdir()):
        if not item.is_dir():
            continue

        # Skip non-point directories
        if item.name.startswith("_") or item.name.startswith("."):
            continue

        # Check if this looks like a point directory (has attempt_* subdirs)
        attempts = [d for d in item.iterdir() if d.is_dir() and d.name.startswith("attempt_")]
        if not attempts:
            continue

        point_id = item.name
        best_attempt = _find_best_attempt(item)

        if best_attempt is None:
            warnings.append(f"No valid attempt for point {point_id}")
            continue

        point_ids.append(point_id)

        # Copy audio
        audio_path = best_attempt / "audio.wav"
        if audio_path.exists():
            add_file(audio_path, f"audio/points/{point_id}.wav", "audio_raw")
        else:
            warnings.append(f"No audio for point {point_id}")

        # Copy analysis
        analysis_path = best_attempt / "analysis.json"
        if analysis_path.exists():
            add_file(analysis_path, f"spectra/points/{point_id}/analysis.json", "analysis_peaks")

        # Generate spectrum CSV if possible
        if audio_path.exists():
            spectrum_path = pack_root / f"spectra/points/{point_id}/spectrum.csv"
            if _generate_spectrum_csv(audio_path, analysis_path, spectrum_path):
                files.append({
                    "relpath": f"spectra/points/{point_id}/spectrum.csv",
                    "sha256": sha256_file(spectrum_path),
                    "bytes": spectrum_path.stat().st_size,
                    "kind": "spectrum_csv",
                })

    if not point_ids:
        return ExportResult(
            success=False,
            error="No measurement points found in session",
            warnings=warnings,
        )

    # Create session metadata
    session_meta = {
        "schema_id": "session_meta_v1",
        "schema_version": "1.0",
        "run_id": session_dir.name,
        "exported_at_utc": utc_now_iso(),
        "point_count": len(point_ids),
        "source": "tap_tone_pi_gui",
    }

    meta_path = pack_root / "meta" / "session_meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(session_meta, indent=2), encoding="utf-8")
    files.append({
        "relpath": "meta/session_meta.json",
        "sha256": sha256_file(meta_path),
        "bytes": meta_path.stat().st_size,
        "kind": "session_meta",
    })

    # Create manifest
    manifest = {
        "schema_id": "viewer_pack_v1",
        "schema_version": "v1",
        "created_at_utc": utc_now_iso(),
        "source_session": session_dir.name,
        "detected_phase": "quality_gated",
        "measurement_only": True,
        "points": point_ids,
        "contents": {
            "audio": any(f["kind"] == "audio_raw" for f in files),
            "spectra": any(f["kind"] in ("spectrum_csv", "analysis_peaks") for f in files),
            "coherence": False,
            "ods": False,
            "wolf": False,
            "plots": False,
            "provenance": False,
        },
        "files": sorted(files, key=lambda x: x["relpath"]),
    }

    # Compute bundle SHA before adding it
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    bundle_sha = sha256_bytes(manifest_bytes)
    manifest["bundle_sha256"] = bundle_sha

    manifest_path = pack_root / "viewer_pack.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Create ZIP if requested
    if as_zip:
        zip_path = output_dir / f"{session_dir.name}_viewer_pack.zip"
        if zip_path.exists():
            zip_path.unlink()

        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
            for fp in pack_root.rglob("*"):
                if fp.is_file():
                    arcname = fp.relative_to(pack_root).as_posix()
                    zf.write(fp, arcname=arcname)

        # Clean up directory
        shutil.rmtree(pack_root)

        return ExportResult(
            success=True,
            output_path=zip_path,
            point_count=len(point_ids),
            warnings=warnings,
        )
    else:
        return ExportResult(
            success=True,
            output_path=pack_root,
            point_count=len(point_ids),
            warnings=warnings,
        )


__all__ = [
    "ExportResult",
    "export_gui_session",
]
