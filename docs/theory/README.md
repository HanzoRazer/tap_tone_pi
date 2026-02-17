# Theory of Operation

This directory contains educational documentation explaining the signal processing
concepts used in Tap Tone Pi. Understanding these fundamentals helps users interpret
results correctly and design effective measurement setups.

## Contents

| Document | Description |
|----------|-------------|
| [FFT Fundamentals](fft_fundamentals.md) | Windowing, frequency resolution, spectral leakage |
| [Coherence Interpretation](coherence_interpretation.md) | What coherence tells you about measurement quality |
| [Transfer Functions](transfer_function.md) | H1, H2, Hv estimators and when to use each |
| [Uncertainty and Averaging](uncertainty_averaging.md) | Why averaging matters, how many averages to use |
| [Common Measurement Errors](common_errors.md) | Pitfalls and how to avoid them |

## Quick Reference

### The Big Picture

When measuring acoustic or mechanical systems, we're trying to characterize how the
system responds to excitation. The key concepts are:

1. **Spectrum Analysis** - Breaking down a signal into its frequency components
2. **Transfer Function** - The ratio of output to input across frequency
3. **Coherence** - How linearly related the output is to the input
4. **Averaging** - Reducing random noise by combining multiple measurements

### Common Questions

**Q: Why do my peaks look smeared?**
A: Spectral leakage from improper windowing. See [FFT Fundamentals](fft_fundamentals.md).

**Q: Why is my coherence low at certain frequencies?**
A: Low signal-to-noise ratio or nonlinear behavior. See [Coherence Interpretation](coherence_interpretation.md).

**Q: Which transfer function estimator should I use?**
A: H1 for noise on output, H2 for noise on input, Hv for balanced noise. See [Transfer Functions](transfer_function.md).

**Q: How many averages do I need?**
A: Depends on coherence and acceptable error. See [Uncertainty and Averaging](uncertainty_averaging.md).

**Q: Why don't my results match the reference?**
A: Check for common setup errors. See [Common Measurement Errors](common_errors.md).

## Mathematical Notation

Throughout these documents:

- **X(f)** - Fourier transform of input signal x(t)
- **Y(f)** - Fourier transform of output signal y(t)
- **Gxx(f)** - Auto-spectral density of x (power spectrum)
- **Gyy(f)** - Auto-spectral density of y
- **Gxy(f)** - Cross-spectral density between x and y
- **H(f)** - Transfer function (frequency response)
- **γ²(f)** - Coherence (gamma-squared)
- **n** - Number of averages

## Further Reading

- Bendat & Piersol, "Random Data: Analysis and Measurement Procedures"
- Broch, "Mechanical Vibration and Shock Measurements"
- Harris, "Shock and Vibration Handbook"
- Randall, "Frequency Analysis"
