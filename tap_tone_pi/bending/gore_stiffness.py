#!/usr/bin/env python3
"""
gore_stiffness.py — Gore-style stiffness index calculations for tonewood analysis.

Implements the "Gore spreadsheet" approach from Trevor Gore's
"Contemporary Acoustic Guitar Design and Build" methodology.

Core Concepts:
    Stiffness Index (SI):  SI = E × h³
    - Measures plate's resistance to bending
    - Allows comparison between woods of different E and h
    - Units: GPa·mm³ (shop units) or N·m (SI units)

    Orthotropic Analysis:
    - E_L = long-grain (parallel to fibers) modulus
    - E_C = cross-grain (perpendicular to fibers) modulus
    - Ratio E_L/E_C typically 10-20 for quality tonewoods

    Thickness Targeting:
    - Given target SI and measured E, compute required thickness
    - h_target = (SI_target / E)^(1/3)

Usage:
    # Single direction
    python -m tap_tone_pi.bending.gore_stiffness \\
        --E_GPa 12.5 --h_mm 3.0 --direction L

    # Orthotropic (both directions)
    python -m tap_tone_pi.bending.gore_stiffness \\
        --E_L_GPa 12.5 --E_C_GPa 0.8 --h_mm 3.0 \\
        --SI_target_L 320

References:
    - Gore & Gilet, "Contemporary Acoustic Guitar Design and Build"
    - David Hurd, "Left-Brain Lutherie"
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# =============================================================================
# Constants and Presets
# =============================================================================


class GrainDirection(str, Enum):
    """Grain direction for anisotropic wood properties."""

    LONG = "L"  # Parallel to grain (longitudinal)
    CROSS = "C"  # Perpendicular to grain (radial/tangential)
    UNKNOWN = "?"  # Direction not specified


class InstrumentType(str, Enum):
    """Instrument types for target SI presets."""

    CLASSICAL_GUITAR = "classical"
    STEEL_STRING_DREADNOUGHT = "dreadnought"
    STEEL_STRING_OM = "om"
    STEEL_STRING_PARLOR = "parlor"
    ARCHTOP = "archtop"
    UKULELE_SOPRANO = "ukulele_soprano"
    UKULELE_CONCERT = "ukulele_concert"
    UKULELE_TENOR = "ukulele_tenor"
    MANDOLIN = "mandolin"
    CUSTOM = "custom"


@dataclass(frozen=True)
class SITargetPreset:
    """Preset target stiffness index values for instrument types.

    Values derived from Gore & Gilet recommendations and common luthier practice.
    SI values in GPa·mm³.
    """

    instrument: InstrumentType
    description: str
    SI_L_min: float  # Long-grain SI minimum
    SI_L_typical: float  # Long-grain SI typical/target
    SI_L_max: float  # Long-grain SI maximum
    SI_C_min: Optional[float] = None  # Cross-grain SI minimum (if specified)
    SI_C_typical: Optional[float] = None  # Cross-grain SI typical
    SI_C_max: Optional[float] = None  # Cross-grain SI maximum
    h_typical_mm: float = 2.8  # Typical finished thickness
    notes: str = ""


# Preset target SI values based on Gore & Gilet and common practice
SI_PRESETS: Dict[InstrumentType, SITargetPreset] = {
    InstrumentType.CLASSICAL_GUITAR: SITargetPreset(
        instrument=InstrumentType.CLASSICAL_GUITAR,
        description="Classical guitar soundboard (cedar or spruce)",
        SI_L_min=280,
        SI_L_typical=320,
        SI_L_max=380,
        SI_C_min=18,
        SI_C_typical=25,
        SI_C_max=35,
        h_typical_mm=2.5,
        notes="Lower SI for warmer tone, higher for projection",
    ),
    InstrumentType.STEEL_STRING_DREADNOUGHT: SITargetPreset(
        instrument=InstrumentType.STEEL_STRING_DREADNOUGHT,
        description="Steel-string dreadnought (Sitka spruce typical)",
        SI_L_min=350,
        SI_L_typical=420,
        SI_L_max=500,
        SI_C_min=22,
        SI_C_typical=30,
        SI_C_max=40,
        h_typical_mm=2.8,
        notes="Higher SI for volume and projection",
    ),
    InstrumentType.STEEL_STRING_OM: SITargetPreset(
        instrument=InstrumentType.STEEL_STRING_OM,
        description="Steel-string OM/000 (balanced response)",
        SI_L_min=320,
        SI_L_typical=380,
        SI_L_max=450,
        SI_C_min=20,
        SI_C_typical=28,
        SI_C_max=38,
        h_typical_mm=2.7,
        notes="Slightly lighter build than dreadnought",
    ),
    InstrumentType.STEEL_STRING_PARLOR: SITargetPreset(
        instrument=InstrumentType.STEEL_STRING_PARLOR,
        description="Steel-string parlor (intimate, responsive)",
        SI_L_min=280,
        SI_L_typical=340,
        SI_L_max=400,
        SI_C_min=18,
        SI_C_typical=25,
        SI_C_max=32,
        h_typical_mm=2.5,
        notes="Lighter build for smaller body",
    ),
    InstrumentType.ARCHTOP: SITargetPreset(
        instrument=InstrumentType.ARCHTOP,
        description="Archtop guitar (carved spruce or maple)",
        SI_L_min=400,
        SI_L_typical=500,
        SI_L_max=650,
        h_typical_mm=3.5,
        notes="Higher SI for carved top stability",
    ),
    InstrumentType.UKULELE_SOPRANO: SITargetPreset(
        instrument=InstrumentType.UKULELE_SOPRANO,
        description="Soprano ukulele soundboard",
        SI_L_min=80,
        SI_L_typical=120,
        SI_L_max=160,
        h_typical_mm=2.0,
        notes="Very light build",
    ),
    InstrumentType.UKULELE_CONCERT: SITargetPreset(
        instrument=InstrumentType.UKULELE_CONCERT,
        description="Concert ukulele soundboard",
        SI_L_min=100,
        SI_L_typical=140,
        SI_L_max=180,
        h_typical_mm=2.2,
    ),
    InstrumentType.UKULELE_TENOR: SITargetPreset(
        instrument=InstrumentType.UKULELE_TENOR,
        description="Tenor ukulele soundboard",
        SI_L_min=120,
        SI_L_typical=160,
        SI_L_max=200,
        h_typical_mm=2.3,
    ),
    InstrumentType.MANDOLIN: SITargetPreset(
        instrument=InstrumentType.MANDOLIN,
        description="Mandolin soundboard (carved or flat)",
        SI_L_min=200,
        SI_L_typical=280,
        SI_L_max=350,
        h_typical_mm=2.5,
    ),
}


def get_preset(instrument: InstrumentType | str) -> Optional[SITargetPreset]:
    """Get preset SI targets for an instrument type."""
    if isinstance(instrument, str):
        try:
            instrument = InstrumentType(instrument.lower())
        except ValueError:
            return None
    return SI_PRESETS.get(instrument)


def list_presets() -> List[Dict[str, Any]]:
    """List all available SI presets."""
    return [
        {
            "instrument": p.instrument.value,
            "description": p.description,
            "SI_L_range": f"{p.SI_L_min}-{p.SI_L_max}",
            "SI_L_typical": p.SI_L_typical,
            "h_typical_mm": p.h_typical_mm,
        }
        for p in SI_PRESETS.values()
    ]


# =============================================================================
# Core Stiffness Calculations
# =============================================================================


def stiffness_index(E_GPa: float, h_mm: float) -> float:
    """
    Compute stiffness index SI = E × h³.

    Args:
        E_GPa: Young's modulus in GPa
        h_mm: Thickness in mm

    Returns:
        Stiffness index in GPa·mm³

    Physics:
        SI captures the plate's bending stiffness independent of width.
        Two plates with equal SI will have equal bending rigidity per unit width.
    """
    return E_GPa * (h_mm**3)


def thickness_for_target_SI(SI_target: float, E_GPa: float) -> float:
    """
    Compute thickness required to achieve target stiffness index.

    h = (SI_target / E)^(1/3)

    Args:
        SI_target: Target stiffness index in GPa·mm³
        E_GPa: Young's modulus in GPa

    Returns:
        Required thickness in mm

    Raises:
        ValueError: If E_GPa <= 0
    """
    if E_GPa <= 0:
        raise ValueError(f"E must be positive, got {E_GPa}")
    return (SI_target / E_GPa) ** (1.0 / 3.0)


def SI_ratio(SI_1: float, SI_2: float) -> float:
    """Compute ratio of two stiffness indices."""
    if SI_2 == 0:
        return float("inf")
    return SI_1 / SI_2


def orthotropic_ratio(E_L: float, E_C: float) -> float:
    """
    Compute orthotropic ratio E_L / E_C.

    Typical values for quality tonewoods:
        Sitka spruce: 12-16
        Engelmann spruce: 10-14
        Western red cedar: 8-12
        European spruce: 14-20

    Args:
        E_L: Long-grain modulus (GPa)
        E_C: Cross-grain modulus (GPa)

    Returns:
        Orthotropic ratio (dimensionless)
    """
    if E_C == 0:
        return float("inf")
    return E_L / E_C


# =============================================================================
# Result Data Classes
# =============================================================================


@dataclass
class SingleDirectionResult:
    """Result for single-direction stiffness analysis."""

    direction: str  # "L" or "C"
    E_GPa: float
    h_mm: float
    SI: float  # GPa·mm³

    # Optional: thickness targeting
    SI_target: Optional[float] = None
    h_target_mm: Optional[float] = None

    # Optional: density-derived
    density_kg_m3: Optional[float] = None
    specific_stiffness: Optional[float] = None  # E/ρ in m²/s²
    wave_speed_m_s: Optional[float] = None

    # Metadata
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, removing None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != []}


@dataclass
class OrthotropicResult:
    """Result for orthotropic (L + C) stiffness analysis."""

    # Geometry (shared)
    h_mm: float

    # Long-grain
    E_L_GPa: float
    SI_L: float

    # Cross-grain
    E_C_GPa: float
    SI_C: float

    # Ratios
    E_ratio_L_C: float  # E_L / E_C
    E_ratio_C_L: float  # E_C / E_L
    SI_ratio_L_C: float  # SI_L / SI_C

    # Optional: thickness targeting
    SI_target_L: Optional[float] = None
    h_target_L_mm: Optional[float] = None
    SI_target_C: Optional[float] = None
    h_target_C_mm: Optional[float] = None

    # Optional: density (assumes same density for L and C strips)
    density_kg_m3: Optional[float] = None
    specific_stiffness_L: Optional[float] = None
    specific_stiffness_C: Optional[float] = None
    wave_speed_L_m_s: Optional[float] = None
    wave_speed_C_m_s: Optional[float] = None

    # Instrument match
    instrument_match: Optional[str] = None
    preset_comparison: Optional[Dict[str, Any]] = None

    # Metadata
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, removing None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != []}


# =============================================================================
# Analysis Functions
# =============================================================================


def analyze_single_direction(
    E_GPa: float,
    h_mm: float,
    direction: GrainDirection | str = GrainDirection.UNKNOWN,
    SI_target: Optional[float] = None,
    density_kg_m3: Optional[float] = None,
) -> SingleDirectionResult:
    """
    Analyze stiffness for a single grain direction.

    Args:
        E_GPa: Young's modulus in GPa
        h_mm: Thickness in mm
        direction: Grain direction ("L", "C", or "?")
        SI_target: Optional target SI for thickness recommendation
        density_kg_m3: Optional density for specific stiffness

    Returns:
        SingleDirectionResult with computed values
    """
    if isinstance(direction, str):
        direction = (
            GrainDirection(direction.upper())
            if direction.upper() in ("L", "C")
            else GrainDirection.UNKNOWN
        )

    warnings = []

    # Core calculation
    SI = stiffness_index(E_GPa, h_mm)

    result = SingleDirectionResult(
        direction=direction.value,
        E_GPa=round(E_GPa, 3),
        h_mm=round(h_mm, 3),
        SI=round(SI, 2),
    )

    # Thickness targeting
    if SI_target is not None:
        h_target = thickness_for_target_SI(SI_target, E_GPa)
        result.SI_target = SI_target
        result.h_target_mm = round(h_target, 3)

        # Warning if target requires significant material removal
        if h_target < h_mm * 0.6:
            warnings.append(
                f"Target thickness {h_target:.2f}mm is <60% of current ({h_mm:.2f}mm). "
                "Consider a stiffer billet."
            )

    # Density-derived properties
    if density_kg_m3 is not None:
        E_Pa = E_GPa * 1e9
        spec = E_Pa / density_kg_m3
        c = math.sqrt(spec)

        result.density_kg_m3 = round(density_kg_m3, 1)
        result.specific_stiffness = round(spec, 0)
        result.wave_speed_m_s = round(c, 0)

    result.warnings = warnings
    return result


def analyze_orthotropic(
    E_L_GPa: float,
    E_C_GPa: float,
    h_mm: float,
    SI_target_L: Optional[float] = None,
    SI_target_C: Optional[float] = None,
    density_kg_m3: Optional[float] = None,
    match_instrument: Optional[InstrumentType | str] = None,
) -> OrthotropicResult:
    """
    Analyze orthotropic stiffness (both grain directions).

    Args:
        E_L_GPa: Long-grain modulus in GPa
        E_C_GPa: Cross-grain modulus in GPa
        h_mm: Thickness in mm (assumed same for both)
        SI_target_L: Optional target SI for long-grain
        SI_target_C: Optional target SI for cross-grain
        density_kg_m3: Optional density for specific stiffness
        match_instrument: Optional instrument type for preset comparison

    Returns:
        OrthotropicResult with computed values and ratios
    """
    warnings = []

    # Core calculations
    SI_L = stiffness_index(E_L_GPa, h_mm)
    SI_C = stiffness_index(E_C_GPa, h_mm)

    E_ratio_LC = orthotropic_ratio(E_L_GPa, E_C_GPa)
    E_ratio_CL = orthotropic_ratio(E_C_GPa, E_L_GPa)
    SI_ratio_LC = SI_ratio(SI_L, SI_C)

    result = OrthotropicResult(
        h_mm=round(h_mm, 3),
        E_L_GPa=round(E_L_GPa, 3),
        SI_L=round(SI_L, 2),
        E_C_GPa=round(E_C_GPa, 3),
        SI_C=round(SI_C, 2),
        E_ratio_L_C=round(E_ratio_LC, 2),
        E_ratio_C_L=round(E_ratio_CL, 4),
        SI_ratio_L_C=round(SI_ratio_LC, 2),
    )

    # Orthotropic ratio warnings
    if E_ratio_LC < 8:
        warnings.append(
            f"E_L/E_C = {E_ratio_LC:.1f} is low (<8). May indicate runout or unusual wood."
        )
    elif E_ratio_LC > 25:
        warnings.append(
            f"E_L/E_C = {E_ratio_LC:.1f} is high (>25). Verify cross-grain measurement."
        )

    # Thickness targeting
    if SI_target_L is not None:
        h_target_L = thickness_for_target_SI(SI_target_L, E_L_GPa)
        result.SI_target_L = SI_target_L
        result.h_target_L_mm = round(h_target_L, 3)

    if SI_target_C is not None:
        h_target_C = thickness_for_target_SI(SI_target_C, E_C_GPa)
        result.SI_target_C = SI_target_C
        result.h_target_C_mm = round(h_target_C, 3)

    # Density-derived properties
    if density_kg_m3 is not None:
        E_L_Pa = E_L_GPa * 1e9
        E_C_Pa = E_C_GPa * 1e9

        spec_L = E_L_Pa / density_kg_m3
        spec_C = E_C_Pa / density_kg_m3
        c_L = math.sqrt(spec_L)
        c_C = math.sqrt(spec_C)

        result.density_kg_m3 = round(density_kg_m3, 1)
        result.specific_stiffness_L = round(spec_L, 0)
        result.specific_stiffness_C = round(spec_C, 0)
        result.wave_speed_L_m_s = round(c_L, 0)
        result.wave_speed_C_m_s = round(c_C, 0)

    # Instrument preset matching
    if match_instrument is not None:
        preset = get_preset(match_instrument)
        if preset:
            result.instrument_match = preset.instrument.value

            # Compare to preset
            SI_L_status = (
                "low"
                if SI_L < preset.SI_L_min
                else "high"
                if SI_L > preset.SI_L_max
                else "good"
            )

            result.preset_comparison = {
                "instrument": preset.description,
                "SI_L_target_range": f"{preset.SI_L_min}-{preset.SI_L_max}",
                "SI_L_typical": preset.SI_L_typical,
                "SI_L_measured": round(SI_L, 2),
                "SI_L_status": SI_L_status,
                "h_typical_mm": preset.h_typical_mm,
                "h_recommended_mm": round(
                    thickness_for_target_SI(preset.SI_L_typical, E_L_GPa), 3
                ),
            }

            if SI_L_status == "low":
                warnings.append(
                    f"SI_L ({SI_L:.0f}) below range for {preset.instrument.value} "
                    f"({preset.SI_L_min}-{preset.SI_L_max}). Consider thicker stock."
                )
            elif SI_L_status == "high":
                warnings.append(
                    f"SI_L ({SI_L:.0f}) above range for {preset.instrument.value} "
                    f"({preset.SI_L_min}-{preset.SI_L_max}). Can thin more."
                )

    result.warnings = warnings
    return result


# =============================================================================
# Report Formatting
# =============================================================================


def format_single_report(result: SingleDirectionResult) -> str:
    """Format single-direction result as text report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"Gore Stiffness Index — {result.direction}-grain")
    lines.append("=" * 60)

    lines.append("\nInput:")
    lines.append(f"  E ({result.direction})     : {result.E_GPa:.3f} GPa")
    lines.append(f"  Thickness h : {result.h_mm:.3f} mm")

    lines.append("\nStiffness Index:")
    lines.append(f"  SI = E × h³ : {result.SI:.2f} GPa·mm³")

    if result.SI_target is not None:
        lines.append("\nThickness Target:")
        lines.append(f"  Target SI   : {result.SI_target:.2f} GPa·mm³")
        lines.append(f"  h required  : {result.h_target_mm:.3f} mm")
        delta = result.h_mm - result.h_target_mm
        lines.append(
            f"  Remove      : {delta:.3f} mm"
            if delta > 0
            else f"  Add         : {-delta:.3f} mm"
        )

    if result.density_kg_m3 is not None:
        lines.append("\nDensity / Specific Stiffness:")
        lines.append(f"  Density     : {result.density_kg_m3:.1f} kg/m³")
        lines.append(f"  E/ρ         : {result.specific_stiffness:.0f} m²/s²")
        lines.append(f"  Wave speed  : {result.wave_speed_m_s:.0f} m/s")

    if result.warnings:
        lines.append("\nWarnings:")
        for w in result.warnings:
            lines.append(f"  - {w}")

    lines.append("")
    return "\n".join(lines)


