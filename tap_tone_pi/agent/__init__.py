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

Two integration paths:
1. Standalone (mock-friendly): Use types.py + message_spec.py + MeasurementAgent
2. Integrated (real QC types): Use messages.py with build_agent_message(ctx, verdict)
"""

# Standalone types (usable without importing quality_policy)
from .types import (
    ActionId,
    AgentContext as StandaloneAgentContext,
    AgentMessage as StandaloneAgentMessage,
    SuggestedAction as StandaloneSuggestedAction,
    UserStage,
)
from .message_spec import (
    RULE_SPECS as STANDALONE_RULE_SPECS,
    VERDICT_TEMPLATES as STANDALONE_VERDICT_TEMPLATES,
    RuleSpec,
    VerdictTemplate as StandaloneVerdictTemplate,
    get_rule_spec,
    get_verdict_template,
)
from .ftue import (
    FTUE_HINTS as STANDALONE_FTUE_HINTS,
    get_ftue_hint,
    infer_user_stage as standalone_infer_user_stage,
    max_rules_to_show,
    max_actions_to_show,
    show_why_it_matters,
    show_advanced_note,
    show_metrics,
)
from .selector import (
    ExplanationMode,
    order_rules,
    select_actions_for_verdict,
    build_rule_detail,
    choose_explanation_mode as standalone_choose_explanation_mode,
    should_suppress_for_verdict_streak as standalone_should_suppress_for_verdict_streak,
    should_show_learning_hint_standalone,
)
from .render import (
    render_cli,
    render_gui,
    render_compact,
)
from .measurement_agent import (
    MeasurementAgent,
    build_agent_message as standalone_build_agent_message,
)

# Integrated types (uses real quality_policy types)
from .messages import (
    AgentContext,
    AgentMessage,
    SessionTracker,
    SuggestedAction,
    RuleMessageSpec,
    VerdictTemplate,
    RULE_SPECS,
    VERDICT_TEMPLATES,
    FTUE_HINTS,
    infer_user_stage,
    sort_triggered_rules,
    choose_explanation_mode,
    should_suppress_for_verdict_streak,
    build_agent_message,
    render_agent_message_cli,
    format_verdict_summary_agent,
)

__all__ = [
    # Integrated API (preferred for production use)
    "AgentContext",
    "AgentMessage",
    "SessionTracker",
    "SuggestedAction",
    "RuleMessageSpec",
    "VerdictTemplate",
    "RULE_SPECS",
    "VERDICT_TEMPLATES",
    "FTUE_HINTS",
    "infer_user_stage",
    "sort_triggered_rules",
    "build_agent_message",
    "render_agent_message_cli",
    "format_verdict_summary_agent",
    # Standalone API (for testing / mock-friendly use)
    "ActionId",
    "UserStage",
    "StandaloneAgentContext",
    "StandaloneAgentMessage",
    "StandaloneSuggestedAction",
    "RuleSpec",
    "get_rule_spec",
    "get_verdict_template",
    "MeasurementAgent",
    "standalone_build_agent_message",
    "standalone_infer_user_stage",
    "STANDALONE_RULE_SPECS",
    "STANDALONE_VERDICT_TEMPLATES",
    "STANDALONE_FTUE_HINTS",
    "StandaloneVerdictTemplate",
    # FTUE helpers
    "get_ftue_hint",
    "max_rules_to_show",
    "max_actions_to_show",
    "show_why_it_matters",
    "show_advanced_note",
    "show_metrics",
    # Selector helpers
    "ExplanationMode",
    "order_rules",
    "select_actions_for_verdict",
    "build_rule_detail",
    "standalone_choose_explanation_mode",
    "standalone_should_suppress_for_verdict_streak",
    "should_show_learning_hint_standalone",
    # Integrated PR6
    "choose_explanation_mode",
    "should_suppress_for_verdict_streak",
    # Renderers
    "render_cli",
    "render_gui",
    "render_compact",
]
