"""Campaign governance: configuration, artifacts, accounting, promotion.

DO-102's review left two lessons this file is written to keep. The renderer must
enforce the same invariants as the validator rather than a second copy of them,
and a claim a record cannot support must be refused wherever it is made — not
only on the path someone remembered to guard.

The promotion tests are the sharpest ones here. DO-103 §10 promotes a capability
off ``NOT_VERIFIED_ON_HARDWARE`` only on a *witnessed* session, and this order's
whole point is that no such session exists yet. Everything below proves the
software says so rather than assuming it.
"""

from __future__ import annotations

import dataclasses

import pytest

from tap_tone_pi.grant_readiness import (
    AcquisitionChannelV1,
    AcquisitionRole,
    CalibrationTraceability,
    CampaignConditionV1,
    CampaignExecutionStatus,
    CampaignExperimentOutcomeV1,
    CampaignExperimentPlanV1,
    EvidenceOrigin,
    ExperimentKind,
    HardwareCampaignConfigV1,
    ObservedFeatureV1,
    PreliminaryExperimentRunV1,
    RepeatabilityStudyV1,
)
from tap_tone_pi.grant_readiness.errors import RepeatabilityStatisticsError
from tap_tone_pi.grant_readiness.hardware_campaign import (
    artifact_digest,
    build_campaign_acquisition,
    build_campaign_definition,
    build_campaign_record,
    build_external_artifact,
    build_force_channel,
    build_response_channel,
    build_rig_excitation_context,
)
from tap_tone_pi.grant_readiness.phase2_experiment import TRANSFER_MAGNITUDE
from tap_tone_pi.grant_readiness.report import (
    build_campaign_report,
    canonical_json,
    render_campaign_report,
)
from tap_tone_pi.grant_readiness.validation import (
    validate_artifact_manifest,
    validate_campaign_config,
    validate_campaign_record,
    validate_channel_calibration,
    validate_experiment_runs,
    validate_witnessed_hardware_session,
)

UTC_NOW = "2026-08-22T12:00:00+00:00"
UNIT = "Pa/N"

# Language a campaign report must never contain. Checked as phrases rather than
# bare words so that ruling a name out ("it is not mobility") is not mistaken
# for using it.
FORBIDDEN_PHRASES = (
    "accurate to",
    "accuracy of",
    "is calibrated",
    "validated against",
    "laboratory-equivalent",
    "certified",
    "proven accurate",
    "the mobility",
    "measured mobility",
    "accelerance of",
    "receptance of",
)


def codes(findings) -> list[str]:
    return [finding.code.value for finding in findings]


