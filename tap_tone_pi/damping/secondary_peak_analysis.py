# INSTRUMENT CLASS: MEASUREMENT
"""Secondary peak characterization: a versioned artifact over existing damping math.

This module does NOT reimplement bandwidth/decay/Q extraction. It orchestrates the
production routines already in :mod:`tap_tone_pi.damping.extraction`
(``extract_damping_halfpower``, ``extract_damping_curvefit``,
``extract_damping_logdec``) and serializes a single selected spectral peak into the
``secondary_peak_analysis_v1`` contract.

Scope and boundaries
---------------------
- It characterizes a *measured* peak. It assigns no wood quality, tone quality,
  historical equivalence, or suitability.
- Secondary characterization is advanced/optional. A failure to resolve bandwidth
  or decay yields ``status = NOT_RESOLVED`` with the affected fields reported in
  ``blocked_fields`` and omitted from the artifact — it never fabricates a value
  and never invalidates the primary frequency observation.
- Two Q estimates are preserved independently and never silently merged:
  ``q_from_bandwidth`` (half-power) and ``q_from_decay`` (exponential envelope
  fit). Log-decrement is retained as a cross-check diagnostic only.

Q convention
------------
Adopted unchanged from :mod:`tap_tone_pi.damping.extraction`: amplitude decay
``A(t) = A0 * exp(-alpha * t)`` with ``alpha = zeta * omega_n``,
``Q = 1 / (2 * zeta)``, ``tau = 1 / alpha = 1 / (zeta * omega_n)``. Both the
half-power and the decay estimates express Q under this single amplitude-decay
convention; no module mixes amplitude and energy decay under the same field name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from tap_tone_pi.damping.extraction import (
    extract_damping_curvefit,
    extract_damping_halfpower,
    extract_damping_logdec,
)

SCHEMA_VERSION = "secondary_peak_analysis_v1"

STATUS_RESOLVED = "RESOLVED"
STATUS_PARTIAL = "PARTIAL"
STATUS_NOT_RESOLVED = "NOT_RESOLVED"

_EPS = 1e-12


@dataclass(frozen=True)
class ExtractionStatus:
    """Which secondary quantities were resolvable, and why not when they were not."""

    valid_peak: bool
    bandwidth_resolved: bool
    decay_resolved: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SecondaryPeakAnalysisV1:
    """Serializable ``secondary_peak_analysis_v1`` record for one selected peak.

    Optional metrics are ``None`` when unresolved; :meth:`to_dict` omits them so
    the emitted artifact carries absence honestly rather than sentinel numbers.
    """

    source_wav_sha256: str
    peak_id: str
    peak_frequency_hz: float
    status: str
    peak_magnitude_db: float | None = None
    bandwidth_3db_hz: float | None = None
    q_from_bandwidth: float | None = None
    decay_tau_s: float | None = None
    q_from_decay: float | None = None
    log_decrement: float | None = None
    q_agreement_pct: float | None = None
    confidence: float | None = None
    confidence_components: dict[str, float] | None = None
    fit_window_s: float | None = None
    noise_floor_db: float | None = None
    snr_db: float | None = None
    method_flags: tuple[str, ...] = ()
    blocked_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source_wav_sha256": self.source_wav_sha256,
            "peak_id": self.peak_id,
            "peak_frequency_hz": self.peak_frequency_hz,
            "status": self.status,
        }
        optional_scalars = (
            "peak_magnitude_db",
            "bandwidth_3db_hz",
            "q_from_bandwidth",
            "decay_tau_s",
            "q_from_decay",
            "log_decrement",
            "q_agreement_pct",
            "confidence",
            "fit_window_s",
            "noise_floor_db",
            "snr_db",
        )
        for name in optional_scalars:
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        if self.confidence_components is not None:
            out["confidence_components"] = dict(self.confidence_components)
        if self.method_flags:
            out["method_flags"] = list(self.method_flags)
        if self.blocked_fields:
            out["blocked_fields"] = list(self.blocked_fields)
        return out


def _spectrum_levels(
    freqs: np.ndarray, magnitude: np.ndarray, peak_frequency_hz: float
) -> tuple[float, float, float]:
    """Return (peak_magnitude_db, noise_floor_db, snr_db).

    dB are referenced to the spectrum maximum, so the dominant peak sits at 0 dB
    and ``snr_db == peak_magnitude_db - noise_floor_db``. The noise floor is the
    median magnitude (robust to the peaks themselves).
    """
    mag = np.asarray(magnitude, dtype=np.float64)
    max_lin = float(np.max(mag)) if mag.size else 0.0
    if max_lin <= _EPS:
        return 0.0, 0.0, 0.0
    peak_bin = int(np.argmin(np.abs(freqs - peak_frequency_hz)))
    peak_lin = float(mag[peak_bin])
    noise_lin = float(np.median(mag[mag > 0])) if np.any(mag > 0) else max_lin
    peak_db = 20.0 * np.log10(max(peak_lin, _EPS) / max_lin)
    noise_db = 20.0 * np.log10(max(noise_lin, _EPS) / max_lin)
    snr_db = peak_db - noise_db
    return peak_db, noise_db, snr_db


def _clamp01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def analyze_secondary_peak(
    *,
    signal: np.ndarray,
    sample_rate: int,
    freqs: np.ndarray,
    magnitude: np.ndarray,
    peak_frequency_hz: float,
    peak_id: str,
    source_wav_sha256: str,
    search_bandwidth_hz: float = 50.0,
    filter_bandwidth_hz: float = 20.0,
    min_decay_r2: float = 0.90,
) -> SecondaryPeakAnalysisV1:
    """Characterize one selected spectral peak by reusing the damping routines.

    ``peak_frequency_hz`` is the peak chosen by primary extraction; this routine
    does not re-select peaks. Bandwidth comes from the half-power method and decay
    from the exponential envelope fit, kept as independent Q estimates. Nothing
    here can block or alter the primary measurement.
    """
    if not (np.isfinite(peak_frequency_hz) and peak_frequency_hz > 0):
        raise ValueError("peak_frequency_hz must be finite and positive")

    reasons: list[str] = []
    method_flags: list[str] = []
    blocked_fields: list[str] = []

    peak_db, noise_db, snr_db = _spectrum_levels(freqs, magnitude, peak_frequency_hz)

    # --- Bandwidth / Q from half-power (frequency domain) ---------------------
    _, _, hp = extract_damping_halfpower(
        np.asarray(freqs, dtype=np.float64),
        np.asarray(magnitude, dtype=np.float64),
        peak_frequency_hz,
        search_bandwidth_hz=search_bandwidth_hz,
    )
    bandwidth_resolved = (
        "error" not in hp
        and "warning" not in hp  # an edge crossing is not a resolved half-power point
        and np.isfinite(hp.get("Q", np.nan))
        and hp.get("Q", 0.0) > 0
        and hp.get("bandwidth_hz", 0.0) > 0
    )
    bandwidth_3db_hz: float | None = None
    q_from_bandwidth: float | None = None
    if bandwidth_resolved:
        bandwidth_3db_hz = float(hp["bandwidth_hz"])
        q_from_bandwidth = float(hp["Q"])
        method_flags.append("bandwidth_halfpower")
    else:
        blocked_fields.extend(["bandwidth_3db_hz", "q_from_bandwidth"])
        reasons.append(
            "bandwidth: " + str(hp.get("error") or hp.get("warning") or "unresolved")
        )

    # --- Decay / Q from exponential envelope fit (time domain) ----------------
    cf_zeta, _, cf = extract_damping_curvefit(
        np.asarray(signal, dtype=np.float64),
        int(sample_rate),
        peak_frequency_hz,
        bandwidth_hz=filter_bandwidth_hz,
    )
    r2 = cf.get("r_squared", 0.0)
    alpha = cf.get("alpha_nepers_per_s", np.nan)
    decay_resolved = (
        "error" not in cf
        and np.isfinite(cf_zeta)
        and cf_zeta > 0
        and np.isfinite(alpha)
        and alpha > 0
        and r2 >= min_decay_r2
    )
    decay_tau_s: float | None = None
    q_from_decay: float | None = None
    fit_window_s: float | None = None
    if decay_resolved:
        decay_tau_s = float(1.0 / alpha)
        q_from_decay = float(1.0 / (2.0 * cf_zeta))
        fit_window_s = (
            float(cf.get("fit_duration_s")) if "fit_duration_s" in cf else None
        )
        method_flags.append("decay_curvefit")
    else:
        blocked_fields.extend(["decay_tau_s", "q_from_decay"])
        if "error" in cf:
            reasons.append(f"decay: {cf['error']}")
        elif r2 < min_decay_r2:
            reasons.append(f"decay: poor fit (R2={r2:.3f} < {min_decay_r2})")
        else:
            reasons.append("decay: unresolved")

    # --- Log decrement: cross-check diagnostic only ---------------------------
    _, _, ld = extract_damping_logdec(
        np.asarray(signal, dtype=np.float64),
        int(sample_rate),
        peak_frequency_hz,
        bandwidth_hz=filter_bandwidth_hz,
    )
    log_decrement: float | None = None
    if (
        "error" not in ld
        and np.isfinite(ld.get("delta_mean", np.nan))
        and ld.get("delta_mean", 0.0) > 0
    ):
        log_decrement = float(ld["delta_mean"])
        method_flags.append("logdec_cross_check")
    else:
        blocked_fields.append("log_decrement")

    # --- Independent-Q agreement (only when both exist) -----------------------
    q_agreement_pct: float | None = None
    if q_from_bandwidth is not None and q_from_decay is not None:
        mean_q = (q_from_bandwidth + q_from_decay) / 2.0
        if mean_q > 0:
            rel_diff = abs(q_from_bandwidth - q_from_decay) / mean_q
            q_agreement_pct = float(max(0.0, min(100.0, 100.0 * (1.0 - rel_diff))))
    if q_agreement_pct is None:
        blocked_fields.append("q_agreement_pct")

    # --- Confidence: a transparent mean of component scores -------------------
    snr_score = _clamp01(snr_db / 40.0)
    bw_score = 1.0 if bandwidth_resolved else 0.0
    decay_score = _clamp01(float(r2)) if "error" not in cf else 0.0
    components = {
        "snr": round(snr_score, 6),
        "bandwidth": round(bw_score, 6),
        "decay_r2": round(decay_score, 6),
    }
    confidence = round(float(np.mean(list(components.values()))), 6)

    if bandwidth_resolved and decay_resolved:
        status = STATUS_RESOLVED
    elif bandwidth_resolved or decay_resolved:
        status = STATUS_PARTIAL
    else:
        status = STATUS_NOT_RESOLVED

    return SecondaryPeakAnalysisV1(
        source_wav_sha256=source_wav_sha256,
        peak_id=peak_id,
        peak_frequency_hz=float(peak_frequency_hz),
        status=status,
        peak_magnitude_db=round(peak_db, 4),
        bandwidth_3db_hz=bandwidth_3db_hz,
        q_from_bandwidth=q_from_bandwidth,
        decay_tau_s=decay_tau_s,
        q_from_decay=q_from_decay,
        log_decrement=log_decrement,
        q_agreement_pct=q_agreement_pct,
        confidence=confidence,
        confidence_components=components,
        fit_window_s=fit_window_s,
        noise_floor_db=round(noise_db, 4),
        snr_db=round(snr_db, 4),
        method_flags=tuple(method_flags),
        blocked_fields=tuple(blocked_fields),
    )


def extraction_status(record: SecondaryPeakAnalysisV1) -> ExtractionStatus:
    """Summarize what resolved for a produced record (convenience for callers)."""
    return ExtractionStatus(
        valid_peak=bool(
            np.isfinite(record.peak_frequency_hz) and record.peak_frequency_hz > 0
        ),
        bandwidth_resolved=record.bandwidth_3db_hz is not None,
        decay_resolved=record.decay_tau_s is not None,
        reasons=tuple(record.blocked_fields),
    )
