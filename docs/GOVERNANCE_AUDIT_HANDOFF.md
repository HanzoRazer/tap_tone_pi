# Governance Audit Handoff — Annotated Developer Guide

> **Audit Date:** 2026-05-22  
> **Scope:** Authority, Provenance, Execution, and Boundary Interrogation  
> **Purpose:** Enable new developers to understand what claims truth, what can mutate state, and where legitimacy boundaries exist.

---

## Executive Summary

This document synthesizes a four-axis governance audit of `tap_tone_pi`:

1. **Ownership** — What systems claim authority over truth, validity, and normalization
2. **Provenance** — How observation is distinguished from interpretation
3. **Execution** — What can automatically mutate state
4. **Boundaries** — What experimental outputs could be mistaken for legitimacy

**Core invariant:** This repository builds measurement instruments, not opinions. All advisory logic is explicitly separated from measurement truth.

---

## 1. OWNERSHIP — What Claims Authority?

### 1.1 Schema Authority (Canonical Contracts)

**Location:** [`contracts/schema_registry.json`](../contracts/schema_registry.json)

All measurement artifacts must conform to versioned schemas. The registry defines team ownership:

| Team | Schemas Owned | Justification |
|------|---------------|---------------|
| `acoustics-team` | phase2_grid, phase2_session_meta, phase2_ods_snapshot, phase2_wolf_candidates | ODS/coherence requires acoustic DSP expertise |
| `measurement-team` | tap_peaks, moe_result, manifest, wood_flitch_record | Core measurement outputs |
| `agentic-team` | session_timeline | Directive/event provenance |
| `chladni-team` | chladni_run | Pattern analysis expertise |

**Version bump policy** (line 38-45):
```json
{
  "major": "adr-plus-owner-signoff",   // Breaking change requires ADR
  "minor": "owner-review",              // New optional fields
  "patch": "self-approve"               // Documentation/typo fixes
}
```

**Justification:** Team ownership prevents unauthorized schema changes and ensures domain experts review structural modifications.

---

### 1.2 Quality Policy Engine (Hard/Soft Rules)

**Location:** [`tap_tone_pi/core/quality_policy.py`](../tap_tone_pi/core/quality_policy.py)

Quality rules claim authority over measurement validity:

#### HARD Rules (Measurement MUST Fail)

| Rule | Condition | Justification |
|------|-----------|---------------|
| Q001_CLIPPED | Audio clipping detected | Clipped signals contain unrecoverable distortion |
| Q002_SILENT | RMS < 0.001 | No signal = no measurement |
| Q003_NO_PEAKS | No dominant frequency | FFT cannot extract meaningful data |
| Q004_LOW_CONFIDENCE | Confidence < 0.3 | Below minimum SNR threshold |
| Q005_INVALID_SAMPLE_RATE | Rate not in [44100, 48000, 96000] | Prevents aliasing/Nyquist violations |

#### SOFT Rules (Warning, Can Override)

| Rule | Condition | Override Justification |
|------|-----------|------------------------|
| Q010_QUIET | RMS < 0.01 | Experienced operator may accept quiet signal |
| Q011_NEAR_CLIPPING | Peak > 0.9 | May be acceptable if no actual clipping |
| Q012_MARGINAL_CONFIDENCE | 0.3 ≤ confidence < 0.5 | Operator judgment on measurement context |

**Schema Reference:** Rules map to `quality_check.json` artifact per [`contracts/schemas/`](../contracts/schemas/).

---

### 1.3 Calibration Gate

**Location:** [`tap_tone_pi/calibration/gate.py`](../tap_tone_pi/calibration/gate.py)

Hardware validity is enforced via calibration age:

| Status | Age | Behavior | Justification |
|--------|-----|----------|---------------|
| VALID | ≤ 30 days | Session starts normally | Calibration drift is acceptable |
| STALE | > 30 days | Warning, `--force` required | Operator accepts risk |
| UNCALIBRATED | Never calibrated | Blocked, `--force-uncalibrated` required | No baseline exists |
| FAILED | Calibration check failed | Always blocked | Hardware is known-bad |

**Schema Reference:** Calibration state persisted to [`~/.tap_tone_pi/calibration/`](../tap_tone_pi/calibration/).

---

### 1.4 Normalization Authority

These modules claim authority over canonical identifiers:

#### Wood Species Normalization

**Location:** [`tap_tone_pi/materials/wood_db.py`](../tap_tone_pi/materials/wood_db.py)

