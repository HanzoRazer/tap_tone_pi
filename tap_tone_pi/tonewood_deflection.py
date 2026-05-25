#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""
tonewood_deflection.py

Compute Young's modulus from 3-point bending (Euler-Bernoulli),
plus density, specific stiffness, and thickness targeting (Eh^3 constant).

This is the static deflection method - distinct from the acoustic tap tone method.
Use this with a simple jig: knife-edge supports + dial indicator + known weights.

Derivation (Euler-Bernoulli beam, central point load):
    delta = F * L^3 / (48 * E * I)
    I = b * h^3 / 12  (rectangular section)
    => E = F * L^3 / (4 * b * h^3 * delta)

For multiple load points, use linear fit (F vs delta) for stability:
    k = dF/d(delta)  =>  E = k * L^3 / (4 * b * h^3)

Thickness targeting (Gore-style "normalize stiffness"):
    E1 * h1^3 = E2 * h2^3
    => h2 = h1 * (E1/E2)^(1/3)

Usage examples:
    # Single measurement
    python -m tap_tone_pi.tonewood_deflection --span_mm 400 --width_mm 30 --thick_mm 3.0 \\
        --loads_N 5 10 15 --defl_mm 0.55 1.10 1.65 \\
        --strip_len_mm 450 --strip_mass_g 18.2

    # From CSV
    python -m tap_tone_pi.tonewood_deflection --csv data.csv --span_mm 400 --width_mm 30 --thick_mm 3.0

    # With thickness targeting
    python -m tap_tone_pi.tonewood_deflection --span_mm 400 --width_mm 30 --thick_mm 3.0 \\
        --loads_N 10 --defl_mm 1.5 --href_mm 2.8 --eref_GPa 12.0

CSV columns supported:
    load_N, defl_mm                                         (net deflection)
    m_base_kg, m_test_kg, defl_base_mm, defl_test_mm        (app computes net)

References:
    - Gore & Gilet, "Contemporary Acoustic Guitar Design and Build"
    - David Hurd, "Left-Brain Lutherie"
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

# Gravitational acceleration (m/s^2)
G = 9.80665


# =============================================================================
# Data classes
# =============================================================================


@dataclass(frozen=True)
class Geometry:
    """Beam geometry for 3-point bending test."""

    span_m: float  # Support span L
    width_m: float  # Strip width b
    thick_m: float  # Strip thickness h (bending direction)

    @property
    def second_moment_of_area(self) -> float:
        """I = b * h^3 / 12 for rectangular section."""
        return self.width_m * (self.thick_m**3) / 12.0

    @property
    def slenderness_ratio(self) -> float:
        """L/h ratio - should be >= 20 for Euler-Bernoulli accuracy."""
        if self.thick_m <= 0:
            return 0.0
        return self.span_m / self.thick_m


@dataclass(frozen=True)
class StripMassGeom:
    """Strip dimensions for density calculation."""

    strip_len_m: float
    strip_mass_kg: float


@dataclass(frozen=True)
class FitResult:
    """Linear regression result for F vs delta."""

    slope_N_per_m: float  # k = dF/d(delta)
    intercept_N: float
    r2: float
    n_points: int


@dataclass
class DeflectionResult:
    """Complete result from deflection analysis."""

    # Geometry
    span_mm: float
    width_mm: float
    thick_mm: float
    slenderness_ratio: float

    # Fit
    method: str  # "linear_fit" or "single_point"
    slope_N_per_m: float
    r2: Optional[float]
    n_points: int

    # Stiffness
    E_Pa: float
    E_GPa: float

    # Optional: density and specific stiffness
    density_kg_m3: Optional[float] = None
    density_g_cm3: Optional[float] = None
    specific_stiffness_m2_s2: Optional[float] = None
    wave_speed_m_s: Optional[float] = None

    # Optional: thickness targeting
    h_target_mm: Optional[float] = None
    h_ref_mm: Optional[float] = None
    E_ref_GPa: Optional[float] = None

    # Warnings
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# Unit conversions
# =============================================================================