def make_config(**overrides) -> HardwareCampaignConfigV1:
    kwargs = {
        "campaign_id": "camp-1",
        "created_at": UTC_NOW,
        "operator_id": "operator-1",
        "interface_id": "iface-1",
        "sample_rate_hz": 48000,
        "excitation": build_rig_excitation_context(
            rig_configuration_id="rig-1", shaker_id="shaker-1", stinger_id="stinger-1"
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


def make_artifact(**overrides):
    kwargs = {
        "artifact_id": "art-1",
        "kind": "raw_audio",
        "sha256": artifact_digest(b"bytes"),
        "byte_count": 5,
        "media_type": "audio/wav",
        "storage_locator": "campaigns/camp-1/raw/001.wav",
        "capture_run_id": "r1",
    }
    kwargs.update(overrides)
    return build_external_artifact(**kwargs)


def make_hardware_run(
    run_id: str,
    value: float,
    *,
    witnessed_by: str | None = "operator-1",
    config: HardwareCampaignConfigV1 | None = None,
) -> PreliminaryExperimentRunV1:
    config = config or make_config()
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="e2",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.HARDWARE,
        source_artifact_ids=(f"campaigns/camp-1/{run_id}.json",),
        observed_features=(ObservedFeatureV1(TRANSFER_MAGNITUDE, UNIT, value),),
        acquisition=build_campaign_acquisition(
            config,
            session_id="sess-1",
            acquisition_id=f"acq-{run_id}",
            raw_artifact_ids=(f"art-{run_id}",),
            witnessed_by=witnessed_by,
        ),
        campaign_condition=CampaignConditionV1(
            ExperimentKind.FIXED_POINT, contact_configuration_id="att-1"
        ),
    )


def make_study(runs, **overrides) -> RepeatabilityStudyV1:
    config = make_config()
    kwargs = {
        "study_id": "study-e2",
        "experiment_definition": build_campaign_definition(
            config.experiments[0], config, created_at=UTC_NOW
        ),
        "generated_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.HARDWARE,
        "runs": tuple(runs),
    }
    kwargs.update(overrides)
    return RepeatabilityStudyV1(**kwargs)


class TestConfigurationMustBeStated:
    def test_a_complete_configuration_validates(self):
        assert validate_campaign_config(make_config()) == []

    def test_an_unidentified_rig_is_refused(self):
        config = make_config(
            excitation=build_rig_excitation_context(rig_configuration_id="")
        )
        assert "NSF-501" in codes(validate_campaign_config(config))

    def test_an_ambiguous_channel_pair_is_refused(self):
        # The transfer quantity's unit is derived from exactly one of each role.
        config = make_config(
            channels=(
                build_force_channel(channel_index=0, sensor_id="f1", unit="N"),
                build_force_channel(channel_index=1, sensor_id="f2", unit="N"),
                build_response_channel(channel_index=2, sensor_id="mic", unit="Pa"),
            )
        )
        assert "NSF-501" in codes(validate_campaign_config(config))

    def test_a_missing_force_channel_is_refused(self):
        # DO-103 §4.2: drive voltage alone is not a measured excitation.
        config = make_config(
            channels=(
                AcquisitionChannelV1(
                    0, AcquisitionRole.EXCITATION, "voltage", "V", "amp-1"
                ),
                build_response_channel(channel_index=1, sensor_id="mic", unit="Pa"),
            )
        )
        assert "NSF-501" in codes(validate_campaign_config(config))

    def test_a_reused_channel_index_is_refused(self):
        config = make_config(
            channels=(
                build_force_channel(channel_index=0, sensor_id="f", unit="N"),
                build_response_channel(channel_index=0, sensor_id="mic", unit="Pa"),
            )
        )
        assert "NSF-501" in codes(validate_campaign_config(config))

    def test_a_duplicate_experiment_is_refused(self):
        plan = make_config().experiments[0]
        config = make_config(experiments=(plan, plan))
        assert "NSF-501" in codes(validate_campaign_config(config))

    def test_too_few_planned_repeats_is_refused(self):
        config = make_config(
            experiments=(
                dataclasses.replace(
                    make_config().experiments[0], planned_repeat_count=1
                ),
            )
        )
        assert "NSF-202" in codes(validate_campaign_config(config))

    def test_a_rig_experiment_must_declare_the_rig_as_its_subject(self):
        # DO-103 §9: recording the rig in instrument_id is permitted, and only
        # where the record says that is what happened.
        config = make_config(
            experiments=(
                CampaignExperimentPlanV1(
                    experiment_id="e1",
                    kind=ExperimentKind.RIG_CHARACTERIZATION,
                    instrument_id="rig-1",
                    measurement_point_id="drive-point",
                    planned_repeat_count=5,
                ),
            )
        )
        assert "NSF-501" in codes(validate_campaign_config(config))

    def test_a_declared_rig_subject_validates_for_e1(self):
        config = make_config(
            experiments=(
                CampaignExperimentPlanV1(
                    experiment_id="e1",
                    kind=ExperimentKind.RIG_CHARACTERIZATION,
                    instrument_id="rig-1",
                    measurement_point_id="drive-point",
                    planned_repeat_count=5,
                    subject_is_rig=True,
                ),
            )
        )
        assert validate_campaign_config(config) == []

    def test_a_specimen_experiment_may_not_claim_the_rig_as_subject(self):
        config = make_config(
            experiments=(
                dataclasses.replace(make_config().experiments[0], subject_is_rig=True),
            )
        )
        assert "NSF-501" in codes(validate_campaign_config(config))


class TestCalibrationClaims:
    def test_an_unknown_calibration_produces_no_finding(self):
        channel = build_force_channel(channel_index=0, sensor_id="f", unit="N")
        assert validate_channel_calibration(channel) == []

    def test_a_nominal_sensitivity_produces_no_finding(self):
        channel = build_force_channel(
            channel_index=0,
            sensor_id="f",
            unit="N",
            sensitivity_value=10.2,
            sensitivity_unit="mV/N",
            calibration_traceability=CalibrationTraceability.NOMINAL,
        )
        assert validate_channel_calibration(channel) == []

    def test_a_traceable_claim_needs_a_reference(self):
        channel = build_force_channel(
            channel_index=0,
            sensor_id="f",
            unit="N",
            calibration_traceability=CalibrationTraceability.TRACEABLE,
        )
        assert codes(validate_channel_calibration(channel)) == ["NSF-510"]

    def test_a_referenced_traceable_claim_validates(self):
        channel = build_force_channel(
            channel_index=0,
            sensor_id="f",
            unit="N",
            calibration_traceability=CalibrationTraceability.TRACEABLE,
            calibration_reference="cert-2026-014",
        )
        assert validate_channel_calibration(channel) == []

    def test_a_half_recorded_sensitivity_is_refused(self):
        channel = build_force_channel(
            channel_index=0, sensor_id="f", unit="N", sensitivity_value=10.2
        )
        assert codes(validate_channel_calibration(channel)) == ["NSF-501"]

    def test_run_validation_carries_the_calibration_check(self):
        run = make_hardware_run("r1", 1.0)
        traceable = dataclasses.replace(
            run.acquisition.channels[0],
            calibration_traceability=CalibrationTraceability.TRACEABLE,
        )
        acquisition = dataclasses.replace(
            run.acquisition, channels=(traceable, run.acquisition.channels[1])
        )
        broken = dataclasses.replace(run, acquisition=acquisition)
        assert "NSF-510" in codes(validate_experiment_runs([broken]))


class TestArtifactIdentity:
    def test_a_well_formed_artifact_validates(self):
        assert validate_artifact_manifest([make_artifact()]) == []

    def test_a_digest_that_is_not_one_is_refused(self):
        assert codes(validate_artifact_manifest([make_artifact(sha256="abc")])) == [
            "NSF-508"
        ]

    def test_a_duplicate_artifact_is_refused(self):
        artifact = make_artifact()
        assert "NSF-508" in codes(validate_artifact_manifest([artifact, artifact]))

    @pytest.mark.parametrize(
        "locator", ["/home/op/captures/001.wav", "D:/captures/001.wav", "\\\\nas\\raw"]
    )
    def test_a_host_path_is_not_a_durable_identity(self, locator):
        findings = validate_artifact_manifest([make_artifact(storage_locator=locator)])
        assert codes(findings) == ["NSF-509"]

    def test_a_local_path_hint_stays_permitted(self):
        # The hint is ephemeral acquisition metadata; the digest is the identity.
        artifact = make_artifact(local_path_hint="D:/captures/001.wav")
        assert validate_artifact_manifest([artifact]) == []

    def test_a_run_may_not_retain_an_artifact_the_manifest_lacks(self):
        run = make_hardware_run("r1", 1.0)
        findings = validate_artifact_manifest([], runs=[run])
        assert codes(findings) == ["NSF-401"]

    def test_a_covered_run_validates(self):
        run = make_hardware_run("r1", 1.0)
        findings = validate_artifact_manifest(
            [make_artifact(artifact_id="art-r1")], runs=[run]
        )
        assert findings == []


class TestCampaignAccounting:
    def make_record(self, **overrides):
        kwargs = {
            "config": make_config(),
            "generated_at": UTC_NOW,
            "execution_status": CampaignExecutionStatus.NOT_EXECUTED,
        }
        kwargs.update(overrides)
        return build_campaign_record(**kwargs)

    def test_a_planned_but_unrun_campaign_validates(self):
        assert validate_campaign_record(self.make_record()) == []

    def test_an_executed_experiment_must_name_its_study(self):
        record = self.make_record(
            execution_status=CampaignExecutionStatus.EXECUTED,
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.EXECUTED,
                ),
            ),
        )
        assert "NSF-501" in codes(validate_campaign_record(record))

    def test_a_blocked_experiment_must_name_the_gate(self):
        record = self.make_record(
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.BLOCKED_BY_GATE,
                ),
            ),
        )
        assert "NSF-501" in codes(validate_campaign_record(record))

    def test_a_blocked_experiment_naming_its_gate_validates(self):
        record = self.make_record(
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.BLOCKED_BY_GATE,
                    blocked_by_experiment_id="e1",
                ),
            ),
        )
        assert validate_campaign_record(record) == []

    def test_a_blocked_experiment_is_stated_in_the_limitations(self):
        record = self.make_record(
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.BLOCKED_BY_GATE,
                    blocked_by_experiment_id="e1",
                ),
            ),
        )
        assert any("earlier campaign gate failed" in t for t in record.limitations)

    def test_an_outcome_for_an_unplanned_experiment_is_refused(self):
        record = self.make_record(
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e9",
                    kind=ExperimentKind.RECIPROCITY,
                    status=CampaignExecutionStatus.NOT_EXECUTED,
                ),
            ),
        )
        assert "NSF-501" in codes(validate_campaign_record(record))

    def test_a_not_executed_campaign_may_not_carry_an_executed_experiment(self):
        record = self.make_record(
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.EXECUTED,
                    study_id="study-e2",
                ),
            ),
        )
        assert "NSF-501" in codes(validate_campaign_record(record))

    def test_an_executed_campaign_must_have_executed_something(self):
        record = self.make_record(execution_status=CampaignExecutionStatus.EXECUTED)
        assert "NSF-501" in codes(validate_campaign_record(record))


