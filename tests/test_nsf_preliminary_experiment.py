"""Preliminary repeatability analysis path (DO-102, Commit 6).

Exercises the ingestion of phase1_tap_analysis_v1 results into a bounded study.
All data here is deterministic fixture data, constructed in-test and labelled
FIXTURE. None of it is hardware evidence and none of it may be reported as such.
"""

from __future__ import annotations

import json

import pytest

from tap_tone_pi.grant_readiness import (
    EnvironmentalContextV1,
    EvidenceOrigin,
    ExcitationContextV1,
    GrantReadinessErrorCode,
    RejectionReason,
)
from tap_tone_pi.grant_readiness.errors import ExperimentRecordError
from tap_tone_pi.grant_readiness.experiment import (
    PHASE1_SCHEMA_VERSION,
    SUMMARIZED_QUANTITIES,
    build_preliminary_experiment,
    build_repeatability_study,
    default_study_limitations,
    load_phase1_analysis,
    record_experiment_run,
    record_missing_run,
)

jsonschema = pytest.importorskip("jsonschema")

UTC_NOW = "2026-08-09T12:00:00+00:00"


def phase1_payload(
    *,
    dominant_hz: float | None = 245.0,
    magnitude: float = 0.82,
    snr_db: float = 31.0,
    confidence: float = 0.91,
    clipped: bool = False,
    rms: float = 0.12,
    verdict: str = "pass",
    triggered_rules: list | None = None,
    demo: bool = False,
    temp_c: float | None = 21.5,
    rh_pct: float | None = 44.0,
) -> dict:
    """A deterministic phase1_tap_analysis_v1 document. Fixture data only."""
    peaks = []
    if dominant_hz is not None:
        peaks = [
            {"freq_hz": dominant_hz, "magnitude": magnitude},
            {"freq_hz": dominant_hz * 2.0, "magnitude": magnitude * 0.5},
        ]
    payload = {
        "schema_version": PHASE1_SCHEMA_VERSION,
        "timestamp_utc": UTC_NOW,
        "sample_rate": 48000,
        "duration_s": 2.5,
        "demo": demo,
        "analysis": {
            "dominant_hz": dominant_hz,
            "peaks": peaks,
            "clipped": clipped,
            "rms": rms,
            "confidence": confidence,
            "confidence_components": {"snr_db": snr_db},
        },
        "quality": {
            "verdict": verdict,
            "policy_version": "quality_policy_v1",
            "triggered_rules": triggered_rules or [],
        },
        "provenance": {
            "audio_sha256": "a" * 64,
            "environment": {"temp_c": temp_c, "rh_pct": rh_pct},
        },
    }
    return payload


def hard_rule(rule_id: str) -> dict:
    return {"rule_id": rule_id, "severity": "hard", "message": "m"}


def make_definition(**overrides):
    kwargs = {
        "experiment_id": "exp-001",
        "instrument_id": "guitar-top-A",
        "measurement_point_id": "P1",
        "operator_id": "op-1",
        "planned_repeat_count": 10,
        "created_at": UTC_NOW,
    }
    kwargs.update(overrides)
    return build_preliminary_experiment(**kwargs)


def record(run_id: str, payload: dict, **overrides):
    kwargs = {
        "run_id": run_id,
        "experiment_id": "exp-001",
        "evidence_origin": EvidenceOrigin.FIXTURE,
        "source_artifact_ids": (f"wav-{run_id}",),
    }
    kwargs.update(overrides)
    return record_experiment_run(payload, **kwargs)


# ---------------------------------------------------------------------------
# Definition
# ---------------------------------------------------------------------------


class TestBuildPreliminaryExperiment:
    def test_builds_a_bounded_experiment(self):
        definition = make_definition()
        assert definition.experiment_id == "exp-001"
        assert definition.analysis_profile == PHASE1_SCHEMA_VERSION

    def test_zero_repeats_rejected(self):
        with pytest.raises(ExperimentRecordError) as exc:
            make_definition(planned_repeat_count=0)
        assert exc.value.code is GrantReadinessErrorCode.INSUFFICIENT_REPEAT_COUNT

    def test_missing_measurement_point_rejected(self):
        with pytest.raises(ExperimentRecordError) as exc:
            make_definition(measurement_point_id="  ")
        assert exc.value.code is GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION

    def test_non_utc_timestamp_rejected(self):
        with pytest.raises(ExperimentRecordError) as exc:
            make_definition(created_at="2026-08-09T12:00:00")
        assert exc.value.code is GrantReadinessErrorCode.TIMESTAMP_NOT_UTC

    def test_excitation_defaults_to_unspecified(self):
        assert make_definition().excitation.excitation_method == "unspecified"

    def test_shaker_excitation_is_recordable_today(self):
        # The contract must already carry the grounded shaker architecture
        # without the hardware program existing.
        definition = make_definition(
            excitation=ExcitationContextV1(
                excitation_method="shaker_stinger",
                excitation_device_id="shaker-01",
                excitation_point="bridge, treble side",
                contact_condition="stinger, 2mm nylon",
                fixture_id="fx-3",
                excitation_contract_id="exc-777",
            )
        )
        assert definition.excitation.excitation_method == "shaker_stinger"
        assert definition.excitation.is_known_method

    def test_unknown_environment_is_accepted(self):
        assert make_definition().environmental_context.is_fully_unknown


