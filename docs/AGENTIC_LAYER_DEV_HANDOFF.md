# Agentic Layer — Developer Handoff

**Date:** 2026-02-08
**Audience:** Incoming engineer(s) taking over agentic layer development
**Scope:** Everything under `tap_tone_pi/agentic/`, `tap_tone_pi/agent/`, `tap_tone_pi/workflow/`, and associated governance docs + tests

---

## 0. 30-Second Orientation

Tap Tone Pi is a **measurement instrument** — it outputs facts (FFT peaks, coherence, phase, RMS), never design advice. The agentic layer sits *on top of* the measurement core and has **one job**: help operators understand quality verdicts and navigate the measurement workflow — without ever altering measurement truth.

There are three subsystems, layered bottom-up:

```
┌─────────────────────────────────────────────────────────┐
│              Agent Layer (Presentation)                  │
│   tap_tone_pi/agent/                                    │
│   Messages, selectors, FTUE, renderers                  │
├─────────────────────────────────────────────────────────┤
│              Spine (Orchestration Engine)                │
│   tap_tone_pi/agentic/spine/                            │
│   Moments detection, policy decisions, UWSM, replay    │
├─────────────────────────────────────────────────────────┤
│              Contracts (Cross-Repo Thin Waist)          │
│   tap_tone_pi/agentic/contracts/                        │
│   ToolCapabilityV1, AttentionDirectiveV1, AgentEventV1  │
├─────────────────────────────────────────────────────────┤
│              Workflow (State Machine)                    │
│   tap_tone_pi/workflow/                                 │
│   OperatorLoop, Attempt tracking                        │
└─────────────────────────────────────────────────────────┘
```

The contracts mirror identical types in the **luthiers-toolbox** repo (`services/api/app/agentic/`). Both repos serialize to the same JSON — tap_tone_pi uses stdlib `dataclasses` (zero external deps), the toolbox uses Pydantic.

---

## 1. Contracts — The Cross-Repo Thin Waist

**Location:** `tap_tone_pi/agentic/contracts/`
**Mirror:** `luthiers-toolbox/services/api/app/agentic/contracts/`
**Governance doc:** [AGENTIC_CONTRACTS_ENGINEER_HANDOFF.md](AGENTIC_CONTRACTS_ENGINEER_HANDOFF.md)

### 1.1 Three Core Contracts

| Contract | File | Purpose |
|----------|------|---------|
| `ToolCapabilityV1` | `contracts/tool_capability.py` | Declares what a tool *can* do (manifest, not execution) |
| `AttentionDirectiveV1` | `contracts/analyzer_attention.py` | How the agent guides user focus without touching internals |
| `AgentEventV1` | `contracts/event_emission.py` | Unified event vocabulary across all repos |

**Critical invariant:** The agent can only **point, highlight, and reset view**. It cannot change measurement parameters, start/stop acquisition, export data, or persist analyzer state.

### 1.2 ToolCapabilityV1

Declares what a tool is capable of so the agent can reason about *possibility* without knowing *implementation*.

```python
# tap_tone_pi/agentic/capabilities.py
TAP_TONE_ANALYZER = ToolCapabilityV1(
    tool_id="tap_tone_analyzer",
    version="2.0.0",
    display_name="Tap Tone Analyzer",
    actions=[
        CapabilityAction.ANALYZE_AUDIO,
        CapabilityAction.ANALYZE_SPECTRUM,
        CapabilityAction.GENERATE_REPORT,
        CapabilityAction.VALIDATE_SCHEMA,
    ],
    input_schemas=["tap_tone_bundle_v1", "audio_wav"],
    output_schemas=["wolf_candidates_v1", "ods_snapshot_v1", "viewer_pack_v1"],
    safe_defaults=SafeDefaults(
        redaction_layer=2,
        dry_run=False,
        require_confirmation=False,
        timeout_seconds=120,
    ),
    source_repo="tap_tone_pi",
)
```

Four capabilities are declared: `TAP_TONE_ANALYZER`, `WOLF_DETECTOR`, `ODS_ANALYZER`, `CHLADNI_ANALYZER`. Each has explicit `SafeDefaults` with timeouts (30–120s) and max output sizes (up to 50MB for viewer packs).

`CapabilityAction` is a **closed vocabulary** — 12 actions across 4 categories:

| Category | Actions |
|----------|---------|
| Analysis (read-only) | `ANALYZE_AUDIO`, `ANALYZE_GEOMETRY`, `ANALYZE_TOOLPATH`, `ANALYZE_SPECTRUM` |
| Generation (creates artifacts) | `GENERATE_REPORT`, `GENERATE_GCODE`, `GENERATE_DXF`, `GENERATE_PREVIEW` |
| Validation (conformance) | `VALIDATE_SCHEMA`, `VALIDATE_FEASIBILITY`, `VALIDATE_SAFETY` |
| Transformation (modifies data) | `TRANSFORM_NORMALIZE`, `TRANSFORM_REDACT`, `TRANSFORM_AGGREGATE` |

### 1.3 AttentionDirectiveV1

Guides user focus. Actions are ordered by urgency:

```python
class AttentionAction(str, Enum):
    INSPECT = "inspect"       # Low urgency — look when you can
    REVIEW = "review"         # Medium — please look soon
    COMPARE = "compare"       # Medium — compare two things
    DECIDE = "decide"         # High — make a choice
    CONFIRM = "confirm"       # High — approve or reject
    INTERVENE = "intervene"   # Critical — stop and fix
    ABORT = "abort"           # Critical — stop everything
```

Each directive carries: `directive_id`, `action`, `summary`, `detail`, `focus` (`FocusTarget` with `target_type`, `target_id`, `highlight_region`), `urgency` (0–1), `confidence` (0–1), `evidence_refs` (traceability to artifacts), `source_tool`, dismissal rules (`auto_dismiss_after_seconds`, `persist_across_views`, `max_show_count`).

### 1.4 AgentEventV1

Unified event vocabulary — 20 event types across 6 categories:

