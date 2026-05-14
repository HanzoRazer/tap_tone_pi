"""
Spectrum chart widget using Matplotlib embedded in PyQt6.
"""

from typing import Optional, List, Dict, Any
import numpy as np

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from analyzer.analysis.peaks import find_spectrum_peaks


class SpectrumChartWidget(QWidget):
    """Widget for displaying spectrum data as a chart."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._data: Optional[Dict[str, Any]] = None
        self._freq: Optional[np.ndarray] = None
        self._magnitude: Optional[np.ndarray] = None
        self._coherence: Optional[np.ndarray] = None
        self._phase: Optional[np.ndarray] = None

        self._zoom_level = 1.0
        self._x_limits = None
        self._y_limits = None

        self._setup_ui()
        self._apply_dark_theme()

    def _setup_ui(self):
        """Set up the chart UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create figure with two subplots (magnitude + coherence)
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)

        # Create subplots
        self.ax_mag = self.figure.add_subplot(211)
        self.ax_coh = self.figure.add_subplot(212, sharex=self.ax_mag)

        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def _apply_dark_theme(self):
        """Apply dark theme to the matplotlib figure."""
        self.figure.patch.set_facecolor("#1e1e1e")

        for ax in [self.ax_mag, self.ax_coh]:
            ax.set_facecolor("#252526")
            ax.tick_params(colors="#cccccc")
            ax.xaxis.label.set_color("#cccccc")
            ax.yaxis.label.set_color("#cccccc")
            ax.title.set_color("#cccccc")
            for spine in ax.spines.values():
                spine.set_color("#3d3d3d")

    def set_data(self, data: Dict[str, Any]):
        """
        Set spectrum data to display.

        Args:
            data: Dictionary with keys:
                - freq_hz: array of frequencies
                - H_mag: array of magnitude values
                - coherence: array of coherence values (optional)
                - phase_deg: array of phase values (optional)
        """
        self._data = data
        self._freq = np.array(data.get("freq_hz", []))
        self._magnitude = np.array(data.get("H_mag", []))
        self._coherence = np.array(data.get("coherence", []))
        self._phase = np.array(data.get("phase_deg", []))

        self._plot()

    def _plot(self):
        """Render the spectrum plot."""
        self.ax_mag.clear()
        self.ax_coh.clear()

        if self._freq is None or len(self._freq) == 0:
            self.canvas.draw()
            return

        # Plot magnitude
        self.ax_mag.semilogy(
            self._freq, self._magnitude, color="#007acc", linewidth=0.8
        )
        self.ax_mag.set_ylabel("Magnitude (dB)")
        self.ax_mag.set_title("Transfer Function Magnitude")
        self.ax_mag.grid(True, alpha=0.3, color="#3d3d3d")

        # Plot coherence if available
        if self._coherence is not None and len(self._coherence) > 0:
            self.ax_coh.plot(
                self._freq, self._coherence, color="#4ec9b0", linewidth=0.8
            )
            self.ax_coh.set_ylim(0, 1.1)
            self.ax_coh.axhline(
                y=0.9, color="#ce9178", linestyle="--", alpha=0.5, label="0.9 threshold"
            )
            self.ax_coh.set_ylabel("Coherence")
            self.ax_coh.legend(loc="lower right")
        else:
            self.ax_coh.text(
                0.5,
                0.5,
                "No coherence data",
                ha="center",
                va="center",
                transform=self.ax_coh.transAxes,
                color="#6d6d6d",
            )

        self.ax_coh.set_xlabel("Frequency (Hz)")
        self.ax_coh.grid(True, alpha=0.3, color="#3d3d3d")

        # Apply dark theme
        self._apply_dark_theme()

        self.figure.tight_layout()
        self.canvas.draw()

    def has_data(self) -> bool:
        """Check if data is loaded."""
        return self._freq is not None and len(self._freq) > 0

    def find_peaks(
        self, min_prominence: float = 0.1, min_distance: int = 10
    ) -> List[Dict[str, float]]:
        """
        Find peaks in the current spectrum.

        Returns:
            List of peak dictionaries with freq_hz, magnitude, coherence
        """
        if not self.has_data():
            return []

        return find_spectrum_peaks(
            self._freq,
            self._magnitude,
            self._coherence,
            min_prominence=min_prominence,
            min_distance=min_distance,
        )

    def analyze_coherence(self) -> Dict[str, float]:
        """
        Analyze coherence statistics.

        Returns:
            Dictionary with mean, min, max, and percentage above threshold
        """
        if self._coherence is None or len(self._coherence) == 0:
            return {}

        return {
            "mean": float(np.mean(self._coherence)),
            "min": float(np.min(self._coherence)),
            "max": float(np.max(self._coherence)),
            "pct_above_90": float(
                np.sum(self._coherence >= 0.9) / len(self._coherence) * 100
            ),
        }

    def zoom_in(self):
        """Zoom in on the chart."""
        self._zoom_level *= 1.2
        xlim = self.ax_mag.get_xlim()
        center = (xlim[0] + xlim[1]) / 2
        width = (xlim[1] - xlim[0]) / 1.2
        self.ax_mag.set_xlim(center - width / 2, center + width / 2)
        self.canvas.draw()

    def zoom_out(self):
        """Zoom out on the chart."""
        self._zoom_level /= 1.2
        xlim = self.ax_mag.get_xlim()
        center = (xlim[0] + xlim[1]) / 2
        width = (xlim[1] - xlim[0]) * 1.2
        self.ax_mag.set_xlim(center - width / 2, center + width / 2)
        self.canvas.draw()

    def reset_zoom(self):
        """Reset zoom to show full data range."""
        self._zoom_level = 1.0
        if self._freq is not None and len(self._freq) > 0:
            self.ax_mag.set_xlim(self._freq[0], self._freq[-1])
            self.canvas.draw()

    def highlight_peaks(self, peaks: List[Dict[str, float]]):
        """Highlight peaks on the chart."""
        if not self.has_data():
            return

        # Re-plot to clear old markers
        self._plot()

        # Add peak markers
        for peak in peaks:
            freq = peak["freq_hz"]
            mag = peak["magnitude"]
            self.ax_mag.axvline(x=freq, color="#ce9178", linestyle="--", alpha=0.5)
            self.ax_mag.annotate(
                f"{freq:.0f} Hz",
                xy=(freq, mag),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color="#cccccc",
            )

        self.canvas.draw()
