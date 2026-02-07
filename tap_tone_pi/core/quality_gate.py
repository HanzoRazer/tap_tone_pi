"""Quality Gate for tap-tone-pi measurements.

Applies quality policy rules to analysis results and returns a verdict.
This is the enforcement layer — policy is defined in quality_policy.py.
"""
from __future__ import annotations

import numpy as np

from tap_tone_pi.core.analysis import AnalysisResult
from tap_tone_pi.core.quality_policy import (
    Verdict,
    Severity,
    QualityThresholds,
    QualityVerdict,
    TriggeredRule,
    DEFAULT_THRESHOLDS,
    Q001_CLIPPED,
    Q002_SILENT,
    Q003_NO_PEAKS,
    Q004_LOW_CONFIDENCE,
    Q005_INVALID_SAMPLE_RATE,
    Q010_QUIET,
    Q011_NEAR_CLIPPING,
    Q012_MARGINAL_CONFIDENCE,
    Q013_FEW_PEAKS,
)


def check_quality(
    analysis: AnalysisResult,
    sample_rate: int,
    audio: np.ndarray | None = None,
    thresholds: QualityThresholds | None = None,
) -> QualityVerdict:
    """
    Check measurement quality against policy rules.

    Args:
        analysis: The AnalysisResult from analyze_tap()
        sample_rate: Sample rate used for capture
        audio: Raw audio array (optional, for peak level check)
        thresholds: Custom thresholds (defaults to DEFAULT_THRESHOLDS)

    Returns:
        QualityVerdict with verdict and any triggered rules
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    triggered: list[TriggeredRule] = []

    # Calculate peak level if audio provided
    peak_level = float(np.max(np.abs(audio))) if audio is not None else None

    # =========================================================================
    # HARD RULES — Any trigger = FAIL
    # =========================================================================

    # Q001: Clipping
    if analysis.clipped:
        triggered.append(TriggeredRule(
            rule=Q001_CLIPPED,
            message=Q001_CLIPPED.message,
        ))

    # Q002: Silent (no signal)
    if analysis.rms < thresholds.rms_silent:
        triggered.append(TriggeredRule(
            rule=Q002_SILENT,
            message=Q002_SILENT.message,
        ))

    # Q003: No peaks / no dominant frequency
    if analysis.dominant_hz is None:
        triggered.append(TriggeredRule(
            rule=Q003_NO_PEAKS,
            message=Q003_NO_PEAKS.message,
        ))

    # Q004: Low confidence
    if analysis.confidence < thresholds.confidence_fail:
        triggered.append(TriggeredRule(
            rule=Q004_LOW_CONFIDENCE,
            message=Q004_LOW_CONFIDENCE.message,
        ))

    # Q005: Invalid sample rate
    if sample_rate not in thresholds.valid_sample_rates:
        triggered.append(TriggeredRule(
            rule=Q005_INVALID_SAMPLE_RATE,
            message=Q005_INVALID_SAMPLE_RATE.message,
        ))

    # =========================================================================
    # SOFT RULES — Trigger = WARN (only if no FAIL)
    # =========================================================================

    # Q010: Quiet signal (but not silent)
    if analysis.rms >= thresholds.rms_silent and analysis.rms < thresholds.rms_quiet:
        triggered.append(TriggeredRule(
            rule=Q010_QUIET,
            message=Q010_QUIET.message,
        ))

    # Q011: Near clipping
    if peak_level is not None and peak_level > thresholds.peak_near_clipping and not analysis.clipped:
        triggered.append(TriggeredRule(
            rule=Q011_NEAR_CLIPPING,
            message=Q011_NEAR_CLIPPING.message,
        ))

    # Q012: Marginal confidence (but above fail threshold)
    if thresholds.confidence_fail <= analysis.confidence < thresholds.confidence_marginal:
        triggered.append(TriggeredRule(
            rule=Q012_MARGINAL_CONFIDENCE,
            message=Q012_MARGINAL_CONFIDENCE.message,
        ))

    # Q013: Few peaks
    peak_count = len(analysis.peaks) if analysis.peaks else 0
    if 0 < peak_count < thresholds.min_peaks_expected:
        triggered.append(TriggeredRule(
            rule=Q013_FEW_PEAKS,
            message=Q013_FEW_PEAKS.message.format(peak_count=peak_count),
        ))

    # =========================================================================
    # Determine final verdict
    # =========================================================================

    has_hard_fail = any(r.rule.severity == Severity.HARD for r in triggered)
    has_soft_warn = any(r.rule.severity == Severity.SOFT for r in triggered)

    if has_hard_fail:
        verdict = Verdict.FAIL
    elif has_soft_warn:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.PASS

    return QualityVerdict(
        verdict=verdict,
        triggered_rules=triggered,
    )


def format_verdict_summary(verdict: QualityVerdict) -> str:
    """
    Format a human-readable summary of the quality verdict.

    Args:
        verdict: QualityVerdict to format

    Returns:
        Multi-line string summary
    """
    lines = []

    # Header with verdict
    if verdict.verdict == Verdict.PASS:
        lines.append("[PASS] Measurement quality OK")
    elif verdict.verdict == Verdict.WARN:
        lines.append(f"[WARN] Measurement has {len(verdict.warnings)} warning(s)")
    else:
        lines.append(f"[FAIL] Measurement failed {len(verdict.errors)} check(s)")

    # List triggered rules
    if verdict.triggered_rules:
        lines.append("")
        for tr in verdict.triggered_rules:
            severity_marker = "ERROR" if tr.rule.severity == Severity.HARD else "WARN"
            lines.append(f"  [{severity_marker}] {tr.rule.rule_id}: {tr.message}")

    return "\n".join(lines)


def can_proceed(verdict: QualityVerdict, allow_warnings: bool = True) -> bool:
    """
    Check if workflow can proceed given the verdict.

    Args:
        verdict: QualityVerdict to check
        allow_warnings: If True, WARN verdicts can proceed

    Returns:
        True if workflow can proceed
    """
    if verdict.verdict == Verdict.FAIL:
        return False
    if verdict.verdict == Verdict.WARN and not allow_warnings:
        return False
    return True


__all__ = [
    "check_quality",
    "format_verdict_summary",
    "can_proceed",
]
