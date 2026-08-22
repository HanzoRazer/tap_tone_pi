"""Grant-readiness evidence contracts (DO-102, Commit 2).

Covers the frozen-record behavior, the four-state and evidence-origin
vocabularies, strict deserialization, and the two exclusions DO-102 depends on:
no acceptance flag on a repeatability metric, and no way to record a run without
saying where its data came from.
"""

from __future__ import annotations

import dataclasses

import pytest

from tap_tone_pi.grant_readiness import (
    AUDIT_SCHEMA_VERSION,
    STUDY_SCHEMA_VERSION,
    CapabilityEvidenceV1,
    CapabilityStatus,
    EnvironmentalContextV1,
    EvidenceOrigin,
    ExcitationContextV1,
    GrantReadinessAuditV1,
    GrantReadinessErrorCode,
    HardwareVerification,
    ObservedFeatureV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
    RepeatabilityMetricV1,
    RepeatabilityStudyV1,
    RiskStatus,
    TechnicalRiskV1,
)
from tap_tone_pi.grant_readiness.contracts import (
    KNOWN_EXCITATION_METHODS,
    ReferenceMethodV1,
    ReferenceValidationPlanV1,
    require_utc_timestamp,
)
from tap_tone_pi.grant_readiness.errors import (
    CapabilityAuditError,
    ExperimentRecordError,
    GrantReadinessError,
)

UTC_NOW = "2026-08-09T12:00:00+00:00"


def make_definition(**overrides) -> PreliminaryExperimentDefinitionV1:
    kwargs = {
        "experiment_id": "exp-001",
        "instrument_id": "guitar-top-A",
        "measurement_point_id": "P1",
        "operator_id": "op-1",
        "planned_repeat_count": 10,
        "created_at": UTC_NOW,
    }
    kwargs.update(overrides)
    return PreliminaryExperimentDefinitionV1(**kwargs)


def make_run(**overrides) -> PreliminaryExperimentRunV1:
    kwargs = {
        "run_id": "run-001",
        "experiment_id": "exp-001",
        "captured_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.FIXTURE,
    }
    kwargs.update(overrides)
    return PreliminaryExperimentRunV1(**kwargs)


def make_metric(**overrides) -> RepeatabilityMetricV1:
    kwargs = {
        "metric_id": "m-1",
        "quantity": "dominant_frequency",
        "unit": "Hz",
        "sample_count": 3,
        "mean": 245.0,
        "median": 245.0,
        "standard_deviation": 1.0,
        "coefficient_of_variation_pct": 0.4,
        "minimum": 244.0,
        "maximum": 246.0,
        "range_value": 2.0,
        "median_absolute_deviation": 1.0,
        "source_run_ids": ("run-001", "run-002", "run-003"),
    }
    kwargs.update(overrides)
    return RepeatabilityMetricV1(**kwargs)


# ---------------------------------------------------------------------------
# Frozen behavior and defaults
# ---------------------------------------------------------------------------


ALL_RECORDS = [
    CapabilityEvidenceV1,
    GrantReadinessAuditV1,
    EnvironmentalContextV1,
    ExcitationContextV1,
    PreliminaryExperimentDefinitionV1,
    ObservedFeatureV1,
    PreliminaryExperimentRunV1,
    RepeatabilityMetricV1,
    RepeatabilityStudyV1,
    TechnicalRiskV1,
    ReferenceMethodV1,
    ReferenceValidationPlanV1,
]


@pytest.mark.parametrize("record_cls", ALL_RECORDS, ids=lambda c: c.__name__)
class TestRecordShape:
    def test_is_frozen_dataclass(self, record_cls):
        assert dataclasses.is_dataclass(record_cls)
        assert record_cls.__dataclass_params__.frozen

    def test_no_mutable_defaults(self, record_cls):
        for spec in dataclasses.fields(record_cls):
            assert not isinstance(spec.default, (list, dict, set))


