# Active Dev Order

**Current:** _(none — awaiting DO-101A promotion)_
**Previous:** DO-100 — Guided Digital Laboratory Foundation (COMPLETE)

> **DO-100 — Guided Digital Laboratory Foundation (COMPLETE)**
>
> Merged as **PR #16** → `main` merge commit
> `6ca0105ecc3535dfeeb13f565df92b62ccc105ab` (branch
> `feat/do-100-guided-digital-laboratory`, feature commit
> `f398f52b498da4a2d17607e7856a683d18efe7db`). Authoritative handoff remains
> at `docs/dev_orders/DO-100_GUIDED_DIGITAL_LABORATORY.md` (placed via PR #15).
>
> **Delivered:** `tap_tone_pi/guided_lab/` (contracts, error vocabulary, pure
> definition validation, deterministic engine, builder-intent catalog, thin
> CLI); reference workflow `plate_measurement_setup` v1 (19 nodes, 21
> transitions); `contracts/guided_lab_session_v1.schema.json` plus
> `schema_registry.json` entry; `guided-lab` on the unified CLI with isolated
> registration so a guided-laboratory defect cannot stop unrelated `ttp`
> commands.
>
> **Deliberate non-goals (remain for later orders):** session persistence
> layer, GUI, server endpoint, workflow-version migration, and an adapter
> between `tap_tone_pi.guided_lab` and existing `tap_tone_pi.workflow`
> measurement contracts.
>
> DO-100 **COMPLETE**. DO-101 is **not** promoted in this closure — promotion
> belongs to DO-101A's first docs/status commit.

> **DO-99 — Server Authorization Observability & Diagnostics (COMPLETE)**
>
> Depends on **PR #10** + **PR #11** (both merged to `main`). Branches from `main`
> (`fix/server-authz-observability`). **Diagnostics only — no authorization
> decision changes; all DO-98 tests pass unchanged.**
>
> **Scope:** make the filesystem-authorization layer observable without exposing
> host paths — structured events + a status endpoint.
>
> **Delivered:**
> - `tap_tone_pi.server.authz` logger emits one path-free `AuthorizationEvent`
>   per authorization call (frozen dataclass via `extra=`): allowed→DEBUG,
>   OUTSIDE_ROOT/SYMLINK_ESCAPE→WARNING, INVALID_ROOT/PATH_RESOLUTION_FAILURE→ERROR.
> - `OUTSIDE_ROOT` vs `SYMLINK_ESCAPE` distinguished by a diagnostic-only lexical
>   check (decision unchanged); `INVALID_ROOT` emitted at `create_app` before the
>   `ValueError` re-raises; `PATH_RESOLUTION_FAILURE` emitted then original
>   exception re-raised unchanged (no HTTP conversion).
> - `_safe_directory(directory, *, endpoint, input_role)`; fields `endpoint`,
>   `input_role`, `request_path_type` kept separate.
> - `GET /server/status` → `policy_version="filesystem-auth-v2"`, `configured`,
>   `root_digest=sha256(root)[:12]`, `started_at`; no host-path disclosure.
> - No raw request/resolved/root path or exception text ever logged (only an
>   exception class name where relevant).
>
> Commit sequence on branch: `521d39d` (tests), `c21b37b` (implementation),
> `986d6e5` (docs).
> Merged as **PR #13** → `main` merge commit
> `ec9f93a362249cee037766c06e767b38c1a4b1e0` (branch
> `fix/server-authz-observability`). A review follow-up merged as **PR #14**
> (`fix/do99-review-followup`). DO-99 **COMPLETE**.

> **DO-98 — COMPLETE**
>
> Merged as **PR #11** → `main` commit `79c2d36` (branch
> `fix/server-data-root-authorization`, off `d8010dd`).
> Replaced the fixed `Path.cwd()` anchor with a configurable data root and unified
> containment for relative *and* absolute request paths across `/grids`,
> `/sessions`, `/sessions/{id}`, and `/export/{id}` reads. `--data-root` on
> `ttp server` (env-bridged for `uvicorn --reload`, non-contaminating).
> Full CI green on 3.10/3.11 at merge; the deferred `output_dir` write policy and
> Windows path tests are tracked in `SPRINTS.md` (B-001/B-002).
>
> **Scope:** replace the fixed `Path.cwd()` authorization anchor with an explicit
> configurable server data root, and unify containment so **relative and
> absolute** request paths must both resolve beneath it. Closes the absolute-path
> gap PR #10 intentionally left, while preserving external data directories
> (authorized by configuring the root).
>
> **Delivered:**
> - `create_app(*, data_root=None)`; precedence `arg > TTP_SERVER_DATA_ROOT > cwd`;
>   invalid configured root fails at creation; resolved root on `app.state.data_root`.
> - Unified `_safe_directory` (post-resolution `is_relative_to` containment for
>   relative *and* absolute; `..` and symlink escapes rejected).
> - `--data-root` on `ttp server`, bridged to the import-string app via the env
>   var (preserves `uvicorn --reload`), non-contaminating for direct unit tests.
> - The four `/grids`/`/sessions` endpoint tests reconstructed with an explicit
>   `data_root`; new authorization, precedence, symlink, and CLI tests.
> - README "HTTP API server" section documents the policy.
>
> **Verification commands:**
> ```bash
> python -m pytest -q tests/test_server_path_traversal.py tests/test_server_app.py
> python -m ruff check tap_tone_pi/server/app.py tests/test_server_path_traversal.py tests/test_server_app.py
> python -m ruff format --check tap_tone_pi/server/app.py tests/test_server_path_traversal.py tests/test_server_app.py
> ```
> Full `pre-commit run --all-files` + `pytest -q` + the CI 3.10/3.11 matrix gate merge.
>
> Commit sequence on branch: `c8d1cd8` (tests), `1519870` (implementation), docs (this).
> PR/merge reference to be recorded on completion.

