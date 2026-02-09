"""
Agent message spec for tap-tone-pi.

Purpose
- Translate QualityVerdict + context into a deterministic, policy-safe operator message.
- NO DSP, NO QC logic changes. This module only formats/structures guidance.

Integration options
1) CLI/GUI: call build_agent_message(context, verdict) and render it.
2) Existing flow: call format_verdict_summary_agent(context, verdict) instead of (or after)
   tap_tone_pi.core.quality_gate.format_verdict_summary(verdict).

This module depends only on:
- tap_tone_pi.core.quality_policy (Verdict, Severity, QualityVerdict, TriggeredRule)
It does not modify any QC outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Sequence

from tap_tone_pi.core.quality_policy import QualityVerdict, TriggeredRule, Verdict, Severity


# =============================================================================
# PR6: Explanation Mode (three-tier verbosity)
# =============================================================================

class ExplanationMode(str, Enum):
    """Three-tier explanation verbosity.

    FULL: What happened + why it matters + common causes (FTUE / first exposure).
    SHORT: One-sentence explanation + immediate fix (seen before, low repetition).
    COMPACT: No explanation — 'Same issue recurring, focus on fix' (heavy repetition).
    """
    FULL = "full"
    SHORT = "short"
    COMPACT = "compact"


def choose_explanation_mode(ctx: AgentContext, rule_id: str) -> ExplanationMode:
    """Determine explanation verbosity for a rule based on context.

    PR6 Rules:
    - First-time rule (new + session count ≤1) → FULL
    - Consecutive hits ≥3 OR session count ≥3 → COMPACT
    - Otherwise → SHORT
    """
    is_first_time = ctx.is_rule_new(rule_id)
    session_count = ctx.get_rule_count(rule_id)
    streak = ctx.get_consecutive_hits(rule_id)

    if is_first_time and session_count <= 1:
        return ExplanationMode.FULL
    if streak >= 3 or session_count >= 3:
        return ExplanationMode.COMPACT
    return ExplanationMode.SHORT


def should_suppress_for_verdict_streak(ctx: AgentContext) -> bool:
    """True if 3+ identical verdicts in a row — suppress explanations entirely.

    At this point the user knows what is wrong; show only verdict title
    + strongest corrective action.
    """
    return ctx.consecutive_same_verdict >= 3


# -----------------------------------------------------------------------------
# Context + output models
# -----------------------------------------------------------------------------

UserStage = Literal["first_run", "novice", "regular", "expert"]
Workflow = Literal["record", "measure", "phase2"]


@dataclass(frozen=True)
class AgentContext:
    """
    Minimal context used to tailor messaging without changing measurement truth.

    You can create this from CLI/GUI state or from OperatorLoop state.

    Notes:
    - user_stage may be provided explicitly; otherwise inferred from pass_count/session_count.
    - history counters are optional. If omitted, the agent won't escalate messaging.
    """
    workflow: Workflow = "record"
    user_stage: Optional[UserStage] = None

    point_id: Optional[str] = None
    attempt_num: int = 1
    max_attempts: int = 1

    device_name: str = "default"
    sample_rate: Optional[int] = None
    policy_version: Optional[str] = None

    # FTUE inference signals (from persistence)
    pass_count_lifetime: int = 0
    session_count_lifetime: int = 0
    override_count_lifetime: int = 0
    seen_rule_ids: tuple[str, ...] = ()  # persisted rule exposure

    # In-session history for escalation (use tuple for frozen compatibility)
    rule_counts_this_session: tuple[tuple[str, int], ...] = ()
    consecutive_rule_hits: tuple[tuple[str, int], ...] = ()
    consecutive_same_verdict: int = 0

    # UI toggles
    show_details: bool = True  # GUI may hide details behind disclosure
    expert_mode: bool = False  # force expert verbosity

    def get_rule_count(self, rule_id: str) -> int:
        """Get count for a rule from session history."""
        for rid, count in self.rule_counts_this_session:
            if rid == rule_id:
                return count
        return 0

    def get_consecutive_hits(self, rule_id: str) -> int:
        """Get consecutive hit count for a rule."""
        for rid, count in self.consecutive_rule_hits:
            if rid == rule_id:
                return count
        return 0

    def is_rule_new(self, rule_id: str) -> bool:
        """True if user has never seen this rule (not in persisted seen_rule_ids)."""
        return rule_id not in self.seen_rule_ids

    def is_rule_fatiguing(self, rule_id: str) -> bool:
        """True if rule is repeated (in-session ≥2 or previously seen)."""
        return self.get_rule_count(rule_id) >= 2 or not self.is_rule_new(rule_id)


@dataclass(frozen=True)
class SuggestedAction:
    """
    Suggested actions are *choices* presented to the operator (or UI buttons).
    They do not execute anything and do not alter measurement outputs.
    """
    action_id: str
    label: str
    rationale: str
    requires_input: bool = False


@dataclass(frozen=True)
class AgentMessage:
    title: str
    summary: str
    details: tuple[str, ...] = ()
    suggested_actions: tuple[SuggestedAction, ...] = ()
    learning_hint: Optional[str] = None
    telemetry_tags: tuple[tuple[str, Any], ...] = ()

    def get_tag(self, key: str) -> Any:
        """Get a telemetry tag by key."""
        for k, v in self.telemetry_tags:
            if k == key:
                return v
        return None


# -----------------------------------------------------------------------------
# Message spec tables
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleMessageSpec:
    rule_id: str
    severity: Severity
    operator_explanation: str
    why_it_matters: str
    first_fix: str
    fallback_fix: str
    advanced_note: str
    actions: tuple[SuggestedAction, ...]


@dataclass(frozen=True)
class VerdictTemplate:
    title: str
    summary: str
    default_actions: tuple[SuggestedAction, ...]


# Short reusable hints
FTUE_HINTS: Dict[UserStage, tuple[str, ...]] = {
    "first_run": (
        "Tip: Run 'ttp setup' once to lock the right input device (USB indices can change).",
        "Tip: Aim for a strong signal without clipping; near-clipping warnings are common at first.",
        "Tip: Consistent support and tap point matter more than tap strength.",
    ),
    "novice": (
        "Tip: If the same warning repeats, adjust setup once rather than retrying many times.",
    ),
    "regular": (),
    "expert": (),
}

# Verdict-level templates (headlines + default CTAs)
VERDICT_TEMPLATES: Dict[Verdict, VerdictTemplate] = {
    Verdict.PASS: VerdictTemplate(
        title="Measurement accepted",
        summary="Quality checks passed. You can proceed to the next point.",
        default_actions=(
            SuggestedAction("advance", "Next point", "Proceed in workflow"),
        ),
    ),
    Verdict.WARN: VerdictTemplate(
        title="Measurement usable with warnings",
        summary="Capture is usable, but conditions may reduce repeatability.",
        default_actions=(
            SuggestedAction("accept", "Accept", "Proceed with warning noted"),
            SuggestedAction("retry", "Retry", "Try to improve quality"),
        ),
    ),
    Verdict.FAIL: VerdictTemplate(
        title="Measurement failed quality gate",
        summary="Capture is not acceptable under policy.",
        default_actions=(
            SuggestedAction("retry", "Retry", "Correct conditions and retake"),
            SuggestedAction("abort", "Abort", "Stop and troubleshoot"),
            SuggestedAction("override", "Override (requires reason)", "Log exception explicitly", requires_input=True),
        ),
    ),
}

# Rule-level specs (Q001–Q013)
RULE_SPECS: Dict[str, RuleMessageSpec] = {
    # HARD
    "Q001": RuleMessageSpec(
        rule_id="Q001",
        severity=Severity.HARD,
        operator_explanation="The signal clipped (hit the recorder's maximum). This capture is distorted.",
        why_it_matters="Clipping changes the spectrum and can produce false peaks.",
        first_fix="Reduce input gain or move the mic farther away.",
        fallback_fix="Use a softer tap if gain can't be changed.",
        advanced_note="If clipping persists at low gain, check OS mic boost / auto gain control.",
        actions=(
            SuggestedAction("adjust_gain_down", "Lower gain and retry", "Prevents distortion"),
            SuggestedAction("retry", "Retry capture", "Need an unclipped waveform"),
            SuggestedAction("abort", "Abort", "Cannot proceed with clipped data"),
        ),
    ),
    "Q002": RuleMessageSpec(
        rule_id="Q002",
        severity=Severity.HARD,
        operator_explanation="No usable signal was detected.",
        why_it_matters="Without sufficient signal, peaks and confidence are meaningless.",
        first_fix="Check the selected input device and tap closer / harder.",
        fallback_fix="Increase input gain and confirm the level meter moves.",
        advanced_note="On Pi, wrong default device is common after USB reconnect.",
        actions=(
            SuggestedAction("check_device", "Check input device", "Wrong input looks like silence"),
            SuggestedAction("retry", "Retry with a harder tap", "Need a measurable impulse"),
            SuggestedAction("run_setup", "Run setup wizard", "Persist the right device"),
        ),
    ),
    "Q003": RuleMessageSpec(
        rule_id="Q003",
        severity=Severity.HARD,
        operator_explanation="The analyzer couldn't identify a clear resonance in the capture.",
        why_it_matters="No clear peak means the measurement can't be trusted.",
        first_fix="Improve coupling: consistent support point, reduce room noise.",
        fallback_fix="Increase capture duration slightly (e.g., 2.5s → 4s).",
        advanced_note="If peak range excludes the true mode, adjust analysis config later—avoid changing during baseline.",
        actions=(
            SuggestedAction("retry", "Retry with better coupling", "Cleaner impulse yields clear peaks"),
            SuggestedAction("adjust_duration_up", "Increase duration and retry", "Gives more usable decay"),
            SuggestedAction("help", "Show tapping tips", "Reduce operator variability"),
        ),
    ),
    "Q004": RuleMessageSpec(
        rule_id="Q004",
        severity=Severity.HARD,
        operator_explanation="Peak detection confidence is too low for a reliable reading.",
        why_it_matters="Low confidence often means noise, clipping, or weak coupling.",
        first_fix="Retry after addressing signal level and coupling.",
        fallback_fix="Try a second capture to confirm repeatability.",
        advanced_note="If confidence is consistently low, check environment noise and mic placement.",
        actions=(
            SuggestedAction("retry", "Retry capture", "Need higher confidence"),
            SuggestedAction("check_environment", "Reduce noise and retry", "Noise lowers confidence"),
            SuggestedAction("abort", "Abort", "Cannot proceed under threshold"),
        ),
    ),
    "Q005": RuleMessageSpec(
        rule_id="Q005",
        severity=Severity.HARD,
        operator_explanation="The capture sample rate is not supported by policy.",
        why_it_matters="Non-standard rates can break comparability across sessions.",
        first_fix="Switch to 48k or 44.1k and retry.",
        fallback_fix="Run setup wizard to save a compatible device/rate combination.",
        advanced_note="If the device rejects rates, fall back to its supported default.",
        actions=(
            SuggestedAction("set_samplerate_standard", "Use 48k and retry", "Policy-approved rate"),
            SuggestedAction("run_setup", "Run setup wizard", "Persist correct rate"),
            SuggestedAction("abort", "Abort", "Cannot proceed with non-standard rate"),
        ),
    ),
    # SOFT
    "Q010": RuleMessageSpec(
        rule_id="Q010",
        severity=Severity.SOFT,
        operator_explanation="Signal is quiet. This may still be usable, but repeatability can suffer.",
        why_it_matters="Quiet signals are more sensitive to noise and coupling variation.",
        first_fix="Increase gain slightly or tap closer.",
        fallback_fix="Retake once to see if confidence improves.",
        advanced_note="If confidence remains high, accepting is usually fine.",
        actions=(
            SuggestedAction("accept", "Accept with warning", "Measurement may still be valid"),
            SuggestedAction("retry", "Retry with slightly higher level", "Improve repeatability"),
        ),
    ),
    "Q011": RuleMessageSpec(
        rule_id="Q011",
        severity=Severity.SOFT,
        operator_explanation="Signal is near clipping. This capture is usable, but margin is small.",
        why_it_matters="A slightly harder tap could clip and invalidate the next capture.",
        first_fix="Reduce gain slightly, then retake for safety margin.",
        fallback_fix="Accept if consistent and confidence is strong.",
        advanced_note="Aim for headroom; avoid any automatic mic boost features.",
        actions=(
            SuggestedAction("retry", "Retry with slightly lower gain", "Avoid clipping next attempt"),
            SuggestedAction("accept", "Accept with warning", "Current capture is not clipped"),
        ),
    ),
    "Q012": RuleMessageSpec(
        rule_id="Q012",
        severity=Severity.SOFT,
        operator_explanation="Confidence is marginal. The reading may be correct but less stable.",
        why_it_matters="Low stability increases the chance of drift between attempts.",
        first_fix="Retry once to see if confidence improves.",
        fallback_fix="Accept if the dominant peak repeats across attempts.",
        advanced_note="If repeated, treat as environment/coupling problem rather than algorithm error.",
        actions=(
            SuggestedAction("retry", "Retry once", "Try for higher confidence"),
            SuggestedAction("accept", "Accept with warning", "If repeatable, usable"),
        ),
    ),
    "Q013": RuleMessageSpec(
        rule_id="Q013",
        severity=Severity.SOFT,
        operator_explanation="Only a few peaks were detected.",
        why_it_matters="Can indicate weak coupling or insufficient excitation of modes.",
        first_fix="Tap with firmer coupling and ensure consistent support.",
        fallback_fix="Accept if the dominant frequency is stable across attempts.",
        advanced_note="Not necessarily bad; some structures naturally show fewer peaks.",
        actions=(
            SuggestedAction("retry", "Retry with improved coupling", "May reveal clearer peak structure"),
            SuggestedAction("accept", "Accept with warning", "Dominant peak may still be valid"),
        ),
    ),
}


# -----------------------------------------------------------------------------
# FTUE stage inference + selection rules
# -----------------------------------------------------------------------------

def infer_user_stage(ctx: AgentContext) -> UserStage:
    """
    Deterministic FTUE inference. You can replace this later with persisted user profile.
    """
    if ctx.expert_mode:
        return "expert"
    if ctx.user_stage is not None:
        return ctx.user_stage
    # Simple default inference:
    if ctx.pass_count_lifetime <= 0:
        return "first_run"
    if ctx.session_count_lifetime < 5 or ctx.pass_count_lifetime < 10:
        return "novice"
    return "regular"


def _rule_id(tr: TriggeredRule) -> str:
    return tr.rule.rule_id


def _severity(tr: TriggeredRule) -> Severity:
    return tr.rule.severity


def sort_triggered_rules(triggered: Sequence[TriggeredRule]) -> List[TriggeredRule]:
    """
    HARD first, then SOFT, then stable by rule_id.
    """
    def key(tr: TriggeredRule) -> tuple[int, str]:
        sev_rank = 0 if tr.rule.severity == Severity.HARD else 1
        return (sev_rank, tr.rule.rule_id)

    return sorted(triggered, key=key)


def _top_k_rules_for_stage(stage: UserStage, sorted_rules: Sequence[TriggeredRule]) -> List[TriggeredRule]:
    if stage == "first_run":
        return list(sorted_rules[:2])  # show only top 1–2
    return list(sorted_rules)


# -----------------------------------------------------------------------------
# Fatigue policy — suppress repeated explanations
# -----------------------------------------------------------------------------

def should_show_learning_hint(ctx: AgentContext, rule_ids: List[str], stage: UserStage) -> bool:
    """
    Show learning hint only if ALL are true:
    1. user is first_run or novice
    2. at least one rule is new (not in seen_rule_ids)
    3. no rule is repeating in-session (count <= 1 for all)
    4. not in expert_mode
    5. workflow is 'measure' (PR6: record=minimal, phase2=experienced)

    This prevents "nagging" when the user has seen the same issue before.
    """
    if ctx.expert_mode:
        return False
    if stage not in ("first_run", "novice"):
        return False
    # PR6 Rule 5: workflow sensitivity
    if ctx.workflow != "measure":
        return False
    if not rule_ids:
        return False
    # At least one rule must be genuinely new
    any_new = any(ctx.is_rule_new(rid) for rid in rule_ids)
    if not any_new:
        return False
    # No rule should be fatiguing (repeated in-session)
    any_fatiguing_in_session = any(ctx.get_rule_count(rid) >= 2 for rid in rule_ids)
    if any_fatiguing_in_session:
        return False
    return True


def should_show_full_explanation(ctx: AgentContext, rule_id: str) -> bool:
    """
    Show full explanation only on first exposure.

    Suppress if:
    - rule repeated in-session (count >= 2), OR
    - rule was previously seen (in seen_rule_ids), OR
    - override_count >= 1 AND user is not first_run (experienced override = concise preference)
    """
    # First-run always gets full explanation on first in-session occurrence
    stage = infer_user_stage(ctx)
    if stage == "first_run" and ctx.get_rule_count(rule_id) <= 1:
        return True
    # Otherwise, suppress if fatiguing
    if ctx.is_rule_fatiguing(rule_id):
        return False
    # Suppress if experienced overrider (unless first_run)
    if ctx.override_count_lifetime >= 1 and stage != "first_run":
        return False
    return True


def _pick_ftue_hint(stage: UserStage, ctx: AgentContext, rule_ids: List[str]) -> Optional[str]:
    hints = FTUE_HINTS.get(stage, ())
    if not hints:
        return None
    # Very simple, deterministic choice:
    # If we hit device/silence problems, prefer setup hint first.
    if "Q002" in rule_ids or "Q005" in rule_ids:
        for h in hints:
            if "setup" in h.lower():
                return h
    return hints[0]


def _merge_actions(
    base: tuple[SuggestedAction, ...],
    rule_actions: List[SuggestedAction],
    *,
    stage: UserStage,
    verdict: Verdict,
    ctx: AgentContext,
    rule_ids: List[str],
) -> tuple[SuggestedAction, ...]:
    """
    Merge verdict default actions with rule-suggested actions deterministically.

    Rules:
    - FAIL: prioritize retry + fix actions. Keep override available (measure workflow), but don't push it early for first_run.
    - WARN: novice -> retry first; regular/expert -> accept first.
    - PASS: advance only.
    - Avoid duplicates by action_id.
    - Escalate if a rule repeats (consecutive hits or count).
    """
    merged: List[SuggestedAction] = []
    seen: set[str] = set()

    def add(act: SuggestedAction) -> None:
        if act.action_id in seen:
            return
        seen.add(act.action_id)
        merged.append(act)

    # Escalation: if repeat rule hit, inject stronger corrective action earlier
    # (still deterministic; no hidden interpretation)
    def repeated(rule_id: str, threshold: int) -> bool:
        return (ctx.get_consecutive_hits(rule_id) >= threshold) or (ctx.get_rule_count(rule_id) >= threshold)

    # Special escalations (PR6: expanded for Q010 and Q003)
    if "Q011" in rule_ids and repeated("Q011", 3):
        add(SuggestedAction("adjust_gain_down", "Lower gain before retrying", "Near-clipping repeated; reduce risk of clipping"))
    if "Q002" in rule_ids and repeated("Q002", 2):
        add(SuggestedAction("check_device", "Check input device", "Silence repeated; likely wrong device"))
        add(SuggestedAction("run_setup", "Run setup wizard", "Persist correct device selection"))
    if "Q010" in rule_ids and repeated("Q010", 3):
        add(SuggestedAction("adjust_gain_up", "Move mic closer and increase gain", "Quiet signal repeated; need stronger input"))
    if "Q003" in rule_ids and repeated("Q003", 3):
        add(SuggestedAction("check_environment", "Retap with firmer coupling; confirm mic", "No peaks repeated; coupling or environment issue"))

    # For FAIL, pull in top rule actions first (more actionable than generic abort/override)
    if verdict == Verdict.FAIL:
        for a in rule_actions:
            add(a)
        # Then add defaults, but soften override prominence for first_run
        for a in base:
            if stage == "first_run" and a.action_id == "override":
                continue
            add(a)
        # First_run: also add help if missing
        if stage == "first_run":
            add(SuggestedAction("help", "Show quick help", "Common fixes for first measurement"))
        return tuple(merged[:4])  # keep concise

    # WARN: reorder accept/retry based on stage
    if verdict == Verdict.WARN:
        # bring in rule actions first, then defaults, then reorder accept/retry
        for a in rule_actions:
            add(a)
        for a in base:
            add(a)
        # reorder: novice/first_run => retry first; regular/expert => accept first
        if stage in ("first_run", "novice"):
            merged.sort(key=lambda a: 0 if a.action_id == "retry" else 1 if a.action_id == "accept" else 2)
        else:
            merged.sort(key=lambda a: 0 if a.action_id == "accept" else 1 if a.action_id == "retry" else 2)
        return tuple(merged[:3])

    # PASS: only defaults (advance)
    for a in base:
        add(a)
    return tuple(merged[:2])


# -----------------------------------------------------------------------------
# Core builder + render helpers
# -----------------------------------------------------------------------------

def build_agent_message(ctx: AgentContext, verdict: QualityVerdict) -> AgentMessage:
    """
    Convert a QualityVerdict into an AgentMessage.

    Deterministic rules:
    - No DSP. No QC edits.
    - Select rule explanations from RULE_SPECS keyed by rule_id.
    - Progressive disclosure via user stage.
    - Stable action ordering.
    """
    stage = infer_user_stage(ctx)
    tpl = VERDICT_TEMPLATES[verdict.verdict]

    triggered_sorted = sort_triggered_rules(verdict.triggered_rules or [])
    rule_ids = [_rule_id(tr) for tr in triggered_sorted]

    show_details = ctx.show_details and (stage != "first_run" or ctx.workflow != "record")
    # (first_run record: keep minimal unless UI expands)

    # Details (PR6: three-tier explanation mode + verdict streak suppression)
    details: List[str] = []
    top_rules = _top_k_rules_for_stage(stage, triggered_sorted)
    verdict_streak_suppress = should_suppress_for_verdict_streak(ctx)

    if show_details and top_rules:
        for tr in top_rules:
            rid = _rule_id(tr)
            spec = RULE_SPECS.get(rid)
            if spec is None:
                # fallback: use the QC message directly
                sev = "ERROR" if _severity(tr) == Severity.HARD else "WARN"
                details.append(f"[{sev}] {rid}: {tr.message}")
                continue

            sev = "ERROR" if spec.severity == Severity.HARD else "WARN"

            # PR6 Rule 4: verdict streak ≥ 3 → action-only
            if verdict_streak_suppress:
                details.append(f"[{sev}] {rid}: {spec.first_fix}")
                continue

            # PR6 Rule 5: phase2 forces compact
            if ctx.workflow == "phase2":
                details.append(f"[{sev}] {rid}: {spec.first_fix}")
                continue

            # PR6 Rule 2: three-tier explanation mode
            mode = choose_explanation_mode(ctx, rid)

            if mode == ExplanationMode.COMPACT:
                # Heavy repetition — just the fix
                details.append(f"[{sev}] {rid}: Same issue — {spec.first_fix}")
            elif mode == ExplanationMode.SHORT:
                # Seen before — one-line explanation + fix
                details.append(f"[{sev}] {rid}: {spec.operator_explanation}")
            elif stage in ("first_run", "novice"):
                # FULL for novice/first_run: physical-action oriented
                details.append(f"[{sev}] {rid}: {spec.operator_explanation}")
                details.append(f"      Fix: {spec.first_fix}")
            elif stage == "expert":
                details.append(f"[{sev}] {rid}: {spec.operator_explanation}")
                details.append(f"      Why: {spec.why_it_matters}")
                details.append(f"      Fix: {spec.first_fix}  (Fallback: {spec.fallback_fix})")
            else:  # regular, FULL mode
                details.append(f"[{sev}] {rid}: {spec.operator_explanation}")
                details.append(f"      Fix: {spec.first_fix}")

    # Build rule action suggestions: take top rule's actions (most actionable) + any additional if multiple HARD
    rule_actions: List[SuggestedAction] = []
    for tr in top_rules:
        rid = _rule_id(tr)
        spec = RULE_SPECS.get(rid)
        if not spec:
            continue
        rule_actions.extend(spec.actions)

    suggested_actions = _merge_actions(
        base=tpl.default_actions,
        rule_actions=rule_actions,
        stage=stage,
        verdict=verdict.verdict,
        ctx=ctx,
        rule_ids=rule_ids,
    )

    # Learning hint (FTUE only, with fatigue suppression)
    learning_hint = None
    if should_show_learning_hint(ctx, rule_ids, stage):
        learning_hint = _pick_ftue_hint(stage, ctx, rule_ids)

    # Summary tweaks (contextual but non-interpretive)
    summary = tpl.summary
    if ctx.point_id:
        summary = f"{summary} (Point: {ctx.point_id}, attempt {ctx.attempt_num}/{max(ctx.max_attempts, 1)})"
    elif ctx.max_attempts > 1:
        summary = f"{summary} (Attempt {ctx.attempt_num}/{ctx.max_attempts})"

    # Telemetry tags (as frozen tuple)
    telemetry = (
        ("rule_ids", tuple(rule_ids)),
        ("verdict", verdict.verdict.value),
        ("user_stage", stage),
        ("workflow", ctx.workflow),
        ("attempt_num", ctx.attempt_num),
        ("max_attempts", ctx.max_attempts),
        ("device_name", ctx.device_name),
        ("sample_rate", ctx.sample_rate),
        ("policy_version", ctx.policy_version),
    )

    # For first_run, keep details minimal unless explicitly requested
    if stage == "first_run" and ctx.workflow in ("record", "measure") and not ctx.show_details:
        details = []

    return AgentMessage(
        title=tpl.title,
        summary=summary,
        details=tuple(details),
        suggested_actions=suggested_actions,
        learning_hint=learning_hint,
        telemetry_tags=telemetry,
    )


def render_agent_message_cli(msg: AgentMessage, *, color: bool = False) -> str:
    """
    Render AgentMessage for CLI output.
    
    Args:
        msg: The AgentMessage to render
        color: Whether to include ANSI color codes (default False for deterministic output)
    """
    lines: List[str] = []
    
    title = msg.title
    if color:
        verdict = msg.get_tag("verdict")
        if verdict == "fail":
            title = f"\033[31m{title}\033[0m"  # Red
        elif verdict == "warn":
            title = f"\033[33m{title}\033[0m"  # Yellow
        elif verdict == "pass":
            title = f"\033[32m{title}\033[0m"  # Green
    
    lines.append(title)
    lines.append(msg.summary)

    if msg.details:
        lines.append("")
        lines.extend(msg.details)

    if msg.suggested_actions:
        lines.append("")
        lines.append("Suggested actions:")
        for i, a in enumerate(msg.suggested_actions, 1):
            suffix = " (requires input)" if a.requires_input else ""
            lines.append(f"  {i}. {a.label}{suffix} — {a.rationale}")

    if msg.learning_hint:
        lines.append("")
        hint = msg.learning_hint
        if color:
            hint = f"\033[36m{hint}\033[0m"  # Cyan
        lines.append(hint)

    return "\n".join(lines)


def format_verdict_summary_agent(ctx: AgentContext, verdict: QualityVerdict) -> str:
    """
    Plug-in replacement/augmenter for existing format_verdict_summary() output.

    If you want to keep the old summary too, call both and concatenate:
        old = format_verdict_summary(verdict)
        new = format_verdict_summary_agent(ctx, verdict)
    """
    return render_agent_message_cli(build_agent_message(ctx, verdict))


__all__ = [
    "AgentContext",
    "AgentMessage",
    "SuggestedAction",
    "RuleMessageSpec",
    "VerdictTemplate",
    "ExplanationMode",
    "RULE_SPECS",
    "VERDICT_TEMPLATES",
    "FTUE_HINTS",
    "infer_user_stage",
    "sort_triggered_rules",
    "choose_explanation_mode",
    "should_suppress_for_verdict_streak",
    "build_agent_message",
    "render_agent_message_cli",
    "format_verdict_summary_agent",
]
