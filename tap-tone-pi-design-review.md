# tap_tone_pi — 1% Critical Design Review

**Reviewer posture:** Skeptical outside evaluator. No credit for intent — only what the artifact proves.

**Date:** 2026-02-05
**Artifact:** `tap_tone_pi-main` (commit snapshot, ~1.8 MB zipped)
**Stack:** Python 3.10+, NumPy/SciPy, sounddevice, Tkinter GUI, CLI via argparse
**Quantitative profile:**
- 20,834 lines of Python across 151 files
- 3,964 lines of tests across 25 test files (19% test ratio)
- 200 KB of documentation across 25 markdown files

---

## Stated Assumptions

1. **Target user is a solo luthier/researcher** measuring acoustic properties of tonewoods, guitar plates, and similar specimens. They have a USB microphone and possibly a Raspberry Pi at their workbench.

2. **"Measurement-only" is the design philosophy.** The system measures and logs; it does not advise, score, or optimize. I'm taking this boundary doctrine at face value.

3. **This is a companion system to the Luthier's ToolBox**, not a standalone product. Export artifacts (viewer packs) flow into the ToolBox for interpretation.

4. **The existing in-repo design review (tap_tone_pi_design_review.md) is prior art.** I've checked its bug findings: both bugs (peaks_from_wav return order, storage.py arg order) have been **fixed** in this snapshot.

5. **Hardware validation is incomplete.** The `out/` directory and test fixtures suggest Phase 2 ODS has only run in synthetic/simulated mode. Real roving-grid sessions with actual hardware have not been committed.

---

## Category Scores

### 1. Purpose Clarity — 9/10

**What's good:** This is the project's standout dimension. The measurement-only philosophy is articulated with unusual rigor:

- The README opens with "**Boundary:** This project measures and summarizes signals. It does **not** interpret 'tone quality' or prescribe structural modifications."
- GOVERNANCE.md runs 400+ lines defining what the system may and may not express.
- The ADR trail (7 architecture decision records) documents boundary decisions.
- The "IS / IS NOT" table in the README is crystal clear.

The phrase "Analysis is permitted; interpretation is prohibited" is a loadbearing design principle and it appears consistently across boundary documentation. This is architectural discipline that most professional engineering organizations don't achieve.

**What's wrong:** Version identity is fragmented. `pyproject.toml` says `2.0.0`, BUILD_READINESS says `v2.0-instrumentation`, the schema registry says `1.0.0` and `2.0.0` for different schemas. There's a CHANGELOG but no release tags. The `pyproject.toml` description says "Offline tap tone analyzer for Raspberry Pi" which undersells the actual scope (ODS, Chladni, bending rig, wolf metrics).

**Concrete improvements:**
- Update pyproject.toml description to match the actual scope: "Multi-mode acoustic measurement toolchain for lutherie (tap tone, ODS, bending stiffness, Chladni patterns)."
- Tag releases in git. The CHANGELOG exists but has no corresponding tags.
- Pick one version number and propagate it everywhere (pyproject.toml is the single source of truth; everything else references it).

---

### 2. User Fit — 7/10

**What's good:** The domain modeling is authentic. WSI (Wolf Stress Index), transfer function coherence, Chladni pattern analysis, three-point bending MOE calculations — this is the work of someone who actually measures tonewoods.

The QUICKSTART.md and FIRST_MEASUREMENT_CHECKLIST.md are excellent onboarding documents. They meet the user where they are ("What Success Looks Like: Read This First") and include a troubleshooting table. The 5-minute quickstart is genuinely achievable for a user who can install Python.

**What's wrong:** The happy path still requires CLI proficiency:

```bash
python -m tap_tone.main record \
  --device 1 \
  --seconds 2.5 \
  --out ./captures/session_001 \
  --label "OM_top_bridge_tap"
```

A luthier who wants to tap a plate and see frequencies must know their audio device index, construct a CLI invocation with flags, and interpret JSON output. The GUI exists but is a Tkinter shell that doesn't display spectra inline — results go to files.

Phase 2 (ODS) is steeper still: users must understand transfer functions, manage grid JSON files, and run multi-point capture sequences manually.

