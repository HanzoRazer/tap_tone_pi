# AN-003: Transfer Function Measurement Setup

**Application Note** | Tap Tone Pi Analyzer

---

## Overview

A transfer function describes how a system modifies a signal between input and output. This note covers setting up Tap Tone Pi for transfer function measurements, which are essential for:

- Frequency response of amplifiers and filters
- Mechanical impedance of structures
- Room acoustics characterization
- Loudspeaker + room combined response

## Theory: Transfer Functions

The transfer function H(f) relates output Y(f) to input X(f):

```
H(f) = Y(f) / X(f)
```

In practice, we compute this using spectral averaging:

- **H1 estimator:** H1 = Gxy / Gxx (noise on output)
- **H2 estimator:** H2 = Gyy / Gyx (noise on input)
- **Hv estimator:** Geometric mean of H1 and H2

Where:
- Gxx = Auto-spectrum of input
- Gyy = Auto-spectrum of output
- Gxy = Cross-spectrum (input × output conjugate)

## Equipment Required

| Item | Purpose |
|------|---------|
| Tap Tone Pi system | Analysis engine |
| Two-channel audio interface | Simultaneous input capture |
| Signal generator source | Reference signal |
| Appropriate transducers | Input and output measurement |

## Setup: Electrical Transfer Function

For measuring amplifiers, filters, or electronic circuits:

```
                    Device Under Test
                   ┌─────────────────┐
    ┌──────────┐   │                 │   ┌──────────┐
    │ Signal   │──►│   Amplifier/    │──►│  Load    │
    │ Generator│   │   Filter/etc    │   │          │
    └────┬─────┘   └────────┬────────┘   └──────────┘
         │                  │
         ▼                  ▼
    ┌─────────────────────────────────┐
    │        Audio Interface          │
    │   Ch 1 (Ref)    Ch 2 (Response) │
    └─────────────────────────────────┘
                    │
                    ▼
              [Computer]
```

### Configuration

```bash
# Verify two-channel capture
ttp devices --verbose

# Configure for dual-channel
ttp preflight --device-in <interface_index> --channels 2
```

## Setup: Acoustic Transfer Function

For measuring speaker-room systems:

```
                            Room
    ┌─────────────────────────────────────────┐
    │                                         │
    │   [Speaker]  ──────────►  [Microphone] │
    │       │                        │        │
    └───────│────────────────────────│────────┘
            │                        │
            ▼                        ▼
    ┌─────────────────────────────────────────┐
    │            Audio Interface              │
    │   Ch 1 (Electrical)    Ch 2 (Acoustic)  │
    └─────────────────────────────────────────┘
```

**Reference Channel Options:**
1. Electrical signal to amplifier (before speaker)
2. Near-field microphone at speaker
3. Loop-back of generated signal

## Measurement Procedure

### Step 1: Signal Generation

```bash
# Generate test signal (pink noise recommended for acoustics)
ttp generate noise --type pink --duration 30 --output stimulus.wav

# Or for electronic circuits, use swept sine
ttp generate sweep --start-freq 20 --end-freq 20000 \
    --duration 10 --output sweep.wav
```

### Step 2: Dual-Channel Capture

```bash
# Capture both channels simultaneously
# Channel 1: Reference (input)
# Channel 2: Response (output)
ttp capture --duration 30 --channels 2 --output measurement.wav
```

### Step 3: Transfer Function Computation

```bash
# Compute transfer function with coherence
ttp transfer-function measurement.wav \
    --ref-channel 0 \
    --response-channel 1 \
    --averages 32 \
    --output tf_result.json
```

### Output Format

```json
{
  "transfer_function": {
    "frequencies_hz": [20, 25, 31.5, ...],
    "magnitude_db": [-3.2, -2.8, -1.5, ...],
    "phase_deg": [12.3, 15.6, 18.9, ...],
    "coherence": [0.92, 0.95, 0.98, ...]
  },
  "estimator": "H1",
  "averages": 32,
  "frequency_resolution_hz": 1.5
}
```

## Coherence: Quality Indicator

Coherence γ² ranges from 0 to 1:

| Coherence | Interpretation | Action |
|-----------|----------------|--------|
| > 0.9 | Excellent | Trust the measurement |
| 0.7 - 0.9 | Good | Usable, some noise |
| 0.5 - 0.7 | Marginal | Increase averaging |
| < 0.5 | Poor | Check setup, noise source |

**Low coherence causes:**
- Noise on input or output
- Nonlinearities in system
- Multiple signal paths (reflections)
- Insufficient averaging

## Best Practices

### Signal Level
- Reference channel: -20 to -10 dBFS
- Response channel: -30 to -10 dBFS
- Avoid clipping either channel

### Averaging
- More averages = cleaner result
- 16-32 averages typical for acoustics
- 64+ for very noisy environments

### Frequency Resolution

Trade-off between resolution and averaging:

| FFT Size | Resolution @ 48 kHz | Time per Average |
|----------|---------------------|------------------|
| 2048 | 23.4 Hz | 42.7 ms |
| 4096 | 11.7 Hz | 85.3 ms |
| 8192 | 5.9 Hz | 170.7 ms |
| 16384 | 2.9 Hz | 341.3 ms |

```bash
# Specify FFT size
ttp transfer-function measurement.wav --fft-size 8192
```

### Windowing
- Hann window for continuous signals (noise)
- Rectangular for transients (sweeps)

## Example: Room Frequency Response

```bash
# 1. Generate pink noise
ttp generate noise --type pink --duration 60 --output room_stimulus.wav

# 2. Play through speaker while capturing
#    Ch1: Direct electrical feed
#    Ch2: Room microphone
ttp capture --duration 60 --channels 2 --output room_capture.wav

# 3. Compute transfer function
ttp transfer-function room_capture.wav \
    --ref-channel 0 --response-channel 1 \
    --averages 64 \
    --smoothing third-octave \
    --output room_tf.json

# 4. Apply limits test
ttp limit-test room_tf.json --limits room_response --verbose
```

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| Low coherence at all frequencies | Wiring error | Check connections, channel assignment |
| Low coherence at specific frequencies | Room modes, nulls | Move microphone, increase averaging |
| Phase wrapping | Normal behavior | Unwrap phase in post-processing |
| Noisy magnitude | Insufficient averaging | Increase averages, longer capture |
| DC offset | Coupling capacitors | Use AC coupling, high-pass filter |

## Related Notes

- [AN-001: Measuring Frequency Response of a Speaker](AN-001_speaker_frequency_response.md)
- [AN-004: Coherence and Measurement Quality](AN-004_coherence_quality.md)

## References

1. Bendat, J.S. & Piersol, A.G. "Random Data: Analysis and Measurement Procedures"
2. Brüel & Kjær Application Notes on Transfer Function Measurement
3. AES Standard: AES17 "Measurement of Digital Audio Equipment"