class TestFrozenAndEquality:
    def test_cannot_mutate(self):
        metric = make_metric()
        with pytest.raises(dataclasses.FrozenInstanceError):
            metric.mean = 1.0  # type: ignore[misc]

    def test_deterministic_equality(self):
        assert make_metric() == make_metric()
        assert make_metric() != make_metric(mean=1.0)

    def test_schema_versions_are_not_constructor_arguments(self):
        # schema_version is identity, not input: it cannot be overridden.
        with pytest.raises(TypeError):
            RepeatabilityStudyV1(  # type: ignore[call-arg]
                study_id="s",
                experiment_definition=make_definition(),
                generated_at=UTC_NOW,
                evidence_origin=EvidenceOrigin.FIXTURE,
                schema_version="something-else",
            )

    def test_schema_version_constants(self):
        assert AUDIT_SCHEMA_VERSION == "nsf_grant_readiness_audit_v1"
        assert STUDY_SCHEMA_VERSION == "ttp_preliminary_repeatability_study_v1"


# ---------------------------------------------------------------------------
# The exclusions DO-102 depends on
# ---------------------------------------------------------------------------


class TestRepeatabilityMetricCarriesNoVerdict:
    """A metric reports spread. It does not report acceptability."""

    def test_no_acceptance_fields(self):
        names = {spec.name for spec in dataclasses.fields(RepeatabilityMetricV1)}
        forbidden = {
            "is_acceptable",
            "acceptance_threshold_pct",
            "passed_repeatability_gate",
            "gate_failure_reason",
            "verdict",
            "accuracy_pct",
        }
        assert not (names & forbidden)

    def test_serialized_form_carries_no_verdict(self):
        payload = make_metric().to_dict()
        for key in payload:
            assert "accept" not in key
            assert "gate" not in key
            assert "verdict" not in key

    def test_metric_names_its_source_runs(self):
        # Every derived statistic must point back at the runs that produced it.
        metric = make_metric()
        assert metric.sample_count == len(metric.source_run_ids)


class TestEvidenceOrigin:
    def test_only_hardware_is_hardware_evidence(self):
        assert EvidenceOrigin.HARDWARE.is_hardware_evidence
        assert not EvidenceOrigin.FIXTURE.is_hardware_evidence
        assert not EvidenceOrigin.SYNTHETIC.is_hardware_evidence

    def test_run_requires_an_origin(self):
        with pytest.raises(TypeError):
            PreliminaryExperimentRunV1(  # type: ignore[call-arg]
                run_id="r", experiment_id="e", captured_at=UTC_NOW
            )

    def test_study_reports_its_origin(self):
        study = RepeatabilityStudyV1(
            study_id="s-1",
            experiment_definition=make_definition(),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.SYNTHETIC,
        )
        assert not study.is_hardware_evidence
        assert study.to_dict()["evidence_origin"] == "SYNTHETIC"


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


class TestVocabularies:
    def test_capability_status_is_exactly_four_states(self):
        assert {s.value for s in CapabilityStatus} == {
            "IMPLEMENTED",
            "EXPERIMENTAL",
            "PARTIAL",
            "PLANNED",
        }

    def test_no_vague_status(self):
        with pytest.raises(ValueError):
            CapabilityStatus("MOSTLY_DONE")

    def test_hardware_verification_states(self):
        assert {s.value for s in HardwareVerification} == {
            "VERIFIED_ON_HARDWARE",
            "NOT_VERIFIED_ON_HARDWARE",
            "NOT_APPLICABLE",
        }

    def test_rejection_reasons_cover_the_do102_list(self):
        values = {r.value for r in RejectionReason}
        assert {
            "CLIPPING",
            "INSUFFICIENT_SIGNAL",
            "ANALYSIS_FAILURE",
            "MISSING_ARTIFACT",
            "INVALID_METADATA",
        } <= values

    def test_risk_status_values(self):
        assert RiskStatus.OPEN.value == "OPEN"


