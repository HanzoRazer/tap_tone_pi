# ADR-0008: Spine Wiring Architecture — Coexistence, Persistence, Rollout

## Status
Accepted

## Date
2026-02-08

## Context

Tap Tone Pi has two parallel presentation systems that emerged from different design eras:

1. **Agent layer** (`tap_tone_pi/agent/`) — per-verdict coaching messages.
   Built during Phase 1. Wired into CLI via `--agent` flag. Renders `AgentMessage`
   objects (title + explanation rows + suggestion rows + actions). Consumes
   `QualityVerdict` and `Attempt` directly. Has selector, renderer, FTUE state.

2. **Agentic spine** (`tap_tone_pi/agentic/`) — event-driven orchestration layer.
   Designed during Phase 2. Specifies `AgentEventV1`, `AttentionDirectiveV1`,
   moments engine, policy engine, UWSM, replay. Has contracts and test stubs
   but **zero production event emission** and **no persistent UWSM state**.

The incoming engineer needs unambiguous answers to four architectural questions
before wiring the spine into production:

- How do AgentMessage and AttentionDirectiveV1 coexist?
- Where do events get persisted?
- Where does UWSM state live?
- What is the rollout sequence from shadow to production?

This ADR crystallizes decisions made during the 2026-02-08 handoff session.

---

## Decision 1: Coexistence Model

**AgentMessage and AttentionDirectiveV1 coexist. Neither replaces the other.**

| System | Scope | Trigger | Lifetime |
|--------|-------|---------|----------|
| `AgentMessage` | Single verdict | `QualityVerdict` + `Attempt` | Per-tap |
| `AttentionDirectiveV1` | Cross-event pattern | Moment detection over event stream | Per-session |

### Rules

1. `AgentMessage` remains the per-verdict coaching surface. It is rendered
   immediately after each measurement in both CLI and GUI.

2. `AttentionDirectiveV1` is the cross-event orchestration surface. It fires
   when the moments engine detects session-level patterns (hesitation, overload,
   repeated failures, wolf-frequency findings).

3. In CLI, directives render as a **separate block after** the agent message —
   never interleaved. Format: `── Spine ──\n{summary}\n{hint}`.

4. In GUI, directives render in a dedicated toast/panel widget, separate from
   the `QualityVerdictViewer`.

5. If both fire for the same tap, the agent message appears first (immediate
   feedback), then the directive (contextual pattern).

6. The bridge is built incrementally: the spine consumes the same
   `QualityVerdict` that the agent layer does, via emitted events — it does
   not import or call agent-layer code.

### Non-goals

- Merging AgentMessage into AttentionDirectiveV1.
- Having the spine suppress or override agent messages.
- Deprecating the agent layer.

---

## Decision 2: Event Persistence

**Events persist as append-only JSONL in the session directory.**

### Location

```
{session_dir}/events.jsonl
```

Each line is a single `AgentEventV1`-shaped JSON object. The file is created
on the first emitted event and appended thereafter. No rotation, no cleanup
within a session.

### Gating

Event emission is **disabled by default** and controlled via environment
variables (design from `SHADOW_MODE_INTEGRATION_PLAN.md`):

| Variable | Default | Values |
|----------|---------|--------|
| `AGENTIC_EMIT_EVENTS` | `0` | `0` (off), `1` (on) |
| `AGENTIC_EVENT_SINK` | `jsonl` | `jsonl`, `stdout`, `null` |
| `AGENTIC_EVENT_LOG` | `events.jsonl` | Filename (relative to session dir) |

When `AGENTIC_EVENT_SINK=jsonl`, the emitter writes to
`{session_dir}/{AGENTIC_EVENT_LOG}`. When `stdout`, events print to stderr
(for piping). When `null`, events are computed but discarded (testing).

### Emission Points

Events are emitted from `OperatorLoop.run_single()` — the single method that
orchestrates one measurement cycle (record → analyze → gate → verdict → retry
decision). This keeps emission centralized rather than scattered across
`cmd_record`, `cmd_measure`, and future GUI paths.

### Minimum Event Set (v1)

