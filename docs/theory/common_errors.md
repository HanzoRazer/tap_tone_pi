# Common Measurement Errors

This guide covers frequent mistakes in acoustic and vibration measurements,
how to recognize them, and how to fix them.

## 1. Aliasing

### What It Is
Frequencies above the Nyquist limit (sample_rate / 2) fold back into the
measurement range, appearing as false signals.

### Symptoms
- Unexpected peaks that shift when you change sample rate
- High-frequency content appearing at impossible frequencies
- Results that don't match when measured with different equipment

### Example
```
True signal: 25 kHz tone
Sample rate: 44.1 kHz
Nyquist limit: 22.05 kHz
Aliased frequency: 44.1 - 25 = 19.1 kHz  ← Wrong!
```

### Prevention
- Use anti-aliasing filter (most ADCs have this built-in)
- Sample at > 2.5× your maximum frequency of interest
- Verify with different sample rates

### Detection
```python
def check_for_aliasing(spectrum1, spectrum2, freqs):
    """
    Compare spectra at two sample rates.
    Aliased content will appear at different frequencies.
    """
    # Spectra should match up to lower Nyquist
    max_common_freq = min(freqs1[-1], freqs2[-1])
    # Large differences indicate aliasing
    ...
```

## 2. Spectral Leakage

### What It Is
FFT assumes signals are periodic in the analysis window. Non-periodic signals
spread energy across many bins, smearing peaks.

### Symptoms
- Broad, smeared peaks instead of sharp lines
- Low coherence on tonal signals
- Peak magnitudes vary with slight frequency changes

### Example
```
100.5 Hz sine analyzed with 100 Hz resolution
→ Energy splits between 100 Hz and 101 Hz bins
→ Neither bin shows correct amplitude
```

### Prevention
- Use appropriate window function (Hanning, Blackman)
- Match block size to signal periodicity when possible
- Use higher frequency resolution for narrowband signals

### Detection
- Compare windowed vs. rectangular results
- Check if peak amplitude changes with small frequency shifts

## 3. Insufficient Averaging

### What It Is
Random noise isn't adequately reduced, making results noisy and unrepeatable.

### Symptoms
- Results change significantly between repeated measurements
- Coherence is moderate (0.6-0.8) but not improving
- Noise floor varies wildly

### Prevention
- Use at least 10 averages for production testing
- Use 50+ averages for characterization
- Continue averaging until results stabilize

### Detection
```python
def check_averaging_stability(spectra_sequence):
    """
    Track running average to see if more averaging helps.
    """
    running = []
    for i in range(2, len(spectra_sequence)):
        avg = np.mean(spectra_sequence[:i], axis=0)
        running.append(avg)

    # If still changing significantly, need more averages
    final_change = np.max(np.abs(running[-1] - running[-2]) / running[-1])
    return final_change < 0.01
```

## 4. Ground Loops

### What It Is
Multiple ground paths create voltage differences that appear as noise,
typically at power line frequency and harmonics.

### Symptoms
- Strong peaks at 50/60 Hz and harmonics (100/120, 150/180, etc.)
- Noise that changes when you touch cables
- Problems that go away with battery-powered equipment

### Prevention
- Use balanced connections when possible
- Ground all equipment at a single point
- Use isolated USB or optical connections
- Keep signal cables away from power cables

### Detection
```python
def detect_power_line_interference(spectrum, freqs, power_freq=60):
    """
    Check for power line frequency and harmonics.
    """
    line_freqs = [power_freq * n for n in range(1, 11)]
    interference = []

    for f in line_freqs:
        if f < freqs[-1]:
            idx = np.argmin(np.abs(freqs - f))
            # Compare to neighbors
            neighbors = spectrum[max(0,idx-5):idx+5]
            if spectrum[idx] > 3 * np.median(neighbors):
                interference.append(f)

    return interference
```

## 5. Double Hits (Impact Testing)

### What It Is
The hammer bounces and strikes the structure twice, creating a notch in
the force spectrum and corrupting the transfer function.

### Symptoms
- Deep notches in force spectrum at regular intervals
- Low coherence at notch frequencies
- Transfer function shows unrealistic peaks at notches

### Prevention
- Use softer hammer tip
- Strike more gently
- Practice technique
- Use force window to truncate after first impact

### Detection
```python
def detect_double_hit(force_signal, sample_rate, threshold_db=-20):
    """
    Detect if force signal has multiple impacts.
    """
    # Find envelope peaks
    from scipy.signal import hilbert
    envelope = np.abs(hilbert(force_signal))

    # Find peaks above threshold
    peak_level = np.max(envelope)
    threshold = peak_level * 10**(threshold_db/20)

    # Count distinct impulses
    above_threshold = envelope > threshold
    transitions = np.diff(above_threshold.astype(int))
    n_impulses = np.sum(transitions == 1)

    return n_impulses > 1
```

## 6. Pre-Trigger Issues

### What It Is
The beginning of an impact is clipped because the trigger fired too late.

### Symptoms
- Impact force waveform starts mid-rise
- Force spectrum shows more high-frequency content than expected
- Inconsistent peak force readings

