"""The acquisition budget attached to a Phase 2 session (DO-107B §25).

Two things are being protected. **The bytes**: what comes back out of a session
is what was computed, to the last float, or the budget is a rendering of a
result rather than the result. And **every session recorded before this
existed**: a session with no budget is a normal session, loads unchanged, and
acquires no defect from the absence.

The third line is quieter. Attaching a budget writes a document *about* a
session; it captures nothing. Every session built here is synthetic, and stays
synthetic with a budget attached — only hardware execution produces the genuine
acquisition milestone, and no fixture may stand in for it.
"""

from __future__ import annotations

import json

import pytest

from tap_tone_pi.phase2.session_acquisition import (
    ACQUISITION_BUDGET_FILENAME,
    SessionAcquisitionError,
    attach_acquisition_budget,
    find_acquisition_budget,
    has_acquisition_budget,
    load_acquisition_budget,
)
from tap_tone_pi.uncertainty.acquisition import (
    AcquisitionBudgetV1,
    Provenance,
    validate_acquisition_budget,
)

from tests.test_e0_acquisition_adapter import (
    POINT,
    base_budget,
    executed,
)
from tap_tone_pi.uncertainty.acquisition import build_acquisition_budget_from_e0


def synthetic_session(tmp_path, name="session_20260901T120000Z"):
    """A Phase 2 session in the shape ``scripts/phase2_slice.py`` writes.

    ``synthetic: true`` throughout, and deliberately so: DO-107B may not
    manufacture the first genuine acquisition, and a fixture that claimed
    ``synthetic: false`` would be doing exactly that.
    """
    session = tmp_path / name
    (session / "points" / "point_A1").mkdir(parents=True)
    (session / "derived").mkdir()
    (session / "metadata.json").write_text(
        json.dumps(
            {
                "session_id": name,
                "created_at_utc": "2026-09-01T12:00:00Z",
                "phase": 2,
                "mode": "roving_grid_vertical_slice",
                "capture": {
                    "synthetic": True,
                    "sample_rate_hz": 48000,
                    "seconds": 4.0,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (session / "points" / "point_A1" / "capture_meta.json").write_text(
        json.dumps({"point_id": "A1", "synthetic": True, "sample_rate_hz": 48000}),
        encoding="utf-8",
    )
    return session


@pytest.fixture
def budget():
    return build_acquisition_budget_from_e0(base_budget(), executed(), POINT).budget


class TestAttachment:
    def test_f1_a_session_carries_one_canonical_budget(self, tmp_path, budget):
        session = synthetic_session(tmp_path)
        assert has_acquisition_budget(session) is False

        path = attach_acquisition_budget(session, budget)
        assert path.name == ACQUISITION_BUDGET_FILENAME
        assert path.parent.name == "meta"
        assert has_acquisition_budget(session) is True

    def test_f1_a_second_budget_is_refused_unless_superseding_is_stated(
        self, tmp_path, budget
    ):
        session = synthetic_session(tmp_path)
        attach_acquisition_budget(session, budget)
        with pytest.raises(SessionAcquisitionError, match="already carries"):
            attach_acquisition_budget(session, budget)

        # Stated outright, it is permitted, and one document remains.
        attach_acquisition_budget(session, budget, replace=True)
        assert len(list((session / "meta").glob("acquisition_budget*.json"))) == 1

    def test_a_budget_cannot_attach_to_a_session_that_does_not_exist(
        self, tmp_path, budget
    ):
        with pytest.raises(SessionAcquisitionError, match="does not exist"):
            attach_acquisition_budget(tmp_path / "no_such_session", budget)

    def test_a_budget_that_fails_its_own_contract_is_not_filed(self, tmp_path):
        session = synthetic_session(tmp_path)
        # An evidence grade that disagrees with its own reasons: the exact state
        # the contract exists to catch, constructed rather than computed.
        broken = base_budget().computed()

        class Lying:
            def as_dict(self):
                payload = broken.as_dict()
                payload["evidence"]["evidence_grade"] = True
                return payload

        with pytest.raises(SessionAcquisitionError, match="contract"):
            attach_acquisition_budget(session, Lying())
        assert has_acquisition_budget(session) is False


class TestLosslessRoundTrip:
    def test_f2_the_budget_survives_the_session_losslessly(self, tmp_path, budget):
        session = synthetic_session(tmp_path)
        attach_acquisition_budget(session, budget)
        restored = load_acquisition_budget(session)
        assert restored.as_dict() == budget.as_dict()

    def test_f2_provenance_and_source_survive_the_file(self, tmp_path, budget):
        session = synthetic_session(tmp_path)
        attach_acquisition_budget(session, budget)
        restored = load_acquisition_budget(session)
        corner = restored.converter.hp_corner_hz
        assert corner.provenance is Provenance.MEASURED
        assert corner.source == budget.converter.hp_corner_hz.source
        assert corner.value == budget.converter.hp_corner_hz.value

    def test_f2_the_stored_bytes_are_the_canonical_payload(self, tmp_path, budget):
        session = synthetic_session(tmp_path)
        path = attach_acquisition_budget(session, budget)
        stored = json.loads(path.read_text(encoding="utf-8"))
        assert stored == budget.as_dict()
        assert validate_acquisition_budget(stored) == []

    def test_f3_the_session_does_not_reinterpret_the_evidence_grade(
        self, tmp_path, budget
    ):
        session = synthetic_session(tmp_path)
        attach_acquisition_budget(session, budget)
        restored = load_acquisition_budget(session)
        assert restored.evidence().as_dict() == budget.evidence().as_dict()
        assert restored.evidence().evidence_grade is False
        # And the session itself asserts nothing about it.
        metadata = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
        assert "evidence" not in json.dumps(metadata)

    def test_attaching_a_budget_captures_nothing(self, tmp_path, budget):
        """A fixture session with a budget attached is still a fixture session."""
        session = synthetic_session(tmp_path)
        before = (session / "metadata.json").read_bytes()
        attach_acquisition_budget(session, budget)
        assert (session / "metadata.json").read_bytes() == before
        metadata = json.loads(before)
        assert metadata["capture"]["synthetic"] is True


class TestBackwardCompatibility:
    def test_f4_a_session_without_a_budget_is_legal_and_silent(self, tmp_path):
        session = synthetic_session(tmp_path)
        assert load_acquisition_budget(session) is None
        assert find_acquisition_budget(session) is None

    def test_f5_a_historical_session_loads_unchanged(self, tmp_path):
        """Sessions written before DO-107B keep working, byte for byte."""
        session = synthetic_session(tmp_path)
        before = sorted(
            (p.relative_to(session).as_posix(), p.read_bytes())
            for p in session.rglob("*")
            if p.is_file()
        )
        assert load_acquisition_budget(session) is None
        after = sorted(
            (p.relative_to(session).as_posix(), p.read_bytes())
            for p in session.rglob("*")
            if p.is_file()
        )
        assert after == before

    def test_a_present_but_unreadable_budget_does_not_read_as_absent(self, tmp_path):
        session = synthetic_session(tmp_path)
        path = session / "meta" / ACQUISITION_BUDGET_FILENAME
        path.parent.mkdir(parents=True)
        path.write_text("{ not json", encoding="utf-8")
        assert has_acquisition_budget(session) is True
        with pytest.raises(SessionAcquisitionError, match="readable JSON"):
            load_acquisition_budget(session)

    def test_a_foreign_document_in_the_budget_slot_is_refused(self, tmp_path):
        session = synthetic_session(tmp_path)
        path = session / "meta" / ACQUISITION_BUDGET_FILENAME
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": "something_else"}), "utf-8")
        with pytest.raises(SessionAcquisitionError, match="acquisition_budget_v1"):
            load_acquisition_budget(session)

    def test_a_hand_placed_budget_beside_the_session_is_found(self, tmp_path, budget):
        session = synthetic_session(tmp_path)
        (session / ACQUISITION_BUDGET_FILENAME).write_text(
            json.dumps(budget.as_dict()), encoding="utf-8"
        )
        loaded = load_acquisition_budget(session)
        assert isinstance(loaded, AcquisitionBudgetV1)
        # Attaching canonically leaves exactly one document, not two that can
        # disagree.
        attach_acquisition_budget(session, budget, replace=True)
        assert not (session / ACQUISITION_BUDGET_FILENAME).exists()
        assert (session / "meta" / ACQUISITION_BUDGET_FILENAME).is_file()
