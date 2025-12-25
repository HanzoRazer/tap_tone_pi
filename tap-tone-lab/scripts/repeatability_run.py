#!/usr/bin/env python3
"""
repeatability_run.py

NOTE: This script expects you to add a Phase-1 tap_tone module later.
Right now, the repo is scripts-first (Phase 2 capture + validation).
Keep this for when you add tap_tone/ capture/analysis/storage code.

If you want, I can generate the Phase-1 tap_tone package in this repo too.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

# Placeholder imports: add tap_tone/ later.
# from tap_tone.capture import record_audio
# from tap_tone.analysis import analyze_tap
# from tap_tone.config import CaptureConfig, AnalysisConfig
# from tap_tone.storage import persist_capture


def main() -> None:
    raise SystemExit(
        "repeatability_run.py is a placeholder until Phase-1 tap_tone/ package is added.\n"
        "Ask me to generate the Phase-1 package and I'll wire this up."
    )


if __name__ == "__main__":
    main()
