# AN-004: Coherence and Measurement Quality

**Application Note** | Tap Tone Pi Analyzer

---

## Overview

Coherence is the single most important quality metric for frequency-domain measurements. This note explains what coherence means, how to interpret it, and how to improve poor coherence measurements.

## What Is Coherence?

Coherence (γ²) measures how well the output of a system is linearly related to its input at each frequency. It ranges from 0 to 1:

```
         |Gxy|²
γ²(f) = ─────────
        Gxx · Gyy
```

Where:
- Gxy = Cross-spectral density
- Gxx = Input auto-spectral density
- Gyy = Output auto-spectral density

**In plain terms:** Coherence tells you how much of the output power at each frequency is caused by the input, versus noise or nonlinearities.

## Interpreting Coherence

### The Coherence Scale

```
1.0 ──────── Perfect: Output entirely determined by input
    │
0.9 ──────── Excellent: Professional measurement quality
    │
0.8 ──────── Good: Acceptable for most applications
    │
0.7 ──────── Marginal: Results usable but noisy
    │
0.5 ──────── Poor: Consider the data unreliable
    │
0.0 ──────── None: Output unrelated to input (noise only)
```

### What Low Coherence Means

| Cause | Explanation | Typical Pattern |
|-------|-------------|-----------------|
| **Noise** | Random noise on input or output | Uniform low coherence |
| **Nonlinearity** | System distorts the signal | Low at harmonics, ok elsewhere |
| **Multiple paths** | Signal arrives via different routes | Dips at specific frequencies |
| **Time variance** | System changed during measurement | Random dropouts |
| **Insufficient averaging** | Not enough data to stabilize | Noisy coherence curve |

## Measuring Coherence

### Basic Coherence Measurement

```bash
# Two-channel capture (reference + response)
ttp capture --duration 30 --channels 2 --output dual_ch.wav

# Compute transfer function with coherence
ttp transfer-function dual_ch.wav \
    --ref-channel 0 \
    --response-channel 1 \
    --averages 32 \
    --output result.json
```

### Viewing Coherence

```bash
# Show coherence in output
ttp transfer-function dual_ch.wav --show-coherence

# Plot coherence (requires matplotlib)
ttp plot result.json --type coherence
```

### Output Example

```json
{
  "transfer_function": {
    "frequencies_hz": [100, 200, 500, 1000, 2000, 5000, 10000],
    "coherence": [0.95, 0.97, 0.98, 0.99, 0.96, 0.88, 0.72]
  },
  "coherence_summary": {
    "min": 0.72,
    "mean": 0.92,
    "frequencies_below_0.8": [10000, 12000, 14000]
  }
}
```

## Diagnosing Coherence Problems

### Pattern 1: Uniformly Low Coherence

```
Coherence across all frequencies: ~0.5-0.7
```

**Causes:**
- SNR too low (signal buried in noise)
- Wrong channel assignment
- Cable fault or bad connection

**Solutions:**
- Increase signal level
- Check wiring and connections
- Verify channel mapping

### Pattern 2: Low Coherence at Specific Frequencies

```
Coherence: 0.95, 0.96, 0.45, 0.97, 0.95
                        ↑
               Dip at ~200 Hz
```

**Causes:**
- Room mode (acoustic null)
- Comb filtering from reflections
- Anti-resonance in structure

**Solutions:**
- Move microphone position
- Add acoustic treatment
- Use near-field measurement

### Pattern 3: Coherence Drops at High Frequencies

```
Coherence: 0.98, 0.97, 0.95, 0.88, 0.72, 0.55
            ↓    ↓    ↓    ↓    ↓    ↓
          100  200  1k   5k  10k  15k Hz
```

**Causes:**
- Noise floor reached
- Transducer bandwidth limit
- Aliasing effects

**Solutions:**
- Increase high-frequency drive level
- Use wider-bandwidth transducer
- Check sample rate settings

### Pattern 4: Low Coherence at Harmonics

