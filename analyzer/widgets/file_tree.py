"""
File tree widget for navigating viewer pack contents.
"""

from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel
from PyQt6.QtCore import pyqtSignal


class FileTreeWidget(QWidget):
    """Widget for displaying viewer pack file structure."""

    file_selected = pyqtSignal(dict)  # Emitted when a file is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pack: Optional[Dict[str, Any]] = None
        self._setup_ui()

    def _setup_ui(self):
        """Set up the tree UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header
        header = QLabel("Pack Contents")
        header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(self.tree)

    def set_pack(self, pack: Dict[str, Any]):
        """
        Set the viewer pack to display.

        Args:
            pack: Viewer pack dictionary with structure:
                - metadata: session/capture metadata
                - spectra: list of spectrum files
                - peaks: list of peak files
                - raw_audio: list of audio files (optional)
        """
        self._pack = pack
        self._populate_tree()

    def _populate_tree(self):
        """Populate the tree with pack contents."""
        self.tree.clear()

        if not self._pack:
            return

        # Root item with pack name
        pack_name = self._pack.get("name", "Viewer Pack")
        root = QTreeWidgetItem(self.tree, [pack_name])
        root.setExpanded(True)

        # Metadata section
        metadata = self._pack.get("metadata", {})
        if metadata:
            meta_item = QTreeWidgetItem(root, ["Metadata"])
            meta_item.setExpanded(True)

            session_meta = metadata.get("session")
            if session_meta:
                session_item = QTreeWidgetItem(meta_item, ["Session Info"])
                session_item.setData(
                    0,
                    256,
                    {"type": "metadata", "subtype": "session", "data": session_meta},
                )

            capture_meta = metadata.get("capture")
            if capture_meta:
                capture_item = QTreeWidgetItem(meta_item, ["Capture Info"])
                capture_item.setData(
                    0,
                    256,
                    {"type": "metadata", "subtype": "capture", "data": capture_meta},
                )

        # Spectra section
        spectra = self._pack.get("spectra", [])
        if spectra:
            spectra_item = QTreeWidgetItem(root, [f"Spectra ({len(spectra)})"])
            spectra_item.setExpanded(True)

            for spec in spectra:
                name = spec.get("name", "spectrum")
                item = QTreeWidgetItem(spectra_item, [name])
                item.setData(
                    0, 256, {"type": "spectrum", "name": name, "data": spec.get("data")}
                )

        # Peaks section
        peaks_list = self._pack.get("peaks", [])
        if peaks_list:
            peaks_item = QTreeWidgetItem(root, [f"Peaks ({len(peaks_list)})"])

            for peak_file in peaks_list:
                name = peak_file.get("name", "peaks")
                item = QTreeWidgetItem(peaks_item, [name])
                item.setData(
                    0,
                    256,
                    {"type": "peaks", "name": name, "data": peak_file.get("data")},
                )

        # Derived data section
        derived = self._pack.get("derived", {})
        if derived:
            derived_item = QTreeWidgetItem(root, ["Derived Data"])

            for key, value in derived.items():
                item = QTreeWidgetItem(derived_item, [key])
                item.setData(0, 256, {"type": "derived", "name": key, "data": value})

        # Raw audio section (if available)
        raw_audio = self._pack.get("raw_audio", [])
        if raw_audio:
            audio_item = QTreeWidgetItem(root, [f"Raw Audio ({len(raw_audio)})"])

            for audio in raw_audio:
                name = audio.get("name", "audio")
                item = QTreeWidgetItem(audio_item, [name])
                item.setData(
                    0, 256, {"type": "audio", "name": name, "path": audio.get("path")}
                )

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle single click on tree item."""
        data = item.data(0, 256)
        if data:
            self.file_selected.emit(data)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double click on tree item."""
        data = item.data(0, 256)
        if data:
            # Double-click could trigger a different action (e.g., open in new window)
            self.file_selected.emit(data)

    def clear(self):
        """Clear the tree."""
        self._pack = None
        self.tree.clear()

    def get_selected_item(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected item's data."""
        selected = self.tree.selectedItems()
        if selected:
            return selected[0].data(0, 256)
        return None