class TestExcitationIsGeneric:
    def test_manual_tap_is_one_value_among_several(self):
        assert "manual_tap" in KNOWN_EXCITATION_METHODS
        assert "shaker_stinger" in KNOWN_EXCITATION_METHODS
        assert "instrumented_hammer" in KNOWN_EXCITATION_METHODS

    def test_default_method_is_not_manual_tap(self):
        # Nothing may default to manual tapping as the canonical architecture.
        assert ExcitationContextV1().excitation_method == "unspecified"

    def test_unlisted_method_is_recorded_not_rejected(self):
        context = ExcitationContextV1.from_dict(
            {"excitation_method": "pendulum_impactor"}
        )
        assert context.excitation_method == "pendulum_impactor"
        assert not context.is_known_method

    def test_links_to_driven_excitation_contract(self):
        context = ExcitationContextV1(
            excitation_method="shaker_stinger",
            excitation_device_id="shaker-01",
            contact_condition="stinger, 2mm nylon",
            fixture_id="fx-3",
            excitation_contract_id="exc-777",
        )
        assert context.to_dict()["excitation_contract_id"] == "exc-777"


# ---------------------------------------------------------------------------
# Environment is recorded, never corrected
# ---------------------------------------------------------------------------


class TestEnvironmentalContext:
    def test_unknown_stays_unknown(self):
        context = EnvironmentalContextV1()
        assert context.is_fully_unknown
        assert context.to_dict() == {
            "temp_c": None,
            "rh_pct": None,
            "specimen_moisture_pct": None,
            "ambient_noise_note": None,
        }

    def test_partial_knowledge_is_preserved(self):
        context = EnvironmentalContextV1(temp_c=21.5)
        assert not context.is_fully_unknown
        assert context.to_dict()["rh_pct"] is None

    def test_round_trip(self):
        context = EnvironmentalContextV1(
            temp_c=21.5, rh_pct=44.0, ambient_noise_note="shop compressor off"
        )
        assert EnvironmentalContextV1.from_dict(context.to_dict()) == context

    def test_non_finite_rejected(self):
        with pytest.raises(GrantReadinessError) as exc:
            EnvironmentalContextV1.from_dict({"temp_c": float("nan")})
        assert exc.value.code is GrantReadinessErrorCode.NON_FINITE_STATISTIC


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


class TestUtcTimestamps:
    @pytest.mark.parametrize(
        "value", ["2026-08-09T12:00:00+00:00", "2026-08-09T12:00:00Z"]
    )
    def test_accepts_utc(self, value):
        assert require_utc_timestamp(value, record="R", field_name="t") == value

    @pytest.mark.parametrize(
        "value",
        ["2026-08-09T12:00:00", "2026-08-09T12:00:00-05:00", "not-a-time", "", None, 5],
    )
    def test_rejects_non_utc(self, value):
        with pytest.raises(ExperimentRecordError) as exc:
            require_utc_timestamp(value, record="R", field_name="t")
        assert exc.value.code is GrantReadinessErrorCode.TIMESTAMP_NOT_UTC


# ---------------------------------------------------------------------------
# Strict deserialization
# ---------------------------------------------------------------------------