```python
# ID patterns (enforced via regex in __post_init__)
_SPECIES_ID_RE = r"^[a-z][a-z0-9_]{1,40}$"      # spruce_sitka
_FLITCH_ID_RE = r"^[A-Z][A-Z0-9_]{2,80}$"       # SPRUCE_SITKA_001
_MEASUREMENT_ID_RE = r"^[A-Z0-9][A-Z0-9_]{2,80}$"
```

**Justification:** Canonical IDs prevent duplicate records and enable cross-session queries.

**Schema Reference:** [`contracts/wood_flitch_record_v1.schema.json`](../contracts/wood_flitch_record_v1.schema.json)

#### Frequency Tolerance Normalization

**Location:** [`tap_tone_pi/chladni/policy.py`](../tap_tone_pi/chladni/policy.py)

Three tolerance modes (configured via environment variables):

| Mode | Default | Use Case |
|------|---------|----------|
| RELATIVE | 2.0% | Wide frequency ranges (recommended) |
| SEMITONE | 50 cents | Musical interval consistency |
| FIXED | 5.0 Hz | Legacy compatibility only |

**Justification:** Frequency-relative tolerance prevents low-frequency measurements from failing on acceptable variance.

---

## 2. PROVENANCE — Observation vs Interpretation

### 2.1 The Measurement Boundary (Hard Architectural Rule)

**ADR Reference:** [`docs/ADR-0001-measurement-scope.md`](ADR-0001-measurement-scope.md)

```
This repo CAPTURES evidence, COMPUTES deterministic DSP, PERSISTS artifacts.
This repo DOES NOT interpret tone quality, prescribe modifications, or grade instruments.
```

**Manifest Declaration:**

**Schema Reference:** [`contracts/viewer_pack_v1.schema.json`](../contracts/viewer_pack_v1.schema.json) (lines 52-62)

```json
{
  "measurement_only": true,
  "interpretation": "deferred"
}
```

**Justification:** Downstream systems (ToolBox, RMOS) own interpretation. Mixing measurement with advice corrupts forensic defensibility.

---

### 2.2 Kind-Based File Classification

**Location:** [`scripts/phase2/export_viewer_pack_v1.py`](../scripts/phase2/export_viewer_pack_v1.py) (lines 119-134)

Files are tagged with non-interpretive `kind` values:

| Kind | Classification | Example | Authority Level |
|------|----------------|---------|-----------------|
| `audio_raw` | Pure observation | `audio/points/A1.wav` | CANONICAL |
| `spectrum_csv` | Pure measurement | FFT magnitude | CANONICAL |
| `provenance` | Capture metadata | `capture_meta.json` | CANONICAL |
| `analysis_peaks` | Derived (algorithmic) | `scipy.find_peaks()` output | DERIVED |
| `transfer_function` | Derived (computation) | ODS coherence estimation | DERIVED |
| `wolf_candidates` | Advisory classification | Beat frequency scoring | ADVISORY |

**Justification:** Kind classification enables downstream systems to filter by authority level.

---

### 2.3 SHA-256 Provenance Chain

**Location:** [`tap_tone_pi/io/manifest.py`](../tap_tone_pi/io/manifest.py)

Every artifact records:

```json
{
  "artifact_type": "manifest",
  "ts_utc": "2026-05-22T14:30:45Z",
  "artifacts": [
    {
      "path": "audio.wav",
      "sha256": "a1b2c3d4e5f6...",
      "size": 245000
    }
  ]
}
```

**Bundle-level hash** (computed at export):

```python
manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
bundle_sha = sha256_bytes(manifest_bytes)
manifest["bundle_sha256"] = bundle_sha
```

**Schema Reference:** [`contracts/schemas/manifest.schema.json`](../contracts/schemas/manifest.schema.json)

**Justification:** Content-addressable artifacts enable integrity verification and cache invalidation.

---

### 2.4 Forbidden Interpretive Language

**Location:** [`docs/contracts/EVIDENCE_PACK_CONTRACT_v1.md`](contracts/EVIDENCE_PACK_CONTRACT_v1.md)

The following words are **PROHIBITED** in `analysis.json` notes:

| Category | Forbidden Terms | Justification |
|----------|-----------------|---------------|
| Ranking | "strongest", "dominant", "worst", "primary" | Implies subjective ordering |
| Quality | "good", "bad", "optimal" | Value judgment |
| Prescription | "fix", "thin", "stiffen" | Design guidance |
| Diagnosis | "wolf", "dead spot" | Interpretive classification |

**CI Enforcement:** `ci/check_advisory_boundary.py` scans exports and blocks prohibited fields.

---

## 3. EXECUTION — What Can Mutate State?

### 3.1 CLI Commands (Primary Mutation Vectors)

**Location:** [`tap_tone_pi/cli/main.py`](../tap_tone_pi/cli/main.py)

