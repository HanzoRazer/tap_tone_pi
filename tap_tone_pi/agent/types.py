"""Agent types — dataclasses for agent responses.

These are the structured outputs the agent produces;
CLI/GUI renders them appropriately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class UserStage(str, Enum):
    """User experience level for progressive disclosure."""
    FIRST_RUN = "first_run"  # Never completed a PASS
    NOVICE = "novice"        # ≤5 sessions or ≤20 captures
    REGULAR = "regular"      # Steady usage
    EXPERT = "expert"        # Explicitly toggled or inferred


class ActionId(str, Enum):
    """Canonical action identifiers."""
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


@dataclass
class SuggestedAction:
    """A recommended action the operator can take."""
    action_id: ActionId
    label: str
    rationale: str
    requires_input: bool = False

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id.value,
            "label": self.label,
            "rationale": self.rationale,
            "requires_input": self.requires_input,
        }


@dataclass
class AgentMessage:
    """Structured agent response for CLI/GUI rendering."""
    title: str
    summary: str
    details: list[str] = field(default_factory=list)
    suggested_actions: list[SuggestedAction] = field(default_factory=list)
    learning_hint: str | None = None
    telemetry_tags: dict = field(default_factory=dict)

    @property
    def severity(self) -> Literal["info", "warn", "error"]:
        """Infer severity from verdict in telemetry."""
        verdict = self.telemetry_tags.get("verdict", "pass")
        if verdict == "fail":
            return "error"
        elif verdict == "warn":
            return "warn"
        return "info"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity,
            "details": self.details,
            "suggested_actions": [a.to_dict() for a in self.suggested_actions],
            "learning_hint": self.learning_hint,
            "telemetry_tags": self.telemetry_tags,
        }


@dataclass
class AgentContext:
    """Minimum context the agent needs to generate messages."""
    user_stage: UserStage = UserStage.REGULAR
    workflow: Literal["record", "measure", "phase2"] = "measure"
    point_id: str = ""
    attempt_num: int = 1
    max_attempts: int = 5
    device_name: str = "default"
    sample_rate: int = 48000
    policy_version: str = "1.0.0"
    
    # History tracking
    rule_counts_session: dict[str, int] = field(default_factory=dict)
    consecutive_same_verdict: int = 0
    consecutive_rule_hits: dict[str, int] = field(default_factory=dict)
    first_time_seen_rules: set[str] = field(default_factory=set)
    _last_verdict: str = ""

    def record_rules(self, rule_ids: list[str], verdict: str = "") -> None:
        """Update history after a verdict.

        Args:
            rule_ids: Rule IDs triggered in this verdict.
            verdict: Verdict string ("pass"/"warn"/"fail") for streak tracking.
                     If empty, verdict streak is not updated (backward compat).
        """
        for rule_id in rule_ids:
            self.rule_counts_session[rule_id] = self.rule_counts_session.get(rule_id, 0) + 1
            self.consecutive_rule_hits[rule_id] = self.consecutive_rule_hits.get(rule_id, 0) + 1
        
        # Reset consecutive counts for rules NOT triggered
        for rid in list(self.consecutive_rule_hits.keys()):
            if rid not in rule_ids:
                self.consecutive_rule_hits[rid] = 0

        # PR7: verdict streak tracking
        if verdict:
            if verdict == self._last_verdict:
                self.consecutive_same_verdict += 1
            else:
                self.consecutive_same_verdict = 1
            self._last_verdict = verdict