**Concrete improvements:**
- Add a zero-argument entry point: `ttp quick` that auto-detects the microphone, captures, analyzes, and displays the spectrum in a popup window.
- Embed matplotlib spectrum plots in the GUI instead of writing PNGs and showing message boxes.
- Add a "guided capture" mode for Phase 2 that prompts "Tap point A1 now... Tap point A2 now..." instead of requiring grid JSON pre-configuration.
- Consider a local web UI (Flask + simple HTML) instead of Tkinter. It's more portable to Raspberry Pi deployments and can display plots natively.

---

### 3. Usability — 6/10

**What's good:** The Makefile is well-organized (370 lines, clear target naming, sensible defaults). The project has exactly one way to do most things: `tap_tone/main.py` for Phase 1, `scripts/phase2_slice.py` for Phase 2, `gui/app.py` for GUI. The duplicated entry points problem noted in earlier reviews appears to be mostly resolved.

The CLI structure is clean:
```
tap-tone devices      # list audio devices
tap-tone record       # single capture
tap-tone live         # loop capture
tap-tone gold-run     # full validated session
```

**What's wrong:** There are still multiple module structures that feel redundant:

- `tap_tone/` — Phase 1 package (installed as `tap-tone` entry point)
- `tap_tone_pi/` — apparent Phase 2 restructure (installed as `ttp` entry point)
- `modes/` — mode scripts for acquisition, bending rig, Chladni, etc.
- `scripts/` — yet more CLI tools including `phase2_slice.py`

The relationship between `tap_tone/`, `tap_tone_pi/`, and `modes/` is unclear. Are they competing implementations? Migration stages? The pyproject.toml installs both `tap-tone` and `ttp` entry points pointing to different packages.

The GUI subprocess pattern (shelling out to mode scripts) was noted in the existing review. It appears partially fixed — the GUI now has direct import paths for some analysis — but some workflows still invoke subprocess.

**Concrete improvements:**
- Consolidate into a single package namespace. If `tap_tone_pi` is the future, delete or formally deprecate `tap_tone/`.
- Document the relationship between `modes/`, `scripts/`, and the main packages in a ARCHITECTURE.md file.
- Complete the GUI migration to direct imports — eliminate all `subprocess.check_call` invocations.

---

### 4. Reliability — 7/10

**What's good:** The bugs identified in the prior design review have been fixed:
- `peaks_from_wav.py` now correctly destructures `x, meta = read_wav_mono(...)`
- `storage.py` now correctly calls `write_wav_mono(audio_path, audio, sample_rate)`

There are **zero bare `except:` clauses** in the codebase (excellent discipline). The 34 broad `except Exception` blocks are mostly in appropriate places: GUI error dialogs, optional feature detection, and non-critical logging.

The CI boundary check (`ci/check_boundary_imports.py`) prevents accidental coupling to the Luthier's ToolBox. Schema validation is enforced via JSON Schema contracts in `contracts/`. The viewer pack export has a validation gate that fails-fast on malformed output.

**What's wrong:** Test coverage is claimed at ~55% in the existing review. The test-to-production ratio (3,964 / 16,870 = 24%) is decent but there are gaps:
- No integration tests for the GUI path
- No end-to-end tests that run capture → analysis → export → validation on real hardware
- The `tests/` directory has no fixtures for Phase 2 sessions

The `except Exception` blocks in `modes/chladni/manifest_utils.py` are overly broad — they silently fall back on parse failures instead of failing loudly.

**Concrete improvements:**
- Add a GUI smoke test that launches the app, exercises each button, and verifies no exceptions.
- Add an integration test that uses simulated audio input to exercise the full pipeline (capture → analyze → export → validate).
- Tighten exception handling in `manifest_utils.py` — catch `json.JSONDecodeError` and `KeyError` specifically, not bare `Exception`.
- Run `pytest --cov` in CI and publish the actual coverage number.

---

### 5. Maintainability — 8/10

**What's good:** The codebase is appropriately sized. The largest file is 837 lines (`scripts/session_close.py`), which is large but not pathological. Most files are under 500 lines. Type hints are present and consistently applied via frozen dataclasses and proper `from __future__ import annotations`.