class TestWitnessedSessionsAndPromotion:
    def test_a_fixture_study_can_never_be_witnessed(self):
        run = dataclasses.replace(
            make_hardware_run("r1", 1.0),
            evidence_origin=EvidenceOrigin.FIXTURE,
            acquisition=None,
        )
        study = make_study([run], evidence_origin=EvidenceOrigin.FIXTURE)
        assert codes(validate_witnessed_hardware_session(study)) == ["NSF-307"]

    def test_hardware_origin_alone_is_not_witnessed(self):
        study = make_study([make_hardware_run("r1", 1.0, witnessed_by=None)])
        assert codes(validate_witnessed_hardware_session(study)) == ["NSF-307"]

    def test_one_unattributed_run_breaks_the_session(self):
        study = make_study(
            [
                make_hardware_run("r1", 1.0),
                make_hardware_run("r2", 1.1, witnessed_by=None),
            ]
        )
        assert codes(validate_witnessed_hardware_session(study)) == ["NSF-307"]

    def test_a_fully_attributed_hardware_study_is_witnessed(self):
        study = make_study([make_hardware_run("r1", 1.0), make_hardware_run("r2", 1.1)])
        assert validate_witnessed_hardware_session(study) == []

    def test_the_report_promotes_nothing_even_from_a_witnessed_session(self):
        study = make_study([make_hardware_run("r1", 1.0), make_hardware_run("r2", 1.1)])
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.EXECUTED,
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.EXECUTED,
                    study_id=study.study_id,
                ),
            ),
        )
        markdown = render_campaign_report(record, [study])
        assert "This report promotes nothing" in markdown
        assert "remains a separate, per-capability" in markdown

    def test_a_campaign_without_a_witnessed_session_says_so(self):
        study = make_study([make_hardware_run("r1", 1.0, witnessed_by=None)])
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.EXECUTED,
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.EXECUTED,
                    study_id=study.study_id,
                ),
            ),
        )
        markdown = render_campaign_report(record, [study])
        assert "no capability is eligible for promotion" in markdown


