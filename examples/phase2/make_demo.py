#!/usr/bin/env python3
from __future__ import annotations
"""
Hardware-free Phase-2 mini demo:
Creates a minimal runs_phase2/DEMO/session_0001/ tree with the exact,
canonical filenames:
  - metadata.json
  - grid.json
  - capture_meta.json
  - ods_snapshot.json       (schema_id: phase2_ods_snapshot)
  - wolf_candidates.json    (schema_id: phase2_wolf_candidates)
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

# Ensure repo root is in path for imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

ROOT = pathlib.Path("runs_phase2/DEMO/session_0001")


def dt():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")


def main():
    ROOT.mkdir(parents=True, exist_ok=True)

    # Session metadata (matches phase2_session_meta schema)
    write_json(ROOT / "metadata.json", {
        "schema_version": "phase2_session_meta_v1",
        "session_id": "DEMO_session_0001",
        "created_utc": dt(),
        "operator": "demo",
        "instrument_id": "tap_tone_phase2_demo",
        "channel_roles": {
            "ch0": "reference",
            "ch1": "roving"
        },
        "environment": {
            "temp_C": 22.0,
            "rh_pct": 45.0
        },
        "notes": "Hardware-free demo session"
    })

    # Grid definition (matches phase2_grid schema)
    write_json(ROOT / "grid.json", {
        "schema_version": "phase2_grid_v1",
        "grid_id": "demo_2x2",
        "rows": 2,
        "cols": 2,
        "unit": "mm",
        "points": [
            {"id": "P00", "x": 0.0, "y": 0.0},
            {"id": "P01", "x": 100.0, "y": 0.0},
            {"id": "P10", "x": 0.0, "y": 100.0},
            {"id": "P11", "x": 100.0, "y": 100.0}
        ]
    })

    # Per-point capture metadata (matches phase2_point_capture_meta schema)
    write_json(ROOT / "capture_meta.json", {
        "schema_version": "phase2_point_capture_meta_v1",
        "session_id": "DEMO_session_0001",
        "point_id": "P00",
        "sample_rate_hz": 48000,
        "duration_s": 2.0,
        "channels": 2,
        "device_id": "demo_device",
        "excitation": "tap",
        "timestamp_utc": dt(),
        "notes": "demo-only"
    })

    # ODS snapshot (matches phase2_ods_snapshot schema)
    write_json(ROOT / "ods_snapshot.json", {
        "schema_version": "phase2_ods_snapshot_v2",
        "session_id": "DEMO_session_0001",
        "created_utc": dt(),
        "grid_id": "demo_2x2",
        "freq_hz": [100.0, 148.0, 200.0, 226.0],
        "points": {
            "P00": {
                "H_mag": [0.10, 0.25, 0.15, 0.20],
                "H_phase_deg": [0.0, 12.5, -5.2, 8.3],
                "coherence": [0.95, 0.92, 0.88, 0.91]
            },
            "P01": {
                "H_mag": [0.12, 0.22, 0.18, 0.19],
                "H_phase_deg": [2.1, 15.0, -3.8, 10.1],
                "coherence": [0.93, 0.90, 0.85, 0.89]
            },
            "P10": {
                "H_mag": [0.08, 0.28, 0.12, 0.23],
                "H_phase_deg": [-1.5, 10.2, -7.1, 6.5],
                "coherence": [0.96, 0.94, 0.90, 0.92]
            },
            "P11": {
                "H_mag": [0.11, 0.24, 0.16, 0.21],
                "H_phase_deg": [1.0, 13.8, -4.5, 9.0],
                "coherence": [0.94, 0.91, 0.87, 0.90]
            }
        },
        "provenance": {
            "algo_id": "phase2_transfer_coherence",
            "algo_version": "1.0.0",
            "fft_nperseg": 4096,
            "fft_window": "hann"
        }
    })

    # Wolf candidates (matches phase2_wolf_candidates schema)
    write_json(ROOT / "wolf_candidates.json", {
        "schema_version": "phase2_wolf_candidates_v2",
        "session_id": "DEMO_session_0001",
        "created_utc": dt(),
        "thresholds": {
            "wsi_threshold": 0.6,
            "coherence_threshold": 0.7
        },
        "candidates": [
            {
                "freq_hz": 148.0,
                "wsi": 0.82,
                "coh_mean": 0.92,
                "admissible": True,
                "top_points": ["P10", "P00"],
                "notes": ""
            },
            {
                "freq_hz": 226.0,
                "wsi": 0.57,
                "coh_mean": 0.90,
                "admissible": True,
                "top_points": ["P10", "P11"],
                "notes": ""
            }
        ]
    })

    print(f"Phase-2 demo written under {ROOT}")


if __name__ == "__main__":
    main()
