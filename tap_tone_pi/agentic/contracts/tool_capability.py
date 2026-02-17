"""
Tool Capability Contract v1

Declares what each tool/analyzer can do in a cross-repo discoverable way.
Uses stdlib dataclasses for zero external dependencies.

Mirrors: luthiers-toolbox/app/agentic/contracts/tool_capability.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class CapabilityAction(str, Enum):
    """
    Actions a tool can perform.

    Categories:
    - ANALYZE_*: Read-only analysis operations
    - GENERATE_*: Creates new artifacts
    - VALIDATE_*: Checks conformance to spec
    - TRANSFORM_*: Modifies existing data
    """

    # Analysis (read-only)
    ANALYZE_AUDIO = "analyze_audio"
    ANALYZE_GEOMETRY = "analyze_geometry"
    ANALYZE_TOOLPATH = "analyze_toolpath"
    ANALYZE_SPECTRUM = "analyze_spectrum"

    # Generation (creates artifacts)
    GENERATE_REPORT = "generate_report"
    GENERATE_GCODE = "generate_gcode"
    GENERATE_DXF = "generate_dxf"
    GENERATE_PREVIEW = "generate_preview"

    # Validation (conformance checks)
    VALIDATE_SCHEMA = "validate_schema"
    VALIDATE_FEASIBILITY = "validate_feasibility"
    VALIDATE_SAFETY = "validate_safety"

    # Transformation (modifies data)
    TRANSFORM_NORMALIZE = "transform_normalize"
    TRANSFORM_REDACT = "transform_redact"
    TRANSFORM_AGGREGATE = "transform_aggregate"


@dataclass(frozen=True)
class SafeDefaults:
    """
    Explicit safe defaults for tool operation.

    These defaults are chosen for safety over performance.
    Agents can override, but must do so explicitly.
    """

    # Privacy defaults
    redaction_layer: int = 3  # 0=ephemeral, 5=cohort-only
    pii_scrub_enabled: bool = True

    # Safety defaults
    dry_run: bool = True
    require_confirmation: bool = True

    # Resource defaults
    timeout_seconds: int = 30
    max_output_size_bytes: int = 10_000_000  # 10MB


@dataclass(frozen=True)
class ToolCapabilityV1:
    """
    Declares what a tool can do.

    This contract is published by each tool repo and consumed by
    the agent orchestration layer.

    Example (tap_tone_pi analyzer):
        ToolCapabilityV1(
            tool_id="tap_tone_analyzer",
            version="1.0.0",
            display_name="Tap Tone Analyzer",
            actions=[CapabilityAction.ANALYZE_AUDIO, CapabilityAction.ANALYZE_SPECTRUM],
            input_schemas=["tap_tone_bundle_v1", "audio_wav"],
            output_schemas=["wolf_candidates_v1", "mode_analysis_v1"],
        )
    """

    # Identity
    tool_id: str
    version: str
    display_name: str

    # Capabilities
    actions: List[CapabilityAction]
    input_schemas: List[str] = field(default_factory=list)
    output_schemas: List[str] = field(default_factory=list)

    # Safety
    safe_defaults: SafeDefaults = field(default_factory=SafeDefaults)

    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # Cross-repo coordination
    source_repo: str = "tap_tone_pi"
    requires_repos: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "tool_id": self.tool_id,
            "version": self.version,
            "display_name": self.display_name,
            "actions": [a.value for a in self.actions],
            "input_schemas": list(self.input_schemas),
            "output_schemas": list(self.output_schemas),
            "safe_defaults": {
                "redaction_layer": self.safe_defaults.redaction_layer,
                "pii_scrub_enabled": self.safe_defaults.pii_scrub_enabled,
                "dry_run": self.safe_defaults.dry_run,
                "require_confirmation": self.safe_defaults.require_confirmation,
                "timeout_seconds": self.safe_defaults.timeout_seconds,
                "max_output_size_bytes": self.safe_defaults.max_output_size_bytes,
            },
            "description": self.description,
            "tags": list(self.tags),
            "source_repo": self.source_repo,
            "requires_repos": list(self.requires_repos),
        }