class TestCapabilityEvidenceSerialization:
    def test_round_trip(self):
        evidence = CapabilityEvidenceV1(
            capability_id="phase1_tap_workflow",
            name="Phase 1 single-microphone tap workflow",
            status=CapabilityStatus.IMPLEMENTED,
            implementation_paths=("tap_tone_pi/phase1/demo.py",),
            test_paths=("tests/test_phase1_demo.py",),
            hardware_verified=HardwareVerification.NOT_VERIFIED_ON_HARDWARE,
            notes="Exercised by synthetic impulse generation.",
        )
        assert CapabilityEvidenceV1.from_dict(evidence.to_dict()) == evidence

    def test_unknown_field_rejected(self):
        with pytest.raises(CapabilityAuditError) as exc:
            CapabilityEvidenceV1.from_dict(
                {
                    "capability_id": "x",
                    "name": "x",
                    "status": "IMPLEMENTED",
                    "hardware_verified": "NOT_APPLICABLE",
                    "notes": "n",
                    "confidence": 0.9,
                }
            )
        assert exc.value.code is GrantReadinessErrorCode.CONTRADICTORY_CAPABILITY_CLAIM
        assert exc.value.context["unknown_fields"] == ["confidence"]

    def test_invalid_status_rejected(self):
        with pytest.raises(CapabilityAuditError) as exc:
            CapabilityEvidenceV1.from_dict(
                {
                    "capability_id": "x",
                    "name": "x",
                    "status": "MOSTLY_DONE",
                    "hardware_verified": "NOT_APPLICABLE",
                    "notes": "n",
                }
            )
        assert exc.value.code is GrantReadinessErrorCode.INVALID_CAPABILITY_STATUS

    def test_invalid_hardware_state_rejected(self):
        with pytest.raises(CapabilityAuditError) as exc:
            CapabilityEvidenceV1.from_dict(
                {
                    "capability_id": "x",
                    "name": "x",
                    "status": "IMPLEMENTED",
                    "hardware_verified": "PROBABLY",
                    "notes": "n",
                }
            )
        assert exc.value.code is GrantReadinessErrorCode.INVALID_HARDWARE_VERIFICATION

    def test_notes_are_required(self):
        with pytest.raises(CapabilityAuditError):
            CapabilityEvidenceV1.from_dict(
                {
                    "capability_id": "x",
                    "name": "x",
                    "status": "IMPLEMENTED",
                    "hardware_verified": "NOT_APPLICABLE",
                    "notes": "  ",
                }
            )


class TestAuditSerialization:
    def _audit(self) -> GrantReadinessAuditV1:
        return GrantReadinessAuditV1(
            audit_id="audit-1",
            generated_at=UTC_NOW,
            repository_commit="a01e973",
            capabilities=(
                CapabilityEvidenceV1(
                    capability_id="a",
                    name="A",
                    status=CapabilityStatus.IMPLEMENTED,
                    notes="n",
                ),
                CapabilityEvidenceV1(
                    capability_id="b",
                    name="B",
                    status=CapabilityStatus.PLANNED,
                    notes="n",
                ),
            ),
            limitations=("No hardware campaign executed.",),
        )

    def test_round_trip(self):
        audit = self._audit()
        assert GrantReadinessAuditV1.from_dict(audit.to_dict()) == audit

    def test_status_counts_include_every_state(self):
        counts = self._audit().status_counts
        assert set(counts) == {s.value for s in CapabilityStatus}
        assert counts["IMPLEMENTED"] == 1
        assert counts["PLANNED"] == 1
        assert counts["EXPERIMENTAL"] == 0

    def test_hardware_verified_count_is_zero(self):
        assert self._audit().hardware_verified_count == 0

    def test_wrong_schema_version_rejected(self):
        payload = self._audit().to_dict()
        payload["schema_version"] = "nsf_grant_readiness_audit_v2"
        with pytest.raises(CapabilityAuditError):
            GrantReadinessAuditV1.from_dict(payload)


class TestRunSerialization:
    def test_valid_run_round_trip(self):
        run = make_run(
            source_artifact_ids=("wav-1",),
            measurement_result_id="res-1",
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 245.1),),
            conditions=EnvironmentalContextV1(temp_c=21.0),
        )
        assert PreliminaryExperimentRunV1.from_dict(run.to_dict()) == run

    def test_rejected_run_round_trip(self):
        run = make_run(
            run_id="run-004",
            valid=False,
            rejection_reason=RejectionReason.CLIPPING,
            source_artifact_ids=("wav-4",),
        )
        restored = PreliminaryExperimentRunV1.from_dict(run.to_dict())
        assert restored == run
        assert restored.rejection_reason is RejectionReason.CLIPPING

    def test_invalid_rejection_reason_rejected(self):
        payload = make_run(valid=False).to_dict()
        payload["rejection_reason"] = "OPERATOR_DIDNT_LIKE_IT"
        with pytest.raises(ExperimentRecordError) as exc:
            PreliminaryExperimentRunV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.INVALID_REJECTION_REASON

    def test_missing_evidence_origin_rejected(self):
        payload = make_run().to_dict()
        del payload["evidence_origin"]
        with pytest.raises(ExperimentRecordError) as exc:
            PreliminaryExperimentRunV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED

    def test_feature_lookup(self):
        run = make_run(
            observed_features=(
                ObservedFeatureV1("dominant_frequency", "Hz", 245.1),
                ObservedFeatureV1("snr", "dB", 31.0),
            )
        )
        assert run.feature("snr").value == 31.0
        assert run.feature("coherence") is None


