"""
Wood property estimation from acoustic measurements.

This module provides functions to estimate mechanical properties of wood
from tap tone measurements, including:
- Density estimation
- Stiffness (Young's modulus)
- Sound radiation coefficient
- Quality grading

References:
- Gore & Gilet, "Contemporary Acoustic Guitar Design and Build"
- Haines, "The essential mechanical properties of wood prepared for
  musical instruments" (Catgut Acoustical Society Journal)
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import numpy as np


@dataclass
class WoodDimensions:
    """Specimen dimensions in mm."""

    length: float
    width: float
    thickness: float

    @property
    def volume_m3(self) -> float:
        """Volume in cubic meters."""
        return (self.length / 1000) * (self.width / 1000) * (self.thickness / 1000)


@dataclass
class WoodProperties:
    """Estimated wood properties."""

    density_kg_m3: float
    stiffness_along_gpa: float  # Young's modulus along grain
    stiffness_cross_gpa: Optional[float]  # Young's modulus across grain
    radiation_coefficient: float  # sqrt(E/ρ) / 1000
    damping_factor: Optional[float]  # Loss factor / internal friction
    quality_grade: str  # A, B, C, D based on radiation coefficient
    fundamental_hz: float
    confidence: float  # 0-1, how confident we are in estimates

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "density_kg_m3": round(self.density_kg_m3, 1),
            "stiffness_along_gpa": round(self.stiffness_along_gpa, 2),
            "stiffness_cross_gpa": round(self.stiffness_cross_gpa, 2)
            if self.stiffness_cross_gpa
            else None,
            "radiation_coefficient": round(self.radiation_coefficient, 2),
            "damping_factor": round(self.damping_factor, 4)
            if self.damping_factor
            else None,
            "quality_grade": self.quality_grade,
            "fundamental_hz": round(self.fundamental_hz, 1),
            "confidence": round(self.confidence, 2),
        }


# Reference values for common tonewoods
TONEWOOD_REFERENCES = {
    "sitka_spruce": {
        "density_range": (380, 450),
        "stiffness_range": (10, 14),
        "radiation_range": (11, 15),
        "description": "Standard soundboard wood, bright tone",
    },
    "engelmann_spruce": {
        "density_range": (350, 420),
        "stiffness_range": (9, 12),
        "radiation_range": (12, 16),
        "description": "Lighter than Sitka, warm tone",
    },
    "western_red_cedar": {
        "density_range": (320, 380),
        "stiffness_range": (6, 9),
        "radiation_range": (10, 13),
        "description": "Warm, complex overtones",
    },
    "european_spruce": {
        "density_range": (400, 480),
        "stiffness_range": (11, 16),
        "radiation_range": (12, 16),
        "description": "Traditional choice, balanced tone",
    },
    "redwood": {
        "density_range": (340, 420),
        "stiffness_range": (7, 10),
        "radiation_range": (10, 13),
        "description": "Warm, cedar-like character",
    },
    "indian_rosewood": {
        "density_range": (800, 950),
        "stiffness_range": (11, 15),
        "radiation_range": (3.5, 4.5),
        "description": "Dense back/side wood, rich lows",
    },
    "mahogany": {
        "density_range": (500, 650),
        "stiffness_range": (8, 12),
        "radiation_range": (4, 6),
        "description": "Warm, punchy midrange",
    },
}


def estimate_density(weight_g: float, dimensions: WoodDimensions) -> float:
    """
    Calculate density from weight and dimensions.

    Args:
        weight_g: Weight in grams
        dimensions: Specimen dimensions

    Returns:
        Density in kg/m³
    """
    weight_kg = weight_g / 1000
    volume_m3 = dimensions.volume_m3

    if volume_m3 <= 0:
        raise ValueError("Invalid dimensions - volume must be positive")

    return weight_kg / volume_m3


def estimate_stiffness_from_frequency(
    fundamental_hz: float,
    dimensions: WoodDimensions,
    density_kg_m3: float,
    boundary_condition: str = "free_free",
) -> float:
    """
    Estimate Young's modulus from fundamental frequency.

    Uses beam vibration theory. For a free-free beam:
    f_n = (λ_n² / 2π) * sqrt(E * I / (ρ * A * L⁴))

    Where λ₁ = 4.730 for first mode of free-free beam.

    Args:
        fundamental_hz: Fundamental frequency in Hz
        dimensions: Specimen dimensions (length along grain)
        density_kg_m3: Density in kg/m³
        boundary_condition: "free_free", "cantilever", or "simply_supported"

    Returns:
        Young's modulus in GPa
    """
    length_m = dimensions.length / 1000
    thickness_m = dimensions.thickness / 1000
    width_m = dimensions.width / 1000

    # Eigenvalue for boundary condition
    if boundary_condition == "free_free":
        lambda_n = 4.730  # First mode
    elif boundary_condition == "cantilever":
        lambda_n = 1.875
    elif boundary_condition == "simply_supported":
        lambda_n = np.pi
    else:
        lambda_n = 4.730

    # Moment of inertia for rectangular cross-section
    moment_I = (width_m * thickness_m**3) / 12

    # Cross-sectional area
    A = width_m * thickness_m

    # Solve for E:
    # f = (λ² / 2πL²) * sqrt(E * I / (ρ * A))
    # E = (f * 2π * L² / λ²)² * (ρ * A / I)

    omega = 2 * np.pi * fundamental_hz
    E = (omega * length_m**2 / lambda_n**2) ** 2 * (density_kg_m3 * A / I)

    return E / 1e9  # Convert to GPa


def calculate_radiation_coefficient(
    stiffness_gpa: float, density_kg_m3: float
) -> float:
    """
    Calculate sound radiation coefficient.

    R = sqrt(E / ρ) / 1000

    Higher values indicate better sound projection.
    Typical values:
    - Excellent soundboard: > 14
    - Good soundboard: 11-14
    - Average: 8-11
    - Below average: < 8

    Args:
        stiffness_gpa: Young's modulus in GPa
        density_kg_m3: Density in kg/m³

    Returns:
        Radiation coefficient (dimensionless)
    """
    stiffness_pa = stiffness_gpa * 1e9
    return np.sqrt(stiffness_pa / density_kg_m3) / 1000


def estimate_damping_from_peaks(
    peaks: List[Dict[str, float]], freq_hz: np.ndarray, magnitude: np.ndarray
) -> Optional[float]:
    """
    Estimate damping factor from peak bandwidth.

    Uses Q factor: Q = f₀ / Δf (3dB bandwidth)
    Damping η = 1 / (2Q)

    Args:
        peaks: List of detected peaks
        freq_hz: Frequency array
        magnitude: Magnitude array

    Returns:
        Average damping factor, or None if cannot estimate
    """
    if not peaks or len(peaks) < 1:
        return None

    q_factors = []

    for peak in peaks:
        peak_freq = peak.get("freq_hz", 0)
        peak_mag = peak.get("magnitude", 0)

        if peak_freq <= 0 or peak_mag <= 0:
            continue

        # Find -3dB points (half power)
        half_power = peak_mag / np.sqrt(2)

        # Find peak index
        peak_idx = np.argmin(np.abs(freq_hz - peak_freq))

        # Search for bandwidth
        left_idx = peak_idx
        while left_idx > 0 and magnitude[left_idx] > half_power:
            left_idx -= 1

        right_idx = peak_idx
        while right_idx < len(magnitude) - 1 and magnitude[right_idx] > half_power:
            right_idx += 1

        bandwidth = freq_hz[right_idx] - freq_hz[left_idx]

        if bandwidth > 0:
            q = peak_freq / bandwidth
            if 5 < q < 500:  # Reasonable Q range
                q_factors.append(q)

    if not q_factors:
        return None

    avg_q = np.mean(q_factors)
    damping = 1 / (2 * avg_q)

    return float(damping)


def grade_wood_quality(radiation_coefficient: float) -> str:
    """
    Assign quality grade based on radiation coefficient.

    Args:
        radiation_coefficient: Calculated radiation coefficient

    Returns:
        Grade string: "AAA", "AA", "A", "B", "C", "D"
    """
    if radiation_coefficient >= 15:
        return "AAA"
    elif radiation_coefficient >= 13:
        return "AA"
    elif radiation_coefficient >= 11:
        return "A"
    elif radiation_coefficient >= 9:
        return "B"
    elif radiation_coefficient >= 7:
        return "C"
    else:
        return "D"


def identify_wood_species(properties: WoodProperties) -> List[Tuple[str, float]]:
    """
    Suggest possible wood species based on measured properties.

    Args:
        properties: Estimated wood properties

    Returns:
        List of (species_name, match_score) tuples, sorted by score
    """
    matches = []

    for species, ref in TONEWOOD_REFERENCES.items():
        score = 0.0
        factors = 0

        # Check density
        d_min, d_max = ref["density_range"]
        if d_min <= properties.density_kg_m3 <= d_max:
            score += 1.0
        elif properties.density_kg_m3 < d_min:
            score += max(0, 1 - (d_min - properties.density_kg_m3) / 100)
        else:
            score += max(0, 1 - (properties.density_kg_m3 - d_max) / 100)
        factors += 1

        # Check stiffness
        e_min, e_max = ref["stiffness_range"]
        if e_min <= properties.stiffness_along_gpa <= e_max:
            score += 1.0
        elif properties.stiffness_along_gpa < e_min:
            score += max(0, 1 - (e_min - properties.stiffness_along_gpa) / 3)
        else:
            score += max(0, 1 - (properties.stiffness_along_gpa - e_max) / 3)
        factors += 1

        # Check radiation coefficient
        r_min, r_max = ref["radiation_range"]
        if r_min <= properties.radiation_coefficient <= r_max:
            score += 1.0
        elif properties.radiation_coefficient < r_min:
            score += max(0, 1 - (r_min - properties.radiation_coefficient) / 3)
        else:
            score += max(0, 1 - (properties.radiation_coefficient - r_max) / 3)
        factors += 1

        # Normalize score
        match_score = score / factors if factors > 0 else 0
        matches.append((species, match_score))

    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)

    return matches


def estimate_wood_properties(
    fundamental_hz: float,
    dimensions: WoodDimensions,
    weight_g: Optional[float] = None,
    density_kg_m3: Optional[float] = None,
    peaks: Optional[List[Dict[str, float]]] = None,
    freq_hz: Optional[np.ndarray] = None,
    magnitude: Optional[np.ndarray] = None,
    coherence_quality: float = 0.9,
) -> WoodProperties:
    """
    Estimate wood properties from acoustic measurements.

    Args:
        fundamental_hz: Fundamental frequency
        dimensions: Specimen dimensions
        weight_g: Weight in grams (if known)
        density_kg_m3: Density in kg/m³ (if known, overrides weight)
        peaks: Detected peaks (for damping estimation)
        freq_hz: Frequency array (for damping estimation)
        magnitude: Magnitude array (for damping estimation)
        coherence_quality: Average coherence (affects confidence)

    Returns:
        WoodProperties dataclass with estimates
    """
    # Estimate or use provided density
    if density_kg_m3 is not None:
        density = density_kg_m3
    elif weight_g is not None:
        density = estimate_density(weight_g, dimensions)
    else:
        # Assume typical soundboard density
        density = 420.0

    # Estimate stiffness
    stiffness = estimate_stiffness_from_frequency(fundamental_hz, dimensions, density)

    # Calculate radiation coefficient
    radiation = calculate_radiation_coefficient(stiffness, density)

    # Estimate damping if we have the data
    damping = None
    if peaks and freq_hz is not None and magnitude is not None:
        damping = estimate_damping_from_peaks(peaks, freq_hz, magnitude)

    # Assign grade
    grade = grade_wood_quality(radiation)

    # Calculate confidence based on data quality
    confidence = coherence_quality * 0.7  # Base confidence from coherence
    if weight_g is not None:
        confidence += 0.15  # Bonus for known weight
    if peaks and len(peaks) >= 3:
        confidence += 0.15  # Bonus for good peak detection
    confidence = min(confidence, 1.0)

    return WoodProperties(
        density_kg_m3=density,
        stiffness_along_gpa=stiffness,
        stiffness_cross_gpa=None,  # Would need cross-grain measurement
        radiation_coefficient=radiation,
        damping_factor=damping,
        quality_grade=grade,
        fundamental_hz=fundamental_hz,
        confidence=confidence,
    )