| Category | Events |
|----------|--------|
| Analysis lifecycle | `ANALYSIS_STARTED`, `ANALYSIS_PROGRESS`, `ANALYSIS_COMPLETED`, `ANALYSIS_FAILED` |
| Artifacts | `ARTIFACT_CREATED`, `ARTIFACT_VALIDATED`, `ARTIFACT_REJECTED`, `ARTIFACT_PROMOTED` |
| Decisions | `DECISION_REQUIRED`, `DECISION_MADE`, `DECISION_DEFERRED` |
| Attention | `ATTENTION_REQUESTED`, `ATTENTION_ACKNOWLEDGED`, `ATTENTION_DISMISSED` |
| User | `USER_ACTION`, `USER_FEEDBACK`, `USER_PREFERENCE_UPDATED` |
| System | `SYSTEM_HEALTH`, `SYSTEM_ERROR`, `SYSTEM_CONFIG_CHANGED` |

Every event carries a `privacy_layer` (0–5) that controls retention:

| Layer | Retention | Content |
|-------|-----------|---------|
| 0 | Ephemeral | Raw events, UWSM signals |
| 1 | Session | Session-scoped aggregates |
| 2 | 30 days | Analysis results, artifacts |
| 3 | 1 year | Anonymized metrics |
| 4 | Indefinite | Aggregate statistics |
| 5 | Cohort-only | No individual data |

**Important rule:** No repo emits "confusion," "expertise," or "intent." Only observable actions. Interpretation lives *above* this layer.

### 1.5 Cross-Repo Compatibility

| Aspect | tap_tone_pi | luthiers-toolbox |
|--------|-------------|------------------|
| Base class | stdlib `dataclasses` | Pydantic `BaseModel` |
| Validation | None (lightweight) | Pydantic validators |
| Serialization | `.to_dict()` | `.model_dump()` |
| Dependencies | Zero external deps | pydantic required |
| UWSM | Not included | ✅ Included (`contracts/uwsm.py`) |

Both serialize to **identical JSON format** — cross-repo compatibility is verified by tests.

### 1.6 Event Emission Utilities

**Location:** `tap_tone_pi/agentic/events.py` (276 lines)

Convenience emitters wrap `AgentEventV1` construction:

```python
from tap_tone_pi.agentic import emit_analysis_completed

event = emit_analysis_completed(
    component="wolf_detector",
    run_id="run_abc123",
    artifacts_created=["wolf_candidates.json", "ods_snapshot.json"],
    metrics={"peak_count": 12, "max_confidence": 0.87},
)
```

Available convenience emitters: `emit_analysis_started()`, `emit_analysis_completed()`, `emit_analysis_failed()`, `emit_attention_requested()`. Also includes `create_wolf_tone_directive()` for wolf-finding directives.

---

## 2. Spine — The Orchestration Engine

**Location:** `tap_tone_pi/agentic/spine/`
**Governance docs:** [AGENT_DECISION_POLICY_V1.md](AGENT_DECISION_POLICY_V1.md), [EVENT_MOMENTS_CATALOG_V1.md](EVENT_MOMENTS_CATALOG_V1.md), [UWSM_UPDATE_RULES_V1.md](UWSM_UPDATE_RULES_V1.md), [AGENTIC_SPINE_ARCHITECTURE_ONEPAGER.md](AGENTIC_SPINE_ARCHITECTURE_ONEPAGER.md)

The spine is a deterministic 5-step pipeline:

```
Ingest & Normalize → Detect Moments → Choose Intervention → Apply UWSM Gates → Emit Output
```

### 2.1 Moment Detection Engine

**File:** `tap_tone_pi/agentic/spine/moments.py` (~170 lines)
**Catalog:** [EVENT_MOMENTS_CATALOG_V1.md](EVENT_MOMENTS_CATALOG_V1.md)

Moments are named patterns detected from event streams. The engine returns the **single highest-priority** moment (not a list).

**Priority map (lower number = higher priority):**

| Priority | Moment | Trigger |
|----------|--------|---------|
| 1 | `MOMENT_ERROR` | `analysis_failed` or `system_error` events |
| 2 | `MOMENT_OVERLOAD` | `user_feedback` "too_much", 3+ undos, or rapid open/close |
| 3 | `MOMENT_DECISION_REQUIRED` | `decision_required` event |
| 4 | `MOMENT_FINDING` | `attention_requested` + high-confidence artifact |
| 5 | `MOMENT_HESITATION` | `idle_timeout` or 2+ hovers (suppressed by `parameter_changed`) |
| 6 | `MOMENT_FIRST_SIGNAL` | `view_rendered` or `analysis_completed` |

```python
# Core API
from tap_tone_pi.agentic.spine import detect_moments

result = detect_moments(events)
# Returns: {"moment": "MOMENT_FINDING", "confidence": 0.87,
#           "trigger_events": [...]}
# Or None if no moment detected
```

The full catalog (in the governance doc) defines 7 moment types, including `CONFIDENCE_CLIMB` (MOM-004), `TRUST_EROSION` (MOM-005), `WORKFLOW_SHIFT` (MOM-006), and `MASTERY_PLATEAU` (MOM-007) — these are specified but not all implemented in the current spine code.

**Hysteresis rules per moment:**

| Moment | Cooldown | Max/Session | Max/Day |
|--------|----------|-------------|---------|
| FIRST_SIGNAL | N/A (once per tool) | 1 per tool | N/A |
| HESITATION | 60 seconds | 10 | 30 |
| OVERLOAD | 5 minutes | 3 | 10 |
| CONFIDENCE_CLIMB | 30 minutes | 5 | 15 |
| TRUST_EROSION | 10 minutes | 3 | 5 |
| WORKFLOW_SHIFT | 24 hours | 1 | 1 |
| MASTERY_PLATEAU | 7 days | 1 per tool | N/A |

### 2.2 Policy Engine (Decision Pipeline)

**File:** `tap_tone_pi/agentic/spine/policy.py` (~170 lines)
**Governance doc:** [AGENT_DECISION_POLICY_V1.md](AGENT_DECISION_POLICY_V1.md)

The policy engine maps moments to attention actions, gated by **three operating modes**:

