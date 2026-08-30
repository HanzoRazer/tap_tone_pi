"""Composition, evidence grading and self-test policy (DO-107A Commit 5).

The line held here: **a budget is not an evidence grade.** The engine must
produce a genuinely useful design-stage budget full of ``PROPOSED`` values while
truthfully refusing to call it evidence — that is what makes it usable before the
hardware exists without letting design intentions become measurement claims.

Evidence grade reads **two independent axes**. Inputs can be excellent while the
computation carries an unresolved authority condition, and a settled computation
can consume proposed inputs. Each failure names which axis it came from.
"""

from __future__ import annotations

import json

import pytest

from tap_tone_pi.uncertainty.acquisition import (
    ACQUISITION_BUDGET_SCHEMA_VERSION,
    AcquisitionBudgetV1,
    CaptureSpec,
    ClockSpec,
    ConverterSpec,
    EvidenceCondition,
    FrontEndSpec,
    ModulusBudget,
    Provenance,
    Quantity,
    ResultAvailability,
    SelfTestThresholdPolicy,
    SpecimenSpec,
    SweepSpec,
    UnavailableSection,
)

Q = Quantity
P = Provenance


def ttp_profile(**overrides) -> AcquisitionBudgetV1:
    """The worked TTP profile. A design-stage budget, not evidence."""
    base = dict(
        profile="ttp_analyzer_phase2b",
        converter=ConverterSpec(
            name="HiFiBerry DAC+ ADC Pro",
            bits=24,
            full_scale_vrms=Q(2.1, "Vrms", P.DATASHEET, "Rev 1.5"),
            thermal_snr_db=Q(110.0, "dB", P.DATASHEET, "Rev 1.5 typ."),
            aperture_jitter_s=Q(1e-12, "s", P.PROPOSED, "pending E0/T4"),
            sample_rate_hz=Q(48000.0, "Hz", P.DATASHEET, "Rev 1.5"),
        ),
        clock=ClockSpec(
            name="local xo",
            rms_jitter_s=Q(5e-12, "s", P.PROPOSED, "no vendor figure"),
            accuracy_ppm=Q(20.0, "ppm", P.ASSUMED, "typical XO grade"),
        ),
        front_end=FrontEndSpec(
            name="OPA1612",
            input_referred_noise_v_per_rthz=Q(1.1e-9, "V/rtHz", P.DATASHEET, "OPA1612"),
            gain_db=Q(52.0, "dB", P.PROPOSED, "MID; prototype hypothesis"),
            bandwidth_hz=Q(20000.0, "Hz", P.ASSUMED, "declared band"),
        ),
        capture=CaptureSpec(
            record_length_s=Q(4.0, "s", P.ASSUMED, "working default"),
            sample_rate_hz=Q(48000.0, "Hz", P.DATASHEET, "Rev 1.5"),
        ),
        sweep=SweepSpec(
            f_start_hz=Q(60.0, "Hz", P.ASSUMED, "below lowest plate mode"),
            f_stop_hz=Q(2000.0, "Hz", P.ASSUMED, "top of declared band"),
            expected_q=Q(50.0, "-", P.PROPOSED, "braced top"),
        ),
        specimen=SpecimenSpec(
            name="spruce top plate, mode 2",
            mode_frequency_hz=Q(187.0, "Hz", P.ASSUMED, "worked example"),
            length_m=Q(0.5, "m", P.ASSUMED, "worked example"),
            length_uncertainty_m=Q(5e-4, "m", P.ASSUMED, "steel rule"),
            thickness_m=Q(0.0028, "m", P.ASSUMED, "worked example"),
            thickness_uncertainty_m=Q(2e-5, "m", P.ASSUMED, "digital caliper"),
            density_kg_m3=Q(420.0, "kg/m3", P.ASSUMED, "worked example"),
            density_uncertainty_kg_m3=Q(4.0, "kg/m3", P.ASSUMED, "mass and volume"),
        ),
    )
    base.update(overrides)
    return AcquisitionBudgetV1(**base)


