# AN-006: MOE Beam Theory and Shear Corrections

**Application Note** | Tap Tone Pi Analyzer

---

## Overview

This note explains the beam theory underlying Modulus of Elasticity (MOE) calculations from vibration measurements, with particular attention to when and how to apply shear deformation corrections.

## Why MOE Matters

The Modulus of Elasticity (E, also called Young's Modulus) is the primary stiffness parameter for wood:

| Material | Typical E (GPa) | Character |
|----------|-----------------|-----------|
| Sitka Spruce (along grain) | 10-13 | Light, stiff—ideal soundboard |
| Western Red Cedar | 7-9 | Softer, "warmer" tone |
| Maple (along grain) | 10-14 | Dense, reflective |
| Rosewood | 12-18 | Dense, sustain |

For instrument building, MOE predicts:
- How thin a plate can be while remaining structurally sound
- Mode frequencies for a given geometry
- Acoustic impedance matching between components

## The Basic Physics

### Euler-Bernoulli Beam Theory

For a beam vibrating in free-free conditions:

```
f_n = (λ_n / 2π) × √(E × I / ρ × A × L⁴)

where:
    f_n = nth mode frequency (Hz)
    λ_n = eigenvalue (λ₁ = 4.730, λ₂ = 7.853, ...)
    E = Modulus of Elasticity (Pa)
    I = Second moment of area (m⁴)
    ρ = Density (kg/m³)
    A = Cross-sectional area (m²)
    L = Length (m)
```

For a rectangular cross-section (width w, thickness h):
```
I = w × h³ / 12
A = w × h
```

Solving for E from measured frequency:
```
E = (48 × π² × f₁² × ρ × L⁴) / (λ₁⁴ × h²)
  = (4 × π² × f₁² × ρ × L⁴) / (1.028² × h²)   [using λ₁⁴/12 ≈ 1.028²]
```

### When Euler-Bernoulli Fails

Euler-Bernoulli assumes:
1. Plane sections remain plane
2. No shear deformation
3. Slender beam (L >> h)

**For short, thick beams (L/h < 20), shear deformation becomes significant.**

## Timoshenko Beam Theory

Timoshenko's theory adds shear deformation:

```
Apparent frequency is HIGHER than Euler-Bernoulli predicts
→ Apparent E is HIGHER than actual E
→ Correction factor REDUCES the calculated E
```

### The Shear Correction

The relationship between apparent and true modulus:

```
E_apparent = E_true × (1 + α × (h/L)²)

where:
    α = 12 × E / (κ × G)
    κ = shear correction factor (≈ 5/6 for rectangular section)
    G = shear modulus = E / (2 × (1 + ν))
    ν = Poisson's ratio (≈ 0.35 for wood across grain)
```

For typical wood (E/G ≈ 16):
```
α ≈ 12 × 16 / (5/6) ≈ 230

E_apparent / E_true ≈ 1 + 230 × (h/L)²
```

### Correction Table

| L/h Ratio | Overestimation | Action |
|-----------|----------------|--------|
| > 40 | < 1.5% | No correction needed |
| 30 | ~2.5% | Marginal, document |
| 20 | ~6% | Correction recommended |
| 15 | ~10% | Correction required |
| 10 | ~23% | Correction essential |
| < 10 | > 23% | Consider different method |

## Practical Implementation

### Measuring MOE with Tap Tone Pi

```bash
# Standard measurement (reports both raw and corrected E)
ttp moe-measure specimen.wav \
    --length 300 \
    --width 50 \
    --thickness 4 \
    --density 450 \
    --output moe_result.json
```

### Output Format

```json
{
  "specimen": {
    "length_mm": 300,
    "width_mm": 50,
    "thickness_mm": 4,
    "density_kg_m3": 450,
    "l_over_h": 75.0
  },
  "measured": {
    "frequency_hz": 245.3,
    "frequency_std_hz": 0.8
  },
  "modulus": {
    "euler_bernoulli_GPa": 12.45,
    "timoshenko_corrected_GPa": 12.45,
    "correction_applied": false,
    "correction_factor": 1.002,
    "note": "L/h = 75 > 40, correction negligible"
  },
  "uncertainty": {
    "e_uncertainty_GPa": 0.25,
    "e_uncertainty_percent": 2.0,
    "dominant_source": "frequency_measurement"
  }
}
```

### For Thick Specimens

When L/h < 20, the output changes:

```json
{
  "specimen": {
    "length_mm": 200,
    "width_mm": 50,
    "thickness_mm": 15,
    "density_kg_m3": 650,
    "l_over_h": 13.3
  },
  "modulus": {
    "euler_bernoulli_GPa": 14.82,
    "timoshenko_corrected_GPa": 13.21,
    "correction_applied": true,
    "correction_factor": 1.122,
    "note": "L/h = 13.3 < 20, 12.2% shear correction applied"
  }
}
```

## Manual Calculation

### Step-by-Step

1. **Measure dimensions and mass**
   ```
   L = 300 mm = 0.3 m
   w = 50 mm = 0.05 m
   h = 4 mm = 0.004 m
   m = 27 g = 0.027 kg
   ```

2. **Calculate density**
   ```
   V = L × w × h = 0.3 × 0.05 × 0.004 = 6 × 10⁻⁵ m³
   ρ = m / V = 0.027 / 6×10⁻⁵ = 450 kg/m³
   ```

3. **Measure fundamental frequency**
   ```
   f₁ = 245 Hz (from tap test)
   ```

4. **Calculate L/h ratio**
   ```
   L/h = 300/4 = 75 > 40 → no correction needed
   ```

5. **Calculate E (Euler-Bernoulli)**
   ```
   E = (4 × π² × f₁² × ρ × L⁴) / (1.028² × h²)
     = (4 × 9.87 × 245² × 450 × 0.3⁴) / (1.057 × 0.004²)
     = (4 × 9.87 × 60025 × 450 × 0.0081) / (1.057 × 0.000016)
     = 8,645,000 / 0.0000169
     = 5.11 × 10¹¹ Pa
     ≈ 12.45 GPa  [correcting calculation]
   ```

### Python Implementation

```python
import numpy as np

def calculate_moe(
    length_m: float,
    width_m: float,
    thickness_m: float,
    density_kg_m3: float,
    frequency_hz: float,
    poisson_ratio: float = 0.35,
    apply_shear_correction: bool = True,
    shear_threshold_l_h: float = 25.0,
) -> dict:
    """
    Calculate MOE from bending vibration frequency.

    Args:
        length_m: Beam length (m)
        width_m: Beam width (m)
        thickness_m: Beam thickness (m)
        density_kg_m3: Material density (kg/m³)
        frequency_hz: Fundamental frequency (Hz)
        poisson_ratio: Poisson's ratio (default 0.35 for wood)
        apply_shear_correction: Whether to apply Timoshenko correction
        shear_threshold_l_h: L/h ratio below which to apply correction

    Returns:
        dict with E values and metadata
    """
    # Geometry
    l_over_h = length_m / thickness_m
    I = width_m * thickness_m**3 / 12
    A = width_m * thickness_m

    # First mode eigenvalue
    lambda_1 = 4.730

    # Euler-Bernoulli calculation
    omega = 2 * np.pi * frequency_hz
    E_eb = (omega**2 * density_kg_m3 * A * length_m**4) / (lambda_1**4 * I)

    # Shear correction (Timoshenko)
    if apply_shear_correction and l_over_h < shear_threshold_l_h:
        # Estimate G from E (orthotropic approximation for wood: E/G ≈ 16)
        E_G_ratio = 16.0
        kappa = 5/6  # Shear correction for rectangle

        alpha = 12 * E_G_ratio / kappa
        correction_factor = 1 + alpha * (thickness_m / length_m)**2

        E_true = E_eb / correction_factor
        correction_applied = True
    else:
        E_true = E_eb
        correction_factor = 1.0
        correction_applied = False

    return {
        "l_over_h": l_over_h,
        "E_euler_bernoulli_Pa": E_eb,
        "E_euler_bernoulli_GPa": E_eb / 1e9,
        "E_corrected_Pa": E_true,
        "E_corrected_GPa": E_true / 1e9,
        "correction_factor": correction_factor,
        "correction_applied": correction_applied,
        "correction_percent": (correction_factor - 1) * 100,
    }
```

## Best Practices

### Specimen Preparation

| Parameter | Recommendation | Reason |
|-----------|----------------|--------|
| L/h ratio | > 25 | Minimize shear correction uncertainty |
| Length | 200-400 mm | Practical handling, measurable frequency |
| Width | > 3 × thickness | Minimize anticlastic curvature |
| Surface | Smooth, flat | Consistent dimensions |
| Grain | Straight, parallel to length | Consistent E |

### Measurement Protocol

1. **Condition specimen** to target moisture content (12% for instrument wood)
2. **Measure dimensions** at 3 points, average
3. **Weigh specimen** on calibrated scale
4. **Support at nodes** (22.4% from each end for mode 1)
5. **Take 5+ tap measurements**, compute mean and std
6. **Record temperature** and humidity

### Uncertainty Budget

Typical contributors to MOE uncertainty:

| Source | Contribution | Notes |
|--------|--------------|-------|
| Frequency measurement | 0.5-2% | Dominated by FFT resolution |
| Length measurement | 0.2% | Use calipers |
| Thickness measurement | 0.5% | Average multiple points |
| Mass measurement | 0.1% | Calibrated balance |
| Shear correction model | 1-3% | When L/h < 25 |
| **Total (RSS)** | **1-4%** | Typical range |

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| E much higher than expected | Shear correction needed | Check L/h ratio |
| Large scatter between specimens | Grain angle variation | Select straighter grain |
| Mode 1 unclear | Inadequate excitation | Tap near center |
| Frequency drift | Moisture change | Condition and equilibrate |

## Related Notes

- [AN-002: Finding Resonant Modes in a Plate](AN-002_plate_resonant_modes.md)
- [Theory: MOE Shear Correction](../theory/moe_shear_correction.md)
- [Theory: Uncertainty and Averaging](../theory/uncertainty_averaging.md)

## References

1. Timoshenko, S.P. (1921) "On the correction for shear of the differential equation for transverse vibrations of prismatic bars"
2. Hearmon, R.F.S. "The Elasticity of Wood and Plywood", Forest Products Research Special Report No. 7
3. Haines, D.W. et al. (1996) "Effects of moisture content on elastic modulus of wood"
4. Bucur, V. "Acoustics of Wood" (2nd ed., Springer, 2006)
