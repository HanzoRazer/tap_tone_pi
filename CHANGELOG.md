# Changelog

All notable changes to this project are documented here. This file follows [Keep a Changelog](https://keepachangelog.com/) style and [Semantic Versioning](https://semver.org/).

## [2.3.0-alpha.7] — 2026-06-21

### Added
- **DO-89D: Cohort Execution Plan Export**
  - `CohortExecutionPlanV1` — 9-section execution protocol
  - Sections: preamble, specimen prep, measurement, data capture, reference body,
    baseline checks, covariate tracking, session housekeeping, provenance
  - Markdown renderer for human-readable execution protocol
  - 33 tests

- **DO-90: Controlled Excitation Contracts**
  - `ExcitationContractV1` — declarative excitation specification (tone/stepped/sweep)
  - `KnownToneRecordV1` — provenance for single emitted tone event
  - `SourceCharacterizationRecordV1` — output-side calibration record
  - `AmplitudeGuardrail` — amplitude validation (default=0.2, warning>0.5, reject>1.0)
  - `emit_tone()` CLI command and programmatic API
  - 36 tests

- **DO-91: Excitation Provenance + TF Workflow**
  - `ExcitationMeasurementLinkV1` — links excitation to measurement
  - `ExcitationResponsePairV1` — bundles excitation+response for TF computation
  - `TransferFunctionResultV1` — provenance-aware TF result
  - `CoherenceSummaryV1`, `UncertaintySummaryV1` — serializable summaries
  - 28 tests

- **DO-92: A0 Main Body Air Resonance Workflow**
  - `A0PeakCandidateV1` — candidate peak in A0 range (70-130 Hz)
  - `A0MeasurementEvidenceV1` — all candidates with selection method
  - `A0MeasurementRecordV1` — provenance-aware A0 measurement record
  - `MainBodyAirResonanceWorkflowV1` — workflow configuration
  - Peak detection wraps existing damping/modes.py
  - Selection method recorded, not hidden
  - 38 tests

- **DO-93: Stepped & Sweep Excitation Records**
  - `SteppedExcitationRecordV1` — sequential frequency steps with dwell/transition
  - `SweepExcitationRecordV1` — linear or logarithmic sweep with waveform hash
  - `SweepType` enum (LINEAR | LOGARITHMIC)
  - `emit_stepped()`, `emit_sweep()` — thin wrappers producing provenance records
  - `generate_stepped_signal()` — composes from generate_sine
  - ExcitationMeasurementLinkV1 integration complete
  - 25 tests

### Architecture
Complete excitation provenance chain:
```
ExcitationContractV1
    ├── KnownToneRecordV1     (emit_tone)
    ├── SteppedExcitationRecordV1  (emit_stepped)
    └── SweepExcitationRecordV1    (emit_sweep)
         ↓
ExcitationMeasurementLinkV1 → ExcitationResponsePairV1 → TransferFunctionResultV1
```

A0 workflow validates the stack end-to-end. All contracts use frozen dataclass
pattern with `to_dict()` and appropriate `epistemic_status`. No advisory semantics.

---

## [2.3.0-alpha.6] — 2026-06-20

### Added
- **Measurement Legitimacy Stack (DO-89A/B/C)** — experimental knowledge infrastructure
  - **DO-89A: Experiment Design Contract**
    - `ExperimentDesignV1` — governing object for cohort studies
    - `DeclaredResponseVariableV1` — what outcomes are being measured
    - `MinimumInterestingEffectV1` — effect size thresholds
    - `CovariateDefinitionV1` — tracked variables (fixed/random)
    - `RandomizationPlanV1` — randomization strategy
    - `BaselineRebuildPlanV1` — baseline rebuild triggers
    - `DesignValidationEvidenceV1` — completeness validation
    - 37 tests
  - **DO-89B: Process Variance Evidence**
    - `ReferenceBodyRecordV1` — metrology standard for σ_measurement isolation
    - `VarianceDecompositionV1` — σ²_total = σ²_measurement + σ²_build
    - `ProcessVarianceEvidenceV1` — variance decomposition with raw values
    - `FeasibilitySummaryV1` — cohort-level variance with neutral bands
    - `VarianceBandThresholdsV1` — low/medium/high classification
    - 35 tests
  - **DO-89C: Cohort Regression Evidence**
    - `CohortRegressionEvidenceV1` — OLS coefficients, R², residuals
    - `FormulaCandidateEvidenceV1` — descriptive formula with limitations
    - `RegressionCoefficientV1` — coefficient with standard error
    - Auto-limitations: "linear model only", "N=X samples"
    - 31 tests (23 + 8 export anchor)
- **Handoffs directory** — `docs/handoffs/` for implementation handoff documents
  - `TTP_ACOUSTIC_EXCITATION_HANDOFF_2026-06-18.md` — DO-90→95 excitation framework
  - `no_soundhole_lab_protocol.md` — closed-body calibration specimens

### Architecture
The stack supports the full experimental knowledge flow:
```
Declare experiment → run cohort → separate σ_measurement from σ_build
→ control covariates → derive formula-candidate evidence
```

All contracts follow frozen dataclass pattern with `to_dict()` and
`epistemic_status="derived"`. No advisory semantics.

---

## [2.2.5] — 2026-02-09

### Added
- **Directive outcome events (PR #10):** `emit_attention_acknowledged()` and `emit_attention_dismissed()` convenience emitters in `events.py`.
- **MOM-004 CONFIDENCE_CLIMB:** Detects ≥80% acknowledge rate over ≥5 directive outcomes — signals growing user trust.
- **MOM-005 TRUST_EROSION:** Detects ≥60% dismiss rate (Path A) or 3+ idle-timeout events (Path B) — signals declining trust.
- Policy mapping: CONFIDENCE_CLIMB → INSPECT, TRUST_EROSION → REVIEW.
- 8 moment-detection tests covering both moments, threshold boundaries, and priority suppression.

---

## [2.2.4] — 2026-02-09

### Changed
- **Frozen contracts (PR #9):** `AttentionDirectiveV1` is now `@dataclass(frozen=True)`. Policy guidance-density gate uses `dataclasses.replace()` instead of in-place mutation. Regression test asserts immutability.

---

## [2.2.3] — 2026-02-09

### Changed
- **Directive schema:** Removed legacy `title` field from `policy._build_directive()`; use `summary` as the sole canonical field.
- **Directive dataclass migration (PR #8):** `_build_directive()` returns `AttentionDirectiveV1` dataclass; `_coerce_directive()` seam guard ensures `decide()` never returns a plain dict directive. Tests assert contract type + `to_dict()` shape; wrapper dict keys unchanged.

---

## [2.2.2] — 2026-02-08

### Added
- **GUI Export Viewer Pack (Phase 11)** — one-click export of GUI sessions to viewer_pack_v1 format
  - "Export Pack" toolbar button (green, Ctrl+E shortcut)
  - "Export Viewer Pack..." menu item under Tools
  - `tap_tone_pi/gui/export.py` — new export module
    - `export_gui_session()` — converts session dir to viewer pack ZIP
    - `_find_best_attempt()` — selects best attempt per point (PASS > WARN > FAIL)
    - `_generate_spectrum_csv()` — creates spectrum CSV from audio FFT
    - `ExportResult` dataclass for structured return
  - Pre-export validation (measurements must exist)
  - Confirmation dialog with point count
  - Progress feedback via status bar
  - Success message with warnings (if any)
  - Offer to open output folder after export
  - 11 unit tests in `tests/test_gui_export.py`

[2.2.2]: https://github.com/HanzoRazer/tap_tone_pi/compare/analyzer-v2.2.1...analyzer-v2.2.2

---

## [2.2.1] — 2026-02-08

### Added
- **GUI Auto-Trigger Integration (Phase 10)** — hands-free tap detection in the GUI
  - "Auto-trigger (wait for tap)" checkbox in Quality-Gated Measurement section
  - Listening state visual indicator ("🎤 Listening for tap...")
  - SNR feedback when tap is detected
  - 30-second timeout with user-friendly message
  - Graceful fallback when sounddevice not available (checkbox disabled)
  - Works in both single-point and grid measurement modes
  - `_on_auto_trigger_toggle()` — checkbox state handler
  - `_update_trigger_listening_state()` — visual feedback updates

### Changed
- GUI version updated to v2.2.0
- `do_quality_measure()` now branches on auto-trigger checkbox state
- `_do_grid_point_measure()` also supports auto-trigger mode

[2.2.1]: https://github.com/HanzoRazer/tap_tone_pi/compare/analyzer-v2.2.0...analyzer-v2.2.1

---

## [2.1.0] — 2026-02-07

### Added
- **Agentic Layer** — `tap_tone_pi.agent` package for deterministic, policy-constrained orchestration
  - `MeasurementAgent` — stateful conductor for measurement workflows
  - `build_agent_message()` — convenience function for structured responses
  - Rule → explanation → suggestion tables (Q001–Q005 HARD, Q010–Q013 SOFT)
  - Verdict templates (PASS/WARN/FAIL) with default actions
  - FTUE (First-Time User Experience) with progressive disclosure
    - `UserStage`: first_run → novice → regular → expert
    - Stage-appropriate hints, detail limits, action suggestions
  - CLI and GUI renderers (`render_cli`, `render_gui`, `render_compact`)
  - History tracking: rule counts, consecutive hits, escalation logic
- **Integrated Agent Messages** — `tap_tone_pi.agent.messages` module
  - Uses real `quality_policy` types (`QualityVerdict`, `TriggeredRule`, `Severity`)
  - Frozen dataclasses for immutability (`AgentContext`, `AgentMessage`, `SuggestedAction`)
  - `format_verdict_summary_agent()` — drop-in replacement for `format_verdict_summary()`
  - **Unknown rule fallback** — gracefully handles future rule IDs not in RULE_SPECS
  - **No imports from `quality_gate`** — policy-safe, no circular dependency pressure
- **Dual API** — standalone (mock-friendly) + integrated (production) exports
- **GUI Polish (Phase 8)** — `tap_tone_pi.gui.widgets` module
  - `AudioLevelMeter` — real-time level visualization with peak hold
  - `StatusBar` — color-coded operation feedback (info/success/warning/error/progress)
  - `DeviceSelector` — audio device dropdown with test button
  - `SetupWizardDialog` — in-GUI hardware configuration
  - `CaptureProgressDialog` — visual feedback during capture operations
- **Session Browser** — `SessionBrowserDialog` for viewing past measurements
  - Session type detection (quality_gated, chladni, bending, moe, tap_tone)
  - Metadata display (date, points, files, size, verdict status)
  - Actions: open folder, select session
- **Pack Diff Tooling** — `tap_tone_pi.core.session_diff` module
  - `PeakDiff`, `MetricDiff`, `SessionDiff` dataclasses
  - `compare_sessions()` — compare before/after measurements
  - `format_diff_report()` — human-readable diff report
  - `PackDiffDialog` — UI for comparing sessions with Summary/Peaks/Metrics tabs
- **Session Metadata Export** — `meta/session_meta.json` in viewer packs (Release A.1)
  - `SessionMetaV1` dataclass with capture setup metadata
  - Auto-extracts: specimen_id, device_id, fixture_id, mic_id, mic_gain_db, sample_rate_hz, tap_count
  - Enables ToolBox compare UI to show capture configuration differences
- **CLI Agent Mode** — `--agent` and `--expert` flags for record/measure commands
  - `ttp record --agent` — agent-formatted QC output with hints
  - `ttp measure --agent` — agent-formatted workflow output
  - `--expert` — more detailed output for advanced users
- **Multi-point Grid (Phase 9)** — `tap_tone_pi.core.grid` module
  - `Grid` — measurement grid with factory methods (`rectangular`, `circular`, `line`)
  - `GridPoint` — individual point with ID, coordinates, optional label
  - `GridSession` — session state tracking with point progress
  - `PointStatus` — PENDING/PASSED/WARNED/FAILED/SKIPPED states
  - Grid-based measurement workflow in GUI (`do_grid_measure()`)
  - JSON serialization for grid definitions and session state
- **Auto-Trigger Detector (Phase 10)** — `tap_tone_pi.core.auto_trigger` module
  - `AutoTriggerDetector` — monitors audio stream for tap onset
  - Adaptive threshold (baseline × multiplier) or fixed RMS threshold
  - Pre-trigger buffer (100ms default) captures initial transient
  - Configurable timeout, chunk size, settling time
  - `TriggerConfig` — all detection parameters
  - `TriggerResult` — captured audio with timing/RMS metadata
  - `record_audio_triggered()` — convenience function
  - CLI flags: `--auto-trigger`, `--trigger-timeout`
  - Usage: `ttp measure --out ./session --auto-trigger`
- **UI Polish** — keyboard shortcuts and tooltips
  - Keyboard shortcuts: Ctrl+B (browse), Ctrl+O (open folder), Ctrl+Q (quit), Ctrl+W (wizard), Ctrl+D (diff), Ctrl+G (grid), F1 (about)
  - Menu accelerator labels
  - Toolbar button tooltips
- **FTUE Persistence** — session and pass counts tracked across invocations
  - `session_count_lifetime` increments per `cmd_measure` call
  - `pass_count_lifetime` increments on PASS verdict
  - `seen_rule_ids` tracks encountered quality rules
- 192 tests for agent layer + 14 tests for session metadata + 15 tests for session diff + 7 tests for auto-trigger

### Architecture
The agent wraps existing components horizontally, not vertically:
```
Capture → Analysis → Quality Gate → Artifacts
                         ↑
                  ┌──────┴──────┐
                  │ Agent Layer │
                  └─────────────┘
```

The agent:
- Observes system state (verdicts, attempts, context)
- Sequences actions (retry, accept, abort, override)
- Explains outcomes (rule → operator-facing message)
- Enforces policy (governance lives here, not in UI)

The agent NEVER:
- Modifies DSP results
- Invents interpretations
- Auto-adjusts parameters
- Makes silent decisions

### Hardening
- **Stable imports / no cycles** — agent imports only from `quality_policy`, not `quality_gate`
- **Guaranteed behavior on unknown rule IDs** — falls back to `TriggeredRule.message` and `rule.severity`
- **Strict determinism** — HARD rules sorted before SOFT, then lexical by rule_id; actions de-duped by `action_id`
- **No UI assumptions** — structured `AgentMessage` output with separate CLI renderer

[2.1.0]: https://github.com/HanzoRazer/tap_tone_pi/compare/analyzer-v2.0.0...analyzer-v2.1.0

---

## [2.0.0] — 2026-02-05

### Breaking Changes
- **Package restructure** — consolidated package namespace from `tap_tone` to `tap_tone_pi`
- Import paths changed: `from tap_tone.analysis import analyze_tap` → `from tap_tone_pi.core.analysis import analyze_tap`
- Deprecation stubs provided for backward compatibility (one release cycle)
- CLI entry point renamed: `ttp` is now primary (replaces `tap-tone`)
- `ttp record` now emits quality evidence (`quality_check.json`) but does not enforce gating; enforcement moved to `ttp measure`

### Fixed
- **Bug 2: WAV write argument transposition** — `storage.py:57` had `write_wav_mono(path, sample_rate, audio)` instead of `write_wav_mono(path, audio, sample_rate)`. All Phase 1 captures now produce valid WAV files.

### Added
- **Quality Gate system** — `tap_tone_pi.core.quality_gate` and `tap_tone_pi.core.quality_policy`
  - HARD rules (Q001-Q005): clipping, silent, no peaks, low confidence, invalid sample rate → FAIL
  - SOFT rules (Q010-Q013): quiet, near-clipping, marginal confidence, few peaks → WARN
  - `quality_check.json` emitted for every capture (evidence layer)
- **Operator Loop** — `tap_tone_pi.workflow.operator_loop`
  - State machine: IDLE → PREFLIGHT → READY → CAPTURING → ANALYZING → GATING → PASS/WARN/FAIL
  - Retry support with attempt numbering (attempt_001, attempt_002, etc.)
  - Override support for FAILED attempts with required reason
- **Attempt tracking** — `tap_tone_pi.workflow.attempt`
  - `Attempt` dataclass with full lifecycle tracking
  - `AttemptStore` for session persistence
- Regression test for storage.py WAV write path (`test_storage_wav_roundtrip.py`)
- 89 tests for quality gate + workflow + CLI integration
- Schema location documented: `contracts/schemas/` is canonical (per `schema_registry.json`)

### CLI
- `ttp record` — record single tap (QC recorded, not gated)
- `ttp measure` — quality-gated measurement (blocks on FAIL)
- `ttp export-pack` — export viewer pack ZIP with validation

### Changed
- Removed 64 stale measurement files from git tracking (`out/` directory)
- GUI rewritten to use direct imports instead of subprocess calls
- GUI binding bug fixed (form values now captured at callback time, not construction)
- **Matplotlib spectrum viewer** — inline visualization with peak annotations (Phase 6)
- Deleted `tap-tone-lab/` directory (49 files, content migrated to `tap_tone_pi/`)

### Governance
- **Evidence always produced** — `quality_check.json` written even when not gating
- **Gating is a workflow decision** — `record` = evidence only; `measure` = blocking gate
- **Artifact contract** — guaranteed per capture: `audio.wav`, `analysis.json`, `quality_check.json`

### Migration Tip
If you maintain downstream scripts:
- Replace `tap_tone.*` imports with `tap_tone_pi.*`
- Prefer `ttp` over `tap-tone` in automation
- Expect `quality_check.json` to appear alongside captures

[2.0.0]: https://github.com/HanzoRazer/tap_tone_pi/compare/analyzer-v1.2.0...analyzer-v2.0.0

---

## [1.2.0] — 2026-01-21

### Added
- **Auto-Trigger Capture** — hands-free impulse detection for `tap_tone gold-run`:
  - `--auto-trigger` flag enables automatic tap detection
  - EMA noise floor estimation during warmup
  - Trigger conditions: peak > noise×10, RMS > noise×3 (configurable)
  - Debounce to avoid glitches (consecutive frames required)
  - Pre-roll (50ms default) + post-roll (1500ms default) capture windowing
  - Clipping detection with reject/accept option
  - Full provenance tracking: `noise_rms`, `trigger_peak`, `snr_est_db`, etc.
- New module: `tap_tone/capture/auto_trigger.py`
  - `AutoTriggerConfig` — all detection parameters
  - `AutoTriggerDetector` — stateful detector with state machine
  - `RingBuffer` — pre-roll audio buffering
  - `capture_one_impulse_stream()` — hardware-agnostic capture
  - `capture_one_impulse_sounddevice()` — sounddevice integration
- 22 unit tests for auto-trigger (synthetic waveforms, no hardware)

### CLI Options (auto-trigger group)
```
--auto-trigger          Enable auto-trigger mode
--warmup-s 0.5          Noise floor estimation period
--peak-mult 10          Peak threshold multiplier
--rms-mult 3            RMS threshold multiplier
--debounce-frames 2     Consecutive trigger frames
--pre-ms 50             Pre-roll before trigger
--post-ms 1500          Post-roll after trigger
--reject-clipping       Reject clipped captures (default)
--no-reject-clipping    Accept with warning
--min-impulse-ms 2      Ignore ultra-short glitches
```

[1.2.0]: https://github.com/HanzoRazer/tap_tone_pi/compare/analyzer-v1.1.0...analyzer-v1.2.0

---

## [1.1.0] — 2026-01-21

### Added
- **`tap_tone gold-run`** CLI command — one-command Gold Standard Run:
  - Capture N points → export viewer pack → validate → optional ingest
  - `--dry-run` mode for preview without hardware
  - `--json` output for machine-readable results
  - Exit codes: 0=success, 2=validation failed, 3=capture failed, 4=device error, 5=unexpected
  - Makefile targets: `gold-run`, `gold-run-dry`
- **`tap_tone/__main__.py`** — enables `python -m tap_tone` invocation
- Developer experience documentation:
  - [INSTRUMENT_SCOPE.md](docs/INSTRUMENT_SCOPE.md)
  - [QUICKSTART.md](docs/QUICKSTART.md)
  - [FIRST_MEASUREMENT_CHECKLIST.md](docs/FIRST_MEASUREMENT_CHECKLIST.md)
  - [GOLD_STANDARD_EXAMPLE_RUN.md](docs/GOLD_STANDARD_EXAMPLE_RUN.md)
  - [GOLD_RUN_COMMAND_SPEC.md](docs/GOLD_RUN_COMMAND_SPEC.md)
- Reference comparison dataset (`examples/reference/run_a_dry`, `examples/reference/run_b_humid`)

### Changed
- Pre-commit workflow now runs on all branches and PRs

[1.1.0]: https://github.com/HanzoRazer/tap_tone_pi/compare/analyzer-v1.0.0...analyzer-v1.1.0

---

## [1.0.0] — 2026-01-18

### Added
- Same feature set as 1.0.0-rc1 promoted to stable:
  - **Schema Registry** (`contracts/schema_registry.json`) with contracts:
    `tap_peaks`, `moe_result`, `measurement_manifest`, `chladni_run`,
    and Phase-2: `phase2_ods_snapshot`, `phase2_wolf_candidates`.
  - **Registry-driven validator** (`scripts/validate_schemas.py`).
  - **Hardware-free demos**: Chladni v1, Phase-2 mini run, MOE.
  - **Canonical WAV I/O** (`modes/_shared/wav_io.py`) + CI guard.
  - **Chladni mismatch policy** (warn+keep; fail if `delta_hz` exceeds tolerance).
  - **Run-level manifest append** for Chladni (idempotent).
  - **Local CI dry run** (`make ci-dry-run`).

### CI / Quality Gates
- Pytest + **coverage ≥ 80%** (merge-blocking).
- **WAV I/O guard** (no direct `scipy.io.wavfile` outside `_shared`).
- **Schema-bump guard** (registry version bump required).
- **PR title linter** for schema edits (`schema: …`).
- **Schema validation** for demo artifacts.
- **CODEOWNERS** for `contracts/**` and `modes/_shared/**`.

### Notes
- Analyzer remains **measurement-only** (facts, not advisories). ToolBox handles interpretation.

[1.0.0]: https://github.com/HanzoRazer/tap_tone_pi/releases/tag/analyzer-v1.0.0

---

## [1.0.0-rc1] — 2026-01-18

### Added
- **Schema Registry** at `contracts/schema_registry.json` and **contracts** for:
  - `tap_peaks`, `moe_result`, `measurement_manifest`, `chladni_run`
  - Phase-2: `phase2_ods_snapshot`, `phase2_wolf_candidates`
- **Registry-driven validator**: `scripts/validate_schemas.py` (consumes registry; no hardcoded maps).
- **Hardware-free demos**:
  - **Chladni v1**: `examples/chladni/` (WAV → peaks → image index → `chladni_run.json`) + manifest append.
  - **Phase-2 mini**: `examples/phase2/` with canonical filenames under `runs_phase2/DEMO/session_0001/`.
  - **MOE**: `examples/moe/` producing a valid `moe_result.json`.
- **Canonical WAV I/O**: `modes/_shared/wav_io.py` (float32 in ±1, PCM16 out).
- **Chladni mismatch policy**: warn+keep with `delta_hz`; **fail** if worst `delta_hz` exceeds `CHLADNI_FREQ_TOLERANCE_HZ` (default 5 Hz).
- **Run-level manifest append** for Chladni: `modes/chladni/manifest_utils.py` (idempotent).
- **Local CI dry run**: `make ci-dry-run` (tests → coverage → demos → schema validation).
- **Pre-export validator**: `tap_tone/validate/viewer_pack_v1.py` for staged directory validation.

### Changed
- All readers/writers route through canonical WAV I/O; removed ad-hoc `/32767` scaling.
- Docs: Governance and Measurement README updated with policy, demos, and local CI instructions.

### CI / Quality Gates
- **pytest** + **coverage ≥ 80%** (merge-blocking).
- **WAV I/O guard**: disallow `scipy.io.wavfile` outside `modes/_shared/wav_io.py`.
- **Schema-bump guard**: changes to `contracts/schemas/*.schema.json` must bump versions in the registry.
- **PR title linter** for schema edits (`schema: …` prefix).
- **Schema validation** in CI for `out/**` and Phase-2 demo.
- **CODEOWNERS** for `contracts/**` and `modes/_shared/**`.

### Tests
- Chladni policy unit tests (warn vs fail).
- Manifest test asserts expected entries + SHA-256 hashes and idempotency.
- Pre-export validator tests (15 rules across M/S/P/W/A/O categories).

### Notes
- This release is **Analyzer-only** ("facts, not opinions"). Design/CAM interpretation remains out-of-scope.

[1.0.0-rc1]: https://github.com/HanzoRazer/tap_tone_pi/releases/tag/analyzer-v1.0.0-rc1
