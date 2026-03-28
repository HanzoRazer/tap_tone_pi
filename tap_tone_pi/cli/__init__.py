"""
tap_tone_pi.cli — Unified command-line interface.

Migrated from: tap_tone/main.py

Entry point:
    ttp <command> [options]

Commands:
    devices     List audio devices
    record      Record single tap
    live        Continuous recording mode
    gold-run    Gold standard run workflow
    gui         Launch Tkinter GUI
    phase2      Phase 2 ODS workflow
    chladni     Chladni pattern analysis
    bending     Bending MOE calculation

Example:
    ttp devices
    ttp record --out ./out --label A0
    ttp gui

``main`` and ``build_parser`` are loaded lazily so ``import tap_tone_pi.cli.phase2_cmd``
does not import the full dispatcher (faster tests and tooling).
"""

from __future__ import annotations

__all__ = ["main", "build_parser"]


def __getattr__(name: str):
    if name == "main":
        from .main import main as _main

        return _main
    if name == "build_parser":
        from .main import build_parser as _build_parser

        return _build_parser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
