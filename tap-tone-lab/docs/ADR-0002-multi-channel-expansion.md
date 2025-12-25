# ADR-0002: Multi-Channel Expansion Strategy

**Status:** Accepted  
**Date:** 2025-03-08  
**Context:** Tap-Tone Measurement Node → Multi-Channel Acoustic Testing  
**Decision Drivers:** Phase coherence, repeatability, physical validity, controlled scope expansion

## Decision

### 1) Expansion Philosophy
Multi-channel SHALL be introduced incrementally with validation gates. No novelty-first visuals.

### 2) Phase 2: Two-Channel (Stereo) Measurement — First Expansion
Objectives:
- phase-coherent capture
- time delay, phase difference, coherence
Requirements:
- shared clock (single interface/device)
- fixed documented geometry
Outputs:
- multi-channel WAV
- channel-indexed FFT data
- cross-channel metrics JSON

No spatial reconstruction claims.

### 3) Phase 3: Small Array (4–8 channels) — Directional Inference
Goal: radiation "hot zones" and frequency-dependent patterns.
Allowed: delay-and-sum beamforming, band-limited maps.
Not allowed: mode shapes / structural deflection claims.

### 4) Phase 4: Near-Field Reconstruction (Research)
Experimental NAH/ESM-style reconstructions with explicit limits and labeling.

### 5) Phase 5: Structural Mode Measurement (Out of scope for mic arrays)
Structural "wave flow" claims require LDV or accelerometer grids.

## Validation Gates
Phase 2: stable phase + coherence in expected bands + consistent delays.
Phase 3+: repeatable spatial patterns with documented decorrelation causes.

## Rationale
- Phase coherence is non-negotiable.
- Radiation ≠ structure.
- Incremental expansion preserves trust.

## Non-Goals
- No "full wave flow" claims from sparse mic arrays
- No skipping Phase 2
