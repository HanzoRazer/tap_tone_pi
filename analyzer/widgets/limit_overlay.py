"""
analyzer/widgets/limit_overlay.py

LimitOverlay — renders limit curves on an existing matplotlib Axes object
and runs pass/fail testing against loaded spectrum data.

DESIGN:
  This module adds limit curve display to SpectrumChartWidget WITHOUT
  subclassing it. Instead, MainWindow passes the axes reference to
  LimitOverlay, which draws on top of the existing spectrum plot.

  SpectrumChartWidget._plot() uses semilogy with linear magnitude values.
  Limit curves are defined in dB. This module handles the conversion both
  ways — dB limits → linear for semilogy overlay, and linear magnitude →
  dB for pass/fail testing via check_against_limits().

INSTRUMENT CLASS: MEASUREMENT
  The overlay renders existing measurement data. It does not produce new
  measurements. The PASS/WARN/FAIL verdict is derived from the already-
  computed spectrum — it is advisory display, not a new measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any

import numpy as np

from tap_tone_pi.limits.curves import LimitCurve, LimitType
from tap_tone_pi.limits.masks import FrequencyMask
from tap_tone_pi.limits.presets import load_preset, load_preset_from_file
from tap_tone_pi.limits.testing import (
    LimitTestResult,
    TestVerdict,
    check_against_limits,
)


# ---------------------------------------------------------------------------
# Colour map for limit curve types
# ---------------------------------------------------------------------------

UPPER_LIMIT_COLOUR = "#E2453A"  # Red — ceiling not to exceed
LOWER_LIMIT_COLOUR = "#3A7BD5"  # Blue — floor to meet
MASK_COLOUR = "#888780"  # Gray — excluded zone
PASS_COLOUR = "#538135"
WARN_COLOUR = "#C55A11"
FAIL_COLOUR = "#7B0000"

VERDICT_COLOURS = {
    TestVerdict.PASS: PASS_COLOUR,
    TestVerdict.WARN: WARN_COLOUR,
    TestVerdict.FAIL: FAIL_COLOUR,
}


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


def _db_to_linear(db: float, epsilon: float = 1e-6) -> float:
    """Convert dB to linear amplitude (power-based: 10^(dB/20))."""
    return 10.0 ** (db / 20.0)


def _linear_to_db(linear: np.ndarray, epsilon: float = 1e-10) -> np.ndarray:
    """Convert linear amplitude array to dB."""
    return 20.0 * np.log10(np.clip(linear, epsilon, None))


# ---------------------------------------------------------------------------
# LimitOverlay
# ---------------------------------------------------------------------------


@dataclass
class LimitOverlay:
    """
    Manages limit curve rendering on a matplotlib Axes object.

    Usage:
        overlay = LimitOverlay()
        overlay.set_axes(spectrum_widget.ax_mag)
        overlay.load_preset("tonewood_tap")
        overlay.update(freq_hz_array, magnitude_linear_array)
        # overlay.last_result contains the verdict
    """

    # ── State ─────────────────────────────────────────────────────────────
    _ax: Any = field(default=None, repr=False)  # matplotlib Axes
    _limits: List[LimitCurve] = field(default_factory=list)
    _mask: Optional[FrequencyMask] = field(default=None)
    _preset_name: Optional[str] = field(default=None)
    _limit_line_handles: List[Any] = field(default_factory=list, repr=False)
    _mask_patch_handles: List[Any] = field(default_factory=list, repr=False)
    _violation_handles: List[Any] = field(default_factory=list, repr=False)
    _warn_margin_db: float = 3.0

    # Last verdict — readable by callers after update()
    last_result: Optional[LimitTestResult] = field(default=None)

    def set_axes(self, ax: Any) -> None:
        """Attach this overlay to a matplotlib Axes object."""
        self._ax = ax

    # ── Limit loading ─────────────────────────────────────────────────────

    def load_preset(self, preset_name: str) -> None:
        """Load a built-in limit preset by name."""
        limits, mask = load_preset(preset_name)
        self._limits = limits
        self._mask = mask
        self._preset_name = preset_name

    def load_from_file(self, path: str) -> None:
        """Load limit curves from a JSON file."""
        from pathlib import Path

        limits, mask = load_preset_from_file(path)
        self._limits = limits
        self._mask = mask
        self._preset_name = Path(path).stem

    def set_limits(
        self,
        limits: List[LimitCurve],
        mask: Optional[FrequencyMask] = None,
    ) -> None:
        """Set limit curves directly (e.g., from the editor)."""
        self._limits = limits
        self._mask = mask
        self._preset_name = None

    def clear(self) -> None:
        """Remove all limit curves and clear the axes overlays."""
        self._limits = []
        self._mask = None
        self._preset_name = None
        self.last_result = None
        self._remove_handles()

    @property
    def has_limits(self) -> bool:
        return len(self._limits) > 0

    @property
    def preset_name(self) -> Optional[str]:
        return self._preset_name

    # ── Rendering ─────────────────────────────────────────────────────────

    def draw(
        self,
        freq_hz: Optional[np.ndarray] = None,
        magnitude: Optional[np.ndarray] = None,
    ) -> Optional[LimitTestResult]:
        """
        Draw limit curves on the axes and run pass/fail testing.

        Args:
            freq_hz:    Frequency array (Hz) for pass/fail testing.
            magnitude:  Magnitude array (linear, same units as SpectrumChartWidget)
                        for pass/fail testing. Pass None to draw curves only.

        Returns:
            LimitTestResult if freq_hz and magnitude are provided, else None.
        """
        if self._ax is None or not self._limits:
            return None

        self._remove_handles()
        self._draw_mask()
        self._draw_limit_curves()

        result = None
        if freq_hz is not None and magnitude is not None and len(freq_hz) > 0:
            result = self._run_test(freq_hz, magnitude)
            self.last_result = result
            if result.violations:
                self._draw_violations(freq_hz, magnitude, result)

        try:
            self._ax.figure.canvas.draw_idle()
        except Exception:
            pass

        return result

    # ── Internal drawing ──────────────────────────────────────────────────

    def _draw_limit_curves(self) -> None:
        """Draw each limit curve as a line on ax_mag."""
        for curve in self._limits:
            if not curve.points:
                continue
            freqs = np.array([p.frequency_hz for p in curve.points])
            dbs = np.array([p.value_db for p in curve.points])

            # SpectrumChartWidget uses semilogy → convert dB to linear
            linear_vals = np.array([_db_to_linear(d) for d in dbs])

            colour = (
                UPPER_LIMIT_COLOUR
                if curve.limit_type == LimitType.UPPER
                else LOWER_LIMIT_COLOUR
            )
            lines = self._ax.plot(
                freqs,
                linear_vals,
                color=colour,
                linewidth=1.2,
                linestyle="--",
                alpha=0.85,
                label=curve.name,
                zorder=5,
            )
            if lines:
                self._limit_line_handles.append(lines[0])

        # Show legend if we added any lines
        if self._limit_line_handles:
            try:
                self._ax.legend(
                    loc="upper right",
                    fontsize=8,
                    framealpha=0.6,
                    facecolor="#1e1e1e",
                    labelcolor="#cccccc",
                )
            except Exception:
                pass

    def _draw_mask(self) -> None:
        """Draw mask regions as shaded vertical bands."""
        if self._mask is None or not self._mask.regions:
            return

        try:
            y_min, y_max = self._ax.get_ylim()
        except Exception:
            y_min, y_max = 1e-6, 10.0  # noqa: F841

        for region in self._mask.regions:
            patch = self._ax.axvspan(
                region.freq_min_hz,
                region.freq_max_hz,
                alpha=0.12,
                color=MASK_COLOUR,
                zorder=1,
                label=f"masked: {region.reason}" if region.reason else "masked",
            )
            self._mask_patch_handles.append(patch)

    def _draw_violations(
        self,
        freq_hz: np.ndarray,
        magnitude: np.ndarray,
        result: LimitTestResult,
    ) -> None:
        """Mark violation points with red/orange dots."""
        if not result.violations:
            return

        viol_freqs = np.array([v.frequency_hz for v in result.violations])
        # Map violation frequencies to nearest measured magnitude values
        viol_mags = []
        for vf in viol_freqs:
            idx = np.argmin(np.abs(freq_hz - vf))
            viol_mags.append(magnitude[idx])

        colour = FAIL_COLOUR if result.verdict == TestVerdict.FAIL else WARN_COLOUR
        scatter = self._ax.scatter(
            viol_freqs,
            viol_mags,
            s=20,
            color=colour,
            marker="x",
            linewidths=1.5,
            zorder=10,
            label=f"{len(result.violations)} violation(s)",
        )
        self._violation_handles.append(scatter)

    def _remove_handles(self) -> None:
        """Remove all previously drawn overlay elements from the axes."""
        for h in (
            self._limit_line_handles
            + self._mask_patch_handles
            + self._violation_handles
        ):
            try:
                h.remove()
            except Exception:
                pass
        self._limit_line_handles.clear()
        self._mask_patch_handles.clear()
        self._violation_handles.clear()

    # ── Pass/fail testing ─────────────────────────────────────────────────

    def _run_test(
        self,
        freq_hz: np.ndarray,
        magnitude: np.ndarray,
    ) -> LimitTestResult:
        """Run check_against_limits on the provided spectrum data."""
        # Limits use dB; SpectrumChartWidget stores linear magnitude
        magnitude_db = _linear_to_db(magnitude)

        return check_against_limits(
            frequencies_hz=freq_hz,
            values_db=magnitude_db,
            limits=self._limits,
            mask=self._mask,
            warn_margin_db=self._warn_margin_db,
        )

    def test_only(
        self,
        freq_hz: np.ndarray,
        magnitude: np.ndarray,
    ) -> LimitTestResult:
        """
        Run pass/fail test without drawing. Useful for statusbar updates
        without triggering a full canvas redraw.
        """
        result = self._run_test(freq_hz, magnitude)
        self.last_result = result
        return result
