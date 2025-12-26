#!/usr/bin/env python3
"""
RMOS RunArtifact Export for Tap Tone Lab

This script generates RMOS-compatible RunArtifact payloads from tap-tone bundles,
enabling integration with the RMOS (Research Management and Orchestration System)
artifact tracking and analysis pipeline.

Export format matches ADR-0006 (RMOS RunArtifact mapping) specification:
- Each capture bundle → one RunArtifact (type: tap_tone_capture)
- SHA256 hashing for file integrity and deduplication
- Provenance tracking (tool_id, version, git_commit, operator, timestamp)
- Structured metadata (instrument_id, build_stage, tap_point, etc.)

Output structure:
    export/
    ├── rmos_artifact.json        # RunArtifact payload (POST to RMOS API)
    ├── manifest.json             # File hashes and metadata
    └── attachments/              # Optional: all bundle files for upload
        ├── audio.wav
        ├── analysis.json
        ├── spectrum.csv
        └── ...

Usage:
    # Generate RMOS artifact payload only
    python scripts/rmos_export.py --bundle ./captures/capture_123 --out ./exports/export_123

    # Include attachments directory (for RMOS runs_v2 intake)
    python scripts/rmos_export.py --bundle ./captures/capture_123 --out ./exports/export_123 --pack-attachments

    # Override metadata fields
    python scripts/rmos_export.py --bundle ./captures/capture_123 --out ./exports/export_123 \\
        --instrument-id "OM-001" --build-stage "pre_finish" --operator "Ross Echols"

Reference: ADR-0006 (RMOS RunArtifact mapping)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def scan_bundle_files(bundle_dir: Path) -> list[dict[str, Any]]:
    """
    Scan bundle directory and compute file hashes.
    Returns list of file records: {name, bytes, sha256}
    """
    files = []
    for path in sorted(bundle_dir.rglob("*")):
        if path.is_file():
            rel_path = path.relative_to(bundle_dir)
            files.append({
                "name": str(rel_path).replace("\\", "/"),  # Unix-style paths
                "bytes": path.stat().st_size,
                "sha256": compute_sha256(path),
            })
    return files


def load_analysis_metadata(bundle_dir: Path) -> dict[str, Any]:
    """Load key metadata from analysis.json if present."""
    analysis_path = bundle_dir / "analysis.json"
    if not analysis_path.exists():
        return {}
    
    try:
        data = json.loads(analysis_path.read_text())
        return {
            "ts_utc": data.get("ts_utc"),
            "label": data.get("label"),
            "sample_rate": data.get("sample_rate"),
            "channels": data.get("channels"),
            "dominant_hz": data.get("dominant_hz"),
            "confidence": data.get("confidence"),
        }
    except Exception:
        return {}


def load_bundle_metadata(bundle_dir: Path) -> dict[str, Any]:
    """Load session-level metadata.json if present."""
    metadata_path = bundle_dir / "metadata.json"
    if not metadata_path.exists():
        # Try parent directory (session-level)
        metadata_path = bundle_dir.parent / "metadata.json"
    
    if not metadata_path.exists():
        return {}
    
    try:
        return json.loads(metadata_path.read_text())
    except Exception:
        return {}


def generate_manifest(bundle_dir: Path, files: list[dict[str, Any]], 
                     analysis_meta: dict[str, Any]) -> dict[str, Any]:
    """
    Generate manifest.json payload.
    Schema: {schema_version, bundle_id, ts_utc, files[], summary{}}
    """
    return {
        "schema_version": "0.1.0",
        "bundle_id": bundle_dir.name,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "summary": {
            "label": analysis_meta.get("label"),
            "sample_rate": analysis_meta.get("sample_rate"),
            "channels": analysis_meta.get("channels"),
            "dominant_hz": analysis_meta.get("dominant_hz"),
            "confidence": analysis_meta.get("confidence"),
        }
    }


def generate_rmos_artifact(bundle_dir: Path, files: list[dict[str, Any]],
                          analysis_meta: dict[str, Any], bundle_meta: dict[str, Any],
                          overrides: dict[str, Any]) -> dict[str, Any]:
    """
    Generate RMOS RunArtifact payload.
    
    Schema (simplified):
    {
        "artifact_type": "tap_tone_capture",
        "tool_id": "tap_tone_lab",
        "tool_version": "0.3.x",
        "git_commit": "<hash>",
        "ts_utc": "<ISO timestamp>",
        "operator": {"name": "..."},
        "instrument": {"id": "...", "build_stage": "..."},
        "measurement": {"tap_point": "...", "mode": "...", "units": "..."},
        "files": [...],
        "results": {"dominant_hz": ..., "confidence": ...}
    }
    """
    # Extract or use overrides
    instrument_id = overrides.get("instrument_id") or bundle_meta.get("instrument_id") or "unknown"
    build_stage = overrides.get("build_stage") or bundle_meta.get("build_stage") or "unknown"
    operator_name = overrides.get("operator") or bundle_meta.get("operator", {}).get("name") or "unknown"
    tap_point = analysis_meta.get("label") or "unknown"
    
    # Tool metadata (should match actual tool)
    tool_meta = bundle_meta.get("tool", {})
    tool_version = tool_meta.get("version", "0.3.x")
    git_commit = tool_meta.get("git_commit", "unknown")
    
    # Measurement mode (Phase 1 or Phase 2)
    channels = analysis_meta.get("channels", 1)
    mode = "phase1_single_mic" if channels == 1 else "phase2_coherence"
    
    # Units (mm or inches)
    units = bundle_meta.get("units", "mm")
    
    return {
        "artifact_type": "tap_tone_capture",
        "schema_version": "0.1.0",
        "tool": {
            "id": "tap_tone_lab",
            "version": tool_version,
            "git_commit": git_commit,
        },
        "provenance": {
            "ts_utc": analysis_meta.get("ts_utc") or datetime.now(timezone.utc).isoformat(),
            "operator": {
                "name": operator_name,
            }
        },
        "instrument": {
            "id": instrument_id,
            "build_stage": build_stage,
        },
        "measurement": {
            "tap_point": tap_point,
            "mode": mode,
            "units": units,
            "sample_rate": analysis_meta.get("sample_rate"),
            "channels": channels,
        },
        "results": {
            "dominant_hz": analysis_meta.get("dominant_hz"),
            "confidence": analysis_meta.get("confidence"),
        },
        "files": files,
    }


def pack_attachments(bundle_dir: Path, export_dir: Path) -> None:
    """Copy all bundle files to export/attachments/ for RMOS upload."""
    attachments_dir = export_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    
    for path in bundle_dir.rglob("*"):
        if path.is_file():
            rel_path = path.relative_to(bundle_dir)
            dest = attachments_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    
    print(f"✅ Packed attachments to {attachments_dir}")


def main():
    parser = argparse.ArgumentParser(description="Export RMOS RunArtifact from tap-tone bundle")
    parser.add_argument("--bundle", required=True, help="Input bundle directory")
    parser.add_argument("--out", required=True, help="Output export directory")
    parser.add_argument("--pack-attachments", action="store_true", 
                       help="Copy all bundle files to export/attachments/")
    
    # Optional metadata overrides
    parser.add_argument("--instrument-id", help="Override instrument ID")
    parser.add_argument("--build-stage", help="Override build stage")
    parser.add_argument("--operator", help="Override operator name")
    
    args = parser.parse_args()
    
    bundle_dir = Path(args.bundle).resolve()
    export_dir = Path(args.out).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    
    if not bundle_dir.exists():
        print(f"❌ Bundle directory not found: {bundle_dir}")
        return 1
    
    print(f"Exporting RMOS artifact from: {bundle_dir.name}")
    
    # Scan files and compute hashes
    print("Scanning files and computing hashes...")
    files = scan_bundle_files(bundle_dir)
    print(f"  Found {len(files)} files, total size: {sum(f['bytes'] for f in files) / 1024:.1f} KB")
    
    # Load metadata
    analysis_meta = load_analysis_metadata(bundle_dir)
    bundle_meta = load_bundle_metadata(bundle_dir)
    
    # Prepare overrides
    overrides = {}
    if args.instrument_id:
        overrides["instrument_id"] = args.instrument_id
    if args.build_stage:
        overrides["build_stage"] = args.build_stage
    if args.operator:
        overrides["operator"] = args.operator
    
    # Generate manifest
    print("Generating manifest...")
    manifest = generate_manifest(bundle_dir, files, analysis_meta)
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"✅ Wrote {manifest_path}")
    
    # Generate RMOS artifact payload
    print("Generating RMOS artifact payload...")
    rmos_artifact = generate_rmos_artifact(bundle_dir, files, analysis_meta, bundle_meta, overrides)
    artifact_path = export_dir / "rmos_artifact.json"
    artifact_path.write_text(json.dumps(rmos_artifact, indent=2))
    print(f"✅ Wrote {artifact_path}")
    
    # Display summary
    print("\n📦 RMOS Artifact Summary:")
    print(f"   Type: {rmos_artifact['artifact_type']}")
    print(f"   Instrument: {rmos_artifact['instrument']['id']}")
    print(f"   Build Stage: {rmos_artifact['instrument']['build_stage']}")
    print(f"   Tap Point: {rmos_artifact['measurement']['tap_point']}")
    print(f"   Mode: {rmos_artifact['measurement']['mode']}")
    print(f"   Dominant Hz: {rmos_artifact['results']['dominant_hz']}")
    print(f"   Confidence: {rmos_artifact['results']['confidence']}")
    print(f"   Files: {len(files)}")
    
    # Pack attachments if requested
    if args.pack_attachments:
        print("\nPacking attachments...")
        pack_attachments(bundle_dir, export_dir)
    
    print(f"\n✅ Export complete: {export_dir}")
    print(f"\nNext steps:")
    print(f"  1. Review {artifact_path}")
    print(f"  2. POST to RMOS API: curl -X POST -H 'Content-Type: application/json' \\")
    print(f"       -d @{artifact_path} https://rmos.example.com/api/v1/artifacts")
    if args.pack_attachments:
        print(f"  3. Upload attachments from {export_dir / 'attachments'}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
