# Tap Tone Pi - AI Coding Agent Instructions

## Project Mission
Tap Tone Pi is evolving into a **professional acoustic measurement and testing system** for luthiers, moving beyond simple tap-tone analysis toward spatial acoustic mapping and wave propagation visualization. This is **not** a single-mic FFT analyzer clone - it's a testing infrastructure for understanding how instruments vibrate and radiate sound.

## Core Philosophy: Measurement First, Interpretation Later
- **This is an instrument, not a toy** - focus on measurement accuracy, repeatability, and artifact generation
- **We measure, we don't optimize** - interpretation and design feedback happen in downstream tools (RMOS/ToolBox)
- **Artifact-first architecture** - every capture produces permanent, queryable records (WAV, JSON, CSV, session logs)
- **Phase relationships matter** - synchronized multi-channel capture is non-negotiable for spatial analysis

## Project Evolution Stages

### Current Stage: Phase 1 (Foundation)
- Single-mic tap tone capture + FFT + peak detection
- Headless CLI with structured artifact output
- Raspberry Pi 4/5 with USB measurement mic
- Prove repeatability and protocol before adding complexity

### Near-term: Phase 2 (Spatial Awareness)
**Phase 1 is a hard gate. Phase 2 begins ONLY after:**
- Artifacts are stable and backward-compatible
- Repeatability tests exist (10 taps, variance bounds documented)
- Measurement protocol v0.1 is written and tested

**Then proceed to:**
- 2-channel synchronized capture (coherence, time delays, phase)
- Cross-channel analysis to understand energy flow
- Foundation for multi-mic array work

### Future: Phase 3+ (Acoustic Mapping)
- 4-8+ mic arrays for near-field acoustic holography (NAH), not architecture
- **tap_tone_pi bundle**: Clean CLI measurement node with artifact-first design - this is the **architectural model** to follow

### Specific DSP Techniques to Port from guitar_tap
**Port AFTER Phase 1 is stable. Requires unit tests with golden WAV fixtures.**

1. **Parabolic peak interpolation** (PRIORITY)
   - Sub-bin frequency refinement for peak accuracy
   - Function: `freq_anal.py` parabolic interpolation logic
   - Test with synthetic pure tones (known frequencies)

2. **Peak prominence/guardrails tuning** (OPTIONAL)
   - Improved peak selection heuristics if better than current scipy defaults
   - Evaluate on real guitar captures before porting

3. **Coherence / cross-correlation** (PHASE 2 ONLY)
   - Multi-channel analysis after 2-channel capture is working
   - Requires synchronized sampling infrastructure first
- "Wave flow across guitar body" visualization
- Potentially scanning laser Doppler vibrometry (SLDV) for structural modes

## Reference Codebases (Do Not Clone Directly)
- **guitar_tap** (forked from dwsdolce/guitar_tap): PyQt6 GUI workstation with mature FFT/peak detection - use as **reference for DSP techniques only** (parabolic peak interpolation, pitch labeling), not architecture
- **tap_tone_pi bundle**: Clean CLI measurement node with artifact-first design - this is the **architectural model** to follow

## Hardware Architecture

### Phase 1 (Sandbox)
- Raspberry Pi 4/5 (4GB+)
- USB measurement mic (UMIK-1 class) - flat response, built-in ADC
- Portable HDMI monitor for dev
- microSD 32-64GB

### Phase 2 (Bench Appliance) 
- Pi 4/5 with 7" touchscreen
- Multi-channel USB audio interface (4-8 inputs, synchronized sampling)
- Panel-mount controls (rotary encoder, pushbuttons)
- Status LEDs, power switch, IEC/barrel jack

### Critical Hardware Requirement for Multi-Mic
- **Shared clock synchronization** across all channels (same audio interface)
- Phase accuracy is critical - no independent USB mics in array mode
- Mic spacing dictates max measurable frequency (wavelength constraints)

## Software Architecture Layers

### 1. Capture Layer (measurement kernel)
- **sounddevice** for audio I/O (not PyAudio)
- Blocking or streaming capture with explicit buffer management
- Device enumeration and configuration
- No assumptions about measurement intent

### 2. Analysis Layer (DSP)
- DC removal + high-pass filtering (Butterworth 2nd order)
- Hanning window + rfft (SciPy)
- Peak detection with prominence/spacing constraints
- Confidence heuristics (RMS, clipping detection)
- **Future**: Cross-channel coherence, delays, beamforming

### 3. Storage Layer (artifacts)
Each capture produces:
- `audio.wav` (int16, full signal)
- `analysis.json` (peaks, dominant freq, RMS, confidence, metadata)
- `spectrum.csv` (freq_hz, magnitude for plotting/reprocessing)
- `session.jsonl` (append-only log for session aggregation)

### 4. UI Layer (optional, separate)
- **Headless CLI is primary interface** for reproducibility
- Desktop GUI (PyQt6 + Matplotlib) is for inspection/debugging only
- **Never** web-based for core measurement (timing/phase corruption risk)
- Future: Simple TUI dashboard for bench use

