from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import socket
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


MANIFEST_VERSION = "TapToneBundleManifestV1"
DEFAULT_EXCLUDES = {
    ".DS_Store",
    "Thumbs.db",
}
# Directories we never recurse into during export (to avoid packing prior exports)
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    "build",
    "node_modules",
    "attachments",  # our own output pack
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Deterministic JSON encoding:
    - sort keys
    - no whitespace variance
    """
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")


def detect_kind(relpath: str) -> str:
    """
    Classify file kind for RMOS-friendly ingest.
    Keep this stable; add new kinds only when necessary.
    """
    p = relpath.replace("\\", "/")
    name = p.split("/")[-1].lower()

    if name == "manifest.json":
        return "manifest"

    if name.endswith(".wav"):
        # If under points/, it's per-point audio
        return "point_audio_raw" if "/points/" in p else "audio_raw"

    if name == "analysis.json":
        return "point_analysis" if "/points/" in p else "analysis_summary"

    if name.endswith(".csv") and ("spectrum" in name or "tf" in name or "transfer" in name):
        return "point_spectrum" if "/points/" in p else "spectrum"

    if name == "grid.json":
        return "grid"

    if name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg"):
        return "plot"

    if name.endswith(".pdf"):
        return "report"

    if name.endswith(".json"):
        # Heuristics for common derived files
        if "wolf" in name and "candidate" in name:
            return "wolf_candidates"
        if "wolf" in name and "map" in name:
            return "derived_map"
        if "metadata" in name:
            return "session_metadata"
        return "json"

    if name.endswith(".npy"):
        return "array"

    if name.endswith(".txt") or name.endswith(".log"):
        return "log"

    return "file"


def infer_point_id(relpath: str) -> Optional[str]:
    """
    Extract point_id from paths like:
      points/point_A1/audio.wav  -> A1
      points/A1/audio.wav        -> A1 (if your structure differs)
    """
    p = relpath.replace("\\", "/")
    parts = [x for x in p.split("/") if x]
    if "points" not in parts:
        return None
    i = parts.index("points")
    if i + 1 >= len(parts):
        return None
    token = parts[i + 1]
    # point_A1 -> A1
    if token.lower().startswith("point_"):
        return token.split("_", 1)[1] or token
    return token


def infer_phase(bundle_root: Path) -> int:
    """
    Infer phase:
      Phase 1: capture_* with audio.wav + analysis.json + spectrum.csv
      Phase 3: has grid.json and points/ subtree
    """
    if (bundle_root / "grid.json").exists() and (bundle_root / "points").exists():
        return 3
    # Phase 2 commonly has 2ch coherence artifacts; keep as 2 if we see coherence keywords
    # Otherwise default to 1
    # (We stay conservative: only declare 2 if strong evidence exists)
    for p in bundle_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".csv", ".json"):
            n = p.name.lower()
            if "coherence" in n or "cross_channel" in n or "phase_deg" in n:
                return 2
    return 1


def infer_capture_times_from_name(bundle_root: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort:
      - capture_YYYYMMDDTHHMMSSZ
      - session_YYYYMMDDTHHMMSSZ
    If not parseable, return None and let caller populate with utc_now.
    """
    name = bundle_root.name
    for prefix in ("capture_", "session_"):
        if name.startswith(prefix):
            ts = name[len(prefix):]
            # Accept forms like 20251225T143052Z
            try:
                dt = datetime.strptime(ts, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                return iso, iso
            except Exception:
                return None, None
    return None, None


def list_bundle_files(bundle_root: Path, *, exclude_dirs: set[str]) -> List[Path]:
    """
    Return all files under bundle_root, excluding known junk.
    """
    files: List[Path] = []
    for p in bundle_root.rglob("*"):
        if p.is_dir():
            # prune excluded dirs
            if p.name in exclude_dirs:
                # prevent descent: rglob doesn't support pruning directly; handle by skipping
                continue
            continue
        if not p.is_file():
            continue
        if p.name in DEFAULT_EXCLUDES:
            continue
        # Skip anything inside excluded dirs (by path parts)
        parts = set(p.parts)
        if parts.intersection(exclude_dirs):
            continue
        files.append(p)
    # Stable ordering
    files.sort(key=lambda x: str(x).lower())
    return files


def guess_mime(path: Path) -> str:
    m, _ = mimetypes.guess_type(str(path))
    return m or "application/octet-stream"


@dataclass(frozen=True)
class ExportInputs:
    bundle_root: Path
    out_dir: Path
    pack: str  # "none" | "dir" | "zip"
    bundle_id: str
    instrument_id: Optional[str]
    build_stage: Optional[str]
    operator: Optional[str]
    mic_model: Optional[str]
    adc_model: Optional[str]
    device_id: Optional[str]
    units: str  # "mm" (v1)
    tool_id: str
    app_version: str
    event_type: str
    coh_min: Optional[float]


def build_manifest(inputs: ExportInputs) -> Dict[str, Any]:
    bundle_root = inputs.bundle_root

    phase = infer_phase(bundle_root)
    started, finished = infer_capture_times_from_name(bundle_root)
    if started is None:
        started = utc_now_iso()
    if finished is None:
        finished = started

    device_id = inputs.device_id or socket.gethostname()

    files_paths = list_bundle_files(bundle_root, exclude_dirs=DEFAULT_EXCLUDE_DIRS)

    files: List[Dict[str, Any]] = []
    for p in files_paths:
        relpath = str(p.relative_to(bundle_root)).replace("\\", "/")
        file_sha = sha256_file(p)
        size = p.stat().st_size
        mime = guess_mime(p)
        kind = detect_kind(relpath)
        point_id = infer_point_id(relpath)

        files.append(
            {
                "relpath": relpath,
                "sha256": file_sha,
                "bytes": int(size),
                "mime": mime,
                "kind": kind,
                "point_id": point_id,
            }
        )

    manifest: Dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "bundle_id": inputs.bundle_id,
        "bundle_root_name": bundle_root.name,
        "capture_started_at_utc": started,
        "capture_finished_at_utc": finished,
        "tool_id": inputs.tool_id,
        "app_version": inputs.app_version,
        "mode": "acoustics",
        "event_type": inputs.event_type,
        "units": inputs.units,
        "instrument": {
            "instrument_id": inputs.instrument_id,
            "build_stage": inputs.build_stage,
            "operator": inputs.operator,
        },
        "provenance": {
            "device_id": device_id,
            "mic_model": inputs.mic_model,
            "adc_model": inputs.adc_model,
        },
        # Domain namespace so future fields don't break generic tooling
        "domain": {
            "acoustics": {
                "phase": phase,
                "coh_min": inputs.coh_min,
            }
        },
        "files": files,
        # Placeholder; filled after canonicalization:
        "bundle_sha256": None,
        "generated_at_utc": utc_now_iso(),
    }

    # Strip Nones cleanly (keep contract tidy)
    def strip_nones(x: Any) -> Any:
        if isinstance(x, dict):
            return {k: strip_nones(v) for k, v in x.items() if v is not None}
        if isinstance(x, list):
            return [strip_nones(v) for v in x]
        return x

    return strip_nones(manifest)


