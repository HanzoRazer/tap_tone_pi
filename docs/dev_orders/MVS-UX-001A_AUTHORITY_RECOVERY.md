# MVS-UX-001A — MVS Authority Recovery and Adjudication

**Status:** COMPLETE — recovery and adjudication only.
**Mode:** Recover → classify → compare → adjudicate. Nothing was redesigned.
**Base:** `main` at `27e92bd`.
**Changed:** this file only. No runtime code, agent behavior, GUI, schema, or
contract was touched. `MVS_UX_CONTRACT_V1` was not created. MVS-UX-001B was not
begun.

---

## 0. The first finding: "MVS" is not a repository term

**"MVS" appears in zero tracked files at `27e92bd`.** Neither does "sophomore". The
identifier on this document is a work-tracking label for this investigation; it
introduces no concept into the repository and should not be read as evidence
that one exists.

What the repository has instead is a set of concepts that together cover much of
the same ground, under its own names:

| Handoff term | Repository vocabulary | Where |
| --- | --- | --- |
| minimum viable scientist / first-time user | `FIRST_RUN`, first-time user, FTUE | `tap_tone_pi/agent/ftue.py`, `types.py` |
| novice / expert | `UserStage` = `FIRST_RUN · NOVICE · REGULAR · EXPERT` | `tap_tone_pi/agent/types.py` |
| progressive disclosure | "stage inference and progressive disclosure"; `ExplanationMode` | `ftue.py:1-4`, `messages.py:38` |
| operator experience floor | *"without requiring the user to begin by selecting an analyzer, scientific model, FFT mode, or calculator"* | `docs/dev_orders/DO-100_GUIDED_DIGITAL_LABORATORY.md:19` |

So this packet adjudicates the handoff's propositions against **the repository's
vocabulary**, not its own. Where the handoff's term has no repository referent,
the proposition is recorded as not witnessed rather than mapped onto the nearest
thing that exists.

A second handoff premise is also absent: **"we are not building the agent"
appears in no tracked file.** It is dispositioned in §12, in two layers.

---

## 1. Scope and exclusions

**In scope:** recovery of what the tracked repository says, implements, tests,
and assumes about the first-time and inexperienced operator — FTUE, user stage,
moments, UWSM, attention directives, OperatorLoop, the agent message layer,
guidance pipelines, quality conditions, authority boundaries, user-facing
surfaces, and user documentation.

**Out of scope, and untouched:** any redesign; any change to moments, priority,
UWSM, guidance density, FTUE, OperatorLoop, quality gates, acquisition, Analyzer
mathematics, safe defaults, or agent behavior; progressive-disclosure or
DO/UNDERSTAND/INSPECT implementation; user modeling; agent development;
`MVS_UX_CONTRACT_V1`.

**Also not repaired, though found:** the latent defect in §9 K9 and the
authority conflicts in §9. Recording them is the job; fixing them is not
authorized here.

---

## 2. Methodology

**Evidence admitted:** tracked files on `main` at `27e92bd`, and git history.

**Evidence excluded:** untracked `__pycache__` residue (it contains bytecode for
modules with no source, which hints at history but is not repository evidence);
a checked-in chat transcript (`.github/tap_tone_pi_chat.txt`), whose one
"minimum viable" hit concerns the *instrument*, not the user, and which carries
none of the concepts under investigation.

**Secondary evidence:** `skylos-deadcode.json`, committed 2026-02-28 (`cff871c`).
It predates the PyQt guidance engine and every later spine change, so each
dead-code claim was re-checked against live source. Only its `unused_*` sections
are verdicts; its `definitions` section names every symbol and establishes
nothing.

**Definitions and consumers were searched separately**, per A02. A symbol with no
consumer is recorded as such, not as active behavior.

**Tests were read for what they prove, not what they are named** (D4).

### Method corrections made during recovery

Five errors were made and caught before this packet was written. They are
recorded because each is the failure the TTP PR admission protocol names, and a
reader reusing this method should not repeat them:

1. **Header-only reading.** OperatorLoop was first judged not to consume the
   spine from its import block. The spine is imported function-locally inside an
   advisory hook at line 584. Lazy imports are now read explicitly.
2. **Absolute-path consumer census.** FTUE first appeared unconsumed because the
   census matched only absolute module paths. Relative imports and package
   re-exports through `agent/__init__.py` were invisible. The census was redone
   through the package's public surface.
3. **Loose regex.** "Not building the agent" first appeared to be recorded in
   `AGENTIC_LAYER_DEV_HANDOFF.md`. The match came from `@dataclass(frozen=True)`
   and `DECISION_DEFERRED`. The phrase is in no tracked file.
4. **Report mis-parse.** The dead-code report was first read from its
   `definitions` section, which lists everything. Only `unused_*` sections are
   verdicts.
5. **Incomplete surface census.** The first pass found two guidance pipelines.
   There are more user-facing surfaces: a Tkinter GUI in `tap_tone_pi/gui/`, the
   DO-100 guided laboratory in `tap_tone_pi/guided_lab/`, and the `ttp quick`,
   `ttp demo` and `ttp record` commands were initially missed. §4 reflects the
   complete census.
6. **Unchecked citations.** Every line citation in this packet was then checked
   mechanically against source. Five pointed a few lines off and were corrected.
   The check also forced three substantive corrections: DO-100 is recorded
   `COMPLETE` in `CURRENT.md` (it had been read as never started);
   `ftue.infer_user_stage` has no production caller (it had been attributed to
   the standalone stack); and the design review's zero-config `ttp quick` is
   implemented (it had been filed as proposed only).

---

## 3. Source inventory

| Area | Tracked sources |
| --- | --- |
| Authority | `docs/ADR-0008-spine-wiring-architecture.md`, `ADR-0009-advisory-boundary.md`, `ADR-0010-guidance-authority-boundary.md` |
| Specifications | `docs/AGENT_DECISION_POLICY_V1.md`, `UWSM_UPDATE_RULES_V1.md`, `EVENT_MOMENTS_CATALOG_V1.md`, `AGENTIC_CONTRACTS_ENGINEER_HANDOFF.md`, `AGENTIC_SPINE_ARCHITECTURE_ONEPAGER.md`, `README_SPINE.md`, `ADVISORY_MODE_THIN_SLICE.md` |
| Handoffs / orders | `docs/AGENTIC_LAYER_DEV_HANDOFF.md`, `docs/dev_orders/DO-100_GUIDED_DIGITAL_LABORATORY.md` |
| Spine | `tap_tone_pi/agentic/spine/{moments,policy,uwsm_store,uwsm_update,view_adapter,shadow_record,directive_history,replay}.py` |
| Contracts | `tap_tone_pi/agentic/contracts/{advisory_authority,analyzer_attention,tool_capability,event_emission,confidence_domain}.py`, `agentic/events.py`, `agentic/capabilities.py` |
| Agent message layer | `tap_tone_pi/agent/{ftue,types,messages,message_spec,selector,measurement_agent,render}.py` |
| Workflow | `tap_tone_pi/workflow/operator_loop.py`, `workflow/attempt.py` |
| Guided laboratory | `tap_tone_pi/guided_lab/{engine,catalog,cli,models,validation,errors}.py`, `workflows/plate_measurement_setup_v1.py` |
| Quality | `tap_tone_pi/core/{quality_policy,quality_gate,analysis}.py` |
| User config | `tap_tone_pi/core/user_config.py` |
| CLI | `tap_tone_pi/cli/main.py` |
| Tkinter GUI | `tap_tone_pi/gui/{app,measurement_flow,quality_verdict,setup_wizard,tooltip,info_banner,advisory_state,directive_history_view,directive_outcomes,timeline_viewer}.py` |
| PyQt6 Analyzer | `analyzer/guidance/{engine,panel}.py` |
| User docs | `README.md`, `QUICKSTART.md`, `docs/ANALYZER_USER_GUIDE.md`, `docs/ISSUES_BACKLOG.md`, `CHANGELOG.md`, `tap-tone-pi-design-review.md` |
| Tests | 34 subsystem test files, listed in §8 |
| Secondary | `skylos-deadcode.json` (2026-02-28) |

---

## 4. The recovered architecture

The handoff's model places one OperatorLoop between four kinds of state and the
presentation layer. **The repository does not support that model.** It has
several guidance and progression systems, independently wired, sharing two
contracts:

```text
CLI  ttp setup ("run first!") · ttp demo (synthetic audio, no hardware)
CLI  ttp quick   — zero-config: auto-detect device → analyze_tap → print   (no quality gate, no guidance)
CLI  ttp record [--agent] [--expert]  — quality gate + agent message, stage pinned to "novice"

CLI  ttp measure [--agent] [--expert]
  OperatorLoop (MEASUREMENT)  ──emits──►  events
     └─ advisory hook (M1 default):  UWSM load/decay/update → detect_moments → policy.decide
                                     → AttentionDirectiveV1 (+ M2 view commands, no real adapter)
  agent message layer (deterministic, template-driven)  ← UserStage, ExplanationMode

CLI  ttp guided-lab list|start|resume|show|act
  guided_lab engine (DO-100) — deterministic, goal-first, self-contained, "no model"
     owns procedure state only; imports nothing else from tap_tone_pi

GUI  ttp gui  (Tkinter, tap_tone_pi/gui/)
  measurement_flow → core.analysis / quality_gate directly   (bypasses OperatorLoop)
  quality_verdict   ← reads spine OUTPUTS: shadow records, directive history, events

GUI  PyQt6 Analyzer (analyzer/)
  AnalyzerGuidanceEngine → Claude API (if ANTHROPIC_API_KEY) or deterministic fallback
     → AttentionDirectiveV1 → GuidancePanelWidget        ← UserStage; no spine, no UWSM

shared across systems:   AttentionDirectiveV1 · UserStage
```

Four facts follow, and 001B will have to take each as given:

1. **OperatorLoop is an integration point, not the integration point.** It
   integrates measurement state with guidance on `ttp measure` only.