> **DO-97 — COMPLETE**
>
> Final corrective commit:
> `c7c22741bfc087a8acaee34254c4ad9b4b985960`
>
> **Verification summary**
> - Focused verification passed (`tests/test_laboratory_manual_registry.py`,
>   `tests/test_laboratory_manual_view.py`, `tests/test_manual_packaging.py`).
> - Wheel packaging verified (real build + isolated `--target` install).
> - Installed-resource verification passed (import origin is the installed wheel,
>   not the checkout; packaged manifest + README load via the public registry API).
> - Boundary validation passed (advisory-boundary + analyzer-isolation checks).
> - Compile validation passed.
> - Ruff checks on touched files passed.
>
> Comparison against base commit
> `7b555ee74a521d8086e4182d16c726ca2015baef`
> confirmed that DO-97G introduced no new CI failures. Repository-wide CI failures
> remain and are tracked separately as baseline conditions (they reproduce on base
> and touch no DO-97 file).
>
> **Final adjudication:** COMPLETE WITH DOCUMENTED BASELINE FAILURES.
>
> The corrective work is a single commit (`c7c2274`) on top of the six original
> DO-97 commits (97A–97F); history was not rewritten. Corrections delivered:
> reject scalar `applies_to`; enforce complete + acyclic supersession; replace
> private `_coerce_status` with public `parse_manual_status`; `Traversable`-native
> resource access (`resolve_manual_entry_resource`) with `resolve_manual_entry_path`
> reduced to a truthful filesystem-only shim; desktop viewer distinguishes
> empty / unavailable / invalid-manifest / missing-document states and cannot crash
> on a bad manifest. Production code is frozen at `c7c2274`; PR #9 is ready for
> final merge review.

> **DO-97 note:** the handoff listed a DO-96 "Laboratory manifest and registry"
> and an existing `tap_tone_pi/acoustic_lab/` package as dependencies. Neither
> existed in the repo, and DO-96 appears nowhere in history. DO-97 was
> implemented self-contained (see `docs/ARCHITECTURE_BASELINE_M4.md` §13). The
> manifest ships **empty** by design — no consolidated Laboratory Manual
> document exists yet, and fabricating one was prohibited. `analyzer/` full
> desktop-installer packaging remains a separate out-of-scope task.