# ---------------------------------------------------------------------------
# Reading a result
# ---------------------------------------------------------------------------


class TestLoadPhase1Analysis:
    def test_reads_a_document(self, tmp_path):
        path = tmp_path / "analysis.json"
        path.write_text(json.dumps(phase1_payload()), encoding="utf-8")
        assert load_phase1_analysis(path)["schema_version"] == PHASE1_SCHEMA_VERSION

    def test_missing_file_is_a_missing_artifact(self, tmp_path):
        with pytest.raises(ExperimentRecordError) as exc:
            load_phase1_analysis(tmp_path / "absent.json")
        assert exc.value.code is GrantReadinessErrorCode.SOURCE_ARTIFACT_MISSING

    def test_malformed_json_rejected(self, tmp_path):
        path = tmp_path / "analysis.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ExperimentRecordError) as exc:
            load_phase1_analysis(path)
        assert exc.value.code is GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION

    def test_non_object_document_rejected(self, tmp_path):
        path = tmp_path / "analysis.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ExperimentRecordError):
            load_phase1_analysis(path)

    def test_error_context_carries_no_host_path(self, tmp_path):
        with pytest.raises(ExperimentRecordError) as exc:
            load_phase1_analysis(tmp_path / "absent.json")
        assert exc.value.context["artifact"] == "absent.json"
        assert str(tmp_path) not in json.dumps(exc.value.to_dict())


# ---------------------------------------------------------------------------
# Recording runs
# ---------------------------------------------------------------------------


class TestRecordValidRun:
    def test_valid_run_observes_every_summarized_quantity(self):
        run = record("run-001", phase1_payload())
        assert run.valid
        assert run.rejection_reason is None
        observed = {feature.quantity for feature in run.observed_features}
        assert observed == {quantity for quantity, _ in SUMMARIZED_QUANTITIES}

    def test_dominant_frequency_is_read_not_computed(self):
        run = record("run-001", phase1_payload(dominant_hz=247.25))
        assert run.feature("dominant_frequency").value == 247.25
        assert run.feature("dominant_frequency").unit == "Hz"

    def test_peak_magnitude_matches_the_dominant_peak(self):
        run = record("run-001", phase1_payload(dominant_hz=245.0, magnitude=0.77))
        assert run.feature("peak_magnitude").value == 0.77

    def test_peak_magnitude_matched_by_frequency_not_position(self):
        payload = phase1_payload()
        # Put a louder, different peak first; the dominant is still 245.0.
        payload["analysis"]["peaks"] = [
            {"freq_hz": 490.0, "magnitude": 0.99},
            {"freq_hz": 245.0, "magnitude": 0.60},
        ]
        assert record("run-001", payload).feature("peak_magnitude").value == 0.60

    def test_snr_and_confidence_are_read(self):
        run = record("run-001", phase1_payload(snr_db=28.5, confidence=0.88))
        assert run.feature("snr").value == 28.5
        assert run.feature("confidence").value == 0.88

    def test_environment_is_carried_from_provenance(self):
        run = record("run-001", phase1_payload(temp_c=19.0, rh_pct=52.0))
        assert run.conditions.temp_c == 19.0
        assert run.conditions.rh_pct == 52.0

    def test_unknown_environment_stays_unknown(self):
        payload = phase1_payload(temp_c=None, rh_pct=None)
        assert record("run-001", payload).conditions.is_fully_unknown

    def test_timestamp_taken_from_the_document(self):
        assert record("run-001", phase1_payload()).captured_at == UTC_NOW

    def test_explicit_timestamp_overrides(self):
        run = record(
            "run-001", phase1_payload(), captured_at="2026-08-10T01:02:03+00:00"
        )
        assert run.captured_at == "2026-08-10T01:02:03+00:00"

    def test_missing_snr_still_yields_a_valid_run(self):
        payload = phase1_payload()
        del payload["analysis"]["confidence_components"]
        run = record("run-001", payload)
        assert run.valid
        assert run.feature("snr") is None
        assert run.feature("dominant_frequency") is not None