class TestTheRendererRefusesWhatTheValidatorWould:
    def make_record(self, study_id="study-e2"):
        return build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.EXECUTED,
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.EXECUTED,
                    study_id=study_id,
                ),
            ),
        )

    def unbacked_study(self):
        run = PreliminaryExperimentRunV1(
            run_id="r1",
            experiment_id="e2",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.HARDWARE,
            source_artifact_ids=("campaigns/camp-1/r1.json",),
            observed_features=(ObservedFeatureV1(TRANSFER_MAGNITUDE, UNIT, 1.0),),
        )
        return make_study([run])

    def test_an_unbacked_hardware_study_is_not_rendered(self):
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            render_campaign_report(self.make_record(), [self.unbacked_study()])
        assert excinfo.value.code.value == "NSF-306"

    def test_an_unbacked_hardware_study_is_not_serialized(self):
        with pytest.raises(RepeatabilityStatisticsError):
            build_campaign_report(self.make_record(), [self.unbacked_study()])

    def test_a_mislabelled_study_is_not_rendered(self):
        study = make_study(
            [make_hardware_run("r1", 1.0)], evidence_origin=EvidenceOrigin.FIXTURE
        )
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            render_campaign_report(self.make_record(), [study])
        assert excinfo.value.code.value == "NSF-305"


