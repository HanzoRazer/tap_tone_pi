# Wolf Beat Analysis - Laboratory Operations Manual

**Document ID:** LOM-WBA-001
**Version:** 1.0
**Effective Date:** 2026-02-16
**Classification:** Technical Operations

---

## 1. Purpose and Scope

This manual provides standardized procedures for performing physics-based wolf note analysis on acoustic instrument bodies using the Tap Tone Analyzer. The procedures detect coupled resonance splitting that causes the characteristic "wolf" beating in bowed and plucked string instruments.

### 1.1 What is a Wolf Note?

A wolf note occurs when a string's vibration frequency closely matches a body resonance frequency. The two oscillators couple, creating **two split modes** instead of one. When both modes are excited simultaneously (as happens with bowing), energy transfers back and forth between string and body at the **beat frequency**:

```
f_beat = |f_upper - f_lower|
```

Audible symptoms:
- **1-4 Hz**: Growling, pulsating tone (most objectionable)
- **4-10 Hz**: Warbling, uneven sustain
- **>10 Hz**: Roughness, less distinct beating

### 1.2 Physical Basis

From coupled oscillator theory:

```
f_beat ≈ k_c / (2π × f_body × √(m_string × m_body))
```

Where:
- `k_c` = bridge coupling stiffness
- `f_body` = body mode frequency (Hz)
- `m_string`, `m_body` = effective masses

The splitting becomes **unresolvable** (wolf masked) when:

```
f_beat < (γ_lower + γ_upper)
```

Where `γ` is the half-power bandwidth of each peak.

---

## 2. Equipment Requirements

### 2.1 Required Hardware

| Item | Specification | Purpose |
|------|---------------|---------|
| Tap hammer | 5-15g steel ball or hard plastic | Impulse excitation |
| Measurement microphone | Flat response 20-5000 Hz | Response capture |
| Microphone preamp | Low noise, phantom power | Signal conditioning |
| Audio interface | 48 kHz minimum, 24-bit | Digitization |
| Specimen support | Foam blocks or string suspension | Isolation |
| Reference accelerometer (optional) | ICP type, 10 mV/g | Force normalization |

### 2.2 Required Software

- Tap Tone Analyzer v2.0+
- Python 3.10+ with tap_tone_pi package
- Viewer pack export capability

### 2.3 Calibration

Before each session:
1. Verify microphone frequency response is flat (±3 dB, 50-2000 Hz)
2. Check preamp gain setting (target -12 dBFS peak)
3. Confirm sample rate matches configuration (48000 Hz default)

---

## 3. Specimen Preparation

### 3.1 Support Configuration

**Critical:** Improper support adds spurious modes or damps real modes.

**For guitar/violin bodies:**
```
┌─────────────────────────────┐
│                             │
│    ○ ← foam block (neck)   │
│                             │
│         BODY                │
│                             │
│    ○ ← foam block (tail)   │
│                             │
└─────────────────────────────┘

Support points: minimum contact, near nodal lines
```

**Acceptance criteria:**
- Body can rock freely (not clamped)
- Tapping produces sustained ring (>1 second decay)
- No rattling or buzzing

### 3.2 Environmental Conditions

| Parameter | Target | Acceptable Range |
|-----------|--------|------------------|
| Temperature | 20°C | 18-25°C |
| Relative humidity | 45% | 35-55% |
| Background noise | <40 dBA | <50 dBA |

Record conditions in session metadata.

### 3.3 Microphone Placement

**Standard position:** 150mm from soundhole center, on axis.

```
        ┌──────────────┐
        │   SOUNDHOLE  │
        │      ○───────┼──── MIC @ 150mm
        │              │
        └──────────────┘
```

**Alternative positions for mode isolation:**
- Lower bout center (emphasizes low modes)
- Upper bout (emphasizes high modes)
- Bridge area (maximum coupling observation)

---

