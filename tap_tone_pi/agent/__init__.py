"""Tap Tone Pi Agent Layer.

The agentic layer orchestrates measurement workflows, enforces policy,
and explains outcomes — without altering measurement facts.

Architecture:
    Capture → Analysis → Quality Gate → Artifacts
                             ↑
                      ┌──────┴──────┐
                      │ Agent Layer │
                      │ (this pkg)  │
                      └─────────────┘

The agent:
- Observes: reads verdicts, tracks attempts, knows context
- Sequences: guides operator through workflow states
- Explains: converts rule IDs to operator-facing messages
- Enforces: policy decisions (retry/accept/abort) without modifying results
"""
from .types import (
    ActionId,
    AgentContext,
    AgentMessage,
    SuggestedAction,
    UserStage,
)
from .message_spec import (
    RULE_SPECS,
    VERDICT_TEMPLATES,
    RuleSpec,
    VerdictTemplate,
    get_rule_spec,
    get_verdict_template,
)
from .ftue import (
    FTUE_HINTS,
    get_ftue_hint,
    infer_user_stage,
    max_rules_to_show,
    max_actions_to_show,
    show_why_it_matters,
    show_advanced_note,
    show_metrics,
)
from .selector import (
    order_rules,
    select_actions_for_verdict,
    build_rule_detail,
)
from .render import (
    render_cli,
    render_gui,
    render_compact,
)
from .measurement_agent import (
    MeasurementAgent,
    build_agent_message,
)

__all__ = [
    # Types
    "ActionId",
    "AgentContext",
    "AgentMessage",
    "SuggestedAction",
    "UserStage",
    # Message spec
    "RULE_SPECS",
    "VERDICT_TEMPLATES",
    "RuleSpec",
    "VerdictTemplate",
    "get_rule_spec",
    "get_verdict_template",
    # FTUE
    "FTUE_HINTS",
    "get_ftue_hint",
    "infer_user_stage",
    "max_rules_to_show",
    "max_actions_to_show",
    "show_why_it_matters",
    "show_advanced_note",
    "show_metrics",
    # Selector
    "order_rules",
    "select_actions_for_verdict",
    "build_rule_detail",
    # Render
    "render_cli",
    "render_gui",
    "render_compact",
    # Agent
    "MeasurementAgent",
    "build_agent_message",
]
