# ADR-0007: Phase 3 Roving-Grid Operational Deflection Shape (ODS) Methodology

**Status:** RESEARCH  
**Date:** 2025-12-25  
**Deciders:** Architecture Team  
**Supersedes:** ADR-0002 (multi-channel expansion phases)

---

## Context

Phase 1 (single-mic tap tone) and Phase 2 (2-channel coherence) provide point measurements of acoustic radiation. To map **spatial wolf-note behavior** and **resonance localization** across the guitar body, we need:

- **Roving measurement topology** (reference mic + roving mic)
- **Operational transfer functions** H_ir(f) = G_ir(f) / G_rr(f)
- **Spatial mapping** of localization indices and coherence
- **Non-contact excitation** (speaker-driven, zero added mass)

This ADR establishes Phase 3 as the **roving-grid ODS measurement phase**, complementing the fixed-array approaches in ADR-0002.

---

## Decision

### Phase 3 Scope

**Roving-grid operational deflection shape (ODS) mapping** with:

1. **Excitation Method:**
   - Speaker-driven (log chirp 30-2000 Hz or stepped sine)
   - Repeatable, broadband, zero plate loading
   - Fixed speaker position and amplitude

2. **Measurement Topology:**
   - **Reference microphone:** Fixed position (near soundhole or off-axis)
   - **Roving microphone:** Manually moved to grid points
   - No structural sensors (acoustic-only, per ADR-0004)

3. **Grid Definition:**
   - Cartesian grid in mm (default) or inches (optional)
   - Origin at bridge center (consistent with ADR-0003)
   - JSON grid specification: `{"points": [{"label": "A1", "x": 0, "y": 50}, ...]}`

4. **Analysis Pipeline:**
   - Cross-spectral density: G_ir(f) = X_i(f) X_r*(f)
   - Auto-spectral density: G_rr(f) = X_r(f) X_r*(f)
   - Transfer estimate: H_ir(f) = G_ir(f) / G_rr(f)
   - Coherence: γ²_ir(f) = |G_ir(f)|² / (G_ii(f) G_rr(f))

5. **Wolf-Region Identification Metrics:**
   - **Peak sharpness (Q proxy):** f_0 / Δf_-3dB
   - **Localization index:** max_i |H_ir(f)| / mean_i |H_ir(f)|
   - **Coherence gate:** Accept only γ² > 0.8 for valid measurements
   - **Repeatability:** Repeated trials at critical points, CV < 10%

6. **Artifact Structure:**
   ```
   session_<ts>/
   ├── metadata.json          # Session-level provenance
   ├── grid.json              # Spatial grid definition (x_mm, y_mm, label)
   ├── wolf_map.json          # Per-point results (localization_index, coherence_mean)
   ├── wolf_map.png           # Spatial heatmap visualization
   └── points/
       ├── point_A1/
       │   ├── audio.wav      # 2-channel (reference, roving)
       │   ├── analysis.json  # Transfer function, coherence, phase
       │   └── spectrum.csv   # f_hz, H_mag, coherence, phase_deg
       └── point_A2/
           └── ...
   ```

7. **Claims Boundaries (per ADR-0004):**
   - **MAY claim:** Operational deflection shapes (ODS), resonance localization, wolf-region mapping
   - **SHALL NOT claim:** True eigenmodes, plate deflection without structural sensors, design causality

---

## Rationale

### Why Roving (Not Fixed Array)?

- **Cost-effective:** 2 mics instead of 8+
- **Scalable:** Arbitrary grid density without hardware limits
- **Complementary:** Validates fixed-array findings with independent method
- **Research-grade:** Standard practice in experimental modal analysis (EMA)

### Why Speaker Excitation?

- **Zero added mass:** Preserves system dynamics (vs. shaker attachment)
- **Repeatable:** Consistent amplitude/phase across all grid points
- **Broadband:** Single capture covers full frequency range
- **Compatible:** Works with mic-only measurement (no force transducer needed)

### Why ODS (Not EMA)?

- Operational conditions (not controlled modal excitation)
- No assumption of linear, time-invariant dynamics required
- Focus on **observable behavior** under realistic playing conditions
- Simpler processing (no modal parameter extraction)

---

## Integration with Existing Phases

| Phase | Topology | Analysis | Wolf Detection |
|-------|----------|----------|----------------|
| **Phase 1** | Single mic, tap | FFT + peaks | Dominant frequency only |
| **Phase 2** | 2-mic fixed, tap | Coherence + phase | Channel correlation |
| **Phase 3** | Reference + roving, speaker | ODS + localization | Spatial mapping |

Phase 3 **requires Phase 2 infrastructure** (2-channel sync capture, coherence analysis) but **extends** it to spatial roving measurements.

---

## Prototype Implementation

See `scripts/roving_grid_ods.py` for Phase 3 reference prototype.

**Key features:**
- Grid definition from JSON (mm or inches)
- Manual roving workflow (operator prompted per point)
- Coherence + transfer function analysis
- Localization index computation
- Wolf map artifact generation

**Future enhancements:**
- Automated mic positioning (robotic arm, laser tracking)
- Time-gated impulse response (suppress room reflections)
- Multi-frequency ODS animation
- RMOS RunArtifact export

---

## Consequences

### Positive

- **Spatially-resolved wolf-note maps** with quantified confidence
- **Complements Phase 2** (fixed array) with independent validation method
- **Research-grade methodology** suitable for publication
- **Scalable** to arbitrary grid densities

### Negative

- **Labor-intensive:** Manual roving requires operator for each point
- **Time-consuming:** ~30s per point × 50 points = 25 minutes minimum
- **Positioning error:** Repeatability depends on operator precision (±5mm typical)
- **Environmental sensitivity:** Longer sessions → greater risk of condition drift

### Mitigation

- Automate critical points only (coarse-to-fine adaptive sampling)
- Document positioning method in metadata (fixture, visual markers)
- Include repeatability checks (revisit reference points)
- Time-stamp each measurement for drift analysis

---

## References

- ADR-0002: Multi-channel expansion (Phase 2 coherence, Phase 4+ arrays)
- ADR-0004: Acoustic vs. structural boundary (claim constraints)
- ADR-0003: Artifact schema (bundle structure)
- `docs/research/phase3-roving-grid-ods-whitepaper.md`: Full experimental method

---

## Acceptance Criteria

Phase 3 is validated when:

1. ✅ Roving-grid script produces wolf_map artifacts
2. ✅ Coherence gate filters invalid measurements (γ² < 0.8)
3. ✅ Localization index identifies known wolf frequencies
4. ✅ Spatial heatmap shows expected resonance localization
5. ✅ Repeatability tests: CV < 10% at reference points

---

## Next Steps (Phase 4+)

After Phase 3 validation:

- **Phase 4:** Fixed 4-8 mic array (beamforming, acoustic holography)
- **Phase 5:** Structural sensors (LDV, accelerometers) for true mode shapes
- **Phase 6:** Hybrid acoustic-structural ODS with validated correlation

---

**Author:** Architecture Team  
**Reviewers:** Pending lab validation with speaker-driven roving setup