## 4. Data Acquisition Procedure

### 4.1 Pre-Acquisition Checklist

- [ ] Specimen properly supported
- [ ] Microphone positioned and secured
- [ ] Preamp gain calibrated
- [ ] Background noise acceptable
- [ ] Session metadata entered

### 4.2 Tap Protocol

**Standard grid: 9-point pattern**

```
    A1 ─── A2 ─── A3
    │      │      │
    B1 ─── B2 ─── B3
    │      │      │
    C1 ─── C2 ─── C3
```

**For each tap point:**

1. Position tap hammer 30mm above surface
2. Allow hammer to fall freely (consistent force)
3. Single clean tap - no bouncing
4. Wait for decay (<-40 dB, typically 2-3 seconds)
5. Verify capture quality (no clipping, coherence >0.8)

**Minimum taps per point:** 3 (for averaging)

### 4.3 Quality Acceptance Criteria

| Metric | Requirement | Action if Failed |
|--------|-------------|------------------|
| Coherence (mean) | >0.85 | Add more averages |
| Coherence (min) | >0.70 | Check for noise/nonlinearity |
| Clipping | None | Reduce preamp gain |
| SNR | >30 dB | Reduce background noise |

---

## 5. Wolf Beat Analysis Procedure

### 5.1 Transfer Function Computation

From the captured impulse responses, compute the frequency response function (FRF):

```python
from tap_tone.wolf_beat import analyze_wolf_beat
import numpy as np

# Load transfer function data
frequencies = np.load("session/derived/frequencies.npy")
magnitude = np.load("session/derived/tf_magnitude.npy")
phase = np.load("session/derived/tf_phase.npy")

# Run wolf beat analysis
result = analyze_wolf_beat(
    frequencies,
    magnitude,
    phase,
    min_freq_hz=60.0,      # Below lowest string fundamental
    max_freq_hz=400.0,     # Typical wolf range
    peak_prominence=0.15,
    use_lorentzian_fit=True,
)
```

### 5.2 Peak Detection Parameters

| Parameter | Default | Adjust When |
|-----------|---------|-------------|
| `min_freq_hz` | 50 | Lower for bass instruments |
| `max_freq_hz` | 500 | Higher for violin/mandolin |
| `peak_prominence` | 0.1 | Increase if too many peaks detected |
| `max_pair_separation_hz` | 50 | Decrease for tighter coupling only |

### 5.3 Interpreting Results

**Key output fields:**

```python
print(f"Peaks detected: {result.n_peaks}")
print(f"Wolf pairs found: {result.n_pairs}")

if result.worst_wolf_freq_hz:
    print(f"Worst wolf at: {result.worst_wolf_freq_hz:.1f} Hz")
    print(f"Beat frequency: {result.worst_wolf_beat_hz:.1f} Hz")
    print(f"Severity: {result.worst_wolf_severity}")
```

**Severity classification:**

| Severity | Merge Ratio | Beat Rate | Audible Effect |
|----------|-------------|-----------|----------------|
| `none` | <0.5 | - | Peaks merged, no beating |
| `mild` | 0.5-1.0 | <1 or >10 Hz | Subtle or fast roughness |
| `moderate` | >1.0 | 4-10 Hz | Warbling tone |
| `severe` | >1.0 | 1-4 Hz | Growling, pulsating |

### 5.4 Detailed Pair Analysis

For each detected pair:

```python
for pair in result.pairs:
    print(f"\n--- Wolf Pair ---")
    print(f"Lower peak: {pair.lower.freq_hz:.1f} Hz (Q={pair.lower.Q:.0f})")
    print(f"Upper peak: {pair.upper.freq_hz:.1f} Hz (Q={pair.upper.Q:.0f})")
    print(f"Split: {pair.delta_f_hz:.2f} Hz")
    print(f"Combined linewidth: {pair.combined_linewidth_hz:.2f} Hz")
    print(f"Merge ratio: {pair.merge_ratio:.2f}")
    print(f"Resolvable: {pair.is_resolvable}")
    print(f"Severity: {pair.wolf_severity}")
```

