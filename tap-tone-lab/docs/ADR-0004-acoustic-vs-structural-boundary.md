# ADR-0004: Acoustic vs Structural Interpretation Boundary

**Status:** Accepted  
**Date:** 2025-03-08  
**Context:** Multi-Channel Acoustic Testing  
**Decision Drivers:** Scientific defensibility, correct claims, scope control

## Decision

### 1) Separate measurement from inference
Microphones measure air pressure. Structural motion requires structural sensors.

### 2) Allowed claims by sensor type

**Microphones MAY claim:**
- radiated pressure distribution (inferred)
- frequency content
- time delays/phase between mic positions
- coherence / reliability bands
- radiation "hot zones" (beamforming/NAH) as inferred acoustic fields

**Microphones SHALL NOT claim:**
- plate deflection shapes
- structural eigenmodes as measured truth
- "wave flow in the wood"
unless corroborated with structural sensors or validated models.

**Accelerometers/LDV MAY claim:**
- structural vibration maps
- mode shapes (with adequate grid)
- structural wave/deflection patterns (within sensor resolution)

### 3) Labeling requirements
Outputs MUST be labeled as:
- Acoustic radiation map (inferred)
- Structural vibration map (measured)
- Structural vibration estimate (inferred, research-only)

## Rationale
Pressure fields are not wood motion. Mixing invalidates results and undermines trust.

## Non-Goals
No structural mode truth from mic-only data.