def mm_to_m(x_mm: float) -> float:
    """Millimeters to meters."""
    return x_mm / 1000.0


def m_to_mm(x_m: float) -> float:
    """Meters to millimeters."""
    return x_m * 1000.0


def cm_to_m(x_cm: float) -> float:
    """Centimeters to meters."""
    return x_cm / 100.0


def g_to_kg(x_g: float) -> float:
    """Grams to kilograms."""
    return x_g / 1000.0


def kg_to_g(x_kg: float) -> float:
    """Kilograms to grams."""
    return x_kg * 1000.0


# =============================================================================
# Core calculations
# =============================================================================


def compute_E_from_slope(geom: Geometry, slope_N_per_m: float) -> float:
    """
    Compute Young's modulus from F/delta slope.

    E = (k * L^3) / (4 * b * h^3)

    Args:
        geom: Beam geometry
        slope_N_per_m: Slope k = dF/d(delta) in N/m

    Returns:
        Young's modulus in Pa
    """
    L, b, h = geom.span_m, geom.width_m, geom.thick_m
    return (slope_N_per_m * (L**3)) / (4.0 * b * (h**3))


def compute_E_single_point(geom: Geometry, F_N: float, delta_m: float) -> float:
    """
    Compute Young's modulus from single load/deflection point.

    E = (F * L^3) / (4 * b * h^3 * delta)

    Args:
        geom: Beam geometry
        F_N: Applied force in N
        delta_m: Deflection at midspan in m

    Returns:
        Young's modulus in Pa

    Raises:
        ValueError: If deflection is not positive
    """
    if delta_m <= 0:
        raise ValueError(f"Deflection must be > 0, got {delta_m}")

    L, b, h = geom.span_m, geom.width_m, geom.thick_m
    return (F_N * (L**3)) / (4.0 * b * (h**3) * delta_m)


def linear_fit(x: List[float], y: List[float]) -> FitResult:
    """
    Fit y = a*x + c using least squares.

    For deflection testing: y = F (force), x = delta (deflection)
    Slope a = k = dF/d(delta)

    Args:
        x: Independent variable (deflection)
        y: Dependent variable (force)

    Returns:
        FitResult with slope, intercept, R^2, and point count

    Raises:
        ValueError: If fewer than 2 points or all x values identical
    """
    n = len(x)
    if n < 2:
        raise ValueError(f"Need at least 2 points for fit, got {n}")

    xbar = sum(x) / n
    ybar = sum(y) / n

    sxx = sum((xi - xbar) ** 2 for xi in x)
    if sxx == 0:
        raise ValueError("All x values are identical; cannot fit")

    sxy = sum((xi - xbar) * (yi - ybar) for xi, yi in zip(x, y))

    a = sxy / sxx  # slope
    c = ybar - a * xbar  # intercept

    # R^2 coefficient of determination
    ss_tot = sum((yi - ybar) ** 2 for yi in y)
    ss_res = sum((yi - (a * xi + c)) ** 2 for xi, yi in zip(x, y))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

    return FitResult(slope_N_per_m=a, intercept_N=c, r2=r2, n_points=n)


def compute_density(strip: StripMassGeom, width_m: float, thick_m: float) -> float:
    """
    Compute density from strip mass and dimensions.

    rho = m / (L * b * h)

    Args:
        strip: Strip length and mass
        width_m: Width in m
        thick_m: Thickness in m

    Returns:
        Density in kg/m^3

    Raises:
        ValueError: If volume is not positive
    """
    V = strip.strip_len_m * width_m * thick_m
    if V <= 0:
        raise ValueError(f"Volume must be > 0, got {V}")
    return strip.strip_mass_kg / V


