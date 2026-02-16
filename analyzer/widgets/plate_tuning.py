"""
Plate Tuning Widget - Regression-based frequency prediction for lutherie.

Allows builders to:
1. Enter measurement points (mass, frequency, deflection)
2. Set a target frequency
3. See regression line and prediction
4. Know how much wood to remove
"""

from typing import Optional, List
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QGroupBox, QSplitter, QHeaderView,
    QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QColor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from analyzer.analysis.plate_tuning import (
    PlateTuningRegression, TuningPoint, RegressionResult
)


class PlateTuningWidget(QWidget):
    """
    Complete plate tuning interface with data entry, plot, and predictions.
    """

    # Signal when prediction changes
    prediction_updated = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.regression = PlateTuningRegression()
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Main splitter: left (inputs) | right (plot)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # === LEFT PANEL: Inputs ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Plate name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Plate:"))
        self.plate_name_edit = QLineEdit("Untitled Plate")
        self.plate_name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.plate_name_edit)
        left_layout.addLayout(name_layout)

        # Target frequency
        target_group = QGroupBox("Target Frequency")
        target_layout = QHBoxLayout(target_group)
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("e.g. 86")
        self.target_input.setValidator(QDoubleValidator(0, 1000, 1))
        self.target_input.textChanged.connect(self._on_target_changed)
        target_layout.addWidget(self.target_input)
        target_layout.addWidget(QLabel("Hz"))
        left_layout.addWidget(target_group)

        # Measurement table
        table_group = QGroupBox("Measurements")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            "Mass (g)", "Freq (Hz)", "Defl X (mm)", "Defl Y (mm)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(150)
        table_layout.addWidget(self.table)

        # Add/Remove buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Point")
        self.add_btn.clicked.connect(self._add_point_row)
        btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("- Remove")
        self.remove_btn.clicked.connect(self._remove_selected_row)
        btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(self.clear_btn)
        table_layout.addLayout(btn_layout)

        left_layout.addWidget(table_group)

        # Prediction display
        pred_group = QGroupBox("Prediction")
        pred_layout = QGridLayout(pred_group)

        pred_layout.addWidget(QLabel("Current:"), 0, 0)
        self.current_label = QLabel("-")
        self.current_label.setStyleSheet("font-weight: bold;")
        pred_layout.addWidget(self.current_label, 0, 1)

        pred_layout.addWidget(QLabel("Target:"), 1, 0)
        self.target_label = QLabel("-")
        self.target_label.setStyleSheet("font-weight: bold; color: #4a9;")
        pred_layout.addWidget(self.target_label, 1, 1)

        pred_layout.addWidget(QLabel("Remove:"), 2, 0)
        self.remove_label = QLabel("-")
        self.remove_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #f80;")
        pred_layout.addWidget(self.remove_label, 2, 1)

        pred_layout.addWidget(QLabel("Rate:"), 3, 0)
        self.rate_label = QLabel("-")
        pred_layout.addWidget(self.rate_label, 3, 1)

        pred_layout.addWidget(QLabel("Fit (R²):"), 4, 0)
        self.fit_label = QLabel("-")
        pred_layout.addWidget(self.fit_label, 4, 1)

        left_layout.addWidget(pred_group)

        # Save/Load buttons
        file_layout = QHBoxLayout()
        save_btn = QPushButton("Save Session")
        save_btn.clicked.connect(self._save_session)
        file_layout.addWidget(save_btn)

        load_btn = QPushButton("Load Session")
        load_btn.clicked.connect(self._load_session)
        file_layout.addWidget(load_btn)
        left_layout.addLayout(file_layout)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # === RIGHT PANEL: Plot ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Matplotlib figure
        self.figure = Figure(figsize=(8, 6), facecolor='#1e1e1e')
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self._setup_plot_style()
        right_layout.addWidget(self.canvas)

        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setSizes([350, 650])
        layout.addWidget(splitter)

        # Add initial empty row
        self._add_point_row()

    def _setup_plot_style(self):
        """Apply dark theme to plot."""
        self.ax.set_facecolor('#252526')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')
        self.ax.title.set_color('white')
        for spine in self.ax.spines.values():
            spine.set_color('#555')
        self.ax.grid(True, alpha=0.3, color='#555')
        self.ax.set_xlabel('Mass (g)')
        self.ax.set_ylabel('Frequency (Hz)')
        self.ax.set_title('Plate Tuning Trajectory')

    def _add_point_row(self):
        """Add a new empty row to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Create editable items with validators
        for col in range(4):
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)

        # Connect cell changes
        self.table.cellChanged.connect(self._on_cell_changed)

    def _remove_selected_row(self):
        """Remove the currently selected row."""
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._sync_from_table()
            self._update_plot()
            self._update_prediction()

    def _clear_all(self):
        """Clear all measurement points."""
        self.table.setRowCount(0)
        self.regression.clear_points()
        self._add_point_row()
        self._update_plot()
        self._update_prediction()

    def _on_name_changed(self, text: str):
        """Handle plate name change."""
        self.regression.plate_name = text

    def _on_target_changed(self, text: str):
        """Handle target frequency change."""
        try:
            freq = float(text) if text else None
            self.regression.set_target(freq)
        except ValueError:
            self.regression.set_target(None)
        self._update_plot()
        self._update_prediction()

    def _on_cell_changed(self, row: int, col: int):
        """Handle cell value change."""
        self._sync_from_table()
        self._update_plot()
        self._update_prediction()

    def _sync_from_table(self):
        """Sync regression data from table."""
        self.regression.clear_points()

        for row in range(self.table.rowCount()):
            try:
                mass_item = self.table.item(row, 0)
                freq_item = self.table.item(row, 1)
                defl_x_item = self.table.item(row, 2)
                defl_y_item = self.table.item(row, 3)

                mass_text = mass_item.text() if mass_item else ""
                freq_text = freq_item.text() if freq_item else ""

                if not mass_text or not freq_text:
                    continue

                mass = float(mass_text)
                freq = float(freq_text)

                defl_x = float(defl_x_item.text()) if defl_x_item and defl_x_item.text() else None
                defl_y = float(defl_y_item.text()) if defl_y_item and defl_y_item.text() else None

                point = TuningPoint(
                    mass_g=mass,
                    freq_hz=freq,
                    deflection_x_mm=defl_x,
                    deflection_y_mm=defl_y
                )
                self.regression.add_point(point)

            except ValueError:
                continue  # Skip invalid rows

    def _update_plot(self):
        """Update the trajectory plot."""
        self.ax.clear()
        self._setup_plot_style()

        data = self.regression.get_trajectory_data()

        # Plot measurement points
        if data["points"]["mass_g"]:
            masses = data["points"]["mass_g"]
            freqs = data["points"]["freq_hz"]
            labels = data["points"]["labels"]

            self.ax.scatter(masses, freqs, c='cyan', s=100, zorder=5,
                           edgecolors='white', linewidths=1.5)

            # Label points
            for m, f, lbl in zip(masses, freqs, labels):
                self.ax.annotate(lbl, (m, f), textcoords="offset points",
                               xytext=(5, 5), fontsize=9, color='white')

        # Plot regression line
        if data["line"]:
            line_m = data["line"]["mass_g"]
            line_f = data["line"]["freq_hz"]
            r2 = data["line"]["r_squared"]

            color = '#4a9' if r2 > 0.9 else '#fa0' if r2 > 0.7 else '#f44'
            self.ax.plot(line_m, line_f, color=color, linewidth=2,
                        linestyle='--', alpha=0.8,
                        label=f'R² = {r2:.3f}')

        # Plot target
        if data["target"]:
            target_f = data["target"]["freq_hz"]
            target_m = data["target"]["predicted_mass_g"]

            # Horizontal line at target frequency
            xlim = self.ax.get_xlim()
            self.ax.axhline(y=target_f, color='#4a9', linestyle=':',
                           alpha=0.7, linewidth=1.5)
            self.ax.annotate(f'Target: {target_f:.0f} Hz',
                           xy=(xlim[1], target_f),
                           xytext=(-10, 5), textcoords='offset points',
                           fontsize=10, color='#4a9', ha='right')

            # Target point
            if target_m > 0 and data["line"]:
                self.ax.scatter([target_m], [target_f], c='#4a9', s=150,
                               marker='*', zorder=6, edgecolors='white')
                self.ax.annotate(f'{target_m:.0f}g',
                               xy=(target_m, target_f),
                               xytext=(5, -15), textcoords='offset points',
                               fontsize=9, color='#4a9')

        # Arrow from current to target
        if data["points"]["mass_g"] and data["target"] and data["line"]:
            current_m = data["points"]["mass_g"][-1]
            current_f = data["points"]["freq_hz"][-1]
            target_m = data["target"]["predicted_mass_g"]
            target_f = data["target"]["freq_hz"]

            if target_m > 0:
                self.ax.annotate('',
                    xy=(target_m, target_f),
                    xytext=(current_m, current_f),
                    arrowprops=dict(arrowstyle='->', color='#f80',
                                   lw=2, ls='--'))

        self.ax.legend(loc='upper right', fontsize=9)
        self.figure.tight_layout()
        self.canvas.draw()

    def _update_prediction(self):
        """Update prediction display."""
        pred = self.regression.get_prediction()

        if not pred:
            self.current_label.setText("-")
            self.target_label.setText("-")
            self.remove_label.setText("-")
            self.rate_label.setText("-")
            self.fit_label.setText("-")
            return

        self.current_label.setText(
            f"{pred['current_mass_g']:.1f}g @ {pred['current_freq_hz']:.1f} Hz"
        )
        self.target_label.setText(
            f"{pred['target_mass_g']:.1f}g @ {pred['target_freq_hz']:.1f} Hz"
        )

        remove = pred['mass_to_remove_g']
        if remove > 0:
            self.remove_label.setText(f"↓ {remove:.1f} g")
            self.remove_label.setStyleSheet(
                "font-weight: bold; font-size: 14pt; color: #f80;"
            )
        else:
            self.remove_label.setText(f"(already below target)")
            self.remove_label.setStyleSheet(
                "font-weight: bold; font-size: 11pt; color: #4a9;"
            )

        hz_per_g = pred['hz_per_gram']
        self.rate_label.setText(f"{hz_per_g:.2f} Hz/gram")

        r2 = pred['r_squared']
        conf = pred['confidence']
        color = '#4a9' if conf == 'high' else '#fa0' if conf == 'medium' else '#f44'
        self.fit_label.setText(f"{r2:.3f} ({conf})")
        self.fit_label.setStyleSheet(f"color: {color};")

        self.prediction_updated.emit(pred)

    def _save_session(self):
        """Save tuning session to file."""
        self._sync_from_table()

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Tuning Session",
            f"{self.regression.plate_name.replace(' ', '_')}_tuning.json",
            "JSON Files (*.json)"
        )

        if path:
            try:
                data = self.regression.to_dict()
                Path(path).write_text(json.dumps(data, indent=2))
                QMessageBox.information(self, "Saved", f"Session saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _load_session(self):
        """Load tuning session from file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Tuning Session", "",
            "JSON Files (*.json)"
        )

        if path:
            try:
                data = json.loads(Path(path).read_text())
                self.regression = PlateTuningRegression.from_dict(data)

                # Update UI
                self.plate_name_edit.setText(self.regression.plate_name)
                if self.regression.target_freq_hz:
                    self.target_input.setText(str(self.regression.target_freq_hz))

                # Populate table
                self.table.setRowCount(0)
                for point in self.regression.points:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(str(point.mass_g)))
                    self.table.setItem(row, 1, QTableWidgetItem(str(point.freq_hz)))
                    if point.deflection_x_mm is not None:
                        self.table.setItem(row, 2, QTableWidgetItem(str(point.deflection_x_mm)))
                    if point.deflection_y_mm is not None:
                        self.table.setItem(row, 3, QTableWidgetItem(str(point.deflection_y_mm)))

                self._update_plot()
                self._update_prediction()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load:\n{e}")

    def set_sample_data(self):
        """Load sample data for demonstration."""
        # Typical guitar top tuning progression
        sample_points = [
            (145.0, 98.5),   # Starting point
            (138.0, 92.0),   # After first thinning
            (132.0, 88.5),   # Getting closer
        ]

        self.table.setRowCount(0)
        for mass, freq in sample_points:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(mass)))
            self.table.setItem(row, 1, QTableWidgetItem(str(freq)))
            self.table.setItem(row, 2, QTableWidgetItem(""))
            self.table.setItem(row, 3, QTableWidgetItem(""))

        self.target_input.setText("86")
        self._sync_from_table()
        self._update_plot()
        self._update_prediction()