| Mode | ID | Description | Allowed Outputs |
|------|----|-------------|----------------|
| **Shadow** | `M0` | Observe only, log decisions | Diagnostic `AgentEventV1` only (`would_have_emitted`) |
| **Advisory** | `M1` | Suggest actions, user decides | `AttentionDirectiveV1` |
| **Actuated** | `M2` | Can adjust analyzer view (opt-in) | Directive + analyzer view commands |

**Default moment → intervention mapping:**

| Moment | Default Action | Rationale |
|--------|----------------|-----------|
| `MOMENT_FIRST_SIGNAL` | `INSPECT` | Teach "one panel, one trace" |
| `MOMENT_HESITATION` | `INSPECT` | Offer single next micro-action |
| `MOMENT_OVERLOAD` | `REVIEW` | Reduce options, reset view |
| `MOMENT_DECISION_REQUIRED` | `DECIDE` | Present 2–3 options max |
| `MOMENT_FINDING` | `REVIEW` | "Potential wolf tone at X Hz" |
| `MOMENT_ERROR` | `REVIEW` | Summarize + recovery action |

```python
# Core API
from tap_tone_pi.agentic.spine import decide

result = decide(
    moment="MOMENT_FINDING",
    uwsm=uwsm_state,
    mode="M1",            # Advisory
    capability=analyzer,  # ToolCapabilityV1
    context={},
)
# Returns: {"directive": AttentionDirectiveV1, "commands": [...]}
```

**UWSM gates applied by the policy engine:**

1. **Initiative gate:** If `initiative_tolerance` ≤ 0.3 (`user_led`), proactive suggestions are suppressed
2. **Guidance gate:** If `guidance_density` is `very_low` or `low`, detail is stripped from directives
3. **Cognitive load gate:** If `cognitive_load_sensitivity` ≥ 0.7, max 1 simultaneous directive

**Verbosity levels controlled by guidance density:**

| Level | Template |
|-------|----------|
| `summary_only` | `"{summary}"` |
| `summary_plus_hint` | `"{summary}\n\nTry: {hint}"` |
| `full_explanation` | `"{summary}\n\n{detail}\n\nWhy it matters: {why}\n\nTry: {hint}"` |

**M2 FTUE policy:** For first-time users in actuated mode, the engine emits `hide_all_except(primary_panel)` + `focus_trace(primary_trace)` commands to simplify the view.

### 2.3 UWSM Update Engine

**File:** `tap_tone_pi/agentic/spine/uwsm_update.py` (388 lines)
**Governance doc:** [UWSM_UPDATE_RULES_V1.md](UWSM_UPDATE_RULES_V1.md)

The User Working Style Model (UWSM) tracks 7 preference dimensions:

| Dimension | Range | Semantic Interpretation |
|-----------|-------|------------------------|
| `guidance_density` | 0–1 | 0 = "stay light", 1 = "guide me" |
| `initiative_tolerance` | 0–1 | 0–0.3 = user-led, 0.3–0.7 = shared, 0.7–1.0 = agent-led |
| `cognitive_load_sensitivity` | 0–1 | 0 = handles complexity, 1 = easily overwhelmed |
| `exploration_style` | enum | `deep_focus`, `iterative`, `dabble` |
| `risk_posture` | enum | `cautious`, `moderate`, `adventurous` |
| `feedback_style` | enum | `gentle`, `neutral`, `direct` |
| `representation_preference` | enum | `visual`, `numeric`, `narrative`, `mixed` |

**Three evidence types with different update strengths:**

| Type | Confidence Delta | Cap | Example |
|------|-----------------|-----|---------|
| `explicit` | +0.20 | 0.90 | User clicks "Guide me" |
| `behavioral` | +0.05 | 0.80 | User expands help 3+ times |
| `contradiction` | −0.15 | (floor 0.20) | Signal contradicts current value |

**Hysteresis gate:** Value only flips when:
1. Confidence ≥ 0.60
2. 2 consecutive evidence windows support the same candidate

This prevents oscillation from noisy signals.

**Confidence decay:** Exponential decay with dimension-specific half-lives:

| Dimension | Half-life |
|-----------|-----------|
| `cognitive_load_sensitivity` | 7 days |
| `guidance_density` | 14 days |
| `initiative_tolerance` | 21 days |
| `exploration_style` | 14 days |
| `risk_posture` | 14 days |
| `feedback_style` | 21 days |
| `representation_preference` | 14 days |

```python
# Core API
from tap_tone_pi.agentic.spine import ensure_uwsm, apply_uwsm_updates

uwsm = ensure_uwsm()  # Initialize with defaults
audit_log = apply_uwsm_updates(events, uwsm)
# Returns list of audit records with before/after for every dimension touched
```

The implementation extracts evidence signals from events (e.g., idle time → `cognitive_load_sensitivity`, undo spikes → `risk_posture`, view switching → `representation_preference`), then applies them through the hysteresis gate, producing a full audit trail.

### 2.4 Shadow Replay Harness

**File:** `tap_tone_pi/agentic/spine/replay.py` (~170 lines)

Replays recorded event streams through the full pipeline (moments → UWSM → policy) in shadow mode for validation.

```bash
python -m tap_tone_pi.agentic.spine.replay path/to/events.jsonl \
    --mode M0 --verbose
```

Loads JSONL/JSON event files, groups by session, runs the full decision pipeline per session, and outputs a JSON report with per-session moments/decisions/UWSM state + summary counts.

---

## 3. Agent Layer — Presentation

**Location:** `tap_tone_pi/agent/`

This is the **presentation + action-suggestion layer**. It processes quality verdicts into operator-facing messages. It is never measurement truth.

### 3.1 Core Types

**File:** `tap_tone_pi/agent/types.py` (150 lines)

