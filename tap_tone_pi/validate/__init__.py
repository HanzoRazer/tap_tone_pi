"""
Validation utilities for tap_tone_pi.

This package contains deterministic, offline validators used by CLI tooling.
"""

from __future__ import annotations

from tap_tone_pi.validate.evidence_check import (
    EvidenceReport,
    Finding,
    FindingSeverity,
    scan_session,
)

__all__ = ["EvidenceReport", "Finding", "FindingSeverity", "scan_session"]
