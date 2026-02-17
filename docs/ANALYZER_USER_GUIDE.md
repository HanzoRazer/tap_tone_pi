# Tap Tone Pi Analyzer — User Guide

**Last Updated:** 2026-02-17

A complete guide to measuring wood properties for lutherie applications.

---

## What This Analyzer Measures

### Core Acoustic Measurements

| Measurement | Unit | Description |
|-------------|------|-------------|
| **Frequency** | Hz | Resonant frequencies / mode shapes |
| **Magnitude** | dB (relative) | Amplitude at each frequency |
| **Phase** | degrees | Phase relationship (two-channel) |
| **Coherence** | 0-1 | Signal quality / measurement reliability |
| **RMS Level** | dBFS | Overall signal strength |

### Derived Wood Properties

From acoustic measurements + physical inputs, the analyzer estimates:

| Property | Unit | How It's Derived |
|----------|------|------------------|
| **Density (ρ)** | kg/m³ | weight ÷ volume (manual input) |
| **Stiffness (E)** | GPa | From tap frequency OR deflection test |
| **Damping** | Q-factor | Peak bandwidth analysis |
| **Radiation Coefficient** | √(E/ρ)/1000 | Calculated from stiffness + density |
| **Quality Grade** | AAA–D | Lookup from radiation coefficient |

---

## Two Methods for Measuring Stiffness

This analyzer supports **two complementary methods** for measuring Young's modulus (stiffness). Choose based on your equipment and preference.

### Method 1: Tap Tone (Acoustic)

**Equipment needed:** Microphone + suspension

**How it works:**
1. Suspend specimen on soft supports (free-free boundary condition)
2. Tap with small hammer or fingernail
3. Record decay response
4. FFT extracts fundamental frequency → calculate E

**Formula:**
```
E = (ω × L² / λ²)² × (ρ × A / I)

Where:
  ω = 2πf (angular frequency)
  L = length (m)
  λ = 4.730 (free-free eigenvalue)
  ρ = density (kg/m³)
  A = cross-sectional area (m²)
  I = moment of inertia = b×h³/12 (m⁴)
```

**Pros:**
- Fast (seconds per measurement)
- Also captures damping (Q-factor)
- Mode shape information
- Non-contact

**Cons:**
- Requires proper suspension setup
- Sensitive to ambient noise
- Requires microphone

**Command:**
```bash
ttp capture --auto-trigger
```

---

### Method 2: Deflection (Static Bending)

**Equipment needed:** Knife-edge supports + dial indicator + known weights

**How it works:**
1. Support specimen on two knife edges (known span L)
2. Apply known weight at center
3. Measure deflection with dial indicator
4. Calculate E from force/deflection

**Formula (3-point bending):**
```
E = (F × L³) / (48 × I × δ)

Where:
  F = applied force (N) = mass × 9.81
  L = support span (m)
  I = moment of inertia = b×h³/12 (m⁴)
  δ = deflection at center (m)
  b = width, h = thickness
```

**Formula (4-point bending):**
```
E = (F × a × (3L² - 4a²)) / (24 × I × δ)

Where:
  a = distance from support to load point (m)
```

**Pros:**
- Simple, inexpensive jig (~$30-50)
- No microphone needed
- Industry standard (David Hurd method)
- Works with any wood shape

**Cons:**
- Cold creep (wood continues deflecting under load)
- One measurement at a time
- No damping information
- Requires accurate measurements

