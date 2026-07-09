# TTP Analyzer — Canonical Hardware Stack Specification

**Document status:** Authoritative design reference  
**Scope:** TTP Analyzer physical instrument (standalone acoustic measurement device)  
**Revision:** 1.3 — Consolidated per-unit calibration coverage and scope-boundary
section from the superseded root-level copy (`HARDWARE_STACK_SPEC.md`, now
removed); earlier (1.2): gain staging corrected for self-excitation
architecture, calibration loop documented, speaker excitation path added

---

## Measurement Architecture

The TTP Analyzer operates in two distinct measurement modes with different
excitation sources. This distinction drives every gain staging decision.

```
Phase 1 — Impulse tap (single channel)
  [Operator tap] → [Plate] → [Mic] → [OPA1612 pre] → [HiFiBerry ADC] → [Pi 5]
                                                                         analyze_tap()

Phase 2 — Speaker-driven ODS (two channel, 35-point grid)
  [Pi 5]──signal_gen──► [DAC+Amp] → [Speaker] → [Plate] → [Ref mic ch0]──┐
                                                          → [Roving mic ch1]──► [HiFiBerry 2-ch ADC] → [Pi 5]
                                                                                                        H(f), γ²(f)
```

**Key architectural property of Phase 2:** The Pi is both source and sink.
Output level is controlled in software via `signal_gen`. If the ADC input is
too quiet, the speaker drive level is increased. The "unknown source level"
problem that affects tap-tone impulse work does not apply to speaker-driven ODS.

---

## Signal Chain (4-Stage)

```
[Mic] → [OPA1612 Balanced Mic-Pre] → [Unbalanced Line] → [HiFiBerry ADC] → [Pi 5] → [tap_tone_pi DSP]
```

All four stages must be present and characterized in the per-unit calibration
record before any session is accepted by the software.

---

## Stage 1 — Microphone

| Parameter | Spec |
|---|---|
| Type | Small-diaphragm condenser (preferred) or dynamic |
| Output | Balanced XLR |
| Phantom power | 48V (Phase 2 / condenser), switchable off for dynamic |
| Sensitivity (typical SDC) | −40 dBV/Pa |
| Output at 75 dB SPL (typical bench tap) | ~1.1 mVrms |
| Output at 85 dB SPL (loud bench tap) | ~3.6 mVrms |

**Note:** Mic frequency response is the one error source the calibration loop
cannot correct. For Phase 2 ODS comparisons across sessions, use the same
microphone or characterize each mic separately.

---

## Stage 2 — Preamplifier (OPA1612-Based)

### Design Selection Rationale

The TTP Analyzer is a **measurement instrument**, not a recording device.
The preamp must be transparent — zero coloration:

- Input-referred noise < 1 µV
- THD < 0.0001% (OPA1612 spec)
- Flat response 20 Hz – 20 kHz ± 0.5 dB

**Tube preamps are explicitly excluded.** THD of 0.5–2% from tube stages
corrupts tap-tone harmonic measurements. The OPA1612 achieves < 0.0001% THD.

### Corrected Circuit (Single Channel — OPA1612 Dual Op-Amp)

```
XLR In (+/−) ──► U1A — Non-inverting mic stage
                       Rf = 100k, Rg = 10k
                       Gain = 1 + 100k/10k = 11× (+20.8 dB)
                               │
                               ▼
                         U1B — Gain/buffer stage
                         3-position switch on Rg:
                         POS 1  Rf=100k, Rg=14k  →  8.1×  (+18.2 dB)
                         POS 2  Rf=470k, Rg=14k  →  34.6× (+30.7 dB)
                         POS 3  Rf=1M,   Rg=10k  →  101×  (+40.1 dB)
                               │
                               ▼
                   Unbalanced line → HiFiBerry ADC
```

### Corrected Gain Staging

The HiFiBerry ADC sweet spot is **0.8–2.1 Vrms**. Target: 1.0 Vrms at the
ADC for best dynamic range.

