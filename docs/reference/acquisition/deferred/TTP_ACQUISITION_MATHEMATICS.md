# TTP Analyzer — Acquisition and Uncertainty Mathematics

**Document class:** Technical reference, intended for the main body.
**Status:** Assembled from working sessions. **Not yet source-verified.**
**Purpose:** state every relation used in the acquisition and uncertainty chain
once, with its symbols, assumptions, validity range, provenance class, and the
code that implements it — so that a reviewer can check the mathematics without
reading the source, and so that the source cannot drift from the mathematics
without the drift being visible.

---

## 0 · How to read this document

Every relation carries five fields. A relation missing any of them is not ready
for the main body.

| Field | Means |
|---|---|
| **Statement** | The equation, in stated symbols |
| **Validity** | The conditions under which it holds, and where it fails |
| **Class** | `STANDARD` (established, citable) · `VENDOR` (manufacturer application note) · `CONVENTION` (engineering practice, not derived) · `SESSION` (derived in working sessions, not checked against literature) |
| **Source** | Where it comes from, or "requires citation" |
| **Code** | The implementing function |

**Provenance warning.** `STANDARD` and `VENDOR` classes below are asserted from
working sessions, not from a literature review. Every one requires a primary
source before this document enters peer review. Section 9 lists the specific
items where the risk is highest.

---

## 1 · Symbols

| Symbol | Quantity | Unit |
|---|---|---|
| `f_in` | analog input frequency | Hz |
| `f_s` | sample rate | Hz |
| `N` | FFT record length, samples | — |
| `M` | integer input cycles per record | — |
| `T` | record length, `N / f_s` | s |
| `Δf` | FFT bin width, `f_s / N = 1/T` | Hz |
| `t_j` | RMS sampling jitter | s |
| `t_ap` | ADC intrinsic aperture jitter | s |
| `t_clk` | external clock jitter at the ADC clock pin | s |
| `n` | converter resolution | bits |
| `SNR_q` | quantization-limited SNR | dB |
| `SNR_th` | converter thermal SNR (datasheet) | dB |
| `SNR_j` | jitter-limited SNR | dB |
| `SNR_fe` | front-end-limited SNR | dB |
| `e_n` | input-referred noise density | V/√Hz |
| `G` | voltage gain (linear) | — |
| `B` | operating-level backoff below full scale | dB |
| `ε` | fractional clock frequency error | — (ppm × 10⁻⁶) |
| `Q` | quality factor of a resonance | — |
| `τ` | resonance time constant | s |
| `E` | longitudinal elastic modulus | Pa |
| `ρ` | density | kg/m³ |
| `L` | characteristic plate dimension | m |
| `h` | plate thickness | m |
| `ν` | Poisson's ratio | — |
| `L(f)` | SSB phase noise density | dBc/Hz |
| `φ` | RMS phase error | rad |

**Sign and reference conventions.** All SNR values are positive dB, referenced to
a full-scale sine unless explicitly stated as signal-referred. All jitter values
are RMS, not peak-to-peak. All uncertainties are standard uncertainties (k = 1)
unless a coverage factor is stated.

---

## 2 · Stage 3 — noise budget

### (2.1) Quantization-limited SNR

**Statement**

```
SNR_q = 6.02 n + 1.76        [dB]
```

**Validity** — ideal uniform quantizer, full-scale sine input, noise measured
over the full Nyquist band. Understates achievable SNR when oversampling and
decimation are used, which is the normal case for a sigma-delta converter, so
this term is generally not the limiter in this instrument.
**Class** `STANDARD` · **Source** requires citation (any data-conversion text)
· **Code** `quantization_snr_db()`

### (2.2) Jitter-limited SNR

**Statement**

```
SNR_j = −20 log₁₀(2π f_in t_j)        [dB]
```

**Validity** — full-scale sine at `f_in`; jitter uncorrelated, zero-mean,
Gaussian. **Fails for deterministic timing error.** A fractional-N clock produces
discrete spurs, not broadband noise; applying this relation to a spur understates
its perceptual and spectral impact. See (2.4) and §8.
**Class** `STANDARD` · **Source** requires citation (Kester / ADI)
· **Code** `jitter_snr_db()`