class TestRejectionMapping:
    @pytest.mark.parametrize(
        "rule_id,expected",
        [
            ("Q001", RejectionReason.CLIPPING),
            ("Q002", RejectionReason.INSUFFICIENT_SIGNAL),
            ("Q003", RejectionReason.ANALYSIS_FAILURE),
            ("Q005", RejectionReason.INVALID_METADATA),
        ],
    )
    def test_rule_id_maps_to_its_reason(self, rule_id, expected):
        payload = phase1_payload(verdict="fail", triggered_rules=[hard_rule(rule_id)])
        run = record("run-001", payload)
        assert not run.valid
        assert run.rejection_reason is expected

    def test_clipped_capture_is_rejected_as_clipping(self):
        payload = phase1_payload(
            clipped=True, verdict="fail", triggered_rules=[hard_rule("Q001")]
        )
        assert record("run-001", payload).rejection_reason is RejectionReason.CLIPPING

    def test_unmapped_hard_rule_reports_the_gate_verdict(self):
        # Q004 is low confidence: a real hard failure with no cause this table
        # names. Guessing clipping or low signal would invent a cause.
        payload = phase1_payload(verdict="fail", triggered_rules=[hard_rule("Q004")])
        assert record("run-001", payload).rejection_reason is (
            RejectionReason.QUALITY_GATE_REJECTED
        )

    def test_fail_with_no_named_rule_reports_the_gate_verdict(self):
        payload = phase1_payload(verdict="fail", triggered_rules=[])
        assert record("run-001", payload).rejection_reason is (
            RejectionReason.QUALITY_GATE_REJECTED
        )

    def test_soft_rules_do_not_reject(self):
        payload = phase1_payload(
            verdict="warn",
            triggered_rules=[{"rule_id": "Q010", "severity": "soft", "message": "m"}],
        )
        assert record("run-001", payload).valid

    def test_soft_rule_on_a_failing_verdict_is_not_the_cause(self):
        payload = phase1_payload(
            verdict="fail",
            triggered_rules=[
                {"rule_id": "Q001", "severity": "soft", "message": "m"},
            ],
        )
        # A soft Q001 did not cause the failure, so it must not be reported as
        # the reason.
        assert record("run-001", payload).rejection_reason is (
            RejectionReason.QUALITY_GATE_REJECTED
        )

    def test_null_dominant_frequency_is_an_analysis_failure(self):
        payload = phase1_payload(dominant_hz=None)
        run = record("run-001", payload)
        assert not run.valid
        assert run.rejection_reason is RejectionReason.ANALYSIS_FAILURE

    def test_wrong_contract_is_invalid_metadata(self):
        payload = phase1_payload()
        payload["schema_version"] = "phase1_tap_analysis_v2"
        run = record("run-001", payload)
        assert not run.valid
        assert run.rejection_reason is RejectionReason.INVALID_METADATA

    def test_missing_quality_block_is_invalid_metadata(self):
        payload = phase1_payload()
        del payload["quality"]
        assert record("run-001", payload).rejection_reason is (
            RejectionReason.INVALID_METADATA
        )

    def test_rejected_run_carries_no_observations(self):
        payload = phase1_payload(verdict="fail", triggered_rules=[hard_rule("Q001")])
        assert record("run-001", payload).observed_features == ()

    def test_rejected_run_keeps_its_artifacts_and_conditions(self):
        payload = phase1_payload(verdict="fail", triggered_rules=[hard_rule("Q001")])
        run = record("run-001", payload)
        assert run.source_artifact_ids == ("wav-run-001",)
        assert run.conditions.temp_c == 21.5


class TestMissingRun:
    def test_missing_artifact_is_still_an_attempt(self):
        run = record_missing_run(
            run_id="run-007",
            experiment_id="exp-001",
            evidence_origin=EvidenceOrigin.FIXTURE,
            captured_at=UTC_NOW,
        )
        assert not run.valid
        assert run.rejection_reason is RejectionReason.MISSING_ARTIFACT


class TestEvidenceOriginEnforcement:
    def test_synthetic_document_cannot_be_called_hardware(self):
        with pytest.raises(ExperimentRecordError) as exc:
            record(
                "run-001",
                phase1_payload(demo=True),
                evidence_origin=EvidenceOrigin.HARDWARE,
            )
        assert exc.value.code is GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED

    def test_synthetic_document_may_be_called_synthetic(self):
        run = record(
            "run-001",
            phase1_payload(demo=True),
            evidence_origin=EvidenceOrigin.SYNTHETIC,
        )
        assert run.evidence_origin is EvidenceOrigin.SYNTHETIC


# ---------------------------------------------------------------------------
# Study assembly
# ---------------------------------------------------------------------------


