# Three-Week Dev Order Plan

**Window:** 3 weeks of focused development time (assumed ~10-15 hours/week available, total ~30-45 hours)
**Goal:** Close the real software gaps identified in `01_GAP_INVENTORY.md` so the toolchain is ready when the TTP Analyzer hardware comes online (3-month timeline)
**Scope:** Software only. Hardware builds run on a parallel track.

## Sequencing principle

Build the work in dependency order, smallest valuable increment first. Each dev order produces a working, mergeable artifact that doesn't depend on subsequent orders to be useful.

| Week | Dev Order | Title | Output |
|---|---|---|---|
| 1 | DO-001 | Predicted mode shape rendering on Phase 2 grid coordinates | `mode_shape_render.py` + tests |
| 1 | DO-002 | Predicted-vs-measured comparison module | `comparison.py` + tests |
| 2 | DO-003 | Per-flitch wood database schema + CRUD | `wood_db.py` + schema + tests |
| 2 | DO-004 | Per-build instrument record schema | `build_record.py` + schema + tests |
| 3 | DO-005 | Analyzer GUI: Phase 2 results widget | `phase2_results_widget.py` + integration |
| 3 | DO-006 | Analyzer GUI: predicted-vs-measured overlay widget | `comparison_widget.py` + integration |

Each order has a clear acceptance test. If a week runs over, push the latest order to next week rather than truncating an in-progress order.

---

## DO-001 — Predicted mode shape rendering on Phase 2 grid

**Week:** 1, Days 1-3
**Effort estimate:** 6-8 hours
**Dependencies:** None
**Blocks:** DO-002

### Context

The Rayleigh-Ritz solver in `tap_tone_pi/design/rayleigh_ritz.py` produces mode shapes as mathematical basis function combinations: `w(x,y) = Σᵢ Σⱼ Cᵢⱼ × φᵢ(x) × ψⱼ(y)`. These are defined on a normalized plate domain.

The Phase 2 measurement workflow produces measured amplitudes at physical grid coordinates (mm) defined in `phase2_grid.schema.json`. Grids look like `[{id: "A1", x: -40, y: 60}, ...]`.

There is no existing code that takes a Rayleigh-Ritz solver output and renders the predicted mode shape at the same physical coordinates as a Phase 2 grid. This is the prerequisite for any prediction-vs-measurement comparison.

### Deliverable

A new module `tap_tone_pi/design/mode_shape_render.py` exposing:

```python
def render_mode_shape_on_grid(
    mode: RayleighRitzMode,
    grid: Grid,
    plate_dimensions_mm: tuple[float, float],
    grid_origin: str = "lower_bout_center",
) -> dict[str, float]:
    """
    Evaluate a Rayleigh-Ritz mode shape at each grid point's physical coordinates.

    Returns dict mapping point_id (e.g. "A1") to predicted normalized amplitude.

    Coordinate transform handles:
    - Mapping grid origin convention to solver's normalized plate domain
    - Sign conventions for x (treble positive) and y (tail positive)
    - Out-of-plate grid points (return None or warn)
    """
```

### Acceptance criteria

- [ ] Function signature matches spec
- [ ] Loads `phase2_grid_mm.json` example without modification
- [ ] Loads a Rayleigh-Ritz `RayleighRitzMode` (or whatever the solver actually returns) without modification
- [ ] Returns dict of point_id → amplitude for all in-plate points
- [ ] Returns None or warning for out-of-plate points
- [ ] Test file `test_mode_shape_render.py` with at least:
  - Synthetic plate with known (1,1) mode → check amplitudes are larger near center than edges
  - Synthetic plate with known (2,1) mode → check amplitudes flip sign across midline
  - Grid with one out-of-plate point → check it's flagged
- [ ] No new dependencies beyond existing repo

### Anti-drift checks before starting

