# Cross-Grain Elastic Modulus (E_C) Estimation Procedure

**Document ID:** `PROC-CROSS-GRAIN-001`
**Status:** Draft
**Author:** tap_tone_pi
**Last Updated:** 2026-03-28

---

## Purpose

When a cross-grain test strip is unavailable (e.g., the plate blank is too narrow, or offcuts have been discarded), the cross-grain elastic modulus E_C can be estimated from:

1. The measured along-grain modulus E_L (from bending test)
2. The measured plate modal frequencies (from Phase 1 tap tone)
3. Known plate geometry

This procedure documents the back-calculation method.

---

## Prerequisites

Before using this procedure, you must have:

1. **Measured E_L** from a along-grain bending test (3-point or 4-point)
2. **Measured modal frequencies** from Phase 1 tap tone capture
3. **Plate dimensions**: length (a), width (b), thickness (h)
4. **Plate density** (ρ) — measured or estimated from species

---

## Theory

For a free orthotropic plate, the fundamental modes depend on the elastic constants D_L and D_C (flexural rigidities):

```
D_L = E_L * h³ / [12 * (1 - ν_LT * ν_TL)]
D_C = E_C * h³ / [12 * (1 - ν_LT * ν_TL)]
```

Where:
- h = plate thickness
- ν_LT, ν_TL = Poisson's ratios (typically ~0.3 for wood)

The modal frequencies follow (for simplified rectangular free plate):

```
f_mn = (π/2) * sqrt(D / (ρ * h)) * [(m/a)² + (n/b)²]
```

For the first few modes of a guitar top (approximately):
- Mode 1 (0,0): "ring" mode — depends primarily on average stiffness
- Mode 2 (1,0): "cross" mode — dominated by E_C
- Mode 5 (0,2): "long dipole" — dominated by E_L

---

## Estimation Procedure

### Step 1: Identify the Cross Mode

From your Phase 1 tap tone data, identify the mode that primarily involves bending across the grain. For a guitar top, this is typically the second or third mode, around 100-150 Hz for a typical spruce top.

Visual identification:
- If you have Chladni pattern data, look for a single nodal line running parallel to the grain
- Without visual data, it's typically the lowest frequency mode above the ring mode

### Step 2: Use the Frequency Ratio

The ratio of cross-mode to ring-mode frequency encodes the orthotropic ratio:

```
f_cross / f_ring ≈ sqrt(E_C / E_avg)
```

Where E_avg ≈ sqrt(E_L * E_C) for the ring mode.

Rearranging:

```
E_C ≈ (f_cross / f_ring)² * E_L * (f_cross / f_long)
```

### Step 3: Apply Correction Factors

The simplified formula above ignores:
- Shear modulus G_LT (typically ~600-900 MPa for spruce)
- Poisson coupling
- Non-rectangular plate shape

For typical guitar top dimensions (500×380×3 mm), apply a correction factor of ~0.85:

```
E_C_corrected = 0.85 * E_C_raw
```

### Step 4: Sanity Check

Verify the result against expected values:

| Species | Typical E_L (GPa) | Typical E_C (GPa) | Typical E_L/E_C |
|---------|-------------------|-------------------|-----------------|
| Sitka spruce | 9-12 | 0.6-0.9 | 12-16 |
| Engelmann spruce | 8-11 | 0.5-0.8 | 12-18 |
| Red cedar | 6-9 | 0.4-0.7 | 12-16 |
| European spruce | 10-14 | 0.7-1.0 | 12-16 |

If your calculated E_L/E_C ratio is:
- **< 8:1** — Suspect measurement error or low-quality wood
- **8-18:1** — Normal range for acoustic tonewood
- **> 20:1** — Exceptional wood or measurement error

---

## Implementation

The `tap_tone_pi` toolchain provides a helper function for this calculation:

```python
from tap_tone_pi.materials.estimation import estimate_E_C_from_modes

E_C_est = estimate_E_C_from_modes(
    E_L_GPa=10.5,
    f_ring_hz=98.0,
    f_cross_hz=145.0,
    f_long_hz=210.0,
    thickness_mm=3.0,
    length_mm=500.0,
    width_mm=380.0,
)

print(f"Estimated E_C: {E_C_est:.2f} GPa")
```

**Note:** This function is planned for v2.4.0. For v2.3.0, use manual calculation.

---

## Uncertainty

Estimated E_C carries higher uncertainty than measured E_C:

| Method | Typical Uncertainty |
|--------|---------------------|
| Direct bending test | ±5% |
| Modal back-calculation | ±15-25% |

When using estimated E_C in the inverse brace engine:
1. Document that the value is estimated, not measured
2. Apply wider uncertainty bounds in optimization constraints
3. Consider running sensitivity analysis with E_C ± 20%

---

## Recording in Viewer Pack

When E_C is estimated rather than measured, record it in the bending section with a source indicator:

```json
{
  "bending": {
    "E_L_GPa": 10.5,
    "E_C_GPa": 0.72,
    "E_C_method": "estimated_from_modes",
    "E_C_uncertainty_pct": 20,
    "source_bundle": "phase1_session/modal_analysis.json"
  }
}
```

---

## References

1. Caldersmith, G. (1984). "Vibration geometry and radiation fields of guitars." *JASA*.
2. Fletcher, N. H., & Rossing, T. D. (1998). *The Physics of Musical Instruments*. Springer.
3. Gore, T., & Gilet, G. (2011). *Contemporary Acoustic Guitar Design and Build*. Trevor Gore.

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-28 | Claude | Initial draft |