DO_107A_AGGREGATION = "canonical_components_with_B022_aggregate_workaround"


def with_historical_b022(budget: AcquisitionBudgetV1) -> AcquisitionBudgetV1:
    """Re-stamp a budget's modulus with the DO-107A-era aggregation identity.

    B-022 is repaired at the canonical authority, so no live computation
    produces this state any more. Records written while it did must still
    deserialize, still grade, and still disclose their advisory condition --
    otherwise repairing a defect would silently rewrite the history of results
    that carried it. Constructed explicitly here, never computed.
    """
    return AcquisitionBudgetV1(
        profile=budget.profile,
        converter=budget.converter,
        clock=budget.clock,
        capture=budget.capture,
        specimen=budget.specimen,
        noise=budget.noise,
        frequency=budget.frequency,
        modulus=ModulusBudget(
            relative_uncertainty=budget.modulus.relative_uncertainty,
            contributions=dict(budget.modulus.contributions),
            dominant=budget.modulus.dominant,
            smallest_resolvable_delta_pct=(
                budget.modulus.smallest_resolvable_delta_pct
            ),
            component_authority=budget.modulus.component_authority,
            aggregation=DO_107A_AGGREGATION,
            notes=budget.modulus.notes,
        ),
        sweep_limits=budget.sweep_limits,
        self_test=budget.self_test,
        clock_topology=budget.clock_topology,
    )


def fully_measured() -> AcquisitionBudgetV1:
    """A hypothetical instrument where every input has been measured.

    Used to ask what remains blocking when the *input* axis is fully satisfied.
    """
    M = P.MEASURED
    return AcquisitionBudgetV1(
        profile="hypothetical_fully_measured",
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
        capture=CaptureSpec(
            record_length_s=Q(4.0, "s", M, "session"),
            sample_rate_hz=Q(48000.0, "Hz", M, "session"),
        ),
        specimen=SpecimenSpec(
            name="plate",
            mode_frequency_hz=Q(187.0, "Hz", M, "session"),
            length_m=Q(0.5, "m", M, "caliper"),
            length_uncertainty_m=Q(5e-5, "m", M, "caliper"),
            thickness_m=Q(0.0028, "m", M, "caliper"),
            thickness_uncertainty_m=Q(2e-6, "m", M, "caliper"),
            density_kg_m3=Q(420.0, "kg/m3", M, "mass and volume"),
            density_uncertainty_kg_m3=Q(1.0, "kg/m3", M, "mass and volume"),
            physical_repeatability_hz=Q(0.4, "Hz", M, "E2"),
        ),
    ).computed()


class TestComposition:
    @pytest.fixture(scope="class")
    def budget(self):
        return ttp_profile().computed()

    def test_every_section_is_present(self, budget):
        assert budget.noise is not None
        assert budget.frequency is not None
        assert budget.modulus is not None
        assert budget.sweep_limits is not None
        assert budget.self_test is not None
        assert budget.clock_topology

    def test_computed_returns_a_copy_rather_than_mutating(self):
        original = ttp_profile()
        computed = original.computed()
        assert original.noise is None
        assert computed.noise is not None
        assert computed is not original

    def test_the_schema_version_is_fixed(self, budget):
        assert budget.schema_version == ACQUISITION_BUDGET_SCHEMA_VERSION
        assert budget.as_dict()["schema_version"] == "acquisition_budget_v1"

    def test_a_budget_without_a_specimen_still_computes_noise(self):
        # The Smart Guitar shape: a signal path, not a measurement chain.
        partial = ttp_profile(capture=None, sweep=None, specimen=None)
        computed = partial.computed(f_in_hz=20000.0)
        assert computed.noise is not None
        assert computed.frequency is None
        assert computed.modulus is None

    def test_a_budget_with_no_specimen_and_no_frequency_is_refused(self):
        with pytest.raises(ValueError, match="f_in_hz is required"):
            ttp_profile(specimen=None).computed()


