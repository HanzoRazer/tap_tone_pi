# INSTRUMENT CLASS: DECISION SUPPORT
"""
Agentic Layer Contracts — tap_tone_pi

Cross-repo contracts matching luthiers-toolbox/app/agentic/contracts.
Uses stdlib dataclasses for zero external dependencies.

These contracts define the "thin waist" between:
- tap_tone_pi (desktop analyzer)
- luthiers-toolbox (experience shell)
- Agent orchestration layer

Version: 1.0.0
"""

from .tool_capability import (
    ToolCapabilityV1,
    CapabilityAction,
    SafeDefaults,
)

from .analyzer_attention import (
    AttentionDirectiveV1,
    AttentionAction,
    FocusTarget,
)

from .event_emission import (
    AgentEventV1,
    EventType,
    EventSource,
)

from .advisory_authority import (
    AuthorityClass,
    GuidanceScope,
    AdvisoryAuthorityV1,
    AGE_ATTENTION_AUTHORITY,
    AGE_EXPLANATION_AUTHORITY,
    AGE_WORKFLOW_AUTHORITY,
)

from .confidence_domain import (
    ConfidenceDomain,
    TypedConfidenceV1,
    MEASUREMENT_DOMAINS,
    ADVISORY_DOMAINS,
)

__all__ = [
    # Tool Capability
    "ToolCapabilityV1",
    "CapabilityAction",
    "SafeDefaults",
    # Analyzer Attention
    "AttentionDirectiveV1",
    "AttentionAction",
    "FocusTarget",
    # Event Emission
    "AgentEventV1",
    "EventType",
    "EventSource",
    # Advisory Authority
    "AuthorityClass",
    "GuidanceScope",
    "AdvisoryAuthorityV1",
    "AGE_ATTENTION_AUTHORITY",
    "AGE_EXPLANATION_AUTHORITY",
    "AGE_WORKFLOW_AUTHORITY",
    # Confidence Domain
    "ConfidenceDomain",
    "TypedConfidenceV1",
    "MEASUREMENT_DOMAINS",
    "ADVISORY_DOMAINS",
]
