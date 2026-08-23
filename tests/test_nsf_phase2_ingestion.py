"""Phase 2 transfer-function ingestion into grant evidence (DO-103 §5.1).

DO-102 read the Phase 1 tap path. DO-103 brings Phase 2 alongside it because a
contact-driven rig is a driven input/output measurement, and reducing one to
scalar peaks would throw away coherence at exactly the moment the rig is least
trusted.

These tests hold the ingestion contract: what is read, at which frequency,
which malformed or incomplete documents become rejected runs rather than
silently-good ones, and that a rejected attempt keeps everything that makes it
accountable. They are written before any instrument data exists, which is the
point — DO-103 §13 Stage 3 requires this path to be settled before the campaign
runs, so the campaign is not analyzed by software shaped to fit its results.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness import (
    MECHANICAL_FRF_NAMES,
    AcquisitionChannelV1,
    AcquisitionProvenanceV1,
    AcquisitionRole,
    EnvironmentalContextV1,
    EvidenceOrigin,
    ExcitationContextV1,
    GrantReadinessErrorCode,
    RejectionReason,
)
from tap_tone_pi.grant_readiness.errors import ExperimentRecordError
from tap_tone_pi.grant_readiness.experiment import (
    build_preliminary_experiment,
    build_repeatability_study,
    record_missing_run,
)
from tap_tone_pi.grant_readiness.phase2_experiment import (
    COHERENCE,
    FREQUENCY_OFFSET,
    NOMINAL_EVALUATION_FREQUENCY,
    DEFAULT_TRANSFER_UNIT,
    EVALUATION_FREQUENCY,
    PHASE2_SCHEMA_VERSION,
    TRANSFER_MAGNITUDE,
    TRANSFER_PHASE,
    load_phase2_transfer,
    record_phase2_run,
    summarized_phase2_quantities,
    transfer_unit_for,
)
from tap_tone_pi.grant_readiness.validation import (
    validate_repeatability_study,
    validate_transfer_quantity_naming,
)

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC_NOW = "2026-08-19T12:00:00+00:00"

FREQUENCIES = [100.0, 200.0, 300.0, 400.0]


def make_document(**overrides) -> dict:
    """A minimal ``phase2_ods_snapshot_v2`` document with one measured point."""
    point = {
        "point_id": "P1",
        "x_mm": 10.0,
        "y_mm": 20.0,
        "H_mag": [0.001, 0.004, 0.002, 0.0015],
        "H_phase_deg": [-5.0, -30.0, -120.0, -160.0],
        "coherence": [0.80, 0.97, 0.95, 0.60],
        "n_averages": 8,
    }
    point.update(overrides.pop("point", {}))
    document = {
        "schema_version": PHASE2_SCHEMA_VERSION,
        "capdir": "runs_phase2/2026-08-19T12-00-00",
        "freqs_hz": list(FREQUENCIES),
        "points": [point],
        "provenance": {
            "algo_id": "phase2_transfer_coherence",
            "algo_version": "1.0.0",
            "numpy_version": "1.26.4",
            "scipy_version": "1.13.0",
            "computed_at_utc": "2026-08-19T13:00:00+00:00",
        },
    }
    document.update(overrides)
    return document


def make_acquisition(**overrides) -> AcquisitionProvenanceV1:
    kwargs = {
        "session_id": "session-e2",
        "acquisition_id": "acq-001",
        "interface_id": "interface-001",
        "sample_rate_hz": 48000,
        "channels": (
            AcquisitionChannelV1(
                channel_index=0,
                role=AcquisitionRole.EXCITATION,
                quantity="force",
                unit="N",
                sensor_id="force-transducer-1",
            ),
            AcquisitionChannelV1(
                channel_index=1,
                role=AcquisitionRole.RESPONSE,
                quantity="acoustic_pressure",
                unit="Pa",
                sensor_id="mic-1",
            ),
        ),
        "excitation_device_id": "shaker-1",
        "raw_artifact_ids": ("runs_phase2/session-e2/run-001.wav",),
        "witnessed_by": "operator-1",
    }
    kwargs.update(overrides)
    return AcquisitionProvenanceV1(**kwargs)


def record(document, **overrides):
    kwargs = {
        "run_id": "run-001",
        "experiment_id": "exp-e2",
        "measurement_point_id": "P1",
        "evaluation_frequency_hz": 200.0,
        "captured_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.FIXTURE,
        "source_artifact_ids": ("runs_phase2/session-e2/run-001.wav",),
    }
    kwargs.update(overrides)
    return record_phase2_run(document, **kwargs)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


class TestLoadPhase2Transfer:
    def test_reads_a_document(self, tmp_path):
        path = tmp_path / "ods.json"
        path.write_text(json.dumps(make_document()), encoding="utf-8")
        assert load_phase2_transfer(path)["schema_version"] == PHASE2_SCHEMA_VERSION

    def test_missing_file_is_nsf_204(self, tmp_path):
        with pytest.raises(ExperimentRecordError) as exc:
            load_phase2_transfer(tmp_path / "absent.json")
        assert exc.value.code is GrantReadinessErrorCode.SOURCE_ARTIFACT_MISSING

    def test_unparseable_document_is_nsf_201(self, tmp_path):
        path = tmp_path / "ods.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ExperimentRecordError) as exc:
            load_phase2_transfer(path)
        assert exc.value.code is GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION

    def test_a_json_array_is_not_a_document(self, tmp_path):
        path = tmp_path / "ods.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(ExperimentRecordError):
            load_phase2_transfer(path)

    def test_the_error_never_carries_a_host_path(self, tmp_path):
        path = tmp_path / "ods.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ExperimentRecordError) as exc:
            load_phase2_transfer(path)
        assert str(tmp_path) not in str(exc.value)
        assert str(tmp_path) not in json.dumps(exc.value.to_dict())


# ---------------------------------------------------------------------------
# What a valid run records
# ---------------------------------------------------------------------------


class TestValidRun:
    def test_records_the_quantities_the_document_supports(self):
        run = record(make_document())
        assert run.valid
        assert run.rejection_reason is None
        assert [feature.quantity for feature in run.observed_features] == [
            EVALUATION_FREQUENCY,
            NOMINAL_EVALUATION_FREQUENCY,
            FREQUENCY_OFFSET,
            TRANSFER_MAGNITUDE,
            TRANSFER_PHASE,
            COHERENCE,
        ]

    def test_the_frequency_asked_for_survives_beside_the_bin_that_answered(self):
        # DO-105 §4.7: a study of repeated runs must be able to show that they
        # all asked the same question and were answered at slightly different
        # frequencies. Discarding the request made that unshowable.
        run = record(make_document(), evaluation_frequency_hz=205.0)
        assert run.feature(NOMINAL_EVALUATION_FREQUENCY).value == 205.0
        assert run.feature(EVALUATION_FREQUENCY).value == 200.0
        assert run.feature(FREQUENCY_OFFSET).value == pytest.approx(-5.0)

    def test_the_offset_is_signed(self):
        # Which side of the request the bin fell on is information.
        run = record(make_document(), evaluation_frequency_hz=195.0)
        assert run.feature(FREQUENCY_OFFSET).value == pytest.approx(5.0)

    def test_an_exact_hit_records_a_zero_offset_not_a_missing_one(self):
        run = record(make_document(), evaluation_frequency_hz=200.0)
        assert run.feature(FREQUENCY_OFFSET).value == 0.0

    def test_the_acquisition_order_survives_ingestion(self):
        # The valid path and the rejected path both carry it. A field the
        # ingestion silently drops is worse than no field: the manifest would
        # record an order that never reaches the evidence.
        assert record(make_document(), sequence_index=4).sequence_index == 4

    def test_a_rejected_run_keeps_its_place_in_the_order(self):
        rejected = record(
            make_document(schema_version="phase2_ods_snapshot_v1"), sequence_index=4
        )
        assert not rejected.valid
        assert rejected.sequence_index == 4

    def test_an_unordered_acquisition_stays_unordered(self):
        assert record(make_document()).sequence_index is None

    def test_the_offset_is_not_summarized(self):
        # Its mean is zero whenever every run landed on its requested bin, and a
        # coefficient of variation over a zero mean is undefined — summarizing it
        # would turn the best possible outcome into an error.
        assert FREQUENCY_OFFSET not in {
            quantity for quantity, _ in summarized_phase2_quantities()
        }

    def test_reads_the_values_at_the_evaluation_frequency(self):
        run = record(make_document())
        assert run.feature(TRANSFER_MAGNITUDE).value == 0.004
        assert run.feature(TRANSFER_PHASE).value == -30.0
        assert run.feature(COHERENCE).value == 0.97

    def test_the_bin_frequency_is_recorded_not_the_request(self):
        # A reader sees where the value was actually read, rather than trusting
        # that the request and the bin coincided.
        run = record(make_document(), evaluation_frequency_hz=215.0)
        assert run.feature(EVALUATION_FREQUENCY).value == 200.0
        assert run.feature(TRANSFER_MAGNITUDE).value == 0.004

    def test_the_nearest_bin_is_selected(self):
        run = record(make_document(), evaluation_frequency_hz=260.0)
        assert run.feature(EVALUATION_FREQUENCY).value == 300.0
        assert run.feature(COHERENCE).value == 0.95

    def test_a_request_on_the_range_boundary_is_read(self):
        run = record(make_document(), evaluation_frequency_hz=100.0)
        assert run.feature(EVALUATION_FREQUENCY).value == 100.0

    def test_conditions_are_recorded_as_supplied(self):
        run = record(
            make_document(), conditions=EnvironmentalContextV1(temp_c=21.5, rh_pct=45.0)
        )
        assert run.conditions.temp_c == 21.5

    def test_unknown_conditions_stay_unknown(self):
        assert record(make_document()).conditions.is_fully_unknown

    def test_a_non_utc_capture_time_is_refused(self):
        with pytest.raises(ExperimentRecordError) as exc:
            record(make_document(), captured_at="2026-08-19T12:00:00")
        assert exc.value.code is GrantReadinessErrorCode.TIMESTAMP_NOT_UTC


class TestTransferUnitIsDerived:
    def test_a_microphone_over_a_measured_force_is_pa_per_newton(self):
        run = record(
            make_document(),
            evidence_origin=EvidenceOrigin.HARDWARE,
            acquisition=make_acquisition(),
        )
        assert run.feature(TRANSFER_MAGNITUDE).unit == "Pa/N"

    def test_without_acquisition_the_ratio_is_unitless(self):
        # H is response over reference in whatever the document's own terms
        # were. Calling that Pa/N would assert a force channel that nothing
        # recorded.
        assert record(make_document()).feature(TRANSFER_MAGNITUDE).unit == (
            DEFAULT_TRANSFER_UNIT
        )

    def test_an_ambiguous_channel_pair_yields_no_unit_claim(self):
        two_responses = make_acquisition(
            channels=(
                AcquisitionChannelV1(
                    channel_index=0,
                    role=AcquisitionRole.RESPONSE,
                    quantity="acoustic_pressure",
                    unit="Pa",
                    sensor_id="mic-1",
                ),
                AcquisitionChannelV1(
                    channel_index=1,
                    role=AcquisitionRole.RESPONSE,
                    quantity="acoustic_pressure",
                    unit="Pa",
                    sensor_id="mic-2",
                ),
            )
        )
        assert transfer_unit_for(two_responses) == DEFAULT_TRANSFER_UNIT

    def test_summarized_quantities_carry_the_unit(self):
        quantities = summarized_phase2_quantities("Pa/N")
        assert (TRANSFER_MAGNITUDE, "Pa/N") in quantities
        assert (COHERENCE, "unitless") in quantities


class TestQuantityIsNotAMechanicalFrf:
    def test_no_recorded_name_is_a_mechanical_frequency_response(self):
        # DO-103 §6.6 rule 1, asked of the data rather than the prose.
        run = record(
            make_document(),
            evidence_origin=EvidenceOrigin.HARDWARE,
            acquisition=make_acquisition(),
        )
        for feature in run.observed_features:
            lowered = feature.quantity.lower()
            assert not any(name in lowered for name in MECHANICAL_FRF_NAMES)

    def test_the_recorded_run_passes_the_naming_validator(self):
        run = record(
            make_document(),
            evidence_origin=EvidenceOrigin.HARDWARE,
            acquisition=make_acquisition(),
        )
        assert validate_transfer_quantity_naming(run) == []


# ---------------------------------------------------------------------------
# Rejection
# ---------------------------------------------------------------------------


class TestRejection:
    def test_a_foreign_contract_is_invalid_metadata(self):
        run = record(make_document(schema_version="phase1_tap_analysis_v1"))
        assert not run.valid
        assert run.rejection_reason is RejectionReason.INVALID_METADATA

    @pytest.mark.parametrize("freqs", [[], "wide", [1.0, "two"], [float("nan")], None])
    def test_an_unusable_frequency_axis_is_invalid_metadata(self, freqs):
        run = record(make_document(freqs_hz=freqs))
        assert run.rejection_reason is RejectionReason.INVALID_METADATA

    def test_a_missing_point_is_an_analysis_failure(self):
        # The document is well-formed; it simply produced nothing for the point
        # this experiment is centred on.
        run = record(make_document(), measurement_point_id="P9")
        assert run.rejection_reason is RejectionReason.ANALYSIS_FAILURE

    def test_a_document_with_no_points_is_an_analysis_failure(self):
        run = record(make_document(points=[]))
        assert run.rejection_reason is RejectionReason.ANALYSIS_FAILURE

    @pytest.mark.parametrize("key", ["H_mag", "H_phase_deg"])
    def test_an_unusable_transfer_array_is_invalid_metadata(self, key):
        run = record(make_document(point={key: None}))
        assert run.rejection_reason is RejectionReason.INVALID_METADATA

    def test_absent_coherence_is_invalid_metadata(self):
        # §5.1 chose Phase 2 because coherence travels with the transfer
        # function. Recording a driven run without its own trust metric would
        # keep the number and discard the reason to believe it.
        run = record(make_document(point={"coherence": None}))
        assert run.rejection_reason is RejectionReason.INVALID_METADATA

    def test_a_length_mismatch_is_invalid_metadata(self):
        run = record(make_document(point={"H_mag": [0.001, 0.004]}))
        assert run.rejection_reason is RejectionReason.INVALID_METADATA

    @pytest.mark.parametrize("requested", [40.0, 2000.0, float("nan")])
    def test_a_frequency_outside_the_result_is_an_analysis_failure(self, requested):
        # Snapping to an edge bin would report a number from a frequency nobody
        # asked about, as though it answered the question.
        run = record(make_document(), evaluation_frequency_hz=requested)
        assert run.rejection_reason is RejectionReason.ANALYSIS_FAILURE

    def test_a_rejected_run_observes_nothing(self):
        run = record(make_document(), measurement_point_id="P9")
        assert run.observed_features == ()

    def test_a_rejected_run_keeps_its_identity_and_provenance(self):
        # DO-103 §6.7: a failed run stays, with everything that makes it
        # accountable. A campaign that reports only its successes is not
        # evidence.
        acquisition = make_acquisition()
        run = record(
            make_document(),
            measurement_point_id="P9",
            evidence_origin=EvidenceOrigin.HARDWARE,
            acquisition=acquisition,
        )
        assert run.run_id == "run-001"
        assert run.source_artifact_ids == ("runs_phase2/session-e2/run-001.wav",)
        assert run.acquisition == acquisition
        assert run.evidence_origin is EvidenceOrigin.HARDWARE

    def test_a_capture_that_produced_no_file_is_still_an_attempt(self):
        # The Phase 2 path has no separate record for this: DO-102's
        # record_missing_run already covers it and is reused unchanged.
        run = record_missing_run(
            run_id="run-004",
            experiment_id="exp-e2",
            evidence_origin=EvidenceOrigin.FIXTURE,
            captured_at=UTC_NOW,
        )
        assert run.rejection_reason is RejectionReason.MISSING_ARTIFACT

    def test_the_document_can_only_support_the_reasons_it_records(self):
        # Stated rather than left implicit. A Phase 2 transfer document carries
        # no quality gate, so this path cannot produce CLIPPING,
        # INSUFFICIENT_SIGNAL, or QUALITY_GATE_REJECTED — those are Phase 1
        # gate verdicts. An operator rejecting a driven capture for one of them
        # records it by constructing the rejected run directly, which the
        # DO-102 contract already supports; inferring a cause the evidence does
        # not name would be a guess.
        producible = {
            record(make_document(schema_version="other")).rejection_reason,
            record(make_document(), measurement_point_id="P9").rejection_reason,
        }
        assert producible == {
            RejectionReason.INVALID_METADATA,
            RejectionReason.ANALYSIS_FAILURE,
        }


# ---------------------------------------------------------------------------
# End to end: a study built from the Phase 2 path
# ---------------------------------------------------------------------------


def make_definition():
    return build_preliminary_experiment(
        experiment_id="exp-e2",
        instrument_id="guitar-top-A",
        measurement_point_id="P1",
        operator_id="operator-1",
        planned_repeat_count=10,
        created_at=UTC_NOW,
        analysis_profile=PHASE2_SCHEMA_VERSION,
        excitation=ExcitationContextV1(
            excitation_method="shaker_stinger",
            excitation_device_id="shaker-1",
            contact_condition="1.0 mm x 40 mm steel stinger, threaded both ends",
            fixture_id="bench-mount-A, independent ground path",
        ),
    )


def make_runs(count: int = 3, *, hardware: bool, acquisition=None):
    runs = []
    for index in range(count):
        document = make_document(
            point={"H_mag": [0.001, 0.004 + index * 0.0001, 0.002, 0.0015]}
        )
        runs.append(
            record(
                document,
                run_id=f"run-{index + 1:03d}",
                evidence_origin=(
                    EvidenceOrigin.HARDWARE if hardware else EvidenceOrigin.FIXTURE
                ),
                acquisition=acquisition,
            )
        )
    return runs


class TestStudyFromPhase2Runs:
    def test_a_fixture_study_summarizes_the_phase2_quantities(self):
        study = build_repeatability_study(
            study_id="study-e2-fixture",
            definition=make_definition(),
            runs=make_runs(hardware=False),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            quantities=summarized_phase2_quantities(),
        )
        assert validate_repeatability_study(study) == []
        assert {metric.quantity for metric in study.metrics} == {
            EVALUATION_FREQUENCY,
            NOMINAL_EVALUATION_FREQUENCY,
            TRANSFER_MAGNITUDE,
            TRANSFER_PHASE,
            COHERENCE,
        }

    def test_a_fixture_study_says_it_is_not_hardware_evidence(self):
        study = build_repeatability_study(
            study_id="study-e2-fixture",
            definition=make_definition(),
            runs=make_runs(hardware=False),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            quantities=summarized_phase2_quantities(),
        )
        assert any("FIXTURE data" in text for text in study.limitations)

    def test_a_hardware_study_needs_provenance_on_every_run(self):
        with pytest.raises(ExperimentRecordError) as exc:
            build_repeatability_study(
                study_id="study-e2",
                definition=make_definition(),
                runs=make_runs(hardware=True),
                generated_at=UTC_NOW,
                evidence_origin=EvidenceOrigin.HARDWARE,
                quantities=summarized_phase2_quantities(),
            )
        assert exc.value.code is (
            GrantReadinessErrorCode.HARDWARE_PROVENANCE_INCOMPLETE
        )

    def test_a_backed_hardware_study_validates_and_persists(self):
        acquisition = make_acquisition()
        study = build_repeatability_study(
            study_id="study-e2",
            definition=make_definition(),
            runs=make_runs(hardware=True, acquisition=acquisition),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.HARDWARE,
            quantities=summarized_phase2_quantities(acquisition.transfer_unit),
        )
        assert validate_repeatability_study(study) == []

        schema = json.loads(
            (
                REPO_ROOT
                / "contracts"
                / "ttp_preliminary_repeatability_study_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.validate(study.to_dict(), schema)

    def test_the_study_reports_the_derived_unit(self):
        acquisition = make_acquisition()
        study = build_repeatability_study(
            study_id="study-e2",
            definition=make_definition(),
            runs=make_runs(hardware=True, acquisition=acquisition),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.HARDWARE,
            quantities=summarized_phase2_quantities(acquisition.transfer_unit),
        )
        magnitude = next(
            metric for metric in study.metrics if metric.quantity == TRANSFER_MAGNITUDE
        )
        assert magnitude.unit == "Pa/N"

    def test_the_phase1_path_is_unchanged_by_this_one(self):
        # DO-103 §5.1: Phase 2 is added alongside Phase 1, not in place of it.
        from tap_tone_pi.grant_readiness.experiment import (
            PHASE1_SCHEMA_VERSION,
            SUMMARIZED_QUANTITIES,
        )

        assert PHASE1_SCHEMA_VERSION == "phase1_tap_analysis_v1"
        assert ("dominant_frequency", "Hz") in SUMMARIZED_QUANTITIES
