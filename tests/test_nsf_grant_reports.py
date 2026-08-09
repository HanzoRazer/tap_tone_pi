"""Grant-readiness reports, pitch source, and scripts (DO-102, Commit 7).

The reports are constrained in what they may say, so most of this suite is
about vocabulary and refusals: no accuracy claim, no calibration claim, no
market language, and no way to render fixture data as a hardware result.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness import (
    EvidenceOrigin,
    GrantReadinessErrorCode,
    ObservedFeatureV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
    RepeatabilityStudyV1,
)
from tap_tone_pi.grant_readiness.audit import build_grant_readiness_audit
from tap_tone_pi.grant_readiness.errors import RepeatabilityStatisticsError
from tap_tone_pi.grant_readiness.experiment import build_repeatability_study
from tap_tone_pi.grant_readiness.pitch_source import (
    HUMAN_INPUT,
    MARKET_PLACEHOLDER_FIELDS,
    TEAM_PLACEHOLDER_FIELDS,
    build_pitch_source_packet,
    render_pitch_source,
)
from tap_tone_pi.grant_readiness.report import (
    REPEATABILITY_IS_NOT_ACCURACY,
    SD_CONVENTION,
    build_audit_report,
    build_study_report,
    canonical_json,
    render_audit_report,
    render_risk_register,
    render_study_report,
)
from tap_tone_pi.grant_readiness.risks import (
    REFERENCE_METHODS,
    TECHNICAL_RISKS,
    build_reference_validation_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC_NOW = "2026-08-09T12:00:00+00:00"

# Language a grant report must never contain unsupported. Each is checked as a
# phrase rather than a bare word so ordinary use ("no comparison against a
# reference method has been performed") is not a false positive.
FORBIDDEN_PHRASES = (
    "accurate to",
    "accuracy of",
    "is calibrated",
    "validated against",
    "laboratory-equivalent",
    "certified",
    "proven accurate",
    "industry-leading",
    "market opportunity of",
    "revenue",
    "customers will",
)


def make_audit():
    return build_grant_readiness_audit(
        audit_id="audit-1", generated_at=UTC_NOW, repository_commit="b7715b2"
    )


def make_definition(**overrides) -> PreliminaryExperimentDefinitionV1:
    kwargs = {
        "experiment_id": "exp-001",
        "instrument_id": "guitar-top-A",
        "measurement_point_id": "P1",
        "operator_id": "op-1",
        "planned_repeat_count": 5,
        "created_at": UTC_NOW,
    }
    kwargs.update(overrides)
    return PreliminaryExperimentDefinitionV1(**kwargs)


def make_run(run_id: str, value: float, *, valid: bool = True):
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="exp-001",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=valid,
        rejection_reason=None if valid else RejectionReason.CLIPPING,
        source_artifact_ids=(f"analysis-{run_id}.json",),
        observed_features=(
            (ObservedFeatureV1("dominant_frequency", "Hz", value),) if valid else ()
        ),
    )


def make_study(**overrides) -> RepeatabilityStudyV1:
    kwargs = {
        "study_id": "study-1",
        "definition": make_definition(),
        "runs": (
            make_run("run-001", 244.0),
            make_run("run-002", 245.0),
            make_run("run-003", 246.0),
            make_run("run-004", 0.0, valid=False),
        ),
        "generated_at": UTC_NOW,
        "evidence_origin": EvidenceOrigin.FIXTURE,
    }
    kwargs.update(overrides)
    return build_repeatability_study(**kwargs)


def assert_no_forbidden_language(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in lowered, phrase


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_canonical_json_is_stable(self):
        assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})

    def test_canonical_json_refuses_nan(self):
        with pytest.raises(ValueError):
            canonical_json({"a": float("nan")})

    def test_audit_markdown_is_reproducible(self):
        assert render_audit_report(make_audit()) == render_audit_report(make_audit())

    def test_study_markdown_is_reproducible(self):
        assert render_study_report(make_study()) == render_study_report(make_study())

    def test_audit_report_carries_a_digest(self):
        report = build_audit_report(make_audit())
        assert len(report["audit_digest"]) == 64

    def test_study_report_carries_a_digest(self):
        report = build_study_report(make_study())
        assert len(report["study_digest"]) == 64


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------


class TestAuditReport:
    @pytest.fixture(scope="class")
    def markdown(self) -> str:
        return render_audit_report(make_audit())

    def test_reports_run_counts_per_status(self, markdown):
        assert "| IMPLEMENTED |" in markdown
        assert "| EXPERIMENTAL |" in markdown
        assert "| PARTIAL |" in markdown
        assert "| PLANNED |" in markdown

    def test_names_the_hardware_verification_section(self, markdown):
        assert "## Hardware verification status" in markdown
        assert "NOT_VERIFIED_ON_HARDWARE" in markdown
        assert "has not been witnessed" in markdown

    def test_states_the_deferred_campaign(self, markdown):
        assert "deferred execution gate that has not run" in markdown

    def test_lists_limitations(self, markdown):
        assert "## What this audit does not establish" in markdown

    def test_records_the_commit(self, markdown):
        assert "b7715b2" in markdown

    def test_uses_no_unsupported_language(self, markdown):
        assert_no_forbidden_language(markdown)

    def test_every_capability_appears(self, markdown):
        for capability in make_audit().capabilities:
            assert capability.capability_id in markdown

    def test_empty_status_section_says_so(self, markdown):
        # Nothing is PLANNED in this repository, and the report must say that
        # rather than silently omitting the heading.
        assert "No capability currently carries PLANNED status." in markdown


# ---------------------------------------------------------------------------
# Study report
# ---------------------------------------------------------------------------


class TestStudyReport:
    @pytest.fixture(scope="class")
    def markdown(self) -> str:
        return render_study_report(make_study())

    def test_run_accounting_is_reported(self, markdown):
        assert "- Runs recorded: 4" in markdown
        assert "- Valid: 3" in markdown
        assert "- Rejected: 1" in markdown

    def test_rejected_runs_appear_in_the_table(self, markdown):
        assert "| `run-004` | no | CLIPPING |" in markdown

    def test_rejection_counts_are_broken_out(self, markdown):
        assert "| CLIPPING | 1 |" in markdown

    def test_metrics_are_reported_with_their_source_runs(self, markdown):
        assert "| dominant_frequency | Hz | 3 | 245 |" in markdown
        assert "`run-001`, `run-002`, `run-003`" in markdown

    def test_repeatability_is_distinguished_from_accuracy(self, markdown):
        assert REPEATABILITY_IS_NOT_ACCURACY in markdown
        assert "not accuracy" in markdown.lower()

    def test_standard_deviation_convention_is_stated(self, markdown):
        assert SD_CONVENTION in markdown
        assert "Bessel" in markdown

    def test_limitations_are_reported(self, markdown):
        assert "## Limitations" in markdown

    def test_unknown_conditions_are_shown_as_unknown(self, markdown):
        assert "- Temperature (C): unknown" in markdown
        assert "not corrected for" in markdown

    def test_excitation_is_reported_generically(self, markdown):
        assert "- Method: `unspecified`" in markdown
        assert "- Contact condition:" in markdown
        assert "- Fixture:" in markdown

    def test_uses_no_unsupported_language(self, markdown):
        assert_no_forbidden_language(markdown)


class TestNonHardwareLabelling:
    """No generated report may present fixture data as hardware evidence."""

    def test_title_marks_non_hardware_evidence(self):
        markdown = render_study_report(make_study())
        assert markdown.startswith(
            "# Preliminary Repeatability Study (Non-Hardware Evidence)"
        )

    def test_banner_states_it_plainly(self):
        markdown = render_study_report(make_study())
        assert "**This study is not hardware evidence.**" in markdown

    def test_origin_is_reported_in_the_header(self):
        markdown = render_study_report(make_study())
        assert "Evidence origin: **FIXTURE**" in markdown
        assert "not hardware evidence" in markdown

    def test_synthetic_origin_is_labelled_too(self):
        study = RepeatabilityStudyV1(
            study_id="s",
            experiment_definition=make_definition(),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.SYNTHETIC,
        )
        markdown = render_study_report(study)
        assert "(Non-Hardware Evidence)" in markdown
        assert "SYNTHETIC" in markdown

    def test_json_report_flags_it_structurally(self):
        report = build_study_report(make_study())
        assert report["is_hardware_evidence"] is False
        assert report["evidence_origin"] == "FIXTURE"

    def test_rendering_a_mislabelled_study_is_refused(self):
        # A study object can be constructed claiming HARDWARE over fixture runs
        # by bypassing the builder. The renderer must still refuse it.
        mislabelled = RepeatabilityStudyV1(
            study_id="s",
            experiment_definition=make_definition(),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.HARDWARE,
            runs=(make_run("run-001", 244.0),),
        )
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            render_study_report(mislabelled)
        assert exc.value.code is GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED

    def test_json_report_of_a_mislabelled_study_is_refused(self):
        mislabelled = RepeatabilityStudyV1(
            study_id="s",
            experiment_definition=make_definition(),
            generated_at=UTC_NOW,
            evidence_origin=EvidenceOrigin.HARDWARE,
            runs=(make_run("run-001", 244.0),),
        )
        with pytest.raises(RepeatabilityStatisticsError):
            build_study_report(mislabelled)


class TestEmptyStudyReport:
    def test_no_metrics_is_reported_as_a_result(self):
        study = make_study(
            runs=(
                make_run("run-001", 0.0, valid=False),
                make_run("run-002", 0.0, valid=False),
            )
        )
        markdown = render_study_report(study)
        assert "no statistic is reported" in markdown.replace("\n", " ")
        assert "This is a result, not an omission." in markdown
        assert "- Rejected: 2" in markdown


# ---------------------------------------------------------------------------
# Risk register and reference plan
# ---------------------------------------------------------------------------


class TestRiskRegister:
    def test_every_required_risk_is_present(self):
        ids = {risk.risk_id for risk in TECHNICAL_RISKS}
        assert ids == {f"R{n}" for n in range(1, 11)}

    def test_every_risk_states_all_four_parts(self):
        for risk in TECHNICAL_RISKS:
            assert risk.current_evidence.strip()
            assert risk.unresolved_question.strip()
            assert risk.phase_i_relevance.strip()
            assert risk.proposed_validation_method.strip()

    def test_every_risk_is_open(self):
        # Closing one requires a hardware campaign that has not run.
        assert all(risk.status.value == "OPEN" for risk in TECHNICAL_RISKS)

    def test_markdown_renders_each_part(self):
        markdown = render_risk_register(TECHNICAL_RISKS)
        assert "**What is known.**" in markdown
        assert "**What is unknown.**" in markdown
        assert "**Proposed test.**" in markdown
        for risk in TECHNICAL_RISKS:
            assert f"## {risk.risk_id} — {risk.title}" in markdown

    def test_register_uses_no_unsupported_language(self):
        assert_no_forbidden_language(render_risk_register(TECHNICAL_RISKS))


class TestReferenceValidationPlan:
    def test_plan_names_prospective_methods(self):
        plan = build_reference_validation_plan(plan_id="ref-1", generated_at=UTC_NOW)
        assert len(plan.methods) == len(REFERENCE_METHODS)
        assert plan.notes

    def test_no_partner_is_invented(self):
        for method in REFERENCE_METHODS:
            assert "TBD" in method.potential_partner

    def test_plan_states_that_nothing_has_been_compared(self):
        plan = build_reference_validation_plan(plan_id="ref-1", generated_at=UTC_NOW)
        text = " ".join(plan.notes).lower()
        assert "no comparison" in text
        assert "prospective" in text


# ---------------------------------------------------------------------------
# Pitch source
# ---------------------------------------------------------------------------


def make_packet(study=None):
    return build_pitch_source_packet(
        packet_id="packet-1",
        generated_at=UTC_NOW,
        audit=make_audit(),
        study=study,
    )


class TestPitchSource:
    def test_technology_and_objectives_are_populated(self):
        packet = make_packet()
        assert packet.technology_innovation_evidence
        assert packet.technical_objectives_evidence

    def test_every_statement_cites_evidence(self):
        packet = make_packet()
        for statement in (
            *packet.technology_innovation_evidence,
            *packet.technical_objectives_evidence,
        ):
            assert statement.evidence_refs

    def test_market_fields_are_placeholders_only(self):
        packet = make_packet()
        assert set(packet.market_claim_placeholders) == set(MARKET_PLACEHOLDER_FIELDS)
        assert set(packet.market_claim_placeholders.values()) == {HUMAN_INPUT}

    def test_team_fields_are_placeholders_only(self):
        packet = make_packet()
        assert set(packet.team_evidence_placeholders) == set(TEAM_PLACEHOLDER_FIELDS)
        assert set(packet.team_evidence_placeholders.values()) == {HUMAN_INPUT}

    def test_no_market_or_team_claim_is_fabricated(self):
        markdown = render_pitch_source(make_packet())
        market_section = markdown.split("## 3. Market Opportunity")[1]
        assert "no market claim is derivable" in market_section.lower()
        assert market_section.count(HUMAN_INPUT) == len(
            MARKET_PLACEHOLDER_FIELDS
        ) + len(TEAM_PLACEHOLDER_FIELDS)

    def test_hardware_status_is_stated_in_the_technology_section(self):
        statements = " ".join(
            s.statement for s in make_packet().technology_innovation_evidence
        )
        assert "0 of 25 are hardware-verified" in statements.replace("\n", " ")

    def test_no_success_threshold_is_invented(self):
        markdown = render_pitch_source(make_packet())
        assert "none has a success threshold attached" in markdown
        assert "sets no target repeatability" in markdown

    def test_study_evidence_is_marked_non_hardware(self):
        statements = " ".join(
            s.statement
            for s in make_packet(make_study()).technology_innovation_evidence
        )
        assert "This is not hardware evidence." in statements

    def test_packet_without_a_study_still_builds(self):
        packet = make_packet()
        assert "study" not in packet.source_digests
        assert "audit" in packet.source_digests

    def test_all_four_headings_render(self):
        markdown = render_pitch_source(make_packet())
        for heading in (
            "## 1. Technology Innovation",
            "## 2. Technical Objectives and Challenges",
            "## 3. Market Opportunity",
            "## 4. Company and Team",
        ):
            assert heading in markdown

    def test_document_disclaims_being_a_submission(self):
        assert "**This is not a submission.**" in render_pitch_source(make_packet())

    def test_uses_no_unsupported_language(self):
        assert_no_forbidden_language(render_pitch_source(make_packet()))

    def test_packet_is_deterministic(self):
        assert canonical_json(make_packet().to_dict()) == canonical_json(
            make_packet().to_dict()
        )


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------


def run_script(name: str, *args: str, cwd: Path | None = None):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / name), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
        timeout=120,
    )


class TestAuditScript:
    def test_check_passes_against_this_repository(self):
        result = run_script("nsf_ttp_audit.py", "--check")
        assert result.returncode == 0, result.stderr
        assert "clean" in result.stdout

    def test_write_produces_both_artifacts(self, tmp_path):
        result = run_script(
            "nsf_ttp_audit.py", "--write", "--output-dir", str(tmp_path)
        )
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "ttp_technical_baseline.json").exists()
        assert (tmp_path / "ttp_technical_baseline.md").exists()

    def test_written_json_carries_the_audit_and_digest(self, tmp_path):
        run_script("nsf_ttp_audit.py", "--write", "--output-dir", str(tmp_path))
        payload = json.loads(
            (tmp_path / "ttp_technical_baseline.json").read_text(encoding="utf-8")
        )
        assert payload["report_type"] == "nsf_ttp_technical_baseline"
        assert len(payload["audit_digest"]) == 64
        assert payload["audit"]["schema_version"] == "nsf_grant_readiness_audit_v1"

    def test_written_audit_validates_against_its_schema(self, tmp_path):
        jsonschema = pytest.importorskip("jsonschema")
        run_script("nsf_ttp_audit.py", "--write", "--output-dir", str(tmp_path))
        payload = json.loads(
            (tmp_path / "ttp_technical_baseline.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            (
                REPO_ROOT / "contracts" / "nsf_grant_readiness_audit_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.validate(payload["audit"], schema)

    def test_requires_a_mode(self):
        assert run_script("nsf_ttp_audit.py").returncode != 0


class TestRepeatabilityScript:
    def _fixture_run(self, path: Path, dominant: float) -> None:
        payload = {
            "schema_version": "phase1_tap_analysis_v1",
            "timestamp_utc": UTC_NOW,
            "sample_rate": 48000,
            "analysis": {
                "dominant_hz": dominant,
                "peaks": [{"freq_hz": dominant, "magnitude": 0.8}],
                "clipped": False,
                "rms": 0.1,
                "confidence": 0.9,
                "confidence_components": {"snr_db": 30.0},
            },
            "quality": {"verdict": "pass", "policy_version": "v1"},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _setup(self, tmp_path: Path) -> tuple[Path, Path]:
        runs = tmp_path / "runs"
        runs.mkdir()
        for index, dominant in enumerate((244.0, 245.0, 246.0), start=1):
            self._fixture_run(runs / f"analysis_{index}.json", dominant)

        experiment = tmp_path / "experiment.json"
        experiment.write_text(json.dumps(make_definition().to_dict()), encoding="utf-8")
        return experiment, runs

    def test_analyzes_a_run_directory(self, tmp_path):
        experiment, runs = self._setup(tmp_path)
        result = run_script(
            "nsf_ttp_repeatability.py",
            "--experiment",
            str(experiment),
            "--runs",
            str(runs),
        )
        assert result.returncode == 0, result.stderr
        assert "Runs recorded: 3" in result.stdout
        assert "valid:    3" in result.stdout

    def test_defaults_to_fixture_origin_and_says_so(self, tmp_path):
        experiment, runs = self._setup(tmp_path)
        result = run_script(
            "nsf_ttp_repeatability.py",
            "--experiment",
            str(experiment),
            "--runs",
            str(runs),
        )
        assert "evidence origin is FIXTURE" in result.stdout
        assert "not hardware evidence" in result.stdout

    def test_write_produces_a_labelled_report(self, tmp_path):
        experiment, runs = self._setup(tmp_path)
        out = tmp_path / "out"
        result = run_script(
            "nsf_ttp_repeatability.py",
            "--experiment",
            str(experiment),
            "--runs",
            str(runs),
            "--write",
            "--output-dir",
            str(out),
        )
        assert result.returncode == 0, result.stderr
        markdown = (out / "ttp_preliminary_repeatability_study.md").read_text(
            encoding="utf-8"
        )
        assert "(Non-Hardware Evidence)" in markdown

    def test_missing_run_directory_fails_cleanly(self, tmp_path):
        experiment, _ = self._setup(tmp_path)
        result = run_script(
            "nsf_ttp_repeatability.py",
            "--experiment",
            str(experiment),
            "--runs",
            str(tmp_path / "absent"),
        )
        assert result.returncode == 2
        assert "Run directory not found" in result.stderr
        assert "Traceback" not in result.stderr

    def test_no_capture_mode_exists(self):
        source = (REPO_ROOT / "scripts" / "nsf_ttp_repeatability.py").read_text(
            encoding="utf-8"
        )
        assert "--capture" not in source
        assert "sounddevice" not in source


class TestPitchSourceScript:
    def test_builds_without_a_study(self, tmp_path):
        result = run_script(
            "nsf_ttp_build_pitch_source.py", "--write", "--output-dir", str(tmp_path)
        )
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "ttp_pitch_source.json").exists()
        assert (tmp_path / "ttp_pitch_source.md").exists()
        assert (tmp_path / "ttp_phase_i_technical_risks.md").exists()

    def test_reports_the_placeholder_count(self, tmp_path):
        result = run_script(
            "nsf_ttp_build_pitch_source.py", "--output-dir", str(tmp_path)
        )
        expected = len(MARKET_PLACEHOLDER_FIELDS) + len(TEAM_PLACEHOLDER_FIELDS)
        assert f"placeholders awaiting an answer: {expected}" in result.stdout

    def test_written_packet_keeps_market_fields_empty(self, tmp_path):
        run_script(
            "nsf_ttp_build_pitch_source.py", "--write", "--output-dir", str(tmp_path)
        )
        payload = json.loads(
            (tmp_path / "ttp_pitch_source.json").read_text(encoding="utf-8")
        )
        assert set(payload["market_claim_placeholders"].values()) == {HUMAN_INPUT}
        assert set(payload["team_evidence_placeholders"].values()) == {HUMAN_INPUT}

    def test_written_markdown_uses_no_unsupported_language(self, tmp_path):
        run_script(
            "nsf_ttp_build_pitch_source.py", "--write", "--output-dir", str(tmp_path)
        )
        assert_no_forbidden_language(
            (tmp_path / "ttp_pitch_source.md").read_text(encoding="utf-8")
        )
