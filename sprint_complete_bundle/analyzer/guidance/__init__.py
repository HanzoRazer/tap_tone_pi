"""
analyzer.guidance — Viewer-side guidance engine (DECISION SUPPORT).

Exports:
    AnalyzerGuidanceEngine  — emits AttentionDirectiveV1 from analyzer events
    GuidancePanelWidget     — QDockWidget that renders those directives

See docs/ADR-0009-advisory-boundary.md for the measurement boundary contract.
"""

from analyzer.guidance.engine import AnalyzerGuidanceEngine

try:
    from analyzer.guidance.panel import GuidancePanelWidget
    __all__ = ["AnalyzerGuidanceEngine", "GuidancePanelWidget"]
except ImportError:
    # PyQt6 not installed — engine is still usable (tests, CI)
    __all__ = ["AnalyzerGuidanceEngine"]