---

## 6. Mitigation Assessment

### 6.1 Wolf Eliminator Sizing

A wolf eliminator adds mass to reduce the frequency split:

```python
from tap_tone.wolf_beat import predict_wolf_severity_change

# Test adding a 5g mass (50% increase in effective mass)
prediction = predict_wolf_severity_change(
    result,
    mass_change_factor=1.5,  # 50% heavier
)
print(prediction)
```

**Estimation formula:**

```
New split ≈ Original split / √(mass_factor)
```

| Added Mass | Mass Factor | Split Reduction |
|------------|-------------|-----------------|
| +25% | 1.25 | 11% |
| +50% | 1.50 | 18% |
| +100% | 2.00 | 29% |

### 6.2 Damping Modifications

Adding damping (e.g., soundpost adjustment, internal dampers) increases linewidth:

```python
prediction = predict_wolf_severity_change(
    result,
    damping_change_factor=1.5,  # 50% more damping
)
```

**Effect:** Peaks broaden and merge, but overall resonance weakens.

### 6.3 Structural Modifications

Changes that shift body mode frequency:
- Plate thickness adjustment
- Bass bar modification
- Soundpost position

**Goal:** Move body mode away from string fundamental.

---

## 7. Reporting

### 7.1 Standard Report Contents

1. **Session metadata**
   - Specimen ID
   - Date/time
   - Environmental conditions
   - Operator

2. **Measurement summary**
   - Number of tap points
   - Average coherence
   - Frequency range analyzed

3. **Wolf analysis results**
   - Number of peaks detected
   - Number of wolf pairs found
   - Worst wolf location and severity
   - Full pair table

4. **Recommendations**
   - Suggested mitigation (if needed)
   - Predicted effect of modifications

### 7.2 Export Format

```python
import json

report = result.to_dict()
with open("wolf_beat_report.json", "w") as f:
    json.dump(report, f, indent=2)
```

### 7.3 Viewer Pack Integration

Wolf beat analysis integrates with the standard viewer pack:

```
viewer_pack_v1/
├── meta/
├── spectra/
├── ods/
├── wolf/
│   ├── wolf_candidates.json    # Spatial WSI analysis
│   ├── wsi_curve.csv
│   └── wolf_beat_analysis.json # Physics-based analysis (NEW)
```

---

## 8. Troubleshooting

### 8.1 No Peaks Detected

| Possible Cause | Diagnostic | Solution |
|----------------|------------|----------|
| Gain too low | Check waveform amplitude | Increase preamp gain |
| Frequency range wrong | Check FRF plot | Adjust min/max_freq_hz |
| Prominence too high | Try 0.05 | Lower peak_prominence |

### 8.2 Too Many Peaks Detected

| Possible Cause | Diagnostic | Solution |
|----------------|------------|----------|
| Noise peaks | Check coherence | Increase averages |
| Prominence too low | Many small peaks | Increase peak_prominence |
| Harmonics included | Peaks at 2×, 3× | Narrow frequency range |

### 8.3 Inconsistent Q Values

| Possible Cause | Diagnostic | Solution |
|----------------|------------|----------|
| Poor fit | Check fit_r_squared | Use half_power method |
| Overlapping peaks | Visual inspection | Manual peak selection |
| Nonlinear response | Coherence dips | Reduce tap force |

### 8.4 Wolf Pair Not Detected

| Possible Cause | Diagnostic | Solution |
|----------------|------------|----------|
| Split too small | Peaks merged visually | Wolf may be suppressed |
| Separation > max | Check max_pair_separation | Increase parameter |
| Amplitude mismatch | One peak dominant | Check amplitude_ratio_max |

---

## 9. Quality Assurance

### 9.1 Daily Verification