### (2.3) Front-end-limited SNR

**Statement**

```
V_n  = e_n · √BW · G            [V rms]
SNR_fe = 20 log₁₀(V_fs / V_n)   [dB]
```

**Validity** — white input-referred noise across `BW`; gain flat across `BW`;
`V_fs` expressed as RMS for a full-scale sine. Ignores 1/f noise, which for an
audio-band measurement extending to 20 Hz is a real omission and a known gap.
**Class** `STANDARD` · **Source** requires citation
· **Code** `FrontEndSpec.snr_db()`

### (2.4) Combination of independent noise terms

**Statement**

```
10^(−SNR_total/10) = Σᵢ 10^(−SNRᵢ/10)
```

**Validity** — terms statistically independent and additive in power. **Fails
when any term is a discrete spur** or is correlated with another term. This is
the single most abused relation in the set; §8 states the guard.
**Class** `STANDARD` · **Code** `combine_snr_db()`

### (2.5) Total sampling jitter

**Statement**

```
t_j,total = √(t_ap² + t_clk² + t_dist² + t_PLL²)
```

reducing, when the clock is characterized **at the ADC clock pin**, to

```
t_j,total = √(t_ap² + t_clk,at-ADC²)
```

**Validity** — contributors independent and random. Measurement location is part
of the definition: a figure taken at the oscillator output is not `t_clk,at-ADC`
and understates the total.
**Class** `VENDOR` · **Source** requires citation (TI SNAA334)
· **Code** `noise_budget()` via `rss()`

### (2.6) Jitter allowance from an SNR target ★

**Statement**

Feasibility gate first:

```
SNR_ADC > SNR_target        (else no clock reaches the target)
```

then

```
r_j       = 10^(−SNR_target/10) − 10^(−SNR_ADC/10)
t_j,max   = √r_j / (2π f_in)
t_ext,max = √(t_j,max² − t_ap²)
```

**Validity** — requires `SNR_ADC` measured or specified at low input frequency
and at the same amplitude, so that it genuinely excludes jitter.

**Why the subtraction matters.** Omitting the `SNR_ADC` term assumes a noiseless
converter and inflates the allowance. The error is negligible far from the
converter's capability and severe near it:

| SNR target | SNR_ADC | Naive `t_j` | Corrected `t_j` |
|---|---|---|---|
| 85 dB | 110 dB | 47.9 ns | 47.8 ns |
| 105 dB | 110 dB | 4.79 ns | 3.96 ns |
| 109 dB | 110 dB | 3.02 ns | 1.37 ns |
| 110.5 dB | 110 dB | 2.54 ns | infeasible |

*(Computed at `f_in` = 187 Hz. The ratio is independent of `f_in`.)*

**Class** `VENDOR` · **Source** requires citation (TI SNAA334)
· **Code** `jitter_allowance_s()` — **pending, patch #2.** The current
`jitter_budget_s()` implements the naive form and must not be used for
allocation.

### (2.7) Operating-level backoff ★

**Statement** — for a signal `B` dB below full scale, referred to the signal:

```
SNR_j(signal-referred)   = SNR_j                 (unchanged)
SNR_q, SNR_th, SNR_fe    = SNR − B               (degraded one-for-one)
```

**Validity** — jitter error voltage is `2π f_in A t_j`, proportional to signal
amplitude `A`, so jitter noise scales with the signal and the ratio is preserved.
Quantization, thermal, and front-end noise are additive and fixed, so the ratio
degrades with backoff.

**Consequence for this instrument.** Neither channel operates at full scale:

| Channel | Level | Backoff | Additive terms lose |
|---|---|---|---|
| ch0 force, 0.5 N peak, +32 dB PGA | 1.58 V rms | −2.5 dBFS | 2.5 dB |
| ch0 force, 0.05 N peak, +32 dB PGA | 0.158 V rms | −22.5 dBFS | 22.5 dB |
| ch1 mic, MID @ 85 dB SPL | 1.37 V rms | −3.7 dBFS | 3.7 dB |
| ch1 mic, MID @ 75 dB SPL | 0.42 V rms | −14.0 dBFS | 14.0 dB |