Run Prompt 2 from `02_ORIENTATION_PROMPTS.md`. Confirm:
- Rayleigh-Ritz solver exists at `tap_tone_pi/design/rayleigh_ritz.py`
- `Grid` class exists at `scripts/phase2/grid.py`
- `phase2_grid_mm.json` exists at `examples/`

If any of those have moved, update this DO before writing code.

---

## DO-002 — Predicted-vs-measured comparison module

**Week:** 1, Days 4-7
**Effort estimate:** 6-8 hours
**Dependencies:** DO-001
**Blocks:** DO-006

### Context

With DO-001, predicted mode shapes are evaluated at the same coordinates as measured Phase 2 data. The next step is to compute residuals — where does the prediction agree or disagree with measurement?

The Phase 2 metrics module (`scripts/phase2/metrics.py`) already produces `PointSpectrum` objects per grid point. Each contains amplitude (and phase) at the modal frequencies that were measured.

### Deliverable

A new module `tap_tone_pi/design/comparison.py` exposing:

```python
@dataclass
class ComparisonResult:
    grid_id: str
    mode_label: str  # "(1,1)", "(2,1)", etc.
    predicted_freq_hz: float
    measured_freq_hz: float
    freq_residual_hz: float
    freq_residual_pct: float
    per_point_residuals: dict[str, PointResidual]
    overall_rms_amplitude_residual: float
    overall_phase_consistency: float  # 0-1, how well phase patterns match
    nodal_line_match: float | None  # 0-1, how well predicted nodes align with measured nodes

@dataclass
class PointResidual:
    point_id: str
    predicted_amplitude_norm: float  # normalized to peak
    measured_amplitude_norm: float
    residual: float  # measured - predicted, normalized
    is_at_predicted_node: bool  # within 10% of zero
    is_at_measured_node: bool

def compare_mode(
    predicted_shape: dict[str, float],  # from DO-001
    measured_spectra: dict[str, PointSpectrum],  # from Phase 2
    mode_freq_hz: float,
    measured_freq_hz: float,
    mode_label: str,
) -> ComparisonResult:
    """Compute prediction-vs-measurement comparison for one mode."""
```

### Acceptance criteria

- [ ] All dataclasses defined with type hints
- [ ] `compare_mode` function works on synthetic data
- [ ] Tests for `test_comparison.py`:
  - Perfect prediction (predicted == measured) → all residuals zero
  - Predicted (1,1), measured (2,1) → high disagreement detected
  - Predicted with known nodal line, measured matches → high nodal_line_match
  - Predicted with known nodal line, measured doesn't match → low nodal_line_match
- [ ] Imports from existing modules (no duplication of Rayleigh-Ritz or Phase 2 code)
- [ ] Documents the normalization convention used

### Anti-drift checks

Verify `PointSpectrum` schema in `scripts/phase2/metrics.py`. If it has changed, update the comparison module to match.

---

## DO-003 — Per-flitch wood database

**Week:** 2, Days 1-3
**Effort estimate:** 6-8 hours
**Dependencies:** None
**Blocks:** DO-004

### Context

The bending rig (when built) and the existing `tap_tone_pi/bending/` modules will produce per-plate wood property measurements (E_L, E_C, ρ, h grid). These measurements need to accumulate into a per-flitch database that supports queries like "what's the mean E_L for Sitka from supplier X?" or "is this new plate within 1 sigma of the population mean?"

Currently no such database exists. Each measurement is logged in its own session output but not aggregated.

### Deliverable

Two artifacts:

**1. Schema file:** `contracts/wood_flitch_record.schema.json`