- [ ] Microphone calibration check
- [ ] Test tap on reference specimen
- [ ] Verify coherence >0.9 at known mode

### 9.2 Monthly Calibration

- [ ] Full microphone frequency response verification
- [ ] Reference specimen full analysis
- [ ] Compare to historical baseline

### 9.3 Traceability

All measurements must include:
- Session ID
- Operator ID
- Calibration date
- Software version (algorithm_version in output)

---

## 10. References

### 10.1 Theory

1. Coupled oscillator eigenvalue analysis
2. Avoided crossing in near-degenerate systems
3. Wolf note physics in bowed string instruments (Gough, 1981)
4. Modal analysis of guitar bodies (Jansson, 2002)

### 10.2 Related Documents

- `LAB_MANUAL_TAP_TONE_CAPTURE.md` - Basic tap tone procedures
- `SCHEMA_wolf_beat_analysis_v1.json` - Output schema
- `ADR-0009-wolf-beat-physics.md` - Architecture decision record

### 10.3 Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-16 | Tap Tone Team | Initial release |

---

## Appendix A: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                WOLF BEAT ANALYSIS - QUICK REF               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  WOLF CONDITION:  f_string ≈ f_body                        │
│                                                             │
│  BEAT FREQUENCY:  f_beat = |f_upper - f_lower|             │
│                                                             │
│  RESOLVABILITY:   f_beat > (γ_upper + γ_lower)             │
│                   ───────────────────────────               │
│                        merge_ratio > 1.0                    │
│                                                             │
│  SEVERITY GUIDE:                                            │
│    1-4 Hz  → SEVERE (growl)                                │
│    4-10 Hz → MODERATE (warble)                             │
│    >10 Hz  → MILD (roughness)                              │
│    <1 Hz   → MILD (slow pulsation)                         │
│                                                             │
│  MITIGATION:                                                │
│    + Mass    → Reduces split by 1/√(mass_factor)           │
│    + Damping → Broadens peaks, promotes merging            │
│    Δ Freq    → Move body mode away from string             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ACCEPTANCE CRITERIA:                                       │
│    Coherence mean > 0.85                                    │
│    Coherence min  > 0.70                                    │
│    SNR           > 30 dB                                    │
│    No clipping                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Example Session

```python
#!/usr/bin/env python3
"""Example wolf beat analysis session."""

from pathlib import Path
import numpy as np
from tap_tone.wolf_beat import analyze_wolf_beat

# Load session data
session_dir = Path("runs/gold/2026-02-16/violin_01/session_001")
derived = session_dir / "derived"

# Load transfer function (assumes ODS compute has run)
data = np.load(derived / "transfer_functions.npz")
freqs = data["freqs"]
H = data["H_real"] + 1j * data["H_imag"]

# Use magnitude from a representative point (e.g., bridge)
magnitude = np.abs(H[0, :])  # First point
phase = np.angle(H[0, :], deg=True)

# Run analysis
result = analyze_wolf_beat(
    freqs,
    magnitude,
    phase,
    min_freq_hz=180.0,   # G string fundamental area
    max_freq_hz=350.0,   # Common wolf range for violin
)

# Report
print(f"=== Wolf Beat Analysis ===")
print(f"Peaks: {result.n_peaks}")
print(f"Pairs: {result.n_pairs}")

if result.worst_wolf_severity != "none":
    print(f"\n** WOLF DETECTED **")
    print(f"Location: {result.worst_wolf_freq_hz:.1f} Hz")
    print(f"Beat rate: {result.worst_wolf_beat_hz:.2f} Hz")
    print(f"Severity: {result.worst_wolf_severity.upper()}")
else:
    print(f"\nNo significant wolf detected.")

# Save report
import json
with open(derived / "wolf_beat_analysis.json", "w") as f:
    json.dump(result.to_dict(), f, indent=2)
```

---

*End of Document*
