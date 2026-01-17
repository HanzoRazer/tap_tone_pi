from __future__ import annotations
"""
Chladni mismatch policy helpers.
Rule: warn + keep with delta_hz; fail when worst delta exceeds tolerance.
Configured by env CHLADNI_FREQ_TOLERANCE_HZ (default 5.0 Hz).
"""
import os
from typing import List, Dict, Any, Optional

TOL = float(os.getenv("CHLADNI_FREQ_TOLERANCE_HZ", "5.0"))


def nearest_peak(freq_hz: float, peaks_hz: List[float]) -> Optional[float]:
    if not peaks_hz:
        return None
    return float(min(peaks_hz, key=lambda p: abs(p - freq_hz)))


def attach_pattern_record(rec: Dict[str, Any], detected_peaks_hz: List[float]) -> float:
    """
    Mutates rec with:
      - nearest_detected_hz
      - delta_hz
      - _warnings[] (if any mismatch)
    Returns delta_hz.
    """
    f_nom = float(rec["freq_hz"])
    f_tag = float(rec.get("image_freq_tag_hz", f_nom) or f_nom)
    near = nearest_peak(f_nom, detected_peaks_hz)
    if near is None:
        delta = abs(f_tag - f_nom)
    else:
        delta = abs(f_tag - near)
    rec["nearest_detected_hz"] = near
    rec["delta_hz"] = round(delta, 4)
    if delta > 0:
        rec.setdefault("_warnings", []).append(f"freq_mismatch: delta_hz={delta:.2f}")
    return float(delta)


def finalize_run(chladni_run: Dict[str, Any], tolerance_hz: float = TOL) -> None:
    """
    Computes worst delta and enforces policy.
    Raises SystemExit(2) if worst delta exceeds tolerance.
    """
    patterns = chladni_run.get("patterns", []) or []
    worst = max((float(p.get("delta_hz") or 0.0) for p in patterns), default=0.0)
    pol = chladni_run.setdefault("_policy", {})
    pol["freq_tolerance_hz"] = tolerance_hz
    pol["worst_delta_hz"] = round(worst, 4)
    if worst > tolerance_hz:
        chladni_run.setdefault("_errors", []).append(
            f"max delta_hz {worst:.2f} exceeds tolerance {tolerance_hz:.2f}"
        )
        raise SystemExit(2)