```python
class UserStage(str, Enum):
    FIRST_RUN = "first_run"
    NOVICE = "novice"
    REGULAR = "regular"
    EXPERT = "expert"

class ActionId(str, Enum):
    RETRY = "retry"
    ACCEPT = "accept"
    ADVANCE = "advance"
    ABORT = "abort"
    OVERRIDE = "override"
    HELP = "help"
    CHECK_DEVICE = "check_device"
    RUN_SETUP = "run_setup"
    ADJUST_GAIN_DOWN = "adjust_gain_down"
    ADJUST_GAIN_UP = "adjust_gain_up"
    ADJUST_DURATION_UP = "adjust_duration_up"
    SET_SAMPLERATE_STANDARD = "set_samplerate_standard"
    CHECK_ENVIRONMENT = "check_environment"
    SHOW_ADVANCED = "show_advanced"

@dataclass(frozen=True)
class SuggestedAction:
    action_id: ActionId
    label: str
    rationale: str
    requires_input: bool = False

@dataclass(frozen=True)
class AgentMessage:
    title: str
    summary: str
    details: tuple[str, ...] = ()
    suggested_actions: tuple[SuggestedAction, ...] = ()
    learning_hint: str | None = None
    telemetry_tags: tuple[tuple[str, Any], ...] = ()
```

### 3.2 MeasurementAgent

**File:** `tap_tone_pi/agent/measurement_agent.py` (169 lines)

The main entry point for verdict → message conversion:

```python
from tap_tone_pi.agent.measurement_agent import MeasurementAgent

agent = MeasurementAgent()
msg: AgentMessage = agent.on_verdict(verdict)
# msg has .title, .summary, .details, .suggested_actions, .learning_hint
```

`on_verdict()` flow:
1. Updates internal context history (via `SessionTracker`)
2. Orders triggered rules (HARD first, fixable causes first)
3. Applies FTUE-gated `max_rules_to_show()` to cap detail
4. Selects actions via `select_actions_for_verdict()`
5. Returns structured `AgentMessage`

Also: `reset_for_point()` and `advance_attempt()` for workflow progression.

### 3.3 SessionTracker (PR7)

**File:** `tap_tone_pi/agent/messages.py` — `SessionTracker` class

Single source of truth for in-session fatigue/history state:

```python
from tap_tone_pi.agent.messages import SessionTracker

tracker = SessionTracker()
tracker.record_verdict(verdict)  # Updates all counters atomically
ctx = tracker.make_context(       # Produces frozen AgentContext snapshot
    workflow="measure",
    point_id="A1",
    attempt_num=2,
)
```

Tracks:
- Per-rule counts and consecutive hit streaks
- Verdict streak (e.g., 3 FAILs in a row)
- Last verdict value for streak detection

`AgentContext` (frozen dataclass) carries all this to downstream consumers without mutation risk.

### 3.4 Rule Specifications

**File:** `tap_tone_pi/agent/message_spec.py` (242 lines)

Every quality rule has a structured `RuleSpec`:

```python
@dataclass
class RuleSpec:
    rule_id: str                    # "Q001"
    severity: str                   # "HARD" or "SOFT"
    operator_explanation: str       # What happened
    why_it_matters: str             # Why they should care
    first_fix: str                  # First-time fix suggestion
    fallback_fix: str               # Escalated fix (after repeats)
    advanced_note: str              # Expert-level detail
    agent_actions: list[SuggestedAction]
```

**HARD rules (Q001–Q005) — trigger FAIL verdict:**

| Rule | Condition |
|------|-----------|
| Q001 | Signal clipped — distorted waveform |
| Q002 | No usable signal detected |
| Q003 | No clear resonance found |
| Q004 | Peak detection confidence too low |
| Q005 | Unsupported sample rate |

**SOFT rules (Q010–Q013) — trigger WARN verdict:**

| Rule | Condition |
|------|-----------|
| Q010 | Signal is quiet (low level) |
| Q011 | Signal near clipping (small margin) |
| Q012 | Marginal confidence |
| Q013 | Few peaks detected |

Registry lookup: `get_rule_spec("Q001")` → `RuleSpec | None`.
Verdict templates: `get_verdict_template("fail")` → `VerdictTemplate`.

### 3.5 Selector — Rule Ordering & Fatigue Suppression (PR6)

**File:** `tap_tone_pi/agent/selector.py` (308 lines)

Three key mechanisms:

**1. Explanation modes (three-tier):**

```python
class ExplanationMode(str, Enum):
    FULL = "full"       # explanation + why + fix (first encounter)
    SHORT = "short"     # explanation + fix (seen before)
    COMPACT = "compact" # "Same issue" + fix only (streak ≥3 or session ≥2)
```

`choose_explanation_mode(rule_id, context)` selects the tier based on:
- First time seeing rule → `FULL`
- Streak ≥ 3 or session count ≥ 2 → `COMPACT`
- Otherwise → `SHORT`

**2. Verdict-streak suppression:**

`should_suppress_for_verdict_streak(context)` returns `True` when 3+ identical verdicts in a row → switches to action-only messaging.

**3. Rule ordering:**

```python
def order_rules(rule_ids: list[str]) -> list[str]:
    hard_priority = ["Q001", "Q002", "Q005", "Q003", "Q004"]
    soft_priority = ["Q010", "Q011", "Q012", "Q013"]
    # HARD first, then SOFT, then unknown
```

**4. Action escalation (repeat failures):**

After 2+ consecutive triggers of the same rule, actions escalate:
- Q001 → "Lower gain (repeated clipping)"
- Q002 → "Run setup wizard (repeated silence)"
- Q003 → "Retap with firmer coupling; confirm mic placement"

At attempt 3+, `ABORT` and `OVERRIDE` actions are promoted.

### 3.6 FTUE (Progressive Disclosure)

**File:** `tap_tone_pi/agent/ftue.py` (120 lines)

Controls information density by user stage:

| Parameter | FIRST_RUN | NOVICE | REGULAR | EXPERT |
|-----------|-----------|--------|---------|--------|
| `max_rules_to_show()` | 2 | 4 | 10 | 10 |
| `max_actions_to_show()` | 2 | 3 | 5 | 5 |
| `show_why_it_matters()` | HARD only | All | All | No |

Stage inference: `infer_user_stage(pass_count, session_count)` — 0 passes → `FIRST_RUN`, ≤5 sessions → `NOVICE`, else → `REGULAR`.

`get_ftue_hint(attempt_num, stage)` rotates tips by attempt number for `FIRST_RUN` and `NOVICE` stages.

### 3.7 Renderer

**File:** `tap_tone_pi/agent/render.py` (191 lines)

