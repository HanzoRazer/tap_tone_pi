"""
Tap Tone Analyzer Capability Declarations

Declares what this analyzer can do for agent discovery.
This is the authoritative source — luthiers-toolbox mirrors this.
"""

from __future__ import annotations

from typing import List, Optional

from .contracts import (
    ToolCapabilityV1,
    CapabilityAction,
    SafeDefaults,
)


# -----------------------------------------------------------------------------
# Main Analyzer Capability
# -----------------------------------------------------------------------------

TAP_TONE_ANALYZER = ToolCapabilityV1(
    tool_id="tap_tone_analyzer",
    version="2.0.0",  # Matches pyproject.toml
    display_name="Tap Tone Analyzer",
    description=(
        "Analyzes acoustic tap tone recordings to identify resonant modes, "
        "wolf tones, and tonal characteristics of instrument bodies. "
        "Produces structured analysis artifacts including mode identification, "
        "ODS snapshots, and wolf candidate detection."
    ),
    actions=[
        CapabilityAction.ANALYZE_AUDIO,
        CapabilityAction.ANALYZE_SPECTRUM,
        CapabilityAction.GENERATE_REPORT,
        CapabilityAction.VALIDATE_SCHEMA,
    ],
    input_schemas=[
        "tap_tone_bundle_v1",
        "audio_wav",
        "phase2_session_meta_v1",
        "phase2_point_capture_meta_v1",
    ],
    output_schemas=[
        "wolf_candidates_v1",
        "mode_analysis_v1",
        "ods_snapshot_v1",
        "chladni_run_v1",
        "moe_result_v1",
        "viewer_pack_v1",
    ],
    safe_defaults=SafeDefaults(
        redaction_layer=2,
        pii_scrub_enabled=True,
        dry_run=False,  # Analysis is read-only
        require_confirmation=False,  # Non-destructive
        timeout_seconds=120,
        max_output_size_bytes=50_000_000,  # 50MB for viewer packs
    ),
    tags=[
        "acoustic",
        "analysis",
        "tap_tone",
        "modal_analysis",
        "wolf_tone",
        "instrument",
        "guitar",
        "violin",
    ],
    source_repo="tap_tone_pi",
)


# -----------------------------------------------------------------------------
# Sub-Capabilities (Pipeline Stages)
# -----------------------------------------------------------------------------

WOLF_DETECTOR = ToolCapabilityV1(
    tool_id="tap_tone_wolf_detector",
    version="2.0.0",
    display_name="Wolf Tone Detector",
    description=(
        "Detects potential wolf tone frequencies in tap tone recordings. "
        "Identifies problematic resonances that may cause tonal issues."
    ),
    actions=[CapabilityAction.ANALYZE_SPECTRUM],
    input_schemas=["phase2_grid_v1"],
    output_schemas=["wolf_candidates_v1"],
    safe_defaults=SafeDefaults(
        redaction_layer=2,
        timeout_seconds=60,
    ),
    tags=["wolf_tone", "spectrum", "analysis"],
    source_repo="tap_tone_pi",
)


ODS_ANALYZER = ToolCapabilityV1(
    tool_id="tap_tone_ods_analyzer",
    version="2.0.0",
    display_name="ODS Analyzer",
    description=(
        "Generates Operating Deflection Shape (ODS) snapshots from tap tone data. "
        "Visualizes how the instrument body moves at specific frequencies."
    ),
    actions=[
        CapabilityAction.ANALYZE_AUDIO,
        CapabilityAction.GENERATE_PREVIEW,
    ],
    input_schemas=["phase2_grid_v1"],
    output_schemas=["ods_snapshot_v1"],
    safe_defaults=SafeDefaults(
        redaction_layer=2,
        timeout_seconds=90,
    ),
    tags=["ods", "deflection", "visualization"],
    source_repo="tap_tone_pi",
)


CHLADNI_ANALYZER = ToolCapabilityV1(
    tool_id="tap_tone_chladni_analyzer",
    version="2.0.0",
    display_name="Chladni Pattern Analyzer",
    description=(
        "Analyzes Chladni patterns from tap tone grid data. "
        "Identifies nodal lines and resonant mode shapes."
    ),
    actions=[
        CapabilityAction.ANALYZE_AUDIO,
        CapabilityAction.GENERATE_PREVIEW,
    ],
    input_schemas=["phase2_grid_v1"],
    output_schemas=["chladni_run_v1"],
    safe_defaults=SafeDefaults(
        redaction_layer=2,
        timeout_seconds=120,
    ),
    tags=["chladni", "modal", "visualization"],
    source_repo="tap_tone_pi",
)


WOLF_BEAT_ADVISOR = ToolCapabilityV1(
    tool_id="tap_tone_wolf_advisor",
    version="2.0.0",
    display_name="Wolf Beat Advisor",
    description=(
        "Physics-based decision support for wolf tone mitigation. "
        "Uses dimensionless avoided-crossing model to analyze coupled "
        "string-body oscillator behavior and generate prioritized "
        "mitigation recommendations (mass addition, damping, structural). "
        "Provides operator guidance, NOT autonomous decisions."
    ),
    actions=[
        CapabilityAction.ANALYZE_SPECTRUM,
        CapabilityAction.GENERATE_REPORT,
    ],
    input_schemas=["wolf_beat_analysis_v1"],
    output_schemas=["wolf_advisor_result_v1", "wolf_directive_v1"],
    safe_defaults=SafeDefaults(
        redaction_layer=2,
        timeout_seconds=30,
        require_confirmation=True,  # Advisory requires operator review
    ),
    tags=[
        "wolf_tone",
        "decision_support",
        "mitigation",
        "physics",
        "coupled_oscillator",
        "avoided_crossing",
    ],
    source_repo="tap_tone_pi",
)


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------

_ALL_CAPABILITIES = [
    TAP_TONE_ANALYZER,
    WOLF_DETECTOR,
    ODS_ANALYZER,
    CHLADNI_ANALYZER,
    WOLF_BEAT_ADVISOR,
]


def get_capabilities() -> List[ToolCapabilityV1]:
    """Return all capabilities for agent discovery."""
    return _ALL_CAPABILITIES.copy()


def get_capability_by_id(tool_id: str) -> Optional[ToolCapabilityV1]:
    """Look up a specific capability by ID."""
    for cap in _ALL_CAPABILITIES:
        if cap.tool_id == tool_id:
            return cap
    return None