2. **Guidance is deterministic almost everywhere.** The only model-backed path is
   the PyQt Analyzer engine, and it falls back to fixed text without a key.
3. **Two independent progression concepts exist**: a measurement-attempt state
   machine (OperatorLoop) and a procedure-state machine (guided laboratory). A
   third, user-competence stage, is orthogonal to both.
4. **The user model is an identity classification.** `UserStage` exists, and the
   top stage is declared rather than earned.

---

## 5. Recovered propositions

57 propositions. Full records for C-bearing, conflicting, authority-boundary,
001B-shaping, and non-obvious claims; compact records for the rest.

Classification counts:

| Classification | Count |
| --- | ---: |
| `CURRENT_AUTHORITY` | 6 |
| `IMPLEMENTED_BEHAVIOR` | 36 |
| `PROPOSED_DESIGN` | 1 |
| `EXPERIMENTAL` | 1 |
| `SUPERSEDED` | 0 |
| `CONFLICTING` | 8 |
| `UNKNOWN` | 5 |

`SUPERSEDED` is zero deliberately. Several propositions look superseded — the
standalone message stack, the moment catalog's priority appendix — but no tracked
authority says so, and D14 forbids choosing between conflicting sources. They are
recorded as `CONFLICTING` or with a `SUPERSEDE_CANDIDATE` disposition instead.

### 5.1 Full records

#### Authority boundaries

**P01 — Guidance may not establish truth** · `AUTHORITY_BOUNDARY` · **CURRENT_AUTHORITY**
- **Claim:** Decision-support output may explain and hint, but may not establish
  truth, modify measurement state, or enter measurement export. UI must not
  conflate guidance with measurement (D6: no measurement-result colors for
  recommendations).
- **Source:** `docs/ADR-0010-guidance-authority-boundary.md` — Status: Accepted;
  core invariant *"Guidance may not establish truth."*
- **Owner:** ADR-0010.
- **Consumers:** `AdvisoryAuthorityV1` (P03); `policy._build_directive` stamps
  every spine directive with `AGE_ATTENTION_AUTHORITY`; `tests/test_advisory_authority_contract.py`,
  `tests/test_guidance_not_in_measurement_exports.py`.
- **Evidence:** Accepted status; encoded as data flags; enforced by a validator
  and two test files.
- **Conflict:** latent only — K9 (a dead GUI path that would fabricate a
  confidence value if it ever ran).
- **Disposition:** PRESERVE · **001B:** YES

**P03 — Advisory authority is encoded and validated** · `AUTHORITY_BOUNDARY` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** `AdvisoryAuthorityV1` carries `can_establish_truth`,
  `can_modify_measurement`, `can_enter_measurement_export`, all default `False`;
  a validator raises if decision-support authority claims export; the spine's
  `AGE_ATTENTION_AUTHORITY` sets all three `False`.
- **Source:** `tap_tone_pi/agentic/contracts/advisory_authority.py:59-125`.
- **Owner:** implements ADR-0010.
- **Consumers:** `agentic/spine/policy.py` (every directive); contracts package.
- **Evidence:** default-deny flags; validator branches at `:97-110`.
- **Conflict:** none found.
- **Disposition:** PRESERVE · **001B:** YES

**P04 — The guided laboratory's constitutional boundary** · `AUTHORITY_BOUNDARY` · **CURRENT_AUTHORITY**
- **Claim:** The guided workflow layer may sequence, validate, explain, invoke
  measurement through explicit adapters, record progress and operator decisions,
  and expose uncertainty. It may not invent acceptance limits, *"mutate
  acquisition parameters without an explicit user action"*, convert advice into
  manufacturing instruction, decide wood removal, claim unsupported conclusions,
  or embed undocumented formulas. *"The measurement core remains authoritative
  for measured values. The workflow engine remains authoritative only for
  procedure state."*
- **Source:** `docs/dev_orders/DO-100_GUIDED_DIGITAL_LABORATORY.md:90-110`.
- **Owner:** DO-100.
- **Consumers:** `tap_tone_pi/guided_lab/` — whose own docstring restates the
  boundary (*"owns none of the science… no network, no model"*).