**Command (recommended — Gore-style module with multi-point fit):**
```bash
# Multi-point fit (recommended for stability)
python -m tap_tone_pi.tonewood_deflection \
  --span_mm 400 --width_mm 30 --thick_mm 3.0 \
  --loads_N 5 10 15 --defl_mm 0.5 1.0 1.5 \
  --strip_len_mm 450 --strip_mass_g 18.0

# With thickness targeting (Gore method)
python -m tap_tone_pi.tonewood_deflection \
  --span_mm 400 --width_mm 30 --thick_mm 3.0 \
  --loads_N 10 --defl_mm 1.0 \
  --href_mm 2.8 --eref_GPa 12.0

# From CSV (supports two schemas)
python -m tap_tone_pi.tonewood_deflection \
  --csv measurements.csv \
  --span_mm 400 --width_mm 30 --thick_mm 3.0

# JSON output for automation
python -m tap_tone_pi.tonewood_deflection \
  --span_mm 400 --width_mm 30 --thick_mm 3.0 \
  --loads_N 5 10 15 --defl_mm 0.5 1.0 1.5 \
  --json result.json
```

**Legacy command (single-point only):**
```bash
python -m modes.bending_stiffness.deflection_to_moe \
  --method 3point --span 400 --width 20 --thickness 3.0 \
  --force 4.9 --deflection 2.5 --density 0.42
```

---

## Deflection Test Setup

### Equipment List

| Item | Typical Cost | Notes |
|------|--------------|-------|
| Two knife-edge supports | $10-20 | V-blocks, razor blades on blocks |
| Dial indicator (0.01mm) | $15-30 | Or digital caliper with depth gauge |
| Calibration weights | $5-15 | Fishing weights, coins, or lab masses |
| Digital scale (0.1g) | $10-20 | For weighing specimen + weights |
| Flat reference surface | — | Granite plate, thick glass, or flat table |

**Total: ~$40-85** vs. specialized suspension for tap testing

### Step-by-Step Procedure

1. **Measure specimen:**
   - Length (L): along grain, in mm
   - Width (b): across grain, in mm
   - Thickness (h): in mm
   - Weight: in grams

2. **Set up supports:**
   - Place knife edges at known span (e.g., 400mm)
   - Ensure parallel and level

3. **Zero the dial indicator:**
   - Position at center of span
   - Zero without load

4. **Apply load:**
   - Place known weight at center
   - Wait 2-3 seconds for settling (avoid cold creep)
   - Record deflection

5. **Calculate:**
   ```bash
   python -m modes.bending_stiffness.deflection_to_moe \
     --span 400 --width 50 --thickness 3.2 \
     --force 9.81 --deflection 1.8 --density 0.41
   ```

### Deflection CSV Format

For batch processing, create a CSV with these columns:

```csv
method,span_mm,width_mm,thickness_mm,force_N,deflection_mm,density_g_cm3,inner_span_mm
3point,400,50,3.2,9.81,1.8,0.41,
3point,400,48,3.0,9.81,2.1,0.43,
4point,400,50,3.2,9.81,1.5,0.41,133
```

---

## Wood Property Grading

### Radiation Coefficient Scale

The radiation coefficient R = √(E/ρ) / 1000 predicts acoustic quality:

| Grade | R Value | Description |
|-------|---------|-------------|
| **AAA** | ≥ 15 | Master grade, exceptional projection |
| **AA** | 13-15 | Concert grade, excellent |
| **A** | 11-13 | Professional grade, very good |
| **B** | 9-11 | Standard grade, good |
| **C** | 7-9 | Budget grade, acceptable |
| **D** | < 7 | Not recommended for soundboards |

### Reference Values by Species

| Species | Density (kg/m³) | Stiffness (GPa) | Radiation |
|---------|-----------------|-----------------|-----------|
| Sitka Spruce | 380-450 | 10-14 | 11-15 |
| Engelmann Spruce | 350-420 | 9-12 | 12-16 |
| European Spruce | 400-480 | 11-16 | 12-16 |
| Western Red Cedar | 320-380 | 6-9 | 10-13 |
| Redwood | 340-420 | 7-10 | 10-13 |
| Indian Rosewood | 800-950 | 11-15 | 3.5-4.5 |
| Mahogany | 500-650 | 8-12 | 4-6 |

---

## Measurement Workflow

### For Raw Billets (Pre-Build)

