"""
analyzer/guidance/panel.py

# INSTRUMENT CLASS: DECISION SUPPORT
# This widget displays guidance directives to the operator.
# It is display-layer only. It cannot trigger capture, modify session
# files, or write to disk. See docs/ADR-0009-advisory-boundary.md

GuidancePanelWidget — QDockWidget that renders AttentionDirectiveV1
directives from AnalyzerGuidanceEngine.

LAYOUT:
  ┌─────────────────────────────────────────────┐
  │  Guidance  [stage: ▼ novice]         [✕ dismiss]  │  ← header
  ├─────────────────────────────────────────────┤
  │  ● REVIEW                                   │
  │  Wolf candidate at 247 Hz — WSI 0.72        │  ← current directive card
  │                                             │
  │  A potential wolf tone was detected at      │
  │  247 Hz. The beat frequency of 8.3 Hz...    │
  │                              [Act]          │
  ├─────────────────────────────────────────────┤
  │  History                                    │  ← collapsible history list
  │  · Bundle loaded — specimen SP_001          │
  │  · Found 4 peaks — dominant at 203.1 Hz     │
  └─────────────────────────────────────────────┘

CONSTRAINTS (ADR-0009):
  - No ability to trigger capture, modify session files, or write to disk.
  - "Act" button navigates the analyzer UI only (tab switching, region
    highlighting). It emits a pyqtSignal — MainWindow handles it.
  - Stage selector changes guidance verbosity only. No measurement effect.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTextBrowser,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QFrame,
)
from PyQt6.QtGui import QFont, QColor

from tap_tone_pi.agentic.contracts.analyzer_attention import (
    AttentionAction,
    AttentionDirectiveV1,
)
from tap_tone_pi.agent.types import UserStage


# ---------------------------------------------------------------------------
# Action → display colour mapping
# ---------------------------------------------------------------------------

_ACTION_COLOUR: dict[AttentionAction, str] = {
    AttentionAction.INSPECT: "#2E74B5",  # blue
    AttentionAction.REVIEW: "#C55A11",  # amber
    AttentionAction.DECIDE: "#843C0C",  # dark amber
    AttentionAction.INTERVENE: "#7B0000",  # red
}

_ACTION_LABEL: dict[AttentionAction, str] = {
    AttentionAction.INSPECT: "INFO",
    AttentionAction.REVIEW: "REVIEW",
    AttentionAction.DECIDE: "DECIDE",
    AttentionAction.INTERVENE: "URGENT",
}

# Nav targets that "Act" can resolve — MainWindow interprets these
_ACT_NAVIGABLE = {
    "spectrum_region",
    "spectrum_view",
    "bode_plot",
    "wsi_plot",
    "stats_panel",
}


# ---------------------------------------------------------------------------
# DirectiveCard — renders a single AttentionDirectiveV1
# ---------------------------------------------------------------------------


class DirectiveCard(QFrame):
    """
    Renders a single directive as a compact card.

    Signals:
        dismissed   — user clicked Dismiss
        acted       — user clicked Act (carries focus target type)
    """

    dismissed = pyqtSignal(str)  # directive_id
    acted = pyqtSignal(str)  # focus.target_type

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("DirectiveCard")
        self._directive: Optional[AttentionDirectiveV1] = None
        self._auto_timer: Optional[QTimer] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header row: badge + summary + dismiss button
        header = QHBoxLayout()
        header.setSpacing(6)

        self._badge = QLabel()
        self._badge.setFixedWidth(60)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_font = QFont()
        badge_font.setPointSize(9)
        badge_font.setBold(True)
        self._badge.setFont(badge_font)
        self._badge.setStyleSheet("border-radius: 3px; padding: 2px 4px; color: white;")
        header.addWidget(self._badge)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        summary_font = QFont()
        summary_font.setPointSize(10)
        summary_font.setBold(True)
        self._summary_label.setFont(summary_font)
        header.addWidget(self._summary_label)

        self._dismiss_btn = QPushButton("✕")
        self._dismiss_btn.setFixedSize(20, 20)
        self._dismiss_btn.setFlat(True)
        self._dismiss_btn.setToolTip("Dismiss")
        self._dismiss_btn.clicked.connect(self._on_dismiss)
        header.addWidget(self._dismiss_btn)
        layout.addLayout(header)

        # Detail text
        self._detail = QTextBrowser()
        self._detail.setReadOnly(True)
        self._detail.setOpenExternalLinks(False)
        self._detail.setMinimumHeight(60)
        self._detail.setMaximumHeight(220)
        self._detail.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._detail.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; }"
        )
        layout.addWidget(self._detail)

        # Footer: act button (only shown when a navigable focus target exists)
        footer = QHBoxLayout()
        footer.addStretch()
        self._act_btn = QPushButton("Act →")
        self._act_btn.setFixedHeight(24)
        self._act_btn.setToolTip("Navigate to the relevant view")
        self._act_btn.clicked.connect(self._on_act)
        self._act_btn.hide()
        footer.addWidget(self._act_btn)
        layout.addLayout(footer)

        self.hide()

    # ── Public API ────────────────────────────────────────────────────────

    def show_directive(self, directive: AttentionDirectiveV1) -> None:
        """Render a directive in the card."""
        self._directive = directive

        # Cancel any pending auto-dismiss from a previous directive
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = None

        action = directive.action
        colour = _ACTION_COLOUR.get(action, "#595959")
        label = _ACTION_LABEL.get(action, "INFO")

        self._badge.setText(label)
        self._badge.setStyleSheet(
            f"border-radius: 3px; padding: 2px 4px; color: white;"
            f" background-color: {colour};"
        )
        self._summary_label.setText(directive.summary)

        # Render detail as markdown-lite HTML
        detail_html = self._md_to_html(directive.detail or "")
        self._detail.setHtml(detail_html)

        # Act button — only show when focus target is navigable
        focus = directive.focus
        if focus and focus.target_type in _ACT_NAVIGABLE:
            self._act_btn.show()
        else:
            self._act_btn.hide()

        # Border colour reflects urgency
        urgency = directive.urgency or 0.5
        if urgency >= 0.65:
            border_colour = "#843C0C"
        elif urgency >= 0.35:
            border_colour = "#C55A11"
        else:
            border_colour = "#2E74B5"

        self.setStyleSheet(
            f"#DirectiveCard {{ border-left: 3px solid {border_colour};"
            f" background: palette(window); border-radius: 3px; }}"
        )

        self.show()

        # Auto-dismiss timer
        seconds = directive.auto_dismiss_after_seconds
        if seconds and seconds > 0:
            self._auto_timer = QTimer(self)
            self._auto_timer.setSingleShot(True)
            self._auto_timer.timeout.connect(self._on_dismiss)
            self._auto_timer.start(seconds * 1000)

    def clear(self) -> None:
        """Hide and reset the card."""
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = None
        self._directive = None
        self.hide()

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_dismiss(self) -> None:
        if self._directive:
            self.dismissed.emit(self._directive.directive_id)
        self.clear()

    def _on_act(self) -> None:
        if self._directive and self._directive.focus:
            self.acted.emit(self._directive.focus.target_type)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _md_to_html(text: str) -> str:
        """
        Minimal markdown-to-HTML conversion for directive detail text.
        Handles **bold**, *italic*, and \n\n paragraph breaks.
        """
        import re

        # Escape HTML entities first
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # **bold**
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # *italic*
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        # Paragraph breaks
        paragraphs = re.split(r"\n\n+", text)
        html_parts = [
            f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip()
        ]
        return "".join(html_parts)


# ---------------------------------------------------------------------------
# GuidancePanelWidget
# ---------------------------------------------------------------------------


class GuidancePanelWidget(QDockWidget):
    """
    Dock panel that shows AnalyzerGuidanceEngine directives.

    Signals:
        stage_changed(UserStage)     — user changed the stage selector
        act_requested(str)           — user clicked Act (focus target type)
        directive_dismissed(str)     — user dismissed a directive (directive_id)
    """

    stage_changed = pyqtSignal(object)  # UserStage
    act_requested = pyqtSignal(str)  # focus.target_type
    directive_dismissed = pyqtSignal(str)  # directive_id

    # Maximum history items to show in the list
    MAX_HISTORY = 40

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Guidance", parent)
        self.setObjectName("GuidancePanelWidget")
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setMinimumWidth(260)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── Stage selector ────────────────────────────────────────────────
        stage_row = QHBoxLayout()
        stage_row.setSpacing(4)
        stage_label = QLabel("Stage:")
        stage_label.setFixedWidth(44)
        stage_row.addWidget(stage_label)

        self._stage_selector = QComboBox()
        for stage in UserStage:
            self._stage_selector.addItem(stage.value.replace("_", " ").title(), stage)
        self._stage_selector.setCurrentIndex(2)  # REGULAR
        self._stage_selector.setToolTip(
            "Set your experience level — affects how much guidance is shown"
        )
        self._stage_selector.currentIndexChanged.connect(self._on_stage_changed)
        stage_row.addWidget(self._stage_selector)
        layout.addLayout(stage_row)

        # Thin separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Current directive card ────────────────────────────────────────
        self._card = DirectiveCard()
        self._card.dismissed.connect(self._on_card_dismissed)
        self._card.acted.connect(self._on_card_acted)
        layout.addWidget(self._card)

        # Placeholder shown when no directive is active
        self._placeholder = QLabel("No active guidance")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: palette(mid); font-style: italic;")
        layout.addWidget(self._placeholder)

        # ── History list ──────────────────────────────────────────────────
        history_label = QLabel("History")
        history_label.setStyleSheet(
            "font-weight: bold; font-size: 10px; color: palette(mid);"
        )
        layout.addWidget(history_label)

        self._history_list = QListWidget()
        self._history_list.setMaximumHeight(120)
        self._history_list.setStyleSheet(
            "QListWidget { font-size: 10px; border: none; background: transparent; }"
            "QListWidget::item { padding: 1px 2px; }"
        )
        layout.addWidget(self._history_list)

        layout.addStretch()
        self.setWidget(container)

        # Internal state
        self._current_directive_id: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────

    def show_directive(self, directive: AttentionDirectiveV1) -> None:
        """Display a new directive. Adds previous directive to history."""
        self._current_directive_id = directive.directive_id
        self._card.show_directive(directive)
        self._placeholder.hide()
        self._add_to_history(directive)
        # Make sure the panel is visible
        self.show()
        self.raise_()

    def clear_directive(self) -> None:
        """Hide the current directive card."""
        self._card.clear()
        self._current_directive_id = None
        self._placeholder.show()

    def current_stage(self) -> UserStage:
        """Return the currently selected UserStage."""
        idx = self._stage_selector.currentIndex()
        return self._stage_selector.itemData(idx) or UserStage.REGULAR

    def set_stage(self, stage: UserStage) -> None:
        """Programmatically set the stage selector."""
        for i in range(self._stage_selector.count()):
            if self._stage_selector.itemData(i) == stage:
                self._stage_selector.setCurrentIndex(i)
                break

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_stage_changed(self, index: int) -> None:
        stage = self._stage_selector.itemData(index)
        if stage:
            self.stage_changed.emit(stage)

    def _on_card_dismissed(self, directive_id: str) -> None:
        self._current_directive_id = None
        self._placeholder.show()
        self.directive_dismissed.emit(directive_id)

    def _on_card_acted(self, target_type: str) -> None:
        self.act_requested.emit(target_type)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _add_to_history(self, directive: AttentionDirectiveV1) -> None:
        """Add a directive summary line to the history list (newest at top)."""
        action_label = _ACTION_LABEL.get(directive.action, "INFO")
        text = f"[{action_label}] {directive.summary}"
        item = QListWidgetItem(text)
        colour = _ACTION_COLOUR.get(directive.action, "#595959")
        item.setForeground(QColor(colour))
        item.setToolTip(directive.detail[:300] if directive.detail else "")
        self._history_list.insertItem(0, item)

        # Trim to MAX_HISTORY
        while self._history_list.count() > self.MAX_HISTORY:
            self._history_list.takeItem(self._history_list.count() - 1)
