# Feature Gap: Per-Point Thickness/Density Tracking

**Noted:** 2026-02-28  
**Status:** Proposed Enhancement (P3)  
**Related:** ADR-0004 (Acoustic vs Structural Boundary)

---

## Problem Statement

During plate tuning, a builder iteratively thins the wood and takes measurements at each step:

1. **Mass** (weight on scale) — changes as material removed
2. **Frequency** (tap tone) — rises as mass decreases
3. **Deflection** (3-point bending) — changes as thickness decreases
4. **Thickness** — decreases at each thinning step

The current `TuningPoint` dataclass captures mass, frequency, and deflection but **not thickness**:

```python
@dataclass
class TuningPoint:
    mass_g: float                      # Tracked
    freq_hz: float                     # Tracked
    deflection_x_mm: Optional[float]   # Tracked
    deflection_y_mm: Optional[float]   # Tracked
    thickness_mm: ???                  # NOT TRACKED
```

---

## Impact

Without per-point thickness tracking:

- **Density cannot be auto-calculated** at each step
- **Stiffness (E) estimation is impaired** — Euler-Bernoulli requires thickness
- **Regression is mass-only** — misses the thickness-to-stiffness relationship

---

## Physics Context

### Density Calculation

Density calculation requires volume:

```
ρ = m / V = m / (L × W × h)
```

Where `h` (thickness) changes at each thinning iteration. Currently, `WoodDimensions` is separate from `TuningPoint`, so the system assumes constant dimensions.

### Young's Modulus from Deflection

```
E = F × L³ / (4 × b × h³ × δ)
```

The `h³` term means small thickness changes have **cubic** impact on stiffness calculation.

---

## Proposed Enhancement

Add optional `thickness_mm` field to `TuningPoint`:

```python
@dataclass
class TuningPoint:
    mass_g: float
    freq_hz: float
    thickness_mm: Optional[float] = None      # ← NEW
    deflection_x_mm: Optional[float] = None
    deflection_y_mm: Optional[float] = None
    timestamp: str = field(default_factory=...)
    notes: str = ""
```

### UI Table (5 columns)

| Mass (g) | Freq (Hz) | Thick (mm) | Defl X (mm) | Defl Y (mm) |
|----------|-----------|------------|-------------|-------------|
| 145.0    | 98.5      | 3.2        | 2.1         | 1.8         |
| 138.0    | 92.0      | 3.0        | 2.3         | 1.9         |
| 132.0    | 88.5      | 2.8        | 2.5         | 2.1         |

---

## Derived Calculations (with thickness)

With per-point thickness, the system could compute:

1. **Per-point density**: `ρᵢ = massᵢ / (L × W × thicknessᵢ)`
2. **Per-point stiffness**: `Eᵢ = f(freqᵢ, thicknessᵢ, ρᵢ)`
3. **Density trajectory**: How density changes as plate is thinned (useful for detecting moisture changes)
4. **Stiffness trajectory**: E vs thickness curve

---

## Backward Compatibility

- `thickness_mm` is optional (default `None`)
- Existing saved sessions load without error
- UI shows column only if user enables "advanced mode" or enters a value

---

## Files Affected

| File | Change |
|------|--------|
| `analyzer/analysis/plate_tuning.py` | Add `thickness_mm` to `TuningPoint`, update `to_dict`/`from_dict` |
| `analyzer/widgets/plate_tuning.py` | Add 5th column to table, update `_sync_from_table` |
| `analyzer/analysis/wood_properties.py` | Add `estimate_properties_with_thickness()` variant |

---

## Related Code

- `analyzer/analysis/wood_properties.py:114` — `estimate_density()` function
- `tap_tone_pi/tonewood_deflection.py` — standalone CLI uses thickness
- ADR-0004: Acoustic vs Structural Boundary

---

## Priority

**P3 (Enhancement)** — This is a workflow enhancement, not a bug. Current system works for mass-to-frequency regression. Thickness tracking would enable richer analysis.
