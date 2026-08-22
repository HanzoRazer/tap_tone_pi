"""Grant-readiness validation and persisted schemas (DO-102, Commit 3).

Covers the pure validators, the evidence-linkage helpers, and strict validation
of both persisted contracts against their JSON schemas — including the rule that
a study may not claim an origin its runs do not support.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness import (
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
    TechnicalRiskV1,
)
from tap_tone_pi.grant_readiness.contracts import (
    ReferenceMethodV1,
    ReferenceValidationPlanV1,
)
from tap_tone_pi.grant_readiness.errors import GrantReadinessError
from tap_tone_pi.grant_readiness.validation import (
    MINIMUM_REPEAT_COUNT,
    ValidationFinding,
    evidence_digest,
    is_host_path,
    normalize_run_ids,
    raise_for_findings,
    validate_capability_evidence,
    validate_capability_inventory,
    validate_experiment_definition,
    validate_experiment_runs,
    validate_no_unwitnessed_hardware_claim,
    validate_reference_validation_plan,
    validate_repeatability_study,
    validate_source_artifact_refs,
    validate_study_evidence_origin,
    validate_technical_risk,
)

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC_NOW = "2026-08-09T12:00:00+00:00"


def codes(findings) -> list[str]:
    return [finding.code.value for finding in findings]


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


def make_valid_run(run_id: str, value: float = 245.0) -> PreliminaryExperimentRunV1:
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="exp-001",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=True,
        source_artifact_ids=(f"wav-{run_id}",),
        measurement_result_id=f"res-{run_id}",
        observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", value),),
    )


def make_rejected_run(
    run_id: str, reason: RejectionReason = RejectionReason.CLIPPING
) -> PreliminaryExperimentRunV1:
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="exp-001",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=False,
        rejection_reason=reason,
        source_artifact_ids=(f"wav-{run_id}",),
    )


def make_metric(source_run_ids=("run-001", "run-002")) -> RepeatabilityMetricV1:
    return RepeatabilityMetricV1(
        metric_id="m-1",
        quantity="dominant_frequency",
        unit="Hz",
        sample_count=len(set(source_run_ids)),
        mean=245.0,
        median=245.0,
        standard_deviation=1.0,
        coefficient_of_variation_pct=0.41,
        minimum=244.0,
        maximum=246.0,
        range_value=2.0,
        median_absolute_deviation=1.0,
        source_run_ids=tuple(source_run_ids),
    )


def make_study(**overrides) -> RepeatabilityStudyV1:
    kwargs = {
        "study_id": "study-1",
        "experiment_definition": make_definition(),
        "generated_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.FIXTURE,
        "runs": (
            make_valid_run("run-001", 244.0),
            make_valid_run("run-002", 246.0),
            make_rejected_run("run-003"),
        ),
        "metrics": (make_metric(),),
        "limitations": ("Fixture data. Not hardware evidence.",),
    }
    kwargs.update(overrides)
    return RepeatabilityStudyV1(**kwargs)


# ---------------------------------------------------------------------------
# Findings machinery
# ---------------------------------------------------------------------------


class TestFindings:
    def test_finding_serializes_with_sorted_context(self):
        finding = ValidationFinding(
            GrantReadinessErrorCode.DUPLICATE_RUN_ID, "dupe", {"z": 1, "a": 2}
        )
        payload = finding.to_dict()
        assert payload["code"] == "NSF-203"
        assert list(payload["context"]) == ["a", "z"]

    def test_raise_for_findings_is_a_no_op_when_clean(self):
        raise_for_findings([])

    def test_raise_for_findings_carries_every_finding(self):
        findings = [
            ValidationFinding(GrantReadinessErrorCode.DUPLICATE_RUN_ID, "first"),
            ValidationFinding(
                GrantReadinessErrorCode.SOURCE_ARTIFACT_MISSING, "second"
            ),
        ]
        with pytest.raises(GrantReadinessError) as exc:
            raise_for_findings(findings)
        assert exc.value.code is GrantReadinessErrorCode.DUPLICATE_RUN_ID
        assert len(exc.value.context["findings"]) == 2


# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------


class TestEvidenceHelpers:
    def test_digest_is_stable_across_key_order(self):
        assert evidence_digest({"a": 1, "b": 2}) == evidence_digest({"b": 2, "a": 1})

    def test_digest_changes_with_content(self):
        assert evidence_digest({"a": 1}) != evidence_digest({"a": 2})

    def test_digest_refuses_non_finite(self):
        with pytest.raises(ValueError):
            evidence_digest({"a": float("nan")})

    def test_normalize_run_ids_dedupes_and_sorts(self):
        assert normalize_run_ids(["b", "a", "b"]) == ("a", "b")

    @pytest.mark.parametrize(
        "value",
        [
            "/home/pi/run.wav",
            "C:\\Users\\x\\run.wav",
            "C:/Users/x/run.wav",
            "\\\\srv\\s",
        ],
    )
    def test_host_paths_detected(self, value):
        assert is_host_path(value)

    @pytest.mark.parametrize(
        "value", ["runs_phase2/session/point.wav", "wav-001", "tap_tone_pi/io/wav.py"]
    )
    def test_relative_references_allowed(self, value):
        assert not is_host_path(value)

    def test_missing_artifact_reference_flagged(self):
        findings = validate_source_artifact_refs((), record="run r")
        assert codes(findings) == ["NSF-204"]

    def test_absolute_artifact_reference_flagged(self):
        findings = validate_source_artifact_refs(("/var/data/run.wav",), record="run r")
        assert "NSF-401" in codes(findings)


# ---------------------------------------------------------------------------
# Capability audit validation
# ---------------------------------------------------------------------------


class TestCapabilityValidation:
    def _evidence(self, **overrides) -> CapabilityEvidenceV1:
        kwargs = {
            "capability_id": "phase1_tap_workflow",
            "name": "Phase 1 tap workflow",
            "status": CapabilityStatus.IMPLEMENTED,
            "implementation_paths": ("tap_tone_pi/phase1/demo.py",),
            "test_paths": ("tests/test_phase1_demo.py",),
            "hardware_verified": HardwareVerification.NOT_VERIFIED_ON_HARDWARE,
            "notes": "Exercised by synthetic impulse generation.",
        }
        kwargs.update(overrides)
        return CapabilityEvidenceV1(**kwargs)

    def test_implemented_with_code_and_tests_is_clean(self):
        assert validate_capability_evidence(self._evidence(), repo_root=REPO_ROOT) == []

    def test_experimental_capability_needs_no_tests(self):
        evidence = self._evidence(status=CapabilityStatus.EXPERIMENTAL, test_paths=())
        assert validate_capability_evidence(evidence) == []

    def test_partial_capability_is_accepted(self):
        evidence = self._evidence(status=CapabilityStatus.PARTIAL)
        assert validate_capability_evidence(evidence) == []

    def test_planned_capability_without_implementation_is_clean(self):
        evidence = self._evidence(
            status=CapabilityStatus.PLANNED, implementation_paths=(), test_paths=()
        )
        assert validate_capability_evidence(evidence) == []

    def test_planned_capability_with_implementation_is_contradictory(self):
        evidence = self._evidence(status=CapabilityStatus.PLANNED)
        assert "NSF-103" in codes(validate_capability_evidence(evidence))

    def test_implemented_without_code_is_flagged(self):
        evidence = self._evidence(implementation_paths=())
        assert "NSF-102" in codes(validate_capability_evidence(evidence))

    def test_implemented_without_tests_is_flagged(self):
        evidence = self._evidence(test_paths=())
        assert "NSF-103" in codes(validate_capability_evidence(evidence))

    def test_status_without_explanation_is_flagged(self):
        evidence = self._evidence(notes="   ")
        assert "NSF-103" in codes(validate_capability_evidence(evidence))

    def test_unresolvable_path_is_flagged(self):
        evidence = self._evidence(
            implementation_paths=("tap_tone_pi/does_not_exist.py",)
        )
        findings = validate_capability_evidence(evidence, repo_root=REPO_ROOT)
        assert codes(findings) == ["NSF-105"]

    def test_absolute_path_is_flagged_without_touching_disk(self):
        evidence = self._evidence(implementation_paths=("/opt/ttp/demo.py",))
        assert "NSF-105" in codes(validate_capability_evidence(evidence))

    def test_duplicate_capability_id_is_flagged(self):
        inventory = (self._evidence(), self._evidence())
        assert "NSF-104" in codes(validate_capability_inventory(inventory))

    def test_inventory_is_clean_against_the_repository(self):
        assert (
            validate_capability_inventory((self._evidence(),), repo_root=REPO_ROOT)
            == []
        )

    def test_hardware_verified_claim_is_refused(self):
        evidence = self._evidence(
            hardware_verified=HardwareVerification.VERIFIED_ON_HARDWARE
        )
        findings = validate_no_unwitnessed_hardware_claim((evidence,))
        assert codes(findings) == ["NSF-106"]

    def test_unverified_hardware_claim_is_accepted(self):
        assert validate_no_unwitnessed_hardware_claim((self._evidence(),)) == []


# ---------------------------------------------------------------------------
# Experiment definition validation
# ---------------------------------------------------------------------------


class TestExperimentDefinitionValidation:
    def test_valid_bounded_experiment(self):
        assert validate_experiment_definition(make_definition()) == []

    def test_zero_repeats_rejected(self):
        findings = validate_experiment_definition(
            make_definition(planned_repeat_count=0)
        )
        assert codes(findings) == ["NSF-202"]

    def test_single_repeat_rejected(self):
        findings = validate_experiment_definition(
            make_definition(planned_repeat_count=1)
        )
        assert codes(findings) == ["NSF-202"]

    def test_minimum_repeat_count_is_two(self):
        assert MINIMUM_REPEAT_COUNT == 2
        assert (
            validate_experiment_definition(
                make_definition(planned_repeat_count=MINIMUM_REPEAT_COUNT)
            )
            == []
        )

    def test_missing_instrument_id_rejected(self):
        findings = validate_experiment_definition(make_definition(instrument_id="  "))
        assert codes(findings) == ["NSF-201"]

    def test_missing_measurement_point_rejected(self):
        findings = validate_experiment_definition(
            make_definition(measurement_point_id="")
        )
        assert codes(findings) == ["NSF-201"]

    def test_unknown_environment_is_accepted(self):
        # DO-102 §4.6: missing environmental fields remain unknown, not invalid.
        definition = make_definition(environmental_context=EnvironmentalContextV1())
        assert validate_experiment_definition(definition) == []
        assert definition.environmental_context.is_fully_unknown

    def test_unlisted_excitation_method_is_accepted(self):
        definition = make_definition(
            excitation=ExcitationContextV1(excitation_method="pendulum_impactor")
        )
        assert validate_experiment_definition(definition) == []


# ---------------------------------------------------------------------------
# Run validation
# ---------------------------------------------------------------------------


class TestRunValidation:
    def test_valid_run_is_clean(self):
        assert validate_experiment_runs((make_valid_run("run-001"),)) == []

    @pytest.mark.parametrize(
        "reason",
        [
            RejectionReason.CLIPPING,
            RejectionReason.INSUFFICIENT_SIGNAL,
            RejectionReason.ANALYSIS_FAILURE,
            RejectionReason.MISSING_ARTIFACT,
            RejectionReason.INVALID_METADATA,
            RejectionReason.QUALITY_GATE_REJECTED,
        ],
    )
    def test_every_rejection_reason_is_recordable(self, reason):
        assert validate_experiment_runs((make_rejected_run("run-001", reason),)) == []

    def test_valid_and_rejected_runs_coexist(self):
        runs = (
            make_valid_run("run-001"),
            make_rejected_run("run-002"),
            make_valid_run("run-003"),
        )
        assert validate_experiment_runs(runs) == []

    def test_duplicate_run_id_flagged(self):
        runs = (make_valid_run("run-001"), make_valid_run("run-001"))
        assert "NSF-203" in codes(validate_experiment_runs(runs))

    def test_run_from_another_experiment_flagged(self):
        stray = PreliminaryExperimentRunV1(
            run_id="run-009",
            experiment_id="exp-999",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            source_artifact_ids=("wav-9",),
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 1.0),),
        )
        findings = validate_experiment_runs((stray,), definition=make_definition())
        assert codes(findings) == ["NSF-206"]

    def test_valid_run_without_source_artifact_flagged(self):
        run = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-001",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 1.0),),
        )
        assert "NSF-204" in codes(validate_experiment_runs((run,)))

    def test_rejected_run_may_have_lost_its_artifact(self):
        # MISSING_ARTIFACT is a rejection reason, so demanding an artifact from
        # a rejected run would make that reason impossible to record.
        run = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-001",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            valid=False,
            rejection_reason=RejectionReason.MISSING_ARTIFACT,
        )
        assert validate_experiment_runs((run,)) == []

    def test_rejected_run_without_reason_flagged(self):
        run = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-001",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            valid=False,
        )
        assert "NSF-205" in codes(validate_experiment_runs((run,)))

    def test_valid_run_carrying_a_reason_flagged(self):
        run = make_valid_run("run-001")
        run = PreliminaryExperimentRunV1(
            run_id=run.run_id,
            experiment_id=run.experiment_id,
            captured_at=run.captured_at,
            evidence_origin=run.evidence_origin,
            valid=True,
            rejection_reason=RejectionReason.CLIPPING,
            source_artifact_ids=run.source_artifact_ids,
            observed_features=run.observed_features,
        )
        assert "NSF-205" in codes(validate_experiment_runs((run,)))

    def test_valid_run_observing_nothing_flagged(self):
        run = PreliminaryExperimentRunV1(
            run_id="run-001",
            experiment_id="exp-001",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.FIXTURE,
            source_artifact_ids=("wav-1",),
        )
        assert "NSF-301" in codes(validate_experiment_runs((run,)))


# ---------------------------------------------------------------------------
# Study validation
# ---------------------------------------------------------------------------


class TestStudyValidation:
    def test_well_formed_study_is_clean(self):
        assert validate_repeatability_study(make_study()) == []

    def test_metric_citing_an_unknown_run_flagged(self):
        study = make_study(metrics=(make_metric(("run-001", "run-404")),))
        assert "NSF-401" in codes(validate_repeatability_study(study))

    def test_metric_drawing_on_a_rejected_run_flagged(self):
        # Rejected runs are counted, never summarized.
        study = make_study(metrics=(make_metric(("run-001", "run-003")),))
        assert "NSF-205" in codes(validate_repeatability_study(study))

    def test_sample_count_must_match_cited_runs(self):
        metric = make_metric(("run-001", "run-002"))
        mismatched = RepeatabilityMetricV1(
            **{
                **metric.to_dict(),
                "sample_count": 5,
                "source_run_ids": ("run-001", "run-002"),
            }
        )
        study = make_study(metrics=(mismatched,))
        assert "NSF-401" in codes(validate_repeatability_study(study))

    def test_metrics_without_limitations_flagged(self):
        study = make_study(limitations=())
        assert "NSF-301" in codes(validate_repeatability_study(study))

    def test_summary_points_at_every_contributing_valid_run(self):
        study = make_study()
        valid_ids = {run.run_id for run in study.runs if run.valid}
        assert set(study.metrics[0].source_run_ids) == valid_ids


class TestStudyEvidenceOrigin:
    def test_fixture_study_of_fixture_runs_is_clean(self):
        assert validate_study_evidence_origin(make_study()) == []

    def test_hardware_claim_over_fixture_runs_is_refused(self):
        study = make_study(evidence_origin=EvidenceOrigin.HARDWARE)
        findings = validate_study_evidence_origin(study)
        assert codes(findings) == ["NSF-305"]
        assert "run-001" in findings[0].context["non_hardware_run_ids"]

    def test_fixture_claim_over_hardware_runs_is_refused(self):
        hardware_run = PreliminaryExperimentRunV1(
            run_id="run-h",
            experiment_id="exp-001",
            captured_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.HARDWARE,
            source_artifact_ids=("wav-h",),
            observed_features=(ObservedFeatureV1("dominant_frequency", "Hz", 1.0),),
        )
        study = make_study(runs=(hardware_run,), metrics=())
        assert codes(validate_study_evidence_origin(study)) == ["NSF-305"]

    def test_empty_study_has_no_origin_conflict(self):
        study = make_study(runs=(), metrics=())
        assert validate_study_evidence_origin(study) == []


# ---------------------------------------------------------------------------
# Risks and reference plan
# ---------------------------------------------------------------------------


class TestRiskAndPlanValidation:
    def test_complete_risk_is_clean(self):
        risk = TechnicalRiskV1(
            risk_id="R1",
            title="Excitation variability",
            current_evidence="No repeated-excitation dataset exists.",
            unresolved_question="How much spread does the tap contribute?",
            phase_i_relevance="Bounds every other repeatability figure.",
            proposed_validation_method="Compare manual tap against a driven source.",
        )
        assert validate_technical_risk(risk) == []

    def test_risk_without_a_proposed_method_flagged(self):
        risk = TechnicalRiskV1(
            risk_id="R1",
            title="t",
            current_evidence="e",
            unresolved_question="q",
            phase_i_relevance="r",
            proposed_validation_method="   ",
        )
        assert codes(validate_technical_risk(risk)) == ["NSF-201"]

    def test_empty_reference_plan_flagged(self):
        plan = ReferenceValidationPlanV1(plan_id="ref-1", generated_at=UTC_NOW)
        assert codes(validate_reference_validation_plan(plan)) == ["NSF-201"]

    def test_plan_with_one_method_is_clean(self):
        plan = ReferenceValidationPlanV1(
            plan_id="ref-1",
            generated_at=UTC_NOW,
            methods=(
                ReferenceMethodV1(
                    method="Calibrated microphone",
                    measurement_compared="Sound pressure level",
                    access_status="Not yet sourced",
                ),
            ),
        )
        assert validate_reference_validation_plan(plan) == []


# ---------------------------------------------------------------------------
# Persisted schemas
# ---------------------------------------------------------------------------


def load_schema(name: str) -> dict:
    return json.loads((REPO_ROOT / "contracts" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def audit_schema() -> dict:
    return load_schema("nsf_grant_readiness_audit_v1.schema.json")


@pytest.fixture(scope="module")
def study_schema() -> dict:
    return load_schema("ttp_preliminary_repeatability_study_v1.schema.json")


def make_audit() -> GrantReadinessAuditV1:
    return GrantReadinessAuditV1(
        audit_id="audit-1",
        generated_at=UTC_NOW,
        repository_commit="a01e973",
        capabilities=(
            CapabilityEvidenceV1(
                capability_id="phase1_tap_workflow",
                name="Phase 1 tap workflow",
                status=CapabilityStatus.IMPLEMENTED,
                implementation_paths=("tap_tone_pi/phase1/demo.py",),
                test_paths=("tests/test_phase1_demo.py",),
                hardware_verified=HardwareVerification.NOT_VERIFIED_ON_HARDWARE,
                notes="Exercised by synthetic impulse generation.",
            ),
        ),
        limitations=("No hardware campaign has been executed.",),
    )


class TestSchemasAreWellFormed:
    def test_audit_schema_is_draft_2020_12(self, audit_schema):
        jsonschema.Draft202012Validator.check_schema(audit_schema)

    def test_study_schema_is_draft_2020_12(self, study_schema):
        jsonschema.Draft202012Validator.check_schema(study_schema)

    def test_both_are_strict(self, audit_schema, study_schema):
        assert audit_schema["additionalProperties"] is False
        assert study_schema["additionalProperties"] is False

    def test_schema_version_constants_match_the_contracts(
        self, audit_schema, study_schema
    ):
        from tap_tone_pi.grant_readiness import (
            AUDIT_SCHEMA_VERSION,
            STUDY_SCHEMA_VERSION,
        )

        assert audit_schema["properties"]["schema_version"]["const"] == (
            AUDIT_SCHEMA_VERSION
        )
        assert study_schema["properties"]["schema_version"]["const"] == (
            STUDY_SCHEMA_VERSION
        )

    def test_metric_schema_carries_no_verdict_field(self, study_schema):
        properties = study_schema["properties"]["metrics"]["items"]["properties"]
        for key in properties:
            assert "accept" not in key
            assert "gate" not in key
            assert "verdict" not in key


class TestAuditSchemaValidation:
    def test_audit_validates(self, audit_schema):
        jsonschema.validate(make_audit().to_dict(), audit_schema)

    def test_unknown_field_rejected(self, audit_schema):
        payload = make_audit().to_dict()
        payload["confidence"] = 0.99
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, audit_schema)

    def test_invalid_status_rejected(self, audit_schema):
        payload = make_audit().to_dict()
        payload["capabilities"][0]["status"] = "MOSTLY_DONE"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, audit_schema)

    def test_absolute_host_path_rejected(self, audit_schema):
        payload = make_audit().to_dict()
        payload["capabilities"][0]["implementation_paths"] = ["/opt/ttp/demo.py"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, audit_schema)

    def test_windows_host_path_rejected(self, audit_schema):
        payload = make_audit().to_dict()
        payload["capabilities"][0]["test_paths"] = ["C:\\ttp\\tests\\test_x.py"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, audit_schema)

    def test_empty_notes_rejected(self, audit_schema):
        payload = make_audit().to_dict()
        payload["capabilities"][0]["notes"] = ""
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, audit_schema)


class TestStudySchemaValidation:
    def test_study_validates(self, study_schema):
        jsonschema.validate(make_study().to_dict(), study_schema)

    def test_round_trip_through_json_is_deterministic(self, study_schema):
        study = make_study()
        first = json.dumps(study.to_dict(), sort_keys=True, allow_nan=False)
        restored = RepeatabilityStudyV1.from_dict(json.loads(first))
        second = json.dumps(restored.to_dict(), sort_keys=True, allow_nan=False)
        assert first == second
        jsonschema.validate(json.loads(second), study_schema)

    def test_audit_round_trip_through_json(self, audit_schema):
        audit = make_audit()
        text = json.dumps(audit.to_dict(), sort_keys=True, allow_nan=False)
        assert GrantReadinessAuditV1.from_dict(json.loads(text)) == audit
        jsonschema.validate(json.loads(text), audit_schema)

    def test_unknown_field_rejected(self, study_schema):
        payload = make_study().to_dict()
        payload["accuracy_pct"] = 99.0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_metric_without_source_runs_rejected(self, study_schema):
        payload = make_study().to_dict()
        payload["metrics"][0]["source_run_ids"] = []
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_single_sample_metric_rejected(self, study_schema):
        payload = make_study().to_dict()
        payload["metrics"][0]["sample_count"] = 1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_unknown_rejection_reason_rejected(self, study_schema):
        payload = make_study().to_dict()
        payload["runs"][2]["rejection_reason"] = "OPERATOR_DISLIKED_IT"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_unknown_evidence_origin_rejected(self, study_schema):
        payload = make_study().to_dict()
        payload["evidence_origin"] = "REAL"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_single_planned_repeat_rejected(self, study_schema):
        payload = make_study().to_dict()
        payload["experiment_definition"]["planned_repeat_count"] = 1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, study_schema)

    def test_unknown_environment_serializes_as_null(self, study_schema):
        study = make_study(
            experiment_definition=make_definition(
                environmental_context=EnvironmentalContextV1()
            )
        )
        payload = study.to_dict()
        assert payload["experiment_definition"]["environmental_context"] == {
            "temp_c": None,
            "rh_pct": None,
            "specimen_moisture_pct": None,
            "ambient_noise_note": None,
        }
        jsonschema.validate(payload, study_schema)

    def test_no_host_paths_in_serialized_study(self):
        text = json.dumps(make_study().to_dict())
        assert "C:\\" not in text
        assert str(REPO_ROOT) not in text

    def test_allow_nan_false_holds(self):
        # allow_nan=False is what keeps a non-finite statistic from reaching a
        # report as the literal NaN, which no JSON reader agrees on.
        payload = make_study().to_dict()
        payload["metrics"][0]["mean"] = float("nan")
        with pytest.raises(ValueError):
            json.dumps(payload, allow_nan=False)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestSchemaRegistry:
    @pytest.fixture(scope="class")
    def registry(self) -> dict:
        path = REPO_ROOT / "contracts" / "schema_registry.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @pytest.mark.parametrize(
        "key",
        [
            "nsf_grant_readiness_audit",
            "ttp_preliminary_repeatability_study",
            "ttp_hardware_campaign",
        ],
    )
    def test_schema_is_registered(self, registry, key):
        entry = registry["schemas"][key]
        assert entry["owner"] == "grant-readiness-team"
        assert (REPO_ROOT / entry["path"]).exists()

    def test_owner_is_declared(self, registry):
        owner = registry["owners"]["grant-readiness-team"]
        assert set(owner["schemas"]) == {
            "nsf_grant_readiness_audit",
            "ttp_preliminary_repeatability_study",
            "ttp_hardware_campaign",
        }

    def test_existing_entries_untouched(self, registry):
        # DO-102 registers additively; it does not reorganize the registry.
        for key in ("phase2_grid", "repeatability_evidence", "guided_lab_session"):
            assert key in registry["schemas"]

    def test_every_registered_schema_version_const_matches_its_file(self, registry):
        for key in (
            "nsf_grant_readiness_audit",
            "ttp_preliminary_repeatability_study",
            "ttp_hardware_campaign",
        ):
            entry = registry["schemas"][key]
            schema = json.loads((REPO_ROOT / entry["path"]).read_text(encoding="utf-8"))
            assert (
                schema["properties"]["schema_version"]["const"]
                == entry["schema_version_const"]
            )