def thickness_target(h_ref_m: float, E_ref_Pa: float, E_new_Pa: float) -> float:
    """
    Compute target thickness for constant flexural rigidity (E * h^3).

    h_new = h_ref * (E_ref / E_new)^(1/3)

    This is the Gore-style "normalize stiffness" calculation.

    Args:
        h_ref_m: Reference thickness in m
        E_ref_Pa: Reference Young's modulus in Pa
        E_new_Pa: Measured Young's modulus in Pa

    Returns:
        Target thickness in m

    Raises:
        ValueError: If E_new is not positive
    """
    if E_new_Pa <= 0:
        raise ValueError(f"E_new must be > 0, got {E_new_Pa}")
    return h_ref_m * (E_ref_Pa / E_new_Pa) ** (1.0 / 3.0)


def compute_specific_stiffness(E_Pa: float, rho_kg_m3: float) -> Tuple[float, float]:
    """
    Compute specific stiffness and longitudinal wave speed.

    E/rho has units m^2/s^2
    c_L = sqrt(E/rho) has units m/s

    Args:
        E_Pa: Young's modulus in Pa
        rho_kg_m3: Density in kg/m^3

    Returns:
        Tuple of (specific_stiffness, wave_speed)
    """
    if rho_kg_m3 <= 0:
        raise ValueError(f"Density must be > 0, got {rho_kg_m3}")

    spec = E_Pa / rho_kg_m3
    c_L = math.sqrt(spec)
    return spec, c_L


# =============================================================================
# CSV parsing
# =============================================================================


def read_csv_points(path: str) -> Tuple[List[float], List[float]]:
    """
    Read load/deflection data from CSV.

    Supported schemas:
        - load_N, defl_mm                                    (net values)
        - m_base_kg, m_test_kg, defl_base_mm, defl_test_mm   (computes net)

    Args:
        path: Path to CSV file

    Returns:
        Tuple of (loads_N, deflections_m)

    Raises:
        ValueError: If CSV schema not recognized
        FileNotFoundError: If file doesn't exist
    """
    loads: List[float] = []
    defls: List[float] = []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = {c.strip() for c in reader.fieldnames or []}

        # Determine schema
        has_net = {"load_N", "defl_mm"}.issubset(cols)
        has_base_test = {
            "m_base_kg",
            "m_test_kg",
            "defl_base_mm",
            "defl_test_mm",
        }.issubset(cols)

        if not has_net and not has_base_test:
            raise ValueError(
                "CSV must contain either (load_N, defl_mm) or "
                "(m_base_kg, m_test_kg, defl_base_mm, defl_test_mm). "
                f"Found columns: {cols}"
            )

        for row in reader:
            # Strip whitespace from keys and values
            row = {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
            }

            if has_net:
                F = float(row["load_N"])
                d = mm_to_m(float(row["defl_mm"]))
            else:
                # Base/test subtraction schema
                m_base = float(row["m_base_kg"])
                m_test = float(row["m_test_kg"])
                F = (m_test - m_base) * G
                d = mm_to_m(float(row["defl_test_mm"]) - float(row["defl_base_mm"]))

            loads.append(F)
            defls.append(d)

    return loads, defls


# =============================================================================
# Main analysis function
# =============================================================================


