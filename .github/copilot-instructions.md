# Tap Tone Pi — AI Coding Agent Instructions

## Mission (Non-Negotiable)
**Acoustic measurement instrument** — outputs facts (peaks, coherence, phase, RMS), NOT design advice.
- ✅ FFT spectra, ODS transfer functions, Wolf Stress Index (WSI), MOE/EI values
- ❌ NO tone scoring, voicing recommendations, or optimization suggestions
- ❌ NO "good/bad/worst/dominant" language — only factual labels (`peak_1`, `candidate frequency`)

> The analyzer exports evidence and derivations, never conclusions. Interpretation is a human act.

## Architecture — Two Packages + Shared Substrate
```
tap_tone_pi/         # v2.0 PRIMARY — active development
  core/              #   analysis.py, quality_gate.py, quality_policy.py, dsp.py, auto_trigger.py
  cli/               #   main.py → ttp command (record, measure, export-pack, gold-run, gui, ...)
  agent/             #   MeasurementAgent — presentation layer (see Agent Boundaries below)
  agentic/           #   Event-driven spine (moments engine, policy engine, replay)
  workflow/          #   operator_loop.py (state machine), attempt.py (retry tracking)
  gui/               #   Tkinter app, widgets, grid_widgets, export
  storage/           #   File I/O layer (loadcell_serial, dial_indicator_serial, simulators)
tap_tone/            # v1.0 FROZEN — legacy single-channel; do not add features here
modes/               # Shared substrate — still depended on; do NOT remove
  _shared/           #   CANONICAL: wav_io.py (only WAV I/O), emit_manifest.py
  bending_rig/       #   Legacy — migrated to tap_tone_pi/bending/ (kept for compat/tests)
  chladni/           #   Legacy — migrated to tap_tone_pi/chladni/ (kept for compat/tests)
  acquisition/       #   Legacy — migrated to tap_tone_pi/storage/ (kept for compat/tests)
contracts/           # schema_registry.json + *.schema.json — bump version on any change
scripts/phase2/      # 2-channel ODS, coherence, wolf metrics
```
**CLI entry point:** `ttp` (registered in `pyproject.toml` → `tap_tone_pi.cli.main:main`).

> ⚠️ `modes/_shared` is **canonical shared infrastructure** imported across all packages, scripts, and tests.
> Other `modes/<name>` dirs are frozen compatibility — new features go in `tap_tone_pi/`.

