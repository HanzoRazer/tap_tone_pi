# INSTRUMENT CLASS: MEASUREMENT
"""DO-107M Utility 1 -- make the B-020 estimator decision inspectable.

The question B-020 holds is which single-tone frequency-estimator expression
TTP is entitled to use, and what to call it. Two expressions are in play:

``source``
    What the archived acquisition calculator computes, reproduced verbatim by
    :func:`estimator_floor_candidate_hz`::

        (1 / (pi * T)) * sqrt(6 / (SNR_linear * N))

``crlb_power_snr``
    The classical Cramer-Rao lower bound for the frequency of a **constant
    amplitude real sinusoid in white Gaussian noise**, with amplitude, phase
    and frequency all unknown, evaluated under the *power* SNR convention
    ``eta = A^2 / (2 * sigma^2)``::

        var(f) >= 12 * fs^2 / ((2*pi)^2 * eta * N * (N^2 - 1))

    which for large ``N``, with ``T = N / fs``, reduces to::

        (1 / (pi * T)) * sqrt(3 / (eta * N))

They differ by exactly ``sqrt(2)``, and that factor is not mysterious: it is
the factor of two between a real sinusoid's power ``A^2/2`` and its squared
amplitude ``A^2``. Substituting ``A^2 / sigma^2`` for ``A^2 / (2 sigma^2)``
turns ``sqrt(3)`` into ``sqrt(6)``. The two expressions are the same bound
stated under two SNR conventions.

**This module adopts neither.** It exists so the comparison can be read off
rather than argued, and so the numerical consequence of a future decision is
visible before it is taken. Nothing here is imported by production code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["EstimatorComparison", "compare_estimators", "crlb_power_snr_hz"]


def crlb_power_snr_hz(record_length_s: float, n_samples: int, snr_db: float) -> float:
    """CRLB for a constant-amplitude real sinusoid, power SNR convention.

    Large-``N`` form. Not adopted by TTP: see the module docstring and B-020.
    """
    if record_length_s <= 0:
        raise ValueError("record_length_s must be positive")
    n = max(n_samples, 2)
    eta = 10.0 ** (snr_db / 10.0)
    return (1.0 / (math.pi * record_length_s)) * math.sqrt(3.0 / (eta * n))


def crlb_exact_power_snr_hz(
    record_length_s: float, n_samples: int, snr_db: float
) -> float:
    """The same bound without the ``N(N^2-1) -> N^3`` approximation."""
    if record_length_s <= 0:
        raise ValueError("record_length_s must be positive")
    n = max(n_samples, 2)
    eta = 10.0 ** (snr_db / 10.0)
    fs = n / record_length_s
    variance = (12.0 * fs * fs) / (((2.0 * math.pi) ** 2) * eta * n * (n * n - 1.0))
    return math.sqrt(variance)


@dataclass(frozen=True)
class EstimatorComparison:
    """Both candidates at one operating point, plus what separates them."""

    record_length_s: float
    n_samples: int
    snr_db: float
    source_hz: float
    crlb_power_snr_hz: float
    crlb_exact_hz: float
    ratio_source_over_crlb: float
    absolute_difference_hz: float

    def as_row(self) -> str:
        return (
            f"T={self.record_length_s:<8g} N={self.n_samples:<8d} "
            f"SNR={self.snr_db:<6.1f} dB  "
            f"source={self.source_hz:.6e}  "
            f"crlb={self.crlb_power_snr_hz:.6e}  "
            f"ratio={self.ratio_source_over_crlb:.6f}"
        )


def compare_estimators(
    record_length_s: float, n_samples: int, snr_db: float
) -> EstimatorComparison:
    """Evaluate both candidates at one operating point."""
    from tap_tone_pi.uncertainty.acquisition import estimator_floor_candidate_hz

    source = estimator_floor_candidate_hz(record_length_s, n_samples, snr_db)
    crlb = crlb_power_snr_hz(record_length_s, n_samples, snr_db)
    exact = crlb_exact_power_snr_hz(record_length_s, n_samples, snr_db)
    return EstimatorComparison(
        record_length_s=record_length_s,
        n_samples=n_samples,
        snr_db=snr_db,
        source_hz=source,
        crlb_power_snr_hz=crlb,
        crlb_exact_hz=exact,
        ratio_source_over_crlb=source / crlb,
        absolute_difference_hz=source - crlb,
    )


def modal_decay_time_s(frequency_hz: float, q_factor: float) -> float:
    """Amplitude decay constant of a lightly damped mode: ``tau = Q / (pi f)``.

    Present because the constant-amplitude signal model assumed by both
    candidates does not describe a tap tone, and the size of that mismatch is
    the reason B-020 could not be closed. See the DO-107M reconciliation record.
    """
    if frequency_hz <= 0 or q_factor <= 0:
        raise ValueError("frequency_hz and q_factor must be positive")
    return q_factor / (math.pi * frequency_hz)
