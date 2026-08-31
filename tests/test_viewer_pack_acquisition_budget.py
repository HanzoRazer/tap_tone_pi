"""The acquisition budget published in a viewer pack (DO-107B §26).

One rule underneath all of these: **the pack must contain the exact bytes whose
digest the manifest reports.** A pack that re-serialized the budget on the way in
could not be checked against what was computed, and a float that changed in
transit would be invisible to every reader downstream.

The second rule is that a pack exported from a session with no budget is a
normal pack. Every pack exported before DO-107B is one.

The golden sessions these tests export are fixture sessions. Attaching a budget
to one does not make it a physical acquisition, and nothing here claims it does.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from tap_tone_pi.phase2.session_acquisition import (  # noqa: E402
    attach_acquisition_budget,
    load_acquisition_budget,
)
from tap_tone_pi.uncertainty.acquisition import (  # noqa: E402
    AcquisitionBudgetV1,
    build_acquisition_budget_from_e0,
)
from tap_tone_pi.validate.viewer_pack_v1 import validate_pack  # noqa: E402

from tests.test_e0_acquisition_adapter import POINT, base_budget, executed  # noqa: E402

GOLDEN = ROOT / "runs_phase2" / "session_20260101T235209Z"

BUDGET_RELPATH = "meta/acquisition_budget.json"


def _export(session_dir: Path, out_dir: Path) -> Path:
    from phase2.export_viewer_pack_v1 import export_viewer_pack

    return export_viewer_pack(session_dir, out_dir, as_zip=False)


def _manifest(pack: Path) -> dict:
    return json.loads((pack / "manifest.json").read_text(encoding="utf-8"))


def _entry(manifest: dict, relpath: str) -> dict | None:
    for entry in manifest["files"]:
        if entry["relpath"] == relpath:
            return entry
    return None


@pytest.fixture(scope="module")
def golden_session(tmp_path_factory):
    if not GOLDEN.is_dir():
        pytest.skip(f"golden Phase 2 session not present: {GOLDEN}")
    session = tmp_path_factory.mktemp("session_with_budget") / GOLDEN.name
    shutil.copytree(GOLDEN, session)
    return session


@pytest.fixture(scope="module")
def budget():
    return build_acquisition_budget_from_e0(base_budget(), executed(), POINT).budget


@pytest.fixture(scope="module")
def pack_with_budget(golden_session, budget, tmp_path_factory):
    attach_acquisition_budget(golden_session, budget, replace=True)
    return _export(golden_session, tmp_path_factory.mktemp("pack_with_budget"))


class TestPublishedBudget:
    def test_g1_the_budget_artifact_is_in_the_pack(self, pack_with_budget):
        assert (pack_with_budget / BUDGET_RELPATH).is_file()

    def test_g2_the_manifest_relpath_resolves(self, pack_with_budget):
        entry = _entry(_manifest(pack_with_budget), BUDGET_RELPATH)
        assert entry is not None, "the pack carries the file but does not list it"
        assert (pack_with_budget / entry["relpath"]).is_file()
        assert entry["kind"] == "session_meta"
        assert entry["mime"] == "application/json"

    def test_g3_the_digest_is_of_the_bytes_the_pack_holds(self, pack_with_budget):
        entry = _entry(_manifest(pack_with_budget), BUDGET_RELPATH)
        data = (pack_with_budget / BUDGET_RELPATH).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]

    def test_g4_the_byte_count_matches(self, pack_with_budget):
        entry = _entry(_manifest(pack_with_budget), BUDGET_RELPATH)
        assert (pack_with_budget / BUDGET_RELPATH).stat().st_size == entry["bytes"]

    def test_g5_the_published_artifact_is_the_session_budget(
        self, pack_with_budget, golden_session, budget
    ):
        published = json.loads(
            (pack_with_budget / BUDGET_RELPATH).read_text(encoding="utf-8")
        )
        assert published == budget.as_dict()
        assert AcquisitionBudgetV1.from_dict(published).as_dict() == budget.as_dict()

    def test_g5_the_bytes_are_the_sessions_bytes_unaltered(
        self, pack_with_budget, golden_session
    ):
        """No second serialization anywhere on the path."""
        assert (pack_with_budget / BUDGET_RELPATH).read_bytes() == (
            golden_session / BUDGET_RELPATH
        ).read_bytes()

    def test_the_published_budget_still_carries_its_provenance(
        self, pack_with_budget, budget
    ):
        published = AcquisitionBudgetV1.from_dict(
            json.loads((pack_with_budget / BUDGET_RELPATH).read_text(encoding="utf-8"))
        )
        assert (
            published.converter.hp_corner_hz.source
            == budget.converter.hp_corner_hz.source
        )
        assert published.evidence().evidence_grade is False

    def test_the_pack_validates(self, pack_with_budget):
        report = validate_pack(pack_with_budget)
        assert report.passed, report.errors
        assert report.stats["acquisition_budget_present"] == 1
        assert report.stats["acquisition_budget_valid"] == 1


class TestHistoricalPacks:
    def test_g6_a_pack_without_a_budget_remains_valid(
        self, tmp_path_factory, golden_session
    ):
        """The shape of every pack exported before DO-107B."""
        if not GOLDEN.is_dir():
            pytest.skip("golden session not present")
        session = tmp_path_factory.mktemp("session_no_budget") / GOLDEN.name
        shutil.copytree(GOLDEN, session)
        assert load_acquisition_budget(session) is None

        pack = _export(session, tmp_path_factory.mktemp("pack_no_budget"))
        assert not (pack / BUDGET_RELPATH).exists()
        assert _entry(_manifest(pack), BUDGET_RELPATH) is None

        report = validate_pack(pack)
        assert report.passed, report.errors
        assert report.stats["acquisition_budget_present"] == 0


class TestTamperDetection:
    """§26 G7. An altered budget must not pass as the budget that was computed."""

    def _tampered_pack(self, tmp_path_factory, budget, mutate) -> Path:
        session = tmp_path_factory.mktemp("session_tampered") / GOLDEN.name
        shutil.copytree(GOLDEN, session)
        attach_acquisition_budget(session, budget, replace=True)
        pack = _export(session, tmp_path_factory.mktemp("pack_tampered"))
        payload = json.loads((pack / BUDGET_RELPATH).read_text(encoding="utf-8"))
        mutate(payload)
        (pack / BUDGET_RELPATH).write_text(json.dumps(payload, indent=2), "utf-8")
        return pack

    def test_g7_a_budget_claiming_evidence_grade_it_cannot_have_is_caught(
        self, tmp_path_factory, budget
    ):
        if not GOLDEN.is_dir():
            pytest.skip("golden session not present")

        def promote(payload):
            payload["evidence"]["evidence_grade"] = True

        pack = self._tampered_pack(tmp_path_factory, budget, promote)
        report = validate_pack(pack)
        assert not report.passed
        assert any(e["rule"] == "ACQ-002" for e in report.errors), report.errors

    def test_g7_a_budget_whose_combination_was_edited_is_caught(
        self, tmp_path_factory, budget
    ):
        if not GOLDEN.is_dir():
            pytest.skip("golden session not present")

        def shrink(payload):
            payload["results"]["frequency"]["combined_hz"] = 0.001

        pack = self._tampered_pack(tmp_path_factory, budget, shrink)
        report = validate_pack(pack)
        assert not report.passed
        assert any(e["rule"] == "ACQ-002" for e in report.errors), report.errors

    def test_g7_a_document_that_is_not_a_budget_is_caught(
        self, tmp_path_factory, budget
    ):
        if not GOLDEN.is_dir():
            pytest.skip("golden session not present")

        def foreign(payload):
            payload["schema_version"] = "something_else_v1"

        pack = self._tampered_pack(tmp_path_factory, budget, foreign)
        report = validate_pack(pack)
        assert not report.passed
        assert any(e["rule"].startswith("ACQ-") for e in report.errors), report.errors

    def test_g7_tampering_also_breaks_the_manifest_digest(
        self, tmp_path_factory, budget
    ):
        """The digest is the second, independent check on the same bytes."""
        if not GOLDEN.is_dir():
            pytest.skip("golden session not present")

        def promote(payload):
            payload["evidence"]["evidence_grade"] = True

        pack = self._tampered_pack(tmp_path_factory, budget, promote)
        entry = _entry(_manifest(pack), BUDGET_RELPATH)
        actual = hashlib.sha256((pack / BUDGET_RELPATH).read_bytes()).hexdigest()
        assert actual != entry["sha256"]