```json
{
  "schema_version": "wood_flitch_record_v1",
  "flitch_id": "string (e.g. SITKA_2026_VENDOR_BATCH_03)",
  "species": "enum: sitka, adirondack, engelmann, mahogany_honduran, ...",
  "supplier": "string",
  "purchase_date": "ISO date",
  "purchase_lot": "string",
  "estimated_age_years": "number | null",
  "moisture_content_pct_at_purchase": "number | null",
  "notes": "string",
  "measurements": [
    {
      "measurement_id": "string",
      "measured_at_utc": "ISO datetime",
      "plate_subid": "string (which piece of the flitch)",
      "rh_at_measurement_pct": "number",
      "tempC_at_measurement": "number",
      "thickness_mm_grid": "array of arrays (h(x,y))",
      "mass_g": "number",
      "density_kg_m3": "number",
      "E_L_GPa": "number",
      "E_C_GPa": "number",
      "E_L_uncertainty_GPa": "number",
      "E_C_uncertainty_GPa": "number",
      "modal_freqs_hz": "object: {(1,1): hz, (2,1): hz, ...} | null",
      "Q_factors": "object: {(1,1): Q, ...} | null",
      "measurement_session_path": "string"
    }
  ]
}
```

**2. Python module:** `tap_tone_pi/materials/wood_db.py`

```python
class WoodDatabase:
    """JSON-backed flitch record store with query support."""
    
    def __init__(self, db_path: Path): ...
    def add_flitch(self, record: FlitchRecord) -> None: ...
    def add_measurement(self, flitch_id: str, m: PlateMeasurement) -> None: ...
    def get_flitch(self, flitch_id: str) -> FlitchRecord: ...
    def list_flitches(self, species: str | None = None) -> list[FlitchRecord]: ...
    def stats_for_species(self, species: str) -> SpeciesStats: ...
    def stats_for_supplier(self, supplier: str, species: str) -> SpeciesStats: ...

@dataclass
class SpeciesStats:
    n_flitches: int
    n_measurements: int
    E_L_mean_GPa: float
    E_L_std_GPa: float
    E_C_mean_GPa: float
    E_C_std_GPa: float
    density_mean_kg_m3: float
    density_std_kg_m3: float
```

### Acceptance criteria

- [ ] Schema validates against `phase2_grid.schema.json` style (draft 2020-12)
- [ ] `WoodDatabase` class supports add, get, list, stats
- [ ] Tests for `test_wood_db.py`:
  - Round-trip: add flitch + measurements, save, load, query → matches
  - Stats: 3 measurements, hand-computed mean/std → matches
  - Schema validation: bad input rejected
- [ ] Stores at a location chosen by the user (`~/.tap_tone_pi/wood_db.json` default, configurable)
- [ ] No external dependencies beyond `jsonschema` (which the repo likely already has)

### Anti-drift checks

Run Prompt 4. Confirm `analyzer/analysis/wood_properties.py` doesn't already implement persistence (it doesn't, but verify).

---

## DO-004 — Per-build instrument record schema

**Week:** 2, Days 4-7
**Effort estimate:** 5-7 hours
**Dependencies:** DO-003
**Blocks:** None (but enables future build-tracking work)

### Context

When a guitar is built, many measurements happen across the build process: wood characterization (linked to flitches via DO-003), brace dimensions as-built, modal frequencies at various build stages, deflection measurements, setup specs, subjective tone notes. Currently no single record ties all of these together for one instrument.

The result is that build N's data is scattered across many files with no canonical "this is build N's record." That makes build-to-build comparison hard.

### Deliverable

Two artifacts:

**1. Schema file:** `contracts/instrument_build_record.schema.json`

Top-level structure (abbreviated):

