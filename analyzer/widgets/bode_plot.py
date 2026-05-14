"""
Bode plot widget for transfer function visualization.

Displays magnitude (dB) and phase plots with log frequency axis.
Migrated from luthiers-toolbox TransferFunctionRenderer.vue.
"""

from typing import Optional, List, Dict
import numpy as np

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QComboBox,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class BodePlotWidget(QWidget):
    """
    Bode plot widget for transfer function display.

    Features:
    - Magnitude plot (dB scale)
    - Phase plot (degrees)
    - Log frequency axis
    - Peak markers overlay
    - Coherence threshold display
    - Decimation for large datasets
    """

    # Signal emitted when user clicks on a frequency
    frequency_clicked = pyqtSignal(float)  # freq_hz

    # Maximum points to render (for performance)
    MAX_POINTS = 2000

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

        # Data
        self._frequencies: List[float] = []
        self._magnitude_db: List[float] = []
        self._phase: List[float] = []
        self._coherence: List[float] = []
        self._peaks: List[Dict[str, float]] = []

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls bar
        controls = QHBoxLayout()

        self._show_phase_cb = QCheckBox("Show Phase")
        self._show_phase_cb.setChecked(True)
        self._show_phase_cb.stateChanged.connect(self._update_plot)
        controls.addWidget(self._show_phase_cb)

        self._show_coherence_cb = QCheckBox("Show Coherence")
        self._show_coherence_cb.setChecked(False)
        self._show_coherence_cb.stateChanged.connect(self._update_plot)
        controls.addWidget(self._show_coherence_cb)

        self._show_peaks_cb = QCheckBox("Show Peaks")
        self._show_peaks_cb.setChecked(True)
        self._show_peaks_cb.stateChanged.connect(self._update_plot)
        controls.addWidget(self._show_peaks_cb)

        controls.addStretch()

        # Frequency range selector
        controls.addWidget(QLabel("Range:"))
        self._range_combo = QComboBox()
        self._range_combo.addItems(
            ["Full", "20-2000 Hz", "20-5000 Hz", "50-1000 Hz", "100-500 Hz"]
        )
        self._range_combo.currentIndexChanged.connect(self._update_plot)
        controls.addWidget(self._range_combo)

        controls_frame = QFrame()
        controls_frame.setLayout(controls)
        layout.addWidget(controls_frame)

        # Matplotlib figure with subplots
        self._figure = Figure(figsize=(10, 6), facecolor="#1e1e1e")
        self._canvas = FigureCanvas(self._figure)
        layout.addWidget(self._canvas)

        # Create subplots
        self._ax_mag = self._figure.add_subplot(211)
        self._ax_phase = self._figure.add_subplot(212, sharex=self._ax_mag)

        self._setup_axes_style()

        # Connect click event
        self._canvas.mpl_connect("button_press_event", self._on_click)

    def _setup_axes_style(self):
        """Apply dark theme styling to axes."""
        for ax in [self._ax_mag, self._ax_phase]:
            ax.set_facecolor("#252526")
            ax.tick_params(colors="white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
            ax.title.set_color("white")
            ax.spines["bottom"].set_color("#555")
            ax.spines["top"].set_color("#555")
            ax.spines["left"].set_color("#555")
            ax.spines["right"].set_color("#555")
            ax.grid(True, alpha=0.3, color="#555")

    def set_data(
        self,
        frequencies: List[float],
        magnitude_db: List[float],
        phase: Optional[List[float]] = None,
        coherence: Optional[List[float]] = None,
        peaks: Optional[List[Dict[str, float]]] = None,
    ):
        """
        Set the transfer function data.

        Args:
            frequencies: Frequency values (Hz)
            magnitude_db: Magnitude values (dB)
            phase: Phase values (degrees)
            coherence: Coherence values (0-1)
            peaks: Peak markers [{freq_hz, magnitude, ...}, ...]
        """
        self._frequencies = frequencies
        self._magnitude_db = magnitude_db
        self._phase = phase or []
        self._coherence = coherence or []
        self._peaks = peaks or []

        # Enable/disable coherence checkbox based on data
        self._show_coherence_cb.setEnabled(len(self._coherence) > 0)

        self._update_plot()

    def set_peaks(self, peaks: List[Dict[str, float]]):
        """Set peak markers."""
        self._peaks = peaks
        self._update_plot()

    def _get_freq_range(self) -> tuple:
        """Get selected frequency range."""
        range_text = self._range_combo.currentText()
        if range_text == "Full":
            return None
        elif range_text == "20-2000 Hz":
            return (20, 2000)
        elif range_text == "20-5000 Hz":
            return (20, 5000)
        elif range_text == "50-1000 Hz":
            return (50, 1000)
        elif range_text == "100-500 Hz":
            return (100, 500)
        return None

    def _decimate(self, arr: List[float], n_points: int) -> List[float]:
        """Decimate array to n_points using min-max preservation."""
        if len(arr) <= n_points:
            return arr

        # Use numpy for efficiency
        arr_np = np.array(arr)
        chunk_size = len(arr) // (n_points // 2)

        result = []
        for i in range(0, len(arr), chunk_size):
            chunk = arr_np[i : i + chunk_size]
            if len(chunk) > 0:
                result.append(float(np.min(chunk)))
                result.append(float(np.max(chunk)))

        return result[:n_points]

    def _decimate_data_if_needed(self) -> tuple:
        """Decimate data arrays if exceeding MAX_POINTS.

        Returns (freq, mag_db, phase, coh) potentially decimated.
        """
        if len(self._frequencies) > self.MAX_POINTS:
            freq = self._decimate(self._frequencies, self.MAX_POINTS)
            mag_db = self._decimate(self._magnitude_db, self.MAX_POINTS)
            phase = self._decimate(self._phase, self.MAX_POINTS) if self._phase else []
            coh = (
                self._decimate(self._coherence, self.MAX_POINTS)
                if self._coherence
                else []
            )
        else:
            freq = self._frequencies
            mag_db = self._magnitude_db
            phase = self._phase
            coh = self._coherence
        return freq, mag_db, phase, coh

    def _apply_freq_range_filter(
        self,
        freq: List[float],
        mag_db: List[float],
        phase: List[float],
        coh: List[float],
    ) -> tuple:
        """Apply frequency range filter to data arrays.

        Returns (freq, mag_db, phase, coh) filtered to selected range.
        """
        freq_range = self._get_freq_range()
        if not freq_range:
            return freq, mag_db, phase, coh

        mask = [(f >= freq_range[0] and f <= freq_range[1]) for f in freq]
        freq = [f for f, m in zip(freq, mask) if m]
        mag_db = [v for v, m in zip(mag_db, mask) if m]
        if phase:
            phase = [v for v, m in zip(phase, mask) if m]
        if coh:
            coh = [v for v, m in zip(coh, mask) if m]
        return freq, mag_db, phase, coh

    def _plot_coherence(self, freq: List[float], coh: List[float]) -> None:
        """Plot coherence overlay on magnitude axes."""
        if not self._show_coherence_cb.isChecked() or not coh:
            return

        ax_coh = self._ax_mag.twinx()
        ax_coh.semilogx(freq, coh, "g-", linewidth=0.8, alpha=0.7, label="Coherence")
        ax_coh.set_ylabel("Coherence", color="#4a4")
        ax_coh.set_ylim(0, 1.1)
        ax_coh.tick_params(colors="#4a4")
        # Draw coherence threshold line
        ax_coh.axhline(y=0.8, color="#4a4", linestyle="--", alpha=0.5)

    def _plot_peaks(self, freq_range: tuple) -> None:
        """Plot peak markers on magnitude axes."""
        if not self._show_peaks_cb.isChecked() or not self._peaks:
            return

        for peak in self._peaks:
            peak_freq = peak.get("freq_hz", 0)
            if freq_range and (peak_freq < freq_range[0] or peak_freq > freq_range[1]):
                continue

            # Find nearest magnitude value
            peak_mag = peak.get("magnitude_db")
            if peak_mag is None and "magnitude" in peak:
                # Convert linear to dB
                from analyzer.loaders.transfer_function import linear_to_db

                peak_mag = linear_to_db(peak["magnitude"])

            self._ax_mag.axvline(
                x=peak_freq, color="#ff6b6b", linestyle="--", alpha=0.6, linewidth=0.8
            )
            # Annotate peak
            if peak_mag is not None:
                self._ax_mag.annotate(
                    f"{peak_freq:.0f}Hz",
                    xy=(peak_freq, peak_mag),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8,
                    color="#ff6b6b",
                    alpha=0.8,
                )

    def _plot_phase(self, freq: List[float], phase: List[float]) -> None:
        """Plot phase curve on phase axes."""
        if not self._show_phase_cb.isChecked() or not phase:
            self._ax_phase.set_visible(False)
            return

        self._ax_phase.semilogx(freq, phase, "m-", linewidth=1, label="Phase")
        self._ax_phase.set_ylabel("Phase (°)", color="white")
        self._ax_phase.set_xlabel("Frequency (Hz)", color="white")

        # Add reference lines
        for ref in [-180, -90, 0, 90, 180]:
            if min(phase) <= ref <= max(phase):
                self._ax_phase.axhline(
                    y=ref, color="#555", linestyle=":", alpha=0.5, linewidth=0.5
                )

    def _update_plot(self):
        """Update the plot with current data."""
        self._ax_mag.clear()
        self._ax_phase.clear()

        if not self._frequencies or not self._magnitude_db:
            self._setup_axes_style()
            self._canvas.draw()
            return

        # Get and filter data
        freq, mag_db, phase, coh = self._decimate_data_if_needed()
        freq, mag_db, phase, coh = self._apply_freq_range_filter(
            freq, mag_db, phase, coh
        )

        if not freq:
            self._setup_axes_style()
            self._canvas.draw()
            return

        # Plot magnitude
        self._ax_mag.semilogx(freq, mag_db, "c-", linewidth=1, label="Magnitude")
        self._ax_mag.set_ylabel("Magnitude (dB)", color="white")
        self._ax_mag.set_title(
            "Transfer Function (Bode Plot)", color="white", fontsize=10
        )

        # Plot overlays
        self._plot_coherence(freq, coh)
        self._plot_peaks(self._get_freq_range())
        self._plot_phase(freq, phase)

        self._setup_axes_style()
        self._figure.tight_layout()
        self._canvas.draw()

    def _on_click(self, event):
        """Handle mouse click on plot."""
        if event.inaxes not in [self._ax_mag, self._ax_phase]:
            return

        freq = event.xdata
        if freq is not None and freq > 0:
            self.frequency_clicked.emit(freq)

    def export_figure(self, path: str, dpi: int = 150):
        """Export the figure to a file."""
        self._figure.savefig(
            path, dpi=dpi, facecolor="#1e1e1e", edgecolor="none", bbox_inches="tight"
        )


class WsiPlotWidget(QWidget):
    """
    WSI (Wolf Stress Index) curve visualization widget.

    Features:
    - WSI curve plot
    - Coherence mean overlay
    - Phase disorder overlay
    - Admissible region shading
    - Problem frequency markers
    """

    frequency_clicked = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls bar
        controls = QHBoxLayout()

        self._show_coh_cb = QCheckBox("Coherence")
        self._show_coh_cb.setChecked(True)
        self._show_coh_cb.stateChanged.connect(self._update_plot)
        controls.addWidget(self._show_coh_cb)

        self._show_pd_cb = QCheckBox("Phase Disorder")
        self._show_pd_cb.setChecked(False)
        self._show_pd_cb.stateChanged.connect(self._update_plot)
        controls.addWidget(self._show_pd_cb)

        self._show_admissible_cb = QCheckBox("Admissible Regions")
        self._show_admissible_cb.setChecked(True)
        self._show_admissible_cb.stateChanged.connect(self._update_plot)
        controls.addWidget(self._show_admissible_cb)

        controls.addStretch()

        controls_frame = QFrame()
        controls_frame.setLayout(controls)
        layout.addWidget(controls_frame)

        # Matplotlib figure
        self._figure = Figure(figsize=(10, 4), facecolor="#1e1e1e")
        self._canvas = FigureCanvas(self._figure)
        layout.addWidget(self._canvas)

        self._ax = self._figure.add_subplot(111)
        self._setup_axes_style()

        # Data
        self._wsi_data = None

        self._canvas.mpl_connect("button_press_event", self._on_click)

    def _setup_axes_style(self):
        """Apply dark theme styling."""
        ax = self._ax
        ax.set_facecolor("#252526")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        ax.spines["bottom"].set_color("#555")
        ax.spines["top"].set_color("#555")
        ax.spines["left"].set_color("#555")
        ax.spines["right"].set_color("#555")
        ax.grid(True, alpha=0.3, color="#555")

    def set_data(self, wsi_data):
        """
        Set WSI curve data.

        Args:
            wsi_data: WsiCurveData object
        """
        self._wsi_data = wsi_data
        self._show_coh_cb.setEnabled(wsi_data.has_coherence() if wsi_data else False)
        self._show_pd_cb.setEnabled(
            wsi_data.has_phase_disorder() if wsi_data else False
        )
        self._update_plot()

    def _decimate_data_if_needed(self) -> tuple:
        """Decimate data arrays if exceeding MAX_POINTS.

        Returns (freq, mag_db, phase, coh) potentially decimated.
        """
        if len(self._frequencies) > self.MAX_POINTS:
            freq = self._decimate(self._frequencies, self.MAX_POINTS)
            mag_db = self._decimate(self._magnitude_db, self.MAX_POINTS)
            phase = self._decimate(self._phase, self.MAX_POINTS) if self._phase else []
            coh = (
                self._decimate(self._coherence, self.MAX_POINTS)
                if self._coherence
                else []
            )
        else:
            freq = self._frequencies
            mag_db = self._magnitude_db
            phase = self._phase
            coh = self._coherence
        return freq, mag_db, phase, coh

    def _apply_freq_range_filter(
        self,
        freq: List[float],
        mag_db: List[float],
        phase: List[float],
        coh: List[float],
    ) -> tuple:
        """Apply frequency range filter to data arrays.

        Returns (freq, mag_db, phase, coh) filtered to selected range.
        """
        freq_range = self._get_freq_range()
        if not freq_range:
            return freq, mag_db, phase, coh

        mask = [(f >= freq_range[0] and f <= freq_range[1]) for f in freq]
        freq = [f for f, m in zip(freq, mask) if m]
        mag_db = [v for v, m in zip(mag_db, mask) if m]
        if phase:
            phase = [v for v, m in zip(phase, mask) if m]
        if coh:
            coh = [v for v, m in zip(coh, mask) if m]
        return freq, mag_db, phase, coh

    def _plot_coherence(self, freq: List[float], coh: List[float]) -> None:
        """Plot coherence overlay on magnitude axes."""
        if not self._show_coherence_cb.isChecked() or not coh:
            return

        ax_coh = self._ax_mag.twinx()
        ax_coh.semilogx(freq, coh, "g-", linewidth=0.8, alpha=0.7, label="Coherence")
        ax_coh.set_ylabel("Coherence", color="#4a4")
        ax_coh.set_ylim(0, 1.1)
        ax_coh.tick_params(colors="#4a4")
        # Draw coherence threshold line
        ax_coh.axhline(y=0.8, color="#4a4", linestyle="--", alpha=0.5)

    def _plot_peaks(self, freq_range: tuple) -> None:
        """Plot peak markers on magnitude axes."""
        if not self._show_peaks_cb.isChecked() or not self._peaks:
            return

        for peak in self._peaks:
            peak_freq = peak.get("freq_hz", 0)
            if freq_range and (peak_freq < freq_range[0] or peak_freq > freq_range[1]):
                continue

            # Find nearest magnitude value
            peak_mag = peak.get("magnitude_db")
            if peak_mag is None and "magnitude" in peak:
                # Convert linear to dB
                from analyzer.loaders.transfer_function import linear_to_db

                peak_mag = linear_to_db(peak["magnitude"])

            self._ax_mag.axvline(
                x=peak_freq, color="#ff6b6b", linestyle="--", alpha=0.6, linewidth=0.8
            )
            # Annotate peak
            if peak_mag is not None:
                self._ax_mag.annotate(
                    f"{peak_freq:.0f}Hz",
                    xy=(peak_freq, peak_mag),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8,
                    color="#ff6b6b",
                    alpha=0.8,
                )

    def _plot_phase(self, freq: List[float], phase: List[float]) -> None:
        """Plot phase curve on phase axes."""
        if not self._show_phase_cb.isChecked() or not phase:
            self._ax_phase.set_visible(False)
            return

        self._ax_phase.semilogx(freq, phase, "m-", linewidth=1, label="Phase")
        self._ax_phase.set_ylabel("Phase (°)", color="white")
        self._ax_phase.set_xlabel("Frequency (Hz)", color="white")

        # Add reference lines
        for ref in [-180, -90, 0, 90, 180]:
            if min(phase) <= ref <= max(phase):
                self._ax_phase.axhline(
                    y=ref, color="#555", linestyle=":", alpha=0.5, linewidth=0.5
                )

    def _update_plot(self):
        """Update the plot."""
        self._ax.clear()

        if not self._wsi_data or not self._wsi_data.freq_hz:
            self._setup_axes_style()
            self._canvas.draw()
            return

        data = self._wsi_data
        freq = data.freq_hz

        # Draw admissible regions first (background)
        if self._show_admissible_cb.isChecked() and data.admissible:
            regions = data.get_admissible_regions()
            for start, end in regions:
                self._ax.axvspan(
                    start,
                    end,
                    alpha=0.15,
                    color="green",
                    label="Admissible" if start == regions[0][0] else None,
                )

        # Plot WSI curve
        self._ax.plot(freq, data.wsi, "c-", linewidth=1.5, label="WSI")

        # Plot coherence mean if enabled
        if self._show_coh_cb.isChecked() and data.coh_mean:
            ax2 = self._ax.twinx()
            ax2.plot(
                freq, data.coh_mean, "g-", linewidth=0.8, alpha=0.7, label="Coh Mean"
            )
            ax2.set_ylabel("Coherence", color="#4a4")
            ax2.set_ylim(0, 1.1)
            ax2.tick_params(colors="#4a4")

        # Plot phase disorder if enabled
        if self._show_pd_cb.isChecked() and data.phase_disorder:
            ax3 = self._ax.twinx()
            if self._show_coh_cb.isChecked():
                ax3.spines["right"].set_position(("outward", 60))
            ax3.plot(
                freq,
                data.phase_disorder,
                "m-",
                linewidth=0.8,
                alpha=0.7,
                label="Phase Disorder",
            )
            ax3.set_ylabel("Phase Disorder", color="#a4a")
            ax3.tick_params(colors="#a4a")

        # Mark problem frequencies
        problems = data.get_problem_frequencies(0.7)
        for prob in problems:
            color = "#ff4444" if prob["severity"] == "high" else "#ff8844"
            self._ax.axvline(
                x=prob["freq_hz"], color=color, linestyle="--", alpha=0.6, linewidth=0.8
            )

        # WSI threshold line
        self._ax.axhline(
            y=0.7, color="#ff6b6b", linestyle=":", alpha=0.5, label="WSI Threshold"
        )

        self._ax.set_xlabel("Frequency (Hz)", color="white")
        self._ax.set_ylabel("Wolf Stress Index", color="white")
        self._ax.set_title("Wolf Stress Index Analysis", color="white", fontsize=10)
        self._ax.set_ylim(0, 1.1)
        self._ax.legend(loc="upper right", fontsize=8)

        self._setup_axes_style()
        self._figure.tight_layout()
        self._canvas.draw()

    def _on_click(self, event):
        """Handle mouse click."""
        if event.inaxes != self._ax:
            return
        if event.xdata is not None:
            self.frequency_clicked.emit(event.xdata)

    def export_figure(self, path: str, dpi: int = 150):
        """Export the figure to file."""
        self._figure.savefig(
            path, dpi=dpi, facecolor="#1e1e1e", edgecolor="none", bbox_inches="tight"
        )