| Command | Creates | Modifies | Justification |
|---------|---------|----------|---------------|
| `ttp setup` | `~/.tap_tone_pi/config.json` | Device config | First-time user experience |
| `ttp record` | `capture_{ts}/audio.wav`, `analysis.json` | — | Core measurement capture |
| `ttp measure` | Same as record | Operator override state | Quality gate with human override |
| `ttp phase2` | `runs_phase2/session_*/` | `session_state.json` | Resumable grid workflow |
| `ttp gold-run` | Export ZIP | Optional ToolBox ingest | Automated end-to-end pipeline |
| `ttp demo` | `demo_output/` | — | Hardware-free testing |
| `ttp calibrate` | `~/.tap_tone_pi/calibration/` | Device calibration | Hardware validation |

---

### 3.2 State Persistence Points

| State | Location | Update Trigger | Persistence Pattern |
|-------|----------|----------------|---------------------|
| User config | `~/.tap_tone_pi/config.json` | `ttp setup`, FTUE metrics | Direct write |
| Session ledger | `{session}/session.jsonl` | Every capture | Append-only |
| Phase 2 state | `{session}/session_state.json` | Checkpoint saves | Atomic (temp → rename) |
| UWSM state | `~/.tap_tone_pi/.uwsm/state.json` | Agentic policy decisions | Direct write |
| Calibration | `~/.tap_tone_pi/calibration/` | `ttp calibrate` | Direct write |

**Justification for append-only ledger:** Session JSONL provides audit trail without risk of corruption during failure.

---

### 3.3 CI/CD Pipelines

**Location:** `.github/workflows/`

| Workflow | Blocking | Mutations | Justification |
|----------|----------|-----------|---------------|
| `test.yml` | Yes | None (read-only) | Core regression suite |
| `boundary_guard.yml` | Yes | None | Enforces import isolation |
| `no_logic_creep.yml` | Yes | None | Blocks advisory in measurement |
| `wav-io-guard.yml` | Yes | None | Canonical audio I/O enforcement |
| `advisory_boundary_guard.yml` | Yes | None | Instrument class validation |
| `precommit.yml` | Yes | Auto-format (if merged) | Code style consistency |

---

### 3.4 Pre-commit Hooks

**Location:** `.pre-commit-config.yaml`

| Hook | Effect | Bypass |
|------|--------|--------|
| `ruff` | Auto-fixes code style | `--no-verify` (not recommended) |
| `ruff-format` | Formats Python | `--no-verify` |
| `mypy` | Type checking (fail-closed) | `--no-verify` |

---

## 4. BOUNDARIES — Experimental vs Legitimate

### 4.1 Two-Class Instrument System

**ADR Reference:** [`docs/ADR-0009-advisory-boundary.md`](ADR-0009-advisory-boundary.md)

Every module must declare its instrument class via file header:

#### MEASUREMENT Class (Authoritative, Can Export)

```python
# INSTRUMENT CLASS: MEASUREMENT
```

**Modules in this class:**
- `tap_tone_pi/wolf/wolf_beat.py` — Wolf tone detection (measurement facts)
- `tap_tone_pi/transfer_function/estimators.py` — Transfer function + coherence
- `tap_tone_pi/calibration/gate.py` — Calibration validation
- `analyzer/widgets/limit_overlay.py` — Limit visualization

#### DECISION SUPPORT Class (Advisory, Cannot Export)

```python
# INSTRUMENT CLASS: DECISION SUPPORT
# Outputs from this module are physics-grounded recommendations,
# NOT calibrated measurement results.
# They MUST NOT appear in viewer_pack_v1 or the provenance chain.
# Operator expertise is required to interpret recommendations.
```

**Modules in this class:**
- `tap_tone_pi/wolf/wolf_advisor.py` — Wolf mitigation recommendations
- `analyzer/analysis/wood_properties.py` — Wood property guidance
- `analyzer/guidance/engine.py` — Analyzer guidance directives

**Justification:** Explicit classification prevents advisory logic from contaminating measurement truth.

---

### 4.2 CI Guardrails

| Guardrail | Location | Blocks | Justification |
|-----------|----------|--------|---------------|
| Logic creep | `ci/no_logic_creep.yml` | Advisory imports in measurement | Measurement boundary enforcement |
| Boundary imports | `ci/check_boundary_imports.py` | ToolBox namespaces in Analyzer | Cross-repo isolation |
| Advisory boundary | `ci/check_advisory_boundary.py` | Undeclared instrument class | Explicit classification requirement |
| Wolf purity | Same as above | Prohibited fields in wolf_candidates | Keeps wolf detection measurement-only |

