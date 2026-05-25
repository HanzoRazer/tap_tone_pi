# INSTRUMENT CLASS: MEASUREMENT
"""
Physics calculations for plate tuning analysis.

Computes density, stiffness (Young's modulus) from manual deflection data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import TuningSession, TuningHistory


@dataclass
class SessionStats:
    """Computed statistics for a tuning session."""

    density_kg_m3: Optional[float]
    avg_thickness_mm: Optional[float]
    avg_deflection_mm: Optional[float]
    stiffness_estimates: dict[str, float]  # location -> E in GPa


def compute_density(
    mass_g: float,
    length_mm: float,
    width_mm: float,
    thickness_mm: float,
) -> float:
    """Compute wood density from mass and dimensions.

    Args:
        mass_g: Panel mass in grams
        length_mm: Panel length in mm
        width_mm: Panel width in mm
        thickness_mm: Panel thickness in mm (average or measured)

    Returns:
        Density in kg/m³

    Formula:
        ρ = m / V = m / (L × W × h)
        Converting units: g/mm³ → kg/m³ (multiply by 1e6)
    """
    volume_mm3 = length_mm * width_mm * thickness_mm
    if volume_mm3 <= 0:
        raise ValueError("Volume must be positive")

    density_g_mm3 = mass_g / volume_mm3
    density_kg_m3 = density_g_mm3 * 1e6  # g/mm³ to kg/m³
    return density_kg_m3


def compute_stiffness(
    deflection_mm: float,
    thickness_mm: float,
    span_mm: float,
    width_mm: float,
    load_n: float = 1.0,
) -> float:
    """Compute Young's modulus from 3-point bending deflection.

    Args:
        deflection_mm: Measured deflection at center
        thickness_mm: Panel thickness at measurement point
        span_mm: Support span (distance between supports)
        width_mm: Panel width (beam width)
        load_n: Applied load in Newtons (default 1.0 for normalized)

    Returns:
        Young's modulus E in GPa

    Formula (3-point bending, center load):
        E = F × L³ / (4 × b × h³ × δ)

    Where:
        F = load (N)
        L = span (mm)
        b = width (mm)
        h = thickness (mm)
        δ = deflection (mm)
    """
    if deflection_mm <= 0:
        raise ValueError("Deflection must be positive")
    if thickness_mm <= 0:
        raise ValueError("Thickness must be positive")

    # E = F × L³ / (4 × b × h³ × δ)
    numerator = load_n * (span_mm**3)
    denominator = 4 * width_mm * (thickness_mm**3) * deflection_mm

    e_mpa = numerator / denominator  # Result in MPa (N/mm²)
    e_gpa = e_mpa / 1000  # Convert to GPa

    return e_gpa


def compute_session_stats(
    session: TuningSession,
    length_mm: float,
    width_mm: float,
    span_mm: Optional[float] = None,
    load_n: float = 1.0,
) -> SessionStats:
    """Compute derived statistics for a tuning session.

    Args:
        session: The tuning session with readings
        length_mm: Panel length
        width_mm: Panel width
        span_mm: Support span for stiffness calculation (default: 0.8 × length)
        load_n: Applied load for stiffness calculation

    Returns:
        SessionStats with density and stiffness estimates
    """
    if span_mm is None:
        span_mm = 0.8 * length_mm  # Typical support span

    avg_thickness = session.avg_thickness_mm()

    # Compute density
    density = None
    if avg_thickness is not None and avg_thickness > 0:
        density = compute_density(
            mass_g=session.mass_g,
            length_mm=length_mm,
            width_mm=width_mm,
            thickness_mm=avg_thickness,
        )

    # Compute per-location stiffness
    stiffness_estimates: dict[str, float] = {}
    for reading in session.readings:
        if reading.deflection_mm > 0 and reading.thickness_mm > 0:
            e = compute_stiffness(
                deflection_mm=reading.deflection_mm,
                thickness_mm=reading.thickness_mm,
                span_mm=span_mm,
                width_mm=width_mm,
                load_n=load_n,
            )
            stiffness_estimates[reading.location] = e

    # Average deflection
    avg_deflection = None
    if session.readings:
        avg_deflection = sum(r.deflection_mm for r in session.readings) / len(
            session.readings
        )

    return SessionStats(
        density_kg_m3=density,
        avg_thickness_mm=avg_thickness,
        avg_deflection_mm=avg_deflection,
        stiffness_estimates=stiffness_estimates,
    )


def compute_history_stats(
    history: TuningHistory,
    span_mm: Optional[float] = None,
    load_n: float = 1.0,
) -> list[SessionStats]:
    """Compute stats for all sessions in a history.

    Args:
        history: Complete tuning history
        span_mm: Support span (default: 0.8 × length)
        load_n: Applied load

    Returns:
        List of SessionStats, one per session
    """
    return [
        compute_session_stats(
            session=s,
            length_mm=history.length_mm,
            width_mm=history.width_mm,
            span_mm=span_mm,
            load_n=load_n,
        )
        for s in history.sessions
    ]