| Switch | U1B gain | Total gain | dB | Phase 1: ADC level at 85 dB SPL | Phase 1: ADC level at 75 dB SPL |
|---|---|---|---|---|---|
| LOW | 8.1× | 89× | +39 dB | 320 mVrms ⚠ low | 98 mVrms ⚠ low |
| MID | 34.6× | 381× | +52 dB | **1.37 Vrms ✅** | 0.42 Vrms ⚠ low |
| HIGH | 101× | 1111× | +61 dB | 4.0 Vrms ⚠ clips | **1.22 Vrms ✅** |

**Default switch position: HIGH** for condenser mic + typical bench tap.
**MID** for close-mic loud taps or dynamic mic.
**LOW** for very loud/close sources only.

For Phase 2 speaker-driven ODS: switch position is irrelevant to measurement
accuracy — the Pi adjusts software output level so the ADC receives ~1.0 Vrms.
Use MID as a neutral starting point.

### Why the Original Gain Was Wrong

The v1.0 and v1.1 hardware docs specified U1B at 2–5.7× gain (total 22–63×,
+27 to +36 dB). This was calculated for an assumed "loud workshop tap" at
85 dB SPL producing ~3.6 mVrms at the mic. At 22× total gain, the ADC would
receive only 79 mVrms — roughly 20 dB below the sweet spot floor.

The corrected design targets 1.0 Vrms by providing +52 to +61 dB total gain,
matched to actual condenser mic output levels at realistic tap SPLs.

### OPA1612 Key Specs

| Parameter | Value |
|---|---|
| Input-referred noise | 1.1 nV/√Hz |
| THD+N | < 0.0001% |
| Bandwidth | 80 MHz GBW |
| Supply | ±12V |
| Cost (production PCB) | ~$5–8/unit |

### Phantom Power

A standard 48V phantom supply is required for condenser mics. Include a
latching relay or DIP switch to disable when using dynamic mics.

---

## Stage 3 — ADC / Audio Interface

**Selected:** HiFiBerry DAC+ ADC Pro (or Studio ADC variant)

| Parameter | Spec |
|---|---|
| Interface to Pi | I²S header (internal) |
| Input range | ±3 V AC-coupled, optimal **0.8–2.1 Vrms** |
| Sample rate | 44.1 / 48 / 96 kHz (configured in tap_tone_pi) |
| Bit depth | 24-bit |
| Input connector | RCA (unbalanced) from preamp |
| Channels | 2 (ch0 = reference, ch1 = roving for Phase 2) |

The ADC is AC-coupled. The OPA1612 output must not carry DC offset —
the circuit handles this by design (op-amp DC offset < 1 mV typical).

---

## Stage 4 — Computing / DSP

**Selected:** Raspberry Pi 5

| Parameter | Value |
|---|---|
| OS | Raspberry Pi OS 64-bit |
| DSP engine | tap_tone_pi (Python / Cython) |
| Signal generation | `tap_tone_pi.signal_gen` — chirp, sweep, sine |
| Playback | `sd.playrec()` via sounddevice (simultaneous I/O) |
| FastAPI server | port 8000 |
| Viewer output | `viewer_pack_v1.json` over USB or Ethernet |
| Phase 2 latency | ~3.1 ms (capture → analysis) |

---

## Self-Calibration Loop

Every TTP unit calibrates itself before use. No external equipment is required.

```
Pi signal_gen → DAC → OPA1612 → HiFiBerry ADC → Pi
  emit -20 dBFS    (loopback)                   measure what arrived
  reference tone                                 compute cal_offset_db
```

**What the cal loop corrects:**

| Error source | Typical magnitude | After calibration |
|---|---|---|
| Resistor tolerance in Rf/Rg (±1%) | ±0.2 dB | Corrected to < 0.05 dB |
| Op-amp gain variation across units | ±0.5 dB | Corrected |
| ADC full-scale variation (unit-to-unit) | ±0.3 dB | Corrected |
| Temperature drift (session-level) | ±0.5 dB | Corrected at session start |

**What the cal loop cannot correct:**

| Error source | Mitigation |
|---|---|
| Mic frequency response (unit-to-unit variation) | Use matched mics or per-mic characterization |
| Speaker-to-plate coupling variation (Phase 2) | Standardized placement fixture |
| Environmental noise floor | Coherence gate (γ² < 0.7 = retry) |