### Prevention
- Use pre-trigger buffer (10-20% of block)
- Set trigger level low enough to catch onset
- Verify waveform before accepting measurement

## 7. Sensor Overload

### What It Is
Input signal exceeds sensor or ADC range, clipping the waveform.

### Symptoms
- Flat-topped waveforms in time domain
- Excessive harmonics (especially odd harmonics)
- Coherence drops during loud passages
- ADC shows "clipping" indicator

### Prevention
- Check levels before measurement
- Use appropriate sensitivity/gain settings
- Allow headroom for transients (peak can be 3-4× RMS)

### Detection
```python
def detect_clipping(signal, threshold=0.99):
    """
    Detect clipped samples.
    """
    max_val = np.max(np.abs(signal))
    n_clipped = np.sum(np.abs(signal) > threshold * max_val)
    clip_percentage = 100 * n_clipped / len(signal)

    return clip_percentage > 0.1, clip_percentage
```

## 8. Wrong Window Function

### What It Is
Using a window inappropriate for the signal type, causing errors.

### Symptoms
- Amplitude errors (flat-top needed but Hanning used)
- Excessive leakage (rectangular used on continuous signal)
- Missing transient detail (too much smoothing)

### Prevention
| Signal Type | Recommended Window |
|-------------|-------------------|
| Transient (impact) | Rectangular or Force/Exponential |
| Continuous periodic | Hanning |
| Random/noise | Hanning with overlap |
| Amplitude-critical | Flat-top |

## 9. Mass Loading

### What It Is
The sensor changes the dynamics of the structure being measured.

### Symptoms
- Resonant frequencies shift lower when sensor attached
- Different sensors give different frequencies
- Frequencies match prediction when unloaded, shift when measured

### Prevention
- Use sensors < 1/10 the mass of the measurement point
- Use laser vibrometer for lightweight structures
- Correct for added mass if necessary

### Estimation
```python
def estimate_mass_loading_shift(f_unloaded, m_structure, m_sensor):
    """
    Estimate frequency shift from sensor mass loading.

    f_loaded ≈ f_unloaded × sqrt(m_structure / (m_structure + m_sensor))
    """
    mass_ratio = m_structure / (m_structure + m_sensor)
    f_loaded = f_unloaded * np.sqrt(mass_ratio)
    return f_loaded
```

## 10. Temperature Effects

### What It Is
Material properties change with temperature, shifting resonances.

### Symptoms
- Frequencies drift over time
- Results differ morning vs. afternoon
- Coherence drops as system warms up

### Prevention
- Allow system to reach thermal equilibrium
- Monitor temperature and note it
- Make measurements quickly if temperature changing
- Use temperature correction if applicable

### Typical Sensitivity
- Metals: ~-0.02% per °C
- Plastics: ~-0.1% per °C
- Wood: Variable, depends on moisture too

## 11. Cable Movement

### What It Is
Moving cables generate triboelectric noise, especially on high-impedance sensors.

### Symptoms
- Low-frequency rumble when cables touched
- Intermittent noise spikes
- Noise that goes away when cables are taped down

### Prevention
- Tape cables in place
- Use low-noise cables
- Avoid long cable runs
- Keep cables away from vibration sources

## 12. Incorrect Calibration

### What It Is
Sensor sensitivity or gain settings are wrong, scaling results incorrectly.

### Symptoms
- Results off by a constant factor
- Don't match other equipment
- Perfect coherence but wrong magnitude

### Prevention
- Verify calibration with known reference
- Check sensitivity values against datasheet
- Document all gain/sensitivity settings

### Verification
```python
def verify_calibration(measured, reference, tolerance_db=1.0):
    """
    Compare measured result to known reference.
    """
    ratio_db = 20 * np.log10(measured / reference)
    return np.abs(ratio_db) < tolerance_db
```

## Summary: Pre-Measurement Checklist

Before measuring:

1. [ ] Sample rate > 2.5× max frequency
2. [ ] Block size appropriate for resolution needed
3. [ ] Window function appropriate for signal type
4. [ ] Trigger settings verified (level, pre-trigger)
5. [ ] Input levels checked (no clipping)
6. [ ] Ground loops eliminated
7. [ ] Cables secured
8. [ ] Sensors not mass-loading structure
9. [ ] System at thermal equilibrium
10. [ ] Calibration verified

During measurement:

1. [ ] Monitor coherence (should be > 0.8 in band of interest)
2. [ ] Watch for double hits (impact testing)
3. [ ] Verify averaging is converging
4. [ ] Check for drift

After measurement:

1. [ ] Verify results make physical sense
2. [ ] Compare to previous measurements or predictions
3. [ ] Document conditions and settings
4. [ ] Save raw data for future reanalysis

## Related Topics

- [FFT Fundamentals](fft_fundamentals.md) - Understanding spectral analysis
- [Coherence Interpretation](coherence_interpretation.md) - Quality indicators
- [Uncertainty and Averaging](uncertainty_averaging.md) - Error reduction
