# AN-001: Measuring Frequency Response of a Speaker

**Application Note** | Tap Tone Pi Analyzer

---

## Overview

This note describes how to measure the on-axis frequency response of a loudspeaker or driver using Tap Tone Pi's signal generator and analyzer. Frequency response is the most fundamental speaker measurement, showing how output level varies across the audio spectrum.

## Equipment Required

| Item | Purpose |
|------|---------|
| Tap Tone Pi system | Signal generation and analysis |
| Measurement microphone | Acoustic pickup (USB or with preamp) |
| Speaker under test | Device being measured |
| Amplifier | To drive the speaker |
| Test environment | Low-noise room or anechoic chamber |

## Setup

### Physical Arrangement

```
                    1 meter (typical)
    [Speaker] ◄─────────────────────► [Microphone]
        │                                   │
        │                                   │
    [Amplifier]                      [Audio Interface]
        │                                   │
        │                                   │
    [Audio Out] ◄──── [Computer] ────► [Audio In]
```

**Key Points:**
- Place microphone on-axis (directly in front of speaker)
- 1 meter is standard measurement distance
- Minimize reflections from nearby surfaces
- Keep noise sources (HVAC, computers) quiet

### Software Configuration

```bash
# List audio devices
ttp devices

# Run preflight check
ttp preflight --device-in <mic_index> --device-out <speaker_index>
```

## Measurement Procedure

### Method 1: Swept Sine (Recommended)

The swept sine provides the best signal-to-noise ratio:

```bash
# Generate logarithmic sweep (covers 20 Hz - 20 kHz)
ttp generate sweep --start-freq 20 --end-freq 20000 \
    --duration 5 --output sweep.wav

# Play sweep while capturing response
# (Requires external synchronization or use loopback)
ttp capture --duration 6 --output response.wav

# Analyze response
ttp analyze response.wav --output speaker_fr.json
```

### Method 2: Pink Noise (Quick Check)

Pink noise provides a fast, continuous measurement:

```bash
# Generate pink noise (equal energy per octave)
ttp generate noise --type pink --duration 10 --output pink.wav

# Capture during playback
ttp capture --duration 10 --output response.wav

# Analyze with octave smoothing
ttp analyze response.wav --smoothing octave
```

### Method 3: Impulse Response (Advanced)

The impulse response contains all frequency information:

```bash
# Generate chirp for impulse response
ttp generate chirp --start-freq 20 --end-freq 20000 \
    --duration 1 --output chirp.wav

# Capture and deconvolve (external tool)
# Result: impulse response → FFT → frequency response
```

## Interpreting Results

### Ideal Response

A "flat" speaker shows:
- Level variation < ±3 dB from 100 Hz to 10 kHz
- Smooth roll-off below resonance frequency
- Gradual roll-off above 15 kHz

### Common Patterns

| Pattern | Likely Cause |
|---------|--------------|
| Sharp dip at specific frequency | Room mode or cabinet resonance |
| Rising response with frequency | Baffle step diffraction |
| Comb filter pattern | Reflection interference |
| Low frequency roll-off | Enclosure too small |
| High frequency roll-off | Tweeter or crossover issue |

### Example Analysis

```bash
# Run analysis with limits
ttp analyze response.wav --limits speaker_response \
    --output results.json --verbose
```

Output includes:
- Frequency response curve
- Sensitivity (dB SPL @ 1W/1m)
- -3 dB points (low and high)
- Smoothed response (1/3 octave typical)

## Best Practices

### Environment
- **Anechoic:** Ideal but expensive
- **Ground plane:** Place mic and speaker on floor (outdoor)
- **Gated measurement:** Use time windowing to remove reflections

### Signal Level
- Target -20 dBFS at microphone
- Avoid clipping in either direction
- Verify level with `ttp preflight`

### Averaging
- Average 3-5 measurements for noise reduction
- Pink noise needs more averaging than sweep

### Documentation
- Record room temperature and humidity
- Note measurement distance
- Save raw captures alongside analysis

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Noisy measurement | Increase signal level, use longer average |
| Comb filtering | Check for reflections, use gating |
| Low frequency missing | Room too small, try near-field |
| Inconsistent results | Check microphone positioning |

## Related Notes

- [AN-003: Transfer Function Measurement Setup](AN-003_transfer_function_setup.md)
- [AN-004: Coherence and Measurement Quality](AN-004_coherence_quality.md)

## References

1. Toole, F. "Sound Reproduction: The Acoustics and Psychoacoustics of Loudspeakers and Rooms"
2. D'Appolito, J. "Testing Loudspeakers"
3. AES Standard: AES56-2008 "Sound Source Modeling"
