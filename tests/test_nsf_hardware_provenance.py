"""Provenance-derived hardware claims (DO-103 Stage 3, §5.4 and §6.6).

DO-102 guarded the ``HARDWARE`` label two ways: it refused the label for a
result marked ``demo: true``, and it required a study's runs to agree with the
study's own label. Neither stopped a caller asserting ``HARDWARE`` over data
that simply lacked a demo flag.

These tests hold the tightening: a hardware claim is derived from recorded
acquisition provenance, so it cannot be made by choosing a label. Most of what
follows is deliberately negative — the useful question about this layer is not
whether a well-formed hardware run validates, it is whether a false one can be
made to.

Two standards are kept apart on purpose. ``EvidenceOrigin.HARDWARE`` classifies
where data came from; a *witnessed* session is the stronger governance
condition §10 requires before a capability may be promoted off
``NOT_VERIFIED_ON_HARDWARE``. Every witnessed run is hardware-origin; the
reverse does not hold, and the tests below prove the gap is real rather than
decorative.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness import (
    KNOWN_ACQUISITION_QUANTITIES,
    AcquisitionChannelV1,
    AcquisitionProvenanceV1,
    AcquisitionRole,
    EvidenceOrigin,
    ExcitationContextV1,
    GrantReadinessErrorCode,
    ObservedFeatureV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
    RepeatabilityStudyV1,
)
from tap_tone_pi.grant_readiness.errors import (
    ExperimentRecordError,
    RepeatabilityStatisticsError,
)
from tap_tone_pi.grant_readiness.report import build_study_report, render_study_report
from tap_tone_pi.grant_readiness.validation import (
    validate_experiment_runs,
    validate_repeatability_study,
    validate_run_acquisition_provenance,
    validate_transfer_quantity_naming,
    validate_witnessed_hardware_session,
)

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC_NOW = "2026-08-19T12:00:00+00:00"


def codes(findings) -> list[str]:
    return [finding.code.value for finding in findings]


def force_channel(**overrides) -> AcquisitionChannelV1:
    kwargs = {
        "channel_index": 0,
        "role": AcquisitionRole.EXCITATION,
        "quantity": "force",
        "unit": "N",
        "sensor_id": "force-transducer-1",
    }
    kwargs.update(overrides)
    return AcquisitionChannelV1(**kwargs)


def mic_channel(**overrides) -> AcquisitionChannelV1:
    kwargs = {
        "channel_index": 1,
        "role": AcquisitionRole.RESPONSE,
        "quantity": "acoustic_pressure",
        "unit": "Pa",
        "sensor_id": "mic-1",
    }
    kwargs.update(overrides)
    return AcquisitionChannelV1(**kwargs)


def make_acquisition(**overrides) -> AcquisitionProvenanceV1:
    kwargs = {
        "session_id": "session-001",
        "acquisition_id": "acq-001",
        "interface_id": "interface-001",
        "sample_rate_hz": 48000,
        "channels": (force_channel(), mic_channel()),
        "excitation_device_id": "shaker-1",
        "drive_parameters": "stepped sine 40-1200 Hz, 0.5 V",
        "raw_artifact_ids": ("runs/e2/run-001.wav",),
    }
    kwargs.update(overrides)
    return AcquisitionProvenanceV1(**kwargs)


def make_hardware_run(
    run_id: str = "run-001", **overrides
) -> PreliminaryExperimentRunV1:
    kwargs = {
        "run_id": run_id,
        "experiment_id": "exp-e2",
        "captured_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.HARDWARE,
        "source_artifact_ids": ("runs/e2/run-001.wav",),
        "observed_features": (
            ObservedFeatureV1("acoustic_transfer_magnitude", "Pa/N", 0.004),
        ),
        "acquisition": make_acquisition(),
    }
    kwargs.update(overrides)
    return PreliminaryExperimentRunV1(**kwargs)


# ---------------------------------------------------------------------------
# Record shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "record_cls",
    [AcquisitionChannelV1, AcquisitionProvenanceV1],
    ids=lambda c: c.__name__,
)
class TestAcquisitionRecordShape:
    def test_is_frozen_dataclass(self, record_cls):
        assert dataclasses.is_dataclass(record_cls)
        assert record_cls.__dataclass_params__.frozen

    def test_no_mutable_defaults(self, record_cls):
        for spec in dataclasses.fields(record_cls):
            assert not isinstance(spec.default, (list, dict, set))


class TestAcquisitionChannel:
    def test_round_trip(self):
        channel = force_channel(gain_setting="+20 dB")
        assert AcquisitionChannelV1.from_dict(channel.to_dict()) == channel

    def test_known_quantity_is_reported_not_enforced(self):
        # Mirrors ExcitationContextV1: an unlisted value is recorded and
        # flagged, never refused. Refusing it would lose the record of what was
        # actually measured.
        assert force_channel().is_known_quantity
        exotic = force_channel(quantity="strain")
        assert not exotic.is_known_quantity
        assert AcquisitionChannelV1.from_dict(exotic.to_dict()) == exotic

    def test_force_and_pressure_are_in_the_known_vocabulary(self):
        assert "force" in KNOWN_ACQUISITION_QUANTITIES
        assert "acoustic_pressure" in KNOWN_ACQUISITION_QUANTITIES

    def test_unknown_field_rejected(self):
        payload = force_channel().to_dict()
        payload["calibrated"] = True
        with pytest.raises(ExperimentRecordError) as exc:
            AcquisitionChannelV1.from_dict(payload)
        assert "calibrated" in str(exc.value)

    @pytest.mark.parametrize("bad", [-1, 1.5, True, None, "0"])
    def test_channel_index_must_be_a_non_negative_integer(self, bad):
        payload = force_channel().to_dict()
        payload["channel_index"] = bad
        with pytest.raises(ExperimentRecordError):
            AcquisitionChannelV1.from_dict(payload)

    def test_unknown_role_rejected(self):
        payload = force_channel().to_dict()
        payload["role"] = "REFERENCE"
        with pytest.raises(ExperimentRecordError) as exc:
            AcquisitionChannelV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION

    def test_sensor_identity_is_required(self):
        payload = force_channel().to_dict()
        payload["sensor_id"] = "   "
        with pytest.raises(ExperimentRecordError):
            AcquisitionChannelV1.from_dict(payload)


class TestAcquisitionProvenance:
    def test_round_trip(self):
        acquisition = make_acquisition(witnessed_by="operator-1")
        assert AcquisitionProvenanceV1.from_dict(acquisition.to_dict()) == acquisition

    def test_absent_provenance_deserializes_to_none(self):
        assert AcquisitionProvenanceV1.from_dict(None) is None

    def test_transfer_unit_is_derived_from_the_channels(self):
        # Pa/N because that is what the two channels say they carried — not
        # because this campaign expects it. DO-103 §6.6.
        assert make_acquisition().transfer_unit == "Pa/N"

    def test_transfer_unit_follows_the_channels_it_is_given(self):
        two_mics = make_acquisition(
            channels=(
                force_channel(quantity="acoustic_pressure", unit="Pa"),
                mic_channel(),
            )
        )
        assert two_mics.transfer_unit == "Pa/Pa"

    def test_transfer_unit_is_unknown_when_the_pair_is_ambiguous(self):
        two_responses = make_acquisition(
            channels=(mic_channel(), mic_channel(channel_index=2, sensor_id="mic-2"))
        )
        assert two_responses.transfer_unit is None
        assert make_acquisition(channels=()).transfer_unit is None

    def test_witnessing_is_recorded_not_assumed(self):
        assert not make_acquisition().is_witnessed
        assert make_acquisition(witnessed_by="operator-1").is_witnessed

    def test_unknown_field_rejected(self):
        payload = make_acquisition().to_dict()
        payload["traceable"] = True
        with pytest.raises(ExperimentRecordError) as exc:
            AcquisitionProvenanceV1.from_dict(payload)
        assert "traceable" in str(exc.value)

    @pytest.mark.parametrize("bad", [0, -48000, 48000.0, True, None])
    def test_sample_rate_must_be_a_positive_integer(self, bad):
        payload = make_acquisition().to_dict()
        payload["sample_rate_hz"] = bad
        with pytest.raises(ExperimentRecordError):
            AcquisitionProvenanceV1.from_dict(payload)


# ---------------------------------------------------------------------------
# The hardware claim is derived, not declared
# ---------------------------------------------------------------------------


class TestHardwareClaimIsDerived:
    def test_complete_provenance_validates(self):
        assert validate_run_acquisition_provenance(make_hardware_run()) == []

    def test_hardware_without_provenance_is_refused(self):
        # The exact gap DO-102 left open: a caller asserting HARDWARE over data
        # that carries no demo flag and no provenance either.
        run = make_hardware_run(acquisition=None)
        findings = validate_run_acquisition_provenance(run)
        assert codes(findings) == ["NSF-306"]

    @pytest.mark.parametrize(
        "field_name", ["session_id", "acquisition_id", "interface_id"]
    )
    def test_hardware_with_a_blank_identifier_is_refused(self, field_name):
        run = make_hardware_run(acquisition=make_acquisition(**{field_name: "  "}))
        findings = validate_run_acquisition_provenance(run)
        assert codes(findings) == ["NSF-306"]
        assert findings[0].context["missing_fields"] == [field_name]

    def test_hardware_with_no_excitation_channel_is_refused(self):
        run = make_hardware_run(acquisition=make_acquisition(channels=(mic_channel(),)))
        findings = validate_run_acquisition_provenance(run)
        assert codes(findings) == ["NSF-306"]
        assert findings[0].context["role"] == "EXCITATION"

    def test_hardware_with_no_response_channel_is_refused(self):
        run = make_hardware_run(
            acquisition=make_acquisition(channels=(force_channel(),))
        )
        findings = validate_run_acquisition_provenance(run)
        assert codes(findings) == ["NSF-306"]
        assert findings[0].context["role"] == "RESPONSE"

    def test_hardware_retaining_no_raw_measurement_is_refused(self):
        run = make_hardware_run(
            source_artifact_ids=(),
            acquisition=make_acquisition(raw_artifact_ids=()),
        )
        assert codes(validate_run_acquisition_provenance(run)) == ["NSF-306"]

    def test_the_run_artifact_satisfies_retention(self):
        # The run already names its source; the provenance need not repeat it.
        run = make_hardware_run(acquisition=make_acquisition(raw_artifact_ids=()))
        assert validate_run_acquisition_provenance(run) == []

    def test_a_lost_artifact_stays_recordable(self):
        # MISSING_ARTIFACT is the rejection reason for a capture that produced
        # no file. Demanding an artifact here would make an honest rejection
        # unrecordable and reward dropping the run instead (DO-103 §6.7).
        run = make_hardware_run(
            valid=False,
            rejection_reason=RejectionReason.MISSING_ARTIFACT,
            observed_features=(),
            source_artifact_ids=(),
            acquisition=make_acquisition(raw_artifact_ids=()),
        )
        assert validate_run_acquisition_provenance(run) == []

    def test_a_rejected_run_still_retains_its_raw_measurement(self):
        # Every other rejection reason keeps the evidence: the capture happened,
        # it was simply not usable.
        run = make_hardware_run(
            valid=False,
            rejection_reason=RejectionReason.CLIPPING,
            observed_features=(),
            source_artifact_ids=(),
            acquisition=make_acquisition(raw_artifact_ids=()),
        )
        assert codes(validate_run_acquisition_provenance(run)) == ["NSF-306"]

    @pytest.mark.parametrize(
        "origin", [EvidenceOrigin.FIXTURE, EvidenceOrigin.SYNTHETIC]
    )
    def test_non_hardware_runs_are_untouched(self, origin):
        # The tightening is additive. A DO-102 fixture record means exactly what
        # it meant before and needs no provenance to stay valid.
        run = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-e2",
            captured_at=UTC_NOW,
            evidence_origin=origin,
            source_artifact_ids=("fixtures/tap.json",),
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 245.0),),
        )
        assert validate_run_acquisition_provenance(run) == []

    def test_relabelling_a_fixture_run_does_not_make_it_hardware(self):
        # The whole point, stated as one test: the label is not the claim.
        fixture = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-e2",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            source_artifact_ids=("fixtures/tap.json",),
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 245.0),),
        )
        assert validate_experiment_runs([fixture]) == []

        relabelled = dataclasses.replace(
            fixture, evidence_origin=EvidenceOrigin.HARDWARE
        )
        assert "NSF-306" in codes(validate_experiment_runs([relabelled]))

    def test_run_collection_validation_carries_the_check(self):
        findings = validate_experiment_runs([make_hardware_run(acquisition=None)])
        assert "NSF-306" in codes(findings)


# ---------------------------------------------------------------------------
# p/F is not a mechanical frequency response (§6.6)
# ---------------------------------------------------------------------------


class TestMechanicalFrfNaming:
    @pytest.mark.parametrize(
        "quantity",
        ["mobility", "transfer_mobility", "accelerance", "receptance", "compliance"],
    )
    def test_a_mechanical_name_over_an_acoustic_response_is_refused(self, quantity):
        run = make_hardware_run(
            observed_features=(ObservedFeatureV1(quantity, "Pa/N", 0.004),)
        )
        findings = validate_transfer_quantity_naming(run)
        assert codes(findings) == ["NSF-308"]
        assert findings[0].context["quantity"] == quantity

    def test_the_acoustic_name_is_accepted(self):
        assert validate_transfer_quantity_naming(make_hardware_run()) == []

    def test_a_mechanical_response_may_use_a_mechanical_name(self):
        # The rule is about the response quantity, not the vocabulary. Measure
        # velocity and mobility is the correct word for v/F.
        run = make_hardware_run(
            observed_features=(ObservedFeatureV1("mobility", "m/s/N", 0.01),),
            acquisition=make_acquisition(
                channels=(
                    force_channel(),
                    mic_channel(quantity="velocity", unit="m/s", sensor_id="ldv-1"),
                )
            ),
        )
        assert validate_transfer_quantity_naming(run) == []

    def test_a_run_without_acquisition_is_not_judged(self):
        run = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-e2",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            observed_features=(ObservedFeatureV1("mobility", "ratio", 1.0),),
        )
        assert validate_transfer_quantity_naming(run) == []


# ---------------------------------------------------------------------------
# Witnessed is stricter than hardware-origin (§5.4, consumed by §10)
# ---------------------------------------------------------------------------


def make_study(**overrides) -> RepeatabilityStudyV1:
    runs = overrides.pop(
        "runs",
        (
            make_hardware_run("run-001"),
            make_hardware_run("run-002"),
        ),
    )
    kwargs = {
        "study_id": "study-e2",
        "experiment_definition": PreliminaryExperimentDefinitionV1(
            experiment_id="exp-e2",
            instrument_id="rig-under-test",
            measurement_point_id="P1",
            operator_id="operator-1",
            planned_repeat_count=10,
            created_at=UTC_NOW,
            excitation=ExcitationContextV1(excitation_method="shaker_stinger"),
        ),
        "generated_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.HARDWARE,
        "runs": runs,
        "limitations": ("Repeatability is not accuracy.",),
    }
    kwargs.update(overrides)
    return RepeatabilityStudyV1(**kwargs)


class TestWitnessedIsStricterThanHardwareOrigin:
    def test_hardware_origin_alone_is_not_witnessed(self):
        study = make_study()
        # Valid as a study: it says truthfully what it observed and where the
        # data came from.
        assert validate_repeatability_study(study) == []
        # Not enough to promote a capability: nobody is attached to it.
        assert codes(validate_witnessed_hardware_session(study)) == ["NSF-307"]

    def test_attributed_acquisition_is_witnessed(self):
        witnessed = make_study(
            runs=(
                make_hardware_run(
                    "run-001", acquisition=make_acquisition(witnessed_by="operator-1")
                ),
                make_hardware_run(
                    "run-002", acquisition=make_acquisition(witnessed_by="operator-1")
                ),
            )
        )
        assert validate_witnessed_hardware_session(witnessed) == []
        assert all(run.is_witnessed_hardware for run in witnessed.runs)

    def test_one_unattributed_run_breaks_the_session(self):
        mixed = make_study(
            runs=(
                make_hardware_run(
                    "run-001", acquisition=make_acquisition(witnessed_by="operator-1")
                ),
                make_hardware_run("run-002"),
            )
        )
        findings = validate_witnessed_hardware_session(mixed)
        assert codes(findings) == ["NSF-307"]
        assert findings[0].context["unwitnessed_run_ids"] == ["run-002"]

    def test_fixture_data_can_never_be_a_witnessed_session(self):
        fixture_runs = tuple(
            dataclasses.replace(
                run, evidence_origin=EvidenceOrigin.FIXTURE, acquisition=None
            )
            for run in make_study().runs
        )
        study = make_study(evidence_origin=EvidenceOrigin.FIXTURE, runs=fixture_runs)
        assert codes(validate_witnessed_hardware_session(study)) == ["NSF-307"]

    def test_witnessing_is_not_required_for_a_study_to_validate(self):
        # Deliberate separation: an unwitnessed hardware study is real evidence
        # of what it observed. It is simply not a promotion.
        assert validate_repeatability_study(make_study()) == []


class TestStudyValidationRefusesUnbackedHardware:
    def test_a_hardware_study_of_unbacked_runs_does_not_validate(self):
        study = make_study(
            runs=(
                make_hardware_run("run-001", acquisition=None),
                make_hardware_run("run-002", acquisition=None),
            )
        )
        assert codes(validate_repeatability_study(study)) == ["NSF-306", "NSF-306"]


class TestTheRendererRefusesWhatTheValidatorWould:
    """The renderer may never emit a document the validator would reject.

    A study can be assembled with ``strict=False``, so the renderer is the one
    place an unbacked hardware claim could otherwise reach a published document.
    It delegates to the same validators rather than re-deriving the rule, which
    is the lesson DO-102's own review recorded.
    """

    def test_an_unbacked_hardware_study_is_not_rendered(self):
        study = make_study(
            runs=(
                make_hardware_run("run-001", acquisition=None),
                make_hardware_run("run-002", acquisition=None),
            )
        )
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            render_study_report(study)
        assert exc.value.code is GrantReadinessErrorCode.HARDWARE_PROVENANCE_INCOMPLETE

    def test_an_unbacked_hardware_study_is_not_serialized(self):
        study = make_study(runs=(make_hardware_run("run-001", acquisition=None),))
        with pytest.raises(RepeatabilityStatisticsError):
            build_study_report(study)

    def test_a_backed_hardware_study_renders(self):
        study = make_study()
        assert "HARDWARE" in render_study_report(study)
        assert build_study_report(study)["is_hardware_evidence"] is True

    def test_the_existing_mislabelling_guard_still_fires(self):
        # Regression on DO-102's own invariant: the new check is additional, not
        # a replacement.
        mixed = make_study(
            runs=(
                make_hardware_run("run-001"),
                dataclasses.replace(
                    make_hardware_run("run-002"),
                    evidence_origin=EvidenceOrigin.FIXTURE,
                    acquisition=None,
                ),
            )
        )
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            render_study_report(mixed)
        assert exc.value.code is GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED


# ---------------------------------------------------------------------------
# Persisted form
# ---------------------------------------------------------------------------


class TestStudySchemaCarriesAcquisition:
    @pytest.fixture(scope="class")
    def study_schema(self) -> dict:
        path = (
            REPO_ROOT
            / "contracts"
            / "ttp_preliminary_repeatability_study_v1.schema.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def test_a_hardware_study_validates_against_the_schema(self, study_schema):
        payload = make_study(
            runs=(
                make_hardware_run(
                    "run-001", acquisition=make_acquisition(witnessed_by="operator-1")
                ),
            )
        ).to_dict()
        jsonschema.validate(payload, study_schema)

    def test_a_non_hardware_run_serializes_acquisition_as_null(self, study_schema):
        run = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-e2",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            source_artifact_ids=("fixtures/tap.json",),
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 245.0),),
        )
        payload = make_study(
            evidence_origin=EvidenceOrigin.FIXTURE, runs=(run,)
        ).to_dict()
        assert payload["runs"][0]["acquisition"] is None
        jsonschema.validate(payload, study_schema)

    def test_the_schema_rejects_an_unknown_acquisition_field(self, study_schema):
        payload = make_study(runs=(make_hardware_run("run-001"),)).to_dict()
        payload["runs"][0]["acquisition"]["traceable_to_standard"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_the_registry_records_the_additive_bump(self):
        registry = json.loads(
            (REPO_ROOT / "contracts" / "schema_registry.json").read_text(
                encoding="utf-8"
            )
        )
        entry = registry["schemas"]["ttp_preliminary_repeatability_study"]
        # 1.1.0 added the acquisition block in Stage 3; 1.2.0 added the
        # per-run campaign condition. Both are additive and neither changed the
        # meaning of an existing field, so the contract stays v1.
        assert entry["version"] == "1.2.0"
        assert entry["schema_version_const"] == "ttp_preliminary_repeatability_study_v1"