def analyze_deflection(
    span_mm: float,
    width_mm: float,
    thick_mm: float,
    loads_N: List[float],
    deflections_mm: List[float],
    strip_len_mm: Optional[float] = None,
    strip_mass_g: Optional[float] = None,
    h_ref_mm: Optional[float] = None,
    E_ref_GPa: Optional[float] = None,
) -> DeflectionResult:
    """
    Analyze deflection data to compute Young's modulus and related properties.

    Args:
        span_mm: Support span L in mm
        width_mm: Strip width b in mm
        thick_mm: Strip thickness h in mm
        loads_N: List of applied forces in N
        deflections_mm: List of deflections at midspan in mm
        strip_len_mm: Optional strip length for density calculation
        strip_mass_g: Optional strip mass for density calculation
        h_ref_mm: Optional reference thickness for targeting
        E_ref_GPa: Optional reference E for targeting

    Returns:
        DeflectionResult with all computed values
    """
    warnings: List[str] = []

    # Build geometry
    geom = Geometry(
        span_m=mm_to_m(span_mm),
        width_m=mm_to_m(width_mm),
        thick_m=mm_to_m(thick_mm),
    )

    # Check slenderness ratio
    if geom.slenderness_ratio < 20:
        warnings.append(
            f"L/h = {geom.slenderness_ratio:.1f} < 20: Euler-Bernoulli may be inaccurate. "
            "Consider longer span or thinner specimen."
        )

    # Convert deflections to meters
    defls_m = [mm_to_m(d) for d in deflections_mm]

    # Fit or single point
    if len(loads_N) >= 2:
        fit = linear_fit(defls_m, loads_N)  # y=F, x=delta
        E = compute_E_from_slope(geom, fit.slope_N_per_m)
        method = "linear_fit"
        slope = fit.slope_N_per_m
        r2 = fit.r2
        n_points = fit.n_points

        # Warn if poor fit
        if r2 < 0.99:
            warnings.append(
                f"R^2 = {r2:.4f} < 0.99: Check for nonlinearity, creep, or measurement error."
            )
    else:
        E = compute_E_single_point(geom, loads_N[0], defls_m[0])
        method = "single_point"
        slope = loads_N[0] / defls_m[0]
        r2 = None
        n_points = 1
        warnings.append(
            "Single-point calculation is less reliable than multi-point fit."
        )

    E_GPa = E / 1e9

    # Build result
    result = DeflectionResult(
        span_mm=span_mm,
        width_mm=width_mm,
        thick_mm=thick_mm,
        slenderness_ratio=round(geom.slenderness_ratio, 1),
        method=method,
        slope_N_per_m=round(slope, 3),
        r2=round(r2, 5) if r2 is not None else None,
        n_points=n_points,
        E_Pa=round(E, 0),
        E_GPa=round(E_GPa, 3),
        warnings=warnings,
    )

    # Density and specific stiffness
    if strip_len_mm is not None and strip_mass_g is not None:
        strip = StripMassGeom(
            strip_len_m=mm_to_m(strip_len_mm),
            strip_mass_kg=g_to_kg(strip_mass_g),
        )
        rho = compute_density(strip, geom.width_m, geom.thick_m)
        spec, c_L = compute_specific_stiffness(E, rho)

        result.density_kg_m3 = round(rho, 1)
        result.density_g_cm3 = round(rho / 1000, 3)
        result.specific_stiffness_m2_s2 = round(spec, 0)
        result.wave_speed_m_s = round(c_L, 0)

    # Thickness targeting
    if h_ref_mm is not None and E_ref_GPa is not None:
        h_ref_m = mm_to_m(h_ref_mm)
        E_ref_Pa = E_ref_GPa * 1e9
        h_new_m = thickness_target(h_ref_m, E_ref_Pa, E)

        result.h_target_mm = round(m_to_mm(h_new_m), 3)
        result.h_ref_mm = h_ref_mm
        result.E_ref_GPa = E_ref_GPa

    return result


# =============================================================================
# CLI interface
# =============================================================================


