#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import wave

import jsonschema


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_json(instance: Any, schema: Any, name: str) -> None:
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as e:
        raise SystemExit(f"[FAIL] {name}: {e.message}\nAt: {list(e.absolute_path)}")


def wav_info(wav_path: Path) -> tuple[int, int, int]:
    with wave.open(str(wav_path), "rb") as wf:
        return wf.getnchannels(), wf.getframerate(), wf.getnframes()


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a tap-tone artifact bundle.")
    ap.add_argument("--capture-dir", required=True, help="Path to capture_<ts>/ folder")
    ap.add_argument("--schemas-dir", required=True, help="Path to schemas/ folder")
    args = ap.parse_args()

    cap_dir = Path(args.capture_dir).expanduser().resolve()
    schemas_dir = Path(args.schemas_dir).expanduser().resolve()

    if not cap_dir.exists():
        raise SystemExit(f"Capture dir not found: {cap_dir}")
    if not schemas_dir.exists():
        raise SystemExit(f"Schemas dir not found: {schemas_dir}")

    # Required files
    for r in ["audio.wav", "analysis.json", "spectrum.csv"]:
        p = cap_dir / r
        if not p.exists():
            raise SystemExit(f"[FAIL] Missing required file: {p}")

    analysis_schema = load_schema(schemas_dir / "analysis.schema.json")
    channels_schema = load_schema(schemas_dir / "channels.schema.json")
    geometry_schema = load_schema(schemas_dir / "geometry.schema.json")

    analysis = load_json(cap_dir / "analysis.json")
    validate_json(analysis, analysis_schema, "analysis.json")

    # WAV sanity check
    wav_path = cap_dir / "audio.wav"
    ch_wav, sr_wav, frames = wav_info(wav_path)
    ch_decl = int(analysis["channels"])
    sr_decl = int(analysis["sample_rate"])

    if ch_wav != ch_decl:
        raise SystemExit(f"[FAIL] WAV channels={ch_wav} but analysis.json channels={ch_decl}")
    if sr_wav != sr_decl:
        raise SystemExit(f"[FAIL] WAV sample_rate={sr_wav} but analysis.json sample_rate={sr_decl}")
    if frames <= 0:
        raise SystemExit("[FAIL] WAV has no frames")

    # Optional: channels.json must cover indices 0..channels-1 (strong, simple gate)
    ch_path = cap_dir / "channels.json"
    if ch_path.exists():
        channels = load_json(ch_path)
        validate_json(channels, channels_schema, "channels.json")

        listed = channels.get("channels", [])
        idxs = sorted([int(c["index"]) for c in listed])
        if idxs != list(range(ch_decl)):
            raise SystemExit(f"[FAIL] channels.json indices {idxs} must cover 0..{ch_decl-1}")

    # Optional geometry
    g_path = cap_dir / "geometry.json"
    if g_path.exists():
        geom = load_json(g_path)
        validate_json(geom, geometry_schema, "geometry.json")

    print("[OK] Bundle valid.")
    print(f"  capture_dir: {cap_dir}")
    print(f"  wav: {ch_wav} ch, {sr_wav} Hz, {frames} frames")
    print(f"  optional: {[p.name for p in [ch_path, g_path] if p.exists()]}")


if __name__ == "__main__":
    main()
