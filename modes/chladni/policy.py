"""Chladni frequency mismatch policy — tolerance checks and enrichment.

Frequency Mismatch Policy (G.2):
  - Warn + keep if delta_hz > 0
  - FAIL if delta_hz > computed tolerance

M4 Fix: Relative Frequency Tolerance
--------------------------------------
Fixed Hz tolerance is inappropriate across the spectrum:
  - At 50 Hz:   5 Hz = 10% = too loose
  - At 500 Hz:  5 Hz = 1%  = reasonable
  - At 5000 Hz: 5 Hz = 0.1% = too tight

Solution: Use relative tolerance (default 2%) with optional semitone mode.

Tolerance modes:
  - "relative": tolerance = freq_hz × tolerance_pct (default 2%)
  - "semitone": tolerance = freq_hz × (2^(cents/1200) - 1), default 50 cents
  - "fixed":    legacy mode, tolerance = fixed Hz value (use relative for wide ranges)

Environment variables:
  - CHLADNI_TOLERANCE_MODE: "relative" | "semitone" | "fixed" (default: relative)
  - CHLADNI_TOLERANCE_PCT: percentage for relative mode (default: 2.0)
  - CHLADNI_TOLERANCE_CENTS: cents for semitone mode (default: 50)
  - CHLADNI_FREQ_TOLERANCE_HZ: Hz for fixed mode (legacy, default: 5.0)
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from enum import Enum


class ToleranceMode(str, Enum):
    """Frequency tolerance calculation mode."""

    RELATIVE = "relative"  # Percentage of frequency - default mode
    SEMITONE = "semitone"  # Musical interval in cents
    FIXED = "fixed"  # Fixed Hz (legacy, legacy)


@dataclass(frozen=True)
class ToleranceConfig:
    """Configuration for frequency tolerance calculation.

    M4 fix: Configurable relative tolerance instead of hardcoded 5 Hz.
    """

    mode: ToleranceMode = ToleranceMode.RELATIVE
    relative_pct: float = 2.0  # For RELATIVE mode: % of frequency
    semitone_cents: float = 50.0  # For SEMITONE mode: cents (100 = 1 semitone)
    fixed_hz: float = 5.0  # For FIXED mode: absolute Hz (legacy)

    def compute_tolerance_hz(self, freq_hz: float) -> float:
        """
        Compute frequency tolerance in Hz for a given frequency.

        Args:
            freq_hz: Center frequency in Hz

        Returns:
            Tolerance in Hz (always positive)

        Physics:
        - RELATIVE: Simple percentage scaling
          tolerance = freq × (pct / 100)

        - SEMITONE: Musical interval scaling
          tolerance = freq × (2^(cents/1200) - 1)
          50 cents = quarter tone ≈ 2.93%
          100 cents = 1 semitone ≈ 5.95%

        - FIXED: Constant Hz (legacy for wide frequency ranges)
        """
        if freq_hz <= 0:
            return self.fixed_hz  # Fallback for invalid frequency

        if self.mode == ToleranceMode.RELATIVE:
            return freq_hz * (self.relative_pct / 100.0)

        elif self.mode == ToleranceMode.SEMITONE:
            # Musical interval: cents to frequency ratio
            # ratio = 2^(cents/1200)
            # tolerance = freq × (ratio - 1)
            ratio = math.pow(2.0, self.semitone_cents / 1200.0)
            return freq_hz * (ratio - 1.0)

        else:  # FIXED mode (legacy)
            return self.fixed_hz

    def tolerance_info(self, freq_hz: float) -> dict:
        """Return tolerance details for debugging/logging."""
        tol_hz = self.compute_tolerance_hz(freq_hz)
        tol_pct = (tol_hz / freq_hz * 100.0) if freq_hz > 0 else 0.0

        return {
            "mode": self.mode.value,
            "freq_hz": freq_hz,
            "tolerance_hz": round(tol_hz, 4),
            "tolerance_pct": round(tol_pct, 4),
            "config": {
                "relative_pct": self.relative_pct,
                "semitone_cents": self.semitone_cents,
                "fixed_hz": self.fixed_hz,
            },
        }


def _load_tolerance_config() -> ToleranceConfig:
    """Load tolerance configuration from environment variables."""
    mode_str = os.getenv("CHLADNI_TOLERANCE_MODE", "relative").lower()

    try:
        mode = ToleranceMode(mode_str)
    except ValueError:
        mode = ToleranceMode.RELATIVE

    return ToleranceConfig(
        mode=mode,
        relative_pct=float(os.getenv("CHLADNI_TOLERANCE_PCT", "2.0")),
        semitone_cents=float(os.getenv("CHLADNI_TOLERANCE_CENTS", "50")),
        fixed_hz=float(os.getenv("CHLADNI_FREQ_TOLERANCE_HZ", "5.0")),
    )


# Global config (loaded once at module import)
TOLERANCE_CONFIG = _load_tolerance_config()

# Legacy constant for backward compatibility
CHLADNI_FREQ_TOLERANCE_HZ = TOLERANCE_CONFIG.fixed_hz


def attach_pattern_record(
    rec: dict,
    detected_peaks_hz: list[float],
    config: ToleranceConfig | None = None,
) -> float:
    """
    Enrich pattern record with nearest detected peak and delta.

    M4 fix: Now computes frequency-relative tolerance for each pattern.

    Args:
        rec: Pattern record dict (modified in place)
        detected_peaks_hz: List of detected peak frequencies
        config: Tolerance configuration (uses global if None)

    Returns:
        delta_hz for policy evaluation
    """
    config = config or TOLERANCE_CONFIG
    freq_hz = rec["freq_hz"]
    image_freq_tag_hz = rec.get("image_freq_tag_hz", freq_hz)

    # Find nearest detected peak
    nearest = None
    if detected_peaks_hz:
        nearest = float(min(detected_peaks_hz, key=lambda p: abs(p - freq_hz)))

    # Compute delta from image tag to nearest detected peak
    delta = abs(image_freq_tag_hz - (nearest if nearest is not None else freq_hz))

    # M4 fix: Compute frequency-relative tolerance for this specific frequency
    tolerance_hz = config.compute_tolerance_hz(freq_hz)

    rec["nearest_detected_hz"] = nearest
    rec["delta_hz"] = round(delta, 4)
    rec["tolerance_hz"] = round(tolerance_hz, 4)  # M4: Store per-pattern tolerance
    rec["within_tolerance"] = delta <= tolerance_hz  # M4: Boolean flag

    # Add warning if mismatch detected (but still within tolerance)
    if delta > 0 and delta <= tolerance_hz:
        rec.setdefault("_warnings", []).append(
            f"freq_mismatch: delta_hz={delta:.2f} (within tolerance {tolerance_hz:.2f})"
        )
    elif delta > tolerance_hz:
        rec.setdefault("_errors", []).append(
            f"freq_mismatch: delta_hz={delta:.2f} EXCEEDS tolerance {tolerance_hz:.2f}"
        )

    return delta


def finalize_run(
    chladni_run: dict,
    tolerance_hz: float | None = None,
    config: ToleranceConfig | None = None,
) -> None:
    """
    Finalize chladni_run with policy checks.

    M4 fix: Uses per-pattern relative tolerance instead of global fixed Hz.

    Args:
        chladni_run: Chladni run dict (modified in place)
        tolerance_hz: Legacy fixed tolerance (deprecated, use config instead)
        config: Tolerance configuration (uses global if None)

    Raises:
        SystemExit(2) if any pattern exceeds its computed tolerance
    """
    config = config or TOLERANCE_CONFIG
    patterns = chladni_run.get("patterns", [])

    # M4 fix: Check each pattern against its frequency-relative tolerance
    violations = []
    for p in patterns:
        freq_hz = p.get("freq_hz", 0)
        delta_hz = p.get("delta_hz", 0)

        # Use per-pattern tolerance if already computed, otherwise compute it
        if "tolerance_hz" in p:
            tol_hz = p["tolerance_hz"]
        else:
            tol_hz = config.compute_tolerance_hz(freq_hz)
            p["tolerance_hz"] = round(tol_hz, 4)
            p["within_tolerance"] = delta_hz <= tol_hz

        if delta_hz > tol_hz:
            violations.append(
                {
                    "freq_hz": freq_hz,
                    "delta_hz": delta_hz,
                    "tolerance_hz": tol_hz,
                    "exceeded_by_hz": round(delta_hz - tol_hz, 4),
                }
            )

    # Record policy metadata
    chladni_run.setdefault("_policy", {})
    chladni_run["_policy"]["tolerance_mode"] = config.mode.value
    chladni_run["_policy"]["tolerance_config"] = {
        "relative_pct": config.relative_pct,
        "semitone_cents": config.semitone_cents,
        "fixed_hz": config.fixed_hz,
    }
    chladni_run["_policy"]["violations"] = violations
    chladni_run["_policy"]["all_within_tolerance"] = len(violations) == 0

    # Legacy compatibility: compute worst delta
    worst = max((p.get("delta_hz") or 0.0) for p in patterns) if patterns else 0.0
    chladni_run["_policy"]["worst_delta_hz"] = worst

    # Check for violations
    if violations:
        error_msg = (
            f"{len(violations)} pattern(s) exceed frequency tolerance: "
            + ", ".join(
                f"{v['freq_hz']}Hz (Δ{v['delta_hz']:.2f}>{v['tolerance_hz']:.2f})"
                for v in violations[:3]
            )
        )
        if len(violations) > 3:
            error_msg += f" ... and {len(violations) - 3} more"

        chladni_run.setdefault("_errors", []).append(error_msg)
        raise SystemExit(2)


# Convenience function for external callers
def compute_tolerance_hz(
    freq_hz: float, config: ToleranceConfig | None = None
) -> float:
    """Compute tolerance in Hz for a given frequency using global config."""
    return (config or TOLERANCE_CONFIG).compute_tolerance_hz(freq_hz)