**Prohibited wolf_candidates fields:**
- `mitigation_type`, `recommendations`, `wolf_directive`
- `severity_label`, `action_required`, `operator_guidance`
- `confidence_label`, `urgency`, `next_steps`

---

### 4.3 Agentic Layer (Shadow Mode)

**ADR Reference:** [`docs/ADR-0008-spine-wiring-architecture.md`](ADR-0008-spine-wiring-architecture.md)

The agentic spine operates in three modes:

| Mode | Behavior | Default | Justification |
|------|----------|---------|---------------|
| M0 | Shadow replay (observational) | **YES** | Safe validation without UI changes |
| M1 | Advisory directives (display-only) | No | Non-binding operator guidance |
| M2 | Agent orchestration | No | Future capability, not implemented |

**Flag gates (all OFF by default):**
```bash
AGENTIC_EMIT_EVENTS=0     # No event emission
AGENTIC_MODE=M0           # Shadow only
```

**Critical invariant:** Agent can only **point, highlight, reset view** — never change measurement parameters, start/stop acquisition, export data, or persist analyzer state.

---

### 4.4 High-Risk Outputs (Could Be Mistaken for Authority)

| Output | Module | Risk | Safeguard |
|--------|--------|------|-----------|
| Wolf recommendations | `wolf_advisor.py` | Looks like measurement | DECISION SUPPORT class, CI blocks export |
| Guidance panel | `analyzer/guidance/` | Polished GUI appearance | Ephemeral state, not persisted |
| Agentic events | `agentic/spine/` | `decision_required` could be misread | Disabled by default, M0 shadow-only |

---

## 5. Schema Reference Matrix

### 5.1 Measurement Schemas (CANONICAL)

| Schema | Owner | Version | File | Export Allowed |
|--------|-------|---------|------|----------------|
| `viewer_pack_v1` | acoustics-team | 1.0 | [`viewer_pack_v1.schema.json`](../contracts/viewer_pack_v1.schema.json) | Yes (bundle) |
| `phase2_grid` | acoustics-team | 1.0 | [`phase2_grid.schema.json`](../contracts/phase2_grid.schema.json) | Yes |
| `phase2_ods_snapshot` | acoustics-team | 2.0 | [`phase2_ods_snapshot.schema.json`](../contracts/phase2_ods_snapshot.schema.json) | Yes |
| `phase2_wolf_candidates` | acoustics-team | 2.0 | [`phase2_wolf_candidates.schema.json`](../contracts/phase2_wolf_candidates.schema.json) | Yes (measurement facts only) |
| `tap_peaks` | measurement-team | 1.0 | [`tap_peaks.schema.json`](../contracts/schemas/tap_peaks.schema.json) | Yes |
| `moe_result` | measurement-team | 1.0 | [`moe_result.schema.json`](../contracts/schemas/moe_result.schema.json) | Yes |
| `manifest` | measurement-team | 1.0 | [`manifest.schema.json`](../contracts/schemas/manifest.schema.json) | Yes |
| `wood_flitch_record` | measurement-team | 1.0 | [`wood_flitch_record_v1.schema.json`](../contracts/wood_flitch_record_v1.schema.json) | Yes |
| `instrument_build_record` | measurement-team | 1.0 | [`instrument_build_record_v1.schema.json`](../contracts/instrument_build_record_v1.schema.json) | Yes |

### 5.2 Agentic Schemas (INTERNAL)

| Schema | Owner | Version | Export Allowed |
|--------|-------|---------|----------------|
| `session_timeline` | agentic-team | 2.0 | No (internal directive tracking) |
| `spine_shadow_record` | agentic-team | 1.0 | No (M0 shadow mode only) |
| `AgentEventV1` | agentic-team | 1.0 | No (observational events) |

---

## 6. Validation Checklist for New Code

Before submitting code, verify:

### 6.1 Authority Claims

- [ ] If module outputs structured data: schema exists in `contracts/`
- [ ] If module validates input: uses `quality_policy.py` rules or documents new rules
- [ ] If module normalizes IDs: follows existing regex patterns

### 6.2 Provenance

- [ ] If module writes artifacts: includes `sha256`, `ts_utc`, `artifact_type`
- [ ] If module processes audio: uses `modes/_shared/wav_io.py` (no direct `wavfile` calls)
- [ ] If module detects peaks: outputs to `analysis_peaks` kind with no ranking language

### 6.3 Execution

- [ ] If CLI command: registered in `tap_tone_pi/cli/main.py`
- [ ] If state persistence: uses atomic write pattern for critical state
- [ ] If session ledger: append-only via `session.jsonl`