```python
from tap_tone_pi.agent.render import render_cli

output = render_cli(agent_message, color=True)
# Returns formatted string with ANSI colors, severity tags, action list
```

Separate renderers exist for CLI and GUI. The renderer is **presentation only** — it never alters message content.

---

## 4. Workflow — State Machine

**Location:** `tap_tone_pi/workflow/`

### 4.1 OperatorLoop

**File:** `tap_tone_pi/workflow/operator_loop.py` (384 lines)

The state machine that drives capture → analyze → gate cycles:

```
IDLE → PREFLIGHT → READY → CAPTURING → ANALYZING → GATING → PASSED / WARNED / FAILED
                                ↑
                            LISTENING (auto-trigger mode)
```

```python
from tap_tone_pi.workflow.operator_loop import OperatorLoop

loop = OperatorLoop(session_dir="./session_001", callback=on_state_change)
ok, msg = loop.preflight(device=3)
result = loop.run_single(
    point_id="A1",
    device=3,
    sample_rate=48000,
    duration=2.5,
    auto_trigger=True,
)
# result.attempt, result.audio, result.analysis, result.verdict
```

Key details:
- Auto-trigger mode: waits for tap onset before recording (uses `record_audio_triggered()`)
- Saves per-attempt artifacts: `audio.wav`, `analysis.json`, `quality_check.json`
- Supports override of failed attempts with required reason

### 4.2 Attempt Tracking

**File:** `tap_tone_pi/workflow/attempt.py` (251 lines)

`Attempt` dataclass tracks full lifecycle:

```
PENDING → CAPTURED → ANALYZED → PASSED / WARNED / FAILED / OVERRIDDEN
```

Each attempt records: device info, sample rate, duration, dominant frequency, RMS, confidence, peak count, clipping status, quality verdict, file paths, timestamps.

`AttemptStore` handles persistence (JSON to disk, per-point attempt lists).

---

## 5. Governance Documents Index

These are the **normative references** for the agentic layer. Any behavior change should be traceable to one of these specs.

### 5.1 Core Architecture

| Document | Purpose | Key Content |
|----------|---------|-------------|
| [AGENTIC_SPINE_ARCHITECTURE_ONEPAGER.md](AGENTIC_SPINE_ARCHITECTURE_ONEPAGER.md) | Architecture overview | Data flow diagram, M0→M1→M2 rollout phases, implementation checklist |
| [AGENTIC_CONTRACTS_ENGINEER_HANDOFF.md](AGENTIC_CONTRACTS_ENGINEER_HANDOFF.md) | Contract specifications | Contract suite, cross-repo parity, integration patterns, bootstrap scripts, rollout phases |

The architecture one-pager defines the data flow:

```
Analyzer → Event Consumer → Moment Detector → Policy Engine → UI/Adapter
```

And the rollout roadmap:
- **Phase 1:** Contract Foundation ✅ COMPLETE
- **Phase 2:** Event Integration (wire events into analysis pipeline, shadow mode logging)
- **Phase 3:** Attention Layer (directives for findings, UI rendering, dismissal tracking)
- **Phase 4:** UWSM Integration (signal collection, preference-aware behavior)

### 5.2 Decision Policy

| Document | Purpose | Key Content |
|----------|---------|-------------|
| [AGENT_DECISION_POLICY_V1.md](AGENT_DECISION_POLICY_V1.md) | When the system emits directives and what the agent is allowed to do | M0/M1/M2 mode definitions, 5-step pipeline, moment→intervention mapping, UWSM gates, analyzer-specific policies (FTUE, wolf tone, overload recovery), policy trace format |

Key policy rules defined:
- `POLICY_FTUE_ONE_TRACE_v1` — simplify view for first-time users
- `POLICY_WOLF_TONE_FINDING_v1` — create attention directive for wolf detection
- `POLICY_OVERLOAD_RECOVERY_v1` — reset view when user is overwhelmed

### 5.3 Moments Catalog

| Document | Purpose | Key Content |
|----------|---------|-------------|
| [EVENT_MOMENTS_CATALOG_V1.md](EVENT_MOMENTS_CATALOG_V1.md) | Full moment pattern definitions | 7 moment types (MOM-001 through MOM-007), YAML trigger patterns, UWSM update tables, hysteresis/cooldown rules, test case tables, cross-analyzer aggregation scope |

The catalog defines moments beyond what's currently implemented:

| ID | Moment | Status |
|----|--------|--------|
| MOM-001 | FIRST_SIGNAL | Implemented |
| MOM-002 | HESITATION | Implemented |
| MOM-003 | OVERLOAD | Implemented |
| MOM-004 | CONFIDENCE_CLIMB | Specified (80% acceptance rate over 5+ suggestions) |
| MOM-005 | TRUST_EROSION | Specified (60%+ rejection rate → mandatory M2→M1 fallback) |
| MOM-006 | WORKFLOW_SHIFT | Specified (statistical shift in behavior → confidence drops 20%) |
| MOM-007 | MASTERY_PLATEAU | Specified (85%+ high-quality results over 30 days) |

### 5.4 UWSM Update Rules

| Document | Purpose | Key Content |
|----------|---------|-------------|
| [UWSM_UPDATE_RULES_V1.md](UWSM_UPDATE_RULES_V1.md) | Deterministic preference update mechanics | 7 dimensions with explicit/behavioral signals, per-dimension rule tables with rule IDs, update pipeline (decay → extract → apply with hysteresis), full code examples |

Each dimension has named rules, e.g.:
- `GD_EXPLICIT_GUIDE_ME_v1` — user clicks "Guide me" → `guidance_density` = 0.8
- `IT_BEHAVIOR_IGNORE_SUGGESTIONS_v1` — 3 ignored suggestions → `initiative_tolerance` shifts toward user-led
- `CLS_BEHAVIOR_LONG_IDLE_v1` — 8s idle after tool reveal → `cognitive_load_sensitivity` increases
- `ES_BEHAVIOR_DABBLE_v1` — many tool switches, shallow changes → `exploration_style` = dabble
- `RP_BEHAVIOR_UNDO_SPIKE_v1` — 3+ undos in 60s → `risk_posture` = cautious

### 5.5 Additional Governance