class TestLosslessRoundTrip:
    """Commit 4's invariant, now at the top level."""

    @pytest.fixture(scope="class")
    def budget(self):
        return ttp_profile().computed()

    def test_the_whole_record_round_trips(self, budget):
        assert (
            AcquisitionBudgetV1.from_dict(budget.as_dict()).as_dict()
            == budget.as_dict()
        )

    def test_it_survives_json(self, budget):
        payload = json.loads(json.dumps(budget.as_dict()))
        assert AcquisitionBudgetV1.from_dict(payload).as_dict() == payload

    def test_nothing_is_rounded_on_the_contract_path(self, budget):
        # Rounding belongs to report rendering. A lossy payload cannot be
        # recomputed from, and precision loss baked into a published contract
        # cannot be taken back.
        payload = budget.as_dict()
        assert payload["results"]["modulus"]["relative_uncertainty"] == (
            budget.modulus.relative_uncertainty
        )
        assert (
            payload["results"]["noise"]["limiter_share"] == budget.noise.limiter_share
        )

    def test_input_provenance_survives_exactly(self, budget):
        restored = AcquisitionBudgetV1.from_dict(budget.as_dict())
        assert (
            restored.converter.aperture_jitter_s == budget.converter.aperture_jitter_s
        )
        assert restored.converter.aperture_jitter_s.provenance is Provenance.PROPOSED
        assert restored.converter.aperture_jitter_s.source == "pending E0/T4"

    def test_an_unmeasured_corner_survives_as_none(self, budget):
        restored = AcquisitionBudgetV1.from_dict(budget.as_dict())
        assert restored.converter.hp_corner_hz is None