```json
{
  "schema_version": "instrument_build_record_v1",
  "build_id": "string (e.g. SPIRAL_JUMBO_001)",
  "build_started": "ISO date",
  "build_completed": "ISO date | null",
  "design_name": "string (Carlos Jumbo / Standard Dreadnought / ...)",
  "design_blueprint_path": "string (link to plan)",
  "wood": {
    "top_flitch_id": "string (links to wood_db)",
    "top_subid": "string",
    "back_flitch_id": "string",
    "back_subid": "string",
    "sides_flitch_id": "string",
    "sides_subid": "string",
    "neck_flitch_id": "string",
    "brace_stock_flitch_id": "string"
  },
  "as_built_dimensions": {
    "top_thickness_grid_mm": "array of arrays",
    "back_thickness_grid_mm": "array of arrays",
    "brace_dimensions": [
      {"name": "X-leg-bass", "height_mm": 8.0, "width_mm": 6.0, "length_mm": 240.0, ...}
    ],
    "soundhole_geometry": "object (refers to soundhole spec)",
    "tornavoz_spec": "object | null"
  },
  "measurements": {
    "modal_scans": ["paths to Phase 2 ods_snapshot.json files"],
    "deflection_measurements": ["paths"],
    "tap_tone_measurements": ["paths"],
    "setup_measurements": ["paths"]
  },
  "predicted": {
    "T1_hz": "number",
    "A0_hz": "number",
    "bridge_deflection_mm_at_string_load": "number"
  },
  "measured_summary": {
    "T1_hz": "number | null",
    "A0_hz": "number | null",
    "bridge_deflection_mm": "number | null"
  },
  "residuals": {
    "T1_residual_pct": "number | null",
    "A0_residual_pct": "number | null"
  },
  "subjective": {
    "builder_notes": "string",
    "player_evaluations": [
      {"player_id": "string", "date": "ISO", "notes": "string", "engagement_minutes": "number | null"}
    ]
  }
}
```

**2. Python module:** `tap_tone_pi/materials/build_record.py` with a `BuildRecord` class supporting CRUD operations.

### Acceptance criteria

- [ ] Schema validates with `jsonschema`
- [ ] `BuildRecord` class supports load/save round-trip
- [ ] References to other artifacts (Phase 2 sessions, deflection measurements) are paths, not duplicated data
- [ ] Tests for `test_build_record.py`:
  - Round-trip serialization
  - Predict-vs-measured residual computation
  - Cross-reference to wood_db: build with flitch_id loads correct flitch data
- [ ] Documentation explains build-to-build comparison workflow

### Anti-drift checks

Confirm no existing `BuildRecord` or `Instrument` schema. There isn't one, but verify.

---

## DO-005 — Analyzer GUI: Phase 2 results widget

**Week:** 3, Days 1-4
**Effort estimate:** 8-10 hours
**Dependencies:** None (Phase 2 outputs already exist)
**Blocks:** DO-006

### Context

The desktop analyzer (`analyzer/main_window.py`) currently has widgets for spectrum, peaks, plate tuning, and Bode plots. There is no widget that loads a Phase 2 scanning session and visualizes the modal scan results.

Phase 2 produces:
- `ods_snapshot.json` — the modal scan data
- `wsi_curve.json` — WSI curve over frequency
- Heatmap PNGs from `viz.heatmap_scatter()`

The analyzer should be able to load a Phase 2 session directory and display these interactively, similar to how it displays viewer pack v1 data.

### Deliverable

A new widget `analyzer/widgets/phase2_results_widget.py`:

```python
class Phase2ResultsWidget(QWidget):
    """Display Phase 2 ODS scanning results.
    
    Shows:
    - WSI curve (frequency on X, weighted shape index on Y)
    - 2D heatmap of point amplitudes at selected frequency
    - Peaks list (clickable to update heatmap frequency)
    - Grid metadata (origin, units, point count)
    """
```

Plus integration in `analyzer/main_window.py`:
- New menu item "File > Open Phase 2 Session..."
- Loads session directory, validates structure, populates widget
- Adds widget as a new tab or dock

A new loader `analyzer/loaders/phase2_session.py` that reads the session directory structure and produces a `Phase2SessionData` dataclass.

### Acceptance criteria

- [ ] Widget renders WSI curve from Phase 2 output
- [ ] Widget renders 2D heatmap (matplotlib scatter or pcolormesh) at user-selected frequency
- [ ] Clicking a peak in the peaks list updates the heatmap frequency
- [ ] Widget displays grid metadata
- [ ] Loader handles malformed sessions gracefully (clear error message, no crash)
- [ ] Synthetic test session (from `phase2_slice.py --synthetic`) loads and renders correctly
- [ ] Widget follows the visual style of existing widgets (`spectrum_chart.py` is the pattern)