- **Evidence:** the clearest statement anywhere in the repository of the
  separation D2 asks to preserve; the implementation conforms. `CURRENT.md`
  records DO-100 `COMPLETE` (PR #16, merge `6ca0105`; closed in `fecbe84`) and
  names the file the *"Authoritative handoff"* (`CURRENT.md:511-532, 676`).
- **Conflict:** minor — the handoff's own Status line still reads *"QUEUED /
  NOT STARTED"* (`:3-5`), contradicting `CURRENT.md`. Its authority is not in
  doubt; its header is stale. Its scope is: the principles are written for the
  guided laboratory, not for every surface (B4).
- **Disposition:** PRESERVE; header RECONCILE · **001B:** YES

**P05 — What guidance can actually do** · `AUTHORITY_BOUNDARY` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** Attention directives are requests *to the user*: `AttentionAction`
  is documented as *"What the agent wants the user to do"* (`INSPECT`, `REVIEW`,
  `COMPARE`, `DECIDE`, `CONFIRM`, `INTERVENE`, `ABORT`). M2 "actuation" commands
  are view-only — `focus_trace`, `hide_all_except`, `highlight_delta`,
  `reset_view`. `CapabilityAction` contains no acquisition, parameter, or export
  verb.
- **Source:** `agentic/contracts/analyzer_attention.py` (`AttentionAction`);
  `agentic/spine/view_adapter.py:7-56`; `agentic/contracts/tool_capability.py`.
- **Owner:** the attention and capability contracts.
- **Consumers:** `policy.py`, `operator_loop.py`, both GUIs' directive handling.
- **Evidence:** D11's prohibitions — start/stop acquisition, change parameters,
  export, alter quality outcome — hold **by structural absence**: no directive,
  command, or capability expresses them. `INTERVENE` and `ABORT` ask a person to
  act; they do not act.
- **Conflict:** D11's list is **not encoded as an explicit prohibition**.
  `SafeDefaults` (`tool_capability.py:53`) carries privacy, `dry_run=True`,
  `require_confirmation=True` and resource limits — not those actions. The
  boundary holds today because nothing can express the actions, not because
  anything forbids them.
- **Disposition:** RECONCILE · **001B:** CONDITIONAL — 001B must decide whether
  structural absence is a sufficient guarantee.

**P06 — Advisory placement rule** · `AUTHORITY_BOUNDARY` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** *"Advisory data is allowed only in designated locations"*:
  `session_timeline_v1.json`, anything under `advisory/`, anything under
  `agentic/`. Measurement artifacts (`analysis.json`, `quality_check.json`,
  `manifest.json`) must not contain advisory keys.
- **Source:** `tests/test_guidance_not_in_measurement_exports.py:7-8, 22, 38-43`.
- **Owner:** the test; implements ADR-0010 item 4.
- **Consumers:** CI.
- **Evidence (D4 — what the test proves):** the checker logic, on fixtures and
  `tmp_path` structures. **It does not scan real OperatorLoop output.** It proves
  the rule is deliberately protected, not that live sessions comply.
- **Conflict:** K5.
- **Disposition:** PRESERVE · **001B:** YES

**P07 — UWSM audit written outside the advisory locations** · `AUTHORITY_BOUNDARY` · **CONFLICTING**
- **Claim:** OperatorLoop writes UWSM update audits to
  `<session_dir>/uwsm_audit.jsonl`.
- **Source:** `tap_tone_pi/workflow/operator_loop.py:197-204, 683`.
- **Owner:** OperatorLoop advisory hook.
- **Consumers:** none found.
- **Evidence:** the file sits at the session root — not `session_timeline_v1.json`,
  not under `advisory/`, not under `agentic/`.
- **Conflict:** P06's placement rule. Mitigating: a pattern search of the export
  code found no directory sweep, so it probably does not reach a viewer pack. A
  pattern search does not prove that.
- **Disposition:** RECONCILE · **001B:** CONDITIONAL — on B7.

**P08 — "Cannot override" versus two override paths** · `AUTHORITY_BOUNDARY` · **CONFLICTING**
- **Claim:** `Severity.HARD` is documented *"Must fail, cannot override"*.
  Yet `OperatorLoop.override_failed(point_id, reason)` overrides the latest
  `FAILED` attempt, whatever rule failed it, given a non-empty reason; the CLI
  calls it; the Tkinter GUI implements its own override by writing
  `override.json`.
- **Source:** `core/quality_policy.py:28-32`; `workflow/operator_loop.py:768-792`;
  `cli/main.py:608, 622`; `gui/measurement_flow.py:238-262`.
- **Owner:** quality policy (severity) vs workflow (attempt status).
- **Consumers:** CLI and Tkinter GUI.
- **Evidence:** override changes the *attempt* status and records a reason; the
  `FAIL` verdict itself is preserved. It is human-initiated, never
  guidance-initiated.
- **Conflict:** wording-level contradiction between "cannot override" and a
  reachable override. Reconcilable as *verdict cannot be overridden; workflow
  advancement can* — but no source says so.
- **Disposition:** RECONCILE · **001B:** CONDITIONAL — on B8.

#### Workflow and progression

**P10 — OperatorLoop is a measurement state machine** · `WORKFLOW_STATE` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** `INSTRUMENT CLASS: MEASUREMENT`. A deterministic workflow —
  `IDLE → PREFLIGHT → READY → (LISTENING) → CAPTURING → ANALYZING → GATING →
  PASSED | WARNED | FAILED → COMPLETED` — that *"enforces quality gates and
  prevents silent advancement past failed measurements."*
- **Source:** `tap_tone_pi/workflow/operator_loop.py:1-9` and `LoopState`.
- **Owner:** the module; no ADR designates it as the canonical workflow.
- **Consumers:** `cli/main.py:701` (`ttp measure`); `grant_readiness/inventory.py`.
- **Evidence:** 525 subsystem tests pass, including
  `test_workflow_operator_loop.py` and `test_event_emission_operator_loop.py`.
- **Conflict:** none — but it is not used by `ttp record`, `ttp quick`, the
  Tkinter GUI (P13), or the guided laboratory (P14).
- **Disposition:** PRESERVE · **001B:** YES

**P11 — OperatorLoop is where the spine meets measurement** · `OTHER` (orchestration) · **IMPLEMENTED_BEHAVIOR**
- **Claim:** Per attempt, an advisory hook loads and decays persisted UWSM,
  applies updates from events, runs `detect_moments()` and `decide()` in the
  current spine mode, dispatches M2 view commands if an adapter exists, persists
  UWSM and its audit, and writes a shadow record.
- **Source:** `workflow/operator_loop.py:584-766` (lazy imports at `:631-635`);
  `spine_mode` default `"M1"` at `:121`; M2 without adapter falls back to M1 at
  `:143-147`.
- **Owner:** ADR-0008 (spine wiring — no status line; see P54).
- **Consumers:** the `ttp measure` path.
- **Evidence:** read in full, including the function-local imports a header read
  misses (§2, correction 1).
- **Conflict:** minor — a comment at `:161` says `decide()` returns plain dicts,
  while `policy._coerce_directive` guarantees `AttentionDirectiveV1` (P15).
- **Disposition:** PRESERVE · **001B:** YES

**P13 — The Tkinter GUI measures without OperatorLoop** · `WORKFLOW_STATE` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** `gui/measurement_flow.py` calls `core.analysis.analyze_tap`,
  `core.quality_gate.check_quality` and `Verdict` directly, and implements its
  own override.
- **Source:** `tap_tone_pi/gui/measurement_flow.py:19-57, 238-262, 354`.
- **Owner:** the Tkinter GUI.
- **Consumers:** `ttp gui` (`cli/main.py:888, 1518`).
- **Evidence:** no import of OperatorLoop, `policy`, `moments` or UWSM. Its
  `quality_verdict.py` *reads* spine outputs — shadow records, directive history,
  events — for advisory display.
- **Conflict:** with C7, and possibly with itself: if GUI-captured points never
  run the advisory hook, the advisory panel reads records nothing produced.
  Not verified at runtime — see open question O3.
- **Disposition:** UNRESOLVED · **001B:** CONDITIONAL — on B9.

**P14 — The guided laboratory owns procedure state** · `WORKFLOW_STATE` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** A deterministic, goal-first procedure engine. *"A builder starts
  from a goal… not from an analyzer. This package owns the procedure: the
  questions asked, the instructions shown, the evidence required, and the
  resumable session record."* Pure: *"no filesystem, no audio device, no network,
  no model."* Reference workflow: `plate_measurement_setup_v1`.
- **Source:** `tap_tone_pi/guided_lab/__init__.py:1-30`;
  `guided_lab/cli.py:260-379`; DO-100.
- **Owner:** DO-100 (see P04 conflict).
- **Consumers:** `ttp guided-lab list|start|resume|show|act`;
  `grant_readiness/inventory.py`, `pitch_source.py`.
- **Evidence:** imports nothing else from `tap_tone_pi`; no link to the spine,
  FTUE, `UserStage`, OperatorLoop, or the agent layer. The "explicit adapters" to
  measurement that DO-100 permits do not exist yet — today it sequences procedure
  only. The separation is deliberate: `CURRENT.md` lists *"an adapter between
  `tap_tone_pi.guided_lab` and existing `tap_tone_pi.workflow` measurement
  contracts"* among DO-100's non-goals left for later orders.
- **Conflict:** none in content; header staleness per P04.
- **Disposition:** PRESERVE · **001B:** YES

#### Moments

**P16 — Moments are interaction patterns, not measurement states** · `ATTENTION_MOMENT` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** Moments are named patterns detected from `AgentEventV1` streams —
  explicit feedback, undo spikes, tool open/close toggles, idle timeouts,
  repeated hovers, view rendering, analysis completion or failure,
  acknowledgement and dismissal rates.
- **Source:** `tap_tone_pi/agentic/spine/moments.py` — `INSTRUMENT CLASS:
  DECISION SUPPORT`; *"Moment Detection Engine — Reference Implementation"*, a
  *"conservative, dependency-light implementation"* designed to *"Pass the test
  suite"*, *"Work correctly in shadow mode"*, and *"Provide a bootstrap for CI"*.
- **Owner:** `docs/EVENT_MOMENTS_CATALOG_V1.md` (v1.0.0, no status).
- **Consumers:** `workflow/operator_loop.py:690`.
- **Evidence:** every detector reads interaction or analysis events. `ERROR`
  comes from `analysis_failed` / `system_error` events — not from a quality rule.
  No detector reads a quality verdict.
- **Conflict:** none on ontology. Priority per P17.
- **Disposition:** PRESERVE · **001B:** YES — as its own ontology, never merged
  with quality conditions (D2, A03).

**P17 — Moment priority, as implemented** · `ATTENTION_MOMENT` · **CONFLICTING**
- **Claim:** Eight moments: `ERROR 1 · OVERLOAD 2 · TRUST_EROSION 3 ·
  DECISION_REQUIRED 4 · FINDING 5 · CONFIDENCE_CLIMB 6 · HESITATION 7 ·
  FIRST_SIGNAL 8`.
- **Source:** `agentic/spine/moments.py:26` (`PRIORITY`).
- **Owner:** the catalog, per the module docstring.
- **Consumers:** `detect_moments`; OperatorLoop.
- **Evidence:** live code; tested in `test_moments_engine_v1.py`.
- **Conflict:** **the catalog's own priority appendix lists six**
  (`EVENT_MOMENTS_CATALOG_V1.md:625-636`): `ERROR, OVERLOAD, DECISION_REQUIRED,
  FINDING, HESITATION, FIRST_SIGNAL`. `TRUST_EROSION` and `CONFIDENCE_CLIMB`
  were added to the catalog's body and to the code; the appendix never followed.
  The handoff's "known ordering" matches the appendix exactly, so that is its
  source.
- **Disposition:** RECONCILE · **001B:** CONDITIONAL — on B1.

#### UWSM

**P21 — What UWSM is** · `USER_GUIDANCE_CONTEXT` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** A per-user adaptive guidance-policy state — not a measurement
  record, not a skill model. Seven dimensions, each with a value, a confidence,
  and a decay half-life: `cognitive_load_sensitivity` (7 d),
  `guidance_density` (14 d), `initiative_tolerance` (21 d),
  `exploration_style` (10 d), `risk_posture` (10 d), `feedback_style` (21 d),
  `representation_preference` (14 d). Defaults `medium · shared_control ·
  medium · iterative · balanced · neutral · mixed`, confidence floor 0.20.
  Exponential decay toward the floor; a value flip needs two consecutive evidence
  windows (hysteresis).
- **Source:** `agentic/spine/uwsm_update.py:56-74, 144`;
  `agentic/spine/uwsm_store.py:113-163`.
- **Owner:** `docs/UWSM_UPDATE_RULES_V1.md` (v1.0.0, no status).
- **Consumers:** OperatorLoop (load, decay, update, persist); `policy.decide`.
- **Evidence:** persisted per user at `$XDG_CONFIG_HOME/tap_tone_pi/uwsm_v1.json`
  or `~/.config/tap_tone_pi/uwsm_v1.json` (`uwsm_store.py:45-55`), with a per-session
  audit (P07). `test_uwsm_persistence.py` passes.
- **Conflict:** none in definition.
- **Disposition:** PRESERVE · **001B:** YES

**P22 — Only three of seven UWSM dimensions are consumed** · `USER_GUIDANCE_CONTEXT` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** `policy.decide` reads three dimensions:
  `cognitive_load_sensitivity` caps directives (1 when high, else 2);
  `initiative_tolerance` = `user_led` suppresses proactive suggestions;
  `guidance_density` = `very_low`/`low` cuts directives to summary-only. The other
  four are updated, decayed and persisted, and **read by nothing**.
- **Source:** `agentic/spine/policy.py` (`decide`, `_max_directives_for_load`,
  initiative gate, guidance-density gate).
- **Owner:** `AGENT_DECISION_POLICY_V1.md`.
- **Consumers:** as stated.
- **Evidence:** full reads of `policy.py` and a repository-wide search for each
  dimension name.
- **Note:** `_build_directive` accepts a `guidance` parameter and never uses it —
  flagged by the dead-code report in February and still true in live source.
  `guidance_density` therefore acts only through the later gate.
- **Conflict:** none. Recorded as an **implementation/consumption asymmetry**,
  not a defect. `representation_preference` is the notable case: the
  architecture captured a representational preference and never wired it to any
  output — directly relevant to any future disclosure model.
- **Disposition:** UNRESOLVED · **001B:** CONDITIONAL — on B11.

**P24 — UWSM cannot reach evidence or quality** · `AUTHORITY_BOUNDARY` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** UWSM influences attention guidance only.
- **Source:** structural — UWSM's only reader is `policy.decide`, whose only
  output is an `AttentionDirectiveV1` stamped with `AGE_ATTENTION_AUTHORITY`. No
  UWSM value reaches `analyze_tap`, `check_quality`, or any verdict.
- **Owner:** ADR-0010 (general rule for decision support).
- **Consumers:** n/a — this is a boundary, not a behavior.
- **Evidence:** consumer census; `policy.py` read in full.
- **Conflict:** `UWSM_UPDATE_RULES_V1.md` **does not itself state** what UWSM may
  or may not influence. The limit is real but inherited, not declared. Placement
  per P07.
- **Disposition:** PRESERVE · **001B:** YES

#### User stage and disclosure

**P26 — A novice/expert user classification already exists** · `USER_GUIDANCE_CONTEXT` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** `UserStage = FIRST_RUN · NOVICE · REGULAR · EXPERT`. FTUE is
  *"stage inference and progressive disclosure. Controls how much detail the agent
  shows based on user experience level."*
- **Source:** `tap_tone_pi/agent/types.py`; `agent/ftue.py:1-4`.
- **Owner:** the agent message layer.
- **Consumers:** `agent/messages.py`, `measurement_agent.py`, `selector.py`;
  `analyzer/guidance/engine.py:37` and `panel.py:60`; the CLI via `--expert`.
- **Evidence:** consumed by both a CLI and a GUI surface.
- **Conflict:** with the handoff's D6 and C3 framing. The repository models the
  user as an identity stage.
- **Disposition:** PRESERVE — recorded as found · **001B:** CONDITIONAL — on B10.

**P27 — Two stage-inference functions, divergent thresholds** · `USER_GUIDANCE_CONTEXT` · **CONFLICTING**
- **Claim:** Stage inference is implemented twice:

  | | `ftue.infer_user_stage` | `messages.infer_user_stage` |
  | --- | --- | --- |
  | `FIRST_RUN` | no passes | no passes |
  | `NOVICE` | sessions ≤ 5 **or** passes ≤ 20 | sessions < 5 **or** passes < 10 |
  | Wins over inference | an explicit stage argument | `expert_mode`, then a supplied `user_stage` |
  | Returns | `UserStage` members | plain strings, despite the annotation |
  | Callers | **no production caller** — exported as `standalone_infer_user_stage` (`agent/__init__.py:45`); tests only | the live CLI path (`messages.py:596, 861`) |

  A third rule is documented and matches neither: *"0 passes → `FIRST_RUN`,
  ≤5 sessions → `NOVICE`, else → `REGULAR`"* (`AGENTIC_LAYER_DEV_HANDOFF.md:539`).
  And one live path skips inference altogether: `ttp record --agent` pins
  `user_stage="novice"` (`cli/main.py:257`), so every `record` user is a novice
  unless they pass `--expert` (P57).
- **Source:** `agent/ftue.py:88-115`; `agent/messages.py:504-517`.
- **Owner:** unclear — three statements of one classification.
- **Consumers:** as tabled.
- **Evidence:** both functions read in full; callers found by repository search.
- **Conflict:** the same user can be `NOVICE` under one rule and `REGULAR` under
  another. In practice only the `messages.py` rule reaches a user.
- **Disposition:** RECONCILE · **001B:** NO — until B2 resolves.

**P28 — `EXPERT` is declared, never earned** · `USER_GUIDANCE_CONTEXT` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** Neither inference rule ever produces `EXPERT` from usage. Automatic
  progression stops at `REGULAR`; `EXPERT` comes only from an explicit override —
  `--expert` on the CLI (`cli/main.py:1328, 1444`), which sets `expert_mode`.
- **Source:** `ftue.py:103-115`; `messages.py:508-517`.
- **Owner:** the agent message layer.
- **Consumers:** every `EXPERT`-gated disclosure — `show_metrics` and
  `show_advanced_note` return true **only** for `EXPERT` (`ftue.py:73-80`).
- **Evidence:** read in full.
- **Consequence (non-obvious):** raw metrics — RMS, peak level, thresholds — are
  never shown by the guidance layer to a user who has not declared themselves an
  expert, however much they have used the tool.
- **Conflict:** none internal; bears directly on C3 and C4.
- **Disposition:** PRESERVE · **001B:** YES — as a fact 001B must design around.

**P30 — Two explanation-mode implementations, divergent thresholds** · `PRESENTATION` · **CONFLICTING**
- **Claim:** A three-tier explanation verbosity — `FULL` (what happened, why it
  matters, common causes), `SHORT` (one sentence plus fix), `COMPACT` (no
  explanation) — keyed to **how often a rule has been seen**, not to user stage.
  Implemented twice: `messages.py` switches to `COMPACT` at three sessions,
  `selector.py` at two.
- **Source:** `agent/messages.py:38-67`; `agent/selector.py:26-58`.
- **Owner:** unclear.
- **Consumers:** `messages.py` is live (CLI); `selector.py` has no external
  production consumer.
- **Evidence:** both read in full.
- **Conflict:** divergent thresholds for one behavior.
- **Disposition:** RECONCILE — `selector.py` is a `SUPERSEDE_CANDIDATE`, but no
  source says so · **001B:** CONDITIONAL — on B3.

**P34 — First-time "One-Trace" onboarding cannot actuate** · `PRESENTATION` · **EXPERIMENTAL**
- **Claim:** On `FIRST_SIGNAL` for a first-time user in M2, policy emits
  `hide_all_except(primary_panel)` and `focus_trace(primary_trace)`
  (`POLICY_FTUE_ONE_TRACE_v1`).
- **Source:** `agentic/spine/policy.py:195-206`;
  `docs/AGENTIC_LAYER_DEV_HANDOFF.md:275, 640`.
- **Owner:** `AGENT_DECISION_POLICY_V1.md` §1.4 — M2 is "Actuated (Opt-In)".
- **Consumers:** **none in production.** The only `ViewAdapter` implementations
  are the protocol and `NullViewAdapter`, both in `view_adapter.py` itself. No GUI
  implements it, and the CLI passes no adapter, so OperatorLoop falls back to M1.
- **Evidence:** repository-wide search for `hide_all_except` / `focus_trace`.
- **Conflict:** none — it is implemented, tested, and inert.
- **Disposition:** PRESERVE · **001B:** CONDITIONAL.

**P35 — The M0 / M1 / M2 model is live** · `OTHER` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** M0 Shadow (decide, record, emit nothing); M1 Advisory (emit
  directives); M2 Actuated, opt-in (also dispatch view commands).
- **Source:** `docs/AGENT_DECISION_POLICY_V1.md` §1.1–1.4, Appendix C;
  `policy.py`; `operator_loop.py:121-147`.
- **Owner:** `AGENT_DECISION_POLICY_V1.md` (v1.0.0, no status).
- **Consumers:** OperatorLoop. The CLI runs **M1 by default**.
- **Evidence:** code and specification agree.
- **Conflict:** none. M2 is inert in practice (P34).
- **Disposition:** PRESERVE · **001B:** YES

#### Guidance systems

**P36 — Two agent message stacks** · `OTHER` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** An *integrated* stack — `messages.build_agent_message(ctx, verdict)`
  over real quality types — and a *standalone* stack —
  `measurement_agent.build_agent_message(verdict, rule_ids)`, exported as
  `standalone_build_agent_message`, with `MeasurementAgent`, `selector.py`, and
  `ftue.infer_user_stage`.
- **Source:** `agent/__init__.py:23, 66-86`; `messages.py:851`;
  `measurement_agent.py:150`.
- **Owner:** the agent package; two modes are documented deliberately.
- **Consumers:** integrated — `cli/main.py:243, 528, 711`, `render.py`.
  Standalone — **no external production consumer**; the dead-code report flags
  `MeasurementAgent.suggest_next_action` and `SuggestedAction`.
- **Evidence:** the duplicate `build_agent_message` names are resolved by explicit
  aliasing, so they are not a conflict. The divergences are in P27 and P30.
- **Conflict:** none in naming.
- **Disposition:** UNRESOLVED · **001B:** CONDITIONAL.

**P38 — The PyQt Analyzer's guidance engine calls Claude** · `OTHER` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** `AnalyzerGuidanceEngine` observes pack, peak, coherence and wood
  events and calls `https://api.anthropic.com/v1/messages` in daemon threads when
  `ANTHROPIC_API_KEY` is set; otherwise, or on failure, emits deterministic
  fallback text. Output: `AttentionDirectiveV1` to `GuidancePanelWidget`. Prompts
  are tailored to `UserStage`.
- **Source:** `analyzer/guidance/engine.py:15-19, 43`; API call `:73-100`;
  stage-tailored prompts `:109-197`; fallbacks `:209-271`.
- **Owner:** ADR-0009 names `AnalyzerGuidanceEngine` an advisory-class module.
- **Consumers:** `analyzer/guidance/panel.py`.
- **Evidence:** added `9293b2d` (2026-03-30, "Sprint AGE"), after the spine
  (February). Three later commits (`e315ae2`, `de76c00`, `85c4055`, all
  2026-07-18) only reformatted it; a whitespace-insensitive diff shows no
  behavioral change since March. It calls no acquisition, export, or quality
  function.
- **Conflict:** with D12 as a repository proposition (§12). Data egress per P09.
- **Disposition:** PRESERVE — recorded, not judged · **001B:** CONDITIONAL — on B9.

**P39 — Several guidance systems, two shared contracts** · `OTHER` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** The spine, the agent message layer, the guided laboratory, the
  Tkinter GUI's advisory display, and the PyQt Claude engine are separate
  systems. `AttentionDirectiveV1` and `UserStage` are the only things shared
  across more than one.
- **Source:** §4; the consumer census in §8.
- **Owner:** no single owner. ADR-0008 covers spine wiring only.
- **Consumers:** n/a.
- **Evidence:** the PyQt Analyzer imports neither OperatorLoop, `moments`, UWSM
  nor `policy`. The guided laboratory imports nothing else from the package. The
  Tkinter measurement flow bypasses OperatorLoop.
- **Conflict:** with the handoff's single-integration-point model (C7).
- **Disposition:** PRESERVE · **001B:** YES — as the architecture 001B inherits.

**P40 — A dead GUI path would fabricate a measurement result** · `AUTHORITY_BOUNDARY` · **CONFLICTING**
- **Claim:** The PyQt engine's wolf-tone handler imports
  `tap_tone_pi.agent.wolf_guidance.generate_wolf_guidance`, builds a
  `unittest.mock.MagicMock` wolf result with `confidence = 0.8`, `pairs = []` and
  a mocked avoided-crossing model, and passes it to that function — all inside
  `except Exception: pass`.
- **Source:** `analyzer/guidance/engine.py` (wolf handler, import at `:332`);
  added in `9293b2d`.
- **Owner:** the PyQt guidance engine.
- **Consumers:** the GUI event stream.
- **Evidence:** `tap_tone_pi/agent/wolf_guidance.py` does not exist on disk, is
  not tracked, and has no history on any branch. `generate_wolf_guidance` is
  defined nowhere. The import therefore fails on every call and the blanket
  `except` hides it.
- **Conflict:** **latent, with ADR-0010.** If the import ever resolved, guidance
  would be generated from a fabricated result carrying an invented confidence — a
  mock object in production code standing in for measurement. It is unreachable
  today, so no fabricated confidence reaches a user.
- **Disposition:** UNRESOLVED — packet-only; not fixed · **001B:** blocker B6.

#### Quality and measurement truth

**P43 — Quality conditions are deterministic rules** · `MEASUREMENT_CONDITION` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** Nine rules, two severities. `HARD` fails the attempt; `SOFT` warns.

  | Rule | Severity | Handoff term | Message |
  | --- | --- | --- | --- |
  | `Q001_CLIPPED` | HARD | clipped | *Signal is clipping. Reduce microphone gain and retry.* |
  | `Q002_SILENT` | HARD | no signal | *No audio signal detected (RMS < 0.001). Check microphone connection.* |
  | `Q003_NO_PEAKS` | HARD | no resonance | *No frequency peaks detected. Ensure specimen was tapped.* |
  | `Q004_LOW_CONFIDENCE` | HARD | low confidence | *Measurement confidence below threshold (< 0.3). Retry with better tap.* |
  | `Q005_INVALID_SAMPLE_RATE` | HARD | — | *Sample rate must be 44100, 48000, or 96000 Hz.* |
  | `Q010_QUIET` | SOFT | — | *Signal is quiet (RMS < 0.01). Consider increasing microphone gain.* |
  | `Q011_NEAR_CLIPPING` | SOFT | — | *Signal is near clipping (peak > 0.9). Consider reducing gain.* |
  | `Q012_MARGINAL_CONFIDENCE` | SOFT | — | *Measurement confidence is marginal (0.3-0.5). Consider retaking.* |
  | `Q013_FEW_PEAKS` | SOFT | — | *Only {peak_count} peaks detected. May indicate poor acoustic coupling.* |

  "Acceptable measurement" is `Verdict.PASS`.
- **Source:** `tap_tone_pi/core/quality_policy.py:20-133`.
- **Owner:** the quality policy; `MEASUREMENT` class under ADR-0009.
- **Consumers:** `core/quality_gate.check_quality`; OperatorLoop; Tkinter
  `measurement_flow`; the agent message layer.
- **Evidence:** each is a deterministic condition. None is a moment, an agent
  rule, or a merely proposed concept. Every message is plain and names a
  corrective action.
- **Conflict:** "cannot override" per P08.
- **Disposition:** PRESERVE · **001B:** YES

**P44 — What owns measurement truth** · `MEASUREMENT_CONDITION` · **IMPLEMENTED_BEHAVIOR**
- **Claim:** Measured values come from `core/analysis.analyze_tap`; acceptability
  from `core/quality_gate.check_quality` under `core/quality_policy`
  (`Verdict`: `PASS · WARN · FAIL`).
- **Source:** those modules; OperatorLoop's imports at `:44-46`.
- **Owner:** ADR-0009 (`MEASUREMENT` class) and ADR-0010.
- **Consumers:** every measurement surface.
- **Evidence:** DO-100 states it in words: *"The measurement core remains
  authoritative for measured values."*
- **Conflict:** none.
- **Disposition:** PRESERVE · **001B:** YES

#### Users

**P48 — An observed first-time user session** · `PRESENTATION` · **UNKNOWN**
- **Claim:** A first-time user testing the PyQt6 Analyzer with sample data
  (noted 2026-02-18) said *"Would take some really explaining to make the user
  comfortable."* Findings: no onboarding or tutorial (*"What do I do first?"*
  suggested); metrics — Coherence, Quality Factor, Est. Stiffness — unexplained;
  **no feedback on failed operations**; no working sample data. Priority P2.
