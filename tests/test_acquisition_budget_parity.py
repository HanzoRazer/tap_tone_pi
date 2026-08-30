"""Parity of the acquisition engine against its 984-line source (DO-107A).

Three different kinds of behavior are established here, and keeping them apart
is the point of the file:

**Exact parity** for calculations that are genuinely new — jitter, quantization,
SNR combination, front-end noise, the noise budget, the frequency budget and the
sweep limits. These must reproduce the archived source to floating-point
equality, because DO-107A's job is to establish what the existing calculator
says, not what it ought to say.

**Delegation** for the modulus propagation, where a canonical authority already
exists. Parity here means the adapter agrees with the source *and* that the
sensitivity coefficients come from
:func:`~tap_tone_pi.uncertainty.stiffness.compute_tap_tone_moe_uncertainty`
rather than from a second copy in the acquisition engine.

**Preserved unresolved semantics** where the source does something questionable.
Those are reproduced and pinned, not silently improved — see
:class:`TestPreservedSourceSemantics`.

The parity baseline is archived in-repo at
``docs/reference/acquisition/acquisition_budget_source.py`` and pinned by digest,
so this file measures against fixed bytes rather than against whatever happens to
be on a developer's disk.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    REPO_ROOT / "docs" / "reference" / "acquisition" / "acquisition_budget_source.py"
)
SOURCE_SHA256 = "043d4bb95cd86be32f6d2778a8a59292325b6af4350861946a4442d6fd0ac887"

from tap_tone_pi.uncertainty.acquisition import (  # noqa: E402
    CaptureSpec,
    ClockSpec,
    ConverterSpec,
    FrontEndSpec,
    Provenance,
    Quantity,
    SpecimenSpec,
    SweepSpec,
    clock_topology_note,
    combine_snr_db,
    compute_sweep_limits,
    estimator_floor_candidate_hz,
    frequency_budget,
    front_end_output_noise_vrms,
    front_end_snr_db,
    jitter_budget_s,
    jitter_snr_db,
    modulus_budget,
    noise_budget,
    quantization_snr_db,
)


@pytest.fixture(scope="module")
def source():
    """The archived source, loaded from fixed bytes."""
    spec = importlib.util.spec_from_file_location("_e0_source", SOURCE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_e0_source"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ours():
    """The TTP analyzer profile expressed in the new specification types."""
    Q = Quantity
    P = Provenance
    return dict(
        converter=ConverterSpec(
            name="HiFiBerry DAC+ ADC Pro",
            bits=24,
            full_scale_vrms=Q(2.1, "Vrms", P.DATASHEET, "Rev 1.5, unbalanced maximum"),
            thermal_snr_db=Q(110.0, "dB", P.DATASHEET, "Rev 1.5 typ."),
            aperture_jitter_s=Q(1e-12, "s", P.PROPOSED, "placeholder pending E0/T4"),
            sample_rate_hz=Q(48000.0, "Hz", P.DATASHEET, "Rev 1.5"),
            ac_coupled=True,
            hp_corner_hz=None,
            anti_alias_filter=False,
        ),
        clock=ClockSpec(
            name="on-board local oscillator",
            rms_jitter_s=Q(5e-12, "s", P.PROPOSED, "no vendor figure"),
            accuracy_ppm=Q(20.0, "ppm", P.ASSUMED, "typical XO grade"),
            topology="local_xo",
            spurious=False,
        ),
        front_end=FrontEndSpec(
            name="OPA1612 balanced mic preamp",
            input_referred_noise_v_per_rthz=Q(1.1e-9, "V/rtHz", P.DATASHEET, "OPA1612"),
            gain_db=Q(52.0, "dB", P.PROPOSED, "MID; prototype hypothesis"),
            bandwidth_hz=Q(20000.0, "Hz", P.ASSUMED, "declared band"),
        ),
        capture=CaptureSpec(
            record_length_s=Q(4.0, "s", P.ASSUMED, "working default"),
            sample_rate_hz=Q(48000.0, "Hz", P.DATASHEET, "Rev 1.5"),
            window="hann",
            peak_interpolation=True,
        ),
        sweep=SweepSpec(
            f_start_hz=Q(60.0, "Hz", P.ASSUMED, "below lowest plate mode"),
            f_stop_hz=Q(2000.0, "Hz", P.ASSUMED, "top of declared band"),
            expected_q=Q(50.0, "-", P.PROPOSED, "braced top, typical 30-80"),
        ),
        specimen=SpecimenSpec(
            name="spruce top plate, mode 2",
            mode_frequency_hz=Q(187.0, "Hz", P.ASSUMED, "worked example"),
            length_m=Q(0.500, "m", P.ASSUMED, "worked example"),
            length_uncertainty_m=Q(0.0005, "m", P.ASSUMED, "steel rule"),
            thickness_m=Q(0.0028, "m", P.ASSUMED, "worked example"),
            thickness_uncertainty_m=Q(0.00002, "m", P.ASSUMED, "digital caliper"),
            density_kg_m3=Q(420.0, "kg/m3", P.ASSUMED, "worked example"),
            density_uncertainty_kg_m3=Q(4.0, "kg/m3", P.ASSUMED, "mass and volume"),
            physical_repeatability_hz=None,
        ),
    )


class TestTheParityBaselineIsFixed:
    def test_the_archived_source_matches_its_digest(self):
        digest = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        assert digest == SOURCE_SHA256, (
            "the archived parity source changed. Every parity number below is "
            "measured against these bytes; update the digest only deliberately."
        )

    def test_the_source_is_the_full_984_lines(self):
        assert len(SOURCE_PATH.read_text(encoding="utf-8").splitlines()) == 984


class TestExactParityNewCalculations:
    """Genuinely new calculations must reproduce the source exactly."""

    @pytest.mark.parametrize(
        "f_hz,tj_s",
        [(1000.0, 1e-12), (20000.0, 5e-12), (187.0, 5.099e-12), (48000.0, 1e-9)],
    )
    def test_jitter_snr(self, source, f_hz, tj_s):
        assert jitter_snr_db(f_hz, tj_s) == source.jitter_snr_db(f_hz, tj_s)

    @pytest.mark.parametrize(
        "f_hz,target_db", [(1000.0, 100.0), (20000.0, 110.0), (187.0, 96.0)]
    )
    def test_jitter_budget(self, source, f_hz, target_db):
        assert jitter_budget_s(f_hz, target_db) == source.jitter_budget_s(
            f_hz, target_db
        )

    def test_jitter_snr_and_budget_are_inverses(self, source):
        # A property of the pair rather than of either, so a sign error in one
        # cannot hide behind matching the other.
        f, target = 1000.0, 100.0
        tj = jitter_budget_s(f, target)
        assert jitter_snr_db(f, tj) == pytest.approx(target, abs=1e-9)

    @pytest.mark.parametrize("bits", [8, 16, 24, 32])
    def test_quantization_snr(self, source, bits):
        assert quantization_snr_db(bits) == source.quantization_snr_db(bits)

    def test_quantization_matches_the_published_relationship(self):
        # 6.02 N + 1.76 dB. Pinned independently of the source so a typo in the
        # constants would not be blessed by parity alone.
        assert quantization_snr_db(24) == pytest.approx(146.24, abs=1e-9)

    def test_snr_combination(self, source):
        terms = (146.24, 110.0, 96.5, 101.2)
        assert combine_snr_db(*terms) == source.combine_snr_db(*terms)

    def test_snr_combination_is_dominated_by_the_worst_term(self):
        assert combine_snr_db(200.0, 100.0) == pytest.approx(100.0, abs=0.05)

    def test_front_end_noise_and_snr(self, source, ours):
        src_fe = source.FrontEndSpec(
            name="OPA1612",
            input_referred_noise_v_per_rthz=source.Quantity(
                1.1e-9, "V/rtHz", source.Provenance.DATASHEET
            ),
            gain_db=source.Quantity(52.0, "dB", source.Provenance.PROPOSED),
            bandwidth_hz=source.Quantity(20000.0, "Hz", source.Provenance.ASSUMED),
        )
        assert (
            front_end_output_noise_vrms(ours["front_end"]) == src_fe.output_noise_vrms()
        )
        assert front_end_snr_db(ours["front_end"], 2.1) == src_fe.snr_db(2.1)


class TestNoiseBudgetParity:
    @pytest.fixture(scope="class")
    def pair(self, source, ours):
        src = source.TTP_ANALYZER_PROFILE().compute()
        mine = noise_budget(ours["converter"], ours["clock"], ours["front_end"], 187.0)
        return src.noise, mine

    def test_terms_match(self, pair):
        src, mine = pair
        assert mine.terms_db == src.terms_db

    def test_combined_snr_matches(self, pair):
        src, mine = pair
        assert mine.combined_snr_db == src.combined_snb_db

    def test_limiter_and_share_match(self, pair):
        src, mine = pair
        assert mine.limiter == src.limiter
        assert mine.limiter_share == pytest.approx(src.limiter_share)

    def test_total_jitter_and_headroom_match(self, pair):
        src, mine = pair
        assert mine.total_jitter_s == src.total_jitter_s
        assert mine.jitter_headroom_db == pytest.approx(src.jitter_headroom_db)

    def test_notes_match(self, pair):
        src, mine = pair
        assert list(mine.notes) == list(src.notes)

    def test_the_limiter_is_named_and_is_not_jitter_here(self, pair):
        # The whole product of this budget: on an audio-band instrument the
        # answer is almost never the clock, and the module says so plainly.
        _, mine = pair
        assert mine.limiter == "front_end"
        assert any("Clock improvement buys nothing" in n for n in mine.notes)

    def test_the_absent_anti_alias_filter_is_reported(self, pair):
        _, mine = pair
        assert any("no input anti-alias filter" in n for n in mine.notes)

    def test_a_spurious_clock_is_not_silently_rss_combined(self, source, ours):
        spurious = ClockSpec(
            name="fractional-N",
            rms_jitter_s=Quantity(1e-9, "s", Provenance.PROPOSED),
            accuracy_ppm=Quantity(50.0, "ppm", Provenance.ASSUMED),
            topology="host_fractional_n",
            spurious=True,
        )
        mine = noise_budget(ours["converter"], spurious, ours["front_end"], 20000.0)
        assert any("NOT valid" in n for n in mine.notes)

    @pytest.mark.parametrize(
        "topology", ["local_xo", "host_fractional_n", "cleanup_pll"]
    )
    def test_topology_notes_match(self, source, topology):
        clock = ClockSpec(
            name="c",
            rms_jitter_s=Quantity(5e-12, "s", Provenance.ASSUMED),
            accuracy_ppm=Quantity(20.0, "ppm", Provenance.ASSUMED),
            topology=topology,
        )
        src_clock = source.ClockSpec(
            name="c",
            rms_jitter_s=source.Quantity(5e-12, "s", source.Provenance.ASSUMED),
            accuracy_ppm=source.Quantity(20.0, "ppm", source.Provenance.ASSUMED),
            topology=topology,
        )
        assert clock_topology_note(clock) == source.clock_topology_note(src_clock)


class TestFrequencyBudgetParity:
    @pytest.fixture(scope="class")
    def pair(self, source, ours):
        src = source.TTP_ANALYZER_PROFILE().compute()
        mine = frequency_budget(
            ours["clock"], ours["capture"], ours["specimen"], src.noise.combined_snb_db
        )
        return src.frequency, mine

    def test_every_reportable_term_matches(self, pair):
        src, mine = pair
        assert mine.clock_error_hz == src.clock_error_hz
        assert mine.bin_width_hz == src.bin_width_hz
        assert mine.estimator_floor_hz == src.estimator_floor_hz
        assert mine.dominant == src.dominant

    def test_the_only_drift_from_the_source_is_the_removed_duplicate(self, pair):
        """B-021, DO-107M: the combined figure now differs, by exactly one term.

        This is the one place DO-107M knowingly departs from the archived
        source, so the departure is asserted exactly rather than absorbed into a
        loosened tolerance. The source counted the estimator floor twice; we
        count it once. Everything else is untouched, so:

            source^2 - ours^2 == estimator_floor^2

        At TTP values the drift is about 4 parts in 1e12 -- far too small to
        notice, which is precisely why it needed a structural test rather than a
        numerical one.
        """
        src, mine = pair
        assert mine.combined_hz != src.combined_hz
        assert mine.combined_hz < src.combined_hz
        assert src.combined_hz**2 - mine.combined_hz**2 == pytest.approx(
            mine.estimator_floor_hz**2, rel=1e-9
        )

    def test_notes_match(self, pair):
        src, mine = pair
        assert list(mine.notes) == list(src.notes)

    def test_clock_scale_error_is_proportional(self):
        from tap_tone_pi.uncertainty.acquisition import clock_scale_error_hz

        assert clock_scale_error_hz(187.0, 20.0) == pytest.approx(187.0 * 20e-6)
        assert clock_scale_error_hz(374.0, 20.0) == pytest.approx(
            2 * clock_scale_error_hz(187.0, 20.0)
        )

    def test_estimator_floor_matches_the_source(self, source):
        assert estimator_floor_candidate_hz(4.0, 192000, 96.5) == pytest.approx(
            (1.0 / (math.pi * 4.0)) * math.sqrt(6.0 / (10 ** (96.5 / 10.0) * 192000))
        )

    def test_missing_repeatability_makes_it_an_electronic_lower_bound(self, pair):
        _, mine = pair
        assert mine.is_electronic_lower_bound is True
        assert any("ELECTRONIC lower bound" in n for n in mine.notes)

    def test_measured_repeatability_can_dominate(self, source, ours):
        specimen = SpecimenSpec(
            **{
                **{
                    f: getattr(ours["specimen"], f)
                    for f in ours["specimen"].__dataclass_fields__
                    if f != "physical_repeatability_hz"
                },
                "physical_repeatability_hz": Quantity(
                    0.8, "Hz", Provenance.MEASURED, "E2"
                ),
            }
        )
        mine = frequency_budget(ours["clock"], ours["capture"], specimen, 96.5)
        assert mine.dominant == "physical_repeatability"
        assert mine.is_electronic_lower_bound is False
        assert any("Improving the record length" in n for n in mine.notes)

    def test_improving_the_clock_does_not_change_the_narrative(self, source, ours):
        # The finding that changes operator behavior must survive a better clock.
        specimen = SpecimenSpec(
            **{
                **{
                    f: getattr(ours["specimen"], f)
                    for f in ours["specimen"].__dataclass_fields__
                    if f != "physical_repeatability_hz"
                },
                "physical_repeatability_hz": Quantity(0.8, "Hz", Provenance.MEASURED),
            }
        )
        better = ClockSpec(
            name="TCXO",
            rms_jitter_s=Quantity(1e-13, "s", Provenance.DATASHEET),
            accuracy_ppm=Quantity(0.5, "ppm", Provenance.DATASHEET),
        )
        mine = frequency_budget(better, ours["capture"], specimen, 96.5)
        assert mine.dominant == "physical_repeatability"


class TestSweepLimitsParity:
    @pytest.fixture(scope="class")
    def pair(self, source, ours):
        src = source.compute_sweep_limits(
            source.SweepSpec(
                f_start_hz=source.Quantity(60.0, "Hz", source.Provenance.ASSUMED),
                f_stop_hz=source.Quantity(2000.0, "Hz", source.Provenance.ASSUMED),
                expected_q=source.Quantity(50.0, "-", source.Provenance.PROPOSED),
            ),
            187.0,
        )
        return src, compute_sweep_limits(ours["sweep"], 187.0)

    @pytest.mark.parametrize(
        "field",
        [
            "time_constant_s",
            "min_dwell_per_step_s",
            "half_power_bandwidth_hz",
            "max_sweep_rate_hz_per_s",
            "min_total_sweep_time_s",
        ],
    )
    def test_every_limit_matches(self, pair, field):
        src, mine = pair
        assert getattr(mine, field) == src[field]

    def test_time_constant_relationship(self, pair):
        _, mine = pair
        assert mine.time_constant_s == pytest.approx(50.0 / (math.pi * 187.0))

    def test_higher_q_tightens_the_limits(self, ours):
        low = compute_sweep_limits(ours["sweep"], 187.0)
        high_q = SweepSpec(
            f_start_hz=Quantity(60.0, "Hz", Provenance.ASSUMED),
            f_stop_hz=Quantity(2000.0, "Hz", Provenance.ASSUMED),
            expected_q=Quantity(100.0, "-", Provenance.PROPOSED),
        )
        high = compute_sweep_limits(high_q, 187.0)
        assert high.max_sweep_rate_hz_per_s < low.max_sweep_rate_hz_per_s
        assert high.min_dwell_per_step_s > low.min_dwell_per_step_s

    def test_provisional_q_is_visible_in_the_result(self, pair):
        _, mine = pair
        assert mine.q_provenance is Provenance.PROPOSED
        assert mine.is_provisional is True
        assert any("PRELIMINARY" in n for n in mine.notes)

    def test_limits_are_advisory_only(self, pair):
        _, mine = pair
        assert any("do not drive the excitation system" in n for n in mine.notes)


class TestModulusDelegation:
    """The adapter must agree with the source *and* not own the coefficients."""

    @pytest.fixture(scope="class")
    def pair(self, source, ours):
        src = source.TTP_ANALYZER_PROFILE().compute()
        freq = frequency_budget(
            ours["clock"], ours["capture"], ours["specimen"], src.noise.combined_snb_db
        )
        return src.modulus, modulus_budget(ours["specimen"], freq)

    def test_contributions_agree_with_the_source(self, pair):
        src, mine = pair
        for term, value in src.contributions.items():
            assert mine.contributions[term] == pytest.approx(value, rel=1e-12)

    def test_combined_uncertainty_agrees(self, pair):
        src, mine = pair
        assert mine.relative_uncertainty == pytest.approx(
            src.relative_uncertainty, rel=1e-12
        )

    def test_dominant_term_agrees(self, pair):
        src, mine = pair
        assert mine.dominant == src.dominant

    def test_smallest_resolvable_difference_agrees(self, pair):
        src, mine = pair
        assert mine.smallest_resolvable_delta_pct == pytest.approx(
            src.smallest_resolvable_delta_pct, rel=1e-12
        )

    def test_the_engine_does_not_contain_the_sensitivity_coefficients(self):
        # The delegation guard. If this module ever grows its own copy of
        # E proportional to f^2 L^4 rho / t^2, this fails.
        source_text = (
            REPO_ROOT / "tap_tone_pi" / "uncertainty" / "acquisition" / "modulus.py"
        ).read_text(encoding="utf-8")
        for banned in ("4.0 *", "2.0 * (", "* 4 *", "sens_length", "L**4", "L ** 4"):
            assert banned not in source_text, (
                f"modulus.py appears to implement the propagation itself ({banned!r}); "
                "the canonical authority owns the coefficients"
            )

    def test_it_records_the_component_authority_and_canonical_aggregation(self, pair):
        _, mine = pair
        assert mine.component_authority.endswith("compute_tap_tone_moe_uncertainty")
        # An ordinary claim of delegation, now that it is true. DO-107A recorded
        # "canonical_components_with_B022_aggregate_workaround" here.
        assert mine.aggregation == "canonical"
        payload = mine.as_dict()
        assert payload["component_authority"] == mine.component_authority
        assert payload["aggregation"] == mine.aggregation
        assert not any("B-022" in n for n in mine.notes)

    def test_a5_no_local_aggregation_workaround_remains(self, source, ours):
        """B-022 is repaired at the authority; acquisition aggregates nothing.

        This replaces the DO-107A tripwire, which asserted that the canonical
        aggregate was *wrong* and deliberately failed once it was fixed. The
        permanent invariant is the one that outlives the defect: the adapter's
        combined figure is the canonical combined figure, taken verbatim.
        """
        from tap_tone_pi.uncertainty.stiffness import compute_tap_tone_moe_uncertainty

        src = source.TTP_ANALYZER_PROFILE().compute()
        freq = frequency_budget(
            ours["clock"], ours["capture"], ours["specimen"], src.noise.combined_snb_db
        )
        canonical = compute_tap_tone_moe_uncertainty(
            E_GPa=1.0,
            frequency_hz=187.0,
            frequency_uncertainty_hz=freq.combined_hz,
            length_mm=500.0,
            length_uncertainty_mm=0.5,
            thickness_mm=2.8,
            thickness_uncertainty_mm=0.02,
            density_kg_m3=420.0,
            density_uncertainty_kg_m3=4.0,
            snr_db=40.0,
            is_calibrated=True,
        )

        # 1. The canonical aggregate applies each coefficient exactly once.
        coefficient_once = math.sqrt(
            sum(
                (c.sensitivity_coefficient * c.value) ** 2 for c in canonical.components
            )
        )
        assert canonical.combined_standard_uncertainty == pytest.approx(
            coefficient_once, rel=1e-12
        ), "B-022 has regressed in uncertainty/stiffness.py"

        # 2. Components remain unweighted; the factor is carried, not baked in.
        by_name = {c.name: c for c in canonical.components}
        frequency = by_name["Frequency measurement"]
        assert frequency.sensitivity_coefficient == 2.0
        assert frequency.value == pytest.approx(freq.combined_hz / 187.0, rel=1e-12)

        # 3. The adapter reports the canonical aggregate itself -- not an RSS of
        #    components, not a corrected figure, not a parallel aggregation.
        mine = modulus_budget(ours["specimen"], freq)
        assert mine.relative_uncertainty == pytest.approx(
            canonical.combined_standard_uncertainty, rel=1e-12
        )

        # 4. Its per-term contributions are the weighted ones, matching the
        #    archived source calculator term by term.
        for term in ("frequency", "length", "thickness", "density"):
            assert mine.contributions[term] == pytest.approx(
                src.modulus.contributions[term], rel=1e-12
            )

    def test_a5_the_adapter_source_contains_no_aggregation_of_its_own(self):
        """Structural, not behavioural: the workaround cannot creep back."""
        source_text = (
            Path(__file__).resolve().parents[1]
            / "tap_tone_pi"
            / "uncertainty"
            / "acquisition"
            / "modulus.py"
        ).read_text(encoding="utf-8")
        after = source_text.split("def modulus_budget(", 1)[1]
        cut = after.find(chr(10) + "def ")
        body = after if cut == -1 else after[:cut]
        assert "rss(" not in body, (
            "modulus_budget aggregates locally again; the canonical combined "
            "figure must be consumed verbatim"
        )
        assert "combined_standard_uncertainty" in body

    def test_the_coefficients_come_from_the_canonical_authority(self, ours):
        # Verified by construction rather than by inspection: perturbing one
        # input must move its contribution by the canonical sensitivity.
        from tap_tone_pi.uncertainty.acquisition import ModulusBudget as MB

        assert isinstance(MB, type)
        base = ours["specimen"]
        freq = frequency_budget(ours["clock"], ours["capture"], base, 96.5)
        first = modulus_budget(base, freq)
        doubled = SpecimenSpec(
            **{
                **{f: getattr(base, f) for f in base.__dataclass_fields__},
                "length_uncertainty_m": Quantity(0.001, "m", Provenance.ASSUMED),
            }
        )
        second = modulus_budget(doubled, freq)
        # Length enters to the fourth power, so doubling its uncertainty doubles
        # that contribution - the coefficient is 4 and it is applied once.
        assert second.contributions["length"] == pytest.approx(
            2.0 * first.contributions["length"], rel=1e-12
        )

    def test_the_dimensional_finding_is_reported(self, pair):
        _, mine = pair
        assert mine.dominant in ("thickness", "length")
        assert any("Better calipers" in n for n in mine.notes)

    def test_missing_repeatability_marks_the_result_optimistic(self, pair):
        _, mine = pair
        assert any("OPTIMISTIC" in n for n in mine.notes)


class TestPreservedSourceSemantics:
    """Questionable source behavior reproduced and pinned, not improved.

    DO-107A establishes what the existing calculator says. Deciding what it ought
    to say is the source-reconciliation work, and silently changing it during
    integration would destroy the baseline that reconciliation needs.
    """

    def test_the_estimator_term_no_longer_enters_the_combination_twice(
        self, source, ours
    ):
        """B-021, provable half: the duplicate is gone; the source still has it.

        DO-107A reproduced the double count for parity. DO-107M removes it,
        because counting one quantity twice is wrong under any estimator model
        and does not wait on B-020.
        """
        src = source.TTP_ANALYZER_PROFILE().compute()
        mine = frequency_budget(
            ours["clock"], ours["capture"], ours["specimen"], src.noise.combined_snb_db
        )
        floor = mine.estimator_floor_hz
        clock_err = mine.clock_error_hz
        counted_once = math.sqrt(clock_err**2 + floor**2)
        counted_twice = math.sqrt(clock_err**2 + floor**2 + floor**2)
        assert mine.combined_hz == pytest.approx(counted_once, rel=1e-12)
        assert src.frequency.combined_hz == pytest.approx(counted_twice, rel=1e-12)

        # The estimator floor appears exactly once among the contributors, and
        # the bin width is still reported without entering the combination --
        # the open half of B-021.
        sources = [c.source_quantity for c in mine.combined_contributors]
        assert sources.count("estimator_floor_hz") == 1
        assert "bin_width_hz" not in sources
        assert mine.bin_width_hz > 0.0

        # At TTP profile values the estimator floor is ~1e-8 Hz against a
        # 3.7e-3 Hz clock error, so counting it twice is numerically invisible.
        # The defect is structural, and it is demonstrated where it bites: a
        # short record at low SNR, where the estimator term dominates.
        short = CaptureSpec(
            record_length_s=Quantity(0.05, "s", Provenance.ASSUMED),
            sample_rate_hz=Quantity(48000.0, "Hz", Provenance.DATASHEET),
            peak_interpolation=True,
        )
        loud_floor = frequency_budget(ours["clock"], short, ours["specimen"], 10.0)
        once = math.sqrt(
            loud_floor.clock_error_hz**2 + loud_floor.estimator_floor_hz**2
        )
        twice = math.sqrt(
            loud_floor.clock_error_hz**2 + 2 * loud_floor.estimator_floor_hz**2
        )
        assert loud_floor.combined_hz == pytest.approx(once, rel=1e-12)
        assert loud_floor.combined_hz != pytest.approx(twice, rel=1e-9)
        # Where the defect actually bit: the old aggregate was inflated by very
        # nearly sqrt(2) here, because the estimator term dominated.
        assert twice / once == pytest.approx(math.sqrt(2.0), rel=1e-3)

    def test_without_peak_interpolation_the_bin_width_is_used_instead(
        self, source, ours
    ):
        capture = CaptureSpec(
            record_length_s=Quantity(4.0, "s", Provenance.ASSUMED),
            sample_rate_hz=Quantity(48000.0, "Hz", Provenance.DATASHEET),
            peak_interpolation=False,
        )
        mine = frequency_budget(ours["clock"], capture, ours["specimen"], 96.5)
        expected = math.sqrt(
            mine.clock_error_hz**2 + mine.bin_width_hz**2 + mine.estimator_floor_hz**2
        )
        assert mine.combined_hz == pytest.approx(expected, rel=1e-12)

    def test_the_estimator_term_is_never_called_a_cramer_rao_bound(self):
        """F3. B-020 did not close, so this prohibition still stands.

        DO-107M established the SNR convention but refused to close B-020,
        because both candidate expressions assume a constant-amplitude sinusoid
        and a tap tone decays within a few percent of the record. Until that is
        settled, the term is not earned.

        Tightened in DO-107M: the guard previously accepted any occurrence of
        the substring "not" in the preceding 200 characters, which "note",
        "cannot" or "nothing" satisfy by accident. It now requires an explicit
        negation of the naming itself.
        """
        import re

        negation = re.compile(
            r"(deliberately not|never)\b|"
            r"\bnot\s+(called|labelled|labeled|named|claimed|a certified)"
        )
        package = REPO_ROOT / "tap_tone_pi" / "uncertainty" / "acquisition"
        checked = 0
        for path in package.glob("*.py"):
            raw = path.read_text(encoding="utf-8").lower()
            # Markdown emphasis would otherwise split "not* called".
            text = re.sub(r"[*_`]+", "", raw)
            text = re.sub(r"\s+", " ", text)
            for banned in ("cramer-rao", "cramér–rao", "cramer_rao", "crlb"):
                start = 0
                while (index := text.find(banned, start)) != -1:
                    preceding = text[max(0, index - 200) : index]
                    assert negation.search(preceding), (
                        f"{path.name} uses {banned!r} without explicitly "
                        "disclaiming it as a label"
                    )
                    checked += 1
                    start = index + len(banned)
        # The guard must actually be exercised; a silent zero would mean the
        # term had vanished from the package and the test proved nothing.
        assert checked >= 2

    def test_the_result_advertises_the_term_as_a_candidate(self, source, ours):
        mine = frequency_budget(ours["clock"], ours["capture"], ours["specimen"], 96.5)
        assert mine.as_dict()["estimator_floor_status"] == "candidate_source_formula"


class TestAuthorityGuards:
    def test_the_package_never_imports_the_session_diff_heuristic(self):
        # B-020 is an observed conflict, not an invitation to couple the two
        # implementations while reconciliation is pending.
        package = REPO_ROOT / "tap_tone_pi" / "uncertainty" / "acquisition"
        for path in package.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "session_diff" not in text.replace(
                "core/session_diff.py", ""
            ).replace("core.session_diff", ""), f"{path.name} references session_diff"

    def test_no_module_imports_numpy_scipy_or_pandas(self):
        package = REPO_ROOT / "tap_tone_pi" / "uncertainty" / "acquisition"
        for path in package.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for banned in ("import numpy", "import scipy", "import pandas"):
                assert banned not in text, f"{path.name} contains {banned!r}"

    def test_no_patch_02_material_was_incorporated(self):
        # Patch #2 arrived after the order was written and is archived, not
        # applied. Its distinguishing features must not appear in the engine.
        package = REPO_ROOT / "tap_tone_pi" / "uncertainty" / "acquisition"
        blob = "\n".join(
            p.read_text(encoding="utf-8").lower() for p in package.glob("*.py")
        )
        for marker in (
            "noise_subtracted",
            "sweep_regression",
            "operating_level_backoff",
            "backoff_db",
            "smart_guitar",
        ):
            assert marker not in blob, f"engine contains Patch #2 material: {marker}"


class TestStdlibOnlyIsExecutable:
    """DO-107 §4.10 as a capability, not an import-graph observation."""

    def test_a_budget_computes_with_numpy_unavailable(self):
        # NumPy is blocked at import time, then a representative TTP budget is
        # computed. The noise, frequency and sweep budgets must all succeed;
        # modulus must degrade with a reason rather than crash or invent one.
        program = f"""