### Anti-drift checks

Run Prompt 3. Confirm:
- PyQt6 + matplotlib via `FigureCanvasQTAgg` is the established pattern
- Existing widgets in `analyzer/widgets/` show the structure to follow
- Phase 2 outputs the file types expected (run `python scripts/phase2_slice.py run --synthetic` and inspect output dir)

---

## DO-006 — Analyzer GUI: predicted-vs-measured overlay widget

**Week:** 3, Days 5-7
**Effort estimate:** 6-8 hours
**Dependencies:** DO-001, DO-002, DO-005
**Blocks:** None

### Context

DO-001 renders predicted mode shapes on Phase 2 grids. DO-002 computes comparisons. DO-005 displays measured Phase 2 data in the analyzer. This dev order ties them together by adding a comparison overlay to the Phase 2 results widget.

### Deliverable

Extension to `analyzer/widgets/phase2_results_widget.py` adding a "Compare with Prediction" mode:

```python
class Phase2ResultsWidget(QWidget):
    # ... (existing from DO-005)
    
    def load_prediction(self, prediction_path: Path) -> None:
        """Load a Rayleigh-Ritz prediction file and overlay on heatmap."""
    
    def show_comparison_mode(self, mode_label: str) -> None:
        """Display side-by-side predicted vs measured for selected mode."""
```

The overlay UI provides:
- Three-panel view: Predicted | Measured | Residual
- Mode selection dropdown (populated from prediction file)
- Numeric comparison table showing per-mode frequency residuals
- Overall agreement metrics from `ComparisonResult` (DO-002)

### Acceptance criteria

- [ ] Widget can load a Rayleigh-Ritz prediction (file format from DO-001/DO-002 outputs)
- [ ] Three-panel comparison view renders correctly
- [ ] Mode dropdown switches between modes
- [ ] Residual panel shows quantitative agreement
- [ ] Synthetic test: perfect prediction → residual panel shows near-zero
- [ ] Synthetic test: predicted (1,1), measured (2,1) → residual panel shows large disagreement, mode selection helps diagnose
- [ ] Documentation explains the typical workflow: scan body, run solver, load prediction, compare

### Anti-drift checks

Confirm DO-001 and DO-002 deliverables are merged and available before starting this order.

---

## What gets deferred (NOT in three-week plan)

The following were on the table but are explicitly out of scope for this window:

- **Body geometry overlay (§6.4):** Requires importing CAD/blueprint files. Defer until first body is being built and there's a real outline to overlay.
- **Build journal integration (§6.5):** Workflow design first, code later.
- **Plate experiment campaign manager (§5.10):** Wait until at least one plate measurement run has happened manually. Tooling that automates a workflow nobody has run is premature.
- **Tornavoz prototype tracking (§6.3):** Wait until tornavoz experiments are imminent.
- **Build-to-build comparison tooling (§6.2):** Build the database first (DO-003, DO-004), then build comparison views once there's data to compare.

These deferred items become candidates for the next 3-week window, prioritized based on what the first three weeks reveal.

---

## Daily standup template

Each day during the dev window, take 5 minutes to write:

```
Date: YYYY-MM-DD
Active DO: DO-XXX
Yesterday: [what got done]
Today: [what will get done]
Blockers: [anything stopping progress]
Anti-drift check: [confirm I'm building what's missing, not what exists]
```

Save as `dev_log/YYYY-MM-DD.md`. This is the audit trail that prevents drift across sessions.

---

## Three-week retrospective questions

At the end of the window, answer:

1. Did each DO produce the deliverable on its acceptance criteria?
2. Did anything I built duplicate code that already existed (drift detection)?
3. Did any DO take significantly more or less time than estimated?
4. What did the work reveal about the next three-week window's priorities?
5. Did the gap inventory need updating? (Update it.)

---

*End of plan. Six dev orders, three weeks, real software gaps closed.*