class TestStudySerialization:
    def _study(self) -> RepeatabilityStudyV1:
        return RepeatabilityStudyV1(
            study_id="study-1",
            experiment_definition=make_definition(),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            runs=(
                make_run(run_id="run-001"),
                make_run(run_id="run-002"),
                make_run(
                    run_id="run-003",
                    valid=False,
                    rejection_reason=RejectionReason.CLIPPING,
                ),
                make_run(
                    run_id="run-004",
                    valid=False,
                    rejection_reason=RejectionReason.MISSING_ARTIFACT,
                ),
            ),
            metrics=(make_metric(),),
            limitations=("Fixture data; not hardware evidence.",),
            referenced_repeatability_evidence_ids=("do085-evidence-1",),
        )

    def test_round_trip(self):
        study = self._study()
        assert RepeatabilityStudyV1.from_dict(study.to_dict()) == study

    def test_valid_and_rejected_counts(self):
        study = self._study()
        assert study.valid_run_count == 2
        assert study.rejected_run_count == 2

    def test_rejection_counts_cover_every_reason(self):
        counts = self._study().rejection_counts
        assert set(counts) == {r.value for r in RejectionReason}
        assert counts["CLIPPING"] == 1
        assert counts["MISSING_ARTIFACT"] == 1
        assert counts["ANALYSIS_FAILURE"] == 0

    def test_cross_reference_is_optional(self):
        # A study serializes and restores without any DO-085 evidence linked.
        study = RepeatabilityStudyV1(
            study_id="s",
            experiment_definition=make_definition(),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
        )
        assert study.referenced_repeatability_evidence_ids == ()
        assert RepeatabilityStudyV1.from_dict(study.to_dict()) == study

    def test_unknown_field_rejected(self):
        payload = self._study().to_dict()
        payload["accuracy_pct"] = 99.0
        with pytest.raises(ExperimentRecordError):
            RepeatabilityStudyV1.from_dict(payload)

    def test_contradictory_valid_run_count_rejected(self):
        # The derived counts round-trip, but a persisted count that disagrees
        # with the runs is an internally inconsistent document and must fail
        # rather than deserialize silently into an object whose count differs.
        payload = self._study().to_dict()
        assert payload["valid_run_count"] == 2
        payload["valid_run_count"] = 99
        with pytest.raises(ExperimentRecordError):
            RepeatabilityStudyV1.from_dict(payload)

    def test_contradictory_rejection_counts_rejected(self):
        payload = self._study().to_dict()
        payload["rejection_counts"] = dict(payload["rejection_counts"])
        payload["rejection_counts"]["CLIPPING"] += 5
        with pytest.raises(ExperimentRecordError):
            RepeatabilityStudyV1.from_dict(payload)

    def test_consistent_counts_still_round_trip(self):
        # The consistency check must not reject the canonical to_dict payload.
        study = self._study()
        payload = study.to_dict()
        assert RepeatabilityStudyV1.from_dict(payload) == study