class TestCampaignReport:
    def make(self):
        return build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.NOT_EXECUTED,
        )

    def test_a_not_executed_campaign_says_so_in_its_title(self):
        assert render_campaign_report(self.make()).startswith(
            "# Hardware Measurement Campaign (Not Executed)"
        )

    def test_a_not_executed_campaign_carries_the_banner(self):
        markdown = render_campaign_report(self.make())
        assert "**This campaign has not been executed.**" in markdown
        assert "supports no hardware claim of any kind" in markdown

    def test_an_executed_fixture_campaign_is_not_read_as_hardware(self):
        study = make_study(
            [
                dataclasses.replace(
                    make_hardware_run(f"r{i}", 1.0 + i / 100),
                    evidence_origin=EvidenceOrigin.FIXTURE,
                    acquisition=None,
                )
                for i in (1, 2)
            ],
            evidence_origin=EvidenceOrigin.FIXTURE,
        )
        record = build_campaign_record(
            config=make_config(),
            generated_at=UTC_NOW,
            execution_status=CampaignExecutionStatus.EXECUTED,
            outcomes=(
                CampaignExperimentOutcomeV1(
                    experiment_id="e2",
                    kind=ExperimentKind.FIXED_POINT,
                    status=CampaignExecutionStatus.EXECUTED,
                    study_id=study.study_id,
                ),
            ),
        )
        markdown = render_campaign_report(record, [study])
        assert "**No hardware evidence.**" in markdown
        assert "FIXTURE data" in markdown

    def test_the_report_states_reference_agreement_remains_open(self):
        assert "R10 reference-method agreement remains entirely open" in (
            render_campaign_report(self.make())
        )

    def test_the_report_never_names_the_quantity_as_a_mechanical_frf(self):
        markdown = render_campaign_report(self.make()).lower()
        assert "it is not mobility, accelerance, or receptance" in markdown
        # Every occurrence is inside a sentence that rules the name out. The
        # word appearing is fine; the quantity being *called* one is not.
        for line in markdown.splitlines():
            if any(name in line for name in ("mobility", "accelerance", "receptance")):
                assert "not mobility" in line

    def test_the_report_marks_unknown_fields_as_unknown(self):
        markdown = render_campaign_report(self.make())
        assert "| Contact tip | unknown |" in markdown

    def test_the_report_marks_observed_fields_as_observed(self):
        markdown = render_campaign_report(self.make())
        assert "| Stinger | stinger-1 (observed) |" in markdown

    def test_the_report_derives_the_transfer_unit_from_the_channels(self):
        assert "Derived transfer unit: **Pa/N**" in render_campaign_report(self.make())

    def test_the_report_separates_measured_from_traceable(self):
        assert "Measured is not traceable" in render_campaign_report(self.make())

    @pytest.mark.parametrize("phrase", FORBIDDEN_PHRASES)
    def test_the_generated_report_avoids_overclaiming_language(self, phrase):
        markdown = render_campaign_report(self.make()).lower()
        assert phrase not in markdown

    def test_the_report_is_deterministic(self):
        first = render_campaign_report(self.make())
        second = render_campaign_report(self.make())
        assert first == second

    def test_the_json_report_carries_a_digest_of_its_own_campaign(self):
        from tap_tone_pi.grant_readiness.validation import evidence_digest

        record = self.make()
        payload = build_campaign_report(record)
        assert payload["campaign_digest"] == evidence_digest(record.to_dict())

    def test_the_json_report_is_canonical(self):
        payload = build_campaign_report(self.make())
        assert canonical_json(payload) == canonical_json(payload)

    def test_the_json_report_states_the_execution_status(self):
        payload = build_campaign_report(self.make())
        assert payload["execution_status"] == "NOT_EXECUTED"
        assert payload["is_executed"] is False
