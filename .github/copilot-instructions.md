# Tap Tone Pi — AI Coding Agent Instructions

## Mission & Boundary (Non‑Negotiable)
This repo is a **measurement instrument**. Output facts only (FFT peaks, ODS transfer functions, coherence, WSI, MOE/EI). Do **not** provide tone scoring, recommendations, or “good/bad/dominant” language. See [docs/MEASUREMENT_BOUNDARY.md](../docs/MEASUREMENT_BOUNDARY.md).

## Architecture (Where to add features)
- `tap_tone_pi/` is v2 primary: `core/` DSP + quality gate, `cli/` (`ttp`), `storage/` I/O, `agent/` presentation layer, `agentic/` event‑driven spine, `workflow/` state machine, `gui/` Tkinter.
- `tap_tone/` is legacy v1 single‑mic (frozen).
- `modes/_shared/` is canonical shared infra (WAV I/O + manifest). Other `modes/*` are legacy compat.
- `scripts/phase2/` and `tools/run_phase2.py` implement Phase‑2 ODS/coherence/WSI runs.

## Critical workflows
- Install/editable: `pip install -e .`
- Tests/lint/typecheck: `make test`, `make test-wav-io`, `make lint`, `make typecheck`, `make ci-dry-run`.
- Phase 2 (recommended runner avoids PYTHONPATH issues):
  - `python tools/run_phase2.py run --grid examples/phase2_grid_mm.json --out ./runs_phase2 --synthetic`
  - `python tools/run_phase2.py devices`
- CLI entry: `ttp` (see `tap_tone_pi.cli.main:main`).

## Project-specific patterns (enforced)
- **Pure DSP, no I/O** in analysis (e.g., `tap_tone_pi/core/analysis.py`, `scripts/phase2/dsp.py`). File writes go through `tap_tone_pi/storage/` or `modes/_shared/emit_manifest.py`.
- **WAV I/O single source**: use `modes/_shared/wav_io.py` (never `scipy.io.wavfile`). CI enforces.
- **Quality gate**: rules in `tap_tone_pi/core/quality_policy.py`, enforcement in `tap_tone_pi/core/quality_gate.py` (`ttp record` = evidence only; `ttp measure` = blocking gate).
- **Schemas are contracts**: update `contracts/*.schema.json` and bump `contracts/schema_registry.json` for any output field change (breaking changes require a new ADR in `docs/`).

## Evidence pack invariants (do not break)
- `analysis.json` is factual only; labels like `peak_1`/`user_label` only.
- `spectrum.csv` header/order fixed; frequency bins identical across points in a session.
- No OS‑specific absolute paths in metadata. See [docs/contracts/EVIDENCE_PACK_CONTRACT_v1.md](../docs/contracts/EVIDENCE_PACK_CONTRACT_v1.md).

## Agentic layer boundaries
- `tap_tone_pi/agent/` is presentation only (messages + renderers). Never tune DSP thresholds or alter `QualityVerdict` logic.
- Decision policy lives in `tap_tone_pi/agentic/` (see [docs/AGENT_DECISION_POLICY_V1.md](../docs/AGENT_DECISION_POLICY_V1.md)).
- Agent behavior changes require selector/message tests.

## Hard boundaries / CI guardrails
- Forbidden imports: `app.*`, `services.*`, `packages.*` (ToolBox namespaces). Check with `python ci/check_boundary_imports.py --preset analyzer`.
- Do not change CSV headers, FFT binning, or add quality/interpretation language.