import sys

class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("numpy", "scipy", "pandas"):
            raise ImportError(f"{{name}} is deliberately unavailable")
        return None

sys.meta_path.insert(0, _Blocker())
sys.path.insert(0, {str(REPO_ROOT)!r})

from tap_tone_pi.uncertainty.acquisition import (
    CaptureSpec, ClockSpec, ConverterSpec, FrontEndSpec, Provenance, Quantity,
    SpecimenSpec, SweepSpec, ModulusUnavailable,
    noise_budget, frequency_budget, compute_sweep_limits, modulus_budget,
)

Q, P = Quantity, Provenance
converter = ConverterSpec(
    name="HiFiBerry DAC+ ADC Pro", bits=24,
    full_scale_vrms=Q(2.1, "Vrms", P.DATASHEET),
    thermal_snr_db=Q(110.0, "dB", P.DATASHEET),
    aperture_jitter_s=Q(1e-12, "s", P.PROPOSED),
    sample_rate_hz=Q(48000.0, "Hz", P.DATASHEET),
)
clock = ClockSpec(name="xo", rms_jitter_s=Q(5e-12, "s", P.PROPOSED),
                  accuracy_ppm=Q(20.0, "ppm", P.ASSUMED))
front_end = FrontEndSpec(
    name="OPA1612",
    input_referred_noise_v_per_rthz=Q(1.1e-9, "V/rtHz", P.DATASHEET),
    gain_db=Q(52.0, "dB", P.PROPOSED), bandwidth_hz=Q(20000.0, "Hz", P.ASSUMED))
