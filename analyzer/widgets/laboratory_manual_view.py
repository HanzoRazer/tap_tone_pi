"""Laboratory Manual view — read-only offline browser for packaged procedures.

Presents the Laboratory Manual registered in
``tap_tone_pi.acoustic_lab``: a section/title list on the left, the selected
document rendered read-only on the right, with the procedure's maturity status
and revision always visible.

This view reads. It does not edit, author, annotate, or export. It renders the
packaged Markdown source through QTextBrowser without rewriting it. Maturity
status is shown so an operator can never mistake a provisional or deferred
procedure for an approved measurement method.

The view depends only on the read-only Laboratory registry API. It does not
import any measurement-execution module.

Manifest loading is a controlled operation. A malformed packaged manifest
(``ManualContractError``) and an unavailable manifest (``ManualRegistryError``)
are distinct, visibly different states — neither may crash view construction or
the Help action. A missing selected document is an entry-display failure, not a
manifest-load state, and is reported separately.
"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tap_tone_pi.acoustic_lab import (
    LaboratoryManualEntryV1,
    ManualContractError,
    ManualRegistryError,
    ManualStatus,
    list_manual_entries,
    load_laboratory_manual_manifest,
    read_manual_entry_text,
)

# Both failure families can surface while loading a packaged manifest: the
# registry raises ManualRegistryError when resources are absent/unreadable, and
# the contract raises ManualContractError when the manifest parses but violates
# an identity/status rule. The desktop boundary must catch both.
_MANUAL_LOAD_ERRORS = (ManualRegistryError, ManualContractError)


class ManualViewState(Enum):
    """Load state of the manual, driving which controlled copy is shown."""

    READY = "ready"  # valid manifest with at least one entry
    EMPTY = "empty"  # valid manifest, zero entries
    UNAVAILABLE = "unavailable"  # manifest resources absent/unreadable
    INVALID = "invalid"  # manifest present but contract-invalid/malformed


# Primary user-facing copy per non-ready state (DO-97G §6.7).
_EMPTY_STATE_TEXT = "No laboratory procedures are currently registered."
_UNAVAILABLE_STATE_TEXT = "The Laboratory Manual is unavailable in this installation."
_INVALID_STATE_TEXT = (
    "The Laboratory Manual manifest is invalid and cannot be displayed."
)
_MISSING_DOCUMENT_TEXT = "This registered procedure is unavailable."

_STATE_MESSAGES: dict[ManualViewState, str] = {
    ManualViewState.EMPTY: _EMPTY_STATE_TEXT,
    ManualViewState.UNAVAILABLE: _UNAVAILABLE_STATE_TEXT,
    ManualViewState.INVALID: _INVALID_STATE_TEXT,
}

# Visual distinction by maturity (status must be visible).
_STATUS_COLORS: dict[ManualStatus, str] = {
    ManualStatus.APPROVED: "#1b7f37",
    ManualStatus.PROVISIONAL: "#b8860b",
    ManualStatus.DEFERRED: "#6a6a6a",
    ManualStatus.SUPERSEDED: "#8a4a4a",
}

_STATUS_LABELS: dict[ManualStatus, str] = {
    ManualStatus.APPROVED: "APPROVED — validated procedure",
    ManualStatus.PROVISIONAL: "PROVISIONAL — under controlled evaluation",
    ManualStatus.DEFERRED: "DEFERRED — not authorized for execution",
    ManualStatus.SUPERSEDED: "SUPERSEDED — retained for lineage",
}

_ROLE_ENTRY = Qt.ItemDataRole.UserRole


class ManualLoadResult:
    """Outcome of classifying a manifest load — GUI-free and unit-testable."""

    __slots__ = ("state", "entries", "detail")

    def __init__(
        self,
        state: ManualViewState,
        entries: tuple[LaboratoryManualEntryV1, ...],
        detail: str | None,
    ) -> None:
        self.state = state
        self.entries = entries
        self.detail = detail


def classify_manifest_load() -> ManualLoadResult:
    """Load the packaged manifest and classify the outcome.

    Distinguishes the four operational states without touching Qt, so the
    state-classification logic can be tested without a display. A contract
    failure (malformed/invalid manifest) is reported as INVALID; a registry
    failure (resources absent/unreadable) as UNAVAILABLE. These are never
    conflated — telling an operator "no procedures are registered" when the
    manifest actually failed to load would be a lie.
    """
    try:
        manifest = load_laboratory_manual_manifest()
    except ManualContractError as exc:
        return ManualLoadResult(ManualViewState.INVALID, (), str(exc))
    except ManualRegistryError as exc:
        return ManualLoadResult(ManualViewState.UNAVAILABLE, (), str(exc))

    entries = list_manual_entries(manifest)
    state = ManualViewState.READY if entries else ManualViewState.EMPTY
    return ManualLoadResult(state, entries, None)


class LaboratoryManualView(QWidget):
    """Read-only navigator and reader for the packaged Laboratory Manual."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Laboratory Manual")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(900, 640)

        self._entries: tuple[LaboratoryManualEntryV1, ...] = ()
        self._state: ManualViewState = ManualViewState.EMPTY
        self._load_detail: str | None = None

        self._build_ui()
        self._load_manifest()
        self._populate_navigation()

    # -- construction --------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self._nav = QTreeWidget()
        self._nav.setHeaderLabel("Procedures")
        self._nav.setMinimumWidth(240)
        self._nav.currentItemChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._nav)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self._title_label = QLabel("")
        title_font = self._title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        self._title_label.setFont(title_font)
        header.addWidget(self._title_label, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header.addWidget(self._status_label)
        right_layout.addLayout(header)

        self._revision_label = QLabel("")
        self._revision_label.setStyleSheet("color: #666;")
        right_layout.addWidget(self._revision_label)

        # QTextBrowser is inherently read-only; setMarkdown renders offline
        # without transforming the source file. No editing surface is exposed.
        self._document = QTextBrowser()
        self._document.setOpenExternalLinks(False)
        self._document.setOpenLinks(False)
        right_layout.addWidget(self._document, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    # -- data ----------------------------------------------------------------

    def _load_manifest(self) -> None:
        """Classify the manifest load, capturing state and any detail.

        Both registry and contract failures are absorbed here so that neither a
        missing package nor a malformed manifest can crash view construction.
        """
        result = classify_manifest_load()
        self._state = result.state
        self._entries = result.entries
        self._load_detail = result.detail

    def _populate_navigation(self) -> None:
        """Fill the tree, grouping by section in authored order."""
        self._nav.clear()

        if self._state is not ManualViewState.READY or not self._entries:
            self._show_state_message()
            return

        section_items: dict[str, QTreeWidgetItem] = {}
        for entry in self._entries:
            section_item = section_items.get(entry.section)
            if section_item is None:
                section_item = QTreeWidgetItem([entry.section])
                section_item.setFlags(
                    section_item.flags() & ~Qt.ItemFlag.ItemIsSelectable
                )
                self._nav.addTopLevelItem(section_item)
                section_items[entry.section] = section_item

            leaf = QTreeWidgetItem([entry.title])
            leaf.setData(0, _ROLE_ENTRY, entry)
            color = _STATUS_COLORS.get(entry.status)
            if color is not None:
                leaf.setForeground(0, QColor(color))
            section_item.addChild(leaf)

        self._nav.expandAll()

    def _show_state_message(self) -> None:
        """Render the controlled copy for a non-ready (or empty) state.

        Empty, unavailable, and invalid states use distinct primary messages, so
        an operator is never told procedures are unregistered when the manifest
        actually failed to load. Technical detail, when present, is shown below.
        """
        self._title_label.setText("")
        self._status_label.setText("")
        self._status_label.setStyleSheet("")
        self._revision_label.setText("")

        primary = _STATE_MESSAGES.get(self._state, _EMPTY_STATE_TEXT)
        if self._load_detail:
            self._document.setPlainText(f"{primary}\n\nDetails:\n{self._load_detail}")
        else:
            self._document.setPlainText(primary)

    # -- interaction ---------------------------------------------------------

    def _on_selection_changed(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            return
        entry = current.data(0, _ROLE_ENTRY)
        if isinstance(entry, LaboratoryManualEntryV1):
            self._display_entry(entry)

    def _display_entry(self, entry: LaboratoryManualEntryV1) -> None:
        """Render one procedure with its status and revision visible."""
        self._title_label.setText(entry.title)

        status_text = _STATUS_LABELS.get(entry.status, entry.status.value.upper())
        color = _STATUS_COLORS.get(entry.status, "#000000")
        self._status_label.setText(status_text)
        self._status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        revision = f"Revision {entry.revision}"
        if entry.superseded_by is not None:
            revision += f"  ·  superseded by {entry.superseded_by}"
        self._revision_label.setText(revision)

        try:
            text = read_manual_entry_text(entry)
        except _MANUAL_LOAD_ERRORS as exc:
            # Missing/unreadable registered document — an entry-display failure,
            # not a manifest-load state. Never a crash.
            self._document.setPlainText(
                f"{_MISSING_DOCUMENT_TEXT}\n\n"
                f"Document ID: {entry.doc_id}\n\nDetails:\n{exc}"
            )
            return

        self._document.setMarkdown(text)
