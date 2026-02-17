"""
Statistics panel widget for displaying analysis summaries.
"""

from typing import Dict, Any

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLabel


class StatsPanel(QWidget):
    """Widget for displaying analysis statistics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Coherence stats group
        self.coherence_group = QGroupBox("Coherence")
        coh_layout = QFormLayout(self.coherence_group)

        self.coh_mean_label = QLabel("-")
        self.coh_min_label = QLabel("-")
        self.coh_max_label = QLabel("-")
        self.coh_pct_label = QLabel("-")

        coh_layout.addRow("Mean:", self.coh_mean_label)
        coh_layout.addRow("Min:", self.coh_min_label)
        coh_layout.addRow("Max:", self.coh_max_label)
        coh_layout.addRow("% > 0.9:", self.coh_pct_label)

        layout.addWidget(self.coherence_group)

        # Peaks stats group
        self.peaks_group = QGroupBox("Peaks")
        peaks_layout = QFormLayout(self.peaks_group)

        self.peaks_count_label = QLabel("-")
        self.peaks_fundamental_label = QLabel("-")
        self.peaks_highest_label = QLabel("-")

        peaks_layout.addRow("Count:", self.peaks_count_label)
        peaks_layout.addRow("Fundamental:", self.peaks_fundamental_label)
        peaks_layout.addRow("Strongest:", self.peaks_highest_label)

        layout.addWidget(self.peaks_group)

        # Wood properties group (computed from peaks)
        self.wood_group = QGroupBox("Wood Properties")
        wood_layout = QFormLayout(self.wood_group)

        self.wood_stiffness_label = QLabel("-")
        self.wood_damping_label = QLabel("-")
        self.wood_quality_label = QLabel("-")

        wood_layout.addRow("Est. Stiffness:", self.wood_stiffness_label)
        wood_layout.addRow("Damping:", self.wood_damping_label)
        wood_layout.addRow("Quality Factor:", self.wood_quality_label)

        layout.addWidget(self.wood_group)

        # Session info group
        self.session_group = QGroupBox("Session Info")
        session_layout = QFormLayout(self.session_group)

        self.session_specimen_label = QLabel("-")
        self.session_date_label = QLabel("-")
        self.session_device_label = QLabel("-")

        session_layout.addRow("Specimen:", self.session_specimen_label)
        session_layout.addRow("Date:", self.session_date_label)
        session_layout.addRow("Device:", self.session_device_label)

        layout.addWidget(self.session_group)

        # Add stretch to push groups to top
        layout.addStretch()

    def set_coherence_stats(self, stats: Dict[str, float]):
        """
        Set coherence statistics.

        Args:
            stats: Dictionary with mean, min, max, pct_above_90
        """
        self.coh_mean_label.setText(f"{stats.get('mean', 0):.3f}")
        self.coh_min_label.setText(f"{stats.get('min', 0):.3f}")
        self.coh_max_label.setText(f"{stats.get('max', 0):.3f}")
        self.coh_pct_label.setText(f"{stats.get('pct_above_90', 0):.1f}%")

    def set_peaks_stats(self, peaks: list):
        """
        Set peaks statistics.

        Args:
            peaks: List of peak dictionaries
        """
        if not peaks:
            self.peaks_count_label.setText("0")
            self.peaks_fundamental_label.setText("-")
            self.peaks_highest_label.setText("-")
            return

        self.peaks_count_label.setText(str(len(peaks)))

        # Find fundamental (lowest frequency peak)
        sorted_by_freq = sorted(peaks, key=lambda p: p.get("freq_hz", float("inf")))
        fundamental = sorted_by_freq[0] if sorted_by_freq else None
        if fundamental:
            self.peaks_fundamental_label.setText(f"{fundamental['freq_hz']:.1f} Hz")

        # Find strongest peak
        sorted_by_mag = sorted(peaks, key=lambda p: p.get("magnitude", 0), reverse=True)
        strongest = sorted_by_mag[0] if sorted_by_mag else None
        if strongest:
            self.peaks_highest_label.setText(f"{strongest['freq_hz']:.1f} Hz")

    def set_wood_properties(self, props: Dict[str, Any]):
        """
        Set estimated wood properties.

        Args:
            props: Dictionary with stiffness, damping, quality_factor
        """
        stiffness = props.get("stiffness")
        if stiffness is not None:
            self.wood_stiffness_label.setText(f"{stiffness:.2f}")
        else:
            self.wood_stiffness_label.setText("-")

        damping = props.get("damping")
        if damping is not None:
            self.wood_damping_label.setText(f"{damping:.4f}")
        else:
            self.wood_damping_label.setText("-")

        qf = props.get("quality_factor")
        if qf is not None:
            self.wood_quality_label.setText(f"{qf:.1f}")
        else:
            self.wood_quality_label.setText("-")

    def set_session_info(self, info: Dict[str, Any]):
        """
        Set session information.

        Args:
            info: Dictionary with specimen_id, date, device_id
        """
        self.session_specimen_label.setText(info.get("specimen_id", "-"))
        self.session_date_label.setText(info.get("date", "-"))
        self.session_device_label.setText(info.get("device_id", "-"))

    def clear(self):
        """Clear all statistics."""
        self.coh_mean_label.setText("-")
        self.coh_min_label.setText("-")
        self.coh_max_label.setText("-")
        self.coh_pct_label.setText("-")

        self.peaks_count_label.setText("-")
        self.peaks_fundamental_label.setText("-")
        self.peaks_highest_label.setText("-")

        self.wood_stiffness_label.setText("-")
        self.wood_damping_label.setText("-")
        self.wood_quality_label.setText("-")

        self.session_specimen_label.setText("-")
        self.session_date_label.setText("-")
        self.session_device_label.setText("-")