class TestEvidenceGrade:
    @pytest.fixture(scope="class")
    def budget(self):
        return ttp_profile().computed()

    def test_the_design_stage_budget_is_useful_and_not_evidence(self, budget):
        # Both halves matter. It computed everything it could...
        assert budget.noise.limiter == "front_end"
        assert budget.modulus.relative_uncertainty > 0
        # ...and it refuses to call the result evidence.
        assert budget.evidence().evidence_grade is False

    def test_every_failure_says_which_condition_caused_it(self, budget):
        reasons = budget.evidence().reasons
        assert reasons
        for reason in reasons:
            assert isinstance(reason.condition, EvidenceCondition)
            assert reason.detail
        # No consumer should have to reverse-engineer this from note strings.
        assert all(r.detail != "" for r in reasons)

    def test_proposed_inputs_block(self, budget):
        conditions = {r.condition for r in budget.evidence().blockers}
        assert EvidenceCondition.PROPOSED_INPUTS in conditions

    def test_unmeasured_repeatability_blocks(self, budget):
        conditions = {r.condition for r in budget.evidence().blockers}
        assert EvidenceCondition.PHYSICAL_REPEATABILITY_UNMEASURED in conditions

    def test_b014_blocks_and_is_referenced(self, budget):
        reason = next(
            r
            for r in budget.evidence().reasons
            if r.condition is EvidenceCondition.NO_ANTI_ALIAS_FILTER
        )
        assert reason.blocking is True
        assert reason.reference == "B-014"

    def test_e3_a_computed_budget_reports_no_b022_condition(self, budget):
        """B-022 is repaired; the condition disappears because the state did.

        Not suppressed by name -- ``evidence()`` derives this reason from
        ``modulus.aggregation``, and the adapter now consumes the canonical
        aggregate, so there is no non-canonical state left to report.
        """
        assert budget.modulus.aggregation == "canonical"
        assert not [
            r
            for r in budget.evidence().reasons
            if r.condition is EvidenceCondition.AGGREGATE_AUTHORITY_WORKAROUND
        ]

    def test_a_historical_b022_record_still_reports_the_condition(self, budget):
        """The derivation reads state, so old records still grade correctly."""
        reason = next(
            r
            for r in with_historical_b022(budget).evidence().reasons
            if r.condition is EvidenceCondition.AGGREGATE_AUTHORITY_WORKAROUND
        )
        assert reason.reference == "B-022"
        # It is about the computation path, not about the inputs.
        assert "canonical" in reason.detail

    def test_the_b021_composition_defect_is_reported(self, budget):
        reason = next(
            r
            for r in budget.evidence().reasons
            if r.condition is EvidenceCondition.CONTRIBUTOR_COMPOSITION_DEFECT
        )
        assert reason.reference == "B-021"
        assert "more than once" in reason.detail

    def test_b020_is_reported_as_a_provisional_formula_not_as_a_foreign_bug(
        self, budget
    ):
        # DO-107 does not consume session_diff. What it does consume is an
        # expression whose authority is unresolved, and that is what is reported.
        reason = next(
            r
            for r in budget.evidence().reasons
            if r.condition is EvidenceCondition.PROVISIONAL_FORMULA
        )
        assert reason.reference == "B-020"
        assert "session_diff" not in reason.detail

    def test_the_reasons_round_trip(self, budget):
        payload = budget.as_dict()
        restored = AcquisitionBudgetV1.from_dict(payload)
        assert restored.evidence().as_dict() == budget.evidence().as_dict()

    def test_the_axes_are_independent(self):
        """Input quality and computation settledness are separate questions.

        With every input measured, the input-axis conditions clear completely and
        only computation-axis conditions remain. That separation is the point.
        """
        evidence = fully_measured().evidence()
        conditions = {r.condition for r in evidence.blockers}
        input_axis = {
            EvidenceCondition.PROPOSED_INPUTS,
            EvidenceCondition.ASSUMED_INPUTS,
            EvidenceCondition.PHYSICAL_REPEATABILITY_UNMEASURED,
            EvidenceCondition.NO_ANTI_ALIAS_FILTER,
            EvidenceCondition.COUPLING_CORNER_UNMEASURED,
        }
        assert not (conditions & input_axis), "input axis should be clear"
        assert conditions == {
            EvidenceCondition.PROVISIONAL_FORMULA,
            EvidenceCondition.CONTRIBUTOR_COMPOSITION_DEFECT,
        }

    def test_b022_is_advisory_not_blocking(self):
        """Authority debt, not a defect in the emitted result.

        The modulus adapter does **not** reproduce the bad canonical aggregate.
        It takes the component construction and sensitivities from the canonical
        authority and performs a correct generic RSS over them, and parity
        independently confirms agreement with the source calculator. What is
        unresolved is that the repository's nominal canonical aggregate
        disagrees — authority debt to be repaid in ``stiffness.py``, not a reason
        to withhold evidence grade from a correct number.

        Repairing B-022 removes this condition without changing the value.
        """
        reason = next(
            r
            for r in with_historical_b022(fully_measured()).evidence().reasons
            if r.condition is EvidenceCondition.AGGREGATE_AUTHORITY_WORKAROUND
        )
        assert reason.blocking is False
        assert reason.reference == "B-022"

    # --- the two tests replacing DO-107 section 8.G.49 --------------------
    #
    # G.49 expected qualified inputs to produce an evidence-grade budget
    # immediately. Grounding discovered structural computation blockers the
    # original order did not know existed, so that expectation is empirically
    # invalid. It is replaced by the pair below, which separate two very
    # different failures: "true is unreachable because the mathematics is
    # unresolved" from "true is unreachable because the grading function is
    # permanently false".

    def test_qualified_inputs_are_necessary_but_not_sufficient(self):
        """Every input qualifies, and the budget is still not evidence-grade.

        Exactly the two structural blockers remain — B-020's provisional formula
        and B-021's contributor-composition defect. Neither is about input
        quality, and neither shrinks because its numerical effect is small today:
        evidence grade states that the computation is valid, not that a known
        defect happens not to matter for the current profile.
        """
        evidence = fully_measured().evidence()
        assert evidence.evidence_grade is False
        assert {r.condition for r in evidence.blockers} == {
            EvidenceCondition.PROVISIONAL_FORMULA,
            EvidenceCondition.CONTRIBUTOR_COMPOSITION_DEFECT,
        }
        assert {r.reference for r in evidence.blockers} == {"B-020", "B-021"}

    def test_the_grading_function_can_return_true(self):
        """Proves the machinery works, not that today's budget is evidence-grade.

        A noise-only budget — the signal-path shape, no specimen and no capture —
        with every input measured, an anti-alias filter fitted and the coupling
        corner measured. There is no frequency section, so neither structural
        blocker applies, and nothing else is outstanding.

        Without this test a permanently-false grading function would be
        indistinguishable from unresolved mathematics.
        """
        M = Provenance.MEASURED
        budget = AcquisitionBudgetV1(
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
        ).computed(f_in_hz=1000.0)

        evidence = budget.evidence()
        assert evidence.blockers == (), [r.condition.value for r in evidence.blockers]
        assert evidence.evidence_grade is True

    def test_a_true_grade_still_reports_advisory_conditions(self):
        """An advisory condition neither suppresses a true grade nor vanishes.

        The frequency section here is constructed by hand rather than computed:
        an established formula and a contributor set with no duplication, which
        is what the mathematics looks like once B-020 and B-021 are reconciled.
        The modulus keeps its B-022 workaround.
        """
        from tap_tone_pi.uncertainty.acquisition import (
            AggregateContributor,
            FormulaStatus,
            FrequencyBudget,
        )

        base = fully_measured()
        reconciled = FrequencyBudget(
            mode_frequency_hz=base.frequency.mode_frequency_hz,
            clock_error_hz=base.frequency.clock_error_hz,
            bin_width_hz=base.frequency.bin_width_hz,
            estimator_floor_hz=base.frequency.estimator_floor_hz,
            physical_repeatability_hz=base.frequency.physical_repeatability_hz,
            combined_hz=base.frequency.combined_hz,
            dominant=base.frequency.dominant,
            combined_contributors=(
                AggregateContributor("clock_accuracy", "clock_error_hz", 1.0),
                AggregateContributor("spectral_resolution", "bin_width_hz", 2.0),
                AggregateContributor(
                    "physical_repeatability", "physical_repeatability_hz", 3.0
                ),
            ),
            estimator_floor_status=FormulaStatus.ESTABLISHED,
        )
        budget = AcquisitionBudgetV1(
            profile=base.profile,
            converter=base.converter,
            clock=base.clock,
            capture=base.capture,
            specimen=base.specimen,
            noise=base.noise,
            frequency=reconciled,
            modulus=base.modulus,
        )
        budget = with_historical_b022(budget)
        evidence = budget.evidence()
        assert evidence.evidence_grade is True
        advisory = [r for r in evidence.reasons if not r.blocking]
        assert [r.condition for r in advisory] == [
            EvidenceCondition.AGGREGATE_AUTHORITY_WORKAROUND
        ]
        assert advisory[0].reference == "B-022"