| Event Type | Emitted When | Key Payload Fields |
|------------|-------------|-------------------|
| `analysis_started` | `run_single()` begins | `point_id`, `attempt` |
| `analysis_completed` | Analysis returns successfully | `peak_count`, `rms`, `clipped` |
| `analysis_failed` | Analysis raises or verdict=FAIL | `error`, `rule_id` |
| `artifact_created` | WAV/JSON/CSV written | `artifact_type`, `path` |
| `decision_required` | Gate verdict needs operator input | `verdict_class`, `options` |
| `user_action` | Operator chooses retry/accept/override | `action`, `reason` |

### Storage Abstraction

The emitter module (`tap_tone_pi/agentic/emitter.py`) owns a `write_event()`
function that accepts a session directory path. The caller (OperatorLoop) passes
the session dir; the emitter handles file creation, append, and flush. This
keeps OperatorLoop unaware of sink details.

### Non-goals

- Cross-session event aggregation (future, not v1).
- Database-backed event storage.
- Real-time event streaming to external services.

---

## Decision 3: UWSM Persistence

**UWSM state persists in a separate file, decoupled from FTUE config.**

### Location

```
~/.config/tap_tone_pi/uwsm_v1.json
```

This is intentionally **not** `~/.tap_tone_pi/config.json` (where `UserConfig`
and `FtueState` live). Rationale:

- UWSM dimensions are learned over time and may be reset independently.
- FTUE state tracks factual counts (passes, sessions, overrides). UWSM tracks
  inferred preferences (cognitive load sensitivity, guidance density, initiative
  tolerance). Different lifecycles, different reset semantics.
- Separating files avoids version-coupling: bumping UWSM schema does not
  require migrating UserConfig.

### Schema (v1)

```json
{
  "schema_version": "uwsm_v1",
  "last_updated": "2026-02-08T12:00:00Z",
  "dimensions": {
    "cognitive_load_sensitivity": {
      "value": 0.5,
      "confidence": 0.0,
      "last_updated": "2026-02-08T12:00:00Z"
    },
    "guidance_density": {
      "value": 0.5,
      "confidence": 0.0,
      "last_updated": "2026-02-08T12:00:00Z"
    },
    "initiative_tolerance": {
      "value": 0.5,
      "confidence": 0.0,
      "last_updated": "2026-02-08T12:00:00Z"
    }
  },
  "session_streak": {
    "dismiss_count": 0,
    "accept_count": 0,
    "override_count": 0
  }
}
```

### Rules

1. On first load, if the file does not exist, create it with neutral defaults
   (all dimensions at 0.5, confidence 0.0).
2. Use the same atomic-write pattern as `UserConfig` (`tmp` + `os.replace`).
3. UWSM updates happen at session end (not per-verdict), driven by
   `session_streak` counts accumulated during the session.
4. Confidence increases only with consistent signal; a single contradictory
   action resets confidence toward 0.
5. The UWSM file is **never read by the agent layer** (`agent/`). Only the
   spine policy engine reads it.

### Non-goals

- Coupling UWSM to FTUE state or `UserConfig`.
- Per-instrument UWSM profiles (future consideration).
- Cloud sync of UWSM state.

---

## Decision 4: Rollout Gates

**Shadow first (M0), then advisory CLI (M1), then GUI. Each gate requires
explicit evidence before proceeding.**

### Sequence

```
M0 Shadow     →  M1 Advisory (CLI)  →  M1 Advisory (GUI)  →  M2 Actuated (GUI)
   │                    │                      │                      │
   │  Gate A            │  Gate B              │  Gate C              │
   ▼                    ▼                      ▼                      ▼
  emit events       directives           GUI directive           view commands
  log decisions     render in CLI        toast/panel             (opt-in only)
  no user output    user sees them       user sees them          agent adjusts UI
```

### Gate Criteria

