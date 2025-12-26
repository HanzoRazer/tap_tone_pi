# Instrumentation Baseline — v1.0

This repository represents a frozen instrumentation baseline.

- Measurement topology validated
- Signal processing validated
- Error/confidence framework defined
- RMOS integration defined

⚠️ Changes to this repository MUST increment the major version.
No experimental features should be added here.

**Date frozen:** 2025-12-25  
**Owner:** Ross Echols

## What's Frozen

### Phase 1: Single-Channel Tap Tone
- CLI with devices/record/live commands
- FFT + peak detection with confidence heuristics
- Artifact-first architecture (WAV/JSON/CSV/JSONL)

### Phase 2: 2-Channel Coherence
- Synchronized stereo capture
- Cross-channel coherence, phase, time delay
- Focus-band analysis for wolf-note region

### Phase 3: Roving-Grid ODS
- Speaker-driven excitation
- Reference + roving microphone topology
- Operational transfer functions H_ir(f)
- Wolf-region localization metrics

### Supporting Tools
- Bundle validation (schema + WAV consistency)
- Manifest generation (SHA256 hashing)
- Repeatability framework (N-take variance)
- PDF lab report generation (ReportLab)
- Time-gated impulse response (room reflection suppression)
- RMOS RunArtifact export (provenance + integration)

### Documentation
- 7 ADRs (measurement scope, multi-channel expansion, artifact schema, claim boundaries, repeatability, RMOS mapping, Phase 3 ODS)
- 4 JSON schemas (analysis, channels, geometry, metadata)
- Phase 3 whitepaper (experimental method)

## Governance

This baseline is **reference-only**. Future work should:
- Branch to `v2.x-experimental` if extending measurement capabilities
- Create new repo if adding product features (UI, packaging, hardware)
- Reference this baseline as ground truth for scientific claims

## Version History

- **v0.1.0**: Initial Phase 1 prototype
- **v0.2.0**: Phase 2 coherence added
- **v0.3.0**: Phase 1 package + CLI
- **v0.3.1**: Zero-drift dual entrypoints
- **v0.3.2**: PDF reports + ReportLab
- **v1.0.0**: Instrumentation baseline freeze (2025-12-25)