```
1. Weigh specimen → density
2. Choose method:
   - Tap tone (fast, includes damping)
   - Deflection (simple jig, no mic)
3. Calculate stiffness → radiation coefficient → grade
4. Compare specimens, match pairs
```

### For Assembled Tops (David Hurd Method)

After gluing soundboard to sides, before back:

```
1. Support guitar body at rim
2. Apply known weight at bridge location
3. Measure deflection at saddle position
4. Calculate effective stiffness
5. Adjust bracing if needed
6. Re-measure until target compliance reached
```

This is the **primary application** for deflection testing in lutherie.

---

## Common Questions

### Q: Which method is more accurate?

**Both give comparable results** when done correctly. Deflection is considered more "direct" but tap tone captures dynamic behavior. Professional luthiers often use both and compare.

### Q: What's "cold creep"?

Wood continues to deflect slowly under static load. To minimize:
- Take reading within 2-3 seconds of loading
- Or use tap tone method (dynamic, no creep)

### Q: Do I need both methods?

**No.** Choose based on your situation:
- Have a good microphone? → Tap tone (faster, more data)
- Have a dial indicator? → Deflection (simpler setup)
- Building guitars? → Deflection for assembled top compliance

### Q: What affects measurement accuracy?

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Grain angle | ±10-20% | Measure along grain |
| Moisture content | ±5% per 1% MC | Stabilize at 6-8% MC |
| Temperature | ±1% per 10°C | Room temperature |
| Support conditions | ±5-10% | Use proper knife edges |
| Measurement precision | ±2-5% | Use quality instruments |

---

## CLI Quick Reference

### Tap Tone Capture
```bash
# List devices
ttp devices

# Auto-trigger capture
ttp capture --auto-trigger --output ./session

# Full gold run (capture → analyze → validate → export)
ttp gold-run --auto-trigger --output ./session
```

### Deflection Calculation (Gore-Style)
```bash
# Multi-point fit (recommended)
python -m tap_tone_pi.tonewood_deflection \
  --span_mm 400 --width_mm 30 --thick_mm 3.0 \
  --loads_N 5 10 15 20 --defl_mm 0.5 1.0 1.5 2.0

# With density + thickness targeting
python -m tap_tone_pi.tonewood_deflection \
  --span_mm 400 --width_mm 30 --thick_mm 3.0 \
  --loads_N 5 10 15 --defl_mm 0.5 1.0 1.5 \
  --strip_len_mm 450 --strip_mass_g 18.0 \
  --href_mm 2.8 --eref_GPa 12.0 \
  --json result.json
```

### Output Files

| File | Description |
|------|-------------|
| `analysis.json` | FFT results, peaks, dominant frequency |
| `quality_check.json` | Quality gate pass/fail |
| `bending_test.json` | Deflection-derived stiffness |
| `wood_properties.json` | Estimated material properties |
| `viewer_pack.zip` | Exportable session bundle |

---

## Further Reading

- [QUICK_START.md](QUICK_START.md) — Getting started guide
- [API.md](API.md) — Programmatic API reference
- [MEASUREMENT_BOUNDARY.md](MEASUREMENT_BOUNDARY.md) — Scope and limitations
- [ANALYZER_COMPARISON.md](ANALYZER_COMPARISON.md) — Commercial analyzer comparison
- David Hurd, *Left-Brain Lutherie* — Deflection compliance method
- Gore & Gilet, *Contemporary Acoustic Guitar Design* — Wood properties reference

---

## Summary: What Test Gives What Property

| Test | Input | Output |
|------|-------|--------|
| **Weighing** | mass + dimensions | Density (ρ) |
| **Tap Tone** | frequency + dimensions + density | Stiffness (E), Damping (Q), Grade |
| **Deflection** | force + deflection + dimensions | Stiffness (E) |
| **Calculation** | E + ρ | Radiation coefficient, Grade |

**Bottom line:** You need density (weigh it) plus either tap tone OR deflection to get all the wood properties that matter for lutherie.