```
Coherence at fundamentals: 0.98
Coherence at 2nd harmonic: 0.60
Coherence at 3rd harmonic: 0.45
```

**Causes:**
- System is nonlinear (distortion)
- Energy at harmonics not from input

**Solutions:**
- Reduce drive level
- This is real data—the system is nonlinear

## Improving Coherence

### 1. Increase Signal-to-Noise Ratio

```bash
# Check current levels
ttp preflight --device-in <index>

# Aim for:
# - Reference channel: -15 to -5 dBFS peak
# - Response channel: -25 to -10 dBFS peak
```

### 2. Increase Averaging

More averages reduce random noise effects:

| Averages | Coherence Improvement |
|----------|----------------------|
| 8 | Baseline |
| 16 | ~1.5 dB SNR improvement |
| 32 | ~3 dB SNR improvement |
| 64 | ~4.5 dB SNR improvement |

```bash
# More averages
ttp transfer-function capture.wav --averages 64
```

### 3. Reduce Ambient Noise

- Turn off HVAC during measurement
- Use a quieter time of day
- Shield from electromagnetic interference

### 4. Optimize FFT Parameters

```bash
# Larger FFT = better frequency resolution but longer measurement
ttp transfer-function capture.wav --fft-size 8192 --averages 32
```

### 5. Use Appropriate Excitation

| Signal Type | Best For |
|-------------|----------|
| Pink noise | Room acoustics, speakers |
| White noise | Electronic systems |
| Swept sine | Highest coherence possible |
| MLS | Fast measurement, good coherence |

## Quality Acceptance Criteria

### General Guidelines

| Application | Minimum Coherence |
|-------------|-------------------|
| Research/publication | > 0.95 |
| Production testing | > 0.90 |
| Quick checks | > 0.80 |
| Troubleshooting | > 0.70 |

### Using Limits

```bash
# Define coherence limits
ttp transfer-function capture.wav \
    --min-coherence 0.85 \
    --warn-coherence 0.90

# Output indicates quality
# PASS: All frequencies above 0.90
# WARN: Some frequencies 0.85-0.90
# FAIL: Any frequency below 0.85
```

## Coherence and Uncertainty

Low coherence increases measurement uncertainty:

```
Magnitude uncertainty ≈ σ / γ
```

Where σ is the standard deviation of the estimate.

| Coherence | Relative Uncertainty |
|-----------|---------------------|
| 0.99 | 1.0× (baseline) |
| 0.95 | 1.05× |
| 0.90 | 1.11× |
| 0.80 | 1.25× |
| 0.50 | 2.0× |

**Implication:** A measurement with γ² = 0.5 has twice the uncertainty of one with γ² = 0.99.

## Example: Room Measurement Quality Check

```bash
# 1. Capture room response
ttp capture --duration 60 --channels 2 --output room.wav

# 2. Analyze with coherence
ttp transfer-function room.wav \
    --averages 64 \
    --show-coherence \
    --output room_tf.json

# 3. Check quality
python -c "
import json
with open('room_tf.json') as f:
    data = json.load(f)

coh = data['transfer_function']['coherence']
freqs = data['transfer_function']['frequencies_hz']

poor = [(f, c) for f, c in zip(freqs, coh) if c < 0.8]
if poor:
    print(f'Low coherence at {len(poor)} frequencies:')
    for f, c in poor[:5]:
        print(f'  {f:.0f} Hz: γ² = {c:.2f}')
else:
    print('All frequencies have acceptable coherence (>0.8)')
"
```

## Related Notes

- [AN-003: Transfer Function Measurement Setup](AN-003_transfer_function_setup.md)
- [AN-001: Measuring Frequency Response of a Speaker](AN-001_speaker_frequency_response.md)

## References

1. Bendat, J.S. & Piersol, A.G. "Engineering Applications of Correlation and Spectral Analysis"
2. Brüel & Kjær "Frequency Analysis" (handbook)
3. ISO 9614-1: Determination of sound power using intensity (coherence requirements)