> **Note on DO-94 numbering:** the commits `6b74304` / `8255c8e` are tagged
> "(DO-94)" but implement *pressure response mapping* — a non-goal of this
> dev order. This DO-94 (Luthiery Formula Target Mapping) is a distinct work
> item that reuses the same number. Its commits are labeled
> "luthiery formula target" for disambiguation.

## Sprint Summary

DO-001 through DO-008, and DO-084 through DO-089 completed. The tap_tone_pi modal mapping toolchain now has:

| Dev Order | Description | Status |
|---|---|---|
| DO-001 | GUM uncertainty framework | COMPLETED |
| DO-002 | Wood species data sourcing | COMPLETED |
| DO-003 | Per-flitch wood database | COMPLETED |
| DO-004 | Per-build instrument record schema | COMPLETED |
| DO-005 | Analyzer GUI: Phase 2 results widget | COMPLETED |
| DO-006 | Predicted-vs-measured comparison overlay | COMPLETED |
| DO-008 | Build record auto-discovery + cleanup | COMPLETED |
| DO-084 | Transfer function uncertainty propagation | COMPLETED |
| DO-085 | Repeatability evidence and measurement validity envelope | COMPLETED |
| DO-086 | Workflow measurement contracts and procedural provenance | COMPLETED |
| DO-087 | Experimental provenance and measurement campaign lineage | COMPLETED |
| DO-088 | Build session and environmental provenance | COMPLETED |
| DO-089 | Campaign lifecycle state and measurement set aggregation | COMPLETED |
| DO-089A | Experiment design contract and cohort planning framework | COMPLETED |
| DO-089B | Process variance evidence and feasibility summary | COMPLETED |
| DO-089C | Covariate-aware cohort regression | COMPLETED |
| DO-097 | Laboratory Manual packaging & desktop access | COMPLETED |
| DO-098 | Server data-root authorization | COMPLETED |
| DO-099 | Server authorization observability & diagnostics | COMPLETED |
| DO-100 | Guided Digital Laboratory Foundation | COMPLETED |

## Pre-existing test failures (baseline)

3 failures unrelated to this dev order:
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]` — missing 'bending' key
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]` — missing 'bending' key
- `test_advisory_in_calibration_is_error` — advisory boundary test

These are documented baseline failures, not introduced by this sprint.

## Daily log

### 2026-06-27 (DO-95)
- DO-95 PR 95A: FormulaValidationEnvelopeV1 contract (`tap_tone_pi/luthiery/formula_validation.py`)
- DO-95 PR 95B: validate_formula_candidate() scalar helper + validate_formula_candidate_from_evidence() overload
- DO-95 PR 95C: optional formula_validation_envelope schema block
- DO-95 PR 95D: additive export integration in export_viewer_pack_v1.py
- DO-95 PR 95E: tests/test_luthiery_formula_validation.py (13 tests)
- DO-95 PR 95F: docs reconciliation + package exports
- DO-95 complete — error-detection evidence around formula candidates; no pass/fail or advisory language

### 2026-06-27 (DO-94)
- DO-94 PR 94A: LuthieryFormulaDomain, LuthieryFormulaTargetV1, LuthieryFormulaEvidenceLinkV1 contracts (`tap_tone_pi/luthiery/formula_targets.py`)
- DO-94 PR 94B: create_luthiery_formula_target(), link_formula_candidate_to_target() helpers
- DO-94 PR 94C: optional luthiery_formula_target / luthiery_formula_evidence_link schema blocks
- DO-94 PR 94D: additive export integration in export_viewer_pack_v1.py
- DO-94 PR 94E: tests/test_luthiery_formula_targets.py (13 tests)
- DO-94 PR 94F: docs reconciliation (CURRENT.md, GOVERNANCE_AUDIT_HANDOFF.md)
- DO-94 complete — declarative luthiery formula target layer; no advisory logic

