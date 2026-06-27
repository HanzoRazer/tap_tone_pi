# INSTRUMENT CLASS: MEASUREMENT
"""Tests for luthiery formula targets (Dev Order 94).

Covers the LuthieryFormulaTargetV1 / LuthieryFormulaEvidenceLinkV1 contracts,
their helpers, and the additive viewer-pack export blocks. Also asserts that
no advisory or prescriptive language enters these measurement artifacts.
"""

import json
from pathlib import Path

import pytest

from scripts.phase2.export_viewer_pack_v1 import _build_manifest
from tap_tone_pi.luthiery import (
    LuthieryFormulaDomain,
    LuthieryFormulaEvidenceLinkV1,
    LuthieryFormulaTargetV1,
    create_luthiery_formula_target,
    link_formula_candidate_to_target,
)


#: Advisory/prescriptive terms that must never appear in these artifacts.
FORBIDDEN_TERMS = {
    "best",
    "optimal",
    "recommended",
    "approved",
    "use_this",
    "prescription",
}


def _make_target(**overrides) -> LuthieryFormulaTargetV1:
    kwargs = dict(
        target_id="target_top_001",
        domain=LuthieryFormulaDomain.TOP_GRADUATION.value,
        studied_variable_name="top_thickness_mm",
        response_variable_name="A0_Hz",
        covariate_names=("density_g_cm3", "E_L_GPa", "E_C_GPa", "humidity_pct"),
        experiment_design_id="design_001",
        campaign_id="campaign_001",
        notes="Top thickness against A0 frequency, covariates held controlled.",
    )
    kwargs.update(overrides)
    return create_luthiery_formula_target(**kwargs)


