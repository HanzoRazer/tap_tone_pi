# Claude Code Orientation Prompts

**Purpose:** Drop-in terminal prompts to ground Claude Code (or any AI assistant) in the actual state of the repos before starting work. Each prompt forces a specific verification of what already exists, so the assistant doesn't drift into rebuilding things or hallucinating gaps.

**Usage:** Copy the relevant prompt block into your terminal session at the start of work. Run the commands, paste output back into the chat as context. Then state the actual task.

---

## Prompt 0 — Universal session opener

Use this at the start of any session involving `tap_tone_pi` or `luthiers-toolbox`.

```bash
# === SESSION ORIENTATION: Read before any code work ===
echo "=== Current branch + last commits ==="
git log --oneline -10
echo ""
echo "=== Repo top-level structure ==="
ls -la
echo ""
echo "=== Reading the gap inventory (authoritative for what's missing) ==="
cat docs/01_GAP_INVENTORY.md 2>/dev/null | head -100 || echo "Gap inventory not yet committed"
echo ""
echo "=== Active sprint / dev order ==="
ls docs/dev_orders/ 2>/dev/null && cat docs/dev_orders/CURRENT.md 2>/dev/null | head -40 || echo "No active dev order"
```

**Then in chat:**
> "Before any work, confirm: what is your current understanding of (a) what's already shipped in this repo, (b) what the gap inventory says is missing, and (c) what dev order is active? Do not start any new work until you have read those three things and stated them back."

---

## Prompt 1 — Phase 2 / ODS scanning capability check

Use before any work that touches modal mapping, scanning, or grid-based measurement.

```bash
# === PHASE 2 / ODS SCANNING CAPABILITY ORIENTATION ===
echo "=== Phase 2 module structure ==="
ls tap_tone_pi/phase2/
echo ""
echo "=== Phase 2 schemas (JSON) ==="
ls contracts/ | grep phase2
echo ""
echo "=== Phase 2 scripts ==="
ls scripts/phase2/
echo ""
echo "=== Phase 2 CLI command exists? ==="
grep "def cmd_phase2" tap_tone_pi/cli/main.py | head -2
echo ""
echo "=== Example grid file ==="
cat examples/phase2_grid_mm.json 2>/dev/null | head -25
echo ""
echo "=== Phase 2 viz functions ==="
grep "^def " scripts/phase2/viz.py
echo ""
echo "=== Phase 2 metrics functions ==="
grep "^def " scripts/phase2/metrics.py
```

**Then in chat:**
> "Confirm what Phase 2 scanning capability already exists. Specifically state: (1) the schemas, (2) the capture workflow, (3) the visualization, (4) the export format, (5) the CLI entry point. Do NOT propose to build any of these — they exist. Only propose work that builds ON TOP of this foundation."

---

## Prompt 2 — Predicted-vs-measured comparison gap check

Use before work on modal prediction comparison, mode shape overlay, or Rayleigh-Ritz validation.

```bash
# === PREDICTED-VS-MEASURED ORIENTATION ===
echo "=== Rayleigh-Ritz solver (THE prediction engine) ==="
head -50 tap_tone_pi/design/rayleigh_ritz.py
echo ""
echo "=== Coupled 2-osc model ==="
head -30 tap_tone_pi/design/coupled_2osc.py
echo ""
echo "=== Search for ANY existing comparison code ==="
grep -rln "predicted.*measured\|residual.*shape\|compare.*mode\|prediction_vs" tap_tone_pi/ analyzer/ scripts/ 2>/dev/null
echo ""
echo "=== Phase 2 outputs that comparison would consume ==="
find scripts/phase2/ tap_tone_pi/phase2/ -name "*.py" -exec grep -l "PointSpectrum\|ods_snapshot\|wsi" {} \;
```

**Then in chat:**
> "Confirm: The Rayleigh-Ritz solver exists and produces predicted mode shapes. The Phase 2 workflow exists and produces measured spatial data. There is NO existing code that brings them together for comparison. The work to do is build the bridge. State your understanding of what that bridge needs to be."

---

## Prompt 3 — Analyzer GUI integration check

Use before work that touches the desktop analyzer.

```bash
# === ANALYZER GUI ORIENTATION ===
echo "=== Existing widgets ==="
ls analyzer/widgets/
echo ""
echo "=== Main window's tab/dock structure ==="
grep "addDockWidget\|addTab\|self.tabs\|QTabWidget\|QDockWidget" analyzer/main_window.py | head -20
echo ""
echo "=== Existing loaders (data input) ==="
ls analyzer/loaders/
echo ""
echo "=== Does analyzer load Phase 2 outputs? ==="
grep -l "phase2\|ods_snapshot" analyzer/**/*.py 2>/dev/null
echo ""
echo "=== Existing matplotlib widgets pattern ==="
head -30 analyzer/widgets/spectrum_chart.py
```

