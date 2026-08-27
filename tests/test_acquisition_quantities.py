"""Acquisition quantities, specifications, and the stdlib boundary (DO-107A).

Two lines are held here.

**A number carries where it came from.** Provenance survives construction and
serialization unchanged, a bare float arrives explicitly weak rather than
untagged, and nothing may be built from a value that is not finite.

**The acquisition core loads on the instrument.** DO-107 §4.10 requires it to
import without NumPy *transitively*, which is stricter than "no `import numpy`
in these files" — the leak that had to be closed was a parent package's eager
`__init__`, not anything in this package.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from tap_tone_pi.uncertainty.acquisition import (
    AcquisitionQuantityError,
    CaptureSpec,
    ClockSpec,
    ConverterSpec,
    FrontEndSpec,
    Provenance,
    Quantity,
    SpecimenSpec,
    SweepSpec,
    as_quantity,
    spec_quantities,
)


def q(value=1.0, unit="Hz", provenance=Provenance.MEASURED, source="test"):
    return Quantity(value, unit, provenance, source)


def converter(**overrides):
    base = dict(
        name="test converter",
        bits=24,
        full_scale_vrms=q(2.1, "Vrms", Provenance.DATASHEET),
        thermal_snr_db=q(110.0, "dB", Provenance.DATASHEET),
        aperture_jitter_s=q(1e-12, "s", Provenance.PROPOSED),
        sample_rate_hz=q(48000.0, "Hz", Provenance.DATASHEET),
    )
    base.update(overrides)
    return ConverterSpec(**base)


def clock(**overrides):
    base = dict(
        name="test clock",
        rms_jitter_s=q(5e-12, "s", Provenance.PROPOSED),
        accuracy_ppm=q(20.0, "ppm", Provenance.ASSUMED),
    )
    base.update(overrides)
    return ClockSpec(**base)


def specimen(**overrides):
    base = dict(
        name="test plate",
        mode_frequency_hz=q(187.0, "Hz", Provenance.ASSUMED),
        length_m=q(0.5, "m", Provenance.ASSUMED),
        length_uncertainty_m=q(0.0005, "m", Provenance.ASSUMED),
        thickness_m=q(0.0028, "m", Provenance.ASSUMED),
        thickness_uncertainty_m=q(2e-5, "m", Provenance.ASSUMED),
        density_kg_m3=q(420.0, "kg/m3", Provenance.ASSUMED),
        density_uncertainty_kg_m3=q(4.0, "kg/m3", Provenance.ASSUMED),
    )
    base.update(overrides)
    return SpecimenSpec(**base)


class TestProvenance:
    @pytest.mark.parametrize("member", list(Provenance))
    def test_every_member_round_trips(self, member):
        assert Provenance(member.value) is member
        assert Quantity.from_dict(q(provenance=member).as_dict()).provenance is member

    def test_an_unknown_provenance_is_refused(self):
        with pytest.raises(AcquisitionQuantityError) as exc:
            Quantity(1.0, "Hz", "vibes")
        assert "unknown provenance" in str(exc.value)

    @pytest.mark.parametrize(
        "member,expected",
        [
            (Provenance.PROPOSED, False),
            (Provenance.ASSUMED, False),
            (Provenance.DATASHEET, True),
            (Provenance.DERIVED, True),
            (Provenance.MEASURED, True),
        ],
    )
    def test_which_tags_can_support_evidence(self, member, expected):
        # The split is the whole reason the vocabulary exists: the first two are
        # stated intentions, the rest have something behind them.
        assert member.is_evidence is expected

    def test_a_string_value_compares_equal_to_the_member(self):
        # Provenance is a str Enum so serialized records stay readable.
        assert Provenance.MEASURED == "measured"


class TestQuantity:
    def test_unit_and_source_are_preserved(self):
        item = Quantity(2.1, "Vrms", Provenance.DATASHEET, "Rev 1.5 unbalanced max")
        assert item.unit == "Vrms"
        assert item.source == "Rev 1.5 unbalanced max"
        assert item.as_dict()["source"] == "Rev 1.5 unbalanced max"

    def test_round_trip_preserves_everything(self):
        item = Quantity(1e-12, "s", Provenance.PROPOSED, "placeholder pending E0")
        assert Quantity.from_dict(item.as_dict()) == item

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_values_are_refused(self, bad):
        # A NaN uncertainty reads as "no answer yet" rather than as a defect,
        # which is how it would survive all the way into a report.
        with pytest.raises(AcquisitionQuantityError) as exc:
            Quantity(bad, "Hz", Provenance.MEASURED)
        assert "finite" in str(exc.value)

    @pytest.mark.parametrize("bad", ["1.0", None, [1.0]])
    def test_non_numeric_values_are_refused(self, bad):
        with pytest.raises(AcquisitionQuantityError):
            Quantity(bad, "Hz", Provenance.MEASURED)

    def test_a_bool_is_not_a_number(self):
        with pytest.raises(AcquisitionQuantityError):
            Quantity(True, "Hz", Provenance.MEASURED)

    def test_integers_are_accepted_and_normalized(self):
        assert Quantity(48000, "Hz", Provenance.DATASHEET).value == 48000.0

    def test_a_payload_without_provenance_is_refused(self):
        with pytest.raises(AcquisitionQuantityError) as exc:
            Quantity.from_dict({"value": 1.0, "unit": "Hz"})
        assert "records no provenance" in str(exc.value)

    def test_an_unknown_payload_field_is_refused(self):
        with pytest.raises(AcquisitionQuantityError):
            Quantity.from_dict(
                {
                    "value": 1.0,
                    "unit": "Hz",
                    "provenance": "measured",
                    "measured_by": "x",
                }
            )

    def test_quantities_are_frozen(self):
        item = q()
        with pytest.raises(Exception):
            item.value = 2.0  # type: ignore[misc]

    def test_float_conversion(self):
        assert float(q(187.0)) == 187.0


class TestBareValueCoercion:
    def test_a_bare_float_arrives_explicitly_weak(self):
        # Callers may be lazy at an edge; the laziness is recorded, not hidden.
        coerced = as_quantity(3.0, "Hz")
        assert coerced.provenance is Provenance.ASSUMED
        assert coerced.provenance.is_evidence is False
        assert "bare value" in coerced.source

    def test_a_bare_float_never_becomes_measured(self):
        assert as_quantity(3.0, "Hz").provenance is not Provenance.MEASURED

    def test_an_existing_quantity_passes_through_untouched(self):
        item = q(5.0, "Hz", Provenance.MEASURED, "E0 T1")
        assert as_quantity(item) is item


class TestSpecifications:
    def test_specifications_are_frozen(self):
        spec = converter()
        with pytest.raises(Exception):
            spec.bits = 16  # type: ignore[misc]

    def test_nyquist_is_half_the_sample_rate(self):
        assert converter().nyquist_hz() == 24000.0

    def test_capture_sample_count_and_bin_width(self):
        capture = CaptureSpec(
            record_length_s=q(4.0, "s", Provenance.ASSUMED),
            sample_rate_hz=q(48000.0, "Hz", Provenance.DATASHEET),
        )
        assert capture.n_samples() == 192000
        assert capture.bin_width_hz() == pytest.approx(0.25)

    def test_bin_width_agrees_with_the_canonical_resolution_function(self):
        # DO-107A delegates bin resolution to the canonical authority. Literal
        # delegation is impossible from the stdlib core - importing that function
        # pulls NumPy - so agreement is pinned by test instead, and the
        # delegation itself happens at the integration boundary.
        from tap_tone_pi.uncertainty import compute_frequency_resolution

        capture = CaptureSpec(
            record_length_s=q(4.0, "s", Provenance.ASSUMED),
            sample_rate_hz=q(48000.0, "Hz", Provenance.DATASHEET),
        )
        canonical = compute_frequency_resolution(
            int(float(capture.sample_rate_hz)), capture.n_samples()
        )
        assert capture.bin_width_hz() == pytest.approx(canonical)

    @pytest.mark.parametrize("bits", [0, -24, 24.0, True])
    def test_bit_depth_must_be_a_positive_integer(self, bits):
        with pytest.raises(AcquisitionQuantityError):
            converter(bits=bits)

    @pytest.mark.parametrize(
        "field", ["full_scale_vrms", "aperture_jitter_s", "sample_rate_hz"]
    )
    def test_converter_quantities_must_be_positive(self, field):
        with pytest.raises(AcquisitionQuantityError):
            converter(**{field: q(0.0, "x", Provenance.ASSUMED)})

    def test_an_unmeasured_coupling_corner_is_none_not_zero(self):
        # None means unmeasured, which is a finding. Zero would be a claim.
        assert converter().hp_corner_hz is None

    def test_an_unrecognised_clock_topology_is_refused(self):
        with pytest.raises(AcquisitionQuantityError) as exc:
            clock(topology="quantum")
        assert "topology" in str(exc.value)

    def test_a_spurious_clock_invalidates_the_gaussian_model(self):
        assert clock(spurious=False).is_gaussian_model_valid() is True
        assert clock(spurious=True).is_gaussian_model_valid() is False

    def test_clock_accuracy_may_be_zero_but_not_negative(self):
        assert clock(accuracy_ppm=q(0.0, "ppm", Provenance.MEASURED))
        with pytest.raises(AcquisitionQuantityError):
            clock(accuracy_ppm=q(-1.0, "ppm", Provenance.MEASURED))

    def test_a_sweep_must_run_upward(self):
        with pytest.raises(AcquisitionQuantityError):
            SweepSpec(
                f_start_hz=q(2000.0, "Hz", Provenance.ASSUMED),
                f_stop_hz=q(60.0, "Hz", Provenance.ASSUMED),
                expected_q=q(50.0, "-", Provenance.PROPOSED),
            )

    def test_a_non_positive_q_is_refused(self):
        with pytest.raises(AcquisitionQuantityError):
            SweepSpec(
                f_start_hz=q(60.0, "Hz", Provenance.ASSUMED),
                f_stop_hz=q(2000.0, "Hz", Provenance.ASSUMED),
                expected_q=q(0.0, "-", Provenance.PROPOSED),
            )

    def test_front_end_carries_no_calculation(self):
        # Front-end noise arithmetic belongs to the budget engine, not here. A
        # specification that caches results is no longer a statement about a rig.
        front_end = FrontEndSpec(
            name="preamp",
            input_referred_noise_v_per_rthz=q(1.1e-9, "V/rtHz", Provenance.DATASHEET),
            gain_db=q(52.0, "dB", Provenance.PROPOSED),
            bandwidth_hz=q(20000.0, "Hz", Provenance.ASSUMED),
        )
        for banned in ("output_noise_vrms", "snr_db"):
            assert not hasattr(front_end, banned)


class TestPhysicalRepeatability:
    def test_it_has_no_default(self):
        # Session-to-session variation routinely dominates every electronic term
        # combined. A plausible default would make a budget look complete while
        # resting on a figure nobody observed.
        assert specimen().physical_repeatability_hz is None
        assert specimen().has_measured_repeatability() is False

    def test_a_measured_value_is_recognised(self):
        with_rep = specimen(
            physical_repeatability_hz=q(0.8, "Hz", Provenance.MEASURED, "E2")
        )
        assert with_rep.has_measured_repeatability() is True

    def test_zero_repeatability_is_distinguishable_from_unmeasured(self):
        measured_zero = specimen(
            physical_repeatability_hz=q(0.0, "Hz", Provenance.MEASURED)
        )
        assert measured_zero.has_measured_repeatability() is True
        assert specimen().has_measured_repeatability() is False

    def test_negative_repeatability_is_refused(self):
        with pytest.raises(AcquisitionQuantityError):
            specimen(physical_repeatability_hz=q(-1.0, "Hz", Provenance.MEASURED))


class TestProvenanceWalk:
    def test_every_quantity_on_a_spec_is_found(self):
        found = spec_quantities(converter())
        assert len(found) == 4
        assert all(isinstance(item, Quantity) for item in found)

    def test_the_walk_follows_fields_rather_than_a_hand_written_list(self):
        # A field added to a specification must not be able to escape the
        # provenance count silently.
        names = {f for f in ConverterSpec.__dataclass_fields__}
        assert "thermal_snr_db" in names
        assert len(spec_quantities(specimen())) == 7
        assert (
            len(
                spec_quantities(
                    specimen(
                        physical_repeatability_hz=q(0.8, "Hz", Provenance.MEASURED)
                    )
                )
            )
            == 8
        )


class TestTheStdlibBoundary:
    """DO-107 §4.10, enforced transitively rather than by grepping for imports."""

    @staticmethod
    def _numpy_loaded_after(statement: str) -> bool:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import sys\n{statement}\nprint('numpy' in sys.modules)",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip() == "True"

    @pytest.mark.parametrize(
        "statement",
        [
            "import tap_tone_pi.uncertainty.acquisition",
            "import tap_tone_pi.uncertainty.acquisition.quantities",
            "import tap_tone_pi.uncertainty.acquisition.specs",
            "from tap_tone_pi.uncertainty.acquisition import Quantity, ConverterSpec",
        ],
    )
    def test_the_acquisition_core_loads_without_numpy(self, statement):
        # The leak this closes was not in these files. It was the parent
        # package's eager __init__, which pulled NumPy through budget and
        # propagation and therefore into every subpackage beneath it. A test
        # that only grepped these files for "import numpy" would have passed
        # while the constraint was false.
        assert self._numpy_loaded_after(statement) is False

    def test_the_parent_package_is_also_clean_to_import(self):
        assert self._numpy_loaded_after("import tap_tone_pi.uncertainty") is False

    def test_the_canonical_authority_still_resolves(self):
        # Laziness must not have broken the public API - it only moves when the
        # heavy import happens.
        assert (
            self._numpy_loaded_after(
                "from tap_tone_pi.uncertainty import compute_tap_tone_moe_uncertainty"
            )
            is True
        )

    def test_the_acquisition_package_does_not_import_the_uncertainty_authorities(self):
        import tap_tone_pi.uncertainty.acquisition.quantities as quantities
        import tap_tone_pi.uncertainty.acquisition.specs as specs

        for module in (quantities, specs):
            source = open(module.__file__, encoding="utf-8").read()
            for banned in ("from ..budget", "from ..propagation", "import numpy"):
                assert banned not in source, f"{module.__name__} imports {banned}"


class TestTheArchivedSourceSurvivesTheRepository:
    """Archived source is identified by digest, so its bytes must round-trip.

    Two repository mechanisms tried to rewrite it: the whitespace and
    end-of-file hooks, and git's line-ending normalization. Both are correct for
    source code and both silently invalidate a recorded digest, which turns a
    provenance record into a false one.
    """

    ARCHIVE = "docs/reference/acquisition"
    EXPECTED = {
        "JITTER_TO_SNR_CALCULATOR.html": "052d1fb009f314c8cdee11e03efef6a56fdc7e993bd9c0184e62c0d19960ac05",
        "deferred/patch-02-acquisition.patch": "9e964a8e6408ba97",
        "deferred/TTP_ACQUISITION_MATHEMATICS.md": "c9a77a862913206a",
    }

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_the_archived_bytes_match_the_recorded_digest(self, name):
        import hashlib
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        digest = hashlib.sha256((root / self.ARCHIVE / name).read_bytes()).hexdigest()
        assert digest.startswith(self.EXPECTED[name]), (
            f"{name} no longer matches the digest recorded in the archive README. "
            "Something rewrote archived source - check the pre-commit exclusions "
            "and .gitattributes before updating the recorded value."
        )

    def test_the_archive_is_excluded_from_rewriting_hooks(self):
        # Four hooks rewrite files in place, and each would invalidate a recorded
        # digest. trailing-whitespace and end-of-file-fixer mangled the archive
        # once already; ruff and ruff-format would reformat the archived parity
        # source, which is a .py file.
        from pathlib import Path

        config = (
            Path(__file__).resolve().parents[1] / ".pre-commit-config.yaml"
        ).read_text(encoding="utf-8")
        for hook in ("ruff", "ruff-format", "trailing-whitespace", "end-of-file-fixer"):
            marker = f"- id: {hook}\n"
            assert marker in config, f"hook {hook} not found"
            following = config.split(marker, 1)[1][:220]
            assert "exclude: ^docs/reference/acquisition/" in following, (
                f"{hook} may rewrite the archived source and invalidate its digest"
            )

    def test_the_archive_is_excluded_from_line_ending_normalization(self):
        from pathlib import Path

        attrs = (Path(__file__).resolve().parents[1] / ".gitattributes").read_text(
            encoding="utf-8"
        )
        assert "docs/reference/acquisition/** -text" in attrs
