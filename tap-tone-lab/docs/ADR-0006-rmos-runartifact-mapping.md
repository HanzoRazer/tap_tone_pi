# ADR-0006: RMOS RunArtifact Mapping

**Status:** Accepted  
**Date:** 2025-03-08  
**Context:** Tap-Tone Node → ToolBox/RMOS (future)  
**Decision Drivers:** Forward compatibility, minimal coupling, clean ingestion path

## Decision

### 1) Integration deferred, contract not
No RMOS dependency in Phase 1–2, but artifacts are shaped for later ingestion.

### 2) Mapping strategy
Each capture → one RunArtifact type `tap_tone_capture` with attachments:
- audio.wav
- analysis.json
- spectrum.csv
- optional channels.json / geometry.json
- optional plots later

Session-level repeatability may map to parent `tap_tone_session`.

### 3) Required provenance fields (metadata)
- tool_id, tool_version
- mode="acoustics", event_type="measurement"
- ts_utc, label/tap_point
- sample_rate, seconds, channels
- protocol identifiers (fixture, distance, tap tool) when known

### 4) Hashing / dedup
Include sha256 hashes in manifest/export. Dedup is RMOS-side.

### 5) Export adapter (future)
Separate adapter module reads bundles and uploads to RMOS intake.

## Non-Goals
No RMOS DB writes from node, no network required, no forced sync to runs.