**Calibration command:** `ttp calibrate tone --device 0`

`cal_offset_db` is stored in `~/.tap_tone_pi/calibration/device_0.json`
and injected into every session's `session_meta.json` automatically.
The Phase 2 capture CLI refuses to start a session without a valid calibration
record (≤ 30 days old). Use `--force` for stale, `--force-uncalibrated` for
development/synthetic testing only.

### Per-Unit Calibration Requirement

Because mic, preamp, and ADC each have tolerance-level differences, **every unit
requires individual calibration** before shipping. The cal record is signed to
the Pi 5 serial number and stored in `session_meta.json`. See
`tap_tone_pi/calibration/` for the calibration workflow.

The calibration procedure covers:

- Amplitude offset (dBFS vs. acoustic reference)
- Frequency response (flat within ±0.5 dB, 80 Hz – 8 kHz)
- Latency (loopback measurement)
- Noise floor verification (> −80 dBFS required)

---

## Prototype vs. Production Hardware

| Phase | Preamp hardware | Cost | Notes |
|---|---|---|---|
| Prototype | AliExpress OPA1612 module | ~$12–15 | **Fixed gain only** — verify output level meets ADC sweet spot |
| Production | Custom 2-stage PCB (OPA1612, 3-position switch) | ~$8–12 BOM | Matched Rf/Rg values from corrected table above |

**Important for prototype:** AliExpress OPA1612 modules typically provide
+20–30 dB gain (mic stage only). To reach the corrected +52–61 dB target,
you need either:
1. A second gain stage board in series, or
2. Build the 2-stage circuit on breadboard using the values in Stage 2 above

---

## Connector Map

| Connection | Connector | Signal |
|---|---|---|
| Mic → Preamp | XLR female (panel mount) | Balanced, 48V phantom |
| Preamp → ADC | RCA or 3.5mm TRS | Unbalanced, 0.8–2.1 Vrms |
| ADC → Pi 5 | 40-pin I²S header (internal) | Digital |
| Pi 5 → DAC/Amp (Phase 2) | 3.5mm TRS or GPIO I²S | Digital or analog |
| Pi 5 → PC/Viewer | USB-C or RJ45 | viewer_pack_v1.json |

---

## Speaker Driver (Phase 2 Only)

For ODS grid measurements, the Pi drives a small full-range speaker placed
approximately 30 cm from the plate surface.

| Parameter | Requirement |
|---|---|
| Frequency range | 30–2000 Hz (−3 dB) |
| SPL at 30 cm | > 80 dB (needs ~5–10W at 1m spec) |
| Distortion (THD) | < 1% in measurement band |
| Connection | Pi DAC output → Class-D amp → speaker |
| Software level | Adjusted by `signal_gen` until ADC input ≈ 1.0 Vrms |

Suitable low-cost options: Dayton Audio RS100, Tang Band W3-593SF.
The speaker is not part of the measurement chain — it excites the plate.
Nonlinear distortion in the speaker is rejected by the coherence function
(γ²(f) drops at frequencies where output is not linearly related to input).

---

## What This Document Is Not

This document specifies the signal chain for **acoustic measurement** (tap tone,
ODS grid, frequency response). It does not cover:

- Smart Guitar signal chain (see Smart Guitar spec)
- Production Shop integration architecture (see `viewer_pack_v1.schema.json`)
- Software API (see tap_tone_pi FastAPI server docs)

---

## Change History

| Rev | Date | Change |
|---|---|---|
| 1.0 | 2026-03-30 | Initial document — 4-stage signal chain, OPA1612 preamp |
| 1.1 | 2026-03-30 | Tube preamp removed; OPA1612 declared canonical |
| 1.2 | 2026-03-30 | Gain staging corrected (+39/+52/+61 dB 3-position switch); self-excitation architecture documented; calibration loop section added; speaker driver section added |
| 1.3 | 2026-07-08 | Merged unique sections from the superseded `HARDWARE_STACK_SPEC.md` (per-unit calibration coverage, "What This Document Is Not" scope boundary); removed the duplicate |