class TestUnavailableSectionSurvivesComposition:
    def test_an_unavailable_modulus_is_not_null_or_empty_or_zero(self):
        budget = ttp_profile().computed()
        replaced = AcquisitionBudgetV1(
            profile=budget.profile,
            converter=budget.converter,
            clock=budget.clock,
            front_end=budget.front_end,
            capture=budget.capture,
            sweep=budget.sweep,
            specimen=budget.specimen,
            noise=budget.noise,
            frequency=budget.frequency,
            modulus=UnavailableSection(
                reason_code="canonical_authority_unavailable",
                reason="canonical uncertainty authority unavailable in the "
                "instrument-safe environment",
            ),
            sweep_limits=budget.sweep_limits,
            self_test=budget.self_test,
            clock_topology=budget.clock_topology,
        )
        payload = replaced.as_dict()["results"]["modulus"]
        assert payload is not None
        assert payload != {}
        assert payload["availability"] == "unavailable"
        assert "reason_code" in payload
        assert not any(isinstance(v, (int, float)) for v in payload.values())

    def test_it_round_trips_as_an_unavailable_section(self):
        budget = ttp_profile().computed()
        replaced = AcquisitionBudgetV1(
            profile=budget.profile,
            converter=budget.converter,
            clock=budget.clock,
            capture=budget.capture,
            specimen=budget.specimen,
            noise=budget.noise,
            frequency=budget.frequency,
            modulus=UnavailableSection("canonical_authority_unavailable", "reason"),
        )
        restored = AcquisitionBudgetV1.from_dict(replaced.as_dict())
        assert isinstance(restored.modulus, UnavailableSection)
        assert restored.modulus.availability is ResultAvailability.UNAVAILABLE

    def test_an_available_modulus_round_trips_as_a_budget(self):
        budget = ttp_profile().computed()
        restored = AcquisitionBudgetV1.from_dict(budget.as_dict())
        assert isinstance(restored.modulus, ModulusBudget)
        assert restored.modulus.availability is ResultAvailability.AVAILABLE

    def test_an_unavailable_section_blocks_evidence_grade(self):
        budget = ttp_profile().computed()
        replaced = AcquisitionBudgetV1(
            profile=budget.profile,
            converter=budget.converter,
            clock=budget.clock,
            capture=budget.capture,
            specimen=budget.specimen,
            noise=budget.noise,
            frequency=budget.frequency,
            modulus=UnavailableSection("canonical_authority_unavailable", "reason"),
        )
        conditions = {r.condition for r in replaced.evidence().blockers}
        assert EvidenceCondition.SECTION_UNAVAILABLE in conditions


