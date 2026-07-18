"""
analyzer/widgets/limit_editor_panel.py

LimitEditorPanel — QDockWidget for selecting, applying, and inspecting
limit curves against the loaded spectrum.

LAYOUT:
  ┌──────────────────────────────────────┐
  │  Limit Curves                        │  ← dock title
  ├──────────────────────────────────────┤
  │  Preset  [tonewood_tap ▼] [Apply]    │
  │          [Load file...] [Clear]      │
  ├──────────────────────────────────────┤
  │  ● PASS  · 0 violations              │  ← verdict badge (live)
  │    Warn margin: ±3 dB                │
  ├──────────────────────────────────────┤
  │  Violations                          │
  │  (none)                              │  ← scrollable list
  └──────────────────────────────────────┘

Signals:
  preset_selected(str)      — user selected a preset and clicked Apply
  file_selected(str)        — user loaded a file
  limits_cleared()          — user clicked Clear
  warn_margin_changed(float)— user changed the warn margin spinner
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtGui import QFont, QColor

from tap_tone_pi.limits.testing import TestVerdict
from tap_tone_pi.limits.presets import get_preset_names


_VERDICT_COLOURS = {
    TestVerdict.PASS: ("#538135", "#E2EFDA"),
    TestVerdict.WARN: ("#843C0C", "#FFF2CC"),
    TestVerdict.FAIL: ("#7B0000", "#FCE4D6"),
}

_VERDICT_LABELS = {
    TestVerdict.PASS: "PASS",
    TestVerdict.WARN: "WARN",
    TestVerdict.FAIL: "FAIL",
}


class LimitEditorPanel(QDockWidget):
    """
    Dock panel for limit curve selection, application, and verdict display.

    Signals:
        preset_selected(str)       — emitted when user clicks Apply with a preset
        file_selected(str)         — emitted when user loads a JSON limit file
        limits_cleared()           — emitted when user clicks Clear
        warn_margin_changed(float) — emitted when warn margin spinner changes
    """

    preset_selected    = pyqtSignal(str)
    file_selected      = pyqtSignal(str)
    limits_cleared     = pyqtSignal()
    warn_margin_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Limit Curves", parent)
        self.setObjectName("LimitEditorPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setMinimumWidth(240)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── Preset selector ───────────────────────────────────────────────
        preset_group_label = QLabel("Preset")
        preset_group_label.setStyleSheet("font-weight: bold; font-size: 11px; color: palette(mid);")
        layout.addWidget(preset_group_label)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        self._preset_combo = QComboBox()
        for name in get_preset_names():
            self._preset_combo.addItem(name.replace("_", " ").title(), name)
        self._preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        preset_row.addWidget(self._preset_combo)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setFixedHeight(26)
        self._apply_btn.setToolTip("Apply selected preset to spectrum")
        self._apply_btn.clicked.connect(self._on_apply)
        preset_row.addWidget(self._apply_btn)
        layout.addLayout(preset_row)

        file_row = QHBoxLayout()
        file_row.setSpacing(4)
        self._load_file_btn = QPushButton("Load file...")
        self._load_file_btn.setFixedHeight(26)
        self._load_file_btn.setToolTip("Load limit curves from a JSON file")
        self._load_file_btn.clicked.connect(self._on_load_file)
        file_row.addWidget(self._load_file_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(26)
        self._clear_btn.setToolTip("Remove all limit curves from the spectrum")
        self._clear_btn.clicked.connect(self._on_clear)
        file_row.addWidget(self._clear_btn)
        layout.addLayout(file_row)

        # ── Warn margin ───────────────────────────────────────────────────
        margin_row = QHBoxLayout()
        margin_row.setSpacing(4)
        margin_label = QLabel("Warn margin:")
        margin_label.setFixedWidth(88)
        margin_row.addWidget(margin_label)

        self._margin_spinner = QDoubleSpinBox()
        self._margin_spinner.setRange(0.5, 20.0)
        self._margin_spinner.setSingleStep(0.5)
        self._margin_spinner.setValue(3.0)
        self._margin_spinner.setSuffix(" dB")
        self._margin_spinner.setFixedWidth(80)
        self._margin_spinner.setToolTip(
            "Violations within this margin of the limit are WARN, not FAIL"
        )
        self._margin_spinner.valueChanged.connect(
            lambda v: self.warn_margin_changed.emit(v)
        )
        margin_row.addWidget(self._margin_spinner)
        margin_row.addStretch()
        layout.addLayout(margin_row)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Verdict badge ─────────────────────────────────────────────────
        self._verdict_card = QFrame()
        self._verdict_card.setObjectName("VerdictCard")
        self._verdict_card.setFrameShape(QFrame.Shape.StyledPanel)
        verdict_layout = QVBoxLayout(self._verdict_card)
        verdict_layout.setContentsMargins(8, 6, 8, 6)
        verdict_layout.setSpacing(2)

        verdict_header = QHBoxLayout()
        self._verdict_badge = QLabel("—")
        badge_font = QFont()
        badge_font.setPointSize(11)
        badge_font.setBold(True)
        self._verdict_badge.setFont(badge_font)
        verdict_header.addWidget(self._verdict_badge)
        verdict_header.addStretch()
        self._violation_count_label = QLabel("")
        self._violation_count_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        verdict_header.addWidget(self._violation_count_label)
        verdict_layout.addLayout(verdict_header)

        self._active_preset_label = QLabel("No limits active")
        self._active_preset_label.setStyleSheet("color: palette(mid); font-style: italic; font-size: 10px;")
        verdict_layout.addWidget(self._active_preset_label)
        layout.addWidget(self._verdict_card)

        # ── Violations list ───────────────────────────────────────────────
        violations_label = QLabel("Violations")
        violations_label.setStyleSheet("font-weight: bold; font-size: 11px; color: palette(mid);")
        layout.addWidget(violations_label)

        self._violations_list = QListWidget()
        self._violations_list.setMaximumHeight(140)
        self._violations_list.setStyleSheet(
            "QListWidget { font-size: 10px; border: none; background: transparent; }"
            "QListWidget::item { padding: 1px 2px; }"
        )
        layout.addWidget(self._violations_list)

        layout.addStretch()
        self.setWidget(container)

        # Internal state
        self._active_preset: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────

    def update_verdict(
        self,
        verdict: Optional[TestVerdict],
        violation_count: int = 0,
        worst_margin_db: float = float("inf"),
        active_preset: Optional[str] = None,
        violation_details: Optional[list] = None,
    ) -> None:
        """
        Update the verdict display with the result of a limit test.
        Called by MainWindow after LimitOverlay.draw() returns a result.
        """
        if active_preset:
            self._active_preset = active_preset
            self._active_preset_label.setText(
                active_preset.replace("_", " ").title()
            )

        if verdict is None:
            self._verdict_badge.setText("—")
            self._verdict_badge.setStyleSheet("color: palette(mid);")
            self._violation_count_label.setText("")
            self._verdict_card.setStyleSheet("")
            self._violations_list.clear()
            item = QListWidgetItem("No limits active")
            item.setForeground(QColor("#888780"))
            self._violations_list.addItem(item)
            return

        text_colour, bg_colour = _VERDICT_COLOURS[verdict]
        label = _VERDICT_LABELS[verdict]

        self._verdict_badge.setText(label)
        self._verdict_badge.setStyleSheet(f"color: {text_colour};")
        self._verdict_card.setStyleSheet(
            f"#VerdictCard {{ border-left: 3px solid {text_colour};"
            f" background: {bg_colour}; border-radius: 3px; }}"
        )

        if violation_count == 0:
            self._violation_count_label.setText("· 0 violations")
        elif verdict == TestVerdict.WARN:
            self._violation_count_label.setText(
                f"· {violation_count} within ±{worst_margin_db:.1f} dB"
            )
        else:
            self._violation_count_label.setText(
                f"· {violation_count} violation(s)"
            )

        # Populate violations list
        self._violations_list.clear()
        if not violation_details:
            item = QListWidgetItem("No violations")
            item.setForeground(QColor("#538135"))
            self._violations_list.addItem(item)
        else:
            for v in violation_details[:30]:
                freq = v.get("frequency_hz", 0.0)
                margin = v.get("margin_db", 0.0)
                limit_name = v.get("limit_name", "")
                text = f"{freq:.1f} Hz  {margin:+.1f} dB  [{limit_name}]"
                item = QListWidgetItem(text)
                item.setForeground(QColor(text_colour))
                self._violations_list.addItem(item)

    def clear_verdict(self) -> None:
        """Reset verdict to no-limits state."""
        self.update_verdict(None)

    def current_warn_margin(self) -> float:
        return self._margin_spinner.value()

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_apply(self) -> None:
        idx = self._preset_combo.currentIndex()
        preset_key = self._preset_combo.itemData(idx)
        if preset_key:
            self.preset_selected.emit(preset_key)

    def _on_load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Limit Curves",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if path:
            self.file_selected.emit(path)

    def _on_clear(self) -> None:
        self.clear_verdict()
        self._active_preset_label.setText("No limits active")
        self.limits_cleared.emit()
