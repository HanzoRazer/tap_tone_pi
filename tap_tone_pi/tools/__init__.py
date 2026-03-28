"""
tap_tone_pi.tools — Utility tools and generators.

This module provides standalone tools that support the measurement workflow:
- PDF grid template generator for shop floor printouts
- (Future) Calibration report generator
- (Future) Session comparison tool
"""

from tap_tone_pi.tools.grid_template_pdf import (
    generate_grid_pdf,
    TemplateConfig,
    add_grid_template_subcommand,
)

__all__ = [
    "generate_grid_pdf",
    "TemplateConfig",
    "add_grid_template_subcommand",
]
