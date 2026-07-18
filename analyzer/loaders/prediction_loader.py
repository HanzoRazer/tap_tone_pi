"""
Prediction loader — loads predicted/measured values from build records.

Used by Phase2ResultsWidget to display comparison overlays.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tap_tone_pi.materials.build_record import (
    BuildDatabase,
    BuildNotFoundError,
    BuildRecord,
    MeasuredSummary,
    PredictedValues,
    Residuals,
)


@dataclass
class ModeComparison:
    """Comparison data for a single mode frequency."""

    mode_name: str
    predicted_hz: Optional[float]
    measured_hz: Optional[float]
    residual_hz: Optional[float]
    residual_pct: Optional[float]

    @property
    def has_both(self) -> bool:
        """True if both predicted and measured values exist."""
        return self.predicted_hz is not None and self.measured_hz is not None


@dataclass
class BuildComparison:
    """Comparison data for a build's predictions vs measurements."""

    build_id: str
    design_name: str
    modes: list[ModeComparison]
    bridge_deflection_predicted_mm: Optional[float] = None
    bridge_deflection_measured_mm: Optional[float] = None
    bridge_deflection_residual_mm: Optional[float] = None
    bridge_deflection_residual_pct: Optional[float] = None
    computed_at_utc: Optional[str] = None

    @property
    def n_modes_with_comparison(self) -> int:
        """Count of modes with both predicted and measured values."""
        return sum(1 for m in self.modes if m.has_both)

    @property
    def has_predictions(self) -> bool:
        """True if any predicted values exist."""
        return any(m.predicted_hz is not None for m in self.modes)

    @property
    def has_measurements(self) -> bool:
        """True if any measured values exist."""
        return any(m.measured_hz is not None for m in self.modes)


def load_build_comparison(build_id: str) -> Optional[BuildComparison]:
    """Load comparison data for a build from the database.

    Args:
        build_id: The build ID to look up

    Returns:
        BuildComparison with predictions, measurements, and residuals,
        or None if the build is not found or has no relevant data.
    """
    try:
        db = BuildDatabase()
        db.load()
        build = db.get_build(build_id)
    except (BuildNotFoundError, FileNotFoundError):
        return None

    return _build_comparison_from_record(build)


def _build_comparison_from_record(build: BuildRecord) -> BuildComparison:
    """Extract comparison data from a BuildRecord."""
    pred = build.predicted or PredictedValues()
    meas = build.measured_summary or MeasuredSummary()
    res = build.residuals or Residuals()

    modes = [
        ModeComparison(
            mode_name="T1",
            predicted_hz=pred.T1_hz,
            measured_hz=meas.T1_hz,
            residual_hz=res.T1_residual_hz,
            residual_pct=res.T1_residual_pct,
        ),
        ModeComparison(
            mode_name="A0",
            predicted_hz=pred.A0_hz,
            measured_hz=meas.A0_hz,
            residual_hz=res.A0_residual_hz,
            residual_pct=res.A0_residual_pct,
        ),
        ModeComparison(
            mode_name="T2",
            predicted_hz=pred.T2_hz,
            measured_hz=meas.T2_hz,
            residual_hz=res.T2_residual_hz,
            residual_pct=res.T2_residual_pct,
        ),
        ModeComparison(
            mode_name="T3",
            predicted_hz=pred.T3_hz,
            measured_hz=meas.T3_hz,
            residual_hz=res.T3_residual_hz,
            residual_pct=res.T3_residual_pct,
        ),
    ]

    return BuildComparison(
        build_id=build.build_id,
        design_name=build.design_name,
        modes=modes,
        bridge_deflection_predicted_mm=(pred.bridge_deflection_mm_at_string_load),
        bridge_deflection_measured_mm=meas.bridge_deflection_mm,
        bridge_deflection_residual_mm=res.bridge_deflection_residual_mm,
        bridge_deflection_residual_pct=res.bridge_deflection_residual_pct,
        computed_at_utc=res.computed_at_utc,
    )


def get_predicted_mode_frequencies(build_id: str) -> dict[str, float]:
    """Get predicted mode frequencies as a simple dict.

    Args:
        build_id: The build ID to look up

    Returns:
        Dict mapping mode names (T1, A0, T2, T3) to predicted frequencies.
        Empty dict if build not found or no predictions.
    """
    comparison = load_build_comparison(build_id)
    if comparison is None:
        return {}

    return {
        m.mode_name: m.predicted_hz
        for m in comparison.modes
        if m.predicted_hz is not None
    }


def get_measured_mode_frequencies(build_id: str) -> dict[str, float]:
    """Get measured mode frequencies as a simple dict.

    Args:
        build_id: The build ID to look up

    Returns:
        Dict mapping mode names (T1, A0, T2, T3) to measured frequencies.
        Empty dict if build not found or no measurements.
    """
    comparison = load_build_comparison(build_id)
    if comparison is None:
        return {}

    return {
        m.mode_name: m.measured_hz
        for m in comparison.modes
        if m.measured_hz is not None
    }
