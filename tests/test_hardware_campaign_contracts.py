"""Hardware campaign evidence contracts (DO-103 §7, §9).

DO-103 §9 rules that the DO-102 evidence container stays the container for all
five experiments, and that a field which genuinely cannot carry a meaning is
added rather than overloaded. These tests hold both halves of that: the additive
fields behave like every other record in this package — frozen, strict, exactly
round-tripping — and the records that carry what no study record can hold say
what their samples are instead of borrowing a field that means something else.

They are written before any rig exists, which is deliberate. The campaign is
analyzed by software that was settled before it produced data, not by software
shaped to fit the data it produced.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness import (
    CAMPAIGN_SCHEMA_VERSION,
    AcquisitionChannelV1,
    AcquisitionRole,
    AttachmentVariationV1,
    CalibrationTraceability,
    CampaignConditionV1,
    CampaignExecutionStatus,
    CampaignExperimentOutcomeV1,
    CampaignExperimentPlanV1,
    EvidenceOrigin,
    ExcitationContextV1,
    ExperimentKind,
    ExperimentOutcomeStatus,
    ExternalArtifactV1,
    GrantReadinessErrorCode,
    GroupSpreadV1,
    HardwareCampaignConfigV1,
    HardwareCampaignRecordV1,
    MassLoadingObservationV1,
    ObservedFeatureV1,
    PreliminaryExperimentRunV1,
    ReciprocityObservationV1,
    RepeatabilityMetricV1,
)
from tap_tone_pi.grant_readiness.errors import ExperimentRecordError
from tap_tone_pi.grant_readiness.hardware_campaign import (
    build_campaign_record,
    build_external_artifact,
    build_force_channel,
    build_response_channel,
    build_rig_excitation_context,
    artifact_digest,
)

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC_NOW = "2026-08-22T12:00:00+00:00"


def make_metric(**overrides) -> RepeatabilityMetricV1:
    kwargs = {
        "metric_id": "metric-1",
        "quantity": "acoustic_transfer_magnitude",
        "unit": "Pa/N",
        "sample_count": 2,
        "mean": 1.0,
        "median": 1.0,
        "standard_deviation": 0.1,
        "coefficient_of_variation_pct": 10.0,
        "minimum": 0.9,
        "maximum": 1.1,
        "range_value": 0.2,
        "median_absolute_deviation": 0.1,
        "source_run_ids": ("r1", "r2"),
    }
    kwargs.update(overrides)
    return RepeatabilityMetricV1(**kwargs)


def make_spread(**overrides) -> GroupSpreadV1:
    kwargs = {
        "group_kind": "attachment",
        "quantity": "acoustic_transfer_magnitude",
        "unit": "Pa/N",
        "group_count": 2,
        "group_ids": ("att-1", "att-2"),
        "group_values": (1.0, 1.3),
        "mean": 1.15,
        "median": 1.15,
        "standard_deviation": 0.212,
        "coefficient_of_variation_pct": 18.4,
        "minimum": 1.0,
        "maximum": 1.3,
        "range_value": 0.3,
        "median_absolute_deviation": 0.15,
    }
    kwargs.update(overrides)
    return GroupSpreadV1(**kwargs)


def make_config(**overrides) -> HardwareCampaignConfigV1:
    kwargs = {
        "campaign_id": "camp-1",
        "created_at": UTC_NOW,
        "operator_id": "operator-1",
        "interface_id": "iface-1",
        "sample_rate_hz": 48000,
        "excitation": build_rig_excitation_context(
            rig_configuration_id="rig-1",
            shaker_id="shaker-1",
            stinger_id="stinger-1",
            contact_tip_id="tip-1",
        ),
        "channels": (
            build_force_channel(channel_index=0, sensor_id="force-1", unit="N"),
            build_response_channel(channel_index=1, sensor_id="mic-1", unit="Pa"),
        ),
        "experiments": (
            CampaignExperimentPlanV1(
                experiment_id="e2",
                kind=ExperimentKind.FIXED_POINT,
                instrument_id="plate-A",
                measurement_point_id="P1",
                planned_repeat_count=5,
            ),
        ),
    }
    kwargs.update(overrides)
    return HardwareCampaignConfigV1(**kwargs)


def make_reciprocity(**overrides) -> ReciprocityObservationV1:
    kwargs = {
        "observation_id": "reciprocity-1",
        "quantity": "acoustic_transfer_magnitude",
        "unit": "Pa/N",
        "forward_run_id": "f1",
        "reverse_run_id": "r1",
        "forward_drive_point_id": "A",
        "forward_response_point_id": "B",
        "forward_value": 1.0,
        "reverse_value": 0.9,
        "absolute_residual": 0.1,
    }
    kwargs.update(overrides)
    return ReciprocityObservationV1(**kwargs)


def make_mass_loading(**overrides) -> MassLoadingObservationV1:
    kwargs = {
        "observation_id": "mass-1",
        "quantity": "acoustic_transfer_magnitude",
        "unit": "Pa/N",
        "mass_challenge_id": "m-2g",
        "added_mass_g": 2.03,
        "baseline_metric": make_metric(metric_id="metric-baseline"),
        "loaded_metric": make_metric(metric_id="metric-loaded", mean=0.9),
        "absolute_delta": -0.1,
    }
    kwargs.update(overrides)
    return MassLoadingObservationV1(**kwargs)


CAMPAIGN_RECORDS = [
    CampaignConditionV1,
    GroupSpreadV1,
    AttachmentVariationV1,
    ReciprocityObservationV1,
    MassLoadingObservationV1,
    ExternalArtifactV1,
    CampaignExperimentPlanV1,
    HardwareCampaignConfigV1,
    CampaignExperimentOutcomeV1,
    HardwareCampaignRecordV1,
]


@pytest.mark.parametrize("record_cls", CAMPAIGN_RECORDS, ids=lambda c: c.__name__)
class TestRecordShape:
    def test_is_frozen_dataclass(self, record_cls):
        assert dataclasses.is_dataclass(record_cls)
        assert record_cls.__dataclass_params__.frozen

    def test_no_mutable_defaults(self, record_cls):
        for field in dataclasses.fields(record_cls):
            assert not isinstance(field.default, (list, dict, set))


class TestCampaignCondition:
    def test_round_trip(self):
        condition = CampaignConditionV1(
            experiment_kind=ExperimentKind.MASS_LOADING,
            mass_challenge_id="m-2g",
            added_mass_g=2.03,
            nominal_added_mass_g=2.0,
            mass_location_id="bridge",
            note="lead tape",
        )
        assert CampaignConditionV1.from_dict(condition.to_dict()) == condition

    def test_absent_condition_deserializes_to_none(self):
        assert CampaignConditionV1.from_dict(None) is None

    def test_unknown_field_rejected(self):
        payload = CampaignConditionV1(ExperimentKind.FIXED_POINT).to_dict()
        payload["added_mass_kg"] = 0.002
        with pytest.raises(ExperimentRecordError):
            CampaignConditionV1.from_dict(payload)

    def test_unknown_experiment_kind_rejected(self):
        payload = CampaignConditionV1(ExperimentKind.FIXED_POINT).to_dict()
        payload["experiment_kind"] = "E6"
        with pytest.raises(ExperimentRecordError):
            CampaignConditionV1.from_dict(payload)

    def test_a_measured_zero_is_the_baseline(self):
        assert CampaignConditionV1(
            ExperimentKind.MASS_LOADING, added_mass_g=0.0
        ).is_mass_baseline

    def test_an_unrecorded_mass_is_not_a_baseline(self):
        # None is unknown, not zero. Treating it as a baseline would let an
        # unmeasured run anchor every comparison drawn against it.
        assert not CampaignConditionV1(ExperimentKind.MASS_LOADING).is_mass_baseline

    def test_transpose_is_recognised(self):
        forward = CampaignConditionV1(
            ExperimentKind.RECIPROCITY, drive_point_id="A", response_point_id="B"
        )
        reverse = CampaignConditionV1(
            ExperimentKind.RECIPROCITY, drive_point_id="B", response_point_id="A"
        )
        assert forward.is_transpose_of(reverse)
        assert reverse.is_transpose_of(forward)

    def test_a_repeat_is_not_a_transpose(self):
        forward = CampaignConditionV1(
            ExperimentKind.RECIPROCITY, drive_point_id="A", response_point_id="B"
        )
        assert not forward.is_transpose_of(forward)

    def test_a_self_pair_is_not_a_transpose(self):
        same = CampaignConditionV1(
            ExperimentKind.RECIPROCITY, drive_point_id="A", response_point_id="A"
        )
        assert not same.is_transpose_of(same)

    def test_a_partial_pair_has_no_point_pair(self):
        assert (
            CampaignConditionV1(
                ExperimentKind.RECIPROCITY, drive_point_id="A"
            ).point_pair
            is None
        )


class TestRunCarriesTheCondition:
    def make_run(self, **overrides) -> PreliminaryExperimentRunV1:
        kwargs = {
            "run_id": "r1",
            "experiment_id": "e2",
            "captured_at": UTC_NOW,
            "evidence_origin": EvidenceOrigin.FIXTURE,
            "source_artifact_ids": ("fixtures/a.json",),
            "observed_features": (
                ObservedFeatureV1("acoustic_transfer_magnitude", "Pa/N", 1.0),
            ),
        }
        kwargs.update(overrides)
        return PreliminaryExperimentRunV1(**kwargs)

    def test_round_trip_with_a_condition(self):
        run = self.make_run(
            campaign_condition=CampaignConditionV1(
                ExperimentKind.DETACH_REATTACH, contact_configuration_id="att-1"
            )
        )
        assert PreliminaryExperimentRunV1.from_dict(run.to_dict()) == run

    def test_a_do102_run_still_round_trips_without_one(self):
        run = self.make_run()
        payload = run.to_dict()
        assert payload["campaign_condition"] is None
        assert PreliminaryExperimentRunV1.from_dict(payload) == run

    def test_experiment_kind_is_none_without_a_condition(self):
        assert self.make_run().experiment_kind is None

    def test_experiment_kind_comes_from_the_condition(self):
        run = self.make_run(
            campaign_condition=CampaignConditionV1(ExperimentKind.RECIPROCITY)
        )
        assert run.experiment_kind is ExperimentKind.RECIPROCITY


class TestRigIdentity:
    def test_round_trip_with_rig_parts(self):
        excitation = build_rig_excitation_context(
            rig_configuration_id="rig-1",
            shaker_id="shaker-1",
            stinger_id="stinger-1",
            contact_tip_id="tip-1",
            fixture_id="fix-1",
        )
        assert ExcitationContextV1.from_dict(excitation.to_dict()) == excitation

    def test_a_do102_excitation_still_round_trips(self):
        excitation = ExcitationContextV1(excitation_method="manual_tap")
        assert ExcitationContextV1.from_dict(excitation.to_dict()) == excitation

    def test_rig_identity_names_every_swappable_part(self):
        identity = build_rig_excitation_context(rig_configuration_id="rig-1")
        assert set(identity.rig_identity) == {
            "rig_configuration_id",
            "excitation_device_id",
            "stinger_id",
            "contact_tip_id",
            "fixture_id",
        }

    def test_contact_drive_uses_a_known_method(self):
        assert build_rig_excitation_context(
            rig_configuration_id="rig-1"
        ).is_known_method


class TestChannelCalibrationMetadata:
    def test_round_trip(self):
        channel = build_force_channel(
            channel_index=0,
            sensor_id="force-1",
            unit="N",
            sensitivity_value=10.2,
            sensitivity_unit="mV/N",
            calibration_traceability=CalibrationTraceability.NOMINAL,
        )
        assert AcquisitionChannelV1.from_dict(channel.to_dict()) == channel

    def test_traceability_defaults_to_unknown(self):
        # A sensor nobody has calibrated has no traceability this repository can
        # attest to, and the default must not imply one.
        channel = build_force_channel(channel_index=0, sensor_id="f", unit="N")
        assert channel.calibration_traceability is CalibrationTraceability.UNKNOWN
        assert not channel.claims_traceability

    def test_a_do102_channel_deserializes_as_unknown(self):
        payload = {
            "channel_index": 0,
            "role": "EXCITATION",
            "quantity": "force",
            "unit": "N",
            "sensor_id": "force-1",
        }
        channel = AcquisitionChannelV1.from_dict(payload)
        assert channel.calibration_traceability is CalibrationTraceability.UNKNOWN

    def test_an_unrecognised_traceability_is_refused_not_defaulted(self):
        payload = build_force_channel(
            channel_index=0, sensor_id="f", unit="N"
        ).to_dict()
        payload["calibration_traceability"] = "PROBABLY_FINE"
        with pytest.raises(ExperimentRecordError):
            AcquisitionChannelV1.from_dict(payload)

    def test_sensitivity_needs_both_halves_to_be_recorded(self):
        channel = build_force_channel(
            channel_index=0, sensor_id="f", unit="N", sensitivity_value=10.2
        )
        assert not channel.sensitivity_is_recorded

    def test_no_sensor_sensitivity_is_assumed(self):
        # DO-103 fixes no transducer in advance, so nothing here may supply a
        # plausible mV/N on the caller's behalf.
        channel = build_force_channel(channel_index=0, sensor_id="f", unit="N")
        assert channel.sensitivity_value is None
        assert channel.sensitivity_unit is None


class TestGroupSpreadSaysWhatItsSamplesAre:
    def test_round_trip(self):
        spread = make_spread()
        assert GroupSpreadV1.from_dict(spread.to_dict()) == spread

    def test_it_names_its_groups_not_runs(self):
        spread = make_spread()
        payload = spread.to_dict()
        assert "source_run_ids" not in payload
        assert payload["group_kind"] == "attachment"
        assert payload["group_ids"] == ["att-1", "att-2"]

    def test_every_value_is_traceable_to_its_group(self):
        spread = make_spread()
        assert len(spread.group_values) == len(spread.group_ids)

    def test_unknown_field_rejected(self):
        payload = make_spread().to_dict()
        payload["is_acceptable"] = True
        with pytest.raises(ExperimentRecordError):
            GroupSpreadV1.from_dict(payload)


class TestAttachmentVariation:
    def test_round_trip(self):
        variation = AttachmentVariationV1(
            variation_id="variation-1",
            quantity="acoustic_transfer_magnitude",
            unit="Pa/N",
            attachment_ids=("att-1", "att-2"),
            within_attachment_metrics=(make_metric(),),
            between_attachment_spread=make_spread(),
            unsummarized_attachment_ids=("att-3",),
        )
        assert AttachmentVariationV1.from_dict(variation.to_dict()) == variation

    def test_a_variation_without_a_between_spread_round_trips(self):
        variation = AttachmentVariationV1(
            variation_id="variation-1",
            quantity="q",
            unit="Pa/N",
            attachment_ids=("att-1",),
        )
        payload = variation.to_dict()
        assert payload["between_attachment_spread"] is None
        assert AttachmentVariationV1.from_dict(payload) == variation

    def test_a_disagreeing_derived_count_is_refused(self):
        payload = AttachmentVariationV1(
            variation_id="v",
            quantity="q",
            unit="Pa/N",
            attachment_ids=("att-1", "att-2"),
        ).to_dict()
        payload["attachment_count"] = 7
        with pytest.raises(ExperimentRecordError):
            AttachmentVariationV1.from_dict(payload)


class TestObservationRecordsCarryNoVerdict:
    @pytest.mark.parametrize(
        "payload",
        [make_reciprocity().to_dict(), make_mass_loading().to_dict()],
        ids=["reciprocity", "mass_loading"],
    )
    def test_no_acceptance_field_exists(self, payload):
        # DO-103 §4.6 and §4.7: the campaign produces the evidence a limit would
        # have to be derived from, so no observation may carry one.
        forbidden = {
            "passed",
            "is_acceptable",
            "acceptance_threshold",
            "verdict",
            "tolerance",
            "within_tolerance",
        }
        assert not forbidden & set(payload)

    def test_reciprocity_round_trip(self):
        observation = make_reciprocity(
            relative_residual=0.105,
            forward_evaluation_frequency_hz=220.0,
            reverse_evaluation_frequency_hz=220.5,
            forward_coherence=0.97,
            reverse_coherence=0.81,
        )
        assert ReciprocityObservationV1.from_dict(observation.to_dict()) == observation

    def test_reciprocity_keeps_both_coherences_apart(self):
        payload = make_reciprocity(
            forward_coherence=0.97, reverse_coherence=0.31
        ).to_dict()
        assert payload["forward_coherence"] == 0.97
        assert payload["reverse_coherence"] == 0.31

    def test_mass_loading_round_trip(self):
        observation = make_mass_loading(
            nominal_added_mass_g=2.0,
            mass_location_id="bridge",
            relative_delta_pct=-10.0,
        )
        assert MassLoadingObservationV1.from_dict(observation.to_dict()) == observation

    def test_mass_loading_keeps_measured_and_intended_apart(self):
        payload = make_mass_loading(nominal_added_mass_g=2.0).to_dict()
        assert payload["added_mass_g"] == 2.03
        assert payload["nominal_added_mass_g"] == 2.0

    def test_mass_loading_delta_keeps_its_sign(self):
        assert make_mass_loading().to_dict()["absolute_delta"] < 0

    def test_reciprocity_unknown_field_rejected(self):
        payload = make_reciprocity().to_dict()
        payload["passed"] = True
        with pytest.raises(ExperimentRecordError):
            ReciprocityObservationV1.from_dict(payload)

    def test_mass_loading_unknown_field_rejected(self):
        payload = make_mass_loading().to_dict()
        payload["detected"] = True
        with pytest.raises(ExperimentRecordError):
            MassLoadingObservationV1.from_dict(payload)


class TestExternalArtifact:
    def test_round_trip(self):
        artifact = build_external_artifact(
            artifact_id="art-1",
            kind="raw_audio",
            sha256=artifact_digest(b"bytes"),
            byte_count=5,
            media_type="audio/wav",
            storage_locator="campaigns/camp-1/raw/001.wav",
            capture_run_id="r1",
            local_path_hint="D:/captures/001.wav",
        )
        assert ExternalArtifactV1.from_dict(artifact.to_dict()) == artifact

    def test_the_builder_never_claims_repository_tracking(self):
        artifact = build_external_artifact(
            artifact_id="art-1",
            kind="raw_audio",
            sha256=artifact_digest(b""),
            byte_count=0,
            media_type="audio/wav",
            storage_locator="campaigns/camp-1/raw/001.wav",
        )
        assert artifact.repository_tracked is False

    def test_the_digest_is_of_the_bytes(self):
        import hashlib

        assert artifact_digest(b"abc") == hashlib.sha256(b"abc").hexdigest()

    def test_unknown_field_rejected(self):
        payload = build_external_artifact(
            artifact_id="art-1",
            kind="raw_audio",
            sha256=artifact_digest(b""),
            byte_count=0,
            media_type="audio/wav",
            storage_locator="a/b.wav",
        ).to_dict()
        payload["absolute_path"] = "D:/x.wav"
        with pytest.raises(ExperimentRecordError):
            ExternalArtifactV1.from_dict(payload)


class TestCampaignConfig:
    def test_round_trip(self):
        config = make_config()
        assert HardwareCampaignConfigV1.from_dict(config.to_dict()) == config

    def test_the_force_channel_is_found_by_what_it_carries(self):
        config = make_config()
        assert config.force_channel is not None
        assert config.force_channel.quantity == "force"

    def test_a_voltage_excitation_channel_is_not_a_force_channel(self):
        # Drive voltage is an excitation channel and is not a measured force.
        config = make_config(
            channels=(
                AcquisitionChannelV1(
                    0, AcquisitionRole.EXCITATION, "voltage", "V", "amp-1"
                ),
                build_response_channel(channel_index=1, sensor_id="mic-1", unit="Pa"),
            )
        )
        assert config.force_channel is None

    def test_plan_lookup(self):
        config = make_config()
        assert config.plan_for("e2") is not None
        assert config.plan_for("nope") is None

    def test_unknown_field_rejected(self):
        payload = make_config().to_dict()
        payload["shaker_amplifier_gain"] = 3
        with pytest.raises(ExperimentRecordError):
            HardwareCampaignConfigV1.from_dict(payload)


class TestCampaignRecord:
    def test_round_trip(self):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        )
        assert HardwareCampaignRecordV1.from_dict(record.to_dict()) == record

    def test_schema_version_is_identity_not_input(self):
        with pytest.raises(TypeError):
            HardwareCampaignRecordV1(
                campaign_id="c",
                generated_at=UTC_NOW,
                execution_status=CampaignExecutionStatus.PREPARED,
                config=make_config(),
                schema_version="something-else",
            )

    def test_wrong_schema_version_rejected(self):
        payload = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        ).to_dict()
        payload["schema_version"] = "ttp_hardware_campaign_v2"
        with pytest.raises(ExperimentRecordError):
            HardwareCampaignRecordV1.from_dict(payload)

    def test_every_planned_experiment_is_accounted_for(self):
        # An experiment nobody reported is recorded as not executed rather than
        # omitted: a gap and a decision must not look the same.
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        )
        assert [outcome.experiment_id for outcome in record.outcomes] == ["e2"]
        assert record.outcomes[0].status is ExperimentOutcomeStatus.NOT_EXECUTED

    def test_a_supplied_outcome_is_not_overwritten(self):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.HALTED_AT_GATE,
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=ExperimentOutcomeStatus.BLOCKED_BY_GATE,
                    blocked_by_experiment_id="e1",
                ),
            ),
        )
        assert record.outcomes[0].status is ExperimentOutcomeStatus.BLOCKED_BY_GATE

    def test_is_executed_follows_the_outcomes(self):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        )
        assert not record.is_executed
        assert record.executed_experiment_ids == ()

    def test_a_not_executed_campaign_states_it_in_its_limitations(self):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        )
        assert any("has not been executed" in text for text in record.limitations)

    def test_an_untraceable_force_channel_is_stated_as_a_limitation(self):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        )
        assert any("measured but not traceable" in text for text in record.limitations)

    def test_the_transfer_quantity_is_named_in_every_campaign(self):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        )
        joined = " ".join(record.limitations).lower()
        assert "not mobility, accelerance, or receptance" in joined


class TestPersistedForm:
    @pytest.fixture(scope="class")
    def campaign_schema(self) -> dict:
        path = REPO_ROOT / "contracts" / f"{CAMPAIGN_SCHEMA_VERSION}.schema.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_schema_is_a_valid_2020_12_schema(self, campaign_schema):
        jsonschema.Draft202012Validator.check_schema(campaign_schema)

    def test_a_minimal_campaign_validates(self, campaign_schema):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        )
        jsonschema.validate(record.to_dict(), campaign_schema)

    def test_a_full_campaign_validates(self, campaign_schema):
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
            artifacts=(
                build_external_artifact(
                    artifact_id="art-1",
                    kind="raw_audio",
                    sha256=artifact_digest(b"x"),
                    byte_count=1,
                    media_type="audio/wav",
                    storage_locator="campaigns/camp-1/raw/001.wav",
                    capture_run_id="r1",
                ),
            ),
            attachment_variation=(
                AttachmentVariationV1(
                    variation_id="v",
                    quantity="acoustic_transfer_magnitude",
                    unit="Pa/N",
                    attachment_ids=("att-1", "att-2"),
                    within_attachment_metrics=(make_metric(),),
                    between_attachment_spread=make_spread(),
                ),
            ),
            reciprocity=(make_reciprocity(relative_residual=0.1),),
            mass_loading=(make_mass_loading(),),
        )
        jsonschema.validate(record.to_dict(), campaign_schema)

    def test_the_schema_rejects_an_unknown_field(self, campaign_schema):
        payload = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
        ).to_dict()
        payload["conclusion"] = "the rig works"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, campaign_schema)

    def test_the_schema_rejects_a_digest_that_is_not_one(self, campaign_schema):
        payload = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
            artifacts=(
                build_external_artifact(
                    artifact_id="art-1",
                    kind="raw_audio",
                    sha256="not-a-digest",
                    byte_count=1,
                    media_type="audio/wav",
                    storage_locator="campaigns/camp-1/raw/001.wav",
                ),
            ),
        ).to_dict()
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, campaign_schema)

    def test_the_schema_rejects_a_mass_challenge_that_adds_nothing(
        self, campaign_schema
    ):
        payload = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
            mass_loading=(make_mass_loading(added_mass_g=0.0),),
        ).to_dict()
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, campaign_schema)

    def test_a_campaign_with_a_frequency_gap_validates(self, campaign_schema):
        payload = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.PREPARED,
            reciprocity=(
                make_reciprocity(
                    forward_evaluation_frequency_hz=220.0,
                    reverse_evaluation_frequency_hz=221.5,
                ),
            ),
        ).to_dict()
        jsonschema.validate(payload, campaign_schema)
        assert payload["reciprocity"][0]["frequency_mismatch_hz"] == pytest.approx(1.5)

    def test_the_registry_records_the_campaign_contract(self):
        registry = json.loads(
            (REPO_ROOT / "contracts" / "schema_registry.json").read_text(
                encoding="utf-8"
            )
        )
        entry = registry["schemas"]["ttp_hardware_campaign"]
        assert entry["owner"] == "grant-readiness-team"
        assert entry["schema_version_const"] == CAMPAIGN_SCHEMA_VERSION
        assert (REPO_ROOT / entry["path"]).exists()

    def test_the_registry_records_the_additive_study_bump(self):
        # The study contract gained an optional per-run campaign condition. Its
        # semantics did not change, so this is a minor bump and not a v2.
        registry = json.loads(
            (REPO_ROOT / "contracts" / "schema_registry.json").read_text(
                encoding="utf-8"
            )
        )
        entry = registry["schemas"]["ttp_preliminary_repeatability_study"]
        assert entry["version"] == "1.2.0"
        assert entry["schema_version_const"] == "ttp_preliminary_repeatability_study_v1"


class TestErrorVocabulary:
    def test_campaign_codes_do_not_collide_with_existing_families(self):
        codes = [member.value for member in GrantReadinessErrorCode]
        assert len(codes) == len(set(codes))

    @pytest.mark.parametrize(
        "code",
        [
            "NSF-501",
            "NSF-502",
            "NSF-503",
            "NSF-504",
            "NSF-505",
            "NSF-506",
            "NSF-507",
            "NSF-508",
            "NSF-509",
            "NSF-510",
        ],
    )
    def test_every_campaign_code_is_declared(self, code):
        assert code in {member.value for member in GrantReadinessErrorCode}
