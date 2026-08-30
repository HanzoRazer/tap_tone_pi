"""Published contract: schema, registry, and semantic invariants (DO-107A Commit 6).

**The contract is capable of representing evidence-grade acquisition budgets. It
is not itself validated, evidence-grade, or publication-ready** — an individual
instance earns or fails evidence grade on its own inputs and computation
conditions, and publishing the schema asserts nothing about any instrument.

The four representative payloads below are the publication acceptance gate. The
one that matters most is the third: a `true` grade that still carries an advisory
condition, which proves the schema does not encode today's limitations as
restrictions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tap_tone_pi.uncertainty.acquisition import (
    SCHEMA_FILE,
    SCHEMA_VERSION,
    AcquisitionBudgetV1,
    AggregateContributor,
    ClockSpec,
    ConverterSpec,
    FormulaStatus,
    FrequencyBudget,
    ModulusBudget,
    FrontEndSpec,
    Provenance,
    Quantity,
    UnavailableSection,
    validate_acquisition_budget,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_acquisition_budget_composition import (  # noqa: E402
    fully_measured,
    ttp_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / SCHEMA_FILE
REGISTRY_PATH = REPO_ROOT / "contracts" / "schema_registry.json"

Q = Quantity
P = Provenance


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(payload, schema) -> None:
    import jsonschema

    jsonschema.validate(payload, schema)


# ---------------------------------------------------------------------------
# The four representative payloads
# ---------------------------------------------------------------------------


def payload_1_current_ttp() -> dict:
    """Today's TTP profile. Not evidence-grade, and says exactly why."""
    return ttp_profile().computed().as_dict()


def payload_2_noise_only_measured() -> dict:
    """A fully measured signal path. Evidence-grade, and legitimately so."""
    M = P.MEASURED
    return (
        AcquisitionBudgetV1(
            profile="noise_path_fully_measured",
            converter=ConverterSpec(
                name="ADC",
                bits=24,
                full_scale_vrms=Q(2.05, "Vrms", M, "E0 T6"),
                thermal_snr_db=Q(108.0, "dB", M, "E0 T1"),
                aperture_jitter_s=Q(9e-13, "s", M, "E0"),
                sample_rate_hz=Q(48000.0, "Hz", M, "E0"),
                hp_corner_hz=Q(18.5, "Hz", M, "E0 T3"),
                anti_alias_filter=True,
            ),
            clock=ClockSpec(
                name="xo",
                rms_jitter_s=Q(4e-12, "s", M, "E0"),
                accuracy_ppm=Q(1.2, "ppm", M, "E0"),
            ),
            front_end=FrontEndSpec(
                name="pre",
                input_referred_noise_v_per_rthz=Q(1.1e-9, "V/rtHz", M, "measured"),
                gain_db=Q(52.0, "dB", M, "measured"),
                bandwidth_hz=Q(20000.0, "Hz", M, "measured"),
            ),
        )
        .computed(f_in_hz=1000.0)
        .as_dict()
    )


DO_107A_AGGREGATION = "canonical_components_with_B022_aggregate_workaround"


def payload_3_reconciled_with_advisory() -> dict:
    """A DO-107A-era record: reconciled frequency, B-022 workaround still on it.

    Constructed by hand: an established formula and a contributor set with no
    duplication. B-022 has since been repaired at the canonical authority, so
    no live computation emits this aggregation identity any more -- which is
    exactly what this fixture is for. Records written while it did must keep
    validating, deserializing and grading, otherwise repairing a defect would
    silently invalidate the results that disclosed it.
    """
    base = fully_measured()
    reconciled = FrequencyBudget(
        mode_frequency_hz=base.frequency.mode_frequency_hz,
        clock_error_hz=base.frequency.clock_error_hz,
        bin_width_hz=base.frequency.bin_width_hz,
        estimator_floor_hz=base.frequency.estimator_floor_hz,
        physical_repeatability_hz=base.frequency.physical_repeatability_hz,
        combined_hz=(1.0**2 + 2.0**2 + 3.0**2) ** 0.5,
        dominant="physical_repeatability",
        combined_contributors=(
            AggregateContributor("clock_accuracy", "clock_error_hz", 1.0),
            AggregateContributor("spectral_resolution", "bin_width_hz", 2.0),
            AggregateContributor(
                "physical_repeatability", "physical_repeatability_hz", 3.0
            ),
        ),
        estimator_floor_status=FormulaStatus.ESTABLISHED,
    )
    return AcquisitionBudgetV1(
        profile="reconciled_frequency_fixture",
        converter=base.converter,
        clock=base.clock,
        capture=base.capture,
        specimen=base.specimen,
        noise=base.noise,
        frequency=reconciled,
        modulus=ModulusBudget(
            relative_uncertainty=base.modulus.relative_uncertainty,
            contributions=dict(base.modulus.contributions),
            dominant=base.modulus.dominant,
            smallest_resolvable_delta_pct=base.modulus.smallest_resolvable_delta_pct,
            component_authority=base.modulus.component_authority,
            aggregation=DO_107A_AGGREGATION,
            notes=base.modulus.notes,
        ),
        sweep_limits=base.sweep_limits,
        self_test=base.self_test,
        clock_topology=base.clock_topology,
    ).as_dict()