def build_study(**overrides):
    runs = overrides.pop(
        "runs",
        (
            record("run-001", phase1_payload(dominant_hz=244.0)),
            record("run-002", phase1_payload(dominant_hz=245.0)),
            record("run-003", phase1_payload(dominant_hz=246.0)),
            record(
                "run-004",
                phase1_payload(verdict="fail", triggered_rules=[hard_rule("Q001")]),
            ),
        ),
    )
    kwargs = {
        "study_id": "study-1",
        "definition": make_definition(),
        "runs": runs,
        "generated_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.FIXTURE,
    }
    kwargs.update(overrides)
    return build_repeatability_study(**kwargs)


class TestBuildRepeatabilityStudy:
    def test_valid_and_rejected_runs_are_both_accounted_for(self):
        study = build_study()
        assert study.valid_run_count == 3
        assert study.rejected_run_count == 1
        assert study.rejection_counts["CLIPPING"] == 1

    def test_metrics_summarize_only_valid_runs(self):
        metric = build_study().metrics[0]
        assert metric.quantity == "dominant_frequency"
        assert metric.sample_count == 3
        assert metric.mean == 245.0
        assert set(metric.source_run_ids) == {"run-001", "run-002", "run-003"}

    def test_rejected_run_stays_out_of_every_metric(self):
        study = build_study()
        for metric in study.metrics:
            assert "run-004" not in metric.source_run_ids

    def test_every_summarized_quantity_appears(self):
        quantities = {metric.quantity for metric in build_study().metrics}
        assert quantities == {q for q, _ in SUMMARIZED_QUANTITIES}

    def test_quantity_with_one_observation_is_omitted(self):
        runs = (
            record("run-001", phase1_payload()),
            record("run-002", phase1_payload()),
        )
        payload = phase1_payload()
        del payload["analysis"]["confidence_components"]
        runs = (runs[0], record("run-002", payload))
        quantities = {m.quantity for m in build_study(runs=runs).metrics}
        assert "snr" not in quantities
        assert "dominant_frequency" in quantities

    def test_study_is_traceable_to_its_source_runs(self):
        study = build_study()
        run_ids = {run.run_id for run in study.runs if run.valid}
        for metric in study.metrics:
            assert set(metric.source_run_ids) <= run_ids

    def test_hardware_claim_over_fixture_runs_is_refused(self):
        with pytest.raises(ExperimentRecordError) as exc:
            build_study(evidence_origin=EvidenceOrigin.HARDWARE)
        assert exc.value.code is GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED

    def test_all_runs_rejected_yields_no_metrics(self):
        runs = tuple(
            record(
                f"run-00{i}",
                phase1_payload(verdict="fail", triggered_rules=[hard_rule("Q001")]),
            )
            for i in range(1, 4)
        )
        study = build_study(runs=runs)
        assert study.metrics == ()
        assert study.valid_run_count == 0
        assert study.rejected_run_count == 3

    def test_cross_reference_to_do085_evidence_is_recorded(self):
        study = build_study(referenced_repeatability_evidence_ids=("do085-1",))
        assert study.referenced_repeatability_evidence_ids == ("do085-1",)

    def test_study_validates_against_its_schema(self):
        schema_path = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "contracts"
            / "ttp_preliminary_repeatability_study_v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(build_study().to_dict(), schema)


class TestStudyLimitations:
    def test_limitations_are_always_stated(self):
        assert build_study().limitations

    def test_repeatability_is_distinguished_from_accuracy(self):
        text = " ".join(build_study().limitations).lower()
        assert "not an accuracy" in text
        assert "reference method" in text

    def test_non_hardware_origin_is_stated_first(self):
        first = build_study().limitations[0].lower()
        assert "fixture" in first
        assert "not hardware evidence" in first

    def test_unknown_environment_is_called_out(self):
        text = " ".join(build_study().limitations).lower()
        assert "no environmental conditions were supplied" in text

    def test_known_environment_suppresses_that_limitation(self):
        definition = make_definition(
            environmental_context=EnvironmentalContextV1(temp_c=21.0, rh_pct=44.0)
        )
        text = " ".join(build_study(definition=definition).limitations).lower()
        assert "no environmental conditions were supplied" not in text

    def test_hardware_origin_omits_the_fixture_caveat(self):
        # Reached only through the helper, since no hardware runs exist here.
        limitations = default_study_limitations(
            make_definition(), (), EvidenceOrigin.HARDWARE
        )
        assert "not hardware evidence" not in " ".join(limitations).lower()

    def test_sample_scope_is_stated(self):
        text = " ".join(build_study().limitations).lower()
        assert "single measurement point" in text
        assert "between-session" in text