- **Source:** `docs/ISSUES_BACKLOG.md:2-40`.
- **Owner:** the backlog.
- **Consumers:** n/a.
- **Evidence:** the only observational evidence in the repository about a
  first-time user. It predates the PyQt guidance engine (March), and whether any
  finding was since resolved is not recorded. The Tkinter GUI now has a setup
  wizard (hardware configuration, `ttp setup`) and a tooltip widget, but those
  belong to a different GUI from the one tested.
- **Classification:** historical observation; its present truth is `UNKNOWN`.
- **Conflict:** with C1 as current reality.
- **Disposition:** PRESERVE · **001B:** YES — as evidence, not as a requirement.

**P52 — The agentic layer was handed off for continued development** · `OTHER` · **UNKNOWN**
- **Claim:** `AGENTIC_LAYER_DEV_HANDOFF.md` addresses *"Incoming engineer(s)
  taking over agentic layer development"*, scoped to `agentic/`, `agent/`,
  `workflow/`, and governance.
- **Source:** `docs/AGENTIC_LAYER_DEV_HANDOFF.md:4-5`; added 2026-02-09, last
  edited 2026-02-16.
- **Owner:** the handoff.
- **Consumers:** n/a.
- **Evidence:** records historical intent to continue agent development. It has
  no status line and nothing marks it current or superseded.