A full-scale budget is a best case that neither channel occupies. This relation
is also the theoretical basis for test **T8**, which distinguishes additive from
multiplicative noise by sweeping amplitude.

**Class** `VENDOR` · **Source** requires citation
· **Code** pending, patch #2

---

## 3 · Jitter measurement and bounding

### (3.1) Two-tone aperture jitter extraction

**Statement**

```
r_j       = 10^(−SNR_HF/10) − 10^(−SNR_LF/10)
t_j,total = √r_j / (2π f_in,HF)
t_ap      = √(t_j,total² − t_clk²)        only when t_j,total > t_clk
```

`f_in,HF` is the **actual coherent frequency** from (4.1), never the nominal
target.

**Validity** — both captures share `f_s`, `N`, clock route, drive level, and FFT
analysis rules. Source phase noise must be demonstrably below the system under
test. Requires `f_in,HF` high enough to lift the jitter term clear of the
converter floor — typically 0.3–0.45 `f_s` on an RF part.

**Not applicable to this instrument.** See (3.2).
**Class** `VENDOR` · **Source** requires citation (ADI AN-501, TI SLWA036)

### (3.2) In-band jitter bound, and why aperture jitter is unmeasurable here ★

**Statement** — assuming pessimistically that all observed noise is jitter noise:

```
t_j ≤ 10^(−SNR_obs/20) / (2π f_in)
```

**Result for the TTP Analyzer.** At `f_in` = 187 Hz with an observed 90.6 dB, the
bound is **25.2 ns** — roughly four orders of magnitude above any plausible value,
establishing nothing.

**Consequence.** (3.1) cannot be run in the audio band, and (3.2) is the only
bound obtainable. Therefore `ConverterSpec.aperture_jitter_s` is tagged
`BOUNDED`, no E0 test is scheduled for it, and the justification of record is the
73.9 dB of headroom in (2.2) rather than a measurement.

**Class** `SESSION` · **Code** `jitter_bound_from_snr()`

### (3.3) Phase noise to jitter

**Statement**

```
φ² = 2 ∫[f_L → f_H] 10^(L(f)/10) df        [rad²]
t_j = φ / (2π f_s)                          [s]
```

**Validity** — integrate in **linear** units over each offset segment; dBc/Hz
values are never averaged or summed directly. The factor 2 converts single-
sideband to total. The carrier is the **sample clock** `f_s`, not `f_in`.

**Corollary, and the reason this relation is in the document.** A jitter figure
is incomplete without `f_L`, `f_H`, and the carrier. A vendor claim of a
"low-jitter clock" carrying none of the three is not a quantity and cannot enter
a budget.

**Class** `VENDOR` · **Source** requires citation
· **Code** `phase_noise_to_jitter()` — pending, patch #2

---

## 4 · Coherent sampling

### (4.1) Coherence condition

**Statement**

```
f_in = (M / N) · f_s        with gcd(M, N) = 1
Δf   = f_s / N
```

For `N = 2^m`, `gcd(M, N) = 1` reduces to **M odd**.

**Validity** — requires the source and the sampling clock to share a frequency
reference. Entering calculated frequencies into two free-running instruments does
not achieve coherence over a long rectangular-window capture.

**Applicability in this instrument.** The DAC and ADC share one board oscillator,
so every **loopback** test achieves exact coherence with no external reference.
**T4 alone requires an external source and therefore cannot be coherent**; it runs
windowed, and its results carry leakage error accordingly.

Worked, at `f_s` = 48 kHz and `N` = 65536 (`Δf` = 0.732421875 Hz, `T` = 1.3653 s):

