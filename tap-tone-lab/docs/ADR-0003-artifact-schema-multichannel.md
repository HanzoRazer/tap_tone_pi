# ADR-0003: Artifact Schema for Multi-Channel Data

**Status:** Accepted  
**Date:** 2025-03-08  
**Context:** Tap-Tone Measurement Node — Single & Multi-Channel Acquisition  
**Decision Drivers:** Reproducibility, forward compatibility, RMOS ingestion, scientific traceability

## Decision

### 1) Artifact-First Principle
Artifacts fully describe what/how/where measurement occurred. Artifacts are the product.

### 2) Canonical Bundle Structure
```
session_<UTC_TIMESTAMP>/
├── metadata.json
├── session.jsonl
├── captures/
│   └── capture_<UTC_TIMESTAMP>/
│       ├── audio.wav
│       ├── analysis.json
│       ├── spectrum.csv
│       ├── channels.json
│       └── geometry.json
```
Phase 1 may omit optional files, but paths should be stable.

### 3) audio.wav
PCM 16/24-bit WAV. Deterministic channel order. No resampling/mixing at capture time.

### 4) analysis.json
Required:
- ts_utc, sample_rate, channels
- dominant_hz, rms[], clipped[], confidence
Phase 2+:
- peaks by channel
- cross_channel metrics (delay/coherence/phase)

### 5) spectrum.csv
Shared freq axis; columns per channel.

### 6) channels.json
Defines physical meaning of each channel; must match WAV order.

### 7) geometry.json
Explicit numeric geometry: coordinate frame, units, origin, mic positions.

### 8) session.jsonl
Append-only chronological ground truth.

## Rationale
- WAV+JSON+CSV can be reanalyzed forever.
- Geometry is required for multi-channel meaning.
- Reproducibility requires separation of raw/derived/interpretation.

## Non-Goals
- No binary-only formats
- No implicit geometry
- No mutation of raw data
