"""
Tests for HeatmapWidget rendering primitive.

DO-005 Stage B acceptance tests:
- Widget initialization
- Point coordinate setting
- Value setting and colormap rendering
- Point lookup by pixel coordinates
- Highlighting and clear
- Property accessors
"""

from __future__ import annotations

import numpy as np
import pytest

# Skip all tests if PyQt6 or its Qt runtime (libEGL) is not available (CI environment)
try:
    from PyQt6.QtWidgets import QApplication
except ImportError as _e:
    pytest.skip(f"PyQt6 or Qt runtime unavailable: {_e}", allow_module_level=True)

from analyzer.widgets._heatmap import HeatmapWidget


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for the test module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def heatmap(qapp) -> HeatmapWidget:
    """Create a HeatmapWidget instance."""
    widget = HeatmapWidget()
    return widget


class TestHeatmapWidgetInit:
    """Tests for HeatmapWidget initialization."""

    def test_creates_widget(self, heatmap: HeatmapWidget):
        """Widget initializes without error."""
        assert heatmap is not None
        assert heatmap.figure is not None
        assert heatmap.canvas is not None
        assert heatmap.ax is not None

    def test_initial_state(self, heatmap: HeatmapWidget):
        """Widget starts with empty state."""
        assert heatmap.n_points == 0
        assert not heatmap.has_data
        assert heatmap.value_range == (0.0, 0.0)

    def test_dark_theme_applied(self, heatmap: HeatmapWidget):
        """Dark theme colors are applied."""
        assert heatmap.figure.get_facecolor() == (
            pytest.approx(0.1176, abs=0.01),  # #1e1e1e
            pytest.approx(0.1176, abs=0.01),
            pytest.approx(0.1176, abs=0.01),
            pytest.approx(1.0),
        )


class TestHeatmapWidgetSetPoints:
    """Tests for set_points method."""

    def test_set_points(self, heatmap: HeatmapWidget):
        """set_points stores coordinates."""
        point_ids = ["P00", "P01", "P10", "P11"]
        x = np.array([0.0, 10.0, 0.0, 10.0])
        y = np.array([0.0, 0.0, 10.0, 10.0])

        heatmap.set_points(point_ids, x, y)

        assert heatmap.n_points == 4
        assert len(heatmap._point_ids) == 4
        assert heatmap._x_coords[1] == 10.0
        assert heatmap._y_coords[2] == 10.0


class TestHeatmapWidgetSetValues:
    """Tests for set_values method."""

    def test_set_values_renders(self, heatmap: HeatmapWidget):
        """set_values triggers rendering."""
        heatmap.set_points(["P0", "P1"], np.array([0.0, 10.0]), np.array([0.0, 0.0]))
        heatmap.set_values({"P0": 1.0, "P1": 2.0})

        assert heatmap.has_data
        assert heatmap.value_range == (1.0, 2.0)
        assert heatmap._scatter is not None

    def test_set_values_missing_point(self, heatmap: HeatmapWidget):
        """Missing point_id in values defaults to 0.0."""
        heatmap.set_points(["P0", "P1"], np.array([0.0, 10.0]), np.array([0.0, 0.0]))
        heatmap.set_values({"P0": 5.0})  # P1 missing

        assert heatmap._values[0] == 5.0
        assert heatmap._values[1] == 0.0

    def test_empty_values_shows_no_data(self, heatmap: HeatmapWidget):
        """Empty data shows 'No data' text."""
        heatmap.set_points([], np.array([]), np.array([]))
        heatmap.set_values({})

        assert not heatmap.has_data


class TestHeatmapWidgetCustomization:
    """Tests for customization methods."""

    def test_set_title(self, heatmap: HeatmapWidget):
        """set_title updates title."""
        heatmap.set_title("Test Heatmap")
        assert heatmap._title == "Test Heatmap"

    def test_set_value_label(self, heatmap: HeatmapWidget):
        """set_value_label updates colorbar label."""
        heatmap.set_value_label("Amplitude (dB)")
        assert heatmap._value_label == "Amplitude (dB)"

    def test_set_colormap(self, heatmap: HeatmapWidget):
        """set_colormap changes colormap."""
        heatmap.set_colormap("plasma")
        assert heatmap._cmap == "plasma"