| Gate | Name | Entry Criteria |
|------|------|---------------|
| A | Shadow → Advisory CLI | ≥ 3 real sessions replayed with zero false-positive directives at I3+ level. Shadow scoreboard reviewed. Moment detectors (FIRST_SIGNAL, HESITATION, OVERLOAD) tested against recorded sessions. |
| B | Advisory CLI → Advisory GUI | CLI directive rendering stable for ≥ 2 releases. GUI `AgentDirectivePanel` widget implemented with dismiss/snooze. No new agent-layer regressions. |
| C | Advisory GUI → Actuated GUI | M1 GUI stable for ≥ 1 release. `ToolCapabilityV1` declarations verified. `require_confirmation` gate tested. User opt-in mechanism implemented. |

### Mode Selection

- **Default:** M0 (shadow). Events emitted only when `AGENTIC_EMIT_EVENTS=1`.
- **CLI flag:** `ttp measure --spine-mode M1` enables advisory directives.
- **GUI:** Mode selection in settings panel (future).
- **No M2 in CLI.** Actuated mode requires a visual surface to adjust.

### Implementation Sequence (PR-S1 through PR-S6)

| PR | Title | Depends On | Gate |
|----|-------|-----------|------|
| PR-S1 | Event emission from OperatorLoop | — | — |
| PR-S2 | Shadow hook (moments + log-only) | S1 | — |
| PR-S3 | UWSM persistence + session-end update | S1 | — |
| PR-S4 | CLI directive rendering (`--spine-mode M1`) | S1, S2, S3 | Gate A |
| PR-S5 | GUI agent panel (replace direct `format_verdict_summary`) | S4 | Gate B |
| PR-S6 | GUI directive toast + M2 opt-in | S5 | Gate C |

### Non-goals

- Skipping M0. Shadow validation is mandatory.
- Enabling M2 in CLI.
- Auto-promoting modes without human review of gate criteria.

---

## Rationale

1. **Coexistence over replacement** avoids a risky rewrite of the working agent
   layer while allowing the spine to prove itself in shadow mode first. The
   agent layer is battle-tested in CLI; the spine is not yet production-proven.

2. **Session-dir JSONL** keeps events co-located with the evidence they
   describe. No external dependencies. Easy to replay, easy to inspect, easy
   to ship in an evidence pack if needed.

3. **Separate UWSM file** respects the different lifecycles of factual state
   (FTUE counts) and inferred state (preference dimensions). It also avoids
   migration complexity when either schema evolves.

4. **Gated rollout** prevents the spine from affecting users before it is
   validated. Shadow mode (M0) lets us collect real decision traces and review
   them offline. Each gate requires evidence, not just elapsed time.

## Consequences

- The incoming engineer has a clear, ordered PR sequence with no ambiguity
  about what ships when.
- CLI and GUI diverge temporarily: CLI gets directives first, GUI follows.
  This is acceptable because the CLI is the primary production interface today.
- Two persistence files (`config.json` + `uwsm_v1.json`) means two load/save
  paths. Both use the same atomic-write pattern, so the implementation cost
  is minimal.
- Events are opt-in (`AGENTIC_EMIT_EVENTS=0` default). Users who never set
  the env var see zero behavioral change.

## Non-goals

- This ADR does not define moment detection logic (see `EVENT_MOMENTS_CATALOG_V1.md`).
- This ADR does not define UWSM update rules (see `UWSM_UPDATE_RULES_V1.md`).
- This ADR does not define directive content/copy (see `agent/message_spec.py`).
- This ADR does not implement MOM-004 through MOM-007. Those moments require
  UWSM persistence (Decision 3) and event replay (Decision 2) to exist first.

---

## References

- [ADR-0007: Phase 2 ODS + Coherence Pipeline](ADR-0007_PHASE2_ODS_COHERENCE.md)
- [AGENT_DECISION_POLICY_V1.md](AGENT_DECISION_POLICY_V1.md)
- [SHADOW_MODE_INTEGRATION_PLAN.md](SHADOW_MODE_INTEGRATION_PLAN.md)
- [AGENTIC_LAYER_DEV_HANDOFF.md](AGENTIC_LAYER_DEV_HANDOFF.md) — Appendix B (PR sequence)
- [EVENT_MOMENTS_CATALOG_V1.md](EVENT_MOMENTS_CATALOG_V1.md)
