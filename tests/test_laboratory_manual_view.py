# INSTRUMENT CLASS: MEASUREMENT
"""GUI tests for the Laboratory Manual desktop view (DO-97).

Verifies the Help -> Laboratory Manual navigation entry, view creation, the
controlled empty state, status/revision visibility for registered content,
read-only behavior, and the controlled missing-document state.

Skipped in full when PyQt6 is unavailable, per the repository's optional-GUI
dependency convention.
"""

from __future__ import annotations

from unittest import mock

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QTextBrowser

from analyzer.widgets.laboratory_manual_view import (
    LaboratoryManualView,
    ManualViewState,
    classify_manifest_load,
    _EMPTY_STATE_TEXT,
    _INVALID_STATE_TEXT,
    _MISSING_DOCUMENT_TEXT,
    _UNAVAILABLE_STATE_TEXT,
)
from tap_tone_pi.acoustic_lab import (
    LaboratoryManualEntryV1,
    LaboratoryManualManifestV1,
    ManualContractError,
    ManualRegistryError,
)

_VIEW_MODULE = "analyzer.widgets.laboratory_manual_view"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _entry(**kw) -> LaboratoryManualEntryV1:
    base = dict(
        doc_id="setup1",
        title="Bench Setup",
        path="setup1.md",
        section="Setup",
        status="provisional",
        revision="0.3",
    )
    base.update(kw)
    return LaboratoryManualEntryV1(**base)


class TestNavigationEntry:
    def test_help_menu_has_laboratory_manual_entry(self, qapp):
        from analyzer.main_window import MainWindow

        win = MainWindow()
        try:
            help_menu = next(
                m.menu()
                for m in win.menuBar().actions()
                if m.menu() and m.text().replace("&", "") == "Help"
            )
            labels = [a.text().replace("&", "") for a in help_menu.actions()]
            assert "Laboratory Manual" in labels
        finally:
            win.close()

    def test_entry_opens_view(self, qapp):
        from analyzer.main_window import MainWindow

        win = MainWindow()
        try:
            win._show_laboratory_manual()
            assert isinstance(win._laboratory_manual_view, LaboratoryManualView)
        finally:
            win._laboratory_manual_view.close()
            win.close()


class TestEmptyState:
    def test_empty_manifest_shows_controlled_message(self, qapp):
        # The packaged manifest is empty by design.
        view = LaboratoryManualView()
        try:
            browser = view.findChild(QTextBrowser)
            assert _EMPTY_STATE_TEXT in browser.toPlainText()
        finally:
            view.close()


class TestPopulatedView:
    @pytest.fixture
    def two_entries(self):
        return LaboratoryManualManifestV1(
            manual_revision="1.0",
            entries=(
                _entry(doc_id="a", title="Tap Location", status="approved"),
                _entry(doc_id="b", title="Draft Method", status="deferred", path="b.md"),
            ),
        )

    def test_status_and_revision_visible_on_selection(self, qapp, two_entries):
        with mock.patch(
            "analyzer.widgets.laboratory_manual_view.load_laboratory_manual_manifest",
            return_value=two_entries,
        ), mock.patch(
            "analyzer.widgets.laboratory_manual_view.read_manual_entry_text",
            return_value="# Tap Location\n\nBody.",
        ):
            view = LaboratoryManualView()
            try:
                # Select the first leaf (Setup -> Tap Location).
                nav = view._nav
                section = nav.topLevelItem(0)
                leaf = section.child(0)
                nav.setCurrentItem(leaf)

                assert view._title_label.text() == "Tap Location"
                assert "APPROVED" in view._status_label.text()
                assert "0.3" in view._revision_label.text()
                assert "Tap Location" in view.findChild(QTextBrowser).toPlainText()
            finally:
                view.close()

    def test_document_view_is_read_only(self, qapp, two_entries):
        with mock.patch(
            "analyzer.widgets.laboratory_manual_view.load_laboratory_manual_manifest",
            return_value=two_entries,
        ):
            view = LaboratoryManualView()
            try:
                browser = view.findChild(QTextBrowser)
                assert browser.isReadOnly()
            finally:
                view.close()

    def test_missing_document_shows_controlled_state(self, qapp, two_entries):  # G-04
        from tap_tone_pi.acoustic_lab import ManualDocumentMissingError

        with mock.patch(
            f"{_VIEW_MODULE}.load_laboratory_manual_manifest",
            return_value=two_entries,
        ), mock.patch(
            f"{_VIEW_MODULE}.read_manual_entry_text",
            side_effect=ManualDocumentMissingError("gone"),
        ):
            view = LaboratoryManualView()
            try:
                leaf = view._nav.topLevelItem(0).child(0)
                view._nav.setCurrentItem(leaf)
                text = view.findChild(QTextBrowser).toPlainText()
                assert _MISSING_DOCUMENT_TEXT in text
                # The document ID is surfaced for the operator.
                assert "a" in text
            finally:
                view.close()


class TestLoadStateClassification:
    """The four operational states must be distinct and truthfully labeled."""

    def test_empty_manifest_state_and_copy(self, qapp):  # G-01
        empty = LaboratoryManualManifestV1(manual_revision="1.0", entries=())
        with mock.patch(
            f"{_VIEW_MODULE}.load_laboratory_manual_manifest", return_value=empty
        ):
            assert classify_manifest_load().state is ManualViewState.EMPTY
            view = LaboratoryManualView()
            try:
                text = view.findChild(QTextBrowser).toPlainText()
                assert _EMPTY_STATE_TEXT in text
                assert _UNAVAILABLE_STATE_TEXT not in text
                assert _INVALID_STATE_TEXT not in text
            finally:
                view.close()

    def test_unavailable_manifest_state_and_copy(self, qapp):  # G-02
        with mock.patch(
            f"{_VIEW_MODULE}.load_laboratory_manual_manifest",
            side_effect=ManualRegistryError("no package data"),
        ):
            assert classify_manifest_load().state is ManualViewState.UNAVAILABLE
            view = LaboratoryManualView()
            try:
                text = view.findChild(QTextBrowser).toPlainText()
                assert _UNAVAILABLE_STATE_TEXT in text
                assert _EMPTY_STATE_TEXT not in text
                assert "no package data" in text
            finally:
                view.close()

    def test_invalid_manifest_state_and_copy(self, qapp):  # G-03
        with mock.patch(
            f"{_VIEW_MODULE}.load_laboratory_manual_manifest",
            side_effect=ManualContractError("bad manifest"),
        ):
            assert classify_manifest_load().state is ManualViewState.INVALID
            view = LaboratoryManualView()
            try:
                text = view.findChild(QTextBrowser).toPlainText()
                assert _INVALID_STATE_TEXT in text
                assert _EMPTY_STATE_TEXT not in text
            finally:
                view.close()

    def test_malformed_manifest_does_not_crash_construction(self, qapp):  # G-03
        # A ManualContractError during load must be absorbed, not propagated.
        with mock.patch(
            f"{_VIEW_MODULE}.load_laboratory_manual_manifest",
            side_effect=ManualContractError("boom"),
        ):
            view = LaboratoryManualView()  # must not raise
            view.close()

    def test_empty_and_invalid_use_different_copy(self):
        assert _EMPTY_STATE_TEXT != _INVALID_STATE_TEXT
        assert _EMPTY_STATE_TEXT != _UNAVAILABLE_STATE_TEXT
        assert _INVALID_STATE_TEXT != _UNAVAILABLE_STATE_TEXT