capture = CaptureSpec(record_length_s=Q(4.0, "s", P.ASSUMED),
                      sample_rate_hz=Q(48000.0, "Hz", P.DATASHEET))
sweep = SweepSpec(f_start_hz=Q(60.0, "Hz", P.ASSUMED),
                  f_stop_hz=Q(2000.0, "Hz", P.ASSUMED),
                  expected_q=Q(50.0, "-", P.PROPOSED))
specimen = SpecimenSpec(
    name="plate", mode_frequency_hz=Q(187.0, "Hz", P.ASSUMED),
    length_m=Q(0.5, "m", P.ASSUMED), length_uncertainty_m=Q(0.0005, "m", P.ASSUMED),
    thickness_m=Q(0.0028, "m", P.ASSUMED),
    thickness_uncertainty_m=Q(2e-5, "m", P.ASSUMED),
    density_kg_m3=Q(420.0, "kg/m3", P.ASSUMED),
    density_uncertainty_kg_m3=Q(4.0, "kg/m3", P.ASSUMED))

n = noise_budget(converter, clock, front_end, 187.0)
f = frequency_budget(clock, capture, specimen, n.combined_snr_db)
s = compute_sweep_limits(sweep, 187.0)
try:
    modulus_budget(specimen, f)
    modulus = "COMPUTED"