| Document | Purpose |
|----------|---------|
| [ADVISORY_MODE_THIN_SLICE.md](ADVISORY_MODE_THIN_SLICE.md) | Thin-slice plan for advisory mode implementation |
| [SHADOW_MODE_INTEGRATION_PLAN.md](SHADOW_MODE_INTEGRATION_PLAN.md) | Integration plan for shadow mode (M0) |
| [README_SPINE.md](README_SPINE.md) | Developer-facing README for the spine subsystem |
| [BOUNDARY_RULES.md](BOUNDARY_RULES.md) | Boundary enforcement rules |
| [GOVERNANCE.md](GOVERNANCE.md) | Project governance policies |
| [DEVELOPER_HANDOFF_CROSS_REPO.md](DEVELOPER_HANDOFF_CROSS_REPO.md) | Cross-repo integration handoff |

---

## 6. Non-Negotiable Boundaries

These are enforced by CI (`ci/check_boundary_imports.py`) and code review:

1. **Agent never alters measurement truth.** `QualityVerdict` is produced by `quality_gate.py` / `quality_policy.py`. The agent reads it, never writes it.

2. **Agent never tunes DSP.** No adjusting thresholds, FFT parameters, or peak-picking logic.

3. **No interpretation beyond PASS/WARN/FAIL + reason.** No "good/bad/worst/dominant" language.

4. **No auto-fixing.** Agent suggests, operator decides.