| Target | M (odd) | Actual `f_in` |
|---|---|---|
| 187 Hz | 255 | 186.767578125 Hz |
| 1 kHz | 1365 | 999.755859375 Hz |
| 5 kHz | 6827 | 5000.244140625 Hz |
| 10 kHz | 13653 | 9999.755859375 Hz |
| 20 kHz | 27307 | 20000.244140625 Hz |

**Class** `VENDOR` · **Source** requires citation (ADI AN-835)

### (4.2) SNR integration convention

**Statement** — for a coherent capture with a rectangular window:

```
Exclude: DC · bin M · mirror bin N−M · harmonics 2M, 3M, … folded mod N
P_N   = Σ remaining in-band bins
SNR   = 10 log₁₀(P_signal / P_N)
```

**Validity** — the carrier-bin exclusion rule and the integration bandwidth must
be identical at every test frequency, or frequency-dependent comparisons are
meaningless. Under genuine coherence no window is applied; a non-rectangular
window spreads main-lobe energy for no benefit.

**Class** `CONVENTION` — the choice of exclusion rule is a convention, and the
requirement that it be held constant is what makes results comparable.

---

## 5 · Stage 5 and 7 — frequency uncertainty

### (5.1) Clock frequency error

**Statement**

```
Δf_clock = f · ε              where ε = ppm × 10⁻⁶
```

**Validity** — systematic, not random. Scales every measured frequency by the
same fraction, so it does not average out across repeats. Distinct from jitter in
(2.2): accuracy sets the frequency scale, jitter sets the noise floor.
**Class** `STANDARD` · **Code** `frequency_budget()`

### (5.2) Spectral resolution

**Statement**

```
Δf_bin = f_s / N = 1 / T
```

**Class** `STANDARD` · **Code** `CaptureSpec.bin_width_hz()`

### (5.3) Estimator floor — single-tone frequency Cramér–Rao bound ⚠

**Statement, as implemented**

```
σ_f = (1 / (π T)) · √(6 / (SNR_lin · N))
```

**⚠ KNOWN DISCREPANCY — resolve before peer review.** The large-`N` asymptotic
form of the Rife–Boorstyn bound is commonly written

```
σ_f = √(6 / (SNR_lin · N)) / (2π T)
```

which is a **factor of two smaller** than the implemented form. The discrepancy
plausibly arises from real-versus-complex sinusoid conventions and from how
`SNR_lin` is defined (per-sample versus total, amplitude versus power). The
implemented form is the conservative one, so no claim built on it is
overstated — but the constant must be fixed against a primary source and the SNR
convention stated explicitly before this document is submitted.

**Validity in any form** — a lower bound achieved only by an efficient estimator
at high SNR. It is not an achieved uncertainty and must never be reported as one.
For this instrument it evaluates to ~10⁻⁸ Hz, which is a useful result precisely
because it proves the estimator is not the limitation.

**Class** `STANDARD` · **Source** requires citation (Rife & Boorstyn 1974)
· **Code** `frequency_budget()`

### (5.4) Combined frequency uncertainty

**Statement**

```
u(f) = √( Δf_clock² + σ_f² + u_phys² )
```

where `u_phys` is measured session-to-session repeatability including remounting,
recoupling, and environmental variation.

**Validity** — terms independent. **`u_phys` is not derivable and must be
measured.** A budget omitting it is an electronic lower bound and must not be
quoted as measurement uncertainty. In every case examined this session, `u_phys`
is expected to dominate the other two by orders of magnitude.

**Class** `STANDARD` · **Code** `frequency_budget()`

---

## 6 · Stage 1 — swept excitation limits

### (6.1) Resonance time constant and dwell

**Statement**

```
τ         = Q / (π f)
t_dwell   ≥ k · τ,     k = 3 for ≈95% settling
```

**Class** `STANDARD` for `τ`; `CONVENTION` for `k`
· **Code** `compute_sweep_limits()`

### (6.2) Maximum sweep rate

**Statement**

```
BW_3dB  = f / Q
R_max   = BW_3dB² / S,     S = safety factor, default 4
```