## CI Boundary — Will Fail Build
```bash
python ci/check_boundary_imports.py --preset analyzer
```
**Forbidden imports:** `app.*`, `services.*`, `packages.*` (Luthier's ToolBox namespaces).
Pass data via artifacts (JSON/CSV/WAV + manifests), never Python imports.

## Commands
```bash
pip install -e .          # Install (editable)
make test                 # Full pytest suite
make test-wav-io          # WAV I/O roundtrip tests
make lint                 # Ruff linting
make typecheck            # mypy
make ci-dry-run           # Full local CI: tests → coverage → demos → schema validation
make help                 # All Makefile targets
ttp measure --out ./sess --auto-trigger   # Quality-gated measurement
ttp export-pack                           # Export viewer pack ZIP
ttp evidence-check --session ./sess       # Preflight validate session evidence artifacts
python scripts/phase2_slice.py run --synthetic --grid examples/phase2_grid_mm.json --out ./runs_phase2
```

## Code Patterns (Enforced)

### Pure DSP → Frozen Dataclass (No I/O in analysis)
```python
# tap_tone_pi/core/analysis.py
def analyze_tap(audio: np.ndarray, sample_rate: int, **params) -> AnalysisResult: ...
# scripts/phase2/dsp.py
def compute_transfer_and_coherence(x_ref, x_rov, fs, ...) -> TFResult: ...
```
File writes go through `storage/` or `modes/_shared/emit_manifest.py`.

### WAV I/O — Single Source of Truth
```python
from modes._shared.wav_io import read_wav_mono, read_wav_2ch, write_wav_mono, write_wav_2ch
```
**NEVER** use `scipy.io.wavfile` directly — causes int16↔float drift. CI enforces this.

### Quality Gate (HARD/SOFT rules)
- `tap_tone_pi/core/quality_policy.py` — rule definitions (Q001–Q005 HARD=FAIL, Q010–Q013 SOFT=WARN)
- `tap_tone_pi/core/quality_gate.py` — enforcement, returns `QualityVerdict`
- `ttp record` = evidence only; `ttp measure` = blocking gate

### Schema Contracts
All outputs validated against `contracts/*.schema.json`. Registry at `contracts/schema_registry.json`.
**Any new output field** → update schema + bump registry version. Breaking changes need `docs/ADR-*.md`.

## Evidence Pack Contract (Summary)
Full spec: [docs/contracts/EVIDENCE_PACK_CONTRACT_v1.md](../docs/contracts/EVIDENCE_PACK_CONTRACT_v1.md)

**Layout:** `{session}/{point}/attempt_{NNN}/...`

| Status | Artifact | Notes |
|--------|----------|-------|
| MUST | `audio.wav` | Exact recording that produced spectrum; PCM int16/int24 |
| MUST | `analysis.json` | Peaks as annotations — no judgments |
| MUST | `capture_meta.json` | Device, sample rate, timestamp |
| MUST | `quality_check.json` | QualityVerdict from gate |
| SHOULD | `spectrum.csv` | `freq_hz,H_mag,coherence,phase_deg` — monotonic bins |
| SHOULD | `spectrum.png` | Optional visualization |

**Session-level** (`wolf/`): `wsi_curve.csv`, `wolf_candidates.json` — explicit thresholds, no quality language.

**Invariants:** Point IDs stable across session; attempt numbering monotonic; all points share identical `freq_hz` bins; unknown files allowed (ToolBox ignores extras).

## Agent Boundaries (Contributor Guardrails)
The agent (`tap_tone_pi/agent/`) is the **presentation + action-suggestion layer**. It is never measurement truth.

**Non-goals (forbidden):**
- Agent must NOT tune DSP parameters, thresholds, or alter `QualityVerdict` logic
- No interpretation beyond "PASS/WARN/FAIL + reason"
- No auto-"fixing" measurements

**Inputs/outputs contract:**
- Inputs: `QualityVerdict`, `Attempt`, persisted FTUE state
- Outputs: message objects (title, explanation rows, suggestion rows, actions)
- Rendering is separate (CLI/GUI renderers in `render.py`)

**Where to change what:**
| Change | File(s) |
|--------|---------|
| Add/edit rule copy | `agent/message_spec.py`, `agent/messages.py` |
| Change verbosity/escalation | `agent/selector.py` |
| Change presentation format | `agent/render.py` |
| Persist new FTUE signal | `agent/user_config.py` + tests (never in QC) |

**Testing:** Every agent behavior change needs ≥1 selector/message test; CLI wiring changes need ≥1 CLI-level test.

## When Adding Features
1. **DSP:** Pure function → `@dataclass(frozen=True)` result → test with synthetic sine bursts
2. **New output field:** Update schema in `contracts/`, bump `schema_registry.json`
3. **Hardware-free validation:** Add `--synthetic` path (see `phase2_slice.py`)
4. **Provenance:** Include `algo_id`/`algo_version` + numpy/scipy versions via `get_dsp_provenance()`
5. **Evidence export:** No ranking, no quality language, deterministic output
6. **Evidence preflight:** Run `ttp evidence-check --session <dir>` before export/ToolBox ingestion; schema validation remains separate

## Forbidden Patterns (Will Break Contract)
- Changing CSV header names/case after release; varying FFT bins across session points
- `scipy.io.wavfile` outside `modes/_shared/wav_io.py`
- Interpretation language: "strongest", "worst", "good", "bad", "wolf likely", "problem"
- Prescriptions: "thin here", "remove mass", "A0 too high"
- Automatic mode labels ("A0", "T(1,1)") without validated method — use `peak_1`/`user_label`
- Silent filtering/smoothing — if processed, export raw + derived separately
- OS-specific absolute paths in exported metadata
- Missing files in `viewer_pack.json.files[]`

## Key References
- [docs/MEASUREMENT_BOUNDARY.md](../docs/MEASUREMENT_BOUNDARY.md) — Scope policy
- [contracts/schema_registry.json](../contracts/schema_registry.json) — Schema versions
- [DEV_HANDOFF.md](../DEV_HANDOFF.md) — Architecture overview
- [docs/contracts/EVIDENCE_PACK_CONTRACT_v1.md](../docs/contracts/EVIDENCE_PACK_CONTRACT_v1.md) — Full evidence pack column specs
- [docs/AGENT_DECISION_POLICY_V1.md](../docs/AGENT_DECISION_POLICY_V1.md) — Agent decision policy
