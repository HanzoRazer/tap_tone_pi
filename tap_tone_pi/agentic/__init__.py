# INSTRUMENT CLASS: DECISION SUPPORT
"""
Agentic Layer — tap_tone_pi

Cross-repo contracts for agent orchestration with luthiers-toolbox.
These contracts define the "thin waist" between the desktop analyzer
and the ToolBox experience shell.

This module provides:
1. Contracts: Shared schemas matching luthiers-toolbox/app/agentic/contracts
2. Capabilities: Declaration of what this analyzer can do
3. Events: Event emission utilities for agent coordination

Design principles:
- Contracts are the ONLY coupling between repos
- Privacy by default (events respect privacy layers)
- Safe defaults are explicit and auditable
- Event vocabulary is unified across all repos

Usage:
    from tap_tone_pi.agentic import get_capabilities, emit_event
    from tap_tone_pi.agentic.contracts import AgentEventV1, EventType
"""

__version__ = "1.0.0"

# Re-export contracts
from .contracts import (
    # Tool Capability
    ToolCapabilityV1,
    CapabilityAction,
    SafeDefaults,
    # Analyzer Attention
    AttentionDirectiveV1,
    AttentionAction,
    FocusTarget,
    # Event Emission
    AgentEventV1,
    EventType,
    EventSource,
)

# Re-export capabilities
from .capabilities import (
    get_capabilities,
    get_capability_by_id,
    TAP_TONE_ANALYZER,
    WOLF_DETECTOR,
    ODS_ANALYZER,
    CHLADNI_ANALYZER,
)

# Re-export event utilities
from .events import (
    emit_event,
    emit_analysis_started,
    emit_analysis_completed,
    emit_analysis_failed,
    emit_attention_requested,
)

__all__ = [
    # Contracts
    "ToolCapabilityV1",
    "CapabilityAction",
    "SafeDefaults",
    "AttentionDirectiveV1",
    "AttentionAction",
    "FocusTarget",
    "AgentEventV1",
    "EventType",
    "EventSource",
    # Capabilities
    "get_capabilities",
    "get_capability_by_id",
    "TAP_TONE_ANALYZER",
    "WOLF_DETECTOR",
    "ODS_ANALYZER",
    "CHLADNI_ANALYZER",
    # Events
    "emit_event",
    "emit_analysis_started",
    "emit_analysis_completed",
    "emit_analysis_failed",
    "emit_attention_requested",
]