def add_bundle_sha256(manifest: Dict[str, Any]) -> Dict[str, Any]:
    m = dict(manifest)
    m["bundle_sha256"] = None
    b = canonical_json_bytes(m)
    m["bundle_sha256"] = sha256_bytes(b)
    return m


def write_manifest(out_dir: Path, manifest: Dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def build_rmos_artifact(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a ready-to-ingest RunArtifact pointer skeleton for RMOS runs_v2.

    This is intentionally NOT RMOS-internal schema-complete (run_id/status lifecycle
    are RMOS-side concerns). It is an ingest payload that RMOS can accept and
    convert into its canonical run_{run_id}.json form.
    """
    instrument = manifest.get("instrument", {})
    domain = manifest.get("domain", {})
    acoustics = (domain.get("acoustics") or {}) if isinstance(domain, dict) else {}

    # Flatten attachments from manifest files
    attachments = []
    for f in manifest.get("files", []):
        attachments.append({
            "sha256": f.get("sha256"),
            "relpath": f.get("relpath"),
            "bytes": f.get("bytes"),
            "mime": f.get("mime"),
            "kind": f.get("kind"),
            "point_id": f.get("point_id"),
        })

    payload = {
        "mode": manifest.get("mode", "acoustics"),
        "event_type": manifest.get("event_type", "tap_tone.capture"),
        "tool_id": manifest.get("tool_id", "tap_tone_pi"),
        "app_version": manifest.get("app_version"),
        "units": manifest.get("units", "mm"),

        # identity + dedupe keys
        "bundle_id": manifest.get("bundle_id"),
        "bundle_sha256": manifest.get("bundle_sha256"),

        # timestamps
        "capture_started_at_utc": manifest.get("capture_started_at_utc"),
        "capture_finished_at_utc": manifest.get("capture_finished_at_utc"),
        "generated_at_utc": manifest.get("generated_at_utc"),

        # core indexing fields
        "instrument_id": instrument.get("instrument_id"),
        "build_stage": instrument.get("build_stage"),
        "operator": instrument.get("operator"),

        # evolvable namespace (RMOS dev requested this)
        "meta": {
            "acoustics": {
                "phase": acoustics.get("phase"),
                "coh_min": acoustics.get("coh_min"),
                "bundle_root_name": manifest.get("bundle_root_name"),
            }
        },

        # attachments (by sha, relpath, kind)
        "attachments": attachments,
    }

    # prune Nones for cleanliness
    def strip_nones(x: Any) -> Any:
        if isinstance(x, dict):
            return {k: strip_nones(v) for k, v in x.items() if v is not None}
        if isinstance(x, list):
            return [strip_nones(v) for v in x if v is not None]
        return x

    return strip_nones(payload)


def pack_dir(bundle_root: Path, out_dir: Path, manifest_path: Path, files: List[Dict[str, Any]]) -> Path:
    """
    Create an attachment pack folder:
      <out_dir>/attachments/<relpath...>
      <out_dir>/manifest.json (already written)
    """
    attachments_dir = out_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        relpath = f["relpath"]
        src = bundle_root / relpath
        dst = attachments_dir / relpath
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Copy bytes
        dst.write_bytes(src.read_bytes())

    return attachments_dir


def pack_zip(bundle_root: Path, out_dir: Path, bundle_id: str, manifest_path: Path, files: List[Dict[str, Any]]) -> Path:
    """
    Create a zip containing:
      manifest.json
      attachments/<relpath...>
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{bundle_id}_import.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(manifest_path, arcname="manifest.json")
        for f in files:
            relpath = f["relpath"]
            src = bundle_root / relpath
            arc = f"attachments/{relpath}"
            z.write(src, arcname=arc)

    return zip_path


def build_bundle_id(
    bundle_root: Path,
    instrument_id: Optional[str],
    build_stage: Optional[str],
) -> str:
    """
    Default bundle_id if not explicitly provided:
      <instrument_id>_<build_stage>_<bundle_root_name>
    Falls back gracefully.
    """
    parts = []
    if instrument_id:
        parts.append(instrument_id)
    if build_stage:
        parts.append(build_stage)
    parts.append(bundle_root.name)
    # sanitize
    s = "_".join(parts)
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in s)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export tap_tone_pi bundle as ManifestV1 + optional RMOS import pack.")
    ap.add_argument("--bundle", required=True, help="Path to capture_*/session_* bundle root")
    ap.add_argument("--out", required=True, help="Output directory where manifest/pack are written")
    ap.add_argument("--pack", choices=["none", "dir", "zip"], default="none", help="Optional pack style")
    ap.add_argument("--bundle-id", default=None, help="Stable bundle_id (defaults to instrument/build_stage + folder name)")

    ap.add_argument("--instrument-id", default=None, help="Instrument identifier (e.g., OM23)")
    ap.add_argument("--build-stage", default=None, help="Build stage (e.g., braced, boxed, finished)")
    ap.add_argument("--operator", default=None, help="Operator name/initials")
    ap.add_argument("--mic-model", default=None, help="Mic model (e.g., AT2020, iSEMcon EMX-7150)")
    ap.add_argument("--adc-model", default=None, help="ADC model (e.g., Focusrite Solo, USB mic model)")
    ap.add_argument("--device-id", default=None, help="Device ID override (default: hostname)")
    ap.add_argument("--coh-min", type=float, default=None, help="Coherence threshold used (if applicable)")

    ap.add_argument("--units", default="mm", choices=["mm"], help="Units for spatial info (v1 fixed to mm)")
    ap.add_argument("--tool-id", default="tap_tone_pi", help="Tool identifier")
    ap.add_argument("--app-version", default="1.0.0", help="App version (freeze baseline v1.0.0)")
    ap.add_argument("--event-type", default="tap_tone.capture", help="Event type string (stable)")
    ap.add_argument("--emit-rmos-artifact", action="store_true",
                    help="Also write rmos_artifact.json payload (ready-to-ingest skeleton)")

    return ap.parse_args(argv)


def export_bundle(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    bundle_root = Path(args.bundle).expanduser().resolve()
    if not bundle_root.exists() or not bundle_root.is_dir():
        print(f"[ERR] bundle path not found or not a directory: {bundle_root}", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_id = args.bundle_id or build_bundle_id(bundle_root, args.instrument_id, args.build_stage)

    inputs = ExportInputs(
        bundle_root=bundle_root,
        out_dir=out_dir,
        pack=args.pack,
        bundle_id=bundle_id,
        instrument_id=args.instrument_id,
        build_stage=args.build_stage,
        operator=args.operator,
        mic_model=args.mic_model,
        adc_model=args.adc_model,
        device_id=args.device_id,
        units=args.units,
        tool_id=args.tool_id,
        app_version=args.app_version,
        event_type=args.event_type,
        coh_min=args.coh_min,
    )

    manifest = build_manifest(inputs)
    manifest = add_bundle_sha256(manifest)

    manifest_path = write_manifest(out_dir, manifest)
    print(f"[OK] wrote {manifest_path}")

    if args.emit_rmos_artifact:
        rmos_payload = build_rmos_artifact(manifest)
        rmos_path = out_dir / "rmos_artifact.json"
        rmos_path.write_text(json.dumps(rmos_payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[OK] wrote {rmos_path}")

    if args.pack == "dir":
        attachments_dir = pack_dir(bundle_root, out_dir, manifest_path, manifest["files"])
        print(f"[OK] packed attachments dir {attachments_dir}")
    elif args.pack == "zip":
        zip_path = pack_zip(bundle_root, out_dir, bundle_id, manifest_path, manifest["files"])
        print(f"[OK] packed zip {zip_path}")
    else:
        print("[OK] pack=none (manifest only)")

    # Print identity for dedupe
    print(f"[OK] bundle_id={manifest['bundle_id']}")
    print(f"[OK] bundle_sha256={manifest['bundle_sha256']}")
    print(f"[OK] files={len(manifest['files'])}")
    return 0


def main() -> None:
    raise SystemExit(export_bundle())


if __name__ == "__main__":
    main()