- **Conflict:** with D12 as a repository proposition (§12).
- **Disposition:** UNRESOLVED · **001B:** NO.

### 5.2 Compact records

| ID | Proposition | Source | Ontology | Class. | Consumers | Conflict | Disp. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P02 | Two-class instrument system; every module declares `INSTRUMENT CLASS` | ADR-0009 (Accepted); `ci/check_advisory_boundary.py` | AUTHORITY_BOUNDARY | CURRENT_AUTHORITY | CI; all module headers | — | PRESERVE |
| P09 | PyQt engine sends pack, peak, coherence and wood data to an external API; it references no `SafeDefaults` privacy setting | `analyzer/guidance/engine.py:73-100, 109-197` | AUTHORITY_BOUNDARY | UNKNOWN | Anthropic API | Whether sanctioned is unrecorded | UNRESOLVED |
| P12 | CLI builds OperatorLoop with no `spine_mode` and no adapter, so it runs M1 | `cli/main.py:701` | WORKFLOW_STATE | IMPLEMENTED_BEHAVIOR | `ttp measure` | — | PRESERVE |
| P15 | Stale comment: `decide()` "returns plain dict directives" | `operator_loop.py:161` vs `policy._coerce_directive` | OTHER | CONFLICTING | — | Comment contradicts code | RECONCILE |
| P18 | Moment catalog priority appendix lists six moments | `EVENT_MOMENTS_CATALOG_V1.md:625-636` | ATTENTION_MOMENT | CONFLICTING | — | P17 | RECONCILE |
| P19 | Moment → action: `FIRST_SIGNAL`, `HESITATION`, `CONFIDENCE_CLIMB` → INSPECT; `OVERLOAD`, `FINDING`, `ERROR`, `TRUST_EROSION` → REVIEW; `DECISION_REQUIRED` → DECIDE | `policy.py` (`mapping`) | ATTENTION_MOMENT | IMPLEMENTED_BEHAVIOR | `decide` | — | PRESERVE |
| P20 | Detector thresholds: `CONFIDENCE_CLIMB` ≥ 80% acknowledged over ≥ 5; `TRUST_EROSION` ≥ 60% dismissed or 3+ idle; `OVERLOAD` explicit, 3+ undos, or 4+ toggles | `moments.py:64-222` | ATTENTION_MOMENT | IMPLEMENTED_BEHAVIOR | `detect_moments` | — | PRESERVE |
| P23 | `_build_directive`'s `guidance` parameter is unused | `policy.py:229-269`; dead-code report | USER_GUIDANCE_CONTEXT | IMPLEMENTED_BEHAVIOR | — | — | UNRESOLVED |
| P25 | UWSM rules document: v1.0.0, no status line | `UWSM_UPDATE_RULES_V1.md` | USER_GUIDANCE_CONTEXT | UNKNOWN | code cites it | — | UNRESOLVED |
| P29 | Stage-gated disclosure: rules shown 2 / 4 / 10, actions 2 / 3 / 5; "why it matters" for `FIRST_RUN` only on HARD failures, never for `EXPERT` | `ftue.py:46-70` | PRESENTATION | IMPLEMENTED_BEHAVIOR | message layer | — | PRESERVE |
| P31 | Three identical verdicts in a row suppress explanations; only the verdict and strongest fix remain | `messages.py:70` | PRESENTATION | IMPLEMENTED_BEHAVIOR | message layer | — | PRESERVE |
| P32 | Plain-language FTUE hints per stage (*"Run 'ttp setup' once to lock the right input device"*) | `ftue.py:16-27` | PRESENTATION | IMPLEMENTED_BEHAVIOR | `messages._pick_ftue_hint` | — | PRESERVE |
| P33 | FTUE stage persisted to user config | `core/user_config.update_ftue_from_verdict`; `cli/main.py:519-531, 664-671` | USER_GUIDANCE_CONTEXT | IMPLEMENTED_BEHAVIOR | CLI | — | PRESERVE |
| P37 | CLI guidance is deterministic and template-driven | `agent/messages.py`, `message_spec.py` | PRESENTATION | IMPLEMENTED_BEHAVIOR | `cli/main.py` | — | PRESERVE |
| P41 | Tkinter GUI shows advisory state from spine outputs | `gui/quality_verdict.py:251-410`; `directive_outcomes.py:55`; `directive_history_view.py:13` | PRESENTATION | IMPLEMENTED_BEHAVIOR | `ttp gui` | Source of records per P13 | PRESERVE |
| P42 | `AttentionDirectiveV1` ordered by urgency `INSPECT < REVIEW < DECIDE < INTERVENE` | `analyzer_attention.py` | PRESENTATION | IMPLEMENTED_BEHAVIOR | both GUIs, spine | — | PRESERVE |
| P45 | Audience: *"a measurement instrument toolchain for luthier lab work"* | `README.md:3` | OTHER | CURRENT_AUTHORITY | — | — | PRESERVE |
| P46 | Quickstart assumes `git clone`, Python 3.10+, a USB measurement mic, and "free-free support" | `QUICKSTART.md:7-14` | OTHER | CURRENT_AUTHORITY | — | C1 | PRESERVE |
| P47 | User guide leads with Hz, dB, phase, coherence, dBFS, GPa, Q-factor | `docs/ANALYZER_USER_GUIDE.md:5-31` | OTHER | CURRENT_AUTHORITY | — | C1 | PRESERVE |
| P49 | *"The happy path for first-time users should be one command"* — `ttp quick`, recommended by the design review, is implemented: auto-detect device, capture, `analyze_tap`, print. **It runs no quality gate and no guidance.** | `tap-tone-pi-design-review.md:269`; `cli/main.py:354-441, 1355` | WORKFLOW_STATE | IMPLEMENTED_BEHAVIOR | `ttp quick` | C10: failures on this path produce no verdict or corrective message | PRESERVE |
| P50 | `ToolCapabilityV1` is a portfolio-shared contract (includes `GENERATE_GCODE`, `GENERATE_DXF`) | `tool_capability.py:75` | OTHER | IMPLEMENTED_BEHAVIOR | `capabilities.py` | — | PRESERVE |
| P51 | A shadow record is written per attempt, with policy trace | `spine/shadow_record.py`; `operator_loop.py:641, 692, 749` | OTHER | IMPLEMENTED_BEHAVIOR | Tkinter GUI, CLI render | — | PRESERVE |
| P53 | A "Quality Grade AAA–D" exists, advisory-class; already a capability-matrix finding | `ANALYZER_USER_GUIDE.md:31`; ADR-0009 | OTHER | IMPLEMENTED_BEHAVIOR | — | Owned elsewhere; not adjudicated here | PRESERVE |
| P54 | ADR-0008 (spine wiring) has no status line | `docs/ADR-0008-spine-wiring-architecture.md` | OTHER | UNKNOWN | code cites it | — | UNRESOLVED |
| P55 | Advisory-mode thin slice: *"Ready for implementation"*; implementation status unestablished | `docs/ADVISORY_MODE_THIN_SLICE.md` | OTHER | PROPOSED_DESIGN | — | — | UNRESOLVED |
| P56 | `ttp demo` runs the full analysis pipeline on synthetic audio — *"no hardware required"* | `cli/main.py:328-351, 1371-1384` | WORKFLOW_STATE | IMPLEMENTED_BEHAVIOR | `ttp demo` | — | PRESERVE |
| P57 | `ttp record --agent` runs the quality gate and an agent message with `user_stage` pinned to `"novice"`, bypassing stage inference; `--expert` overrides | `cli/main.py:242-262, 1307-1342` | USER_GUIDANCE_CONTEXT | IMPLEMENTED_BEHAVIOR | `ttp record` | K2 | PRESERVE |

