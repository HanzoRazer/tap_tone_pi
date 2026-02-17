# AN-005: Comparing Two Specimens

**Application Note** | Tap Tone Pi Analyzer

---

## Overview

Comparing acoustic or vibration properties between specimens is fundamental to quality control, material selection, and research. This note covers techniques for making meaningful comparisons using Tap Tone Pi.

## Why Compare?

Common comparison scenarios:

| Application | Comparison Purpose |
|-------------|-------------------|
| **Guitar building** | Match top and back plates |
| **Speaker production** | QC against golden sample |
| **Material research** | Evaluate treatment effects |
| **Failure analysis** | Good vs. failed specimen |
| **Grading** | Sort specimens into quality tiers |

## Comparison Methods

### Method 1: Visual Overlay

Overlay spectra for quick visual comparison:

```bash
# Analyze both specimens
ttp analyze specimen_A.wav --output spec_A.json
ttp analyze specimen_B.wav --output spec_B.json

# Plot overlay
ttp plot spec_A.json spec_B.json --overlay \
    --labels "Specimen A" "Specimen B"
```

### Method 2: Numerical Diff

Quantitative comparison of key parameters:

```bash
# Compute diff
ttp diff spec_A.json spec_B.json --output comparison.json
```

Output:
```json
{
  "peak_comparison": [
    {
      "specimen_a": {"freq_hz": 245.3, "amplitude_db": -15.2},
      "specimen_b": {"freq_hz": 252.1, "amplitude_db": -14.8},
      "delta_freq_hz": 6.8,
      "delta_freq_cents": 48.1,
      "delta_amplitude_db": 0.4
    }
  ],
  "summary": {
    "mean_freq_delta_cents": 32.4,
    "max_freq_delta_cents": 52.1,
    "mean_amplitude_delta_db": 0.8,
    "similarity_score": 0.87
  }
}
```

### Method 3: Statistical Comparison

For multiple specimens or repeated measurements:

```bash
# Analyze all specimens
for wav in specimens/*.wav; do
    ttp analyze "$wav" --output "analysis/$(basename ${wav%.wav}.json)"
done

# Statistical comparison
ttp stats analysis/*.json --output stats_report.json
```

## Key Comparison Metrics

### 1. Modal Frequencies

The frequencies of resonant peaks:

```python
# Extract and compare modes
specimen_a_modes = [82.3, 178.5, 245.1, 312.4]
specimen_b_modes = [85.1, 182.3, 251.8, 318.2]

# Calculate differences in cents
# cents = 1200 * log2(f2/f1)
for fa, fb in zip(specimen_a_modes, specimen_b_modes):
    cents = 1200 * math.log2(fb / fa)
    print(f"{fa:.1f} Hz → {fb:.1f} Hz: {cents:+.1f} cents")
```

### 2. Mode Ratios

Ratios between modes often matter more than absolute frequencies:

```python
# Mode ratio comparison
def mode_ratios(modes):
    return [m / modes[0] for m in modes]

ratios_a = mode_ratios(specimen_a_modes)  # [1.0, 2.17, 2.98, 3.80]
ratios_b = mode_ratios(specimen_b_modes)  # [1.0, 2.14, 2.96, 3.74]

# Compare ratios (scale-independent)
for i, (ra, rb) in enumerate(zip(ratios_a, ratios_b)):
    print(f"Mode {i+1} ratio: {ra:.3f} vs {rb:.3f} (Δ={ra-rb:+.3f})")
```

### 3. Damping (Q Factors)

How quickly each mode decays:

```bash
# Extract Q factors
ttp analyze specimen.wav --include-q-factors
```

Higher Q = less damping = longer sustain

### 4. Overall Response Shape

Compare spectral envelopes:

```bash
# Smoothed comparison
ttp analyze specimen_A.wav --smoothing octave --output smooth_A.json
ttp analyze specimen_B.wav --smoothing octave --output smooth_B.json

# RMS difference across spectrum
ttp diff smooth_A.json smooth_B.json --metric rms
```

## Specimen Matching

### Guitar Top/Back Matching

Traditional luthiers match plates by tap tone. Digital approach:

```bash
# Measure multiple specimens
for plate in plates/*.wav; do
    ttp analyze "$plate" --output "analysis/$(basename ${plate%.wav}.json)"
done

# Find best match for target
ttp match analysis/target_top.json analysis/backs/*.json \
    --criteria mode-ratios \
    --output match_results.json
```

