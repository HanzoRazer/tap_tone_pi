"""
tap_tone_pi.design — Plate thickness design and coupled-system analysis.

This module provides tools for determining optimal plate thickness using
orthotropic plate theory and coupled oscillator models.

Core Concepts:
    Orthotropic Plate:
        - E_L: Longitudinal (long-grain) modulus
        - E_C: Cross-grain modulus
        - R_anis = E_L/E_C: Orthotropic ratio (typically 10-20 for tonewoods)

    Coupled Oscillator Models:

        2-Oscillator (rigid back):
            - Top plate (mass + stiffness)
            - Air cavity (Helmholtz resonator)
            - Use when back stiffness >> top stiffness (laminate, archtop)
            - Closed-form eigenvalue solution

        3-Oscillator (active back):
            - Top plate + Back plate + Air cavity
            - Use for traditional flat-top guitars
            - Numerical eigenvalue solution

Modules:
    thickness_calculator: Orthotropic plate solver + 3-oscillator model
    coupled_2osc: 2-oscillator model for rigid back designs
    calibration: Body style calibration tables
"""

from .thickness_calculator import (
    plate_modal_frequency,
    thickness_for_target_frequency,
    helmholtz_frequency,
    chladni_to_box_frequency,
    box_to_chladni_frequency,
    coupled_eigenfrequencies,
    PlateThicknessResult,
    CoupledSystemResult,
    analyze_plate,
    analyze_coupled_system,
)

from .coupled_2osc import (
    coupled_2osc_eigenfrequencies,
    back_activity_ratio,
    minimum_back_thickness_for_rigid,
    Coupled2OscResult,
    analyze_coupled_2osc,
    format_2osc_report,
)

from .calibration import (
    BodyStyle,
    get_body_calibration,
    list_body_styles,
    MaterialPreset,
    get_material_preset,
    list_materials,
)

__all__ = [
    # Core functions
    "plate_modal_frequency",
    "thickness_for_target_frequency",
    "helmholtz_frequency",
    "chladni_to_box_frequency",
    "box_to_chladni_frequency",
    "coupled_eigenfrequencies",
    # 2-oscillator model
    "coupled_2osc_eigenfrequencies",
    "back_activity_ratio",
    "minimum_back_thickness_for_rigid",
    "Coupled2OscResult",
    "analyze_coupled_2osc",
    "format_2osc_report",
    # Result classes
    "PlateThicknessResult",
    "CoupledSystemResult",
    # Analysis functions
    "analyze_plate",
    "analyze_coupled_system",
    # Calibration
    "BodyStyle",
    "get_body_calibration",
    "list_body_styles",
    "MaterialPreset",
    "get_material_preset",
    "list_materials",
]
