# INSTRUMENT CLASS: MEASUREMENT
"""Compatibility tests: luthiery imports and serialization stay unchanged (DO-101A)."""

from __future__ import annotations

import json

import pytest

from tap_tone_pi.empirical.luthiery_compat import (
    empirical_model_from_luthiery_target,
    evidence_reference_from_luthiery_link,
)
from tap_tone_pi.luthiery import (
    FormulaValidationEnvelopeV1,
    LuthieryFormulaDomain,
    LuthieryFormulaEvidenceLinkV1,
    LuthieryFormulaTargetV1,
    create_luthiery_formula_target,
    link_formula_candidate_to_target,
    validate_formula_candidate,
)
from tap_tone_pi.luthiery import formula_validation as luthiery_formula_validation
from tap_tone_pi.empirical import formula_validation as empirical_formula_validation
from tap_tone_pi.empirical.contracts import FormulaValidationEnvelopeV1 as EmpEnvelope


def _make_target(**overrides) -> LuthieryFormulaTargetV1:
    kwargs = dict(
        target_id="target_top_001",
        domain=LuthieryFormulaDomain.TOP_GRADUATION.value,
        studied_variable_name="top_thickness_mm",
        response_variable_name="A0_Hz",
        covariate_names=("density_g_cm3", "E_L_GPa"),
        experiment_design_id="design_001",
        campaign_id="campaign_001",
        notes="Top thickness against A0 frequency.",
    )
    kwargs.update(overrides)
    return create_luthiery_formula_target(**kwargs)


class TestLuthieryImportCompatibility:
    def test_public_luthiery_symbols_still_resolve(self):
        assert LuthieryFormulaTargetV1 is not None
        assert LuthieryFormulaEvidenceLinkV1 is not None
        assert FormulaValidationEnvelopeV1 is EmpEnvelope
        assert (
            luthiery_formula_validation.validate_formula_candidate
            is empirical_formula_validation.validate_formula_candidate
        )

    def test_luthiery_target_serialization_unchanged(self):
        target = _make_target()
        payload = target.to_dict()
        assert payload == {
            "schema_version": "luthiery_formula_target_v1",
            "target_id": "target_top_001",
            "domain": "top_graduation",
            "studied_variable_name": "top_thickness_mm",
            "response_variable_name": "A0_Hz",
            "covariate_names": ["E_L_GPa", "density_g_cm3"],
            "epistemic_status": "derived",
            "experiment_design_id": "design_001",
            "campaign_id": "campaign_001",
            "notes": "Top thickness against A0 frequency.",
        }
        # JSON round-trip must remain stable.
        assert json.loads(json.dumps(payload)) == payload

    def test_luthiery_link_serialization_unchanged(self):
        target = _make_target()
        link = link_formula_candidate_to_target(
            link_id="link_001",
            target=target,
            formula_id="formula_001",
            regression_evidence_id="reg_001",
        )
        payload = link.to_dict()
        assert payload["schema_version"] == "luthiery_formula_evidence_link_v1"
        assert payload["target_id"] == "target_top_001"
        assert payload["formula_id"] == "formula_001"
        assert payload["regression_evidence_id"] == "reg_001"
        assert payload["experiment_design_id"] == "design_001"
        assert payload["campaign_id"] == "campaign_001"
        assert payload["epistemic_status"] == "derived"

    def test_envelope_serialization_unchanged(self):
        envelope = validate_formula_candidate(
            validation_id="val_001",
            formula_id="formula_001",
            sample_count=3,
            minimum_sample_count=10,
            process_variance_available=False,
            repeatability_available=True,
            covariates_present=True,
            residual_std_available=True,
            r_squared_available=True,
        )
        payload = envelope.to_dict()
        assert payload["schema_version"] == "formula_validation_envelope_v1"
        assert payload["sample_count_sufficient"] is False
        assert "sample count below declared minimum" in payload["validation_notes"]
        assert "process variance evidence absent" in payload["validation_notes"]
        assert payload["epistemic_status"] == "derived"


class TestLuthieryProjection:
    def test_target_projects_to_empirical_model(self):
        target = _make_target()
        model = empirical_model_from_luthiery_target(target)
        assert model.model_id == "target_top_001"
        assert model.version == 1
        assert model.domain == "top_graduation"
        assert [i.name for i in model.inputs] == [
            "top_thickness_mm",
            "E_L_GPa",
            "density_g_cm3",
        ]
        assert [o.name for o in model.outputs] == ["A0_Hz"]
        assert model.measurement_links[0].experiment_design_id == "design_001"
        # Projection must not mutate the original target serialization.
        assert target.to_dict()["schema_version"] == "luthiery_formula_target_v1"

    def test_link_projects_to_evidence_reference(self):
        target = _make_target()
        link = link_formula_candidate_to_target(
            link_id="link_001",
            target=target,
            formula_id="formula_001",
            regression_evidence_id="reg_001",
        )
        ref = evidence_reference_from_luthiery_link(link)
        assert ref.reference_id == "link_001"
        assert ref.kind == "luthiery_formula_evidence_link"
        assert ref.formula_id == "formula_001"
        assert ref.regression_evidence_id == "reg_001"

    def test_projection_rejects_advisory_notes_from_target(self):
        with pytest.raises(Exception):
            # create_luthiery_formula_target itself does not scan advisory terms;
            # the empirical projection does.
            target = _make_target(notes="recommended thickness relationship")
            empirical_model_from_luthiery_target(target)
