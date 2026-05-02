# CLAUDE.md — Orientation for AI Coding Assistants

**Read this file before doing any work in this repo.**

This file exists to keep AI coding assistants (Claude, Copilot, etc.) grounded in
the actual state and constraints of `tap_tone_pi`. Sessions that skip reading
this file tend to drift — proposing things that already exist, suggesting work
that violates the measurement-only boundary, or rebuilding patterns that the
repo has already established.

If you are an AI assistant: read this in full. If you are a human reviewing AI
output: check that the AI followed the rules below.

---

## What this repo is

`tap_tone_pi` is a **measurement instrument toolchain** for luthier lab work.
It captures and analyzes acoustic and mechanical signals from instrument
soundboards and assembled bodies. Three workflows:

- **Phase 1** — Single-mic tap-tone capture and FFT peak extraction
- **Phase 2** — Roving-grid 2-channel capture, ODS (operational deflection
  shape), transfer functions, coherence, and WSI metrics
- **Bending rig** — Static bending stiffness measurements (EI, MOE) with
  GUM-compliant uncertainty

There is also a desktop GUI (`analyzer/`) that loads measurement outputs and
visualizes them.

## What this repo IS NOT — the measurement boundary

This is a hard architectural rule. **Do not violate it.**

This repo:
- Does NOT interpret "tone quality" or "good vs bad" sounds
- Does NOT prescribe structural modifications
- Does NOT optimize designs
- Does NOT grade instruments

This repo:
- Captures evidence (WAV files + capture metadata)
- Computes deterministic DSP summaries (peaks, transfer functions,
  coherence)
- Persists structured artifacts (session folders, JSON outputs, schemas)
- Validates outputs against contracts in `contracts/`

If a request would involve advisory logic, design optimization, or tone-quality
interpretation, **reject it or route it to a downstream system** (e.g.,
`luthiers-toolbox`). Do not add such logic to this repo.

See:
- `docs/MEASUREMENT_BOUNDARY.md` — the canonical boundary statement
- `docs/ADR-0001-measurement-scope.md` — original architectural decision
- `docs/ADR-0009-advisory-boundary.md` — most recent boundary refinement
- `ci/no_logic_creep.yml` — automated guardrail

---

## Repository structure

```
tap_tone_pi/                  Main package
├── analyzer/                 Standalone — desktop GUI (PyQt6 + matplotlib)
├── tap_tone_pi/              Core measurement modules
│   ├── bending/              Bending stiffness rig pipeline
│   ├── calibration/          Loopback, reference tone, FR compensation
│   ├── capture/              Audio + serial device capture
│   ├── chladni/              Chladni pattern indexing + tolerance policy
│   ├── cli/                  Unified CLI (entry point: `ttp`)
│   ├── damping/              Q-factor / damping measurement
│   ├── design/               Plate dynamics (Rayleigh-Ritz, thickness calc)
│   ├── multitap/             Multi-tap statistical analysis
│   ├── phase2/               ODS / scanning workflow
│   ├── signal_gen/           Sine, sweep, noise, multitone generators
│   ├── wolf/                 Wolf-tone detection
│   └── ...
├── scripts/
│   └── phase2/               Phase 2 vertical-slice runner + DSP + viz
├── contracts/                JSON schemas (draft 2020-12)
├── docs/                     Architecture decisions, dev orders, plans
├── examples/                 Reference inputs (e.g., phase2_grid_mm.json)
└── tests/                    pytest suite
```

**Key insight:** `scripts/phase2/` is a runner-level directory. The package-level
modules in `tap_tone_pi/phase2/` are the importable API. Do not import from
`scripts/` in package code — it creates fragile dependencies.

---

## Before any code work — orientation prompts

Run these commands at the start of each session and confirm what they show
before proposing any new code:

```bash
# 1. Repo state
git log --oneline -10

# 2. Active dev order
cat docs/dev_orders/CURRENT.md 2>/dev/null || echo "No active dev order"

# 3. Gap inventory (what's actually missing vs already shipped)
head -100 docs/01_GAP_INVENTORY.md 2>/dev/null

# 4. Test baseline
pytest --collect-only 2>&1 | tail -5
```

If `docs/01_GAP_INVENTORY.md` exists, it is **authoritative** for what's
shipped vs missing. Trust it over your training data or memory.

For deeper orientation by topic area, see `docs/02_ORIENTATION_PROMPTS.md`.

---

## Anti-drift rules

1. **Before writing more than ~50 lines of new code, grep the repo** for similar
   functionality. The Rayleigh-Ritz solver, the Phase 2 workflow, the bending
   pipeline, signal generators, calibration — all already exist. Do not rebuild
   them.

2. **Schemas live in `contracts/`** with file naming `*_v{N}.schema.json`. New
   structured data needs a schema there. Existing patterns:
   `phase2_grid.schema.json`, `phase2_point_capture_meta.schema.json`,
   `viewer_pack_v1.schema.json`.

3. **Provenance is mandatory.** Every measurement output records: SHA-256 of
   inputs, timestamp UTC, environment (tempC, RH), schema version. Follow the
   pattern in `tap_tone_pi/chladni/index_patterns.py` and
   `tap_tone_pi/bending/qa_lab_spec.py`.

4. **The Rayleigh-Ritz solver in `tap_tone_pi/design/rayleigh_ritz.py`
   is the prediction engine.** It exposes `solve_rayleigh_ritz()` →
   `RayleighRitzResult`, which has `get_mode_shape(mode_index, x, y)`. New
   prediction code calls these methods, does not reimplement plate dynamics.