---

## 6. Ontology map

The four state kinds D2 names are distinct in the repository, and stay distinct
here. Presentation and authority are recorded separately because they are not
state.

| Ontology | Repository form | Owner | Values |
| --- | --- | --- | --- |
| Measurement condition | quality rules → `Verdict` | `core/quality_policy.py` | `Q001`–`Q013`; `PASS · WARN · FAIL` |
| Measurement-attempt state | `LoopState` | `workflow/operator_loop.py` | `IDLE … COMPLETED` |
| Procedure state | guided-lab session | `guided_lab/engine.py` | per workflow definition |
| Attention moment | `PRIORITY` | `agentic/spine/moments.py` | eight moments |
| User context — adaptive | UWSM | `agentic/spine/uwsm_*.py` | seven dimensions |
| User context — stage | `UserStage` | `agent/types.py` | four stages |
| Presentation | `AttentionAction`, `ExplanationMode`, stage knobs | contracts; `agent/` | — |
| Authority | `AdvisoryAuthorityV1`; DO-100 boundary | contracts; ADR-0010; DO-100 | — |

**Two findings belong here rather than in the conflicts.** "Workflow state" is
not one thing: the repository has an attempt state machine and a separate
procedure state machine, unconnected. And "user context" is not one thing: an
adaptive preference model and an identity stage coexist, and nothing reads both.

---

## 7. Authority map

