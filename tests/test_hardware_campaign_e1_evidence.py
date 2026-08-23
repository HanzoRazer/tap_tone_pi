"""E1 evidence hardening: rig masses, reference structure, acquisition order.

DO-104 puts a physical rig under the stinger for the first time, and three
things it will record had nowhere to live: the measured mass of what the drive
point has to move, the identity of the body being driven, and the order the
captures were taken in.

None of them is E1-specific — every hardware campaign wants them — and none is
recoverable after the fact. A mass recorded as prose cannot be validated or
compared; an acquisition order reconstructed later by sorting timestamps is a
guess. They land before the rig exists for the same reason the Phase 2 ingestion
path did: so the first physical campaign does not immediately discard
information the software already knows it needs.

Nothing here grades anything. A mass is checked for being a mass and a sequence
for being able to order runs; no value is compared against a limit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness import (
    EvidenceOrigin,
    ExcitationContextV1,
    ObservedFeatureV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    RepeatabilityStudyV1,
)
from tap_tone_pi.grant_readiness.contracts import (
    EVALUATION_FREQUENCY,
    FREQUENCY_OFFSET,
    FREQUENCY_OFFSET_EPSILON_HZ,
    NOMINAL_EVALUATION_FREQUENCY,
)
from tap_tone_pi.grant_readiness.errors import ExperimentRecordError
from tap_tone_pi.grant_readiness.hardware_campaign import (
    build_rig_excitation_context,
    elapsed_seconds_from_first,
)
from tap_tone_pi.grant_readiness.report import render_study_report
from tap_tone_pi.grant_readiness.validation import (
    validate_contact_assembly_masses,
    validate_experiment_definition,
    validate_experiment_runs,
    validate_run_sequence,
)

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC_NOW = "2026-08-23T12:00:00+00:00"


def codes(findings) -> list[str]:
    return [finding.code.value for finding in findings]


def make_run(
    run_id: str,
    *,
    sequence_index: int | None = None,
    captured_at: str = UTC_NOW,
    valid: bool = True,
) -> PreliminaryExperimentRunV1:
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="e1-rig",
        captured_at=captured_at,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=valid,
        source_artifact_ids=(f"fixtures/{run_id}.json",),
        observed_features=(
            ObservedFeatureV1("acoustic_transfer_magnitude", "Pa/N", 1.0),
        ),
        sequence_index=sequence_index,
    )


def at(minute: int) -> str:
    return f"2026-08-23T12:{minute:02d}:00+00:00"


class TestContactAssemblyMasses:
    def test_the_three_masses_round_trip(self):
        excitation = build_rig_excitation_context(
            rig_configuration_id="rig-1",
            stinger_id="stinger-1",
            contact_tip_id="tip-1",
        )
        weighed = ExcitationContextV1(
            **{
                **excitation.to_dict(),
                "stinger_mass_g": 1.42,
                "contact_tip_mass_g": 0.31,
                "combined_contact_mass_g": 1.80,
            }
        )
        assert ExcitationContextV1.from_dict(weighed.to_dict()) == weighed

    def test_an_unweighed_rig_records_nothing_rather_than_zero(self):
        # Unknown is not zero. A rig nobody has weighed must not read as
        # weightless.
        excitation = build_rig_excitation_context(rig_configuration_id="rig-1")
        assert excitation.contact_assembly_masses_g == {
            "stinger_mass_g": None,
            "contact_tip_mass_g": None,
            "combined_contact_mass_g": None,
        }

    def test_a_weighed_rig_validates(self):
        excitation = ExcitationContextV1(
            stinger_mass_g=1.42, contact_tip_mass_g=0.31, combined_contact_mass_g=1.80
        )
        assert validate_contact_assembly_masses(excitation, record="rig") == []

    def test_a_zero_mass_is_permitted(self):
        # A tip too light for the scale is a legitimate reading of zero.
        excitation = ExcitationContextV1(contact_tip_mass_g=0.0)
        assert validate_contact_assembly_masses(excitation, record="rig") == []

    @pytest.mark.parametrize(
        "field",
        ["stinger_mass_g", "contact_tip_mass_g", "combined_contact_mass_g"],
    )
    def test_a_negative_mass_is_refused(self, field):
        excitation = ExcitationContextV1(**{field: -0.5})
        assert codes(validate_contact_assembly_masses(excitation, record="rig")) == [
            "NSF-511"
        ]

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_a_non_finite_mass_is_refused_on_read(self, bad):
        payload = ExcitationContextV1().to_dict()
        payload["stinger_mass_g"] = bad
        with pytest.raises(ExperimentRecordError):
            ExcitationContextV1.from_dict(payload)

    def test_the_combined_mass_is_not_checked_against_the_parts(self):
        # What moves with the specimen is not always the whole stinger, so a
        # combined mass below the sum is a real measurement, not an error.
        excitation = ExcitationContextV1(
            stinger_mass_g=1.42, contact_tip_mass_g=0.31, combined_contact_mass_g=0.90
        )
        assert validate_contact_assembly_masses(excitation, record="rig") == []

    def test_definition_validation_carries_the_check(self):
        definition = PreliminaryExperimentDefinitionV1(
            experiment_id="e1-rig",
            instrument_id="rig-1",
            measurement_point_id="D1",
            operator_id="op-1",
            planned_repeat_count=5,
            created_at=UTC_NOW,
            excitation=ExcitationContextV1(stinger_mass_g=-1.0),
        )
        assert "NSF-511" in codes(validate_experiment_definition(definition))


class TestReferenceStructure:
    def make_definition(self, **overrides) -> PreliminaryExperimentDefinitionV1:
        kwargs = {
            "experiment_id": "e1-rig",
            "instrument_id": "rig-1",
            "measurement_point_id": "D1",
            "operator_id": "op-1",
            "planned_repeat_count": 5,
            "created_at": UTC_NOW,
        }
        kwargs.update(overrides)
        return PreliminaryExperimentDefinitionV1(**kwargs)

    def test_round_trip(self):
        definition = self.make_definition(reference_structure_id="ref-plate-1")
        assert PreliminaryExperimentDefinitionV1.from_dict(definition.to_dict()) == (
            definition
        )

    def test_a_do102_definition_still_round_trips_without_one(self):
        definition = self.make_definition()
        payload = definition.to_dict()
        assert payload["reference_structure_id"] is None
        assert PreliminaryExperimentDefinitionV1.from_dict(payload) == definition

    def test_the_rig_and_the_body_it_drives_are_named_separately(self):
        # E1 records the rig in instrument_id, so without this field the body
        # under the stinger would have nowhere to be named at all.
        definition = self.make_definition(
            instrument_id="rig-1", reference_structure_id="ref-plate-1"
        )
        assert definition.instrument_id == "rig-1"
        assert definition.reference_structure_id == "ref-plate-1"

    def test_it_is_optional_and_validates_when_absent(self):
        assert validate_experiment_definition(self.make_definition()) == []


class TestAcquisitionOrder:
    def test_round_trip(self):
        run = make_run("r1", sequence_index=3)
        assert PreliminaryExperimentRunV1.from_dict(run.to_dict()) == run

    def test_a_run_without_an_index_round_trips(self):
        run = make_run("r1")
        assert run.to_dict()["sequence_index"] is None
        assert PreliminaryExperimentRunV1.from_dict(run.to_dict()) == run

    @pytest.mark.parametrize("bad", [-1, 1.5, "2", True])
    def test_an_index_that_cannot_order_is_refused(self, bad):
        payload = make_run("r1").to_dict()
        payload["sequence_index"] = bad
        with pytest.raises(ExperimentRecordError) as excinfo:
            PreliminaryExperimentRunV1.from_dict(payload)
        assert excinfo.value.code.value == "NSF-512"

    def test_zero_is_a_valid_first_index(self):
        payload = make_run("r1").to_dict()
        payload["sequence_index"] = 0
        assert PreliminaryExperimentRunV1.from_dict(payload).sequence_index == 0

    def test_a_well_ordered_sequence_validates(self):
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(0)),
            make_run("r2", sequence_index=1, captured_at=at(1)),
            make_run("r3", sequence_index=2, captured_at=at(2)),
        ]
        assert validate_run_sequence(runs) == []

    def test_a_repeated_index_is_refused(self):
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(0)),
            make_run("r2", sequence_index=0, captured_at=at(1)),
        ]
        findings = validate_run_sequence(runs)
        assert codes(findings) == ["NSF-512"]
        assert findings[0].context["run_ids"] == ["r1", "r2"]

    def test_an_index_that_contradicts_the_clock_is_reported(self):
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(5)),
            make_run("r2", sequence_index=1, captured_at=at(1)),
        ]
        assert codes(validate_run_sequence(runs)) == ["NSF-512"]

    def test_the_conflict_is_reported_not_resolved(self):
        # Picking a winner would invent a fact about the acquisition. The runs
        # keep exactly what they recorded.
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(5)),
            make_run("r2", sequence_index=1, captured_at=at(1)),
        ]
        validate_run_sequence(runs)
        assert runs[0].sequence_index == 0 and runs[0].captured_at == at(5)
        assert runs[1].sequence_index == 1 and runs[1].captured_at == at(1)

    def test_identical_timestamps_are_not_a_conflict(self):
        # Two captures inside one clock tick order fine by index.
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(0)),
            make_run("r2", sequence_index=1, captured_at=at(0)),
        ]
        assert validate_run_sequence(runs) == []

    def test_rejected_runs_keep_their_place_in_the_order(self):
        # A failed attempt still happened, and it happened somewhere.
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(0)),
            make_run("r2", sequence_index=1, captured_at=at(1), valid=False),
            make_run("r3", sequence_index=2, captured_at=at(2)),
        ]
        assert validate_run_sequence(runs) == []

    def test_runs_without_an_index_are_not_judged(self):
        runs = [make_run("r1"), make_run("r2")]
        assert validate_run_sequence(runs) == []

    def test_run_collection_validation_carries_the_check(self):
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(0)),
            make_run("r2", sequence_index=0, captured_at=at(1)),
        ]
        assert "NSF-512" in codes(validate_experiment_runs(runs))


class TestFrequencyOffsetIsVerifiedOnRead:
    """A derived value that can contradict its sources is worse than none.

    The offset reads as corroboration — it says how far the answering bin fell
    from the request — so a document whose offset disagrees with its own two
    frequencies would mislead precisely where a reader is looking for
    reassurance. The check is at deserialization because a document can be
    hand-edited, partially merged, or written by another tool and reach the
    records without passing through ingestion at all.
    """

    def make_run(self, actual=100.4, nominal=100.0, offset=None, drop=()):
        features = []
        if EVALUATION_FREQUENCY not in drop:
            features.append(ObservedFeatureV1(EVALUATION_FREQUENCY, "Hz", actual))
        if NOMINAL_EVALUATION_FREQUENCY not in drop:
            features.append(
                ObservedFeatureV1(NOMINAL_EVALUATION_FREQUENCY, "Hz", nominal)
            )
        if FREQUENCY_OFFSET not in drop:
            features.append(
                ObservedFeatureV1(
                    FREQUENCY_OFFSET,
                    "Hz",
                    actual - nominal if offset is None else offset,
                )
            )
        return PreliminaryExperimentRunV1(
            run_id="r1",
            experiment_id="e1-rig",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            source_artifact_ids=("fixtures/r1.json",),
            observed_features=tuple(features),
        )

    def test_an_honest_offset_round_trips(self):
        run = self.make_run()
        assert PreliminaryExperimentRunV1.from_dict(run.to_dict()) == run

    def test_a_tampered_offset_is_refused(self):
        payload = self.make_run().to_dict()
        payload["observed_features"][2]["value"] = 7.0
        with pytest.raises(ExperimentRecordError) as excinfo:
            PreliminaryExperimentRunV1.from_dict(payload)
        assert excinfo.value.code.value == "NSF-513"

    @pytest.mark.parametrize("sign", [1, -1])
    def test_an_offset_of_the_wrong_sign_is_refused(self, sign):
        # Which side of the request the bin fell on is the information the
        # offset carries, so a flipped sign is a contradiction, not a detail.
        payload = self.make_run(actual=100.0 + sign * 0.4).to_dict()
        payload["observed_features"][2]["value"] = -sign * 0.4
        with pytest.raises(ExperimentRecordError):
            PreliminaryExperimentRunV1.from_dict(payload)

    def test_float_slack_is_allowed(self):
        # 100.4 - 100.0 is not exactly 0.4 in binary floating point. The check
        # must not reject a document for being written in decimal.
        payload = self.make_run().to_dict()
        payload["observed_features"][2]["value"] = 0.4
        assert PreliminaryExperimentRunV1.from_dict(payload) is not None

    def test_slack_beyond_the_declared_epsilon_is_refused(self):
        payload = self.make_run().to_dict()
        payload["observed_features"][2]["value"] = (
            payload["observed_features"][2]["value"] + FREQUENCY_OFFSET_EPSILON_HZ * 100
        )
        with pytest.raises(ExperimentRecordError):
            PreliminaryExperimentRunV1.from_dict(payload)

    @pytest.mark.parametrize(
        "missing", [EVALUATION_FREQUENCY, NOMINAL_EVALUATION_FREQUENCY]
    )
    def test_an_offset_without_its_sources_is_refused(self, missing):
        # Unknown is not zero. An offset standing alone would claim the bin
        # answered exactly what was asked, which nothing here observed.
        payload = self.make_run().to_dict()
        payload["observed_features"] = [
            f for f in payload["observed_features"] if f["quantity"] != missing
        ]
        with pytest.raises(ExperimentRecordError) as excinfo:
            PreliminaryExperimentRunV1.from_dict(payload)
        assert excinfo.value.code.value == "NSF-513"

    def test_unknown_frequencies_with_no_offset_are_fine(self):
        # The offset stays unknown rather than silently becoming zero.
        run = self.make_run(drop=(FREQUENCY_OFFSET,))
        assert PreliminaryExperimentRunV1.from_dict(run.to_dict()) == run

    def test_a_zero_offset_is_a_real_observation(self):
        run = self.make_run(actual=200.0, nominal=200.0)
        restored = PreliminaryExperimentRunV1.from_dict(run.to_dict())
        assert restored.feature(FREQUENCY_OFFSET).value == 0.0

    def test_a_phase1_run_is_not_judged(self):
        run = PreliminaryExperimentRunV1(
            run_id="r1",
            experiment_id="phase1",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            source_artifact_ids=("fixtures/tap.json",),
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 245.0),),
        )
        assert PreliminaryExperimentRunV1.from_dict(run.to_dict()) == run


class TestElapsedIsDerived:
    def test_elapsed_runs_from_the_earliest_capture(self):
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(0)),
            make_run("r2", sequence_index=1, captured_at=at(2)),
        ]
        assert elapsed_seconds_from_first(runs) == {"r1": 0.0, "r2": 120.0}

    def test_a_run_before_the_first_index_reports_negative_rather_than_reordering(
        self,
    ):
        # The disagreement belongs to the validator, not to arithmetic.
        runs = [
            make_run("r1", sequence_index=0, captured_at=at(5)),
            make_run("r2", sequence_index=1, captured_at=at(1)),
        ]
        elapsed = elapsed_seconds_from_first(runs)
        assert elapsed["r2"] == 0.0
        assert elapsed["r1"] == 240.0

    def test_no_runs_yields_no_elapsed(self):
        assert elapsed_seconds_from_first([]) == {}

    def test_elapsed_is_not_stored_on_the_run(self):
        # Derived from a collection, so a stored copy could disagree with the
        # timestamps it was taken over.
        assert "elapsed" not in make_run("r1", sequence_index=0).to_dict()


class TestSequenceReporting:
    def make_study(self, runs) -> RepeatabilityStudyV1:
        return RepeatabilityStudyV1(
            study_id="study-e1",
            experiment_definition=PreliminaryExperimentDefinitionV1(
                experiment_id="e1-rig",
                instrument_id="rig-1",
                measurement_point_id="D1",
                operator_id="op-1",
                planned_repeat_count=2,
                created_at=UTC_NOW,
                reference_structure_id="ref-plate-1",
            ),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            runs=tuple(runs),
        )

    def test_the_sequence_section_appears_when_the_order_was_recorded(self):
        study = self.make_study(
            [
                make_run("r1", sequence_index=0, captured_at=at(0)),
                make_run("r2", sequence_index=1, captured_at=at(2)),
            ]
        )
        markdown = render_study_report(study)
        assert "## Acquisition sequence" in markdown
        assert "| 0 | `r1` | yes |" in markdown
        assert "120" in markdown

    def test_a_study_without_an_order_renders_exactly_as_before(self):
        study = self.make_study([make_run("r1"), make_run("r2")])
        assert "## Acquisition sequence" not in render_study_report(study)

    def test_the_section_says_the_order_was_recorded_not_inferred(self):
        study = self.make_study([make_run("r1", sequence_index=0)])
        markdown = render_study_report(study)
        assert "not reconstructed from timestamps" in markdown

    def test_the_section_carries_no_drift_verdict(self):
        study = self.make_study(
            [
                make_run("r1", sequence_index=0, captured_at=at(0)),
                make_run("r2", sequence_index=1, captured_at=at(2)),
            ]
        )
        markdown = render_study_report(study).lower()
        for marker in ("drifted", "unacceptable", "within tolerance", "passed"):
            assert marker not in markdown


class TestPersistedForm:
    @pytest.fixture(scope="class")
    def study_schema(self) -> dict:
        path = (
            REPO_ROOT
            / "contracts"
            / "ttp_preliminary_repeatability_study_v1.schema.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def make_study(self, **overrides) -> RepeatabilityStudyV1:
        kwargs = {
            "study_id": "study-e1",
            "experiment_definition": PreliminaryExperimentDefinitionV1(
                experiment_id="e1-rig",
                instrument_id="rig-1",
                measurement_point_id="D1",
                operator_id="op-1",
                planned_repeat_count=2,
                created_at=UTC_NOW,
                reference_structure_id="ref-plate-1",
                excitation=ExcitationContextV1(
                    excitation_method="shaker_stinger",
                    rig_configuration_id="rig-1",
                    stinger_mass_g=1.42,
                    contact_tip_mass_g=0.31,
                    combined_contact_mass_g=1.80,
                ),
            ),
            "generated_at": UTC_NOW,
            "evidence_origin": EvidenceOrigin.FIXTURE,
            "runs": (make_run("r1", sequence_index=0),),
        }
        kwargs.update(overrides)
        return RepeatabilityStudyV1(**kwargs)

    def test_a_study_carrying_all_of_it_validates(self, study_schema):
        jsonschema.validate(self.make_study().to_dict(), study_schema)

    def test_a_negative_mass_is_refused_by_the_schema(self, study_schema):
        payload = self.make_study().to_dict()
        payload["experiment_definition"]["excitation"]["stinger_mass_g"] = -1.0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_a_negative_sequence_index_is_refused_by_the_schema(self, study_schema):
        payload = self.make_study().to_dict()
        payload["runs"][0]["sequence_index"] = -1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_the_registry_records_the_additive_bump(self):
        registry = json.loads(
            (REPO_ROOT / "contracts" / "schema_registry.json").read_text(
                encoding="utf-8"
            )
        )
        assert (
            registry["schemas"]["ttp_preliminary_repeatability_study"]["version"]
            == "1.3.0"
        )
        assert registry["schemas"]["ttp_hardware_campaign"]["version"] == "1.1.0"