def payload_4_modulus_unavailable() -> dict:
    """The instrument-safe environment: modulus could not be computed."""
    base = ttp_profile().computed()
    return AcquisitionBudgetV1(
        profile="instrument_safe_no_modulus",
        converter=base.converter,
        clock=base.clock,
        front_end=base.front_end,
        capture=base.capture,
        sweep=base.sweep,
        specimen=base.specimen,
        noise=base.noise,
        frequency=base.frequency,
        modulus=UnavailableSection(
            reason_code="canonical_authority_unavailable",
            reason=(
                "canonical uncertainty authority unavailable in the "
                "instrument-safe environment"
            ),
        ),
        sweep_limits=base.sweep_limits,
        self_test=base.self_test,
        clock_topology=base.clock_topology,
    ).as_dict()


ALL_PAYLOADS = {
    "1_current_ttp": payload_1_current_ttp,
    "2_noise_only_measured": payload_2_noise_only_measured,
    "3_reconciled_with_advisory": payload_3_reconciled_with_advisory,
    "4_modulus_unavailable": payload_4_modulus_unavailable,
}


class TestThePublicationGate:
    @pytest.mark.parametrize("name", sorted(ALL_PAYLOADS))
    def test_every_representative_payload_is_schema_valid(self, name, schema):
        validate(ALL_PAYLOADS[name](), schema)

    @pytest.mark.parametrize("name", sorted(ALL_PAYLOADS))
    def test_every_representative_payload_is_semantically_consistent(self, name):
        assert validate_acquisition_budget(ALL_PAYLOADS[name]()) == []

    @pytest.mark.parametrize("name", sorted(ALL_PAYLOADS))
    def test_every_representative_payload_round_trips_losslessly(self, name):
        payload = json.loads(json.dumps(ALL_PAYLOADS[name]()))
        assert AcquisitionBudgetV1.from_dict(payload).as_dict() == payload

    # --- payload 1 ---------------------------------------------------------

    def test_1_current_ttp_is_not_evidence_grade_and_names_the_blockers(self):
        evidence = payload_1_current_ttp()["evidence"]
        assert evidence["evidence_grade"] is False
        blocking = {
            r["reference"]
            for r in evidence["reasons"]
            if r["blocking"] and r["reference"]
        }
        assert {"B-020", "B-021"} <= blocking

    # --- payload 2 ---------------------------------------------------------

    def test_2_noise_only_measured_is_evidence_grade(self):
        # Not a test-only escape hatch: a fully measured signal path with a
        # filter fitted genuinely has nothing outstanding.
        evidence = payload_2_noise_only_measured()["evidence"]
        assert evidence["evidence_grade"] is True
        assert evidence["reasons"] == []

    def test_2_proves_true_is_a_reachable_scientific_state(self, schema):
        # Without this, "unreachable because the mathematics is unresolved" would
        # be indistinguishable from "unreachable because the grading function is
        # permanently false".
        payload = payload_2_noise_only_measured()
        validate(payload, schema)
        assert payload["results"]["frequency"] is None
        assert payload["results"]["modulus"] is None

    # --- payload 3 ---------------------------------------------------------

    def test_3_is_evidence_grade_while_retaining_the_advisory(self):
        payload = payload_3_reconciled_with_advisory()
        assert payload["results"]["modulus"]["aggregation"] == DO_107A_AGGREGATION
        evidence = payload["evidence"]
        assert evidence["evidence_grade"] is True
        advisory = [r for r in evidence["reasons"] if not r["blocking"]]
        assert [r["condition"] for r in advisory] == ["aggregate_authority_workaround"]
        assert advisory[0]["reference"] == "B-022"

    def test_3_shows_the_schema_permits_true_with_advisory_reasons(self, schema):
        # The schema must not encode today's limitations as restrictions.
        validate(payload_3_reconciled_with_advisory(), schema)

    # --- payload 4 ---------------------------------------------------------

    def test_4_carries_no_fabricated_modulus_number(self):
        modulus = payload_4_modulus_unavailable()["results"]["modulus"]
        assert modulus["availability"] == "unavailable"
        assert modulus["reason_code"] == "canonical_authority_unavailable"
        assert not any(
            isinstance(v, (int, float)) and not isinstance(v, bool)
            for v in modulus.values()
        )

    def test_4_round_trips_as_an_unavailable_section(self):
        restored = AcquisitionBudgetV1.from_dict(payload_4_modulus_unavailable())
        assert isinstance(restored.modulus, UnavailableSection)


