"""E0 observations entering the acquisition budget (DO-107B).

The question these tests hold to: **can a physical characterization observation
enter the acquisition budget without losing where it came from, what was
actually measured, or what remains unknown?**

Three failures would each produce a record that reads as evidence and is not,
and each has its own group below. A number arriving without its origin (B). A
number arriving that nobody measured (A4, A5, I). And a budget that becomes
evidence-grade because one input improved while the mathematics behind it stayed
unresolved (C, E).

E0 has no pass condition. Nothing here computes one, and a fully executed record
is exercised specifically to show that it still does not produce a qualified
instrument.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tap_tone_pi.grant_readiness.e0_characterization import (
    E0AdcCharacterizationV1,
    E0BalancedInputObservationV1,
    E0ControlGranularity,
    E0CouplingObservationV1,
    E0CouplingResultV1,
    E0DeviceIdentityV1,
    E0ExecutionStatus,
    E0FullScaleObservationV1,
    E0InputPath,
    E0LoopbackObservationV1,
    E0NoiseObservationV1,
    E0OutOfBandObservationV1,
    E0PgaObservationV1,
    E0ProvenanceV1,
    E0SourceCapability,
    E0SpurObservationV1,
)
from tap_tone_pi.grant_readiness.errors import E0CharacterizationError
from tap_tone_pi.uncertainty.acquisition import (
    AcquisitionBudgetV1,
    CaptureSpec,
    ClockSpec,
    ConverterSpec,
    E0_MAPPINGS,
    E0_UNMAPPED_GROUPS,
    E0AdapterError,
    E0MappingStatus,
    E0OperatingPoint,
    EvidenceCondition,
    FrontEndSpec,
    Provenance,
    Quantity,
    SpecimenSpec,
    SweepSpec,
    adapt_e0_characterization,
    build_acquisition_budget_from_e0,
    compare_budget_inputs,
    e0_source_locator,
    parse_e0_source_locator,
)

Q = Quantity
P = Provenance

#: The configuration every fixture below is written for: 48 kHz, -12 dB of gain,
#: unbalanced input. Selection is exact — see :class:`E0OperatingPoint`.
POINT = E0OperatingPoint(
    sample_rate_hz=48000.0, pga_db=-12.0, input_path=E0InputPath.UNBALANCED
)

MEASURED_FLOOR_DBFS = -108.4
MEASURED_CORNER_HZ = 18.5
MEASURED_HARD_CLIP_VRMS = 2.11


# ---------------------------------------------------------------------------
# Fixtures — an E0 record and a budget to put it into
# ---------------------------------------------------------------------------


def device() -> E0DeviceIdentityV1:
    return E0DeviceIdentityV1(
        local_id="ADC-001", manufacturer="HiFiBerry", model="DAC+ ADC Pro"
    )


def provenance(**overrides) -> E0ProvenanceV1:
    base = dict(performed_utc="2026-09-01T12:00:00Z", operator="Ross Echols")
    base.update(overrides)
    return E0ProvenanceV1(**base)


def executed(**overrides) -> E0AdcCharacterizationV1:
    """A complete bench record. Unremarkable numbers, no verdict implied."""
    base = dict(
        characterization_id="E0-107B-A",
        device=device(),
        provenance=provenance(
            source_equipment=("second laptop, 192 kHz audio out",),
            source_verified_bandwidth_hz=90000.0,
        ),
        execution_status=E0ExecutionStatus.EXECUTED,
        noise_floor=(
            E0NoiseObservationV1(48000.0, -12.0, MEASURED_FLOOR_DBFS),
            E0NoiseObservationV1(48000.0, 32.0, -84.1),
            E0NoiseObservationV1(96000.0, -12.0, -105.7),
        ),
        spurs=(E0SpurObservationV1(frequency_hz=50.0, level_dbfs=-121.0),),
        pga=(
            E0PgaObservationV1(0.0, 0.0, 0.0, -108.4),
            E0PgaObservationV1(32.0, 32.0, 31.6, -108.1),
        ),
        coupling=E0CouplingResultV1(
            measured_corner_hz=MEASURED_CORNER_HZ,
            points=(
                E0CouplingObservationV1(70.0, -0.31, 15.9),
                E0CouplingObservationV1(200.0, -0.04, 5.3),
            ),
        ),
        out_of_band=(
            E0OutOfBandObservationV1(
                injected_hz=30000.0,
                source_state=E0SourceCapability.MEASURED,
                apparent_hz=18000.0,
                attenuation_db=-6.2,
                sample_rate_hz=48000.0,
            ),
            E0OutOfBandObservationV1(
                injected_hz=200000.0,
                source_state=E0SourceCapability.BLOCKED_BY_SOURCE_CAPABILITY,
            ),
        ),
        balanced_scope=E0BalancedInputObservationV1(
            control_name="ADC Input Mode",
            granularity=E0ControlGranularity.GLOBAL,
            unbalanced_full_scale_vrms=2.05,
            balanced_full_scale_vrms=4.11,
            applies_to="Analyzer only; E1 ch0 needs unbalanced",
        ),
        full_scale=(
            E0FullScaleObservationV1(
                E0InputPath.UNBALANCED, 2.02, MEASURED_HARD_CLIP_VRMS, 2.1
            ),
            E0FullScaleObservationV1(E0InputPath.BALANCED, 4.05, 4.20, 4.2),
        ),
        loopback=E0LoopbackObservationV1(
            run_count=10,
            mean_offset_samples=612.0,
            stddev_samples=0.0,
            within_session_stable=True,
            sample_rate_hz=48000.0,
        ),
    )
    base.update(overrides)
    return E0AdcCharacterizationV1(**base)


def base_budget(**overrides) -> AcquisitionBudgetV1:
    """The TTP design-stage profile: the state E0 is run to improve on."""
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


def outcome_for(adaptation, target):
    return next(o for o in adaptation.outcomes if o.mapping.target == target)


# ---------------------------------------------------------------------------
# Group A — mapping
# ---------------------------------------------------------------------------


class TestMapping:
    """§20. An observation becomes an input, or nothing does."""

    @pytest.fixture(scope="class")
    def adaptation(self):
        return adapt_e0_characterization(executed(), POINT)

    def test_a1_an_executed_observation_becomes_the_right_input(self, adaptation):
        measured = adaptation.measured()
        assert set(measured) == {
            "converter.thermal_snr_db",
            "converter.hp_corner_hz",
            "converter.full_scale_vrms",
        }
        assert measured["converter.hp_corner_hz"].value == MEASURED_CORNER_HZ
        assert measured["converter.full_scale_vrms"].value == MEASURED_HARD_CLIP_VRMS

    def test_a1_the_selected_row_is_the_one_asked_for(self):
        """A different operating point reads a different cell of the same table."""
        other = adapt_e0_characterization(
            executed(),
            E0OperatingPoint(48000.0, 32.0, E0InputPath.UNBALANCED),
        )
        assert other.measured()["converter.thermal_snr_db"].value == 84.1

    def test_a2_every_mapped_input_is_measured_and_says_where_from(self, adaptation):
        for target, quantity in adaptation.measured().items():
            assert quantity.provenance is Provenance.MEASURED, target
            parsed = parse_e0_source_locator(quantity.source)
            assert parsed["characterization_id"] == "E0-107B-A"
            assert parsed["test"] in {"T1", "T3", "T6"}

    def test_a2_the_source_identifies_the_row_not_just_the_test(self, adaptation):
        floor = adaptation.measured()["converter.thermal_snr_db"]
        assert floor.source == e0_source_locator(
            "E0-107B-A",
            "T1",
            "noise_floor",
            "sample_rate_hz=48000,pga_db=-12",
            "rms_dbfs",
        )
        clip = adaptation.measured()["converter.full_scale_vrms"]
        assert parse_e0_source_locator(clip.source)["selector"] == "path=UNBALANCED"

    def test_a3_the_only_conversion_is_a_change_of_reference(self, adaptation):
        # dBFS is defined against full scale, so SNR against that floor is its
        # negation. Exact, not approximate: no bandwidth or weighting enters it.
        assert adaptation.measured()["converter.thermal_snr_db"].value == -(
            MEASURED_FLOOR_DBFS
        )
        assert adaptation.measured()["converter.thermal_snr_db"].unit == "dB"

    def test_a3_identity_mappings_do_not_perturb_the_value(self, adaptation):
        # Carried across, not recomputed. Bitwise equality is the assertion.
        assert (
            adaptation.measured()["converter.hp_corner_hz"].value == MEASURED_CORNER_HZ
        )

    def test_a4_a_missing_observation_fabricates_nothing(self):
        record = executed(coupling=E0CouplingResultV1(measured_corner_hz=None))
        adaptation = adapt_e0_characterization(record, POINT)
        outcome = outcome_for(adaptation, "converter.hp_corner_hz")
        assert outcome.status is E0MappingStatus.NOT_OBSERVED
        assert outcome.quantity is None
        assert "converter.hp_corner_hz" not in adaptation.measured()

    def test_a4_the_acquisition_input_keeps_its_own_provenance(self):
        record = executed(noise_floor=())
        informed = build_acquisition_budget_from_e0(base_budget(), record, POINT)
        thermal = informed.budget.converter.thermal_snr_db
        assert thermal.provenance is Provenance.DATASHEET
        assert thermal.value == 110.0

    def test_a4_a_null_measurement_is_not_a_zero_measurement(self):
        record = executed(
            full_scale=(
                E0FullScaleObservationV1(E0InputPath.UNBALANCED, 2.02, None, 2.1),
            )
        )
        adaptation = adapt_e0_characterization(record, POINT)
        outcome = outcome_for(adaptation, "converter.full_scale_vrms")
        assert outcome.status is E0MappingStatus.NOT_OBSERVED
        assert outcome.quantity is None
        # And the neighbouring level is not substituted for the missing one.
        assert "0.1% THD" in outcome.detail or "THD" in outcome.detail

    def test_a5_a_prepared_record_cannot_produce_a_measured_input(self):
        prepared = E0AdcCharacterizationV1(
            characterization_id="E0-107B-PREPARED",
            device=device(),
            provenance=provenance(),
        )
        with pytest.raises(E0AdapterError, match="PREPARED"):
            adapt_e0_characterization(prepared, POINT)

    def test_a6_a_malformed_record_fails_in_the_existing_error_model(self):
        payload = executed().to_dict()
        payload["coupling"]["points"][0].pop("phase_deg")
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code.value.startswith("NSF-")

    def test_a6_an_observation_at_or_above_full_scale_is_refused_not_carried(self):
        record = executed(
            noise_floor=(E0NoiseObservationV1(48000.0, -12.0, 0.5),),
        )
        adaptation = adapt_e0_characterization(record, POINT)
        outcome = outcome_for(adaptation, "converter.thermal_snr_db")
        assert outcome.status is E0MappingStatus.REFUSED
        assert outcome.quantity is None
        assert "not a noise floor" in outcome.detail

    def test_a7_an_unrelated_observation_is_ignored_with_a_stated_reason(
        self, adaptation
    ):
        groups = {(u.test, u.group): u.reason for u in adaptation.unmapped}
        assert ("T7", "loopback") in groups
        assert ("T4", "out_of_band") in groups
        assert ("T1", "spurs") in groups
        for reason in groups.values():
            assert reason.strip()

    def test_a7_no_ignored_group_quietly_reaches_an_acquisition_input(self, adaptation):
        # The loopback offset is the trap: it is a DAC-to-ADC round trip and
        # would look like a timing number if anything here were fishing by name.
        sources = [q.source for q in adaptation.measured().values()]
        assert not [s for s in sources if "loopback" in s or "out_of_band" in s]

    def test_the_mapping_table_is_declared_rather_than_discovered(self):
        assert {(m.test, m.field) for m in E0_MAPPINGS} == {
            ("T1", "rms_dbfs"),
            ("T3", "measured_corner_hz"),
            ("T6", "hard_clip_vrms"),
        }
        for mapping in E0_MAPPINGS:
            assert mapping.conversion
            assert mapping.target.startswith("converter.")

    def test_every_e0_group_is_either_mapped_or_explained(self):
        """A future observation cannot be added and silently go nowhere."""
        accounted = {m.group for m in E0_MAPPINGS} | {
            u.group.split(".")[0] for u in E0_UNMAPPED_GROUPS
        }
        record_groups = set(executed().observed_groups())
        assert record_groups <= accounted, sorted(record_groups - accounted)


# ---------------------------------------------------------------------------
# Group B — provenance integrity
# ---------------------------------------------------------------------------


class TestProvenanceIntegrity:
    """§21. A correct number that lost its origin is still a scientific defect."""

    @pytest.fixture(scope="class")
    def informed(self):
        return build_acquisition_budget_from_e0(base_budget(), executed(), POINT)

    def test_b1_source_identity_survives_serialization_exactly(self, informed):
        payload = json.loads(json.dumps(informed.budget.as_dict()))
        restored = AcquisitionBudgetV1.from_dict(payload)
        assert restored.converter.hp_corner_hz == informed.budget.converter.hp_corner_hz
        assert restored.converter.hp_corner_hz.provenance is Provenance.MEASURED
        assert parse_e0_source_locator(restored.converter.hp_corner_hz.source) == {
            "characterization_id": "E0-107B-A",
            "test": "T3",
            "group": "coupling",
            "selector": "",
            "field": "measured_corner_hz",
        }

    def test_b2_equal_values_from_different_benches_stay_distinguishable(self):
        first = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        second = build_acquisition_budget_from_e0(
            base_budget(),
            executed(characterization_id="E0-107B-B"),
            POINT,
        )
        a = first.budget.converter.hp_corner_hz
        b = second.budget.converter.hp_corner_hz
        assert a.value == b.value
        assert a != b
        assert a.source != b.source

    def test_b3_a_datasheet_input_e0_did_not_measure_stays_datasheet(self, informed):
        rate = informed.budget.converter.sample_rate_hz
        assert rate.provenance is Provenance.DATASHEET
        assert rate.source == "Rev 1.5"

    def test_b4_an_assumed_input_stays_assumed(self, informed):
        accuracy = informed.budget.clock.accuracy_ppm
        assert accuracy.provenance is Provenance.ASSUMED
        assert accuracy.source == "typical XO grade"

    def test_b4_a_proposed_input_is_not_promoted_by_a_neighbours_measurement(
        self, informed
    ):
        # The aperture jitter sits inside the very converter E0 characterized.
        # Characterizing the board is not measuring that number.
        jitter = informed.budget.converter.aperture_jitter_s
        assert jitter.provenance is Provenance.PROPOSED
        assert jitter.source == "pending E0/T4"

    def test_b5_only_inputs_are_counted_as_measured(self, informed):
        counts = informed.budget.provenance_summary()
        assert counts[Provenance.MEASURED.value] == 3
        # The computed sections are results, not inputs, and none of them
        # acquires an input provenance tag by being derived from measured ones.
        assert informed.budget.noise is not None
        assert informed.budget.frequency is not None

    def test_the_audit_says_what_was_consumed_and_what_was_not(self, informed):
        audit = informed.adaptation.as_dict()
        consumed = [o for o in audit["outcomes"] if o["status"] == "consumed"]
        assert len(consumed) == 3
        assert all(o["source"] for o in consumed)
        assert audit["operating_point"]["sample_rate_hz"] == 48000.0
        assert audit["unmapped"]

    def test_a_provenance_trace_returns_to_the_bench_row(self, informed):
        source = informed.budget.converter.thermal_snr_db.source
        trace = parse_e0_source_locator(source)
        record = executed()
        assert trace["characterization_id"] == record.characterization_id
        row = next(
            r
            for r in record.noise_floor
            if f"sample_rate_hz={r.sample_rate_hz:g},pga_db={r.pga_db:g}"
            == trace["selector"]
        )
        assert row.rms_dbfs == MEASURED_FLOOR_DBFS


# ---------------------------------------------------------------------------
# Group C — evidence grading
# ---------------------------------------------------------------------------


class TestEvidenceGrading:
    """§22. Characterization improves inputs. It does not settle mathematics."""

    def test_c1_an_incomplete_e0_leaves_its_own_condition_blocking(self):
        record = executed(coupling=E0CouplingResultV1(measured_corner_hz=None))
        informed = build_acquisition_budget_from_e0(base_budget(), record, POINT)
        conditions = {r.condition for r in informed.budget.evidence().blockers}
        assert EvidenceCondition.COUPLING_CORNER_UNMEASURED in conditions
        assert informed.budget.evidence().evidence_grade is False

    def test_c1_a_measured_corner_clears_that_condition_and_only_that_one(self):
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        conditions = {r.condition for r in informed.budget.evidence().blockers}
        assert EvidenceCondition.COUPLING_CORNER_UNMEASURED not in conditions
        assert EvidenceCondition.NO_ANTI_ALIAS_FILTER in conditions

    def test_c2_a_full_characterization_leaves_b020_and_b021_blocking(self):
        """The required integration test of D107B-07.

        Every acquisition input E0 can physically supply is measured here, and
        the current full TTP computation is still not evidence-grade.
        """
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        evidence = informed.budget.evidence()
        assert evidence.evidence_grade is False
        blocking = {r.reference for r in evidence.blockers if r.reference}
        assert {"B-020", "B-021"} <= blocking

    def test_c3_no_b022_advisory_returns(self):
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        assert informed.budget.modulus.aggregation == "canonical"
        assert not [
            r
            for r in informed.budget.evidence().reasons
            if r.condition is EvidenceCondition.AGGREGATE_AUTHORITY_WORKAROUND
        ]

    def test_c4_replacing_one_input_erases_no_unrelated_blocker(self):
        before = base_budget().computed()
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        was = {r.condition for r in before.evidence().blockers}
        now = {r.condition for r in informed.budget.evidence().blockers}
        # Exactly one condition cleared, and it is the one E0 measured.
        assert was - now == {EvidenceCondition.COUPLING_CORNER_UNMEASURED}
        assert not now - was

    def test_c5_a_blocker_free_scope_can_still_reach_evidence_grade(self):
        """Proves the integration did not hardcode ``E0 -> not evidence``.

        A noise-path budget: no specimen and no capture, so neither structural
        blocker applies, with the inputs E0 does not measure supplied as measured
        and an anti-alias filter fitted. The three E0 inputs arrive by adaptation.
        """
        M = Provenance.MEASURED
        base = base_budget(
            capture=None,
            sweep=None,
            specimen=None,
            converter=ConverterSpec(
                name="ADC",
                bits=24,
                full_scale_vrms=Q(2.1, "Vrms", P.DATASHEET, "Rev 1.5"),
                thermal_snr_db=Q(110.0, "dB", P.DATASHEET, "Rev 1.5 typ."),
                aperture_jitter_s=Q(9e-13, "s", M, "bench, separately"),
                sample_rate_hz=Q(48000.0, "Hz", M, "session"),
                anti_alias_filter=True,
            ),
            clock=ClockSpec(
                name="xo",
                rms_jitter_s=Q(4e-12, "s", M, "bench, separately"),
                accuracy_ppm=Q(1.2, "ppm", M, "bench, separately"),
            ),
            front_end=FrontEndSpec(
                name="pre",
                input_referred_noise_v_per_rthz=Q(1.1e-9, "V/rtHz", M, "measured"),
                gain_db=Q(52.0, "dB", M, "measured"),
                bandwidth_hz=Q(20000.0, "Hz", M, "measured"),
            ),
        )
        informed = build_acquisition_budget_from_e0(
            base, executed(), POINT, f_in_hz=1000.0
        )
        evidence = informed.budget.evidence()
        assert evidence.blockers == (), [r.condition.value for r in evidence.blockers]
        assert evidence.evidence_grade is True

    def test_what_characterization_changed_is_reportable(self):
        before = base_budget().computed()
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        changed = compare_budget_inputs(before, informed.budget)
        assert set(changed) == {
            "converter.thermal_snr_db",
            "converter.full_scale_vrms",
            "converter.hp_corner_hz",
        }
        assert (
            changed["converter.thermal_snr_db"]["before"]["provenance"] == "datasheet"
        )
        assert changed["converter.thermal_snr_db"]["after"]["provenance"] == "measured"


# ---------------------------------------------------------------------------
# Group D — numerical authority
# ---------------------------------------------------------------------------


class TestNumericalAuthority:
    """§23. The adapter owns zero equations, and this is how that is known."""

    def test_d_the_adapter_reproduces_the_authority_exactly(self):
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        direct = base_budget(
            converter=ConverterSpec(
                name="HiFiBerry DAC+ ADC Pro",
                bits=24,
                full_scale_vrms=Q(
                    MEASURED_HARD_CLIP_VRMS,
                    "Vrms",
                    P.MEASURED,
                    informed.budget.converter.full_scale_vrms.source,
                ),
                thermal_snr_db=Q(
                    -MEASURED_FLOOR_DBFS,
                    "dB",
                    P.MEASURED,
                    informed.budget.converter.thermal_snr_db.source,
                ),
                aperture_jitter_s=Q(1e-12, "s", P.PROPOSED, "pending E0/T4"),
                sample_rate_hz=Q(48000.0, "Hz", P.DATASHEET, "Rev 1.5"),
                hp_corner_hz=Q(
                    MEASURED_CORNER_HZ,
                    "Hz",
                    P.MEASURED,
                    informed.budget.converter.hp_corner_hz.source,
                ),
            )
        ).computed()

        assert informed.budget.as_dict() == direct.as_dict()

    def test_d_every_computed_section_matches_term_for_term(self):
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        budget = informed.budget
        assert budget.noise is not None and budget.noise.terms_db
        assert budget.frequency is not None
        assert budget.modulus is not None
        assert budget.sweep_limits is not None
        # Nothing in the adapter names any of these terms; they exist only
        # because ``computed()`` produced them.
        import tap_tone_pi.uncertainty.acquisition.e0_adapter as adapter

        source = open(adapter.__file__, encoding="utf-8").read()
        for banned in ("log10", "sqrt", "math.pi", "jitter_snr", "frequency_budget("):
            assert banned not in source, f"adapter contains {banned}"


# ---------------------------------------------------------------------------
# Group E — B-020 / B-021 regression
# ---------------------------------------------------------------------------


class TestBacklogRegression:
    """§24. Pin the current composition structurally, not by counting."""

    @pytest.fixture(scope="class")
    def budget(self):
        return build_acquisition_budget_from_e0(base_budget(), executed(), POINT).budget

    def test_e_b020_keeps_the_candidate_estimator_authority(self, budget):
        assert budget.frequency.estimator_floor_status.is_established is False
        reason = next(
            r
            for r in budget.evidence().reasons
            if r.condition is EvidenceCondition.PROVISIONAL_FORMULA
        )
        assert reason.reference == "B-020"
        assert reason.blocking is True

    def test_e_b021_composition_is_unchanged_by_adaptation(self, budget):
        contributors = budget.frequency.combined_contributors
        sources = [c.source_quantity for c in contributors]
        # No duplicate contributor: that half of B-021 was repaired in DO-107M.
        assert len(sources) == len(set(sources))
        # And the open half is unchanged: the spectral-resolution slot is filled
        # by the estimator floor while the bin width stays out of the sum.
        assert "estimator_floor_hz" in sources
        assert "bin_width_hz" not in sources
        roles = {c.role for c in contributors}
        assert "spectral_resolution" in roles

    def test_e_the_open_composition_defect_is_still_reported(self, budget):
        reason = next(
            r
            for r in budget.evidence().reasons
            if r.condition is EvidenceCondition.CONTRIBUTOR_COMPOSITION_DEFECT
        )
        assert reason.reference == "B-021"
        assert reason.blocking is True


# ---------------------------------------------------------------------------
# Group H — stdlib / instrument boundary
# ---------------------------------------------------------------------------


class TestInstrumentBoundary:
    """§27. Integration must not be how NumPy reaches the instrument."""

    @staticmethod
    def _loaded_after(statement: str, module: str) -> bool:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import sys\n{statement}\nprint({module!r} in sys.modules)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == "True"

    @pytest.mark.parametrize("heavy", ["numpy", "jsonschema"])
    def test_h_the_adapter_does_not_pull_a_heavy_dependency(self, heavy):
        assert (
            self._loaded_after(
                "import tap_tone_pi.uncertainty.acquisition.e0_adapter", heavy
            )
            is False
        )

    @pytest.mark.parametrize("heavy", ["numpy", "jsonschema"])
    def test_h_the_package_still_loads_clean_with_the_adapter_exported(self, heavy):
        assert (
            self._loaded_after("import tap_tone_pi.uncertainty.acquisition", heavy)
            is False
        )


# ---------------------------------------------------------------------------
# Group I — E0 semantic truth
# ---------------------------------------------------------------------------


class TestE0SemanticsSurviveIntegration:
    """§28. Integration is where these distinctions are easiest to lose."""

    def test_i_executed_is_not_qualified(self):
        informed = build_acquisition_budget_from_e0(base_budget(), executed(), POINT)
        assert informed.adaptation.execution_status is E0ExecutionStatus.EXECUTED
        payload = json.dumps(informed.adaptation.as_dict()).lower()
        for verdict in ("pass", "verdict", "grade", "acceptable", "qualified"):
            assert verdict not in payload

    def test_i_a_partially_executed_record_is_read_for_what_it_holds(self):
        """PARTIALLY_EXECUTED is neither refused nor treated as complete."""
        record = executed(
            execution_status=E0ExecutionStatus.PARTIALLY_EXECUTED,
            coupling=E0CouplingResultV1(measured_corner_hz=None),
        )
        adaptation = adapt_e0_characterization(record, POINT)
        assert len(adaptation.measured()) == 2
        unfilled = {o.mapping.target for o in adaptation.unfilled()}
        assert unfilled == {"converter.hp_corner_hz"}

    def test_i_prepared_is_not_observed(self):
        prepared = E0AdcCharacterizationV1(
            characterization_id="E0-107B-PREPARED",
            device=device(),
            provenance=provenance(),
        )
        with pytest.raises(E0AdapterError):
            adapt_e0_characterization(prepared, POINT)

    def test_i_a_measurement_of_another_configuration_is_refused(self):
        """A 96 kHz noise floor is not evidence about a 48 kHz budget."""
        point = E0OperatingPoint(96000.0, -12.0, E0InputPath.UNBALANCED)
        with pytest.raises(E0AdapterError, match="configuration"):
            build_acquisition_budget_from_e0(base_budget(), executed(), point)
