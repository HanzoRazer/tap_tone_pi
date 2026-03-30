# TTP Analyzer — Canonical Hardware Stack Specification

**Document status:** Authoritative design reference  
**Scope:** TTP Analyzer physical instrument (standalone acoustic measurement device)  
**Revision:** 1.1 — OPA1612 preamp stage added; tube preamp references removed

---

## Signal Chain (4-Stage)

```
[Mic] → [OPA1612 Balanced Mic-Pre] → [Unbalanced Line] → [HiFiBerry ADC] → [Pi 5] → [tap_tone_pi DSP]
```

No shortcuts. All four stages must be present and characterized in the per-unit calibration record.

---

## Stage 1 — Microphone

| Parameter | Spec |
|---|---|
| Type | Condenser (measurement-grade) or Dynamic |
| Output | Balanced XLR |
| Typical output level (tap tone) | −50 to −30 dBu |
| Phantom power | 48V (supplied by preamp stage) |

**Notes:** Mic selection directly affects frequency response floor. For tap-tone / ODS grid work, a small-diaphragm condenser with flat response through 10 kHz is preferred.

---

## Stage 2 — Preamplifier (OPA1612-Based)

### Design Selection Rationale

The TTP Analyzer is a **measurement instrument**, not a recording device. The preamp must be:

- Transparent (zero coloration)
- Low noise (< 1 µV input-referred)
- Flat frequency response (20 Hz – 20 kHz ± 0.5 dB)
- Matched to HiFiBerry ADC input range (0.8 – 2.1 Vrms for minimum distortion)

**Tube preamps are explicitly excluded.** THD of 0.5–2% from tube stages would corrupt tap-tone harmonic measurements. The OPA1612 achieves < 0.0001% THD — transparent to the ADC.

### Circuit (Single Channel — OPA1612 Dual Op-Amp)

```
XLR In (+) ──┬── R_in (1k) ──► U1A (+)
             │                       OPA1612 (half) — Non-inverting mic stage
XLR In (−) ──┴── R_in (1k) ──► U1A (−)  Gain = 1 + Rf/Rg = 1 + 100k/10k = 11× (+20.8 dB)
                                          Output: mic-level → ~0.1–1 Vrms
                                               │
                                               ▼
                                         U1B (+)
                                         OPA1612 (half) — Gain/buffer stage
                                         Switchable Rg: 10k / 3.6k
                                         Gain: 2× (switch open) to 5.7× (switch closed)
                                         = +6 to +15 dB trim
                                               │
                                               ▼
                                   Unbalanced RCA → HiFiBerry ADC
```

### Gain Staging

| Stage | Gain | dB |
|---|---|---|
| U1A (mic stage) | 11× | +20.8 dB |
| U1B (buffer, switch open) | 2× | +6.0 dB |
| U1B (buffer, switch closed) | 5.7× | +15.1 dB |
| **Total (low gain)** | **22×** | **+26.8 dB** |
| **Total (high gain)** | **63×** | **+35.9 dB** |

Target: Output to ADC stays in 0.8 – 2.1 Vrms sweet spot for lowest distortion.

### Key Specs (OPA1612)

| Parameter | Value |
|---|---|
| Input-referred noise | 1.1 nV/√Hz (< 1 µV across audio band) |
| THD+N | < 0.0001% |
| Gain-bandwidth product | 80 MHz |
| Supply voltage | ±12 V |
| Cost (production) | ~$5–8/unit |

### Phantom Power Supply

If using condenser mics, a standard 48V phantom power circuit is required upstream of U1A. Include a relay or switch to disable when using dynamic mics.

---

## Stage 3 — ADC / Audio Interface

**Selected:** HiFiBerry ADC (DAC+ ADC Pro or Studio ADC variant)

| Parameter | Spec |
|---|---|
| Interface | I²S → Pi 5 |
| Input range | ±3 V (AC-coupled, optimal 0.8–2.1 Vrms) |
| Sample rate | 44.1 / 48 / 96 kHz (configurable in tap_tone_pi) |
| Bit depth | 24-bit |
| Connector | RCA (unbalanced) from preamp stage |

**Note:** The ADC input is AC-coupled. Preamp output must not carry DC offset — the OPA1612 stage handles this by design.

---

## Stage 4 — Computing / DSP

**Selected:** Raspberry Pi 5

| Parameter | Spec |
|---|---|
| OS | Raspberry Pi OS (64-bit) |
| DSP engine | tap_tone_pi (Python / Cython compiled) |
| Server interface | FastAPI on port 8000 |
| Viewer output | viewer_pack_v1.json over USB or Ethernet |
| JACK / audio | HiFiBerry ALSA driver, JACK optional |
| Measured latency (capture → analysis) | ~3.1 ms (target) |

---

## Prototype vs. Production Hardware

| Phase | Preamp | Cost | Notes |
|---|---|---|---|
| Prototype | AliExpress OPA1612 module | ~$12–15 | Drop-in, verify gain staging and noise floor |
| Production | Custom PCB (same OPA1612 circuit) | ~$5–8 BOM | Optimized layout, matched components, proper shielding |

Custom board design proceeds after prototype validation confirms signal chain behavior matches calibration targets.

---

## Per-Unit Calibration Requirement

Because mic, preamp, and ADC each have tolerance-level differences, **every unit requires individual calibration** before shipping. The cal record is signed to the Pi 5 serial number and stored in `session_meta.json`. See `tap_tone_pi/calibration/` for the calibration workflow.

Calibration procedure covers:
- Amplitude offset (dBFS vs. acoustic reference)
- Frequency response (flat within ±0.5 dB, 80 Hz – 8 kHz)
- Latency (loopback measurement)
- Noise floor verification (> −80 dBFS required)

---

## Connector Summary

| Connection | Connector | Signal |
|---|---|---|
| Mic → Preamp | XLR female (panel) | Balanced, 48V phantom |
| Preamp → ADC | RCA or 3.5mm TRS | Unbalanced line, 0.8–2.1 Vrms |
| ADC → Pi 5 | I²S header (internal) | Digital |
| Pi 5 → PC/Viewer | USB-C or RJ45 | viewer_pack_v1.json |

---

## What This Document Is Not

This document specifies the signal chain for **acoustic measurement** (tap tone, ODS grid, frequency response). It does not cover:

- Smart Guitar signal chain (see Smart Guitar spec)
- Production Shop integration architecture (see viewer_pack_v1.schema.json)
- Software API (see tap_tone_pi FastAPI server docs)