### 2026-06-19
- DO-89C Stage A: RegressionInputV1, RegressionCoefficientV1 contracts
- DO-89C Stage B: CohortRegressionEvidenceV1 contract
- DO-89C Stage C: FormulaCandidateEvidenceV1 contract
- DO-89C Stage D: fit_linear_cohort_regression() OLS helper
- DO-89C Stage E: create_formula_candidate_evidence() helper
- DO-89C Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-89C Stage G: Audit reconciliation
- DO-89C complete — 23 tests

- DO-89B Stage A: ReferenceBodyRecordV1 contract
- DO-89B Stage B: VarianceDecompositionV1 and decompose_variance()
- DO-89B Stage C: ProcessVarianceEvidenceV1 and compute_process_variance_evidence()
- DO-89B Stage D: VarianceBandThresholdsV1 and classify_variance_band()
- DO-89B Stage E: FeasibilitySummaryV1 and create_feasibility_summary()
- DO-89B Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-89B Stage G: Audit reconciliation
- DO-89B complete — 35 tests

### 2026-06-18
- DO-89A Stage A: Response variable and MIE contracts
- DO-89A Stage B: Covariate definition contract
- DO-89A Stage C: Randomization plan contract
- DO-89A Stage D: Baseline rebuild plan contract
- DO-89A Stage E: ExperimentDesignV1 governing object
- DO-89A Stage F: Design validation evidence
- DO-89A Stage G: Campaign linkage (experiment_design_id)
- DO-89A Stage H: Schema additions to phase2_ods_snapshot.schema.json
- DO-89A Stage I: Export integration in export_viewer_pack_v1.py
- DO-89A Stage J: Audit reconciliation
- DO-89A complete — 37 tests

### 2026-06-12
- DO-089 Stage A: CampaignLifecycleState enum and campaign lifecycle fields (7 tests)
- DO-089 Stage B: State transition helpers with validation (14 tests)
- DO-089 Stage C: MeasurementSetV1 and MeasurementSetSummaryV1 dataclasses (10 tests)
- DO-089 Stage D: Collection and aggregation helpers (7 tests)
- DO-089 Stage E: CampaignLifecycleExportV1 export block (4 tests)
- DO-089 Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-089 Stage G: Export integration in export_viewer_pack_v1.py
- DO-089 Stage H: Audit reconciliation (GOVERNANCE_AUDIT_HANDOFF.md, CURRENT.md)
- DO-089 complete — 42 tests

### 2026-07-16
- DO-97 (97A): Laboratory Manual contracts + empty manifest + canonical READMEs
- DO-97 (97B): Read-only path-safe manual registry (importlib.resources)
- DO-97 (97C): Desktop Help → Laboratory Manual read-only view
- DO-97 (97D): Package-data config; manifest + README verified in built wheel
- DO-97 (97E): 54 tests — contracts, negative, packaging, boundary, GUI
- DO-97 (97F): Reconciled M4 baseline, README, CURRENT.md
- DO-97 complete — 54 new tests, empty manifest by design

### 2026-05-03
- DO-008 Stage A: Doc reconciliation — no-op (no prediction.py refs found)
- DO-008 Stage B: PyQt6 dependency declaration (1 test)
- DO-008 Stage C: Build record auto-discovery (11 tests)
- DO-008 Stage D: View menu opt-out toggle (3 tests)
- DO-008 complete — 15 new tests

### 2026-05-02
- DO-001, DO-002, DO-003, DO-004 completed
- DO-005 Stage A: Phase 2 session loader (26 tests)
- DO-005 Stage B: Heatmap rendering primitive (20 tests)
- DO-005 Stage C: Phase 2 results widget (15 tests)
- DO-005 Stage D: Main window integration (8 tests)
- DO-006 Stage E: Comparison mode + prediction loader (20 tests)
- Sprint complete — 89 tests across all stages
