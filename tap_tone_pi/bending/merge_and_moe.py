#!/usr/bin/env python3
"""
merge_and_moe.py — Merge load/displacement streams → synchronized pairs → derived MOE.

Migration: Canonical location is now tap_tone_pi.bending.merge_and_moe
           (previously modes/bending_rig/merge_and_moe.py)

Inputs:
    - load_series.json:  {"unit": "N"|"lbf", "data": [[t, force], ...]}
    - displacement_series.json: {"unit": "mm"|"in", "data": [[t, disp], ...]}

Outputs:
    - pairs.csv:           t_s,force_N,disp_mm (synchronized, resampled)
    - pairs_sidecar.json:  provenance + units + sample rate
    - bending_moe.json:    derived MOE with fit statistics

Usage:
    python -m tap_tone_pi.bending.merge_and_moe \\
        --load load_series.json --disp displacement_series.json \\
        --out-dir ./out/rig \\
        --method 3point --span 400 --width 20 --thickness 3.0 \\
        --rate 50 --fit-pct-low 10 --fit-pct-high 90
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _sha256(p: Path) -> str:
    """Compute SHA-256 hash of file."""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_series(path: str) -> Tuple[Optional[str], List[Tuple[float, float]]]:
    """
    Load a time-series JSON file.

    Expected format: {"unit": "N"|"lbf"|"mm"|"in", "data": [[t, value], ...]}
    """
    with open(path, "r", encoding="utf-8") as f:
        js = json.load(f)
    unit = js.get("unit")
    data = [(float(t), float(v)) for t, v in js["data"]]
    return unit, data


def _lin_interp(samples: List[Tuple[float, float]], t: float) -> float:
    """Linear interpolation at time t."""
    if t <= samples[0][0]:
        return samples[0][1]
    if t >= samples[-1][0]:
        return samples[-1][1]

    # Binary search for bracketing samples
    lo, hi = 0, len(samples) - 1
    while lo + 1 < hi:
        m = (lo + hi) // 2
        if samples[m][0] <= t:
            lo = m
        else:
            hi = m

    t0, y0 = samples[lo]
    t1, y1 = samples[hi]
    alpha = (t - t0) / (t1 - t0 + 1e-12)
    return y0 + alpha * (y1 - y0)


def _resample(
    load: List[Tuple[float, float]],
    disp: List[Tuple[float, float]],
    rate_hz: float,
    t0: float,
    t1: float,
) -> List[Tuple[float, float, float]]:
    """Resample load and displacement to uniform time grid."""
    dt = 1.0 / max(rate_hz, 1e-6)
    out: List[Tuple[float, float, float]] = []
    t = t0
    while t <= t1 + 1e-12:
        f = _lin_interp(load, t)
        d = _lin_interp(disp, t)
        out.append((t, f, d))
        t += dt
    return out


@dataclass
class LinearFitResult:
    """Result of linear regression with validation metadata."""

    slope: float  # N/mm
    r_squared: float
    n_points: int
    valid: bool
    warning: Optional[str]  # None if valid, otherwise describes issue
    condition_number: float  # Ratio of max/min singular values (high = ill-conditioned)
    residual_std: float  # Standard deviation of residuals


def _linear_fit(F: List[float], d: List[float]) -> LinearFitResult:
    """
    Compute linear regression slope and R² for F vs d with validation (M1 fix).

    Validates:
    - Minimum 3 points required
    - Condition number < 10⁴ (not near-singular)
    - R² > 0.5 (reasonable linear fit)

    Returns:
        LinearFitResult with slope, R², and validation metadata
    """
    n = len(F)

    # M1 fix: Minimum point count validation
    if n < 3:
        return LinearFitResult(
            slope=0.0,
            r_squared=0.0,
            n_points=n,
            valid=False,
            warning=f"Insufficient data points: {n} < 3 minimum",
            condition_number=float("inf"),
            residual_std=0.0,
        )

    if n != len(d):
        return LinearFitResult(
            slope=0.0,
            r_squared=0.0,
            n_points=n,
            valid=False,
            warning=f"Mismatched array lengths: F={len(F)}, d={len(d)}",
            condition_number=float("inf"),
            residual_std=0.0,
        )

    xbar = statistics.mean(d)
    ybar = statistics.mean(F)

    # Compute condition number (M1 fix: detect near-singular)
    d_centered = [x - xbar for x in d]
    ss_x = sum(x**2 for x in d_centered)

    if ss_x < 1e-20:
        return LinearFitResult(
            slope=0.0,
            r_squared=0.0,
            n_points=n,
            valid=False,
            warning="Near-zero variance in displacement (constant value?)",
            condition_number=float("inf"),
            residual_std=0.0,
        )

    # For simple linear regression, condition number ≈ max(|x|)/min(|x|) of design matrix
    # We use range/std as a simpler proxy
    d_range = max(d) - min(d) if d else 0
    d_std = statistics.stdev(d) if n > 1 else 1e-10
    condition_number = d_range / (d_std + 1e-20)

    num = sum((x - xbar) * (y - ybar) for x, y in zip(d, F))
    den = ss_x + 1e-20
    slope = num / den

    # Compute R² and residuals
    residuals = [(y - (slope * (x - xbar) + ybar)) for x, y in zip(d, F)]
    ss_res = sum(r**2 for r in residuals)
    ss_tot = sum((y - ybar) ** 2 for y in F) + 1e-20
    r2 = max(0.0, 1.0 - ss_res / ss_tot)  # Clamp to non-negative

    residual_std = statistics.stdev(residuals) if n > 2 else 0.0

    # Validation checks
    warning = None
    valid = True

    if condition_number > 1e4:
        warning = f"High condition number ({condition_number:.1f} > 10⁴): near-singular"
        valid = False
    elif r2 < 0.5:
        warning = f"Poor linear fit (R² = {r2:.3f} < 0.5): data may be nonlinear"
        valid = False
    elif r2 < 0.8:
        warning = f"Marginal linear fit (R² = {r2:.3f}): consider inspection"
        # Still valid but with warning

    return LinearFitResult(
        slope=slope,
        r_squared=r2,
        n_points=n,
        valid=valid,
        warning=warning,
        condition_number=condition_number,
        residual_std=residual_std,
    )


def _timoshenko_correction_factor(
    l_over_h: float,
    e_over_g: float = 16.0,
    kappa: float = 5.0 / 6.0,
) -> float:
    """
    Calculate Timoshenko shear correction factor.

    For short, thick beams (L/h < ~25), shear deformation causes Euler-Bernoulli
    to overestimate the apparent modulus. This correction compensates.

    Physics basis (see docs/theory/moe_shear_correction.md):
        E_apparent / E_true ≈ 1 + (π²/12) × (1 + E/(κG)) × (h/L)²

    For wood with E/G ≈ 16 and κ = 5/6:
        Coefficient ≈ 16.6, so correction = 1 + 16.6 × (h/L)²

    Args:
        l_over_h: Length-to-thickness ratio (L/h)
        e_over_g: Ratio of elastic to shear modulus (typically 14-20 for wood)
        kappa: Shear correction factor (5/6 for rectangular section)

    Returns:
        Correction factor: E_apparent / E_true (always >= 1.0)
    """
    import math

    h_over_l_squared = 1.0 / (l_over_h**2)
    coefficient = (math.pi**2 / 12.0) * (1.0 + e_over_g / kappa)

    return 1.0 + coefficient * h_over_l_squared


def _calculate_moe(
    method: str,
    slope_N_per_mm: float,
    span_mm: float,
    width_mm: float,
    thickness_mm: float,
    inner_span_mm: Optional[float] = None,
    shear_correction_threshold: float = 25.0,
    e_over_g: float = 16.0,
    poisson_ratio: Optional[float] = None,
    specimen_type: str = "strip",
) -> Dict[str, Any]:
    """
    Calculate MOE (Pa) from force-displacement slope with Timoshenko correction.

    Uses Euler-Bernoulli beam theory with optional Timoshenko shear correction
    for short/thick beams (L/h < threshold). This prevents 8-15% overestimation
    that occurs with pure Euler-Bernoulli on typical soundboard specimens.

    Args:
        method: "3point" or "4point"
        slope_N_per_mm: dF/dd from linear fit
        span_mm: support span
        width_mm: specimen width
        thickness_mm: specimen thickness
        inner_span_mm: inner load span for 4-point (optional)
        shear_correction_threshold: Apply correction when L/h < this value
        e_over_g: E/G ratio for wood (typically 14-20, default 16)
        poisson_ratio: Poisson ratio for plate-width correction (None = no correction).
            Typical wood: 0.30-0.40. Correction factor = (1 - nu^2), per ASTM E855.
        specimen_type: "strip" (narrow beam, no width correction) or
            "full_plate" (wide specimen, plate-width correction applied).

    Returns:
        Dict with:
            - E_euler_bernoulli_Pa: Uncorrected MOE
            - E_corrected_Pa: Shear-corrected MOE (or same if not applied)
            - E_plate_corrected_Pa: After plate-width correction (full_plate only)
            - plate_width_correction_applied: Whether (1-nu^2) was applied
            - plate_width_correction_factor: The (1-nu^2) factor used
            - poisson_ratio_used: Poisson ratio value used
            - l_over_h: Length-to-thickness ratio
            - shear_correction_applied: Whether Timoshenko correction was applied
            - shear_correction_factor: The Timoshenko correction factor used
            - shear_correction_percent: Percent reduction from Timoshenko correction
    """
    # Convert to meters
    L = span_mm / 1000.0
    b = width_mm / 1000.0
    h = thickness_mm / 1000.0

    # Length-to-thickness ratio
    l_over_h = span_mm / thickness_mm

    # Second moment of area (m^4)
    moment_I = b * h**3 / 12.0

    # Slope in N/m
    S = slope_N_per_mm * 1000.0

    # Euler-Bernoulli calculation (uncorrected)
    if method == "3point":
        # E = S * L³ / (48 * I)
        E_eb = S * L**3 / (48.0 * moment_I)
    else:
        # 4-point: E = S * a * (3L² - 4a²) / (24 * I)
        a = (inner_span_mm / 1000.0) if inner_span_mm else L / 3.0
        E_eb = S * a * (3 * L * L - 4 * a * a) / (24.0 * moment_I)

    # Apply Timoshenko shear correction for short/thick beams
    if l_over_h < shear_correction_threshold:
        correction_factor = _timoshenko_correction_factor(l_over_h, e_over_g)
        E_corrected = E_eb / correction_factor
        correction_applied = True
    else:
        correction_factor = 1.0
        E_corrected = E_eb
        correction_applied = False

    # Plate-width correction (wide specimen: full plate, not a narrow strip)
    # E_true = E_apparent * (1 - nu^2)
    # Wide plates are constrained laterally, making them appear stiffer.
    # This correction removes that bias. Only applies when specimen_type="full_plate"
    # and poisson_ratio is explicitly supplied.
    plate_correction_applied = False
    plate_correction_factor = 1.0
    poisson_used = poisson_ratio

    if specimen_type == "full_plate" and poisson_ratio is not None:
        plate_correction_factor = 1.0 - poisson_ratio ** 2
        E_plate_corrected = E_corrected * plate_correction_factor
        plate_correction_applied = True
    else:
        E_plate_corrected = E_corrected
        poisson_used = None

    return {
        "E_euler_bernoulli_Pa": E_eb,
        "E_corrected_Pa": E_corrected,
        "E_plate_corrected_Pa": E_plate_corrected,
        "plate_width_correction_applied": plate_correction_applied,
        "plate_width_correction_factor": round(plate_correction_factor, 6),
        "poisson_ratio_used": poisson_used,
        "l_over_h": l_over_h,
        "shear_correction_applied": correction_applied,
        "shear_correction_factor": correction_factor,
        "shear_correction_percent": (correction_factor - 1.0) * 100.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Merge load/disp streams and compute bending MOE."
    )
    ap.add_argument("--load", required=True, help="Path to load_series.json")
    ap.add_argument("--disp", required=True, help="Path to displacement_series.json")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--rate", type=float, default=50.0, help="Resample rate (Hz)")
    ap.add_argument(
        "--method",
        choices=["3point", "4point"],
        default="3point",
        help="Bending test method",
    )
    ap.add_argument(
        "--specimen-type",
        choices=["strip", "full_plate"],
        default="strip",
        help=(
            "Specimen type. 'strip': narrow beam (default, no width correction). "
            "'full_plate': full soundboard plate — applies plate-width correction "
            "(1 - nu^2) when --poisson is also supplied."
        ),
    )
    ap.add_argument(
        "--poisson",
        type=float,
        default=None,
        help=(
            "Poisson ratio for plate-width correction (e.g. 0.35 for spruce). "
            "Only used when --specimen-type full_plate. Typical wood: 0.30-0.40. "
            "If omitted, no plate-width correction is applied."
        ),
    )
    ap.add_argument(
        "--grain-orientation",
        choices=["longitudinal", "cross", "unknown"],
        default="unknown",
        help="Grain orientation relative to the span direction. Stored in output for traceability.",
    )
    ap.add_argument("--span", type=float, required=True, help="Support span (mm)")
    ap.add_argument("--width", type=float, required=True, help="Specimen width (mm)")
    ap.add_argument(
        "--thickness", type=float, required=True, help="Specimen thickness (mm)"
    )
    ap.add_argument(
        "--inner-span",
        type=float,
        default=None,
        help="Inner load span for 4-point (mm)",
    )
    ap.add_argument(
        "--fit-pct-low",
        type=float,
        default=10.0,
        help="Lower percentile for fit range",
    )
    ap.add_argument(
        "--fit-pct-high",
        type=float,
        default=90.0,
        help="Upper percentile for fit range",
    )
    args = ap.parse_args()

    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load input series
    unit_F, load = _load_series(args.load)
    unit_D, disp = _load_series(args.disp)

    # Unit conversion to SI (N, mm)
    if unit_F == "lbf":
        load = [(t, v * 4.4482216153) for t, v in load]
    if unit_D == "in":
        disp = [(t, v * 25.4) for t, v in disp]

    # Sort by time
    load = sorted(load, key=lambda x: x[0])
    disp = sorted(disp, key=lambda x: x[0])

    # Find overlapping time range
    t0 = max(load[0][0], disp[0][0])
    t1 = min(load[-1][0], disp[-1][0])

    # Resample to uniform grid
    pairs = _resample(load, disp, args.rate, t0, t1)

    # Write synchronized pairs CSV
    csv_path = outdir / "pairs.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("t_s,force_N,disp_mm\n")
        for t, F, d in pairs:
            f.write(f"{t:.5f},{F:.6f},{d:.6f}\n")

    # Write sidecar JSON with provenance
    sidecar: Dict[str, Any] = {
        "artifact_type": "bending_rig_pairs",
        "pair_csv_path": csv_path.as_posix(),
        "units": {"force": "N", "disp": "mm"},
        "sample_rate_hz_est": args.rate,
        "n_samples": len(pairs),
        "time_range_s": [t0, t1],
        "provenance": {
            "load_series_path": args.load,
            "load_sha256": _sha256(Path(args.load)),
            "disp_series_path": args.disp,
            "disp_sha256": _sha256(Path(args.disp)),
        },
    }
    sidecar_path = outdir / "pairs_sidecar.json"
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2)

    # Fit on mid-range displacement (exclude toe region and yield)
    d_vals = [d for _, _, d in pairs]
    d_sorted = sorted(d_vals)
    n = len(d_sorted) - 1
    d_lo = d_sorted[max(0, min(n, round(args.fit_pct_low / 100 * n)))]
    d_hi = d_sorted[max(0, min(n, round(args.fit_pct_high / 100 * n)))]

    F_fit = [F for _, F, d in pairs if d_lo <= d <= d_hi]
    d_fit = [d for _, F, d in pairs if d_lo <= d <= d_hi]

    fit_result = _linear_fit(F_fit, d_fit)

    # M1 fix: Check fit validity before proceeding
    if not fit_result.valid:
        print(f"WARNING: Linear fit failed - {fit_result.warning}")
        if fit_result.n_points < 3:
            print("  ERROR: Cannot compute MOE with fewer than 3 data points.")
            return

    slope = fit_result.slope
    r2 = fit_result.r_squared

    # Calculate MOE with Timoshenko shear correction
    moe_calc = _calculate_moe(
        args.method,
        slope,
        args.span,
        args.width,
        args.thickness,
        args.inner_span,
        poisson_ratio=args.poisson,
        specimen_type=args.specimen_type,
    )

    # Use plate-corrected value as primary for full_plate; shear-corrected for strip
    E_pa = moe_calc["E_plate_corrected_Pa"]
    E_eb_pa = moe_calc["E_euler_bernoulli_Pa"]

    # Write MOE result
    moe_result: Dict[str, Any] = {
        "artifact_type": "bending_moe",
        "E_GPa": E_pa / 1e9,
        "E_euler_bernoulli_GPa": E_eb_pa / 1e9,
        "method": args.method,
        "geometry": {
            "span_mm": args.span,
            "width_mm": args.width,
            "thickness_mm": args.thickness,
            "inner_span_mm": args.inner_span,
            "l_over_h": round(moe_calc["l_over_h"], 2),
            "specimen_type": args.specimen_type,
            "grain_orientation": args.grain_orientation,
        },
        "plate_width_correction": {
            "applied": moe_calc["plate_width_correction_applied"],
            "factor": moe_calc["plate_width_correction_factor"],
            "poisson_ratio": moe_calc["poisson_ratio_used"],
            "note": (
                f"Plate-width correction applied: E_true = E_apparent * {moe_calc['plate_width_correction_factor']:.4f} "
                f"(Poisson ratio nu = {moe_calc['poisson_ratio_used']}; ASTM E855)"
                if moe_calc["plate_width_correction_applied"]
                else "No plate-width correction (strip specimen or --poisson not supplied)"
            ),
        },
        "shear_correction": {
            "applied": moe_calc["shear_correction_applied"],
            "factor": round(moe_calc["shear_correction_factor"], 4),
            "reduction_percent": round(moe_calc["shear_correction_percent"], 2),
            "note": (
                f"Timoshenko correction applied (L/h = {moe_calc['l_over_h']:.1f} < 25)"
                if moe_calc["shear_correction_applied"]
                else f"No correction needed (L/h = {moe_calc['l_over_h']:.1f} >= 25)"
            ),
        },
        "fit": {
            "pct_low": args.fit_pct_low,
            "pct_high": args.fit_pct_high,
            "disp_range_mm": [d_lo, d_hi],
            "n_points": fit_result.n_points,
            "slope_N_per_mm": round(slope, 6),
            "r2": round(r2, 6),
            "valid": fit_result.valid,
            "condition_number": round(fit_result.condition_number, 2),
            "residual_std": round(fit_result.residual_std, 6),
            "warning": fit_result.warning,
        },
        "provenance": {
            "pairs_csv_path": csv_path.as_posix(),
            "pairs_sha256": _sha256(csv_path),
            "pairs_sidecar_path": sidecar_path.as_posix(),
            "pairs_sidecar_sha256": _sha256(sidecar_path),
            "load_series_path": args.load,
            "load_sha256": sidecar["provenance"]["load_sha256"],
            "disp_series_path": args.disp,
            "disp_sha256": sidecar["provenance"]["disp_sha256"],
        },
    }
    moe_path = outdir / "bending_moe.json"
    with open(moe_path, "w", encoding="utf-8") as f:
        json.dump(moe_result, f, indent=2)

    print(f"Wrote {csv_path}")
    print(f"Wrote {sidecar_path}")
    print(f"Wrote {moe_path}")

    # Report both values when correction is applied
    if moe_calc["shear_correction_applied"]:
        print(
            f"  E = {E_pa / 1e9:.3f} GPa (Timoshenko-corrected, "
            f"L/h = {moe_calc['l_over_h']:.1f})"
        )
        print(
            f"      ({E_eb_pa / 1e9:.3f} GPa Euler-Bernoulli, "
            f"-{moe_calc['shear_correction_percent']:.1f}% correction)"
        )
    else:
        print(
            f"  E = {E_pa / 1e9:.3f} GPa (L/h = {moe_calc['l_over_h']:.1f}, no correction needed)"
        )
    print(f"  R² = {r2:.4f}")


if __name__ == "__main__":
    main()