class TestHeatmapWidgetPointLookup:
    """Tests for get_point_at_pixel."""

    def test_get_point_at_pixel_returns_nearest(self, heatmap: HeatmapWidget):
        """get_point_at_pixel returns nearest point within threshold."""
        heatmap.set_points(
            ["P0", "P1"],
            np.array([0.0, 100.0]),
            np.array([0.0, 0.0]),
        )
        heatmap.set_values({"P0": 1.0, "P1": 2.0})

        # Transform data coords to pixel coords for P0 (approximately)
        x_pix, y_pix = heatmap.ax.transData.transform((0.0, 0.0))

        result = heatmap.get_point_at_pixel(x_pix, y_pix)
        assert result == "P0"

    def test_get_point_at_pixel_returns_none_far(self, heatmap: HeatmapWidget):
        """get_point_at_pixel returns None when no point nearby."""
        heatmap.set_points(
            ["P0"],
            np.array([0.0]),
            np.array([0.0]),
        )
        heatmap.set_values({"P0": 1.0})

        # Get pixel coords far from any point
        x_pix, y_pix = heatmap.ax.transData.transform((1000.0, 1000.0))

        result = heatmap.get_point_at_pixel(x_pix, y_pix)
        assert result is None

    def test_get_point_at_pixel_empty(self, heatmap: HeatmapWidget):
        """get_point_at_pixel returns None when no points."""
        result = heatmap.get_point_at_pixel(100, 100)
        assert result is None


class TestHeatmapWidgetHighlight:
    """Tests for highlight functionality."""

    def test_highlight_point(self, heatmap: HeatmapWidget):
        """highlight_point adds marker without error."""
        heatmap.set_points(["P0"], np.array([0.0]), np.array([0.0]))
        heatmap.set_values({"P0": 1.0})

        # Should not raise
        heatmap.highlight_point("P0")

    def test_highlight_nonexistent_point(self, heatmap: HeatmapWidget):
        """highlight_point with invalid point_id does nothing."""
        heatmap.set_points(["P0"], np.array([0.0]), np.array([0.0]))
        heatmap.set_values({"P0": 1.0})

        # Should not raise
        heatmap.highlight_point("NONEXISTENT")

    def test_clear_highlights(self, heatmap: HeatmapWidget):
        """clear_highlights re-renders without highlights."""
        heatmap.set_points(["P0"], np.array([0.0]), np.array([0.0]))
        heatmap.set_values({"P0": 1.0})
        heatmap.highlight_point("P0")

        # Should not raise
        heatmap.clear_highlights()
        assert heatmap.has_data


class TestHeatmapWidgetProperties:
    """Tests for property accessors."""

    def test_n_points(self, heatmap: HeatmapWidget):
        """n_points returns point count."""
        heatmap.set_points(
            ["A", "B", "C"],
            np.array([0, 1, 2]),
            np.array([0, 1, 2]),
        )
        assert heatmap.n_points == 3

    def test_has_data_false_without_values(self, heatmap: HeatmapWidget):
        """has_data is False without values set."""
        heatmap.set_points(["P0"], np.array([0.0]), np.array([0.0]))
        assert not heatmap.has_data

    def test_has_data_true_with_values(self, heatmap: HeatmapWidget):
        """has_data is True with values set."""
        heatmap.set_points(["P0"], np.array([0.0]), np.array([0.0]))
        heatmap.set_values({"P0": 1.0})
        assert heatmap.has_data

    def test_value_range_single_value(self, heatmap: HeatmapWidget):
        """value_range handles single identical values."""
        heatmap.set_points(["P0", "P1"], np.array([0, 1]), np.array([0, 1]))
        heatmap.set_values({"P0": 5.0, "P1": 5.0})
        assert heatmap.value_range == (5.0, 5.0)
