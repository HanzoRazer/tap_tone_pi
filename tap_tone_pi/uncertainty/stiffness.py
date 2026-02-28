"""
Stiffness (MOE) measurement uncertainty calculations.

Covers both deflection and tap tone methods.
"""

from __future__ import annotations

import math
from typing import Optional

from .budget import (
    UncertaintyBudget,
    UncertaintyType,
    UNCERTAINTY_FACTORS,
)


def compute_deflection_moe_uncertainty(
    E_GPa: float,
    span_mm: float,
    span_uncertainty_mm: float = 0.5,
    width_mm: float = 30.0,
    width_uncertainty_mm: float = 0.2,
    thickness_mm: float = 3.0,
    thickness_uncertainty_mm: float = 0.05,
    deflection_mm: float = 1.0,
    deflection_uncertainty_mm: float = 0.02,
    force_N: float = 10.0,
    force_uncertainty_N: float = 0.05,
    r_squared: Optional[float] = None,
) -> UncertaintyBudget:
    """
    Compute uncertainty budget for deflection-derived MOE.

    For 3-point bending: E = (F × L³) / (4 × b × h³ × δ)

    Error propagation (relative uncertainties):
    (ΔE/E)² = (ΔF/F)² + (3×ΔL/L)² + (Δb/b)² + (3×Δh/h)² + (Δδ/δ)²

    The thickness uncertainty dominates due to the h³ term.

    Args:
        E_GPa: Calculated Young's modulus in GPa
        span_mm: Support span in mm
        span_uncertainty_mm: Span measurement uncertainty
        width_mm: Specimen width in mm
        width_uncertainty_mm: Width measurement uncertainty
        thickness_mm: Specimen thickness in mm
        thickness_uncertainty_mm: Thickness measurement uncertainty
        deflection_mm: Measured deflection in mm
        deflection_uncertainty_mm: Deflection measurement uncertainty
        force_N: Applied force in N
        force_uncertainty_N: Force measurement uncertainty
        r_squared: R² from linear fit (if multi-point), affects uncertainty

    Returns:
        UncertaintyBudget for MOE measurement
    """
    budget = UncertaintyBudget(
        measurement_value=E_GPa,
        measurement_unit="GPa",
    )

    # Relative uncertainties
    rel_force = force_uncertainty_N / force_N if force_N > 0 else 0.1
    rel_span = span_uncertainty_mm / span_mm if span_mm > 0 else 0.01
    rel_width = width_uncertainty_mm / width_mm if width_mm > 0 else 0.01
    rel_thickness = thickness_uncertainty_mm / thickness_mm if thickness_mm > 0 else 0.01
    rel_deflection = (
        deflection_uncertainty_mm / deflection_mm if deflection_mm > 0 else 0.1
    )

    # Sensitivity coefficients (from error propagation)
    # E ∝ F × L³ / (b × h³ × δ)
    sens_force = 1.0
    sens_span = 3.0
    sens_width = 1.0
    sens_thickness = 3.0  # h³ term makes this dominant
    sens_deflection = 1.0

    # Force uncertainty
    force_contrib = E_GPa * rel_force * sens_force
    budget.add_component(
        name="Force measurement",
        value=force_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Force ± {force_uncertainty_N:.3f} N",
        sensitivity_coefficient=sens_force,
    )

    # Span uncertainty
    span_contrib = E_GPa * rel_span * sens_span
    budget.add_component(
        name="Span measurement",
        value=span_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Span ± {span_uncertainty_mm:.1f} mm (×3 sensitivity)",
        sensitivity_coefficient=sens_span,
    )

    # Width uncertainty
    width_contrib = E_GPa * rel_width * sens_width
    budget.add_component(
        name="Width measurement",
        value=width_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Width ± {width_uncertainty_mm:.2f} mm",
        sensitivity_coefficient=sens_width,
    )

    # Thickness uncertainty (DOMINANT)
    thickness_contrib = E_GPa * rel_thickness * sens_thickness
    budget.add_component(
        name="Thickness measurement",
        value=thickness_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Thickness ± {thickness_uncertainty_mm:.3f} mm (×3 sensitivity, DOMINANT)",
        sensitivity_coefficient=sens_thickness,
    )

    # Deflection uncertainty
    deflection_contrib = E_GPa * rel_deflection * sens_deflection
    budget.add_component(
        name="Deflection measurement",
        value=deflection_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Deflection ± {deflection_uncertainty_mm:.3f} mm",
        sensitivity_coefficient=sens_deflection,
    )

    # R² contribution (fit quality)
    if r_squared is not None:
        # Lower R² increases uncertainty
        # Rough heuristic: each 0.01 below 1.0 adds 0.5% relative uncertainty
        if r_squared < 1.0:
            r2_penalty = (1.0 - r_squared) * 50  # % relative uncertainty
            r2_contrib = E_GPa * r2_penalty / 100

            budget.add_component(
                name="Fit quality (R²)",
                value=r2_contrib,
                unit="GPa",
                uncertainty_type=UncertaintyType.TYPE_A,
                description=f"R² = {r_squared:.4f}",
            )

    return budget


