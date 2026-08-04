# INSTRUMENT CLASS: MEASUREMENT
"""BR-045 — tonewood radiation-ratio interoperability contract (Tap Tone Pi)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import jsonschema
import pytest

from tap_tone_pi.bending.gore_spreadsheet import (
    BuildSpreadsheetEntry,
    _compute_derived_properties,
)
from tap_tone_pi.bending.radiation_ratio import (
    CONTRACT_SCHEMA_VERSION,
    FORMULA_ID,
    FORMULA_VERSION,
    OUTPUT_CONVENTION,
    ROUNDING_DECIMALS,
    SCALE_FACTOR,
    RadiationRatioError,
    calculate_radiation_ratio,
    calculate_radiation_ratio_from_modulus,
    calculate_radiation_ratio_from_modulus_gpa,
    formula_identity,
    load_radiation_ratio_contract,
    normalize_radiation_ratio_contract,
    radiation_ratio_contract_digest,
    require_matching_semantic_digest,
    wave_speed_m_s_from_modulus_pa,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "contracts" / "tonewood_radiation_ratio_v1.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "tonewood_radiation_ratio_v1.schema.json"
REGISTRY_PATH = REPO_ROOT / "contracts" / "schema_registry.json"

# Approved V1 semantic digest — CI fails if fixtures/formula semantics drift.
APPROVED_SEMANTIC_DIGEST = (
    "182320dadca871d767fbd7e2341cfbb237a492e88dacddfc0736bc323ed9b898"
)


def _approx(
    a: float, b: float, *, abs_tol: float = 1e-9, rel_tol: float = 1e-9
) -> bool:
    return math.isclose(a, b, abs_tol=abs_tol, rel_tol=rel_tol)


class TestRadiationRatioContractIdentity:
    def test_contract_loads_and_matches_schema(self) -> None:
        contract = load_radiation_ratio_contract()
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=contract, schema=schema)

    def test_registry_resolves_schema(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        entry = registry["schemas"]["tonewood_radiation_ratio_contract"]
        assert entry["schema_version_const"] == CONTRACT_SCHEMA_VERSION
        assert (REPO_ROOT / entry["path"]).is_file()
        assert (
            "tonewood_radiation_ratio_contract"
            in registry["owners"]["governance-team"]["schemas"]
        )

    def test_formula_identity_and_scale(self) -> None:
        contract = load_radiation_ratio_contract()
        assert contract["formula_id"] == FORMULA_ID
        assert contract["formula_version"] == FORMULA_VERSION
        assert contract["scale_factor"] == SCALE_FACTOR
        assert contract["output_convention"] == OUTPUT_CONVENTION
        assert contract["rounding_decimals"] == ROUNDING_DECIMALS
        assert contract["canonical_expression"] == "wave_speed_m_s / density_kg_m3"
        assert (
            "sqrt(dynamic_modulus_pa / density_kg_m3^3)"
            in contract["equivalent_expressions"]
        )

    def test_semantic_digest_stable_and_approved(self) -> None:
        contract = load_radiation_ratio_contract()
        digest = require_matching_semantic_digest(contract)
        assert digest == APPROVED_SEMANTIC_DIGEST
        assert radiation_ratio_contract_digest(contract) == APPROVED_SEMANTIC_DIGEST

    def test_provenance_excluded_from_digest(self) -> None:
        contract = load_radiation_ratio_contract()
        with_provenance = dict(contract)
        with_provenance["authority_repository"] = "HanzoRazer/luthiers-toolbox"
        with_provenance["authority_commit"] = "deadbeef"
        with_provenance["synchronized_at"] = "2026-08-04T00:00:00Z"
        assert (
            radiation_ratio_contract_digest(with_provenance) == APPROVED_SEMANTIC_DIGEST
        )

    def test_unknown_property_rejected_by_schema(self) -> None:
        contract = load_radiation_ratio_contract()
        bad = dict(contract)
        bad["unexpected_field"] = True
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=bad, schema=schema)

    def test_normalize_sorts_fixtures(self) -> None:
        contract = load_radiation_ratio_contract()
        shuffled = dict(contract)
        fixtures = list(shuffled["conformance_fixtures"])
        shuffled["conformance_fixtures"] = list(reversed(fixtures))
        normalized = normalize_radiation_ratio_contract(shuffled)
        ids = [f["fixture_id"] for f in normalized["conformance_fixtures"]]
        assert ids == sorted(ids)


class TestRadiationRatioCalculation:
    def test_fixtures_both_equivalent_expressions(self) -> None:
        contract = load_radiation_ratio_contract()
        for fixture in contract["conformance_fixtures"]:
            rho = fixture["density_kg_m3"]
            e_pa = fixture["dynamic_modulus_pa"]
            c = wave_speed_m_s_from_modulus_pa(
                dynamic_modulus_pa=e_pa,
                density_kg_m3=rho,
            )
            from_c = calculate_radiation_ratio(
                wave_speed_m_s=c,
                density_kg_m3=rho,
            )
            from_e = calculate_radiation_ratio_from_modulus(
                dynamic_modulus_pa=e_pa,
                density_kg_m3=rho,
            )
            from_gpa = calculate_radiation_ratio_from_modulus_gpa(
                dynamic_modulus_gpa=fixture["dynamic_modulus_gpa"],
                density_kg_m3=rho,
            )
            assert _approx(from_c, fixture["expected_radiation_ratio"])
            assert _approx(from_e, fixture["expected_radiation_ratio"])
            assert _approx(from_gpa, fixture["expected_radiation_ratio"])
            assert _approx(from_c, from_e)
            assert (
                round(from_c, ROUNDING_DECIMALS)
                == fixture["expected_radiation_ratio_rounded"]
            )

    def test_reference_display_values(self) -> None:
        contract = load_radiation_ratio_contract()
        by_id = {f["fixture_id"]: f for f in contract["conformance_fixtures"]}
        assert (
            by_id["american_basswood_reference"]["expected_radiation_ratio_rounded"]
            == 11.87
        )
        assert (
            by_id["western_red_cedar_reference"]["expected_radiation_ratio_rounded"]
            == 12.39
        )
        assert by_id["bubinga_reference"]["expected_radiation_ratio_rounded"] == 5.11

    def test_no_hidden_scale_factor(self) -> None:
        rr = calculate_radiation_ratio(
            wave_speed_m_s=4925.957799348656, density_kg_m3=415.0
        )
        assert rr < 20.0
        assert rr > 5.0
        assert not _approx(rr, rr * 1000.0)
        assert not _approx(rr, rr * 1e6)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"wave_speed_m_s": 0.0, "density_kg_m3": 415.0},
            {"wave_speed_m_s": -1.0, "density_kg_m3": 415.0},
            {"wave_speed_m_s": 1000.0, "density_kg_m3": 0.0},
            {"wave_speed_m_s": 1000.0, "density_kg_m3": -10.0},
            {"wave_speed_m_s": float("nan"), "density_kg_m3": 415.0},
            {"wave_speed_m_s": float("inf"), "density_kg_m3": 415.0},
        ],
    )
    def test_invalid_speed_density_rejected(self, kwargs: dict) -> None:
        with pytest.raises(RadiationRatioError):
            calculate_radiation_ratio(**kwargs)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"dynamic_modulus_pa": 0.0, "density_kg_m3": 415.0},
            {"dynamic_modulus_pa": -1.0, "density_kg_m3": 415.0},
            {"dynamic_modulus_pa": 1e10, "density_kg_m3": 0.0},
            {"dynamic_modulus_pa": float("nan"), "density_kg_m3": 415.0},
        ],
    )
    def test_invalid_modulus_rejected(self, kwargs: dict) -> None:
        with pytest.raises(RadiationRatioError):
            calculate_radiation_ratio_from_modulus(**kwargs)

    def test_formula_identity_metadata(self) -> None:
        meta = formula_identity()
        assert meta == {
            "formula_id": FORMULA_ID,
            "formula_version": FORMULA_VERSION,
            "output_convention": OUTPUT_CONVENTION,
            "scale_factor": SCALE_FACTOR,
        }


class TestGoreSpreadsheetConformity:
    def test_gore_path_matches_helper_rounding(self) -> None:
        """Historical Gore rounding preserved; numerical scale unchanged."""
        entry = BuildSpreadsheetEntry(
            specimen_id="rr-fixture",
            direction="L",
            timestamp_utc="2026-08-04T00:00:00Z",
            thickness_mm=3.0,
        )
        density = 415.0
        e_gpa = 10.07
        _compute_derived_properties(entry, e_gpa, density)
        unrounded = calculate_radiation_ratio_from_modulus_gpa(
            dynamic_modulus_gpa=e_gpa,
            density_kg_m3=density,
        )
        assert entry.radiation_ratio == round(unrounded, 4)
        assert entry.radiation_ratio == pytest.approx(11.8698, abs=5e-5)

    def test_no_runtime_cross_repo_import(self) -> None:
        import sys

        import tap_tone_pi.bending.radiation_ratio as rr_mod

        forbidden_prefixes = ("luthiers_toolbox", "services.api")
        forbidden = {
            name for name in sys.modules if name.startswith(forbidden_prefixes)
        }
        assert not forbidden
        # Module must remain stdlib + local only (no foreign package import).
        source = Path(rr_mod.__file__).read_text(encoding="utf-8")
        assert "import luthiers" not in source
        assert "from luthiers" not in source