## What We Do NOT Do (Scope Boundaries)
- ❌ No "tone quality" scoring or optimization in measurement node
- ❌ No monopole/mode assumptions embedded in capture code
- ❌ No design recommendations from the measurement tool
- ❌ No single-timestamp file system - all measurements are standalone artifacts
- ❌ No browser/WebAudio/web-based measurement (phase/sync unreliable)

## Key Workflows

### Measurement Protocol v0.1 (Phase 1 minimum)
**Baseline requirements for repeatability:**
1. **Tap tool**: Small rubber or wood hammer (document specific tool in metadata)
2. **Tap locations**: Bridge area, upper bout, or lower bout (start with 1-2 locations)
3. **Mic setup**:
   - Type: USB measurement mic (UMIK-1 class) or XLR condenser + interface
   - Distance: 30 cm from soundboard
   - Angle: 0-15° off normal, centered on bridge line
   - Document mic model in metadata
4. **Environment**: Quiet room, no fan/HVAC noise, consistent fixture/support
5. **Gain target**: Avoid clipping; aim for RMS 0.01-0.05 in captured signal
6. **Repeatability**: N ≥ 3 takes per condition for variance analysis

**Protocol expansion planned for v0.2+** (multi-point mapping, fixture specs, calibration)

### Development Workflow
**Artifact contract defined now, integration deferred to Phase 3+**

**Minimum RunArtifact-compatible format:**
- `artifact_type`: `"tap_tone_capture"`
- Required files per capture:
  - `audio.wav` (int16, mono/multi-channel)
  - `analysis.json` (structured results)
  - `spectrum.csv` (freq_hz, magnitude)
  - `session.jsonl` (append-only session log)

**Required metadata fields in `analysis.json`:**
- `ts_utc`: ISO timestamp
- `label`: user-provided capture label
- `sample_rate`: Hz
- `dominant_hz`: float or null
- `peaks[]`: array of {freq_hz, magnitude}
- `rms`: float
- `clipped`: boolean
- `confidence`: float 0-1

**Optional/reserved metadata (Phase 2+):**
- `instrument_id`, `build_stage`, `tap_point`, `mic_model`, `mic_distance_mm`, `fixture`, `gain_db`, `channel_count`

Export step to generate RMOS RunArtifact payload not implemented yet.
4. Document protocol changes in `/docs/protocol/`

### Integration with RMOS/ToolBox (Future)
- Artifacts shaped for RunArtifact ingestion
- Metadata includes: instrument_model, tap_point, mic_model, mic_distance_mm, support_fixture
- Export step will generate RMOS-compatible payload (not implemented yet)

## File Organization
```
tap_tone_pi/
├── tap_tone/              # Core measurement kernel
│   ├── capture.py         # Audio I/O
│   ├── analysis.py        # DSP + peak detection
│   ├── storage.py         # Artifact persistence
│   ├── config.py          # Dataclass configs
│   └── main.py            # CLI entrypoint
├── docs/
│   ├── protocol/          # Measurement protocols
│   ├── hardware/          # Wiring, BOM, assembly
│   └── research/          # NAH, beamforming, physics
├── tests/                 # Deterministic DSP tests
└── .github/               # This file + workflows
```

## When Adding Features

### For Audio Capture
- Verify synchronization across channels if multi-channel
- Test on Pi, not just desktop (ALSA behavior differs)
- Measure and document latency
- Handle device disconnection gracefully

### For DSP/Analysis
- Keep analysis functions pure (no I/O inside)
- Return complete spectrum arrays (for reprocessing/plotting)
- Document assumptions (frequency bands, window types, normalization)
- Add unit tests with synthetic signals (pure tones, two-tone, noise)

### For Spatial Analysis (Future)
- Phase relationships are sacred - verify clock sync first
- Frequency-dependent spatial resolution (shorter wavelength = tighter spacing needed)
- Coherence thresholds for valid measurements
- Ensemble averaging across multiple taps

## Technical Decisions Made
- **Python 3.10+** (Pi OS compatibility)
- **sounddevice over PyAudio** (better cross-platform, maintained)
- **Raspberry Pi 4/5 over microcontrollers** (development flexibility over instant-on)
- **Artifact-first over live display** (scientific record over UX)
- **CLI over GUI** for primary interface (automation, repeatability)

## References & Theory
- Trevor Gore's monopole framework (inspiration, not implementation)
- Near-field acoustic holography (NAH) for spatial reconstruction
- Beamforming for acoustic imaging
- **Critical distinction**: This project measures reality; visualization tools (like Iulius Tone Profiler) map design intent

## Questions to Ask When Implementing
1. Does this preserve measurement repeatability?
2. Is the artifact format forward/backward compatible?
3. Have I tested on actual Pi hardware?
4. Does this assume anything about guitar structure? (if yes, move to RMOS)
5. Can this be verified with synthetic test signals?

## Next Milestones
- [ ] Phase 1: Stable single-mic CLI with artifact output
- [ ] Measurement protocol v0.1 documented
- [ ] Pi deployment tested with USB mic
- [ ] Phase 2: 2-channel coherence + delay analysis
- [ ] Phase 3: 4-8 channel array + basic beamforming
