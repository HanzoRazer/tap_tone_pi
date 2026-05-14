# Feature Gap: Deflection Profile with Manual Entry

**Noted:** 2026-02-28
**Updated:** 2026-02-28
**Status:** Proposed Enhancement (P3)
**Related:** ADR-0004 (Acoustic vs Structural Boundary)

---

## Problem Statement

During plate tuning, a builder iteratively thins the wood and takes measurements at each step:

1. **Mass** (weight on scale) — changes as material removed
2. **Frequency** (tap tone) — rises as mass decreases
3. **Deflection** (multi-point readings) — varies by location on the panel
4. **Thickness** — decreases at each thinning step

The current `TuningPoint` dataclass captures mass, frequency, and deflection but **not thickness** or **location**.

---

## Practical Workflow

The simplest solution is **manual entry of deflection profile data**:

1. **Known dimensions** — panel design provides L × W and starting thickness
2. **Multi-point deflection readings** — measure at various locations on top/back panels
3. **Mass delta tracking** — weigh panel before/after each thinning pass
4. **Manual entry** — simple table input, no complex automation needed

The builder knows the design and critical dimensions. They take readings from various areas, note mass changes between sessions, and enter values by hand.

---

## Proposed Data Model

### Deflection Reading (per location, per session)

```python
@dataclass
class DeflectionReading:
    location: str                      # e.g., "center", "lower_bout", "upper_bout"
    thickness_mm: float                # measured at this location
    deflection_mm: float               # deflection under load
    notes: str = ""
```

### Tuning Session (one thinning pass)

```python
@dataclass
class TuningSession:
    timestamp: str
    mass_g: float                      # panel mass (constant across locations)
    freq_hz: Optional[float] = None    # tap tone (if measured)
    readings: list[DeflectionReading] = field(default_factory=list)
```

---

## UI Table (Manual Entry)

### Session View (after one thinning pass)

**Panel Mass: 145.0 g** | **Tap Freq: 98.5 Hz**

| Location    | Thickness (mm) | Deflection (mm) | Notes       |
|-------------|----------------|-----------------|-------------|
| center      | 3.2            | 2.1             |             |
| lower bout  | 3.2            | 1.8             | near bridge |
| upper bout  | 3.4            | 2.4             | thicker     |
| waist L     | 3.1            | 2.0             |             |
| waist R     | 3.1            | 1.9             |             |

### History View (across thinning passes)

| Session | Mass (g) | Freq (Hz) | Avg Thick (mm) | Center Defl (mm) |
|---------|----------|-----------|----------------|------------------|
| 1       | 145.0    | 98.5      | 3.2            | 2.1              |
| 2       | 138.0    | 92.0      | 3.0            | 2.3              |
| 3       | 132.0    | 88.5      | 2.8            | 2.5              |

---

## Physics Context

### Density Calculation

With known dimensions and measured thickness:

```
ρ = m / V = m / (L × W × h_avg)
```

### Young's Modulus from Deflection

```
E = F × L³ / (4 × b × h³ × δ)
```

The `h³` term means small thickness changes have **cubic** impact on stiffness. Per-location thickness allows accurate local stiffness estimation.

---

## Derived Calculations (computed after manual entry)

With per-location thickness and deflection, the system can compute:

1. **Per-location stiffness**: `Eᵢ = f(thicknessᵢ, deflectionᵢ, load)`
2. **Stiffness map**: variation across the panel
3. **Per-session density**: `ρ = mass / (L × W × avg_thickness)`
4. **Trajectory plots**: mass, frequency, stiffness vs. session number

These are derived from manually entered data — no sensors required.

---

## Backward Compatibility

- New fields are optional (default `None` or empty list)
- Existing saved sessions load without error
- Simple mode: mass + frequency only (current behavior)
- Advanced mode: full deflection profile

---

## Files Affected

| File | Change |
|------|--------|
| `tap_tone_pi/tuning/models.py` | Add `DeflectionReading`, `TuningSession` dataclasses |
| `tap_tone_pi/tuning/profile_entry.py` | New: manual entry UI/CLI for deflection profile |
| `tap_tone_pi/tuning/analysis.py` | Stiffness calculation from profile data |
| `analyzer/widgets/plate_tuning.py` | Optional: GUI table for profile entry |

---

## Related Code

- `analyzer/analysis/wood_properties.py:114` — `estimate_density()` function
- `tap_tone_pi/tonewood_deflection.py` — standalone CLI uses thickness
- ADR-0004: Acoustic vs Structural Boundary

---

## Priority

**P3 (Enhancement)** — This is a workflow enhancement, not a bug. Current system works for mass-to-frequency regression. Deflection profile tracking enables richer stiffness analysis with simple manual entry.