def print_report(result: DeflectionResult) -> None:
    """Print formatted report to console."""
    print("\n" + "=" * 60)
    print("3-Point Bending Results (Euler-Bernoulli)")
    print("=" * 60)

    print("\nGeometry:")
    print(f"  Span L        : {result.span_mm:.3f} mm")
    print(f"  Width b       : {result.width_mm:.3f} mm")
    print(f"  Thickness h   : {result.thick_mm:.3f} mm")
    print(f"  L/h ratio     : {result.slenderness_ratio:.1f}")

    print("\nFit:")
    print(f"  Method        : {result.method}")
    print(f"  Points        : {result.n_points}")
    print(f"  Slope k       : {result.slope_N_per_m:.3e} N/m")
    if result.r2 is not None:
        print(f"  R^2           : {result.r2:.5f}")

    print("\nStiffness:")
    print(f"  Young's E     : {result.E_Pa:.3e} Pa")
    print(f"                : {result.E_GPa:.3f} GPa")

    if result.density_kg_m3 is not None:
        print("\nDensity / Specific Stiffness:")
        print(f"  Density       : {result.density_kg_m3:.1f} kg/m^3")
        print(f"                : {result.density_g_cm3:.3f} g/cm^3")
        print(f"  E/rho         : {result.specific_stiffness_m2_s2:.0f} m^2/s^2")
        print(f"  c_L (wave)    : {result.wave_speed_m_s:.0f} m/s")

    if result.h_target_mm is not None:
        print("\nThickness Target (constant E*h^3):")
        print(
            f"  Reference     : {result.h_ref_mm:.3f} mm at {result.E_ref_GPa:.3f} GPa"
        )
        print(f"  Target h      : {result.h_target_mm:.3f} mm")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  - {w}")

    print()


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Compute Young's modulus from 3-point bending deflection test.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required geometry
    ap.add_argument(
        "--span_mm",
        type=float,
        required=True,
        help="Support span L (mm)",
    )
    ap.add_argument(
        "--width_mm",
        type=float,
        required=True,
        help="Strip width b (mm)",
    )
    ap.add_argument(
        "--thick_mm",
        type=float,
        required=True,
        help="Strip thickness h (mm) - bending direction",
    )

    # Load/deflection input (mutually exclusive)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--csv",
        type=str,
        help="CSV file with load/deflection data",
    )
    group.add_argument(
        "--loads_N",
        type=float,
        nargs="+",
        help="Loads (N), space-separated",
    )

    # Deflections (required with --loads_N)
    ap.add_argument(
        "--defl_mm",
        type=float,
        nargs="+",
        help="Deflections at midspan (mm), same count as loads",
    )

    # Optional: density inputs
    ap.add_argument(
        "--strip_len_mm",
        type=float,
        help="Strip length for mass/volume calculation (mm)",
    )
    ap.add_argument(
        "--strip_mass_g",
        type=float,
        help="Strip mass (g)",
    )

    # Optional: thickness targeting
    ap.add_argument(
        "--href_mm",
        type=float,
        help="Reference thickness (mm) for thickness targeting",
    )
    ap.add_argument(
        "--eref_GPa",
        type=float,
        help="Reference E (GPa) for thickness targeting",
    )

    # Output options
    ap.add_argument(
        "--json",
        type=str,
        help="Output JSON file path",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (use with --json)",
    )

    args = ap.parse_args()

    # Get load/deflection data
    if args.csv:
        loads_N, defls_m = read_csv_points(args.csv)
        deflections_mm = [m_to_mm(d) for d in defls_m]
    else:
        if args.defl_mm is None:
            ap.error("--defl_mm is required when using --loads_N")
        if len(args.loads_N) != len(args.defl_mm):
            ap.error(
                f"loads_N ({len(args.loads_N)}) and defl_mm ({len(args.defl_mm)}) "
                "must have the same length"
            )
        loads_N = list(args.loads_N)
        deflections_mm = list(args.defl_mm)

    # Run analysis
    result = analyze_deflection(
        span_mm=args.span_mm,
        width_mm=args.width_mm,
        thick_mm=args.thick_mm,
        loads_N=loads_N,
        deflections_mm=deflections_mm,
        strip_len_mm=args.strip_len_mm,
        strip_mass_g=args.strip_mass_g,
        h_ref_mm=args.href_mm,
        E_ref_GPa=args.eref_GPa,
    )

    # Output
    if not args.quiet:
        print_report(result)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        if not args.quiet:
            print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