The schema registry (`contracts/schema_registry.json`) defines ownership and versioning policy for each contract. The ADR trail documents architectural decisions. The CI boundary guard prevents cross-repo coupling.

The documentation-to-code ratio is healthy: 200 KB of docs for 20K lines of code. Unlike the Luthier's ToolBox, the docs here are *user-facing* (QUICKSTART, FIRST_MEASUREMENT_CHECKLIST) rather than developer archaeology.

**What's wrong:** There are still duplicated schemas between `schemas/` and `contracts/schemas/`. The executive_summary.md notes this gap but it hasn't been resolved in this snapshot. Having two schema directories with different versions of the same schemas is a maintenance trap.

The `modes/` directory has 5 subpackages (`acquisition`, `bending_rig`, `bending_stiffness`, `chladni`, `provenance_import`) plus `_shared`, and its relationship to the main `tap_tone_pi/` package is unclear.

**Concrete improvements:**
- Declare `contracts/` as the single source of truth for schemas. Delete or symlink `schemas/` to avoid divergence.
- Either merge `modes/` into `tap_tone_pi/` or formally document it as a separate concern (e.g., "modes/ contains hardware acquisition scripts that are not part of the core package").
- Add a top-level ARCHITECTURE.md that shows the package dependency graph.

---

### 6. Cost (Resource Efficiency) — 8/10

**What's good:** The dependency set is minimal and appropriate:
- numpy, scipy — core DSP
- sounddevice — audio capture
- matplotlib — visualization
- pyserial — hardware communication
- jsonschema — contract validation

No heavyweight frameworks. No cloud dependencies. Runs on a Raspberry Pi. The development dependencies (pytest, mypy, ruff, black, pre-commit) are standard and well-chosen.

The Makefile provides simulated modes (`make sim-load`, `make sim-dial`) for testing without hardware — this is excellent for development cost.

**What's wrong:** The Tkinter GUI is a sunk cost that delivers limited value. It shells out to subprocesses, doesn't display plots inline, and provides a worse experience than the CLI. The development effort in `gui/app.py` (569 lines) and `tap_tone_pi/gui/app.py` (another copy) could have been spent on a web UI or a better CLI experience.

**Concrete improvements:**
- Evaluate whether the Tkinter GUI is worth maintaining. If <10% of users use it, consider deprecating in favor of CLI-only or a minimal web UI.
- If keeping the GUI, consolidate to one location and invest in inline spectrum display.

---

### 7. Safety — 8/10

**What's good:** The measurement-only boundary is a safety feature. The system explicitly refuses to interpret results or recommend structural modifications. This prevents a luthier from following bad AI advice to thin a plate too much.

The viewer pack validation gate rejects malformed exports. The boundary CI check prevents accidentally shipping code that couples to advisory systems. The schema contracts enforce data hygiene at export time.

Serial input (load cells, dial indicators) includes configurable baud rate and pattern matching, though validation could be tighter.

**What's wrong:** There's no explicit warning when audio input is clipping or saturated — the analysis just produces lower-confidence results. A safety-conscious system would refuse to proceed or display a prominent warning when the input is unusable.

The serial acquisition scripts (`loadcell_serial.py`, `dial_indicator_serial.py`) parse freeform text from hardware devices using regex. Malformed input could produce silent garbage rather than failing loudly.

**Concrete improvements:**
- Add a hard gate: if `clipped: true` in analysis, display a warning dialog (GUI) or print a prominent warning (CLI) and ask user to re-capture.
- Add input validation to serial acquisition: if the parsed value is outside physical plausibility (e.g., negative force, displacement > 100mm), reject the reading.
- Consider adding a "confidence floor" parameter: if analysis confidence drops below threshold, warn the user rather than silently proceeding.

---

### 8. Scalability — 6/10

**What's good:** The artifact-first design (sessions stored as directories of JSON/WAV/CSV files) scales horizontally. You can run thousands of sessions without database complexity. SHA-256 hashing provides integrity verification. The viewer pack format is designed for cross-system portability.

The schema versioning policy (patch = self-approve, minor = owner-review, major = ADR + signoff) is appropriate for a project that may grow.