class TestDefinitionSerialization:
    def test_round_trip_with_full_context(self):
        definition = make_definition(
            excitation=ExcitationContextV1(
                excitation_method="manual_tap",
                excitation_point="bridge, treble side",
                contact_condition="fingertip through 3mm felt",
            ),
            sensor_position="150mm above soundhole, on axis",
            support_condition="foam cradle at lower bout",
            environmental_context=EnvironmentalContextV1(temp_c=21.5, rh_pct=44.0),
        )
        assert (
            PreliminaryExperimentDefinitionV1.from_dict(definition.to_dict())
            == definition
        )

    def test_analysis_profile_defaults_to_phase1(self):
        assert make_definition().analysis_profile == "phase1_tap_analysis_v1"

    def test_non_integer_repeat_count_rejected(self):
        payload = make_definition().to_dict()
        payload["planned_repeat_count"] = "ten"
        with pytest.raises(ExperimentRecordError) as exc:
            PreliminaryExperimentDefinitionV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION

    def test_missing_instrument_id_rejected(self):
        payload = make_definition().to_dict()
        payload["instrument_id"] = ""
        with pytest.raises(ExperimentRecordError):
            PreliminaryExperimentDefinitionV1.from_dict(payload)


class TestMetricSerialization:
    def test_round_trip(self):
        metric = make_metric()
        assert RepeatabilityMetricV1.from_dict(metric.to_dict()) == metric

    def test_non_finite_rejected(self):
        payload = make_metric().to_dict()
        payload["mean"] = float("inf")
        with pytest.raises(ExperimentRecordError) as exc:
            RepeatabilityMetricV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.NON_FINITE_STATISTIC

    def test_missing_statistic_rejected(self):
        payload = make_metric().to_dict()
        del payload["median_absolute_deviation"]
        with pytest.raises(ExperimentRecordError):
            RepeatabilityMetricV1.from_dict(payload)


# ---------------------------------------------------------------------------
# Risks and reference plan
# ---------------------------------------------------------------------------


class TestRiskAndReferencePlan:
    def test_risk_round_trip(self):
        risk = TechnicalRiskV1(
            risk_id="R1",
            title="Excitation variability",
            current_evidence="No repeated-excitation dataset exists.",
            unresolved_question="How much of observed spread is the tap?",
            phase_i_relevance="Bounds every other repeatability figure.",
            proposed_validation_method="Compare manual tap against a driven source.",
            status=RiskStatus.OPEN,
        )
        assert TechnicalRiskV1.from_dict(risk.to_dict()) == risk

    def test_reference_method_defaults_to_tbd(self):
        method = ReferenceMethodV1(
            method="Calibrated microphone",
            measurement_compared="Sound pressure level",
            access_status="Not yet sourced",
        )
        assert method.potential_partner == "TBD"
        assert method.required_preparation == "TBD"
        assert method.phase_i_role == "TBD"

    def test_reference_plan_serializes(self):
        plan = ReferenceValidationPlanV1(
            plan_id="ref-1",
            generated_at=UTC_NOW,
            methods=(
                ReferenceMethodV1(
                    method="Impact hammer",
                    measurement_compared="Input force spectrum",
                    access_status="Not owned",
                ),
            ),
        )
        payload = plan.to_dict()
        assert payload["methods"][0]["potential_partner"] == "TBD"


# ---------------------------------------------------------------------------
# Error vocabulary
# ---------------------------------------------------------------------------


class TestErrorVocabulary:
    def test_codes_are_grouped_by_layer(self):
        for code in GrantReadinessErrorCode:
            assert code.value.startswith("NSF-")
            # 5xx is the DO-103 hardware-campaign family. It is a new layer
            # rather than an extension of 3xx, whose codes are statistics and
            # reporting; overloading that family would make the grouping the
            # errors module documents stop describing anything.
            assert code.value[4] in {"1", "2", "3", "4", "5"}

    def test_codes_are_unique(self):
        values = [code.value for code in GrantReadinessErrorCode]
        assert len(values) == len(set(values))

    def test_error_serializes_deterministically(self):
        error = GrantReadinessError(
            GrantReadinessErrorCode.DUPLICATE_RUN_ID,
            "duplicate run",
            {"z": 1, "a": 2},
        )
        payload = error.to_dict()
        assert payload["code"] == "NSF-203"
        assert list(payload["context"]) == ["a", "z"]