Matching criteria:
- **Mode ratios:** Similar ratio of first few modes
- **Absolute frequencies:** Within ±N cents
- **Damping:** Similar Q factors

### Example Match Report

```json
{
  "target": "top_001.json",
  "matches": [
    {
      "specimen": "back_015.json",
      "score": 0.94,
      "mode_ratio_error": 0.02,
      "freq_delta_mean_cents": 15.3
    },
    {
      "specimen": "back_008.json",
      "score": 0.89,
      "mode_ratio_error": 0.04,
      "freq_delta_mean_cents": 28.1
    }
  ]
}
```

## Quality Control Comparison

### Golden Sample Method

Compare production units to a known-good reference:

```bash
# Define golden sample
ttp golden-set reference_unit.json

# Compare production unit
ttp qc-compare production_unit_042.wav \
    --golden reference_unit.json \
    --tolerance-cents 50 \
    --tolerance-db 3.0
```

Output:
```
QC Result: PASS
  Mode 1: 245.3 Hz (ref: 248.1 Hz) -19.5 cents ✓
  Mode 2: 512.8 Hz (ref: 515.2 Hz) -8.1 cents ✓
  Mode 3: 823.4 Hz (ref: 820.5 Hz) +6.1 cents ✓
  Amplitude deviation: 1.2 dB (max allowed: 3.0 dB) ✓
```

### Batch Statistics

Track consistency across production:

```bash
# Analyze batch
ttp batch-analyze production_run_001/*.wav \
    --output batch_stats.json

# Report
python -c "
import json
with open('batch_stats.json') as f:
    stats = json.load(f)

print(f'Units analyzed: {stats[\"count\"]}')
print(f'Mode 1 frequency: {stats[\"mode1_mean\"]:.1f} ± {stats[\"mode1_std\"]:.1f} Hz')
print(f'Units outside 2σ: {stats[\"outliers\"]}')
"
```

## Best Practices

### Measurement Consistency

For valid comparisons, standardize:

| Parameter | Requirement |
|-----------|-------------|
| Support | Same foam/fixture |
| Sensor position | Same location on each specimen |
| Tap location | Same point |
| Tap force | Consistent (use drop hammer for repeatability) |
| Environment | Same temperature and humidity |

### Number of Measurements

Take multiple measurements per specimen:

```bash
# 3-5 taps per specimen
for i in $(seq 1 5); do
    ttp capture --auto-trigger --output "specimen_A_tap_${i}.wav"
done

# Average results
ttp analyze specimen_A_tap_*.wav --mode average --output specimen_A_avg.json
```

### Normalization

For specimens of different sizes:

```python
# Normalize to equivalent dimensions
# Frequency scales with sqrt(E/ρ) / L²
# where L = characteristic length

def normalize_freq(freq, length, ref_length):
    return freq * (length / ref_length) ** 2
```

## Example: Before/After Treatment

Compare a specimen before and after some treatment:

```bash
# Before treatment
ttp capture --auto-trigger --output specimen_before.wav
ttp analyze specimen_before.wav --output before.json

# [Apply treatment]

# After treatment
ttp capture --auto-trigger --output specimen_after.wav
ttp analyze specimen_after.wav --output after.json

# Compare
ttp diff before.json after.json --output treatment_effect.json

# Report
ttp report treatment_effect.json --format markdown > treatment_report.md
```

Sample output:
```markdown
## Treatment Effect Report

| Mode | Before (Hz) | After (Hz) | Change (cents) |
|------|-------------|------------|----------------|
| 1    | 245.3       | 262.1      | +114           |
| 2    | 512.8       | 548.2      | +116           |
| 3    | 823.4       | 876.5      | +109           |

**Summary:** Treatment increased all modal frequencies by ~110 cents
(consistent with 6.5% stiffness increase or 3% mass reduction)
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Large frequency variations | Temperature difference | Control environment |
| Inconsistent amplitudes | Tap force variation | Use mechanical tapper |
| Extra peaks in one specimen | Different mode excitation | Tap same location |
| Can't match peaks | Too different | Verify correct specimens |

## Related Notes

- [AN-002: Finding Resonant Modes in a Plate](AN-002_plate_resonant_modes.md)
- [AN-004: Coherence and Measurement Quality](AN-004_coherence_quality.md)

## References

1. Hutchins, C.M. "The Acoustics of Violin Plates"
2. Jansson, E.V. "Acoustics for Violin and Guitar Makers"
3. ISO 266: Preferred frequencies for acoustic measurements