**What's wrong:** The system is designed for single-operator use. There's no concept of:
- Multi-user access or permissions
- Concurrent capture sessions
- Centralized session storage or search
- Batch processing of historical data

This is fine for the current scope but limits growth if the system becomes a team tool or SaaS product.

The Phase 2 grid format requires manual JSON editing to define tap points. For complex grids (50+ points), this doesn't scale.

**Concrete improvements:**
- Add a grid editor (CLI or GUI) that lets users define points interactively rather than editing JSON.
- Consider a SQLite index for session metadata (not replacing file storage, just indexing for search).
- Document that the current architecture assumes single-operator use; any multi-user extension would require redesign.

---

### 9. Aesthetics (UI/UX Design) — 5/10

**What's good:** The CLI output is clean and informative. The Makefile target naming follows Unix conventions. The session directory structure (`points/`, `derived/`, `plots/`) is logical.

**What's wrong:** The Tkinter GUI is visually dated and functionally limited. It's a form-based launcher that shows message boxes for results. There's no inline spectrum visualization, no waveform display, no live feedback during capture.

The plot styling in matplotlib output (when generated) uses default colors and fonts. For a tool that produces reports for lutherie work, professional plot aesthetics matter.

**Concrete improvements:**
- If keeping the GUI, add embedded matplotlib figures (the infrastructure exists — `FigureCanvasTkAgg` is imported but barely used).
- Define a consistent plot style (color palette, font, axis formatting) and apply it to all generated figures.
- Consider replacing Tkinter with a local web UI (Flask + Plotly or similar) for richer visualization.

---

## Summary Scorecard

| Category | Score | Weight | Weighted |
|---|---|---|---|
| Purpose Clarity | 9/10 | 1.0 | 9.0 |
| User Fit | 7/10 | 1.5 | 10.5 |
| Usability | 6/10 | 1.5 | 9.0 |
| Reliability | 7/10 | 1.5 | 10.5 |
| Maintainability | 8/10 | 1.5 | 12.0 |
| Cost / Resource Efficiency | 8/10 | 1.0 | 8.0 |
| Safety | 8/10 | 2.0 | 16.0 |
| Scalability | 6/10 | 0.5 | 3.0 |
| Aesthetics | 5/10 | 0.5 | 2.5 |
| **Weighted Average** | | | **7.68/10** |

---

## Comparison to Luthier's ToolBox

| Dimension | tap_tone_pi | luthiers-toolbox |
|---|---|---|
| Lines of Python | 20,834 | 227,136 |
| API routes | 0 (file-based) | 727 |
| Test ratio | 24% | ~17% |
| Bare excepts | 0 | 1 |
| Broad excepts | 34 | 700 |
| Largest file | 837 lines | 2,724 lines |
| Doc size | 200 KB | 11 MB |
| Weighted score | **7.68** | **5.15** |

tap_tone_pi demonstrates what the ToolBox could be if it underwent aggressive scope reduction. The measurement-only boundary doctrine works because it was enforced from the start.

---

## Top 5 Actions (Ranked by Impact)

1. **Consolidate package structure.** Pick one namespace (`tap_tone_pi`), migrate everything into it, and deprecate the others. The current `tap_tone/`, `tap_tone_pi/`, `modes/`, `scripts/` split is confusing.

2. **Add a zero-config entry point.** `ttp quick` should auto-detect the mic, capture, analyze, and display results with no flags. The happy path for first-time users should be one command.

3. **Resolve schema duplication.** Declare `contracts/` canonical, delete `schemas/`, and ensure all code imports from the single source of truth.

4. **Add clipping gate.** If `clipped: true`, refuse to proceed without user acknowledgment. This is a safety and data quality issue.

5. **Embed spectrum plots in GUI.** The infrastructure exists (`FigureCanvasTkAgg` is imported). Use it. A GUI that only shows message boxes provides no value over the CLI.

---

*This project earns a 7.68/10 — a solid B+ grade. The measurement-only philosophy is its greatest strength, and the codebase demonstrates that a focused scope produces a maintainable system. The main gaps are usability polish (entry points, GUI) and structural cleanup (package consolidation, schema deduplication). These are addressable in a single focused sprint.*