5. **Forbidden imports:**
   ```bash
   python ci/check_boundary_imports.py --preset analyzer
   ```
   Blocks imports of `app.*`, `services.*`, `packages.*` (Luthier's ToolBox namespaces). Data crosses the boundary via artifacts (JSON/CSV/WAV + manifests), never Python imports.

6. **Where to change what:**

   | Change | File(s) |
   |--------|---------|
   | Add/edit rule copy | `agent/message_spec.py`, `agent/messages.py` |
   | Change verbosity/escalation | `agent/selector.py` |
   | Change presentation format | `agent/render.py` |
   | Persist new FTUE signal | `agent/ftue.py` + tests (never in QC) |
   | Add moment pattern | `agentic/spine/moments.py` + test |
   | Add UWSM dimension rule | `agentic/spine/uwsm_update.py` + update governance doc |
   | Change policy mapping | `agentic/spine/policy.py` + update governance doc |

---

## 7. Test Coverage

### 7.1 Test Files

| Test File | Validates | Key Patterns |
|-----------|-----------|--------------|
| `tests/test_agentic_contracts.py` | Contract parity, serialization, required fields | Cross-repo JSON round-trip |
| `tests/test_moments_engine_v1.py` | Moment detection from synthetic event streams | Priority ordering, suppression |
| `tests/test_policy_engine_v1.py` | Policy pipeline, mode gates, UWSM gates | M0 shadow logging, M1 directives, M2 view commands |
| `tests/test_agent_types.py` | Core agent type constructors | Frozen dataclass invariants |
| `tests/test_agent_selector.py` | Rule ordering, explanation modes, fatigue suppression | Streak detection, escalation |
| `tests/test_agent_render.py` | CLI rendering | ANSI output, severity formatting |
| `tests/test_agent_message_spec.py` | Rule specs, verdict templates | Q001–Q013 completeness |
| `tests/test_agent_messages.py` | SessionTracker, AgentContext | History tracking, frozen snapshots |
| `tests/test_agent_integration.py` | End-to-end verdict→message flow | Full pipeline |
| `tests/test_agent_ftue.py` | Progressive disclosure, stage inference | Max rules/actions per stage |
| `tests/test_agent_fatigue.py` | Fatigue suppression (PR6) | Verdict streaks, explanation mode transitions |
| `tests/test_cli_measure_agent_output.py` | CLI `ttp measure` agent output | End-to-end CLI integration |
| `tests/test_cli_agent_wiring.py` | CLI agent wiring | Agent message appears in CLI output |

### 7.2 Testing Requirements

Every agent behavior change needs ≥1 selector/message test. CLI wiring changes need ≥1 CLI-level test. This is enforced by review, not CI.

Run tests:
```bash
make test                    # Full suite
pytest tests/test_agent*.py  # Agent tests only
pytest tests/test_agentic*.py tests/test_moments*.py tests/test_policy*.py  # Spine tests
```

---

## 8. Recent PRs (Context for Incoming Engineer)

| PR | What | Commit | Key Files Changed |
|----|------|--------|-------------------|
| PR6 | Rule-fatigue suppression & escalation | `1b7557b` | `selector.py` (ExplanationMode, streak suppression, escalation actions) |
| PR7 | SessionTracker — single-source session history | `5a78307` | `messages.py` (SessionTracker class, replaces scattered counters) |
| PR8 | Evidence preflight validator (clean-slate) | `100a0e1` | `validate/evidence_check.py` (E001/E003/E101/E102 checks) |

---

## 9. Next Steps / Open Work

Based on the governance docs and rollout phases:

1. **Phase 2 — Event Integration:** Wire `emit_event()` calls into the actual analysis pipeline (`core/analysis.py`, `OperatorLoop`). Currently the event emitters exist but are not called from production paths.

2. **Phase 3 — Attention Layer:** Implement directive rendering in the GUI (`gui/`). Currently only CLI rendering exists.

3. **Phase 4 — UWSM Integration:** Connect UWSM signal collection to real user interactions. Currently the UWSM update engine is implemented but not wired to live input.

4. **Catalog gaps:** Moments MOM-004 through MOM-007 are specified in the catalog but not implemented in `moments.py`.

5. **M2 testing:** Actuated mode view commands exist in `policy.py` but have no integration tests against a real GUI.

6. **Cross-repo integration testing:** The contracts mirror needs a CI job that verifies JSON parity between tap_tone_pi and luthiers-toolbox (currently done manually).

---

## 10. Quick Reference — File Map

```
tap_tone_pi/
├── agentic/
│   ├── __init__.py                 # Re-exports contracts + capabilities (v1.0.0)
│   ├── capabilities.py             # 4 tool capability declarations + registry
│   ├── events.py                   # emit_event() + convenience emitters (276 lines)
│   ├── contracts/
│   │   ├── __init__.py             # Re-exports all 9 contract types
│   │   ├── tool_capability.py      # ToolCapabilityV1, CapabilityAction, SafeDefaults
│   │   ├── analyzer_attention.py   # AttentionDirectiveV1, AttentionAction, FocusTarget
│   │   └── event_emission.py       # AgentEventV1, EventType (20 types), EventSource
│   └── spine/
│       ├── __init__.py             # Re-exports core functions
│       ├── moments.py              # detect_moments() — priority-based pattern detection
│       ├── policy.py               # decide() — M0/M1/M2 gated decision pipeline
│       ├── uwsm_update.py          # ensure_uwsm(), apply_uwsm_updates() — 7 dimensions
│       └── replay.py               # run_shadow_replay() — event replay harness
├── agent/
│   ├── types.py                    # UserStage, ActionId, SuggestedAction, AgentMessage
│   ├── measurement_agent.py        # MeasurementAgent.on_verdict() — main entry point
│   ├── messages.py                 # SessionTracker, AgentContext, verdict/rule templates
│   ├── message_spec.py             # RuleSpec Q001–Q013, VerdictTemplate, get_rule_spec()
│   ├── selector.py                 # ExplanationMode, order_rules(), select_actions_for_verdict()
│   ├── ftue.py                     # Progressive disclosure, stage inference
│   └── render.py                   # render_cli() — ANSI terminal formatting
├── workflow/
│   ├── operator_loop.py            # OperatorLoop state machine (IDLE→...→PASSED/FAILED)
│   └── attempt.py                  # Attempt lifecycle tracking, AttemptStore
└── validate/
    └── evidence_check.py           # Evidence preflight (E001/E003/E101/E102)
```

---

**End of handoff. Questions → check governance docs first, then tests, then code.**

---

## Appendix A. Production Ownership Map

### Ownership Tiers

| Tier | Scope | Change Policy | Paths |
|------|-------|--------------|-------|
| **0 — Stable contracts** | Cross-repo thin waist (ToolBox parity) | Break-glass only: version bump + migration note + cross-repo parity check | `agentic/contracts/` |
| **1 — Policy surfaces** | Spine, agent messaging, quality rules | ≥1 targeted test + governance doc alignment if behavior changes | `agentic/spine/`, `agent/`, `core/quality_*.py` |
| **2 — Integration glue** | CLI, GUI, export, validate | Backwards-compat > elegance; prefer additive flags over breaking changes | `cli/`, `gui/`, `export/`, `validate/` |
| **3 — Instrument truth** | DSP, capture, analysis | Explicit justification + fixture-based tests; no agent-driven behavior | `core/analysis.py`, `core/dsp.py`, `capture/` |

### PR Type → Owner Checklist

| PR changes… | Owner layer | Touch | Must add |
|-------------|-------------|-------|----------|
| Operator guidance (copy, fatigue, actions) | Agent presentation | `agent/*` | ≥1 `test_agent_selector` or `test_agent_integration` |
| When to interrupt / what directive to show | Spine policy + moments | `agentic/spine/*` | Moments/policy test + governance doc update |
| Evidence schema or export pack contents | Evidence/export | `export/*`, `validate/*` | Export validation test + evidence-check test |
| PASS/WARN/FAIL logic | Quality gate | `core/quality_*.py` | Rule test + integration fixture update |
| Capture timing / device behavior | Capture + workflow | `capture/`, `workflow/` | Attempt lifecycle test + hardware-safe mocks |

### Current GUI Gap

The GUI ([app.py](../tap_tone_pi/gui/app.py), 1690 lines) has a `QualityVerdictViewer` that renders verdicts directly from `quality_gate.format_verdict_summary()` — it does **not** use the agent presentation layer (`agent/messages.py`, `agent/render.py`). The agent layer is currently CLI-only via `ttp record --agent` and `ttp measure --agent`.

---

## Appendix B. Minimum PR Sequence — End-to-End Spine-Driven Directives

Six PRs, strictly ordered. Each is independently shippable and testable. None touches measurement truth.

### PR-S1: Event Emission in OperatorLoop

**Goal:** Make `OperatorLoop.run_single()` emit `AgentEventV1` events to a JSONL log.

**What to change:**

| File | Change |
|------|--------|
| `workflow/operator_loop.py` | Import `emit_analysis_started`, `emit_analysis_completed`, `emit_analysis_failed` from `agentic.events`. Call them at ANALYZING→GATING transitions. Write events to `{session_dir}/events.jsonl`. |
| `agentic/events.py` | Add `EventSink` protocol: `write(event: AgentEventV1) -> None`. Add `JsonlEventSink(path)` default implementation. Make `emit_event()` accept an optional sink (default: in-memory list for tests). |
| `tests/test_workflow_events.py` (new) | Assert: `run_single()` on synthetic audio produces ≥2 events (started + completed/failed). Assert: events.jsonl is valid JSONL. Assert: event `source.component` is `"operator_loop"`. |

**Does NOT change:** Analysis results, quality verdicts, agent messages, CLI output.

**Risk:** Low. Additive only — events are written alongside existing artifacts.

---

### PR-S2: Shadow-Mode Spine Hook (M0)

**Goal:** After `run_single()` completes, run `detect_moments()` + `decide()` in M0 (shadow) mode. Log what *would have been* emitted.

**What to change:**

| File | Change |
|------|--------|
| `workflow/operator_loop.py` | After verdict is set, if an event sink exists, call `_run_shadow_spine(events)` which: loads events from sink → `detect_moments()` → `decide(..., mode="M0")` → appends shadow diagnostic to events.jsonl. |
| `agentic/spine/policy.py` | No changes needed — M0 path already emits `would_have_emitted` diagnostic. |
| `tests/test_shadow_spine_hook.py` (new) | Assert: shadow diagnostic event appears in JSONL after a FAIL verdict. Assert: shadow diagnostic contains `moment` and `would_have_emitted`. Assert: no `AttentionDirectiveV1` is rendered to the user. |

**Does NOT change:** User-visible output. Shadow mode is observe-only by definition.

**Depends on:** PR-S1 (needs event sink).

---

### PR-S3: UWSM Persistence

**Goal:** Persist UWSM state to disk so cross-session dimensions (decay, hysteresis) actually work.

**What to change:**

| File | Change |
|------|--------|
| `agentic/spine/uwsm_store.py` (new) | `UWSMStore` class: `load(path) -> dict`, `save(uwsm, path)`, `default_path() -> Path` (`~/.config/tap_tone_pi/uwsm.json`). JSON format with `_state.streaks` preserved. Atomic write (tmp + rename). |
| `agentic/spine/uwsm_update.py` | `ensure_uwsm()` gains optional `path` param — loads from disk if exists, creates default if not. `apply_uwsm_updates()` gains optional `persist=True` flag. |
| `workflow/operator_loop.py` | Shadow hook (PR-S2) passes loaded UWSM to `decide()` and saves after update. |
| `tests/test_uwsm_persistence.py` (new) | Assert: fresh install creates default UWSM. Assert: round-trip save/load preserves all 7 dimensions + streaks. Assert: decay applies correctly when timestamps differ by >1 half-life. |

**Does NOT change:** UWSM logic (already implemented). Only adds the missing storage layer.

**Depends on:** PR-S2 (needs shadow hook to exercise persistence).

---

### PR-S4: CLI Directive Rendering (M1 Advisory)

**Goal:** When `ttp measure --agent` runs and the spine produces a directive, render it alongside the existing `AgentMessage`.

**What to change:**

| File | Change |
|------|--------|
| `cli/main.py` | In the `cmd_measure` agent path (after `format_verdict_summary_agent`): if shadow hook produced a directive, switch to M1 and render it via a new `render_directive_cli()`. Add `--spine-mode` flag (default `M0`, options `M0`/`M1`). |
| `agent/render.py` | Add `render_directive_cli(directive: AttentionDirectiveV1, verbosity: str) -> str`. Format: urgency badge + summary + optional detail (controlled by verbosity). Reuse existing ANSI color helpers. |
| `tests/test_cli_spine_directive.py` (new) | Assert: `--spine-mode M0` produces no directive output. Assert: `--spine-mode M1` with a FAIL verdict prints directive summary. Assert: directive output does not replace existing `AgentMessage` output (coexistence). |

**Design decision this PR must resolve:** `AgentMessage` (from `MeasurementAgent`) and `AttentionDirectiveV1` (from spine) coexist. The `AgentMessage` is the per-verdict operator message. The directive is the cross-session/cross-tool attention signal. They serve different purposes and should render in sequence: agent message first, then directive (if any) as a separate block.

**Does NOT change:** Default behavior (`--agent` without `--spine-mode` still works as before).

**Depends on:** PR-S2 (needs shadow hook producing directives).

---

### PR-S5: GUI Agent Message Surface

**Goal:** Replace the GUI's direct `format_verdict_summary()` call with the agent presentation layer, matching what CLI already does.

**What to change:**

| File | Change |
|------|--------|
| `gui/app.py` | In `QualityVerdictViewer.__init__()`: import `SessionTracker`, `build_agent_message` from `agent.messages`. Build `AgentContext` from verdict + FTUE state. Render `AgentMessage` fields (title, summary, details, suggested_actions) into the existing Tkinter layout instead of raw `format_verdict_summary()`. |
| `gui/widgets.py` | Add `AgentMessagePanel(tk.Frame)`: renders an `AgentMessage` as a Tkinter widget with expandable details and action buttons (buttons emit callbacks, don't execute). |
| `tests/test_gui_agent_panel.py` (new) | Assert: `AgentMessagePanel` renders without error for PASS/WARN/FAIL messages. Assert: action buttons are present and labeled correctly. Assert: FTUE hints appear for `FIRST_RUN` stage. |

**Does NOT change:** Verdict logic. The GUI shows the same facts, just through the agent layer's formatting.

**Depends on:** Nothing — can run in parallel with PR-S2/S3/S4. Uses existing `agent/` code.

---

### PR-S6: GUI Directive Surface + Dismissal Tracking

**Goal:** Wire spine directives into the GUI with dismissal tracking (enabling UWSM signal collection for `initiative_tolerance`).

**What to change:**

| File | Change |
|------|--------|
| `gui/app.py` | After quality gate verdict, if spine produces a directive: show `DirectiveToast` widget. Track `ATTENTION_ACKNOWLEDGED` / `ATTENTION_DISMISSED` events to event sink. |
| `gui/widgets.py` | Add `DirectiveToast(tk.Toplevel)`: auto-dismiss timer, urgency color coding, "Got it" / "Show me" / dismiss buttons. Emits callback with action taken. |
| `agentic/events.py` | Add `emit_attention_acknowledged()` and `emit_attention_dismissed()` convenience emitters (parallel to existing `emit_attention_requested()`). |
| `tests/test_gui_directive_toast.py` (new) | Assert: toast appears for REVIEW directive. Assert: dismissal emits correct event type. Assert: `auto_dismiss_after_seconds` from directive is respected. |

**Does NOT change:** Measurement truth. Directive toast is informational only.

**Depends on:** PR-S3 (needs UWSM persistence for dismissal signals to matter), PR-S5 (GUI agent surface should land first for consistent UX).

---

### PR Dependency Graph

```
PR-S1 (Event Emission)
  │
  ▼
PR-S2 (Shadow Hook M0)
  │
  ├──────────────┐
  ▼              ▼
PR-S3 (UWSM     PR-S4 (CLI
 Persist)        Directive M1)
  │
  ▼
PR-S5 (GUI Agent Panel)  ← can also start independently
  │
  ▼
PR-S6 (GUI Directive Toast + Dismissal)
```

**Total estimated scope:** ~1200 lines of new code + ~400 lines of tests across 6 PRs.

**What you have after all 6:**
- OperatorLoop emits events to JSONL → spine detects moments → policy produces directives
- UWSM persists across sessions with decay and hysteresis
- CLI renders directives alongside agent messages (`--spine-mode M1`)
- GUI shows agent messages and directive toasts with dismissal tracking
- Dismissal events feed back into UWSM for `initiative_tolerance` adaptation
- Measurement truth is completely untouched throughout
