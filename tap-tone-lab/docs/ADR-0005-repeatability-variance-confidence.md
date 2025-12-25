# ADR-0005: Repeatability, Variance, and Confidence Metrics

**Status:** Accepted  
**Date:** 2025-03-08  
**Context:** Tap-Tone Measurement Node  
**Decision Drivers:** Measurement reliability, comparability, defensibility

## Decision

### 1) Repeatability is first-class
A "capture" for validation is a set of takes (default N=10).

### 2) Canonical repeatability procedure
For fixed protocol + geometry:
- record N takes
- compute per-take metrics
- compute aggregate stats

### 3) Per-take metrics (minimum)
- dominant_hz
- peaks (top K)
- rms
- clipped
- Phase 2+: coherence + delay

### 4) Aggregate metrics (minimum)
- mean/stdev of dominant_hz
- MAD for robustness
- peak cluster stability across takes
- outlier detection

### 5) Confidence definition (v0.1)
confidence 0..1 based on:
- not clipped
- RMS above floor
- peak prominence
- Phase 2+: coherence in focus band

Confidence is NOT a tone-quality score.

### 6) Starter acceptance gates (defaults)
- clipping rate: 0%
- std(dominant_hz) ≤ 2 Hz over N=10 (starter)
- top peaks appear in ≥70% of takes (starter)

## Rationale
Single-shot taps are too noisy. Confidence must reflect validity, not taste.

## Non-Goals
No "tone rating," no build recommendations from confidence alone.
