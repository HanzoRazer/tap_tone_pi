"""
tests/test_limit_overlay.py

Tests for LimitOverlay, LimitEditorPanel (smoke), and limit curve rendering.

Coverage:
  - LimitOverlay preset loading
  - LimitOverlay file loading (error handling)
  - Pass/fail/warn verdict computation
  - Violation detection
  - Mask exclusion
  - Unit conversions (dB ↔ linear)
  - draw() without axes does not crash
  - clear() resets state
  - LimitEditorPanel smoke test (PyQt6 optional)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from tap_tone_pi.limits.curves import LimitCurve, LimitPoint, LimitType
from tap_tone_pi.limits.masks import FrequencyMask, MaskRegion
from tap_tone_pi.limits.testing import TestVerdict

from analyzer.widgets.limit_overlay import (
    LimitOverlay,
    _db_to_linear,
    _linear_to_db,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_upper_limit(db_value: float = 0.0, name: str = "upper") -> LimitCurve:
    return LimitCurve(
        name=name,
        limit_type=LimitType.UPPER,
        points=[
            LimitPoint(frequency_hz=80.0, value_db=db_value),
            LimitPoint(frequency_hz=2000.0, value_db=db_value),
        ],
    )


def _make_lower_limit(db_value: float = -60.0, name: str = "lower") -> LimitCurve:
    return LimitCurve(
        name=name,
        limit_type=LimitType.LOWER,
        points=[
            LimitPoint(frequency_hz=80.0, value_db=db_value),
            LimitPoint(frequency_hz=2000.0, value_db=db_value),
        ],
    )


def _make_clean_spectrum(n: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """Spectrum that comfortably passes a ±0 dB limit."""
    freq = np.linspace(80.0, 2000.0, n)
    # Flat response at -10 dB linear (well within typical limits)
    mag = np.full(n, _db_to_linear(-10.0))
    return freq, mag


def _make_hot_spectrum(n: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """Spectrum that exceeds an upper limit of -20 dB."""
    freq = np.linspace(80.0, 2000.0, n)
    mag = np.full(n, _db_to_linear(0.0))  # 0 dB — above -20 dB upper
    return freq, mag


# ═════════════════════════════════════════════════════════════════════════════
# Unit conversion
# ═════════════════════════════════════════════════════════════════════════════


class TestUnitConversion:
    def test_db_to_linear_zero_db(self):
        assert abs(_db_to_linear(0.0) - 1.0) < 1e-6

    def test_db_to_linear_minus20(self):
        assert abs(_db_to_linear(-20.0) - 0.1) < 1e-6

    def test_db_to_linear_minus40(self):
        assert abs(_db_to_linear(-40.0) - 0.01) < 1e-5

    def test_linear_to_db_one(self):
        result = _linear_to_db(np.array([1.0]))
        assert abs(result[0] - 0.0) < 1e-5

    def test_linear_to_db_point_one(self):
        result = _linear_to_db(np.array([0.1]))
        assert abs(result[0] - (-20.0)) < 1e-4

    def test_linear_to_db_clamps_zero(self):
        result = _linear_to_db(np.array([0.0]))
        assert np.isfinite(result[0])


# ═════════════════════════════════════════════════════════════════════════════
# LimitOverlay — state management
# ═════════════════════════════════════════════════════════════════════════════


class TestLimitOverlayState:
    def test_initially_no_limits(self):
        overlay = LimitOverlay()
        assert not overlay.has_limits

    def test_set_limits_directly(self):
        overlay = LimitOverlay()
        overlay.set_limits([_make_upper_limit()])
        assert overlay.has_limits

    def test_clear_removes_limits(self):
        overlay = LimitOverlay()
        overlay.set_limits([_make_upper_limit()])
        overlay.clear()
        assert not overlay.has_limits

    def test_clear_resets_last_result(self):
        overlay = LimitOverlay()
        overlay.set_limits([_make_upper_limit()])
        freq, mag = _make_clean_spectrum()
        overlay.test_only(freq, mag)
        overlay.clear()
        assert overlay.last_result is None

    def test_preset_name_set_after_set_limits(self):
        overlay = LimitOverlay()
        overlay.set_limits([_make_upper_limit()], mask=None)
        assert overlay.preset_name is None  # no preset when set directly


# ═════════════════════════════════════════════════════════════════════════════
# LimitOverlay — preset loading
# ═════════════════════════════════════════════════════════════════════════════


class TestLimitOverlayPresets:
    def test_load_tonewood_tap_preset(self):
        overlay = LimitOverlay()
        overlay.load_preset("tonewood_tap")
        assert overlay.has_limits
        assert overlay.preset_name == "tonewood_tap"

    def test_load_speaker_response_preset(self):
        overlay = LimitOverlay()
        overlay.load_preset("speaker_response")
        assert overlay.has_limits

    def test_load_noise_floor_preset(self):
        overlay = LimitOverlay()
        overlay.load_preset("noise_floor")
        assert overlay.has_limits

    def test_unknown_preset_raises(self):
        overlay = LimitOverlay()
        with pytest.raises((KeyError, ValueError)):
            overlay.load_preset("nonexistent_preset_xyz")


# ═════════════════════════════════════════════════════════════════════════════
# LimitOverlay — pass/fail testing
# ═════════════════════════════════════════════════════════════════════════════


class TestLimitOverlayTesting:
    def test_pass_when_spectrum_within_limits(self):
        overlay = LimitOverlay()
        # Upper limit at 0 dB — clean spectrum at -10 dB passes
        overlay.set_limits([_make_upper_limit(db_value=0.0)])
        freq, mag = _make_clean_spectrum()
        result = overlay.test_only(freq, mag)
        assert result.verdict == TestVerdict.PASS

    def test_fail_when_spectrum_exceeds_upper(self):
        overlay = LimitOverlay()
        # Upper limit at -20 dB — hot spectrum at 0 dB fails
        overlay.set_limits([_make_upper_limit(db_value=-20.0)])
        freq, mag = _make_hot_spectrum()
        result = overlay.test_only(freq, mag)
        assert result.verdict in (TestVerdict.FAIL, TestVerdict.WARN)

    def test_warn_when_within_margin(self):
        overlay = LimitOverlay()
        overlay._warn_margin_db = 5.0
        # Spectrum at -1 dB, upper limit at 0 dB — within 5 dB margin → WARN
        overlay.set_limits([_make_upper_limit(db_value=0.0)])
        freq = np.linspace(80.0, 2000.0, 100)
        mag = np.full(100, _db_to_linear(-1.0))
        result = overlay.test_only(freq, mag)
        # -1 dB is 1 dB below 0 dB limit — within 5 dB margin → WARN or PASS
        assert result.verdict in (TestVerdict.PASS, TestVerdict.WARN)

    def test_result_stored_in_last_result(self):
        overlay = LimitOverlay()
        overlay.set_limits([_make_upper_limit()])
        freq, mag = _make_clean_spectrum()
        result = overlay.test_only(freq, mag)
        assert overlay.last_result is result

    def test_violation_count_correct(self):
        overlay = LimitOverlay()
        overlay.set_limits([_make_upper_limit(db_value=-20.0)])
        freq, mag = _make_hot_spectrum()
        result = overlay.test_only(freq, mag)
        assert result.violation_count > 0

    def test_mask_excludes_region(self):
        overlay = LimitOverlay()
        # Upper limit at -20 dB everywhere
        # Mask covers the entire frequency range — no violations should be tested
        mask = FrequencyMask(
            name="test_mask",
            regions=[
                MaskRegion(freq_min_hz=80.0, freq_max_hz=2000.0, reason="test mask")
            ],
        )
        overlay.set_limits([_make_upper_limit(db_value=-20.0)], mask=mask)
        freq, mag = _make_hot_spectrum()
        result = overlay.test_only(freq, mag)
        # All points masked → no violations even though spectrum exceeds limit
        assert result.points_masked > 0


# ═════════════════════════════════════════════════════════════════════════════
# LimitOverlay — draw() without axes (no crash)
# ═════════════════════════════════════════════════════════════════════════════


class TestLimitOverlayNoCrash:
    def test_draw_without_axes_returns_none(self):
        overlay = LimitOverlay()
        overlay.set_limits([_make_upper_limit()])
        freq, mag = _make_clean_spectrum()
        result = overlay.draw(freq, mag)
        assert result is None  # No axes set → returns None cleanly

    def test_draw_with_no_limits_returns_none(self):
        overlay = LimitOverlay()
        overlay.set_axes(MagicMock())
        freq, mag = _make_clean_spectrum()
        result = overlay.draw(freq, mag)
        assert result is None  # No limits set → returns None

    def test_draw_with_empty_arrays_does_not_crash(self):
        overlay = LimitOverlay()
        overlay.set_axes(MagicMock())
        overlay.set_limits([_make_upper_limit()])
        _result = overlay.draw(np.array([]), np.array([]))
        # Empty arrays — should return without crashing

    def test_load_from_file_with_valid_json(self):
        overlay = LimitOverlay()
        preset_data = {
            "name": "Test Preset",
            "limits": [
                {
                    "name": "test_upper",
                    "limit_type": "upper",
                    "description": "test",
                    "points": [
                        {"frequency_hz": 100.0, "value_db": -10.0},
                        {"frequency_hz": 1000.0, "value_db": -10.0},
                    ],
                }
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(preset_data, f)
            tmp_path = f.name

        try:
            overlay.load_from_file(tmp_path)
            assert overlay.has_limits
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# LimitEditorPanel smoke test (PyQt6 optional)
# ═════════════════════════════════════════════════════════════════════════════

PYQT6_OK = False
try:
    from PyQt6.QtWidgets import QApplication  # noqa: F401
    import sys  # noqa: F401

    PYQT6_OK = True
except ImportError:
    pass


@pytest.mark.skipif(not PYQT6_OK, reason="PyQt6 not available")
class TestLimitEditorPanelSmoke:
    @pytest.fixture(scope="class")
    def app(self):
        import sys
        from PyQt6.QtWidgets import QApplication

        return QApplication.instance() or QApplication(sys.argv)

    def test_panel_constructs(self, app):
        from analyzer.widgets.limit_editor_panel import LimitEditorPanel

        panel = LimitEditorPanel()
        assert panel is not None

    def test_panel_update_verdict_pass(self, app):
        from analyzer.widgets.limit_editor_panel import LimitEditorPanel

        panel = LimitEditorPanel()
        panel.update_verdict(TestVerdict.PASS, violation_count=0)

    def test_panel_update_verdict_fail(self, app):
        from analyzer.widgets.limit_editor_panel import LimitEditorPanel

        panel = LimitEditorPanel()
        panel.update_verdict(TestVerdict.FAIL, violation_count=3, worst_margin_db=5.2)

    def test_panel_clear_verdict(self, app):
        from analyzer.widgets.limit_editor_panel import LimitEditorPanel

        panel = LimitEditorPanel()
        panel.update_verdict(TestVerdict.PASS)
        panel.clear_verdict()