| Authority | Status | Governs | Implemented by |
| --- | --- | --- | --- |
| ADR-0009 | **Accepted** | measurement vs decision-support classes | module headers; CI check |
| ADR-0010 | **Accepted** | guidance may not establish truth | `AdvisoryAuthorityV1`; export test |
| ADR-0008 | *no status* | spine wiring | OperatorLoop advisory hook |
| `AGENT_DECISION_POLICY_V1` | v1.0.0, *no status* | modes, policy, FTUE policy | `policy.py` |
| `UWSM_UPDATE_RULES_V1` | v1.0.0, *no status* | UWSM updates | `uwsm_update.py` |
| `EVENT_MOMENTS_CATALOG_V1` | v1.0.0, *no status* | moments | `moments.py` — **priority conflicts** |
| DO-100 | **COMPLETE** per `CURRENT.md`; own header still *"QUEUED / NOT STARTED"* | guided procedures; workflow boundary | `guided_lab/` (PR #16) |
| `ADVISORY_MODE_THIN_SLICE` | *"Ready for implementation"* | advisory mode | unestablished |
| `AGENTIC_LAYER_DEV_HANDOFF` | *no status* | historical handoff | — |

**Only three of the authorities that govern this subsystem carry a status that
makes them current**: ADR-0009 and ADR-0010 (Accepted) and DO-100 (Complete). All
three are boundaries or entry-point principles. Every specification the spine is
built against — decision policy, UWSM rules, moment catalog, spine wiring — is
versioned but unstatused. That is the single largest obstacle to 001B citing any
of them as law.

---

## 8. Consumer census

| Concern | Defined | Consumed by | Surface |
| --- | --- | --- | --- |
| FTUE knobs and hints | `agent/ftue.py` | `messages.py` (via `_pick_ftue_hint`), `measurement_agent.py`, `cli/main.py` (`cfg.ftue`) | CLI |
| `ftue.infer_user_stage` | `agent/ftue.py:88` | **no production caller**; tests only | none |
| `messages.infer_user_stage` | `agent/messages.py:504` | `messages.py:596, 861` | CLI (`measure`) |
| `UserStage` | `agent/types.py` | message layer; PyQt `engine.py:37`, `panel.py:60`; CLI `--expert`; `record` pins `"novice"` | CLI, PyQt |
| Moments | `spine/moments.py` | `operator_loop.py:690` | CLI |
| UWSM | `spine/uwsm_*.py` | `operator_loop.py` (load/decay/update/persist); `policy.decide` (3 of 7 dims) | CLI |
| OperatorLoop | `workflow/operator_loop.py` | `cli/main.py:701`; `grant_readiness/inventory.py` | CLI |
| `policy.decide` | `spine/policy.py` | `operator_loop.py:716` | CLI |
| View adapter / M2 | `spine/view_adapter.py` | `operator_loop.py` only — **no production implementation** | none |
| Agent messages (integrated) | `agent/messages.py` | `cli/main.py:243` (`record`), `528`, `711` (`measure`); `render.py` | CLI |
| Agent messages (standalone) | `agent/measurement_agent.py`, `selector.py` | **none outside the package** | none |
| Attention directives | `contracts/analyzer_attention.py` | `policy.py`; PyQt `engine.py`, `panel.py` | CLI, PyQt |
| Directive history / shadow records | `spine/directive_history.py`, `shadow_record.py` | Tkinter `quality_verdict.py`, `directive_outcomes.py`, `directive_history_view.py` | Tkinter |
| Quality conditions | `core/quality_policy.py` | `quality_gate`; OperatorLoop; `cmd_record`; Tkinter `measurement_flow`; message layer — **not** `ttp quick` | CLI, Tkinter |
| Guided laboratory | `guided_lab/` | `cli/main.py:1209`; `grant_readiness` | CLI |
| PyQt Claude engine | `analyzer/guidance/engine.py` | `panel.py` | PyQt |

**GUI integration:** the PyQt Analyzer consumes attention directives and
`UserStage`, not OperatorLoop, moments, UWSM, or agent messages. The Tkinter GUI
consumes spine *outputs* and the quality policy, not OperatorLoop.
**CLI integration:** `ttp measure` is the only surface where the full spine runs.

**Tests covering the subsystem — 34 files, 525 tests, all passing:**
`test_advisory_authority_contract`, `test_advisory_boundary`,
`test_advisory_boundary_full_coverage`, `test_agent_fatigue`, `test_agent_ftue`,
`test_agent_integration`, `test_agent_message_spec`, `test_agent_messages`,
`test_agent_render`, `test_agent_selector`, `test_agent_types`,
`test_agentic_contracts`, `test_analyzer_guidance`, `test_cli_agent_directives`,
`test_cli_agent_wiring`, `test_cli_list_directive_events`,
`test_cli_measure_agent_output`, `test_cli_measure_ftue_wiring`,
`test_directive_accessor_compat`, `test_directive_history_loader`,
`test_event_emission_operator_loop`, `test_gui_directive_history_view`,
`test_gui_directive_outcomes`, `test_gui_show_directive_history_persistence`,
`test_guidance_language_guard`, `test_guidance_not_in_measurement_exports`,
`test_moments_engine_v1`, `test_operator_loop_view_adapter`,
`test_policy_engine_v1`, `test_shadow_record_policy_trace`,
`test_spine_shadow_hook`, `test_user_config_ftue`, `test_uwsm_persistence`,
`test_workflow_operator_loop`.

---

## 9. Conflicts

Every contradiction found. None was resolved.

| ID | Conflict | Between | Record |
| --- | --- | --- | --- |
| K1 | Moment priority: eight in code, six in the catalog's appendix | `moments.py:26` vs `EVENT_MOMENTS_CATALOG_V1.md:625-636` | P17, P18 |
| K2 | Three stage rules: two implemented with different thresholds, a third documented; one live path pins `"novice"` | `ftue.py:88-115` vs `messages.py:504-517` vs `AGENTIC_LAYER_DEV_HANDOFF.md:539`; `cli/main.py:257` | P27, P57 |
| K3 | Explanation-mode `COMPACT` at two vs three sessions | `selector.py:39-58` vs `messages.py:51-67` | P30 |
| K4 | DO-100's own header says not started; `CURRENT.md` records it complete | `DO-100:3-5` vs `CURRENT.md:511-532, 676` | P04 |
| K5 | UWSM audit written outside every allowed advisory location | `operator_loop.py:204` vs `test_guidance_not_in_measurement_exports.py:7-8, 38-43` | P07 |
| K6 | `HARD` "cannot override" vs two reachable override paths | `quality_policy.py:31` vs `operator_loop.py:768`, `cli/main.py:608`, `gui/measurement_flow.py:238` | P08 |
| K7 | Comment says `decide()` returns dicts; code guarantees directives | `operator_loop.py:161` vs `policy._coerce_directive` | P15 |
| K8 | D12's premise vs a live Claude-backed engine and an agent-development handoff | handoff D12 vs `analyzer/guidance/engine.py`, `AGENTIC_LAYER_DEV_HANDOFF.md:4` | §12 |
| K9 | **Latent implementation finding.** A dead GUI path fabricates a wolf result with `MagicMock` and `confidence = 0.8`, importing a module that does not exist, swallowed by `except Exception: pass` | `analyzer/guidance/engine.py` vs ADR-0010 | P40 |

**K9 is recorded here and nowhere else**, per ruling: no backlog artifact was
created and nothing was fixed. It is listed as blocker B6 so that it cannot be
lost between orders.

**A tension that is not a conflict:** the handoff's model and the repository's
architecture. That is recorded in §4 and P39 as the repository's actual shape,
not as a defect in either.

---

## 10. The fifteen questions

**Q1 — Who is the assumed user?** A *guitar builder* doing luthier lab work
(`README.md:3`; DO-100 *"The Guided Digital Laboratory for Guitar Builders"*).
There is **no competency definition**. Two partial ones exist and do not agree:
the quickstart and user guide assume a technically capable operator (git,
Python, a measurement mic, modal vocabulary); DO-100 says the builder should not
have to begin by choosing an analyzer, model, FFT mode or calculator. FTUE's
"first-time user" means first-time *user of the tool*, measured in sessions and
passes — not someone lacking acoustics knowledge.

**Q2 — Is MVS already an architectural concept?** No — not by name, and not as
one concept. It is distributed across FTUE and `UserStage` (who the user is),
DO-100 (how they should enter), the quality messages (what they are told on
failure), and the spine (when they are prompted). Nothing connects these.

**Q3 — What owns operator progression?** Three things, independently. OperatorLoop
owns measurement-attempt state (CLI only). The guided laboratory owns procedure
state (*"authoritative only for procedure state"*). FTUE owns user-competence
stage. None depends on another.

**Q4 — What owns measurement truth?** `core/analysis.analyze_tap` for values;
`core/quality_gate.check_quality` under `core/quality_policy` for acceptability;
classified `MEASUREMENT` by ADR-0009 and protected by ADR-0010.

**Q5 — What may guidance change?**

| Target | Guidance may change it? | Basis |
| --- | --- | --- |
| Presentation | **yes** | directives, explanation mode, stage knobs |
| Explanation depth | **yes** | `ExplanationMode`; `guidance_density` gate; stage |
| Next-step wording | **yes** | directive text; FTUE hints; rule messages |
| Workflow progression | **no** | guidance emits requests; humans advance and override |
| Acquisition | **no** | no capability or command expresses it; DO-100 forbids it without explicit user action |
| Measurement parameters | **no** | as above |
| Quality status | **no** | ADR-0010; `can_modify_measurement = False` |
| Evidence | **no** | ADR-0010; export test |
| Persistence | **advisory state only** | UWSM to user config; audit at session root (K5); FTUE stage to user config |

**Q6 — What are moments?** Attention moments: named patterns in user-interaction
and analysis events, not measurement states (P16). Eight exist; priority is
contested (K1).

**Q7 — What is UWSM?** A per-user adaptive guidance-policy state with seven
decaying, hysteretic dimensions (P21). It may influence directive count,
proactivity, and summary depth only — and only three of its dimensions reach
anything (P22). It cannot reach evidence or quality (P24).

**Q8 — Is progressive competence represented?** Two mechanisms, neither a
competence model. UWSM adapts over time with decay and hysteresis, but it tracks
guidance preference, not skill. `UserStage` advances `FIRST_RUN → NOVICE →
REGULAR` automatically from usage, but `EXPERT` is declared (P28), and the two
inference functions disagree (K2).

**Q9 — Deterministic or agentic?**

| Behavior | Kind |
| --- | --- |
| Spine policy, moments, UWSM | deterministic |
| CLI agent messages, FTUE hints, quality messages | deterministic |
| Guided laboratory | deterministic (*"no model"*) |
| Tkinter advisory display | presentation-only |
| PyQt guidance engine | **agentic** when a key is set; deterministic fallback otherwise |
| M2 view commands | not wired |
| Standalone message stack | not wired |
| Wolf-guidance handler | not wired — fails silently |

**Q10 — What is user-facing today?** `ttp setup` (*"run first!"*), `ttp demo`,
`ttp quick`, `ttp record [--agent] [--expert]`, `ttp live`, `ttp measure [--agent]
[--expert]`, `ttp guided-lab …`, `ttp gui` (Tkinter), and the PyQt6 Analyzer.
Of these, only `measure` runs the spine, and only `record` and `measure` show
agent messages. Architecture beyond those — M2 actuation, the standalone stack,
`ftue.infer_user_stage`, four UWSM dimensions, the wolf handler — does not reach a
user.

**Q11 — Can operation succeed without technical vocabulary?** The only
observation says no, for the PyQt Analyzer as of 2026-02-18 (P48). The quickstart
requires git, Python and "free-free support". The quality messages and directive
titles are plain (*"Stop and check"*, *"Reduce microphone gain and retry"*).
Current state of the observed issues: unknown.

**Q12 — What happens on failure?**

| Failure | Handling |
| --- | --- |
| Clipping / silence / no peaks / low confidence | `HARD` rule → `FAILED`, plain corrective message; retry or human override with reason |
| Near-clipping / quiet / marginal / few peaks | `SOFT` → `WARNED`, may proceed |
| Repeated identical failure | explanations suppressed after three; `COMPACT` mode |
| Hesitation | `HESITATION` → INSPECT directive (suppressed for `user_led`) |
| Overload | `OVERLOAD` → REVIEW; directive cap drops to 1 at high load |
| Decision boundary | `DECISION_REQUIRED` → DECIDE |
| Loss of trust | `TRUST_EROSION` → REVIEW |
| Analysis failure | `ERROR` moment → REVIEW |
| Any failure under `ttp quick` | **no quality gate** — results print without a verdict or corrective message (P49) |
| GUI operation failing silently | **observed unhandled** (P48); current state unknown |

**Q13 — Are disclosure levels supported?** Progressive disclosure is implemented
along **two** axes, neither of them DO / UNDERSTAND / INSPECT: user stage (rule
and action counts, "why it matters", metrics) and rule familiarity (`FULL`,
`SHORT`, `COMPACT`), plus a UWSM summary-only gate. DO / UNDERSTAND / INSPECT as
named levels is **`PROPOSED_DESIGN`**. The closest existing analogue to INSPECT —
raw metrics — is available only to declared experts.

**Q14 — Are measurement and representation invariant?** Structurally, yes on the
paths examined: nothing a representation choice sets reaches a verdict or a
measured value, every directive carries a no-truth authority, and DO-100 names
the separation. Tested only partly: the export test protects measurement
artifacts on fixtures. No test examined asserts that changing stage or
explanation mode leaves a verdict unchanged.

**Q15 — What does "we are not building the agent" mean?** See §12. Four
separable facts: agent architecture exists; agent implementation exists; one GUI
path is live, conditionally; this increment authorizes no further agent
development.

---

## 11. Candidate propositions

| ID | Proposition | Disposition | Basis |
| --- | --- | --- | --- |
| C1 | Operable without acoustics / signal-processing / lab expertise | **PARTIALLY_SUPPORTED** | DO-100 — current authority — states it for the guided entry point (*"without requiring the user to begin by selecting an analyzer, scientific model, FFT mode, or calculator"*; *"Never ask for a scientific parameter until the workflow has explained why it is needed"*). The design review states a first-time happy path (*"should be one command"*) and `ttp quick`, `ttp demo` and `ttp setup` implement one. It is not stated as a product-wide requirement; the quickstart and user guide assume technical skill; the one observed session contradicts it as current reality; and the zero-config path runs no quality gate. |
| C2 | Sophomore comprehension as the minimum target | **NOT_WITNESSED** | "Sophomore" and any reading-level target appear nowhere. |
| C3 | MVS is a guaranteed floor, not a permanent novice identity | **NOT_SUPPORTED** | The repository models the user as an **identity stage** (`UserStage`), and no guaranteed-floor construct exists outside DO-100's entry principle. One clause holds: the identity is not permanent — `FIRST_RUN → NOVICE → REGULAR` advances automatically. But the top stage is declared, not earned (P28), disclosure is gated on identity, and the stage is computed two ways (K2). The repository's ontology and this proposition diverge; that divergence is the finding. |
| C4 | DO → UNDERSTAND → INSPECT | **PARTIALLY_SUPPORTED** | Progressive disclosure is real and deliberate (FTUE, `ExplanationMode`, stage knobs, `guidance_density` gate, CHANGELOG). The three named levels are absent — `PROPOSED_DESIGN`. `representation_preference` anticipated representational adaptation and was never wired (P22). |
| C5 | Representation depth cannot change measurement, protocol state or evidence | **PARTIALLY_SUPPORTED** | Structurally true on every path examined; ADR-0010 and DO-100 state the separation. Not directly tested under representation change; advisory audit placement contested (K5). |
| C6 | Guidance cannot manufacture measurement truth | **SUPPORTED** | ADR-0010 (Accepted); default-deny authority flags; every spine directive stamped; DO-100 boundary; export test. One latent exception, unreachable today (K9). |
| C7 | OperatorLoop is the integration point between authoritative state and guidance | **PARTIALLY_SUPPORTED** | It is the integration point for `ttp measure`. `ttp record`, `ttp quick`, the PyQt Analyzer, the Tkinter measurement flow and the guided laboratory all bypass it — the last deliberately (`CURRENT.md` defers a guided-lab/workflow adapter to a later order). No authority designates it as *the* integration point. |
| C8 | Not every interaction requires agentic reasoning | **SUPPORTED** | Every system except the PyQt engine is deterministic, and that engine has a deterministic fallback. The guided laboratory declares *"no model"*. |
| C9 | UWSM may affect assistance/presentation but not evidence or quality | **SUPPORTED** | Structural (P24) and under ADR-0010. The UWSM rules document does not itself state the limit. |
| C10 | Recovery from supported failures is part of usability | **PARTIALLY_SUPPORTED** | Recovery mechanics are implemented throughout (Q12): corrective messages, retry, override with reason, streak suppression, moment-driven prompts. No source states recovery as a usability requirement; the observed session found failures surfacing silently; and the zero-config path offers no recovery guidance because it runs no quality gate (P49). |

---

## 12. D12 — recorded in two layers

**As a repository proposition, "we are not building the agent" is
`NOT_WITNESSED`.** No tracked file says it. The repository's own evidence runs the
other way: `AGENTIC_LAYER_DEV_HANDOFF.md` (February) is written for engineers
*taking over* agentic development, and the PyQt Analyzer's guidance engine
(March; reformatted but behaviorally unchanged since) makes live Claude calls. The repository therefore
still contains active agentic behavior.

**As the current scope ruling for MVS-UX-001A, D12 is in force.** This increment
did not expand, reactivate, redesign, or repair agent behavior.

**The Claude engine is not labelled a defect** because of that ruling. A scope
ruling about what this work may do is not a finding about what the repository
should contain. The accurate statement:

> Repository history does not support "we are not building the agent" as an
> architectural fact. Current execution authority still freezes agent
> development during 001A.

Q15, in the four parts it has to be answered in:

| Fact | State |
| --- | --- |
| Agent architecture exists | **yes** — contracts, spine, three ADRs, four specifications |
| Agent implementation exists | **yes** — spine, message layer, FTUE, UWSM; 525 tests |
| A user-facing agentic path is live | **one, conditionally** — the PyQt engine, when `ANTHROPIC_API_KEY` is set |
| This increment authorizes further agent development | **no** |

---

## 13. Implementation-versus-authority gaps

**Documented but unimplemented:** DO / UNDERSTAND / INSPECT (not even
documented — a handoff proposal only); DO-100's explicit measurement adapters;
the advisory-mode thin slice (status unestablished).

**Implemented but not authoritative:** the entire spine — moments, UWSM, decision
policy, spine wiring — rests on specifications with no status line. OperatorLoop
has no designating authority. `UserStage` and FTUE have none beyond a CHANGELOG
entry.

**Authoritative and implemented:** ADR-0009 and ADR-0010, both boundary
authorities; DO-100, for the guided laboratory.

**Implemented and unreachable:** M2 actuation; the standalone message stack,
including `ftue.infer_user_stage`; four UWSM dimensions; the `guidance` parameter
of `_build_directive`; the wolf-guidance handler.

**Experimental:** M2 first-time One-Trace onboarding.

**Unknown:** whether the 2026-02-18 first-time-user findings were resolved;
whether sending analysis data to an external API is sanctioned; whether any
authority superseded the agentic development handoff.

---

## 14. Not-witnessed claims

Claims made in the handoff that the repository does not contain:

| Claim | Status |
| --- | --- |
| "MVS" as a term or concept | not witnessed |
| "MVI" | not witnessed as a term |
| Sophomore / reading-level target | not witnessed |
| "We are not building the agent" | not witnessed (§12) |
| A six-moment priority as current code | not witnessed — six is the catalog appendix; code has eight |
| OperatorLoop as the sole integration point | not witnessed |
| A guaranteed usability floor as a global requirement | not witnessed — DO-100 states it for one entry point |
| DO / UNDERSTAND / INSPECT | not witnessed |

---

## 15. Architecture matrix

| Concern | Current owner | Ontology | Implemented? | Consumed? | Authority status | Conflict? | 001B disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FTUE | `agent/ftue.py` | presentation / user stage | yes | yes — CLI via `messages.py` | none beyond CHANGELOG | K2, K3 | CONDITIONAL — B2, B3 |
| `UserStage` | `agent/types.py` | user context (identity) | yes | yes — CLI, PyQt | none | diverges from C3 | CONDITIONAL — B10 |
| `FIRST_SIGNAL` | `spine/moments.py` | attention moment | yes | yes — OperatorLoop | catalog v1.0.0, no status | K1 | CONDITIONAL — B1 |
| `CLIPPED` (`Q001`) | `core/quality_policy.py` | measurement condition | yes — HARD | yes — every measurement surface | ADR-0009 class | K6 | YES |
| UWSM | `spine/uwsm_*.py` | user context (adaptive) | yes | partly — 3 of 7 dimensions | rules v1.0.0, no status | K5 | CONDITIONAL — B7, B11 |
| OperatorLoop | `workflow/operator_loop.py` | measurement-attempt state; orchestration | yes | yes — CLI only | none designating | K6, K7 | YES, as a CLI integration point |
| Guided laboratory | `guided_lab/` | procedure state | yes | yes — CLI | DO-100, Complete (header stale) | K4 | YES; scope per B4 |
| Agent messages | `agent/messages.py` | guidance (deterministic) | yes | yes — CLI | none | K2, K3 | CONDITIONAL — B2, B3 |
| Attention directives | `contracts/analyzer_attention.py` | presentation | yes | yes — CLI, PyQt | contract; ADR-0010 stamp | — | YES |
| PyQt GUI guidance | `analyzer/guidance/` | guidance (agentic + fallback) | yes | yes — PyQt | ADR-0009 advisory class | K8, K9 | CONDITIONAL — B6, B9 |
| Tkinter GUI | `tap_tone_pi/gui/` | presentation; own measurement flow | yes | yes — `ttp gui` | none | K6 | CONDITIONAL — B9 |

---

## 16. Open questions

- **O1.** Which stage-inference thresholds are intended? (K2)
- **O2.** Is `selector.py` superseded, or is the divergence intended? (K3)
- **O3.** Do Tkinter GUI captures produce the shadow records the Tkinter advisory
  panel reads, given that they bypass OperatorLoop? (P13) The same question
  applies to `ttp record --agent-directives`, which prints *"from spine shadow
  outputs (if available)"* (`cli/main.py:1331-1335`) on a path that does not run
  the spine. Unverified at runtime.
- **O4.** Were the 2026-02-18 first-time-user findings resolved?
- **O5.** Is sending analysis data to the Anthropic API sanctioned? (P09)
- **O6.** Is the agentic development handoff current, superseded, or historical?
  (P52)
- **O7.** Does "cannot override" mean the verdict, the workflow, or both? (K6)

---

## 17. Recommendations for 001B

These are the obstacles to synthesizing a contract, not a design for one.

### Blockers

| ID | Blocker |
| --- | --- |
| B1 | Reconcile moment priority (K1) before any contract cites it. |
| B2 | Choose one stage-inference implementation (K2). |
| B3 | Choose one explanation-mode implementation (K3). |
| B4 | Decide whether DO-100's entry principles govern the guided laboratory only or every surface. DO-100 is current authority and the only source stating a usability floor, but it is written for one entry point. (Its stale header, K4, is a trivial reconcile.) |
| B5 | Give the spine's specifications a status. A contract cannot cite versioned, unstatused documents as law. |
| B6 | Disposition the wolf-guidance handler (K9) — packet-only here, per ruling. |
| B7 | Decide whether UWSM audits belong at the session root (K5). |
| B8 | Say what "cannot override" protects (K6). |
| B9 | **Decide whether the contract spans every surface or one.** Seven measurement-relevant CLI entry points and two GUIs exist, with five guidance systems among them; a contract written against OperatorLoop alone would cover `ttp measure` and silently exclude the rest — including `ttp quick`, the path the design review built for first-time users. |
| B10 | **Decide between the repository's identity model and the floor model** (C3). This is a product decision, not a reconciliation. |
| B11 | Decide what, if anything, `representation_preference` is for — before designing disclosure levels on top of FTUE while UWSM already holds an unused preference for the same thing. |

### Eligible now

Propositions 001B may cite without further work: **P01**, **P02**, **P03**,
**P04** (scope per B4), **P05** (structural action surface, noting the question
in its record), **P06**, **P10**, **P11**, **P14**, **P16** (as an ontology),
**P21**, **P24**, **P28**, **P35**, **P39** (as the architecture 001B inherits),
**P43**, **P44**, **P48** (as evidence), **P49**, **P56**.

---

## 18. Stop-gate disposition

MVS-UX-001A ends with adjudicated evidence, not a new UX architecture.

The acceptance statement holds: from the tracked repository, this packet
distinguishes what the handoff's "MVS" corresponds to (§0), what is implemented
(§5), what is merely proposed (P55; DO/UNDERSTAND/INSPECT), what conflicts
(§9), what is unused (§13), and what remains unknown (§13, §16) — and changes none
of it.

**Not begun:** MVS-UX-001B, `MVS_UX_CONTRACT_V1`, UI mockups, agent
implementation, OperatorLoop or UWSM changes, new moments or quality states,
progressive-disclosure implementation, novice usability trials.
