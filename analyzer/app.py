"""
Main application entry point for tap_tone_pi Analyzer.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from analyzer.main_window import MainWindow


def main():
    """Launch the analyzer application."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Tap Tone Analyzer")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("tap_tone_pi")

    # Set dark theme
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()

    # Ensure window comes to foreground on Windows
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec())


DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
}

QMenuBar {
    background-color: #2d2d2d;
    color: #cccccc;
}

QMenuBar::item:selected {
    background-color: #3d3d3d;
}

QMenu {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #3d3d3d;
}

QMenu::item:selected {
    background-color: #094771;
}

QToolBar {
    background-color: #2d2d2d;
    border: none;
    spacing: 4px;
    padding: 4px;
}

QStatusBar {
    background-color: #007acc;
    color: white;
}

QTreeView, QListView, QTableView {
    background-color: #252526;
    border: 1px solid #3d3d3d;
    color: #cccccc;
}

QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {
    background-color: #094771;
}

QHeaderView::section {
    background-color: #2d2d2d;
    color: #cccccc;
    padding: 4px;
    border: 1px solid #3d3d3d;
}

QTabWidget::pane {
    border: 1px solid #3d3d3d;
    background-color: #1e1e1e;
}

QTabBar::tab {
    background-color: #2d2d2d;
    color: #cccccc;
    padding: 8px 16px;
    border: 1px solid #3d3d3d;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-bottom: 2px solid #007acc;
}

QPushButton {
    background-color: #0e639c;
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 2px;
}

QPushButton:hover {
    background-color: #1177bb;
}

QPushButton:pressed {
    background-color: #094771;
}

QPushButton:disabled {
    background-color: #3d3d3d;
    color: #6d6d6d;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #3d3d3d;
    padding: 4px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #007acc;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
}

QScrollBar::handle:vertical {
    background-color: #5a5a5a;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #6d6d6d;
}

QSplitter::handle {
    background-color: #3d3d3d;
}

QGroupBox {
    border: 1px solid #3d3d3d;
    margin-top: 8px;
    padding-top: 8px;
}

QGroupBox::title {
    color: #cccccc;
    subcontrol-origin: margin;
    left: 8px;
}

QLabel {
    color: #cccccc;
}

QCheckBox {
    color: #cccccc;
}

QCheckBox::indicator:checked {
    background-color: #007acc;
}

QComboBox {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #3d3d3d;
    padding: 4px;
}

QComboBox:hover {
    border: 1px solid #007acc;
}

QComboBox::drop-down {
    border: none;
}

QSpinBox, QDoubleSpinBox {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #3d3d3d;
}
"""


if __name__ == "__main__":
    main()
