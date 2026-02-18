"""
tap_tone_pi.design — Plate thickness design and coupled-system analysis.

This module provides tools for determining optimal plate thickness when both
top and back are acoustically active, using orthotropic plate theory and
coupled oscillator models.

Core Concepts:
    Orthotropic Plate:
        - E_L: Longitudinal (long-grain) modulus — dominates thickness selection
        - E_C: Cross-grain modulus — controls anisotropy and bracing decisions
        - R_anis = E_L/E_C: Orthotropic ratio (typically 10-20 for tonewoods)

    Modal Frequency Scaling:
        - f ∝ h × √(E/ρ)  — thicker or stiffer = higher frequency
        - Stiffness Index: SI = E × h³

    3-Oscillator Coupled Model:
        - Top plate (mass + stiffness)
        - Back plate (mass + stiffness)
        - Air cavity (Helmholtz resonator)
        - Solves eigenvalue problem: det(K - ω²M) = 0

    Chladni-to-Box Mapping:
        - Transfer coefficient γ = √(α/β)
        - Maps free-plate Chladni frequencies to assembled-box modes

Modules:
    thickness_calculator: Orthotropic plate solver + 3-oscillator model
    calibration: Body style calibration tables (η, γ, α, β coefficients)

Usage:
    # Simple thickness calculation
    python -m tap_tone_pi.design.thickness_calculator \\
        --target-freq 86 --material mahogany --body jumbo

    # Full 3-oscillator analysis
    python -m tap_tone_pi.design.thickness_calculator \\
        --mode coupled --body jumbo \\
        --top-EL 12.5 --top-EC 0.8 --top-h 2.8 \\
        --back-EL 10.2 --back-EC 0.65 --back-h 2.9

References:
    - Gore & Gilet, "Contemporary Acoustic Guitar Design and Build"
    - Fletcher & Rossing, "The Physics of Musical Instruments"
    - David Hurd, "Left-Brain Lutherie"
"""

from .thickness_calculator import (
    # Core functions
    thickness_for_target_frequency,
    coupled_eigenfrequencies,
    chladni_to_box_frequency,
    # Result classes
    PlateThicknessResult,
    CoupledSystemResult,
    # Analysis functions
    analyze_plate,
    analyze_coupled_system,
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
    "thickness_for_target_frequency",
    "coupled_eigenfrequencies",
    "chladni_to_box_frequency",
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
