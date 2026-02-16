#!/usr/bin/env python3
"""
Phase 2 Viewer Pack Exporter (viewer_pack_v1)

Input:
  runs_phase2/session_YYYYMMDDTHHMMSSZ/

Output (dir or zip):
  viewer_pack_v1/
    manifest.json
    README.txt
    audio/points/<PID>.wav
    spectra/points/<PID>/spectrum.csv
    spectra/points/<PID>/analysis.json
    provenance/points/<PID>/capture_meta.json
    meta/grid.json
    meta/metadata.json
    ods/ods_snapshot.json
    wolf/wolf_candidates.json
    wolf/wsi_curve.csv
    plots/*.png

Phase 2 assumptions:
  - points live in points/point_<PID>/
  - audio is 2-ch wav (ref=ch0, roving=ch1) kept as-is
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zipfile import ZipFile, ZIP_DEFLATED

# Pre-export validation gate
from tap_tone.validate.viewer_pack_v1 import validate_pack, write_validation_report

# Session metadata export
from tap_tone.export_metadata import SessionMetaV1, write_session_meta


def extract_session_metadata(session_dir: Path) -> Dict[str, Any]:
    """
    Extract metadata from existing session files.

    Reads from metadata.json, grid.json, and capture_meta.json to populate
    session-level metadata for ToolBox compare UI.
    """
    meta: Dict[str, Any] = {}

    # Try metadata.json (session-level config)
    metadata_file = session_dir / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                data = json.load(f)
            meta["specimen_id"] = data.get("specimen_id", data.get("sample_id", ""))
            meta["device_id"] = data.get("device_id", "")
            meta["fixture_id"] = data.get("fixture_id", "")
            meta["mic_id"] = data.get("mic_id", "")
            meta["mic_gain_db"] = data.get("mic_gain_db")
            meta["preamp_model"] = data.get("preamp_model")
            meta["sample_rate_hz"] = data.get("sample_rate_hz")
            meta["tap_protocol"] = data.get("tap_protocol", data.get("protocol", ""))
            meta["ambient_notes"] = data.get("ambient_notes", data.get("notes", ""))
        except (json.JSONDecodeError, OSError):
            pass

    # Try grid.json for point count
    grid_file = session_dir / "grid.json"
    if grid_file.exists():
        try:
            with open(grid_file) as f:
                grid = json.load(f)
            points = grid.get("points", [])
            meta["tap_count"] = len(points)
        except (json.JSONDecodeError, OSError):
            pass

    # Count actual point folders if grid.json not available
    if "tap_count" not in meta or meta["tap_count"] is None:
        points_dir = session_dir / "points"
        if points_dir.exists():
            point_count = sum(1 for p in points_dir.iterdir() if p.is_dir() and p.name.startswith("point_"))
            meta["tap_count"] = point_count

    # Try first capture_meta.json for sample rate if not in metadata.json
    if not meta.get("sample_rate_hz"):
        points_dir = session_dir / "points"
        if points_dir.exists():
            for point_folder in sorted(points_dir.iterdir()):
                cap_meta = point_folder / "capture_meta.json"
                if cap_meta.exists():
                    try:
                        with open(cap_meta) as f:
                            cap = json.load(f)
                        meta["sample_rate_hz"] = cap.get("sample_rate_hz")
                        break
                    except (json.JSONDecodeError, OSError):
                        pass

    # Use session folder name as run_id if not set
    meta["run_id"] = session_dir.name

    return meta


# Canonical kind vocabulary (single source of truth)
# ToolBox viewer dispatches on these exact strings
KIND_VOCAB = {
    "audio_raw",
    "spectrum_csv",
    "analysis_peaks",
    "coherence",
    "transfer_function",  # ODS data (ods_snapshot.json)
    "wolf_candidates",
    "wsi_curve",
    "provenance",
    "plot_png",
    "session_meta",
    "manifest",
    "unknown",
}

KIND_BY_RELPATH_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^audio/points/.+\.wav$", re.I), "audio_raw"),
    (re.compile(r"^spectra/points/.+/spectrum\.csv$", re.I), "spectrum_csv"),
    (re.compile(r"^spectra/points/.+/analysis\.json$", re.I), "analysis_peaks"),
    (re.compile(r"^coherence/.+\.json$", re.I), "coherence"),
    (re.compile(r"^ods/.+\.json$", re.I), "transfer_function"),  # ODS = transfer_function
    (re.compile(r"^wolf/.+candidates\.json$", re.I), "wolf_candidates"),
    (re.compile(r"^wolf/wsi_curve\.csv$", re.I), "wsi_curve"),
    (re.compile(r"^provenance/.+\.json$", re.I), "provenance"),
    (re.compile(r"^plots/.+\.png$", re.I), "plot_png"),
    (re.compile(r"^meta/.+\.json$", re.I), "session_meta"),
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def detect_kind(relpath: str) -> str:
    rp = relpath.replace("\\", "/")
    for pat, kind in KIND_BY_RELPATH_RULES:
        if pat.search(rp):
            return kind
    return "unknown"


def guess_mime(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    return mt or "application/octet-stream"


def point_id_from_folder(folder_name: str) -> Optional[str]:
    # point_A1 -> A1
    if folder_name.startswith("point_"):
        return folder_name.split("point_", 1)[1]
    return None


@dataclass
class FileEntry:
    relpath: str
    sha256: str
    bytes: int
    mime: str
    kind: str


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(dst: Path, text: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def build_readme(session_dir: Path) -> str:
    return "\n".join([
        "Tap Tone Viewer Pack v1",
        "",
        f"Source session: {session_dir.name}",
        "Contents:",
        "- audio/points/*.wav (2-ch: ch0 reference, ch1 roving)",
        "- spectra/points/*/spectrum.csv (freq_hz,H_mag,coherence,phase_deg)",
        "- spectra/points/*/analysis.json (summary/peaks metadata)",
        "- meta/grid.json + meta/metadata.json",
        "- ods/, wolf/, plots/ as available",
        "",
        "Viewer rule: dispatch by manifest.files[].kind",
        ""
    ])


# -------------------------------------------------------------------------
# Export helpers
# -------------------------------------------------------------------------

def _add_readme(pack_root: Path, session_dir: Path, files: List[FileEntry]) -> None:
    """Add README.txt to pack."""
    readme_text = build_readme(session_dir)
    readme_path = pack_root / "README.txt"
    write_text(readme_path, readme_text)
    files.append(FileEntry(
        relpath="README.txt",
        sha256=sha256_file(readme_path),
        bytes=readme_path.stat().st_size,
        mime="text/plain",
        kind="provenance",
    ))


def _add_session_meta(
    pack_root: Path,
    session_dir: Path,
    files: List[FileEntry],
    add_file_fn,
) -> None:
    """Add session metadata files (grid.json, metadata.json, session_meta.json)."""
    grid = session_dir / "grid.json"
    metadata = session_dir / "metadata.json"
    if grid.exists():
        add_file_fn(grid, "meta/grid.json")
    if metadata.exists():
        add_file_fn(metadata, "meta/metadata.json")

    # session_meta.json (canonical metadata for ToolBox compare UI)
    extracted = extract_session_metadata(session_dir)
    session_meta = SessionMetaV1(
        specimen_id=extracted.get("specimen_id", ""),
        run_id=extracted.get("run_id", session_dir.name),
        device_id=extracted.get("device_id", ""),
        fixture_id=extracted.get("fixture_id", ""),
        mic_id=extracted.get("mic_id", ""),
        mic_gain_db=extracted.get("mic_gain_db"),
        preamp_model=extracted.get("preamp_model"),
        sample_rate_hz=extracted.get("sample_rate_hz"),
        tap_count=extracted.get("tap_count"),
        tap_protocol=extracted.get("tap_protocol"),
        ambient_notes=extracted.get("ambient_notes"),
    )
    session_meta_path = write_session_meta(pack_root, session_meta)
    files.append(FileEntry(
        relpath="meta/session_meta.json",
        sha256=sha256_file(session_meta_path),
        bytes=session_meta_path.stat().st_size,
        mime="application/json",
        kind="session_meta",
    ))


def _add_points(
    session_dir: Path,
    add_file_fn,
) -> List[str]:
    """Add point data (audio, spectra, analysis, provenance). Returns point IDs."""
    points_dir = session_dir / "points"
    if not points_dir.exists():
        raise FileNotFoundError(f"Phase2 points/ missing: {points_dir}")

    point_ids: List[str] = []

    for point_folder in sorted([p for p in points_dir.iterdir() if p.is_dir()]):
        pid = point_id_from_folder(point_folder.name)
        if not pid:
            continue
        point_ids.append(pid)

        wav = point_folder / "audio.wav"
        cap = point_folder / "capture_meta.json"
        spectrum = point_folder / "spectrum.csv"
        analysis = point_folder / "analysis.json"

        if wav.exists():
            add_file_fn(wav, f"audio/points/{pid}.wav")
        if spectrum.exists():
            add_file_fn(spectrum, f"spectra/points/{pid}/spectrum.csv")
        if analysis.exists():
            add_file_fn(analysis, f"spectra/points/{pid}/analysis.json")
        if cap.exists():
            add_file_fn(cap, f"provenance/points/{pid}/capture_meta.json")

    return point_ids


def _add_derived(session_dir: Path, add_file_fn) -> None:
    """Add derived artifacts (ods, wolf)."""
    derived_dir = session_dir / "derived"
    if not derived_dir.exists():
        return
    ods = derived_dir / "ods_snapshot.json"
    wc = derived_dir / "wolf_candidates.json"
    wsi = derived_dir / "wsi_curve.csv"
    if ods.exists():
        add_file_fn(ods, "ods/ods_snapshot.json")
    if wc.exists():
        add_file_fn(wc, "wolf/wolf_candidates.json")
    if wsi.exists():
        add_file_fn(wsi, "wolf/wsi_curve.csv")


def _add_coherence(session_dir: Path, add_file_fn) -> None:
    """Add coherence data (optional)."""
    coh_dir = session_dir / "coherence"
    if not coh_dir.exists():
        return
    coh = coh_dir / "coherence_summary.json"
    if coh.exists():
        add_file_fn(coh, "coherence/coherence_summary.json")


def _add_plots(session_dir: Path, add_file_fn) -> None:
    """Add plots."""
    plots_dir = session_dir / "plots"
    if not plots_dir.exists():
        return
    for png in sorted(plots_dir.glob("*.png")):
        add_file_fn(png, f"plots/{png.name}")


def _add_timeline(session_dir: Path, add_file_fn) -> None:
    """Add session timeline (PR #17, fail-closed)."""
    try:
        from tap_tone_pi.core.session_timeline import export_session_timeline
        tl_path = export_session_timeline(session_dir)
        if tl_path is not None and tl_path.is_file():
            add_file_fn(tl_path, "meta/session_timeline_v1.json")
    except (ImportError, OSError, ValueError, KeyError):
        pass  # Non-fatal: pack is valid without timeline


def _build_manifest(
    files: List[FileEntry],
    session_dir: Path,
    point_ids: List[str],
) -> Dict[str, Any]:
    """Build manifest dict and compute bundle_sha256."""
    manifest: Dict[str, Any] = {
        "schema_version": "v1",
        "schema_id": "viewer_pack_v1",
        "created_at_utc": utc_now_iso(),
        "source_capdir": session_dir.name,
        "detected_phase": "phase2",
        "measurement_only": True,
        "interpretation": "deferred",
        "points": point_ids,
        "contents": {
            "audio": any(e.relpath.startswith("audio/") for e in files),
            "spectra": any(e.relpath.startswith("spectra/") for e in files),
            "coherence": any(e.relpath.startswith("coherence/") for e in files),
            "ods": any(e.relpath.startswith("ods/") for e in files),
            "wolf": any(e.relpath.startswith("wolf/") for e in files),
            "plots": any(e.relpath.startswith("plots/") for e in files),
            "provenance": any(e.relpath.startswith("provenance/") for e in files),
        },
        "files": [
            {
                "relpath": e.relpath,
                "sha256": e.sha256,
                "bytes": e.bytes,
                "mime": e.mime,
                "kind": e.kind,
            }
            for e in sorted(files, key=lambda x: x.relpath)
        ],
    }

    # bundle sha = sha256 of manifest JSON bytes (before adding bundle_sha256)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    bundle_sha = sha256_bytes(manifest_bytes)
    manifest["bundle_sha256"] = bundle_sha

    return manifest


def _validate_and_gate(pack_root: Path, manifest_path: Path) -> None:
    """Run validation and raise on failure."""
    viewer_pack_json = pack_root / "viewer_pack.json"
    if not viewer_pack_json.exists():
        shutil.copy2(manifest_path, viewer_pack_json)

    report = validate_pack(pack_root)
    report_path = write_validation_report(pack_root, report)

    if not report.passed:
        excerpt = []
        for e in (report.errors or [])[:3]:
            rule = e.get("rule", "?")
            msg = e.get("message", "")
            path = e.get("path")
            if path:
                excerpt.append(f"{rule}: {msg} ({path})")
            else:
                excerpt.append(f"{rule}: {msg}")

        excerpt_txt = "; ".join(excerpt) if excerpt else "No error details available."
        raise ValueError(
            f"viewer_pack_v1 validation failed: "
            f"errors={len(report.errors)} warnings={len(report.warnings)}. "
            f"{excerpt_txt}. "
            f"See {report_path}"
        )


def _zip_pack(pack_root: Path, out_dir: Path, session_dir: Path) -> Path:
    """Create zip archive of pack."""
    zip_path = out_dir / f"{session_dir.name}__viewer_pack_v1.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as z:
        for fp in pack_root.rglob("*"):
            if fp.is_file():
                arc = fp.relative_to(pack_root.parent).as_posix()
                z.write(fp, arcname=arc)
    return zip_path


# -------------------------------------------------------------------------
# Main export function
# -------------------------------------------------------------------------

def export_viewer_pack(
    session_dir: Path,
    out_dir: Path,
    *,
    as_zip: bool,
) -> Path:
    if not session_dir.exists():
        raise FileNotFoundError(f"session_dir not found: {session_dir}")

    # Initialize pack root
    pack_root = out_dir / "viewer_pack_v1"
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True, exist_ok=True)

    files: List[FileEntry] = []

    def add_file(src: Path, relpath: str):
        dst = pack_root / relpath
        copy_file(src, dst)
        entry = FileEntry(
            relpath=relpath.replace("\\", "/"),
            sha256=sha256_file(dst),
            bytes=dst.stat().st_size,
            mime=guess_mime(dst),
            kind=detect_kind(relpath),
        )
        files.append(entry)

    # Add pack components
    _add_readme(pack_root, session_dir, files)
    _add_session_meta(pack_root, session_dir, files, add_file)
    point_ids = _add_points(session_dir, add_file)
    _add_derived(session_dir, add_file)
    _add_coherence(session_dir, add_file)
    _add_plots(session_dir, add_file)
    _add_timeline(session_dir, add_file)

    # Build and write manifest
    manifest = _build_manifest(files, session_dir, point_ids)
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # Validate
    _validate_and_gate(pack_root, manifest_path)

    # Zip if requested
    if as_zip:
        return _zip_pack(pack_root, out_dir, session_dir)

    return pack_root


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export Phase 2 session to viewer_pack_v1 format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--session-dir", required=True, help="runs_phase2/session_*/ directory")
    ap.add_argument("--out", required=True, help="output directory for pack or zip")
    ap.add_argument("--zip", action="store_true", help="emit a .zip bundle")
    args = ap.parse_args()

    session_dir = Path(args.session_dir).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result = export_viewer_pack(session_dir, out_dir, as_zip=args.zip)
    print(f"[viewer-pack] wrote: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