class TestLuthieryFormulaTarget:
    def test_formula_target_serializes(self):
        """to_dict() round-trips through JSON with all declared fields."""
        target = _make_target()
        d = target.to_dict()
        parsed = json.loads(json.dumps(d))

        assert parsed["schema_version"] == "luthiery_formula_target_v1"
        assert parsed["target_id"] == "target_top_001"
        assert parsed["domain"] == "top_graduation"
        assert parsed["studied_variable_name"] == "top_thickness_mm"
        assert parsed["response_variable_name"] == "A0_Hz"
        assert parsed["covariate_names"] == [
            "E_C_GPa",
            "E_L_GPa",
            "density_g_cm3",
            "humidity_pct",
        ]
        assert parsed["experiment_design_id"] == "design_001"
        assert parsed["campaign_id"] == "campaign_001"
        assert parsed["epistemic_status"] == "derived"

    def test_formula_target_requires_known_domain(self):
        """An unknown domain is rejected."""
        with pytest.raises(ValueError):
            create_luthiery_formula_target(
                target_id="t",
                domain="not_a_domain",
                studied_variable_name="x",
                response_variable_name="y",
            )

    def test_formula_target_requires_studied_variable(self):
        """An empty studied variable name is rejected."""
        with pytest.raises(ValueError):
            create_luthiery_formula_target(
                target_id="t",
                domain=LuthieryFormulaDomain.BRACING.value,
                studied_variable_name="",
                response_variable_name="y",
            )

    def test_formula_target_requires_response_variable(self):
        """An empty response variable name is rejected."""
        with pytest.raises(ValueError):
            create_luthiery_formula_target(
                target_id="t",
                domain=LuthieryFormulaDomain.BRACING.value,
                studied_variable_name="x",
                response_variable_name="",
            )

    def test_covariates_are_sorted(self):
        """Covariate names are sorted deterministically regardless of input order."""
        target = create_luthiery_formula_target(
            target_id="t",
            domain=LuthieryFormulaDomain.SOUNDHOLE.value,
            studied_variable_name="soundhole_area_mm2",
            response_variable_name="A0_Hz",
            covariate_names=["humidity_pct", "density_g_cm3", "E_L_GPa"],
        )
        assert target.covariate_names == ("E_L_GPa", "density_g_cm3", "humidity_pct")

    def test_formula_evidence_link_serializes(self):
        """Evidence link to_dict() round-trips and inherits target lineage."""
        target = _make_target()
        link = link_formula_candidate_to_target(
            link_id="link_001",
            target=target,
            formula_id="formula_001",
            regression_evidence_id="ev_001",
        )
        d = link.to_dict()
        parsed = json.loads(json.dumps(d))

        assert isinstance(link, LuthieryFormulaEvidenceLinkV1)
        assert parsed["schema_version"] == "luthiery_formula_evidence_link_v1"
        assert parsed["link_id"] == "link_001"
        assert parsed["target_id"] == "target_top_001"
        assert parsed["formula_id"] == "formula_001"
        assert parsed["regression_evidence_id"] == "ev_001"
        assert parsed["experiment_design_id"] == "design_001"
        assert parsed["campaign_id"] == "campaign_001"
        assert parsed["epistemic_status"] == "derived"

    def test_formula_target_contains_no_advisory_language(self):
        """Serialized target+link must not contain advisory/prescriptive terms."""
        target = _make_target()
        link = link_formula_candidate_to_target(
            link_id="link_001",
            target=target,
            formula_id="formula_001",
        )
        blob = (json.dumps(target.to_dict()) + json.dumps(link.to_dict())).lower()
        for term in FORBIDDEN_TERMS:
            assert term not in blob, f"forbidden term '{term}' present in artifact"

    def test_formula_target_supports_top_graduation_domain(self):
        target = _make_target(domain=LuthieryFormulaDomain.TOP_GRADUATION.value)
        assert target.domain == "top_graduation"

    def test_formula_target_supports_bracing_domain(self):
        target = _make_target(
            domain=LuthieryFormulaDomain.BRACING.value,
            studied_variable_name="brace_height_mm",
            response_variable_name="top_mobility",
        )
        assert target.domain == "bracing"

    def test_formula_target_supports_soundhole_domain(self):
        target = _make_target(
            domain=LuthieryFormulaDomain.SOUNDHOLE.value,
            studied_variable_name="soundhole_area_mm2",
        )
        assert target.domain == "soundhole"

    def test_formula_target_supports_bridge_domain(self):
        target = _make_target(
            domain=LuthieryFormulaDomain.BRIDGE.value,
            studied_variable_name="bridge_mass_g",
            response_variable_name="T11_2_Hz",
        )
        assert target.domain == "bridge"

    def test_formula_target_supports_body_air_and_plate_stiffness_domains(self):
        body_air = _make_target(domain=LuthieryFormulaDomain.BODY_AIR.value)
        plate = _make_target(domain=LuthieryFormulaDomain.PLATE_STIFFNESS.value)
        assert body_air.domain == "body_air"
        assert plate.domain == "plate_stiffness"


class TestLuthieryExportIntegration:
    def test_phase2_export_includes_optional_luthiery_formula_blocks(self):
        """_build_manifest embeds the luthiery blocks when supplied, omits otherwise."""
        target = _make_target()
        link = link_formula_candidate_to_target(
            link_id="link_001",
            target=target,
            formula_id="formula_001",
            regression_evidence_id="ev_001",
        )

        # When supplied → present in manifest
        manifest = _build_manifest(
            [],
            Path("session_test"),
            [],
            luthiery_formula_target=target.to_dict(),
            luthiery_formula_evidence_link=link.to_dict(),
        )
        assert manifest["luthiery_formula_target"]["target_id"] == "target_top_001"
        assert manifest["luthiery_formula_evidence_link"]["formula_id"] == "formula_001"

        # When omitted → absent (historical exports remain valid)
        manifest_bare = _build_manifest([], Path("session_test"), [])
        assert "luthiery_formula_target" not in manifest_bare
        assert "luthiery_formula_evidence_link" not in manifest_bare
