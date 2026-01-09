#!/usr/bin/env python3
"""
Validate viewer_pack_v1 bundle integrity.

Usage:
    python scripts/phase2/validate_viewer_pack_v1.py --pack-dir out/viewer_packs/viewer_pack_v1
    python scripts/phase2/validate_viewer_pack_v1.py --zip out/viewer_packs/session_...__viewer_pack_v1.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile


# Canonical kind vocabulary (must match exporter)
VALID_KINDS = {
    "audio_raw",
    "spectrum_csv",
    "analysis_peaks",
    "coherence",
    "transfer_function",
    "wolf_candidates",
    "wsi_curve",
    "provenance",
    "plot_png",
    "session_meta",
    "manifest",
    "unknown",
}

REQUIRED_KINDS = {"audio_raw", "spectrum_csv", "session_meta"}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class ValidationError(Exception):
    """Validation failure."""
    pass


def validate_pack(pack_dir: Path) -> dict:
    """
    Validate a viewer_pack_v1 directory.
    
    Returns dict with validation results.
    Raises ValidationError on failure.
    """
    results = {
        "pack_dir": str(pack_dir),
        "manifest_valid": False,
        "files_exist": False,
        "hashes_match": False,
        "kinds_valid": False,
        "required_kinds_present": False,
        "file_count": 0,
        "errors": [],
    }
    
    # Check manifest exists
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValidationError(f"manifest.json not found in {pack_dir}")
    
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in manifest: {e}")
    
    # Validate schema identifiers
    if manifest.get("schema_id") != "viewer_pack_v1":
        results["errors"].append(f"Invalid schema_id: {manifest.get('schema_id')}")
    if manifest.get("schema_version") != "v1":
        results["errors"].append(f"Invalid schema_version: {manifest.get('schema_version')}")
    
    results["manifest_valid"] = len(results["errors"]) == 0
    
    # Check all files exist
    files = manifest.get("files", [])
    results["file_count"] = len(files)
    missing_files = []
    
    for entry in files:
        file_path = pack_dir / entry["relpath"]
        if not file_path.exists():
            missing_files.append(entry["relpath"])
    
    if missing_files:
        results["errors"].append(f"Missing files: {missing_files}")
    results["files_exist"] = len(missing_files) == 0
    
    # Check all hashes match
    hash_mismatches = []
    for entry in files:
        file_path = pack_dir / entry["relpath"]
        if file_path.exists():
            actual = sha256_file(file_path)
            if actual != entry["sha256"]:
                hash_mismatches.append(f"{entry['relpath']}: expected {entry['sha256'][:16]}..., got {actual[:16]}...")
    
    if hash_mismatches:
        results["errors"].append(f"Hash mismatches: {hash_mismatches}")
    results["hashes_match"] = len(hash_mismatches) == 0
    
    # Check all kinds are valid
    invalid_kinds = []
    present_kinds = set()
    for entry in files:
        kind = entry.get("kind")
        present_kinds.add(kind)
        if kind not in VALID_KINDS:
            invalid_kinds.append(f"{entry['relpath']}: {kind}")
    
    if invalid_kinds:
        results["errors"].append(f"Invalid kinds: {invalid_kinds}")
    results["kinds_valid"] = len(invalid_kinds) == 0
    
    # Check required kinds present
    missing_kinds = REQUIRED_KINDS - present_kinds
    if missing_kinds:
        results["errors"].append(f"Missing required kinds: {missing_kinds}")
    results["required_kinds_present"] = len(missing_kinds) == 0
    
    # Final check
    if results["errors"]:
        raise ValidationError("\n".join(results["errors"]))
    
    return results


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate viewer_pack_v1 bundle integrity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--pack-dir", type=Path, help="Path to unzipped viewer_pack_v1 directory")
    ap.add_argument("--zip", type=Path, help="Path to viewer_pack_v1 zip file")
    args = ap.parse_args()
    
    if not args.pack_dir and not args.zip:
        ap.error("Must specify --pack-dir or --zip")
    
    if args.zip:
        # Extract to temp dir and validate
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            with ZipFile(args.zip, "r") as zf:
                zf.extractall(tmppath)
            
            # Find viewer_pack_v1 dir (might be nested)
            candidates = list(tmppath.glob("**/manifest.json"))
            if not candidates:
                print(f"[FAIL] No manifest.json found in {args.zip}")
                return 1
            
            pack_dir = candidates[0].parent
            try:
                results = validate_pack(pack_dir)
                print(f"[OK] {args.zip}")
                print(f"     Files: {results['file_count']}")
                return 0
            except ValidationError as e:
                print(f"[FAIL] {args.zip}")
                print(f"       {e}")
                return 1
    
    else:
        try:
            results = validate_pack(args.pack_dir)
            print(f"[OK] {args.pack_dir}")
            print(f"     Files: {results['file_count']}")
            return 0
        except ValidationError as e:
            print(f"[FAIL] {args.pack_dir}")
            print(f"       {e}")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