class TestSelfTestPolicy:
    @pytest.fixture(scope="class")
    def budget(self):
        return ttp_profile().computed()

    def test_the_margin_carries_its_own_provenance(self, budget):
        margin = budget.self_test.policy.allowed_margin_db
        assert margin.provenance is Provenance.PROPOSED
        assert float(margin) == 6.0

    def test_the_default_margin_is_not_a_scientific_constant(self, budget):
        # A bare default becomes a constant by attrition. This one has to say
        # what it is every time it is serialized.
        payload = budget.as_dict()["results"]["self_test"]
        assert payload["policy"]["allowed_margin_db"]["provenance"] == "proposed"

    def test_the_derived_threshold_is_marked_derived(self, budget):
        payload = budget.as_dict()["results"]["self_test"]
        assert payload["expected_noise_floor_provenance"] == "derived"
        assert payload["fail_above_provenance"] == "derived"

    def test_the_threshold_follows_the_budget(self, budget):
        assert budget.self_test.expected_noise_floor_dbfs == pytest.approx(
            -budget.noise.combined_snr_db
        )
        assert budget.self_test.fail_above_dbfs == pytest.approx(
            -budget.noise.combined_snr_db + 6.0
        )

    def test_a_measured_margin_can_replace_the_proposed_one(self):
        policy = SelfTestThresholdPolicy(
            allowed_margin_db=Q(3.5, "dB", Provenance.MEASURED, "40 healthy units")
        )
        budget = ttp_profile().computed(self_test_policy=policy)
        assert (
            budget.self_test.policy.allowed_margin_db.provenance is Provenance.MEASURED
        )
        assert budget.self_test.fail_above_dbfs == pytest.approx(
            -budget.noise.combined_snr_db + 3.5
        )

    def test_the_self_test_round_trips(self, budget):
        restored = AcquisitionBudgetV1.from_dict(budget.as_dict())
        assert restored.self_test.as_dict() == budget.self_test.as_dict()


class TestNoPrematureCompatibilityMachinery:
    def test_there_is_no_migration_or_version_negotiation_yet(self):
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1]
            / "tap_tone_pi"
            / "uncertainty"
            / "acquisition"
            / "budget.py"
        ).read_text(encoding="utf-8")
        # Commit 6 is the first irreversible publication point; there is nothing
        # published to be compatible with yet.
        for premature in ("migrate", "upgrade_from", "SUPPORTED_VERSIONS", "v2"):
            assert premature not in source

    def test_an_unknown_schema_version_is_refused_outright(self):
        budget = ttp_profile().computed()
        payload = budget.as_dict()
        payload["schema_version"] = "acquisition_budget_v2"
        with pytest.raises(ValueError, match="schema_version"):
            AcquisitionBudgetV1.from_dict(payload)