**Validity** — the criterion that sweep rate must be small compared with the
square of the half-power bandwidth is established swept-sine practice. **The
safety factor `S` is a convention, not derived.** Exceeding `R_max` causes the
measured peak to shift, broaden, and read low in amplitude — a failure that
resembles specimen variation rather than instrument error, which is what makes it
dangerous.

**Result for this instrument.** At 187 Hz with `Q` = 50: `BW_3dB` = 3.74 Hz,
`R_max` = 3.5 Hz/s, minimum dwell 255 ms, and a 60–2000 Hz sweep requires **555 s
minimum**. Nothing in the stack specification currently constrains sweep rate.

**Sensitivity.** `Q` is the binding parameter and is currently `PROPOSED` at 50.
If the true `Q` is higher, these limits are optimistic.

**Class** `STANDARD` with `CONVENTION` factor · **Source** requires citation

---

## 7 · Stage 7 — propagation to the decision

### (7.1) Plate frequency scaling

**Statement** — thin-plate flexure, `D = E h³ / (12(1−ν²))`, areal mass `ρh`:

```
f ∝ (1 / L²) √(D / ρh) = (h / L²) √( E / (12(1−ν²) ρ) )
```

hence

```
E ∝ f² L⁴ ρ / h²
```

**Validity** — the **exponents are exact** for a fixed mode shape, boundary
condition, aspect ratio, and `ν`. The **proportionality constant is not**, and it
absorbs all of those. This relation therefore supports uncertainty *propagation*
and relative comparison, and does not by itself yield absolute `E` without the
mode-specific constant.

**Class** `STANDARD` · **Source** requires citation (plate theory)

### (7.2) Modulus uncertainty propagation ★

**Statement** — from (7.1) by standard propagation:

```
u(E)/E = √( (2 u(f)/f)² + (4 u(L)/L)² + (u(ρ)/ρ)² + (2 u(h)/h)² )
```

**Sensitivity coefficients are the finding.** Length enters to the **fourth**
power and thickness to the **second**. Worked for a representative spruce plate:

| Term | Contribution |
|---|---|
| thickness | 1.429 % |
| density | 0.952 % |
| length | 0.400 % |
| frequency | 0.004 % |
| **combined** | **1.763 %** |

The dominant term is dimensional, not electronic. No improvement to the
acquisition chain reduces it.

**Class** `STANDARD` · **Code** `modulus_budget()`

### (7.3) Discrimination threshold

**Statement** — two independent measurements are distinguishable when their
difference exceeds the combined uncertainty:

```
ΔE_min / E = √2 · u(E)/E
```

**Validity** — `k` = 1, giving roughly 68% confidence. A publication claim should
state the coverage factor and will typically use `k` = 2, doubling the threshold.
**This is the relation that terminates the chain in the unit of the decision.**

For the representative plate: **2.49 %** at `k` = 1.

**Class** `STANDARD` · **Code** `modulus_budget()`

### (7.4) Force at sensor versus force at specimen

**Statement**

```
F_specimen ≈ F_sensor − m_downstream · a
```

where `m_downstream` is the mass between the transducer sensing plane and the
specimen — the lower transducer half, the stinger, and the contact tip.

**Validity** — first order, and valid only while the downstream assembly behaves
as a **rigid lumped mass**. Above that band the assembly is itself a dynamic
system and simple subtraction is inadequate; a dynamic transfer correction is
then required. The frequency at which the lumped approximation fails is an E1
deliverable, not an assumption.

**Unresolved.** Applying the correction requires `a`, the drive-point
acceleration. Phase 2B allocates ch0 to force and ch1 to the microphone and the
converter has two channels, so **`a` is not measured and the correction cannot be
applied.** Three admissible responses, all requiring evidence: bound
`m_downstream` small enough that the uncorrected error falls below the
uncertainty claim; bound the error analytically and carry it as an uncertainty
term; or add a channel.

**Class** `STANDARD` · **Source** requires citation (experimental modal analysis)

### (7.5) Reciprocity

**Statement**

```
H_ij = H_ji
```