def compute_tap_tone_moe_uncertainty(
    E_GPa: float,
    frequency_hz: float,
    frequency_uncertainty_hz: float = 2.0,
    length_mm: float = 400.0,
    length_uncertainty_mm: float = 0.5,
    width_mm: float = 30.0,
    width_uncertainty_mm: float = 0.2,
    thickness_mm: float = 3.0,
    thickness_uncertainty_mm: float = 0.05,
    density_kg_m3: float = 400.0,
    density_uncertainty_kg_m3: float = 10.0,
    snr_db: float = 40.0,
    is_calibrated: bool = False,
) -> UncertaintyBudget:
    """
    Compute uncertainty budget for tap-tone-derived MOE.

    For free-free beam: E ∝ f² × L⁴ × ρ / h²

    Error propagation (relative uncertainties):
    (ΔE/E)² = (2×Δf/f)² + (4×ΔL/L)² + (Δρ/ρ)² + (2×Δh/h)²

    Args:
        E_GPa: Calculated Young's modulus in GPa
        frequency_hz: Measured fundamental frequency in Hz
        frequency_uncertainty_hz: Frequency uncertainty in Hz
        length_mm: Specimen length in mm
        length_uncertainty_mm: Length measurement uncertainty
        width_mm: Specimen width in mm
        width_uncertainty_mm: Width measurement uncertainty (for density)
        thickness_mm: Specimen thickness in mm
        thickness_uncertainty_mm: Thickness measurement uncertainty
        density_kg_m3: Calculated density in kg/m³
        density_uncertainty_kg_m3: Density uncertainty
        snr_db: Signal-to-noise ratio in dB
        is_calibrated: Whether system is calibrated

    Returns:
        UncertaintyBudget for MOE measurement
    """
    budget = UncertaintyBudget(
        measurement_value=E_GPa,
        measurement_unit="GPa",
    )

    # Relative uncertainties
    rel_freq = frequency_uncertainty_hz / frequency_hz if frequency_hz > 0 else 0.01
    rel_length = length_uncertainty_mm / length_mm if length_mm > 0 else 0.01
    rel_thickness = thickness_uncertainty_mm / thickness_mm if thickness_mm > 0 else 0.01
    rel_density = (
        density_uncertainty_kg_m3 / density_kg_m3 if density_kg_m3 > 0 else 0.03
    )

    # Sensitivity coefficients
    # E ∝ f² × L⁴ × ρ / h²
    sens_freq = 2.0
    sens_length = 4.0
    sens_density = 1.0
    sens_thickness = 2.0

    # Frequency uncertainty (×2 sensitivity)
    freq_contrib = E_GPa * rel_freq * sens_freq
    budget.add_component(
        name="Frequency measurement",
        value=freq_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_A,
        description=f"Frequency ± {frequency_uncertainty_hz:.1f} Hz (×2 sensitivity)",
        sensitivity_coefficient=sens_freq,
    )

    # Length uncertainty (×4 sensitivity - MAJOR)
    length_contrib = E_GPa * rel_length * sens_length
    budget.add_component(
        name="Length measurement",
        value=length_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Length ± {length_uncertainty_mm:.1f} mm (×4 sensitivity, MAJOR)",
        sensitivity_coefficient=sens_length,
    )

    # Thickness uncertainty (×2 sensitivity)
    thickness_contrib = E_GPa * rel_thickness * sens_thickness
    budget.add_component(
        name="Thickness measurement",
        value=thickness_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Thickness ± {thickness_uncertainty_mm:.3f} mm (×2 sensitivity)",
        sensitivity_coefficient=sens_thickness,
    )

    # Density uncertainty
    density_contrib = E_GPa * rel_density * sens_density
    budget.add_component(
        name="Density calculation",
        value=density_contrib,
        unit="GPa",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"Density ± {density_uncertainty_kg_m3:.1f} kg/m³",
        sensitivity_coefficient=sens_density,
    )

    # Signal quality contribution
    # Lower SNR increases frequency uncertainty
    if snr_db < 40:
        snr_penalty = (40 - snr_db) / 100 * E_GPa  # ~1% per 10dB below 40dB
        budget.add_component(
            name="Signal quality (SNR)",
            value=snr_penalty,
            unit="GPa",
            uncertainty_type=UncertaintyType.TYPE_A,
            description=f"SNR = {snr_db:.1f} dB (below optimal)",
        )

    # Calibration state
    if not is_calibrated:
        cal_penalty = E_GPa * UNCERTAINTY_FACTORS["tap_tone_method"] * 0.5
        budget.add_component(
            name="Uncalibrated system",
            value=cal_penalty,
            unit="GPa",
            uncertainty_type=UncertaintyType.TYPE_B,
            description="System not calibrated",
        )

    return budget


def compute_stiffness_uncertainty(
    E_GPa: float,
    method: str = "deflection",
    **kwargs,
) -> UncertaintyBudget:
    """
    Compute stiffness uncertainty using appropriate method.

    Args:
        E_GPa: Calculated Young's modulus in GPa
        method: "deflection" or "tap_tone"
        **kwargs: Method-specific parameters

    Returns:
        UncertaintyBudget for MOE measurement
    """
    if method == "deflection":
        return compute_deflection_moe_uncertainty(E_GPa, **kwargs)
    elif method == "tap_tone":
        return compute_tap_tone_moe_uncertainty(E_GPa, **kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")


def estimate_stiffness_repeatability(
    measurements_GPa: list[float],
) -> float:
    """
    Estimate stiffness repeatability from repeated measurements (Type A).

    Args:
        measurements_GPa: List of stiffness measurements in GPa

    Returns:
        Standard deviation of the mean (standard uncertainty)
    """
    if len(measurements_GPa) < 2:
        return float("inf")

    n = len(measurements_GPa)
    mean = sum(measurements_GPa) / n
    variance = sum((x - mean) ** 2 for x in measurements_GPa) / (n - 1)
    std_dev = math.sqrt(variance)

    return std_dev / math.sqrt(n)
