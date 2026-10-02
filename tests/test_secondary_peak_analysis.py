"""Tests for secondary peak analysis (tap_tone_pi.damping.secondary_peak_analysis).

These exercise the versioned artifact that wraps the existing damping routines:
synthetic frequency, bandwidth, decay, dual-Q, noise/quality, and provenance
cases. They are hardware-free and deterministic (seeded noise only). They also
provide the first behavioral coverage of the reused tap_tone_pi.damping math.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from tap_tone_pi.damping.secondary_peak_analysis import (
    SCHEMA_VERSION,
    analyze_secondary_peak,
)
from tests.fixtures.audio import (
    add_noise,
    clip,
    damped_sine,
    dominant_peak_hz,
    spectrum,
    two_modes,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "secondary_peak_analysis_v1.schema.json"
)
SR = 48_000
SHA = "a" * 64

# A cleanly-resolvable resonator for ground-truth recovery. The envelope-fit decay
# method recovers tau/Q to within a few percent here; the half-power bandwidth Q is
# biased high (expected for a windowed tap spectrum). Q = pi * f0 * tau.
CLEAN_F0 = 440.0
CLEAN_TAU = 0.12
CLEAN_Q = np.pi * CLEAN_F0 * CLEAN_TAU


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _analyze(signal, f0, *, sha=SHA, peak_id="p1", **kw):
    freqs, mag = spectrum(signal, SR)
    return analyze_secondary_peak(
        signal=signal,
        sample_rate=SR,
        freqs=freqs,
        magnitude=mag,
        peak_frequency_hz=f0,
        peak_id=peak_id,
        source_wav_sha256=sha,
        **kw,
    )


def _clean_signal():
    return damped_sine(CLEAN_F0, CLEAN_TAU, SR, duration_s=1.0)


# --------------------------------------------------------------------------
# Harness soundness: a clean resonator resolves and validates
# --------------------------------------------------------------------------


def test_clean_resonator_resolves_and_validates():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    d = rec.to_dict()
    jsonschema.validate(d, _schema())
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["status"] == "RESOLVED"
    assert abs(d["peak_frequency_hz"] - CLEAN_F0) <= 2.0
    assert d["bandwidth_3db_hz"] > 0
    assert d["q_from_bandwidth"] > 0
    assert d["decay_tau_s"] > 0
    assert d["q_from_decay"] > 0
    assert d["source_wav_sha256"] == SHA
    assert "blocked_fields" not in d  # nothing blocked on a clean signal


def test_recovered_frequency_is_deterministic():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    a = _analyze(sig, f0).to_dict()
    b = _analyze(sig, f0).to_dict()
    assert a == b


@pytest.mark.parametrize("f0_true", [200.0, 440.0, 660.0])
def test_known_frequencies_within_tolerance(f0_true):
    sig = damped_sine(f0_true, 0.12, SR, duration_s=1.0)
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    assert abs(rec.peak_frequency_hz - f0_true) <= 2.0


# --------------------------------------------------------------------------
# Bandwidth / Q recovery
# --------------------------------------------------------------------------


def test_q_from_bandwidth_is_positive_and_order_of_magnitude():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    # Half-power bandwidth on a windowed tap spectrum is biased (typically high),
    # so assert only positivity and the correct order of magnitude, not a tight
    # ground-truth match. The decay path carries the precise Q check.
    assert rec.q_from_bandwidth is not None
    assert 0.5 * CLEAN_Q <= rec.q_from_bandwidth <= 2.5 * CLEAN_Q


def test_unresolved_bandwidth_blocks_rather_than_fabricates():
    # A search window narrower than the real half-bandwidth forces the crossings
    # to the search edge -> unresolved, not a fabricated bandwidth.
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0, search_bandwidth_hz=1.0)
    assert rec.bandwidth_3db_hz is None
    assert rec.q_from_bandwidth is None
    assert "bandwidth_3db_hz" in rec.blocked_fields
    d = rec.to_dict()
    assert "bandwidth_3db_hz" not in d
    jsonschema.validate(d, _schema())


# --------------------------------------------------------------------------
# Decay recovery
# --------------------------------------------------------------------------


def test_decay_tau_recovers_known_tau():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    assert 0.85 * CLEAN_TAU <= rec.decay_tau_s <= 1.15 * CLEAN_TAU


def test_q_from_decay_recovers_known_q():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    assert 0.85 * CLEAN_Q <= rec.q_from_decay <= 1.15 * CLEAN_Q


def test_truncated_signal_blocks_decay():
    # Far too short to fit an envelope decay; decay must block, not fabricate.
    sig = damped_sine(CLEAN_F0, CLEAN_TAU, SR, duration_s=0.001)
    f0 = CLEAN_F0
    rec = _analyze(sig, f0)
    assert rec.decay_tau_s is None
    assert rec.q_from_decay is None
    assert "decay_tau_s" in rec.blocked_fields


# --------------------------------------------------------------------------
# Dual-Q independence and agreement
# --------------------------------------------------------------------------


def test_two_q_estimates_stored_independently():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    # Both present, independent, and not collapsed to a single merged number.
    assert rec.q_from_bandwidth is not None
    assert rec.q_from_decay is not None
    assert rec.q_agreement_pct is not None
    assert 0.0 <= rec.q_agreement_pct <= 100.0


def test_agreement_absent_when_one_q_missing():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0, search_bandwidth_hz=1.0)  # bandwidth blocked
    assert rec.q_from_bandwidth is None
    assert rec.q_agreement_pct is None
    assert "q_agreement_pct" not in rec.to_dict()
    assert "q_agreement_pct" in rec.blocked_fields


# --------------------------------------------------------------------------
# Noise / quality
# --------------------------------------------------------------------------


def test_two_separated_modes_each_resolve():
    sig = two_modes((300.0, 900.0), (0.12, 0.12))
    for f0_true in (300.0, 900.0):
        rec = _analyze(sig, f0_true)
        assert abs(rec.peak_frequency_hz - f0_true) <= 2.0
        # at least the decay or bandwidth should resolve for well-separated modes
        assert rec.status in ("RESOLVED", "PARTIAL")


def test_noise_only_does_not_fabricate_metrics():
    rng_sig = add_noise(np.zeros(SR, dtype=np.float32) + 1e-6, snr_db=0.0, seed=7)
    rec = _analyze(rng_sig, 200.0)
    # On noise, decay fit must not pass the R^2 gate; nothing is fabricated.
    assert rec.decay_tau_s is None
    assert rec.q_from_decay is None
    jsonschema.validate(rec.to_dict(), _schema())


def test_clipped_signal_still_safe_and_valid_artifact():
    sig = clip(_clean_signal(), level=0.1)
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    jsonschema.validate(rec.to_dict(), _schema())
    assert rec.peak_frequency_hz > 0


def test_confidence_bounded_and_components_retained():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    rec = _analyze(sig, f0)
    assert 0.0 <= rec.confidence <= 1.0
    assert set(rec.confidence_components) == {"snr", "bandwidth", "decay_r2"}


def test_invalid_peak_frequency_raises():
    sig = _clean_signal()
    with pytest.raises(ValueError):
        _analyze(sig, 0.0)


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


def test_source_wav_sha256_is_preserved_verbatim():
    sig = _clean_signal()
    f0 = dominant_peak_hz(sig, SR)
    digest = "b" * 64
    rec = _analyze(sig, f0, sha=digest)
    assert rec.to_dict()["source_wav_sha256"] == digest


def test_status_not_resolved_keeps_primary_frequency():
    # Even when nothing secondary resolves, the primary peak frequency survives.
    sig = damped_sine(CLEAN_F0, CLEAN_TAU, SR, duration_s=0.001)
    rec = _analyze(sig, CLEAN_F0, search_bandwidth_hz=1.0)
    assert rec.status == "NOT_RESOLVED"
    assert rec.peak_frequency_hz == CLEAN_F0
    assert "log_decrement" in rec.blocked_fields
    assert "q_agreement_pct" in rec.blocked_fields
    jsonschema.validate(rec.to_dict(), _schema())
