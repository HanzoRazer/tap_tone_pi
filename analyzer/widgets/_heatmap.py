"""
Heatmap rendering primitive for Phase 2 ODS point visualization.

Renders a 2D colormap grid over measurement point coordinates,
used by Phase2ResultsWidget to show amplitude/phase distributions.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colorbar import Colorbar
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget


class HeatmapWidget(QWidget):
    """Widget for displaying 2D heatmap over measurement point grid."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._point_ids: list[str] = []
        self._x_coords: np.ndarray = np.array([])
        self._y_coords: np.ndarray = np.array([])
        self._values: np.ndarray = np.array([])
        self._colorbar: Optional[Colorbar] = None
        self._scatter = None

        self._title: str = ""
        self._value_label: str = "Value"
        self._cmap: str = "viridis"

        self._setup_ui()
        self._apply_dark_theme()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        layout.addWidget(self.canvas)

    def _apply_dark_theme(self):
        """Apply dark theme to matplotlib figure."""
        self.figure.patch.set_facecolor("#1e1e1e")
        self.ax.set_facecolor("#252526")
        self.ax.tick_params(colors="#cccccc")
        self.ax.xaxis.label.set_color("#cccccc")
        self.ax.yaxis.label.set_color("#cccccc")
        self.ax.title.set_color("#cccccc")
        for spine in self.ax.spines.values():
            spine.set_color("#3d3d3d")

    def set_points(
        self,
        point_ids: list[str],
        x_coords: np.ndarray,
        y_coords: np.ndarray,
    ):
        """Set the measurement point coordinates.

        Args:
            point_ids: List of point identifiers
            x_coords: X coordinates in mm
            y_coords: Y coordinates in mm
        """
        self._point_ids = list(point_ids)
        self._x_coords = np.asarray(x_coords, dtype=float)
        self._y_coords = np.asarray(y_coords, dtype=float)

    def set_values(self, values: dict[str, float]):
        """Set the values to display as colors.

        Args:
            values: Mapping of point_id to value
        """
        self._values = np.array(
            [values.get(pid, 0.0) for pid in self._point_ids], dtype=float
        )
        self._plot()

    def set_title(self, title: str):
        """Set the heatmap title."""
        self._title = title
        if self.ax:
            self.ax.set_title(title, color="#cccccc")
            self.canvas.draw_idle()

    def set_value_label(self, label: str):
        """Set the colorbar label."""
        self._value_label = label
        if self._colorbar:
            self._colorbar.set_label(label, color="#cccccc")
            self.canvas.draw_idle()

    def set_colormap(self, cmap: str):
        """Set the colormap name."""
        self._cmap = cmap
        if len(self._values) > 0:
            self._plot()

    def _plot(self):
        """Render the heatmap."""
        # Clear figure and recreate axes to handle colorbar cleanup
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        self._colorbar = None

        if len(self._x_coords) == 0 or len(self._values) == 0:
            self.ax.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                transform=self.ax.transAxes,
                color="#6d6d6d",
            )
            self._apply_dark_theme()
            self.canvas.draw()
            return

        # Scatter plot with color mapping
        vmin = float(np.min(self._values))
        vmax = float(np.max(self._values))
        if vmin == vmax:
            vmax = vmin + 1.0

        self._scatter = self.ax.scatter(
            self._x_coords,
            self._y_coords,
            c=self._values,
            cmap=self._cmap,
            s=100,
            vmin=vmin,
            vmax=vmax,
            edgecolors="#3d3d3d",
            linewidths=0.5,
        )

        # Colorbar
        self._colorbar = self.figure.colorbar(self._scatter, ax=self.ax)
        self._colorbar.set_label(self._value_label, color="#cccccc")
        self._colorbar.ax.tick_params(colors="#cccccc")

        # Axis labels
        self.ax.set_xlabel("X (mm)", color="#cccccc")
        self.ax.set_ylabel("Y (mm)", color="#cccccc")
        self.ax.set_title(self._title, color="#cccccc")

        # Equal aspect ratio for physical coordinates
        self.ax.set_aspect("equal", adjustable="box")

        # Grid
        self.ax.grid(True, alpha=0.3, color="#3d3d3d")

        self._apply_dark_theme()
        self.figure.tight_layout()
        self.canvas.draw()

    def get_point_at_pixel(self, x_pixel: float, y_pixel: float) -> Optional[str]:
        """Get the point_id at the given pixel coordinates.

        Args:
            x_pixel: X coordinate in pixels (from mouse event)
            y_pixel: Y coordinate in pixels (from mouse event)

        Returns:
            point_id if a point is near the coordinates, else None
        """
        if len(self._x_coords) == 0:
            return None

        # Convert pixel to data coordinates
        inv = self.ax.transData.inverted()
        x_data, y_data = inv.transform((x_pixel, y_pixel))

        # Find nearest point
        distances = np.sqrt(
            (self._x_coords - x_data) ** 2 + (self._y_coords - y_data) ** 2
        )
        min_idx = int(np.argmin(distances))

        # Threshold in data units (10mm)
        if distances[min_idx] < 10.0:
            return self._point_ids[min_idx]

        return None

    def highlight_point(self, point_id: str):
        """Highlight a specific point on the heatmap.

        Args:
            point_id: The point to highlight
        """
        if point_id not in self._point_ids:
            return

        idx = self._point_ids.index(point_id)
        x, y = self._x_coords[idx], self._y_coords[idx]

        # Add highlight circle
        self.ax.plot(
            x,
            y,
            "o",
            markersize=15,
            markerfacecolor="none",
            markeredgecolor="#ce9178",
            markeredgewidth=2,
        )
        self.canvas.draw_idle()

    def clear_highlights(self):
        """Remove all highlights and re-render."""
        self._plot()

    @property
    def n_points(self) -> int:
        """Number of points in the heatmap."""
        return len(self._point_ids)

    @property
    def has_data(self) -> bool:
        """Check if data is loaded."""
        return len(self._x_coords) > 0 and len(self._values) > 0

    @property
    def value_range(self) -> tuple[float, float]:
        """Return (min, max) of current values."""
        if len(self._values) == 0:
            return (0.0, 0.0)
        return (float(np.min(self._values)), float(np.max(self._values)))