**Validity** — linear, time-invariant, reciprocal structure. Justifies obtaining
spatial data by roving the microphone with a fixed exciter rather than roving the
exciter, which avoids per-position mass-loading variance. **Fails** if the
structure is driven into nonlinearity, or if the exciter's mass loading differs
between configurations — which is exactly the reason to fix the exciter.

**Class** `STANDARD` · **Source** requires citation

---

## 8 · Standing guards

Relations that are false in stated circumstances. Each has been violated at least
once during this session's working documents.

| Guard | Statement |
|---|---|
| **G1 — Spurs are not jitter** | (2.4) and (2.5) require independent random terms. A discrete spur from a fractional-N clock or a switching supply must not be RSS'd into a broadband total; it is reported as SFDR against a spur mask. A clean SNR does not imply a clean spectrum. |
| **G2 — Full scale is not the operating point** | A budget computed at full scale is a best case. Apply (2.7) at the actual level before quoting any uncertainty. |
| **G3 — Aliasing, RF demodulation, and jitter are three mechanisms** | They have different magnitudes, frequency dependence, and mitigations. Do not merge them into one requirement or one error term. |
| **G4 — Filter phase cancels only when common** | In a two-channel transfer measurement, filter phase common to both channels cancels; phase that differs does not and enters `H(f)` directly. Separately built channel filters must be phase-matched or the mismatch characterized. |
| **G5 — Loopback measures two converters** | Any loopback figure is the DAC and ADC in series. Only an input-shorted measurement isolates the converter. |
| **G6 — Use the actual coherent frequency** | Every `f_in`-dependent relation takes the exact value from (4.1), never the nominal target. |
| **G7 — A jitter figure needs its integration limits** | Per (3.3), a value without `f_L`, `f_H`, and carrier is not a quantity. |
| **G8 — Bounds are not measurements** | (3.2) and (5.3) are bounds. Neither may be reported as an achieved value. |

---

## 9 · Open items before peer review

1. **(5.3) factor-of-two discrepancy.** Highest priority. Fix the constant and
   state the SNR convention explicitly.
2. **Primary sources.** Every `STANDARD` and `VENDOR` relation currently asserts
   its source class without a citation. All require one.
3. **(2.3) omits 1/f noise.** Real for a measurement band extending to 20 Hz.
   Either add the term or state the omission and its magnitude.
4. **(6.2) safety factor.** `S` = 4 is unjustified. Either derive it from an
   acceptable peak-amplitude error or record it as an explicit convention with a
   stated consequence.
5. **(7.1) proportionality constant.** Absent, so absolute `E` is not obtainable
   from this document alone. State where the mode-specific constant comes from.
6. **(7.4) unresolved correction.** Section 7.4 states a correction that cannot
   currently be applied. The chosen response must be recorded before any
   force-normalized result is published.
7. **Coverage factor.** Section 7.3 uses `k` = 1 throughout. Fix a convention for
   the whole document and apply it uniformly.

---

## 10 · Code cross-reference

| Relation | Function | Module |
|---|---|---|
| 2.1 | `quantization_snr_db()` | `acquisition_budget.py` |
| 2.2 | `jitter_snr_db()` | ″ |
| 2.3 | `FrontEndSpec.snr_db()` | ″ |
| 2.4 | `combine_snr_db()` | ″ |
| 2.5 | `rss()`, `noise_budget()` | ″ |
| 2.6 | `jitter_allowance_s()` | **pending, patch #2** |
| 2.7 | operating-level derating | **pending, patch #2** |
| 3.2 | `jitter_bound_from_snr()` | ″ |
| 3.3 | `phase_noise_to_jitter()` | **pending, patch #2** |
| 4.1 | coherent bin selection | **pending, patch #2** |
| 5.1–5.4 | `frequency_budget()` | ″ |
| 6.1–6.2 | `compute_sweep_limits()` | ″ |
| 7.2–7.3 | `modulus_budget()` | ″ |

A relation in this document with no implementing function, or a function
implementing a relation not in this document, is a defect in one or the other.