**Then in chat:**
> "Confirm: The analyzer is PyQt6, uses matplotlib via FigureCanvasQTAgg, has existing widget patterns I should follow. It does NOT currently have a Phase 2 / scanning results widget. New widgets should match the existing patterns in spectrum_chart.py and bode_plot.py. State your understanding of the widget architecture before proposing new ones."

---

## Prompt 4 — Wood characterization & material data check

Use before work on wood property database, plate experiments, or bending rig integration.

```bash
# === WOOD CHARACTERIZATION ORIENTATION ===
echo "=== Bending submodule ==="
ls tap_tone_pi/bending/
echo ""
echo "=== Bending procedure documentation ==="
ls *bending* *Bending* 2>/dev/null
echo ""
echo "=== Existing wood properties analysis ==="
head -40 analyzer/analysis/wood_properties.py
echo ""
echo "=== QA lab spec (uncertainty handling) ==="
head -30 tap_tone_pi/bending/qa_lab_spec.py
echo ""
echo "=== Does a per-flitch database exist? ==="
find . -name "wood_species*" -o -name "*flitch*" -o -name "wood_db*" 2>/dev/null
```

**Then in chat:**
> "Confirm: The bending rig measurement pipeline is shipped end-to-end (capture, MOE calculation, uncertainty). What is MISSING is a per-flitch persistent database that accumulates measurements across builds. Any new work in this area must build on the existing pipeline, not duplicate it."

---

## Prompt 5 — Build artifact freshness check

Use any time you suspect drift between memory and current repo state.

```bash
# === FRESHNESS / DRIFT CHECK ===
echo "=== Last 20 commits ==="
git log --oneline -20
echo ""
echo "=== Files modified in last 7 days ==="
find . -type f -name "*.py" -mtime -7 | head -20
echo ""
echo "=== Open dev orders ==="
ls docs/dev_orders/ 2>/dev/null
echo ""
echo "=== Closed/completed dev orders ==="
ls docs/dev_orders/completed/ 2>/dev/null
echo ""
echo "=== Run tests to confirm baseline works ==="
pytest --collect-only 2>&1 | tail -10
```

**Then in chat:**
> "State: (1) what is the current branch, (2) what dev order is in progress, (3) what dev orders are completed, (4) does the test baseline pass. Don't start work until those are answered."

---

## Drift-prevention rules (paste these into Claude Code system prompt or repo README)

1. **Before proposing any new module, file, or function, run the relevant orientation prompt above and confirm it doesn't already exist.**

2. **The gap inventory at `docs/01_GAP_INVENTORY.md` is authoritative.** If something is marked SHIPPED there, do not rebuild it. If marked MISSING, that's the work.

3. **Active dev order at `docs/dev_orders/CURRENT.md` defines current scope.** Do not exceed it. If a tangent emerges, write it as a future dev order, do not silently expand current work.

4. **Phase 2 ODS workflow exists.** It has schemas (`contracts/phase2_*.schema.json`), session state (`tap_tone_pi/phase2/`), DSP (`scripts/phase2/dsp.py`), visualization (`scripts/phase2/viz.py`), and CLI (`tap_tone_pi.cli.main:cmd_phase2`). New scanning work integrates with this, does not replace it.

5. **The Rayleigh-Ritz solver in `tap_tone_pi/design/rayleigh_ritz.py` is the prediction engine.** New prediction code should call it, not reimplement plate dynamics.

6. **The desktop analyzer is PyQt6 with matplotlib.** Follow patterns in `analyzer/widgets/spectrum_chart.py` and `analyzer/widgets/bode_plot.py` for new widgets.

7. **Schemas live in `contracts/`.** Any new structured data needs a JSON schema there. Existing pattern: `phase2_grid.schema.json`, `phase2_point_capture_meta.schema.json`.

8. **All measurement modules already track provenance** (sha256, timestamps, environment). New code MUST follow this convention.

9. **If you find yourself about to write more than 200 lines without checking the existing code, STOP** and run the relevant orientation prompt.

10. **End each session by updating the gap inventory** if anything materially shipped or got demoted. Do not let the inventory drift from reality.

---

## Anti-pattern detector (warning signs of drift)

Stop and re-orient if you find yourself:

- Designing a JSON schema without checking `contracts/` for existing ones
- Writing capture code without checking `tap_tone_pi/capture/`
- Writing FFT code without checking `tap_tone_pi/chladni/peaks_from_wav.py`
- Writing visualization without checking `scripts/phase2/viz.py` and `analyzer/widgets/`
- Proposing a "new module for X" when X already exists
- Saying "I'll build the scanning workflow" (it exists)
- Saying "we need a way to track positions" (we have `phase2_grid.schema.json`)
- Proposing structures without referencing the existing `PointSpectrum`, `Grid`, `SessionState` classes

---

*Use these prompts. They are cheap to run and prevent expensive drift.*