class TestTheSchemaPermitsWhatItMust:
    def test_duplicate_contributors_are_legal(self, schema):
        # B-021 is deliberately represented, not repaired. A contract that
        # refused to serialize the computation's actual state would force a
        # choice between lying and staying silent.
        payload = payload_1_current_ttp()
        sources = [
            c["source_quantity"]
            for c in payload["results"]["frequency"]["combined_contributors"]
        ]
        assert sources.count("estimator_floor_hz") == 2
        validate(payload, schema)

    def test_both_evidence_outcomes_validate(self, schema):
        validate(payload_1_current_ttp(), schema)
        validate(payload_2_noise_only_measured(), schema)

    def test_the_estimator_status_is_not_promoted_to_crb_terminology(self, schema):
        blob = json.dumps(schema).lower()
        for banned in ("cramer-rao", "crlb", "cramer_rao"):
            if banned in blob:
                assert "not named" in blob or "deliberately not" in blob

    def test_the_schema_does_not_claim_to_be_validated(self, schema):
        description = schema["description"].lower()
        assert "capable of representing" in description
        assert "neither validated nor evidence-grade" in description


class TestSemanticInvariants:
    """Checks that would be unreadable in JSON Schema, kept in Python."""

    def test_a_true_grade_with_a_blocking_reason_is_refused(self):
        payload = payload_2_noise_only_measured()
        payload["evidence"]["reasons"] = [
            {
                "condition": "provisional_formula",
                "blocking": True,
                "detail": "x",
                "reference": "B-020",
            }
        ]
        problems = validate_acquisition_budget(payload)
        assert any("evidence_grade is true while" in p for p in problems)

    def test_a_false_grade_with_no_blocking_reason_is_refused(self):
        payload = payload_2_noise_only_measured()
        payload["evidence"]["evidence_grade"] = False
        problems = validate_acquisition_budget(payload)
        assert any("must say what blocked it" in p for p in problems)

    def test_a_combined_hz_that_disagrees_with_its_contributors_is_refused(self):
        payload = payload_1_current_ttp()
        payload["results"]["frequency"]["combined_hz"] *= 1.5
        problems = validate_acquisition_budget(payload)
        assert any("root-sum-square of its own contributors" in p for p in problems)

    def test_removing_a_material_contributor_is_refused(self):
        payload = payload_1_current_ttp()
        contributors = payload["results"]["frequency"]["combined_contributors"]
        dominant = max(
            range(len(contributors)), key=lambda i: contributors[i]["value_hz"]
        )
        contributors.pop(dominant)
        assert validate_acquisition_budget(payload)

    def test_removing_a_negligible_contributor_is_not_detectable_numerically(self):
        """A limitation of the RSS check, recorded rather than papered over.

        Dropping the estimator term from the TTP profile moves the root-sum-square
        by parts in 10^10 — far below any tolerance a floating-point comparison
        can use. The aggregate simply cannot police a term that contributes
        nothing to it.

        This is precisely why B-021 is represented as a **contributor sequence**
        rather than being inferred from the combined figure. The structural
        record catches what the arithmetic cannot: the estimator appearing twice
        and the bin width never, regardless of how small the numbers are.
        """
        payload = payload_1_current_ttp()
        contributors = payload["results"]["frequency"]["combined_contributors"]
        negligible = min(
            range(len(contributors)), key=lambda i: contributors[i]["value_hz"]
        )
        assert contributors[negligible]["source_quantity"] == "estimator_floor_hz"
        contributors.pop(negligible)

        # The RSS invariant stays silent, and honestly so.
        assert validate_acquisition_budget(payload) == []
        # The structural evidence is what changed and what a reader can see.
        remaining = [c["source_quantity"] for c in contributors]
        assert remaining.count("estimator_floor_hz") == 1

    def test_an_unavailable_section_carrying_a_number_is_refused(self):
        payload = payload_4_modulus_unavailable()
        payload["results"]["modulus"]["relative_uncertainty"] = 0.0
        problems = validate_acquisition_budget(payload)
        assert any("fabricates nothing" in p for p in problems)

    def test_an_undisclosed_noncanonical_aggregation_is_refused(self):
        payload = payload_1_current_ttp()
        # Live computation is canonical again, so the non-canonical state this
        # rule polices has to be constructed to be tested.
        payload["results"]["modulus"]["aggregation"] = DO_107A_AGGREGATION
        payload["evidence"]["reasons"] = [
            r
            for r in payload["evidence"]["reasons"]
            if r["condition"] != "aggregate_authority_workaround"
        ]
        problems = validate_acquisition_budget(payload)
        assert any("no aggregate_authority_workaround" in p for p in problems)

    def test_a_canonical_aggregation_needs_no_disclosure(self):
        payload = payload_1_current_ttp()
        payload["results"]["modulus"]["aggregation"] = "canonical"
        payload["evidence"]["reasons"] = [
            r
            for r in payload["evidence"]["reasons"]
            if r["condition"] != "aggregate_authority_workaround"
        ]
        assert not any(
            "aggregate_authority_workaround" in p
            for p in validate_acquisition_budget(payload)
        )

    def test_a_wrong_schema_version_is_refused(self):
        payload = payload_1_current_ttp()
        payload["schema_version"] = "acquisition_budget_v2"
        assert any("schema_version" in p for p in validate_acquisition_budget(payload))


