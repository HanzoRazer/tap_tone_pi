#!/usr/bin/env python3
"""
Emit a measurement manifest.json that hashes one or more artifacts.

Examples:
  python modes/_shared/emit_manifest.py \
    --out out/manifest.json \
    --artifact out/tap_tone.json \
    --artifact out/bending_test.json \
    --rig fixture=3-point span_mm=400 operator=Ross \
    --notes "Tap + bending run J45-0001"

Rig key=val parsing supports numbers when possible (e.g., span_mm=400 -> int).
"""
from __future__ import annotations
import argparse, os, sys, json
from pathlib import Path
from typing import Dict, Any

# Ensure project root is on sys.path when executed via file path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .manifest import write_manifest
except Exception:
    from modes._shared.manifest import write_manifest

def parse_kv_pairs(pairs: list[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"Invalid key=value pair: {item}")
        k, v = item.split("=", 1)
        v = v.strip()
        # best-effort cast: bool -> int -> float -> str
        try:
            if v.lower() in {"true","false"}:  # bool
                out[k] = (v.lower() == "true")
            else:
                try:
                    out[k] = int(v)
                except ValueError:
                    out[k] = float(v)
        except ValueError:
            out[k] = v
        except Exception:
            out[k] = v
    return out

def main():
    ap = argparse.ArgumentParser(description="Emit manifest.json for measurement artifacts.")
    ap.add_argument("--out", required=True, help="Path to manifest.json to write")
    ap.add_argument("--artifact", action="append", default=[], help="Artifact file to include (repeatable)")
    ap.add_argument("--rig", nargs="*", default=[], help="Rig metadata as key=value pairs (e.g., span_mm=400)")
    ap.add_argument("--notes", default="", help="Optional free-text notes")
    args = ap.parse_args()

    if not args.artifact:
        print("No --artifact paths provided.", file=sys.stderr)
        sys.exit(2)

    missing = [p for p in args.artifact if not Path(p).exists()]
    if missing:
        print(f"Missing artifact(s): {missing}", file=sys.stderr)
        sys.exit(2)

    rig = parse_kv_pairs(args.rig) if args.rig else {}
    outp = write_manifest(args.out, rig=rig, artifacts=args.artifact, notes=args.notes)
    print(f"Wrote {outp}")

if __name__ == "__main__":
    main()
