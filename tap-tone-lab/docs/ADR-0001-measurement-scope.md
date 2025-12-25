# ADR-0001: Measurement Scope, Protocol, and Integration Boundaries

**Status:** Accepted  
**Date:** 2025-03-08  
**Context:** Tap-Tone Measurement Node / Workstation  
**Decision Drivers:** Repeatability, scientific validity, future extensibility, avoidance of premature optimization

## Decision

### 1. Measurement Protocol (Phase 1)
A minimal but explicit v0.1 measurement protocol SHALL be documented and followed in Phase 1.

Protocol MUST specify:
- Tap tool (consistent mass)
- Tap location(s) (named)
- Mic type (USB measurement mic or XLR + interface)
- Mic placement (distance + angle)
- Environment (quiet + consistent support/fixture)
- Gain target (avoid clipping; RMS in nominal range)

Phase 1 SHALL NOT remain "unspecified."

### 2. Multi-Channel Capture Priority
Phase 1 (single-channel) is a hard gate and MUST be completed before multi-channel development.

Phase 1 complete only when:
- Artifact outputs stable (WAV/JSON/CSV)
- Repeat taps produce bounded variance
- v0.1 protocol written and used

Phase 2 (2-channel) is the first expansion enabling delay/correlation/coherence.

### 3. DSP Techniques and Algorithm Porting
Phase 1 DSP includes:
- FFT magnitude spectrum
- Peak detection with bounds/spacing
- RMS + clipping detection

Approved future ports (post Phase 1):
- Parabolic peak interpolation
- Improved prominence/guardrail logic

DSP additions MUST be standalone + tested on fixed WAV fixtures.

### 4. RMOS / ToolBox Integration Boundary
Direct RMOS integration is deferred. Phase 1 outputs MUST be forward-compatible.

Each capture SHALL produce:
- audio.wav
- analysis.json
- spectrum.csv
- session.jsonl

analysis.json MUST include:
- ts_utc, label, sample_rate
- dominant_hz, peaks[]
- rms, clipped, confidence

No design optimization, modal labeling, or structural recommendations at this layer.

## Rationale
- Repeatability beats cleverness.
- Single-channel truth precedes spatial inference.
- Naming algorithms prevents reinvention.
- Measurement ≠ interpretation.
- Artifacts are the product.

## Consequences
- Small/testable Phase 1.
- Clean growth path.
- Later RMOS ingestion without retrofits.

## Non-Goals
- No real-time "tone optimization"
- No auto mode classification in Phase 1
- No web-based capture UI
- No embedded design advice