### 6.4 Boundaries

- [ ] File header declares `# INSTRUMENT CLASS: MEASUREMENT` or `# INSTRUMENT CLASS: DECISION SUPPORT`
- [ ] DECISION SUPPORT modules are not imported by export pipeline
- [ ] No prohibited words in `analysis.json` notes fields
- [ ] If agentic: respects flag gates and M0 default

---

## 7. Cross-Reference to Governance Documents

| Document | Purpose | Location |
|----------|---------|----------|
| GOVERNANCE.md | Full governance doctrine | [`docs/GOVERNANCE.md`](GOVERNANCE.md) |
| BOUNDARY_RULES.md | Import boundary rules | [`docs/BOUNDARY_RULES.md`](BOUNDARY_RULES.md) |
| ADR-0001 | Measurement scope decision | [`docs/ADR-0001-measurement-scope.md`](ADR-0001-measurement-scope.md) |
| ADR-0004 | Acoustic vs structural boundary | [`docs/ADR-0004-acoustic-vs-structural-boundary.md`](ADR-0004-acoustic-vs-structural-boundary.md) |
| ADR-0009 | Advisory boundary | [`docs/ADR-0009-advisory-boundary.md`](ADR-0009-advisory-boundary.md) |
| Schema Registry | Canonical schema ownership | [`contracts/schema_registry.json`](../contracts/schema_registry.json) |
| Gap Inventory | Shipped vs missing features | [`docs/01_GAP_INVENTORY.md`](01_GAP_INVENTORY.md) |

---

## 8. Ownership Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUTHORITY ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  contracts/schema_registry.json                                         │
│  └── Team ownership mapping                                             │
│      ├── acoustics-team: phase2_*, wolf_candidates                      │
│      ├── measurement-team: tap_peaks, moe_result, manifest              │
│      ├── agentic-team: session_timeline                                 │
│      └── chladni-team: chladni_run                                      │
│                                                                         │
│  tap_tone_pi/core/quality_policy.py                                     │
│  └── HARD rules (Q001-Q009): Measurement MUST fail                      │
│  └── SOFT rules (Q010-Q019): Warning, operator override                 │
│                                                                         │
│  tap_tone_pi/calibration/gate.py                                        │
│  └── VALID/STALE/UNCALIBRATED/FAILED hardware states                    │
│                                                                         │
│  contracts/*_v{N}.schema.json                                           │
│  └── Immutable measurement contracts (no_extra_fields: true)            │
│                                                                         │
│  ci/*.yml                                                               │
│  └── Automated boundary enforcement (merge-blocking)                    │
│                                                                         │
│  viewer_pack_v1 manifest                                                │
│  └── measurement_only: true, interpretation: "deferred"                 │
│                                                                         │
│  DECISION SUPPORT class                                                 │
│  └── Explicitly non-canonical (never enters provenance chain)           │
│                                                                         │
│  Agentic layer (M0 default)                                             │
│  └── Shadow mode: observe only, cannot mutate                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Provenance Flow Diagram

```
CAPTURE                    ANALYSIS                   EXPORT
───────                    ────────                   ──────

audio.wav ──────────────► FFT + find_peaks() ──────► viewer_pack_v1.zip
    │                          │                          │
    │ sha256                   │ kind: analysis_peaks     │ bundle_sha256
    │ ts_utc                   │ no ranking words         │ measurement_only: true
    │ sample_rate              │                          │ interpretation: deferred
    │                          │                          │
    ▼                          ▼                          ▼
capture_meta.json         analysis.json              manifest.json
    │                          │                          │
    └──────────────────────────┴──────────────────────────┘
                               │
                               ▼
                    PROVENANCE CHAIN (immutable)
```

---

## 10. Known Legitimacy Compromises

Per [`docs/CODEBASE_AUDIT_2026.md`](CODEBASE_AUDIT_2026.md):

| Issue | Impact | File | Status |
|-------|--------|------|--------|
| C1: MOE Timoshenko shear correction missing | 8-15% overestimation | `bending/merge_and_moe.py` | **RESOLVED** — `_timoshenko_correction_factor()` at L211, wired at L315 |
| C2: FFT confidence score not physics-based | Arbitrary heuristic | `core/analysis.py` | **RESOLVED** — `ConfidenceComponents` at L61, physics-based at L264-327 |
| C3: No uncertainty propagation in TF/coherence | Point estimates only | `core/dsp.py` | Missing |

**Justification for documenting:** Transparency about measurement limitations is part of forensic defensibility.

---

*Audit completed: 2026-05-22*  
*Document owner: Governance audit process*  
*Next review: Upon schema version bump or ADR update*