class TestRegistry:
    @pytest.fixture(scope="class")
    def registry(self):
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_the_schema_is_registered_additively(self, registry):
        entry = registry["schemas"]["acquisition_budget"]
        assert entry["file"] == SCHEMA_FILE
        assert entry["schema_version_const"] == SCHEMA_VERSION
        assert (REPO_ROOT / entry["path"]).exists()

    def test_no_existing_registry_entry_was_disturbed(self, registry):
        for name in ("bending_stiffness", "e0_adc_characterization", "viewer_pack"):
            if name in registry["schemas"]:
                assert (REPO_ROOT / registry["schemas"][name]["path"]).exists()

    def test_every_registered_path_resolves(self, registry):
        unresolved = [
            name
            for name, entry in registry["schemas"].items()
            if not (REPO_ROOT / entry["path"]).exists()
        ]
        assert unresolved == []


class TestContractMachineryDoesNotContaminateTheInstrumentPath:
    """The schema arrived; the stdlib boundary must be exactly where it was."""

    @staticmethod
    def _modules_after(statement: str) -> set[str]:
        program = (
            "import sys\n"
            f"{statement}\n"
            "print(','.join(m for m in ('numpy','scipy','pandas','jsonschema') "
            "if m in sys.modules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", program], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        return {m for m in result.stdout.strip().split(",") if m}

    @pytest.mark.parametrize(
        "statement",
        [
            "import tap_tone_pi.uncertainty.acquisition",
            "from tap_tone_pi.uncertainty.acquisition import AcquisitionBudgetV1",
            "from tap_tone_pi.uncertainty.acquisition import validate_acquisition_budget",
        ],
    )
    def test_nothing_heavy_is_pulled_in(self, statement):
        assert self._modules_after(statement) == set()

    def test_the_validator_runs_with_numpy_and_jsonschema_unavailable(self):
        program = f"""
import sys

class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("numpy", "scipy", "pandas", "jsonschema"):
            raise ImportError(f"{{name}} is deliberately unavailable")
        return None

sys.meta_path.insert(0, _Blocker())
sys.path.insert(0, {str(REPO_ROOT)!r})

from tap_tone_pi.uncertainty.acquisition import (
    ClockSpec, ConverterSpec, FrontEndSpec, Provenance, Quantity,
    AcquisitionBudgetV1, validate_acquisition_budget,
)
Q, P, M = Quantity, Provenance, Provenance.MEASURED
budget = AcquisitionBudgetV1(
    profile="noise_path_fully_measured",
    converter=ConverterSpec(name="ADC", bits=24,
        full_scale_vrms=Q(2.05,"Vrms",M), thermal_snr_db=Q(108.0,"dB",M),
        aperture_jitter_s=Q(9e-13,"s",M), sample_rate_hz=Q(48000.0,"Hz",M),
        hp_corner_hz=Q(18.5,"Hz",M), anti_alias_filter=True),
    clock=ClockSpec(name="xo", rms_jitter_s=Q(4e-12,"s",M), accuracy_ppm=Q(1.2,"ppm",M)),
    front_end=FrontEndSpec(name="pre",
        input_referred_noise_v_per_rthz=Q(1.1e-9,"V/rtHz",M),
        gain_db=Q(52.0,"dB",M), bandwidth_hz=Q(20000.0,"Hz",M)),
).computed(f_in_hz=1000.0)

payload = budget.as_dict()
problems = validate_acquisition_budget(payload)
assert not problems, problems
assert "numpy" not in sys.modules and "jsonschema" not in sys.modules
print(payload["evidence"]["evidence_grade"])
"""
        result = subprocess.run(
            [sys.executable, "-c", program], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        # An instrument with neither NumPy nor jsonschema can still compute a
        # budget and check its own semantic consistency.
        assert result.stdout.strip() == "True"
