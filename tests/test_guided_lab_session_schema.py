"""The persisted session envelope matches its published contract (DO-100).

Real sessions produced by the engine are validated against
``contracts/guided_lab_session_v1.schema.json``, so the schema cannot drift
away from what the code actually writes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

from tap_tone_pi.guided_lab.engine import (  # noqa: E402
    abandon_session,
    acknowledge_instruction,
    advance_session,
    answer_question,
    attach_evidence,
    complete_session,
    get_current_node,
    pause_session,
    start_session,
)
from tap_tone_pi.guided_lab.models import (  # noqa: E402
    CompleteNodeV1,
    EvidenceRequirementNodeV1,
    InstructionNodeV1,
    QuestionNodeV1,
    WorkflowEvidenceReferenceV1,
)
from tap_tone_pi.guided_lab.workflows import PLATE_MEASUREMENT_SETUP_V1  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "guided_lab_session_v1.schema.json"
REGISTRY_PATH = REPO_ROOT / "contracts" / "schema_registry.json"

T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)

ANSWERS = {
    "q_specimen_id": "TOP-2026-014",
    "q_specimen_type": "top",
    "q_specimen_other_label": "Offcut",
    "q_preparation_state": "joined",
    "q_material_label": "Sitka spruce",
    "q_purpose": "compare_after_removal",
    "q_entry_mode": "capture_new",
    "q_ready_dimensions": True,
    "q_ready_mass": True,
    "q_ready_device": True,
    "q_ready_support": True,
    "q_ready_environment": False,
    "q_environment_skip_reason": "No hygrometer this week.",
}

EVIDENCE_IDS = {
    "specimen_record": "ev-specimen-014",
    "measurement_session": "ev-session-014",
    "baseline_measurement": "ev-baseline-013",
}


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema):
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def walk_full_session():
    definition = PLATE_MEASUREMENT_SETUP_V1
    session = start_session(definition, session_id="s-schema", started_at=T0)
    tick = 0
    for _ in range(64):
        tick += 1
        stamp = T0 + timedelta(minutes=tick)
        node = get_current_node(definition, session)
        if isinstance(node, CompleteNodeV1):
            return definition, session
        if isinstance(node, QuestionNodeV1):
            session = answer_question(
                definition, session, ANSWERS[node.node_id], answered_at=stamp
            )
        elif isinstance(node, InstructionNodeV1):
            session = acknowledge_instruction(
                definition, session, acknowledged_at=stamp
            )
        elif isinstance(node, EvidenceRequirementNodeV1):
            kind = node.required_evidence_kinds[0]
            session = attach_evidence(
                definition,
                session,
                WorkflowEvidenceReferenceV1(
                    evidence_id=EVIDENCE_IDS[kind],
                    evidence_kind=kind,
                    source_system="tap_tone_pi",
                    digest="a" * 64,
                    label="Top plate",
                ),
                attached_at=stamp,
            )
        session = advance_session(definition, session, advanced_at=stamp)
    raise AssertionError("workflow did not terminate")


class TestSchemaDocument:
    def test_schema_file_exists(self):
        assert SCHEMA_PATH.is_file()

    def test_schema_is_draft_2020_12(self, schema):
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_schema_is_itself_well_formed(self, schema):
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_schema_version_is_pinned(self, schema):
        assert schema["properties"]["schema_version"]["const"] == (
            "guided_lab_session_v1"
        )

    def test_unknown_top_level_properties_are_rejected(self, schema):
        assert schema["additionalProperties"] is False

    def test_workflow_version_is_a_positive_integer(self, schema):
        prop = schema["properties"]["workflow_version"]
        assert prop["type"] == "integer"
        assert prop["minimum"] == 1

    def test_status_is_closed_to_four_values(self, schema):
        assert set(schema["properties"]["status"]["enum"]) == {
            "active",
            "paused",
            "completed",
            "abandoned",
        }

    def test_timestamps_are_date_time_strings(self, schema):
        for field in ("started_at", "updated_at", "completed_at"):
            prop = schema["properties"][field]
            assert prop["type"] == "string"
            assert prop["format"] == "date-time"

    def test_answer_revision_starts_at_one(self, schema):
        revision = schema["$defs"]["WorkflowAnswer"]["properties"]["revision"]
        assert revision["type"] == "integer"
        assert revision["minimum"] == 1

    def test_evidence_reference_declares_no_path_property(self, schema):
        evidence = schema["$defs"]["WorkflowEvidenceReference"]
        assert evidence["additionalProperties"] is False
        for forbidden in ("path", "file_path", "uri", "url", "location"):
            assert forbidden not in evidence["properties"]

    def test_answer_value_excludes_containers_and_null(self, schema):
        allowed = set(schema["$defs"]["AnswerValue"]["type"])
        assert allowed == {"string", "boolean", "integer", "number"}
        assert "array" not in allowed
        assert "object" not in allowed
        assert "null" not in allowed


class TestRegistryEntry:
    @pytest.fixture(scope="class")
    def registry(self) -> dict:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_registry_is_still_valid_json(self, registry):
        assert registry["title"] == "tap_tone_pi Schema Registry"

    def test_schema_is_registered(self, registry):
        assert "guided_lab_session" in registry["schemas"]

    def test_entry_uses_the_existing_structure(self, registry):
        entry = registry["schemas"]["guided_lab_session"]
        assert set(entry) == {
            "description",
            "file",
            "owner",
            "path",
            "schema_version_const",
            "status",
            "version",
        }
        assert entry["schema_version_const"] == "guided_lab_session_v1"
        assert entry["path"] == "contracts/guided_lab_session_v1.schema.json"

    def test_registered_path_exists(self, registry):
        entry = registry["schemas"]["guided_lab_session"]
        assert (REPO_ROOT / entry["path"]).is_file()

    def test_owner_is_declared(self, registry):
        entry = registry["schemas"]["guided_lab_session"]
        owner = registry["owners"][entry["owner"]]
        assert "guided_lab_session" in owner["schemas"]


class TestRealSessionsValidate:
    def test_new_session_validates(self, validator):
        session = start_session(
            PLATE_MEASUREMENT_SETUP_V1, session_id="s-new", started_at=T0
        )
        validator.validate(session.to_dict())

    def test_paused_session_validates(self, validator):
        session = start_session(
            PLATE_MEASUREMENT_SETUP_V1, session_id="s-paused", started_at=T0
        )
        session = pause_session(PLATE_MEASUREMENT_SETUP_V1, session, paused_at=T0)
        validator.validate(session.to_dict())

    def test_abandoned_session_validates(self, validator):
        session = start_session(
            PLATE_MEASUREMENT_SETUP_V1, session_id="s-gone", started_at=T0
        )
        session = abandon_session(PLATE_MEASUREMENT_SETUP_V1, session, abandoned_at=T0)
        validator.validate(session.to_dict())

    def test_completed_session_validates(self, validator):
        definition, session = walk_full_session()
        session = complete_session(definition, session, completed_at=T0)
        payload = session.to_dict()
        validator.validate(payload)
        assert payload["status"] == "completed"
        assert payload["completed_at"]
        assert len(payload["evidence_references"]) == 3

    def test_engine_stamped_evidence_validates(self, validator):
        """The stamp the engine writes has to be a shape the contract allows."""
        definition, session = walk_full_session()
        payload = session.to_dict()
        validator.validate(payload)
        stamped = {
            reference["attached_node_id"]
            for reference in payload["evidence_references"]
        }
        assert stamped == {
            "e_specimen_record",
            "e_measurement_reference",
            "e_baseline_reference",
        }

    def test_session_with_a_revised_answer_validates(self, validator):
        from tap_tone_pi.guided_lab.engine import replace_answer

        definition, session = walk_full_session()
        session = replace_answer(
            definition,
            session,
            node_id="q_specimen_type",
            value="back",
            answered_at=T0,
        )
        payload = session.to_dict()
        validator.validate(payload)
        revisions = {a["node_id"]: a["revision"] for a in payload["answers"]}
        assert revisions["q_specimen_type"] == 2


class TestSchemaRejectsBadRecords:
    def _valid(self) -> dict:
        return start_session(
            PLATE_MEASUREMENT_SETUP_V1, session_id="s-bad", started_at=T0
        ).to_dict()

    def test_unknown_top_level_field_is_rejected(self, validator):
        payload = self._valid()
        payload["operator_notes"] = "extra"
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)

    def test_wrong_schema_version_is_rejected(self, validator):
        payload = self._valid()
        payload["schema_version"] = "guided_lab_session_v2"
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)

    def test_zero_workflow_version_is_rejected(self, validator):
        payload = self._valid()
        payload["workflow_version"] = 0
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)

    def test_unknown_status_is_rejected(self, validator):
        payload = self._valid()
        payload["status"] = "archived"
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)

    def test_zero_revision_is_rejected(self, validator):
        payload = self._valid()
        payload["answers"] = [
            {
                "node_id": "q_specimen_id",
                "answer_kind": "text",
                "value": "x",
                "answered_at": "2026-07-29T12:00:00Z",
                "revision": 0,
            }
        ]
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)

    def test_evidence_with_a_path_property_is_rejected(self, validator):
        payload = self._valid()
        payload["evidence_references"] = [
            {
                "evidence_id": "ev-1",
                "evidence_kind": "specimen_record",
                "source_system": "tap_tone_pi",
                "path": "C:/runs/session.json",
            }
        ]
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)

    def test_array_answer_value_is_rejected(self, validator):
        payload = self._valid()
        payload["answers"] = [
            {
                "node_id": "q_specimen_id",
                "answer_kind": "text",
                "value": ["a", "b"],
                "answered_at": "2026-07-29T12:00:00Z",
                "revision": 1,
            }
        ]
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)

    def test_missing_required_field_is_rejected(self, validator):
        payload = self._valid()
        del payload["current_node_id"]
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