def format_orthotropic_report(result: OrthotropicResult) -> str:
    """Format orthotropic result as text report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Gore Stiffness Index — Orthotropic Analysis")
    lines.append("=" * 60)

    lines.append("\nGeometry:")
    lines.append(f"  Thickness h : {result.h_mm:.3f} mm")

    lines.append("\nLong-grain (L):")
    lines.append(f"  E_L         : {result.E_L_GPa:.3f} GPa")
    lines.append(f"  SI_L        : {result.SI_L:.2f} GPa·mm³")

    lines.append("\nCross-grain (C):")
    lines.append(f"  E_C         : {result.E_C_GPa:.3f} GPa")
    lines.append(f"  SI_C        : {result.SI_C:.2f} GPa·mm³")

    lines.append("\nOrthotropic Ratios:")
    lines.append(f"  E_L / E_C   : {result.E_ratio_L_C:.2f}")
    lines.append(f"  E_C / E_L   : {result.E_ratio_C_L:.4f}")
    lines.append(f"  SI_L / SI_C : {result.SI_ratio_L_C:.2f}")

    if result.SI_target_L is not None:
        lines.append("\nThickness Target (L-grain):")
        lines.append(f"  Target SI_L : {result.SI_target_L:.2f} GPa·mm³")
        lines.append(f"  h required  : {result.h_target_L_mm:.3f} mm")

    if result.SI_target_C is not None:
        lines.append("\nThickness Target (C-grain):")
        lines.append(f"  Target SI_C : {result.SI_target_C:.2f} GPa·mm³")
        lines.append(f"  h required  : {result.h_target_C_mm:.3f} mm")

    if result.density_kg_m3 is not None:
        lines.append("\nDensity / Specific Stiffness:")
        lines.append(f"  Density     : {result.density_kg_m3:.1f} kg/m³")
        lines.append(f"  E_L/ρ       : {result.specific_stiffness_L:.0f} m²/s²")
        lines.append(f"  E_C/ρ       : {result.specific_stiffness_C:.0f} m²/s²")
        lines.append(f"  c_L         : {result.wave_speed_L_m_s:.0f} m/s")
        lines.append(f"  c_C         : {result.wave_speed_C_m_s:.0f} m/s")

    if result.preset_comparison is not None:
        pc = result.preset_comparison
        lines.append(f"\nInstrument Match ({pc['instrument']}):")
        lines.append(f"  SI_L range  : {pc['SI_L_target_range']} GPa·mm³")
        lines.append(f"  SI_L typical: {pc['SI_L_typical']} GPa·mm³")
        lines.append(f"  SI_L status : {pc['SI_L_status'].upper()}")
        lines.append(f"  h typical   : {pc['h_typical_mm']:.2f} mm")
        lines.append(f"  h recommend : {pc['h_recommended_mm']:.3f} mm")

    if result.warnings:
        lines.append("\nWarnings:")
        for w in result.warnings:
            lines.append(f"  - {w}")

    lines.append("")
    return "\n".join(lines)


# =============================================================================
# CLI Interface
# =============================================================================


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Gore-style stiffness index calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mode selection
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--single",
        action="store_true",
        help="Single-direction analysis (requires --E_GPa)",
    )
    mode.add_argument(
        "--ortho",
        action="store_true",
        help="Orthotropic analysis (requires --E_L_GPa and --E_C_GPa)",
    )
    mode.add_argument(
        "--list-presets", action="store_true", help="List available instrument presets"
    )

    # Geometry
    ap.add_argument("--h_mm", type=float, help="Thickness in mm")

    # Single-direction inputs
    ap.add_argument("--E_GPa", type=float, help="Young's modulus (single direction)")
    ap.add_argument(
        "--direction",
        choices=["L", "C"],
        default="L",
        help="Grain direction (L=long, C=cross)",
    )

    # Orthotropic inputs
    ap.add_argument("--E_L_GPa", type=float, help="Long-grain modulus")
    ap.add_argument("--E_C_GPa", type=float, help="Cross-grain modulus")

    # Targets
    ap.add_argument("--SI_target", type=float, help="Target SI (single direction)")
    ap.add_argument("--SI_target_L", type=float, help="Target SI for L-grain")
    ap.add_argument("--SI_target_C", type=float, help="Target SI for C-grain")

    # Optional
    ap.add_argument("--density", type=float, help="Density in kg/m³")
    ap.add_argument(
        "--instrument", type=str, help="Instrument type for preset matching"
    )

    # Output
    ap.add_argument("--json", type=str, help="Output JSON file path")
    ap.add_argument("--quiet", action="store_true", help="Suppress console output")

    args = ap.parse_args()

    # List presets mode
    if args.list_presets:
        print("\nAvailable SI Presets:")
        print("=" * 60)
        for p in list_presets():
            print(f"\n{p['instrument']}:")
            print(f"  {p['description']}")
            print(f"  SI_L range: {p['SI_L_range']} GPa·mm³")
            print(f"  SI_L typical: {p['SI_L_typical']} GPa·mm³")
            print(f"  h typical: {p['h_typical_mm']} mm")
        print()
        return

    # Validate inputs
    if args.h_mm is None:
        ap.error("--h_mm is required")

    # Determine mode
    if args.ortho or (args.E_L_GPa is not None and args.E_C_GPa is not None):
        # Orthotropic mode
        if args.E_L_GPa is None or args.E_C_GPa is None:
            ap.error("--E_L_GPa and --E_C_GPa required for orthotropic analysis")

        result = analyze_orthotropic(
            E_L_GPa=args.E_L_GPa,
            E_C_GPa=args.E_C_GPa,
            h_mm=args.h_mm,
            SI_target_L=args.SI_target_L or args.SI_target,
            SI_target_C=args.SI_target_C,
            density_kg_m3=args.density,
            match_instrument=args.instrument,
        )

        if not args.quiet:
            print(format_orthotropic_report(result))

    else:
        # Single-direction mode
        if args.E_GPa is None:
            ap.error("--E_GPa required for single-direction analysis")

        result = analyze_single_direction(
            E_GPa=args.E_GPa,
            h_mm=args.h_mm,
            direction=args.direction,
            SI_target=args.SI_target,
            density_kg_m3=args.density,
        )

        if not args.quiet:
            print(format_single_report(result))

    # JSON output
    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        if not args.quiet:
            print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
