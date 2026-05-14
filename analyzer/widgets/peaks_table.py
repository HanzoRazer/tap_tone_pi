"""
Peaks table widget for displaying detected resonance peaks.
"""

from typing import List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal


class PeaksTableWidget(QWidget):
    """Widget for displaying peaks in a table format."""

    peak_selected = pyqtSignal(dict)  # Emitted when a peak row is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks: List[Dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self):
        """Set up the table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header label
        header = QLabel("Detected Peaks")
        header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Frequency (Hz)", "Magnitude", "Coherence", "Mode", "Notes"]
        )

        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)

        # Column sizing
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        # Connect selection signal
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

    def set_data(self, peaks: List[Dict[str, Any]]):
        """
        Set peaks data to display.

        Args:
            peaks: List of peak dictionaries with keys:
                - freq_hz: frequency in Hz
                - magnitude: magnitude value
                - coherence: coherence value (optional)
                - mode: mode identification (optional)
                - notes: any notes (optional)
        """
        self._peaks = peaks
        self._populate_table()

    def _populate_table(self):
        """Populate the table with peak data."""
        self.table.setRowCount(len(self._peaks))

        for row, peak in enumerate(self._peaks):
            # Frequency
            freq_item = QTableWidgetItem(f"{peak.get('freq_hz', 0):.1f}")
            freq_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 0, freq_item)

            # Magnitude
            mag_item = QTableWidgetItem(f"{peak.get('magnitude', 0):.4f}")
            mag_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 1, mag_item)

            # Coherence
            coh = peak.get("coherence")
            coh_text = f"{coh:.3f}" if coh is not None else "-"
            coh_item = QTableWidgetItem(coh_text)
            coh_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 2, coh_item)

            # Mode identification
            mode_item = QTableWidgetItem(peak.get("mode", ""))
            self.table.setItem(row, 3, mode_item)

            # Notes
            notes_item = QTableWidgetItem(peak.get("notes", ""))
            self.table.setItem(row, 4, notes_item)

    def _on_selection_changed(self):
        """Handle row selection change."""
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if row < len(self._peaks):
                self.peak_selected.emit(self._peaks[row])

    def clear(self):
        """Clear all data from the table."""
        self._peaks = []
        self.table.setRowCount(0)

    def get_selected_peak(self) -> Dict[str, Any]:
        """Get the currently selected peak."""
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if row < len(self._peaks):
                return self._peaks[row]
        return {}

    def export_csv(self, file_path: str):
        """Export peaks to CSV file."""
        import csv

        with open(file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["freq_hz", "magnitude", "coherence", "mode", "notes"])
            for peak in self._peaks:
                writer.writerow(
                    [
                        peak.get("freq_hz", ""),
                        peak.get("magnitude", ""),
                        peak.get("coherence", ""),
                        peak.get("mode", ""),
                        peak.get("notes", ""),
                    ]
                )
