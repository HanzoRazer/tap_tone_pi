# AN-002: Finding Resonant Modes in a Plate

**Application Note** | Tap Tone Pi Analyzer

---

## Overview

This note describes how to use Tap Tone Pi to identify the resonant modes (natural frequencies) of a plate or panel. This technique applies to:

- Soundboard characterization (guitar tops, violin plates)
- Speaker cone analysis
- Structural vibration analysis
- Material property estimation

## Theory: Plate Vibration

When excited, a plate vibrates at its natural frequencies (modes). Each mode has:

- **Frequency:** The resonant frequency in Hz
- **Mode shape:** The spatial pattern of vibration (nodal lines)
- **Damping:** How quickly the vibration decays

For a rectangular plate, modes are typically labeled (m, n) where m and n indicate the number of half-wavelengths in each direction.

```
Mode (1,1)     Mode (2,1)     Mode (1,2)     Mode (2,2)
   ____           ____           ____           ____
  |    |         | +| |         |    |         | +|-|
  | +  |         |  | |         |----| ←node   |----|
  |____|         |-+| |         |____|         |-+| |
                     ↑
                   node
```

## Equipment Required

| Item | Purpose |
|------|---------|
| Tap Tone Pi system | Spectrum analysis |
| Contact microphone or accelerometer | Vibration pickup |
| Small hammer or tapping rod | Impulse excitation |
| Soft support (foam) | To allow free vibration |
| Grid template (optional) | For mode mapping |

## Setup

### Physical Arrangement

```
              Specimen (plate)
    ┌─────────────────────────────┐
    │                             │
    │     X ← tap point          │
    │         ● ← sensor         │
    │                             │
    └─────────────────────────────┘
          ↓ ↓ ↓ ↓ ↓
       Soft foam support
       (allows free vibration)
```

**Key Points:**
- Support plate on soft foam to allow free vibration
- Place sensor away from nodal lines (corners work well)
- Tap firmly but don't damage the material

### Software Configuration

```bash
# Configure for impulse capture
ttp preflight --device-in <sensor_index>

# Set appropriate sample rate for expected frequencies
# Guitar tops: 48 kHz sufficient (modes typically < 2 kHz)
# Metal plates: May need 96 kHz for higher modes
```

## Measurement Procedure

### Step 1: Initial Tap Test

```bash
# Capture a tap response
ttp capture --duration 2 --auto-trigger --output tap_001.wav

# Quick analysis
ttp analyze tap_001.wav --output modes.json
```

### Step 2: Identify Peaks

The analyzer identifies spectral peaks automatically:

```json
{
  "peaks": [
    {"frequency_hz": 82.3, "amplitude_db": -12.4, "q_factor": 45.2},
    {"frequency_hz": 178.5, "amplitude_db": -18.1, "q_factor": 38.7},
    {"frequency_hz": 245.1, "amplitude_db": -22.3, "q_factor": 52.1}
  ]
}
```

### Step 3: Verify Modes

Repeat taps at different locations. True modes appear consistently; artifacts don't:

```bash
# Multiple tap captures
for i in $(seq 1 5); do
    ttp capture --duration 2 --auto-trigger --output tap_00${i}.wav
done

# Batch analysis
for f in tap_*.wav; do
    ttp analyze "$f" --peaks-only
done
```

### Step 4: Mode Mapping (Optional)

To determine mode shapes, use a grid of tap points:

```python
# Example: Grid scan script
import numpy as np
from tap_tone_pi import capture, analyze

# Define grid
grid_x = np.linspace(0.1, 0.9, 5)  # 5 points across
grid_y = np.linspace(0.1, 0.9, 5)  # 5 points down

results = {}
for ix, x in enumerate(grid_x):
    for iy, y in enumerate(grid_y):
        print(f"Tap at ({x:.1f}, {y:.1f})")
        input("Press Enter when ready...")

        data = capture.record_audio(duration=2.0)
        result = analyze.analyze_spectrum(data)
        results[(ix, iy)] = result['peaks']

# Find mode shapes by comparing amplitudes at each point
```

## Interpreting Results

### Guitar Top Example

Typical spruce guitar top modes:

| Mode | Typical Range | Character |
|------|---------------|-----------|
| (1,1) | 80-120 Hz | "Main air" coupled with body |
| (1,2) | 150-200 Hz | Cross-dipole |
| (2,1) | 200-250 Hz | Long dipole |
| (2,2) | 280-350 Hz | Quadrupole |
| Higher | 400+ Hz | Complex patterns |

### Quality Indicators

| Parameter | Good Sign | Concern |
|-----------|-----------|---------|
| Q factor | 30-80 | < 20 (too damped) or > 100 (too ringy) |
| Mode spacing | Even, 1.2-1.5× ratio | Clustered modes |
| Amplitude | Strong fundamental | Weak low modes |

### Comparing Specimens

Use the session diff feature:

```bash
# Analyze both specimens
ttp analyze plate_A.wav --output plate_A.json
ttp analyze plate_B.wav --output plate_B.json

# Compare mode frequencies
ttp diff plate_A.json plate_B.json
```

## Advanced: ODS (Operating Deflection Shape)

For full mode visualization, use the Phase 2 ODS features:

```bash
# Multi-point grid capture with coherence
ttp grid-capture --points 25 --reference-channel 0 \
    --output grid_data.json

# ODS analysis (requires Phase 2 module)
ttp ods-analyze grid_data.json --output ods_result.json
```

## Best Practices

### Excitation
- Use consistent tap force
- Tap perpendicular to surface
- Avoid exciting unwanted modes (edge taps)

### Measurement
- Wait for previous tap to decay completely
- Average multiple taps for noise reduction
- Note any handling noise

### Documentation
- Record material properties (wood species, thickness)
- Photograph specimen with measurement grid
- Save all raw captures

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No clear peaks | Increase tap force, check sensor coupling |
| Too many peaks | Filter out room noise, use closer support |
| Inconsistent frequencies | Check for loose components, temperature drift |
| Low Q factors | Material is highly damped (normal for some woods) |

## Related Notes

- [AN-003: Transfer Function Measurement Setup](AN-003_transfer_function_setup.md)
- [AN-005: Comparing Two Specimens](AN-005_specimen_comparison.md)

## References

1. Fletcher, N. & Rossing, T. "The Physics of Musical Instruments"
2. Schleske, M. "Empirical Tools in Contemporary Violin Making"
3. Elejabarrieta, M.J. et al. "Evolution of the vibrational behavior of a guitar soundboard"
