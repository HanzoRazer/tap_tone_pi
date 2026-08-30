# INSTRUMENT CLASS: MEASUREMENT
"""B-020 -- what DO-107M established about the estimator floor, and what it did not.

DO-107M was authorized to close B-020 if literature reconciliation supported
it, and equally authorized to leave it open. **It is left open.** These tests
record the investigation so the next attempt starts from evidence rather than
from a second reading of the same code.

What was established
--------------------

The source expression is a Cramer-Rao lower bound, stated under a particular
SNR convention. For a constant-amplitude real sinusoid in white Gaussian noise
with amplitude, phase and frequency unknown, the classical bound is::

    var(f) >= 12 * fs**2 / ((2*pi)**2 * eta * N * (N**2 - 1)),  eta = A**2/(2*s**2)

which for large N with ``T = N/fs`` reduces to ``(1/(pi*T)) * sqrt(3/(eta*N))``.
The source computes ``(1/(pi*T)) * sqrt(6/(SNR*N))``. The two differ by exactly
``sqrt(2)``, and substituting the squared-amplitude convention ``A**2/s**2`` for
the power convention ``A**2/(2*s**2)`` carries one into the other. They are the
same bound under two conventions.

TTP feeds the **power** convention. ``quantization_snr_db`` is
``6.02*bits + 1.76``, the full-scale sine figure whose 1.76 dB is
``10*log10(3/2)``, and ``combine_snr_db`` combines on a noise-power basis.
Under that convention the source expression is ``sqrt(2)`` conservative.

Why B-020 is still open
-----------------------

Both candidates assume a sinusoid of **constant amplitude across the whole
record**. A tap tone is a freely decaying mode. With Q between 10 and 100 --
the range this repository's own damping module works in -- a 187 Hz mode has an
amplitude decay constant of 17 to 170 ms against a 4 s record, so most of the
record carries no signal while the bound counts every sample as contributing
Fisher information. That mismatch is unbounded by anything established here and
is larger than the ``sqrt(2)`` it would correct.

Adopting the ``sqrt(3)`` form would therefore trade a conservative factor for an
optimistic model, which is the worse error in a measurement instrument.
Deciding requires the damped-sinusoid bound and its dependence on ``tau/T``,
which is a research task and not a formula substitution. B-020 stays blocking,
the expression keeps ``candidate_source_formula``, and the F3 prohibition on
Cramer-Rao terminology stands.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from tap_tone_pi.uncertainty.acquisition import (
    FormulaStatus,
    combine_snr_db,
    estimator_floor_candidate_hz,
    quantization_snr_db,
)
from tests._util.estimator_comparison import (
    compare_estimators,
    crlb_exact_power_snr_hz,
    crlb_power_snr_hz,
    modal_decay_time_s,
)


class TestF1TheReconciledEquation:
    """The CRLB encoded with its units and assumptions, as a reference only."""

    def test_the_large_n_form_matches_the_exact_bound(self):
        """``N(N**2-1) -> N**3`` is not a material approximation at TTP sizes."""
        assert crlb_power_snr_hz(4.0, 192000, 96.5) == pytest.approx(
            crlb_exact_power_snr_hz(4.0, 192000, 96.5), rel=1e-9
        )

    def test_the_bound_scales_as_the_theory_requires(self):
        """Independent structural checks on the encoded expression."""
        base = crlb_power_snr_hz(4.0, 192000, 40.0)
        # Doubling the record length at a fixed sample rate doubles N as well,
        # so sigma falls by 2 * sqrt(2).
        assert crlb_power_snr_hz(8.0, 384000, 40.0) == pytest.approx(
            base / (2.0 * math.sqrt(2.0)), rel=1e-12
        )
        # 10 dB more SNR is a factor of 10 in power, sqrt(10) in sigma.
        assert crlb_power_snr_hz(4.0, 192000, 50.0) == pytest.approx(
            base / math.sqrt(10.0), rel=1e-12
        )


class TestF2SourceComparison:
    """The numerical relationship between the two candidates, recorded exactly."""

    OPERATING_POINTS = [
        (4.0, 192000, 96.5),
        (4.0, 192000, 40.0),
        (1.0, 48000, 60.0),
        (0.05, 2400, 10.0),
    ]

    @pytest.mark.parametrize("record_s,n,snr_db", OPERATING_POINTS)
    def test_the_source_exceeds_the_crlb_by_exactly_root_two(self, record_s, n, snr_db):
        """Not approximately, and not only at one operating point.

        A constant ratio across record length, sample count and SNR is what
        distinguishes a convention difference from a modelling difference. Had
        the ratio drifted with any argument, the two expressions would encode
        different physics rather than different bookkeeping.
        """
        comparison = compare_estimators(record_s, n, snr_db)
        assert comparison.ratio_source_over_crlb == pytest.approx(
            math.sqrt(2.0), rel=1e-12
        )
        assert comparison.source_hz > comparison.crlb_power_snr_hz

    def test_the_convention_substitution_reproduces_the_source(self):
        """sqrt(3) under A**2/s**2 IS sqrt(6) under A**2/(2*s**2)."""
        record_s, n, snr_db = 4.0, 192000, 40.0
        eta_power = 10.0 ** (snr_db / 10.0)
        # Evaluating the sqrt(3) bound with the squared-amplitude SNR -- which
        # is twice the power SNR -- lands exactly on the power-SNR CRLB.
        under_squared_amplitude = (1.0 / (math.pi * record_s)) * math.sqrt(
            3.0 / ((2.0 * eta_power) * n)
        )
        assert under_squared_amplitude == pytest.approx(
            crlb_power_snr_hz(record_s, n, snr_db) / math.sqrt(2.0), rel=1e-12
        )
        assert estimator_floor_candidate_hz(record_s, n, snr_db) == pytest.approx(
            (1.0 / (math.pi * record_s)) * math.sqrt(6.0 / (eta_power * n)),
            rel=1e-12,
        )


class TestTheSnrConventionTtpActuallyFeeds:
    """Which convention reaches the estimator is a fact about this code."""

    def test_quantization_snr_is_the_full_scale_sine_figure(self):
        assert quantization_snr_db(24) == pytest.approx(6.02 * 24 + 1.76)
        # 1.76 dB is 10*log10(3/2), which arises from signal power A**2/2 over
        # quantization noise power. A squared-amplitude convention would not
        # produce this constant.
        assert 1.76 == pytest.approx(10.0 * math.log10(1.5), abs=5e-3)

    def test_snr_terms_combine_on_a_noise_power_basis(self):
        # Two equal power SNRs combine to 3 dB worse, the signature of adding
        # noise powers rather than amplitudes.
        assert combine_snr_db(100.0, 100.0) == pytest.approx(100.0 - 3.0103, abs=1e-3)


class TestWhyB020RemainsOpen:
    """The assumption that does not map onto a tap tone."""

    @pytest.mark.parametrize("q_factor", [10.0, 50.0, 100.0])
    def test_the_mode_decays_within_a_small_fraction_of_the_record(self, q_factor):
        """Constant amplitude across the record is false by a wide margin."""
        tau = modal_decay_time_s(187.0, q_factor)
        record_length_s = 4.0
        assert tau / record_length_s < 0.05
        # By the end of the record the mode has decayed by e**-23 or more, even
        # at the most lightly damped end of the range this repo works in.
        assert math.exp(-record_length_s / tau) < 1e-9

    def test_the_model_mismatch_is_larger_than_the_convention_factor(self):
        """Which is why adopting sqrt(3) would not be an improvement.

        The bound treats all N samples as informative. If only the first few
        decay constants carry signal, the informative sample count is smaller
        by more than the factor of two separating the two conventions -- so
        correcting the convention while keeping the constant-amplitude model
        would move the number the wrong way.
        """
        tau = modal_decay_time_s(187.0, 100.0)
        informative_fraction = min(1.0, 5.0 * tau / 4.0)
        assert informative_fraction < 0.25
        # sigma scales as 1/sqrt(N), so shrinking the informative sample count
        # by this fraction inflates the bound by more than sqrt(2).
        assert 1.0 / math.sqrt(informative_fraction) > math.sqrt(2.0)


class TestF4StatusHasNotTransitioned:
    """B-020 is open, and every carrier of that fact still says so."""

    def test_the_expression_is_unchanged(self):
        record_s, n, snr_db = 4.0, 192000, 96.5
        eta = 10.0 ** (snr_db / 10.0)
        assert estimator_floor_candidate_hz(record_s, n, snr_db) == pytest.approx(
            (1.0 / (math.pi * record_s)) * math.sqrt(6.0 / (eta * n)), rel=1e-15
        )

    def test_the_status_is_still_the_candidate_source_formula(self):
        assert not FormulaStatus.CANDIDATE_SOURCE_FORMULA.is_established
        assert FormulaStatus.ESTABLISHED.is_established

    def test_the_harness_is_not_reachable_from_production_code(self):
        """The reference CRLB lives in test support and must stay there."""
        package = Path(__file__).resolve().parents[1] / "tap_tone_pi"
        offenders = [
            path.name
            for path in package.rglob("*.py")
            if "estimator_comparison" in path.read_text(encoding="utf-8")
        ]
        assert offenders == []
