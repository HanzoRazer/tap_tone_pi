"""
Phase 2 ODS scanning results widget.

Displays Phase 2 session data:
- WSI curve (frequency vs weighted shape index)
- 2D heatmap of point amplitudes at selected frequency
- Peaks list with clickable frequency selection
- Grid and session metadata
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from analyzer.loaders.phase2_session import Phase2Session
from analyzer.loaders.prediction_loader import BuildComparison, load_build_comparison
from analyzer.widgets._heatmap import HeatmapWidget


class Phase2ResultsWidget(QWidget):
    """Widget for displaying Phase 2 ODS scanning results."""

    frequency_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._session: Optional[Phase2Session] = None
        self._current_freq_idx: int = 0
        self._comparison: Optional[BuildComparison] = None

        self._setup_ui()
        self._apply_dark_theme()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Main splitter: left (charts) | right (metadata + peaks)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: WSI curve + heatmap
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # WSI curve
        self._wsi_group = QGroupBox("WSI Curve")
        wsi_layout = QVBoxLayout(self._wsi_group)
        wsi_layout.setContentsMargins(4, 4, 4, 4)

        self._wsi_figure = Figure(figsize=(8, 3), dpi=100)
        self._wsi_canvas = FigureCanvas(self._wsi_figure)
        self._wsi_ax = self._wsi_figure.add_subplot(111)
        wsi_layout.addWidget(self._wsi_canvas)

        left_layout.addWidget(self._wsi_group)

        # Heatmap
        self._heatmap_group = QGroupBox("Point Amplitude Heatmap")
        heatmap_layout = QVBoxLayout(self._heatmap_group)
        heatmap_layout.setContentsMargins(4, 4, 4, 4)

        self._heatmap = HeatmapWidget()
        heatmap_layout.addWidget(self._heatmap)

        # Frequency slider
        slider_frame = QFrame()
        slider_layout = QHBoxLayout(slider_frame)
        slider_layout.setContentsMargins(4, 0, 4, 0)

        slider_layout.addWidget(QLabel("Frequency:"))
        self._freq_slider = QSlider(Qt.Orientation.Horizontal)
        self._freq_slider.setMinimum(0)
        self._freq_slider.setMaximum(100)
        self._freq_slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self._freq_slider, stretch=1)

        self._freq_label = QLabel("0 Hz")
        self._freq_label.setMinimumWidth(80)
        slider_layout.addWidget(self._freq_label)

        heatmap_layout.addWidget(slider_frame)

        left_layout.addWidget(self._heatmap_group)

        splitter.addWidget(left_widget)

        # Right panel: metadata + peaks
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Session metadata
        self._meta_group = QGroupBox("Session Info")
        meta_layout = QVBoxLayout(self._meta_group)
        meta_layout.setContentsMargins(8, 8, 8, 8)

        self._session_label = QLabel("No session loaded")
        self._session_label.setWordWrap(True)
        meta_layout.addWidget(self._session_label)

        self._grid_label = QLabel("")
        self._grid_label.setWordWrap(True)
        meta_layout.addWidget(self._grid_label)

        self._build_label = QLabel("")
        self._build_label.setWordWrap(True)
        meta_layout.addWidget(self._build_label)

        right_layout.addWidget(self._meta_group)

        # Peaks list
        self._peaks_group = QGroupBox("Peak Frequencies")
        peaks_layout = QVBoxLayout(self._peaks_group)
        peaks_layout.setContentsMargins(4, 4, 4, 4)

        self._peaks_list = QListWidget()
        self._peaks_list.itemClicked.connect(self._on_peak_clicked)
        peaks_layout.addWidget(self._peaks_list)

        right_layout.addWidget(self._peaks_group, stretch=1)

        # Comparison panel (predictions vs measurements)
        self._comparison_group = QGroupBox("Predicted vs Measured")
        comparison_layout = QVBoxLayout(self._comparison_group)
        comparison_layout.setContentsMargins(8, 8, 8, 8)

        self._comparison_label = QLabel("No comparison data")
        self._comparison_label.setWordWrap(True)
        comparison_layout.addWidget(self._comparison_label)

        self._comparison_list = QListWidget()
        self._comparison_list.setMaximumHeight(150)
        comparison_layout.addWidget(self._comparison_list)

        right_layout.addWidget(self._comparison_group)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([700, 300])

        layout.addWidget(splitter)

    def _apply_dark_theme(self):
        """Apply dark theme to matplotlib figures."""
        for fig, ax in [
            (self._wsi_figure, self._wsi_ax),
        ]:
            fig.patch.set_facecolor("#1e1e1e")
            ax.set_facecolor("#252526")
            ax.tick_params(colors="#cccccc")
            ax.xaxis.label.set_color("#cccccc")
            ax.yaxis.label.set_color("#cccccc")
            ax.title.set_color("#cccccc")
            for spine in ax.spines.values():
                spine.set_color("#3d3d3d")

    def set_session(self, session: Phase2Session):
        """Load a Phase 2 session for display.

        Args:
            session: The Phase2Session to display
        """
        self._session = session
        self._current_freq_idx = 0

        # Update slider range
        self._freq_slider.setMaximum(session.n_freqs - 1)
        self._freq_slider.setValue(0)

        # Update metadata labels
        meta = session.session_meta
        session_id = meta.get("session_id", session.session_dir.name)
        created = meta.get("created_at", "unknown")
        self._session_label.setText(f"Session: {session_id}\nCreated: {created}")

        grid = session.grid_meta
        units = grid.get("units", "mm")
        spacing = grid.get("spacing", "?")
        origin = grid.get("origin", {})
        origin_str = f"({origin.get('x', 0)}, {origin.get('y', 0)})"
        self._grid_label.setText(
            f"Grid: {session.n_points} points\n"
            f"Spacing: {spacing} {units}\n"
            f"Origin: {origin_str}"
        )

        if session.build_id:
            self._build_label.setText(f"Build: {session.build_id}")
        else:
            self._build_label.setText("")

        # Set heatmap points
        coords = session.get_point_coords()
        point_ids = [c[0] for c in coords]
        x_coords = np.array([c[1] for c in coords])
        y_coords = np.array([c[2] for c in coords])
        self._heatmap.set_points(point_ids, x_coords, y_coords)

        # Find and display peaks
        self._populate_peaks()

        # Plot WSI curve if available
        self._plot_wsi()

        # Update heatmap for initial frequency
        self._update_heatmap_for_freq_idx(0)

        # Auto-load comparison if build_id present
        if session.build_id:
            self.load_comparison(session.build_id)

    def _populate_peaks(self):
        """Find peaks and populate the peaks list."""
        self._peaks_list.clear()

        if not self._session or self._session.n_freqs == 0:
            return

        # Simple peak finding: local maxima in mean amplitude
        mean_mag = np.zeros(self._session.n_freqs)
        for p in self._session.points:
            mean_mag += p.H_mag
        mean_mag /= self._session.n_points

        # Find local maxima with prominence
        from scipy.signal import find_peaks

        peak_indices, properties = find_peaks(
            mean_mag, prominence=0.1 * np.max(mean_mag), distance=5
        )

        # Sort by prominence (descending)
        if len(peak_indices) > 0:
            prominences = properties["prominences"]
            sorted_order = np.argsort(prominences)[::-1]
            peak_indices = peak_indices[sorted_order]

        # Add to list (top 10)
        for idx in peak_indices[:10]:
            freq = self._session.freqs_hz[idx]
            mag = mean_mag[idx]
            item = QListWidgetItem(f"{freq:.1f} Hz (mag: {mag:.3f})")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self._peaks_list.addItem(item)

    def _plot_wsi(self):
        """Plot the WSI curve if available."""
        self._wsi_ax.clear()

        if not self._session:
            self._wsi_canvas.draw()
            return

        wsi = self._session.wsi_curve
        if wsi and "freqs_hz" in wsi and "wsi_values" in wsi:
            freqs = wsi["freqs_hz"]
            values = wsi["wsi_values"]
            self._wsi_ax.plot(freqs, values, color="#4ec9b0", linewidth=1.2)
            self._wsi_ax.axhline(
                y=0.7, color="#ce9178", linestyle="--", alpha=0.5, label="Threshold"
            )
            self._wsi_ax.set_xlabel("Frequency (Hz)")
            self._wsi_ax.set_ylabel("WSI")
            self._wsi_ax.set_title("Weighted Shape Index")
            self._wsi_ax.grid(True, alpha=0.3, color="#3d3d3d")
            self._wsi_ax.legend(loc="upper right", fontsize=8)
        else:
            # No WSI data — show mean magnitude instead
            mean_mag = np.zeros(self._session.n_freqs)
            for p in self._session.points:
                mean_mag += p.H_mag
            mean_mag /= self._session.n_points

            self._wsi_ax.plot(
                self._session.freqs_hz, mean_mag, color="#007acc", linewidth=1.0
            )
            self._wsi_ax.set_xlabel("Frequency (Hz)")
            self._wsi_ax.set_ylabel("Mean Amplitude")
            self._wsi_ax.set_title("Mean Response (no WSI data)")
            self._wsi_ax.grid(True, alpha=0.3, color="#3d3d3d")

        # Add comparison markers if available
        self._add_comparison_markers_to_wsi()

        self._apply_dark_theme()
        self._wsi_figure.tight_layout()
        self._wsi_canvas.draw()

    def _update_heatmap_for_freq_idx(self, idx: int):
        """Update heatmap for the given frequency index."""
        if not self._session or idx >= self._session.n_freqs:
            return

        self._current_freq_idx = idx
        freq = self._session.freqs_hz[idx]
        self._freq_label.setText(f"{freq:.1f} Hz")

        # Get amplitude values at this frequency
        values = self._session.amplitude_at_freq_index(idx)
        self._heatmap.set_values(values)
        self._heatmap.set_title(f"Amplitude at {freq:.1f} Hz")
        self._heatmap.set_value_label("H_mag")

        self.frequency_changed.emit(freq)

    def _on_slider_changed(self, value: int):
        """Handle frequency slider change."""
        self._update_heatmap_for_freq_idx(value)

    def _on_peak_clicked(self, item: QListWidgetItem):
        """Handle peak list item click."""
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is not None:
            self._freq_slider.setValue(idx)

    def set_frequency(self, freq_hz: float):
        """Set the display frequency by interpolating to nearest index.

        Args:
            freq_hz: The frequency to display
        """
        if not self._session or self._session.n_freqs == 0:
            return

        # Find nearest index
        idx = int(np.argmin(np.abs(self._session.freqs_hz - freq_hz)))
        self._freq_slider.setValue(idx)

    @property
    def current_frequency(self) -> float:
        """Get the currently displayed frequency."""
        if not self._session or self._session.n_freqs == 0:
            return 0.0
        return float(self._session.freqs_hz[self._current_freq_idx])

    @property
    def session(self) -> Optional[Phase2Session]:
        """Get the currently loaded session."""
        return self._session

    def has_session(self) -> bool:
        """Check if a session is loaded."""
        return self._session is not None

    def load_comparison(self, build_id: Optional[str] = None):
        """Load comparison data for the given build (or session's build).

        Args:
            build_id: Build ID to look up. If None, uses session's build_id.
        """
        if build_id is None and self._session:
            build_id = self._session.build_id

        if not build_id:
            self._comparison = None
            self._update_comparison_display()
            return

        self._comparison = load_build_comparison(build_id)
        self._update_comparison_display()
        self._plot_wsi()  # Re-plot with markers

    def _update_comparison_display(self):
        """Update the comparison panel with current data."""
        self._comparison_list.clear()

        if not self._comparison:
            self._comparison_label.setText("No comparison data")
            return

        comp = self._comparison
        self._comparison_label.setText(
            f"Build: {comp.build_id}\nDesign: {comp.design_name}"
        )

        for mode in comp.modes:
            if mode.predicted_hz is None and mode.measured_hz is None:
                continue

            pred_str = f"{mode.predicted_hz:.1f}" if mode.predicted_hz else "-"
            meas_str = f"{mode.measured_hz:.1f}" if mode.measured_hz else "-"

            if mode.has_both and mode.residual_hz is not None:
                sign = "+" if mode.residual_hz >= 0 else ""
                item_text = (
                    f"{mode.mode_name}: pred={pred_str} Hz, meas={meas_str} Hz "
                    f"({sign}{mode.residual_hz:.1f} Hz, {sign}{mode.residual_pct:.1f}%)"
                )
            else:
                item_text = f"{mode.mode_name}: pred={pred_str} Hz, meas={meas_str} Hz"

            self._comparison_list.addItem(item_text)

    def _add_comparison_markers_to_wsi(self):
        """Add vertical markers for predicted mode frequencies on WSI plot."""
        if not self._comparison or not self._session:
            return

        colors = {"T1": "#ff6b6b", "A0": "#4ecdc4", "T2": "#ffe66d", "T3": "#a8dadc"}

        for mode in self._comparison.modes:
            if mode.predicted_hz is None:
                continue

            color = colors.get(mode.mode_name, "#ffffff")
            self._wsi_ax.axvline(
                x=mode.predicted_hz,
                color=color,
                linestyle="--",
                alpha=0.7,
                linewidth=1.5,
                label=f"{mode.mode_name} pred",
            )

            if mode.measured_hz is not None:
                self._wsi_ax.axvline(
                    x=mode.measured_hz,
                    color=color,
                    linestyle="-",
                    alpha=0.5,
                    linewidth=1.0,
                )

    @property
    def comparison(self) -> Optional[BuildComparison]:
        """Get the currently loaded comparison data."""
        return self._comparison

    def has_comparison(self) -> bool:
        """Check if comparison data is loaded."""
        return self._comparison is not None