except ModulusUnavailable:
    modulus = "UNAVAILABLE"

assert "numpy" not in sys.modules, "numpy leaked in"
print(n.limiter, round(n.combined_snr_db, 2), round(f.combined_hz, 9),
      round(s.max_sweep_rate_hz_per_s, 6), modulus)
"""
        result = subprocess.run(
            [sys.executable, "-c", program], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        limiter, snr, combined_hz, rate, modulus = result.stdout.split()
        assert limiter == "front_end"
        assert float(snr) > 90.0
        assert float(combined_hz) > 0.0
        assert float(rate) > 0.0
        # Modulus delegates to the canonical authority, which needs NumPy. It
        # must say so rather than crash or fabricate a propagation.
        assert modulus == "UNAVAILABLE"


class TestRepresentationHardening:
    """Commit 4: the record must be able to say what Commit 3 knows.

    Three gaps were found by the contract-readiness inspection and closed here.
    None of them changes a number — the parity battery above still passes
    unchanged, which is the point.
    """

    @pytest.fixture
    def budget(self, ours):
        return frequency_budget(ours["clock"], ours["capture"], ours["specimen"], 96.5)

    # --- B: contributors actually entering the aggregate --------------------

    def test_combined_is_the_rss_of_the_serialized_contributors(self, budget):
        # The contract guarantee. combined_hz is the RSS of these values and of
        # nothing else, checked from the serialized form so it survives a
        # round-trip through JSON.
        payload = budget.as_dict()
        values = [c["value_hz"] for c in payload["combined_contributors"]]
        assert values, "no contributors serialized"
        assert payload["combined_hz"] == pytest.approx(
            math.sqrt(sum(v * v for v in values)), rel=1e-12
        )

    def test_b021_duplicate_is_repaired_and_the_rest_stays_visible_as_data(
        self, budget
    ):
        """The provable half is fixed; the open half is still legible.

        DO-107A recorded ``estimator_floor_hz`` filling two slots. That
        duplicate is removed. The sequence still carries role and source
        separately, so the remaining question -- a reported bin width that does
        not enter the aggregate -- is readable straight off the data rather
        than inferred from a number that happens not to move.
        """
        sources = [c.source_quantity for c in budget.combined_contributors]
        assert sources.count("estimator_floor_hz") == 1
        assert len(sources) == len(set(sources))
        assert "bin_width_hz" not in sources

    def test_a_reported_quantity_can_be_absent_from_the_combination(self, budget):
        # Bin width is 0.25 Hz next to a combined figure of 0.0037 Hz. Before
        # this change a reader had no way to tell it contributed nothing.
        assert budget.bin_width_hz > budget.combined_hz * 50
        assert all(
            c.source_quantity != "bin_width_hz" for c in budget.combined_contributors
        )

    def test_the_roles_and_their_sources_are_distinguishable(self, budget):
        by_role = {c.role: c.source_quantity for c in budget.combined_contributors}
        assert by_role["spectral_resolution"] == "estimator_floor_hz"
        assert by_role["clock_accuracy"] == "clock_error_hz"

    def test_without_peak_interpolation_the_bin_width_does_contribute(self, ours):
        capture = CaptureSpec(
            record_length_s=Quantity(4.0, "s", Provenance.ASSUMED),
            sample_rate_hz=Quantity(48000.0, "Hz", Provenance.DATASHEET),
            peak_interpolation=False,
        )
        budget = frequency_budget(ours["clock"], capture, ours["specimen"], 96.5)
        sources = [c.source_quantity for c in budget.combined_contributors]
        assert sources.count("bin_width_hz") == 1
        assert sources.count("estimator_floor_hz") == 1

    def test_measured_repeatability_appears_as_a_contributor(self, ours):
        specimen = SpecimenSpec(
            **{
                **{
                    f: getattr(ours["specimen"], f)
                    for f in ours["specimen"].__dataclass_fields__
                },
                "physical_repeatability_hz": Quantity(0.8, "Hz", Provenance.MEASURED),
            }
        )
        budget = frequency_budget(ours["clock"], ours["capture"], specimen, 96.5)
        roles = [c.role for c in budget.combined_contributors]
        assert "physical_repeatability" in roles

    # --- C: the estimator status is typed and round-trips -------------------

    def test_the_estimator_status_is_a_typed_field(self, budget):
        from tap_tone_pi.uncertainty.acquisition import FormulaStatus

        assert budget.estimator_floor_status is FormulaStatus.CANDIDATE_SOURCE_FORMULA
        assert budget.estimator_floor_status.is_established is False

    def test_the_frequency_budget_round_trips(self, budget):
        from tap_tone_pi.uncertainty.acquisition import FrequencyBudget

        restored = FrequencyBudget.from_dict(budget.as_dict())
        assert restored == budget

    def test_the_status_survives_json(self, budget):
        import json

        from tap_tone_pi.uncertainty.acquisition import FormulaStatus, FrequencyBudget

        restored = FrequencyBudget.from_dict(json.loads(json.dumps(budget.as_dict())))
        assert restored.estimator_floor_status is FormulaStatus.CANDIDATE_SOURCE_FORMULA
        assert restored.combined_contributors == budget.combined_contributors

    def test_the_status_is_not_quietly_promoted(self, budget):
        # B-020 and the source-verification question remain open, so nothing here
        # may claim the expression is settled.
        assert budget.as_dict()["estimator_floor_status"] == "candidate_source_formula"

    # --- A: unavailable is representable, not an exception ------------------

    def test_an_available_modulus_carries_the_discriminator(self, source, ours):
        src = source.TTP_ANALYZER_PROFILE().compute()
        freq = frequency_budget(
            ours["clock"], ours["capture"], ours["specimen"], src.noise.combined_snb_db
        )
        from tap_tone_pi.uncertainty.acquisition import (
            ResultAvailability,
            modulus_budget_or_unavailable,
        )

        result = modulus_budget_or_unavailable(ours["specimen"], freq)
        assert result.availability is ResultAvailability.AVAILABLE
        assert result.as_dict()["availability"] == "available"

    def test_an_unavailable_section_fabricates_nothing(self):
        from tap_tone_pi.uncertainty.acquisition import (
            UnavailableSection,
        )

        section = UnavailableSection(
            reason_code="canonical_authority_unavailable",
            reason="canonical uncertainty authority unavailable in the "
            "instrument-safe environment",
        )
        payload = section.as_dict()
        assert payload["availability"] == "unavailable"
        assert payload["reason_code"] == "canonical_authority_unavailable"
        # No numeric field at all - nothing to mistake for a result.
        assert not any(isinstance(v, (int, float)) for v in payload.values())
        assert UnavailableSection.from_dict(payload) == section

    def test_the_reason_is_specific_not_generic(self):
        from tap_tone_pi.uncertainty.acquisition import UnavailableSection

        section = UnavailableSection.from_dict(
            {
                "availability": "unavailable",
                "reason_code": "canonical_authority_unavailable",
                "reason": "canonical uncertainty authority unavailable in the "
                "instrument-safe environment",
            }
        )
        assert "canonical uncertainty authority" in section.reason
        for generic in ("computation failed", "error", "unknown"):
            assert generic not in section.reason.lower()

    def test_the_modulus_budget_round_trips(self, source, ours):
        from tap_tone_pi.uncertainty.acquisition import ModulusBudget

        src = source.TTP_ANALYZER_PROFILE().compute()
        freq = frequency_budget(
            ours["clock"], ours["capture"], ours["specimen"], src.noise.combined_snb_db
        )
        result = modulus_budget(ours["specimen"], freq)
        assert ModulusBudget.from_dict(result.as_dict()) == result


class TestB021ContributorComposition:
    """DO-107M: contributor identity and multiplicity, asserted structurally.

    The lesson from DO-107A Commit 6 is the organising principle here. A
    contributor that adds nothing to the root-sum-square cannot be found by
    watching the aggregate move, so every check below reads the sequence
    directly. None of them infer composition from a number.
    """

    @staticmethod
    def _capture(peak_interpolation: bool) -> CaptureSpec:
        return CaptureSpec(
            record_length_s=Quantity(4.0, "s", Provenance.ASSUMED),
            sample_rate_hz=Quantity(48000.0, "Hz", Provenance.DATASHEET),
            peak_interpolation=peak_interpolation,
        )

    def _budget(self, ours, peak_interpolation, repeatability=None):
        specimen = ours["specimen"]
        if repeatability is not None:
            specimen = SpecimenSpec(
                **{
                    **{f: getattr(specimen, f) for f in specimen.__dataclass_fields__},
                    "physical_repeatability_hz": repeatability,
                }
            )
        return frequency_budget(
            ours["clock"], self._capture(peak_interpolation), specimen, 96.5
        )

    def test_f5_every_contributor_names_a_role_a_source_and_a_value(self, ours):
        for interpolation in (True, False):
            budget = self._budget(ours, interpolation)
            for contributor in budget.combined_contributors:
                assert contributor.role
                assert contributor.source_quantity
                assert isinstance(contributor.value_hz, float)

    def test_f6_multiplicity_is_asserted_directly_not_inferred(self, ours):
        """No source quantity enters the combination more than once."""
        for interpolation in (True, False):
            sources = [
                c.source_quantity
                for c in self._budget(ours, interpolation).combined_contributors
            ]
            assert len(sources) == len(set(sources)), sources

    def test_the_contributor_count_is_not_fixed(self, ours):
        """Two, three or four -- the count depends on configuration.

        Recorded because it is easy to write a downstream check that assumes a
        constant number of terms. Peak interpolation collapses the spectral
        resolution term and the estimator floor into one slot; physical
        repeatability adds a term only when the specimen supplies it.
        """
        assert len(self._budget(ours, True).combined_contributors) == 2
        assert len(self._budget(ours, True, 0.02).combined_contributors) == 3
        assert len(self._budget(ours, False).combined_contributors) == 3
        assert len(self._budget(ours, False, 0.02).combined_contributors) == 4

    def test_f8_bin_width_stays_reportable_when_it_does_not_contribute(self, ours):
        """B-021's open half: reported, excluded, and visibly so.

        Closing the duplicate did not mean putting the bin width into the
        aggregate. It remains a serialized reportable quantity whose absence
        from the combination a reader can see, which is what keeps the open
        question legible instead of implicit.
        """
        budget = self._budget(ours, True)
        assert budget.bin_width_hz > 0.0
        assert "bin_width_hz" not in [
            c.source_quantity for c in budget.combined_contributors
        ]
        payload = budget.as_dict()
        assert payload["bin_width_hz"] == budget.bin_width_hz

    def test_f7_combined_is_the_rss_of_the_contributors_in_every_configuration(
        self, ours
    ):
        for interpolation in (True, False):
            for repeatability in (None, 0.02):
                budget = self._budget(ours, interpolation, repeatability)
                assert budget.combined_hz == pytest.approx(
                    math.sqrt(sum(c.value_hz**2 for c in budget.combined_contributors)),
                    rel=1e-12,
                )

    def test_the_estimator_floor_enters_exactly_once_in_both_modes(self, ours):
        for interpolation in (True, False):
            sources = [
                c.source_quantity
                for c in self._budget(ours, interpolation).combined_contributors
            ]
            assert sources.count("estimator_floor_hz") == 1