5. **Phase 2 / ODS scanning workflow is shipped, not missing.** Schemas in
   `contracts/phase2_*.json`, modules in `tap_tone_pi/phase2/`, runner in
   `scripts/phase2_slice.py`, CLI as `ttp phase2`. New scanning work integrates
   with this; it does not replace it.

6. **Desktop GUI is PyQt6 + matplotlib via FigureCanvasQTAgg.** Follow the
   patterns in `analyzer/widgets/spectrum_chart.py` and
   `analyzer/widgets/bode_plot.py` for new widgets.

7. **CLI follows a unified entry point.** Add new commands to
   `tap_tone_pi/cli/main.py` as `cmd_xxx` functions registered with argparse
   subparsers. Do not create new CLI scripts at the project root.

8. **Tests use pytest classes.** Follow `tests/test_rayleigh_ritz.py` as the
   pattern: `class TestSomething: def test_something(self): assert ...`. No
   custom test framework or runner.

9. **Imports go from `tap_tone_pi.xxx`**, not relative imports across modules.
   Tests can import from anywhere in the package.

10. **Type hints are encouraged but not enforced.** Where present, follow the
    repo's existing style (PEP 604 union syntax `int | None`, NDArray with
    explicit dtype).

---

## Common patterns to follow

### Adding a measurement module

1. Code goes in `tap_tone_pi/{topic}/{name}.py`
2. JSON schema (if structured output) goes in `contracts/{name}.schema.json`
3. Tests go in `tests/test_{name}.py`
4. CLI command (if user-facing) goes in `tap_tone_pi/cli/main.py` as `cmd_xxx`
5. ADR (if architecturally significant) goes in `docs/ADR-{NNNN}-{topic}.md`

### Adding an analyzer widget

1. Widget class goes in `analyzer/widgets/{name}_widget.py`
2. Loader (if needed) goes in `analyzer/loaders/{format}.py`
3. Wire into main window in `analyzer/main_window.py` as a tab or dock
4. Match style of existing widgets — same matplotlib patterns, same
   layout conventions

### Adding a JSON schema

1. File in `contracts/{name}_v{N}.schema.json`
2. Use draft 2020-12: `"$schema": "https://json-schema.org/draft/2020-12/schema"`
3. Include `schema_version` const at top
4. Use `additionalProperties: false` for strict validation
5. Document in `contracts/schema_registry.json`

---

## Active dev orders

The current development plan is tracked in:

- `docs/03_THREE_WEEK_DEV_PLAN.md` — full plan with all dev orders
- `docs/dev_orders/CURRENT.md` — pointer to active order
- `docs/dev_orders/completed/` — historical record of finished orders
- `docs/dev_orders/backlog/` — future orders not yet active

If you are working on a dev order, the order spec defines acceptance criteria.
Do not exceed scope. If a tangent emerges, write a new dev order rather than
silently expanding current work.

---

## Testing

```bash
# Run all tests
pytest

# Run specific module
pytest tests/test_rayleigh_ritz.py -v

# Run with coverage
pytest --cov=tap_tone_pi --cov-report=term-missing
```

Pre-existing test failures (if any) should be documented in
`docs/dev_orders/CURRENT.md` and not "fixed" as part of unrelated dev orders.

---

## When in doubt

- **Doubt about whether something exists:** grep the repo. Run the orientation
  prompts. Check `docs/01_GAP_INVENTORY.md`.
- **Doubt about whether to add advisory logic:** don't. Route it to
  `luthiers-toolbox` instead.
- **Doubt about scope:** read the active dev order. If unclear, ask the human
  before proceeding.
- **Doubt about style:** find a similar existing module and follow its pattern.

The repo has been engineered carefully. Most "improvements" an AI assistant
might propose are actually drift from established patterns. Default to
conservatism — extend what's there, don't replace it.

---

## File index — where to find common things

| Looking for... | Location |
|---|---|
| The Rayleigh-Ritz solver | `tap_tone_pi/design/rayleigh_ritz.py` |
| Mode shape evaluation | `RayleighRitzResult.get_mode_shape()` (same file) |
| Phase 2 grid schema | `contracts/phase2_grid.schema.json` |
| Phase 2 grid loader | `scripts/phase2/grid.py` |
| Phase 2 DSP (transfer functions, coherence) | `scripts/phase2/dsp.py` |
| Phase 2 visualization | `scripts/phase2/viz.py` |
| Phase 2 metrics (PointSpectrum, WSI) | `scripts/phase2/metrics.py` |
| Tuning fork / FFT peaks | `tap_tone_pi/chladni/peaks_from_wav.py` |
| Frequency tolerance policy | `tap_tone_pi/chladni/policy.py` |
| Signal generators | `tap_tone_pi/signal_gen/generators.py` |
| Calibrated capture | `tap_tone_pi/capture/` + `tap_tone_pi/calibration/` |
| Bending MOE calc | `tap_tone_pi/bending/merge_and_moe.py` |
| GUM uncertainty | `tap_tone_pi/bending/qa_lab_spec.py` |
| Damping (Q) measurement | `tap_tone_pi/damping/modes.py` |
| Multi-tap statistics | `tap_tone_pi/multitap/` |
| Wolf-tone detection | `tap_tone_pi/wolf/` |
| Desktop GUI main window | `analyzer/main_window.py` |
| Spectrum chart widget | `analyzer/widgets/spectrum_chart.py` |
| Plate tuning regression | `analyzer/widgets/plate_tuning.py` |
| Wood properties analysis | `analyzer/analysis/wood_properties.py` |
| CLI entry point | `tap_tone_pi/cli/main.py` |
| Example Phase 2 grid | `examples/phase2_grid_mm.json` |

---

*Last updated: 2026-05-02*

*If anything in this file is wrong, that is a bug. File an issue or fix the
file. Drift between this document and reality is more harmful than no
document at all.*
