# INSTRUMENT CLASS: MEASUREMENT
"""Quality Policy for tap-tone-pi measurements.

Defines hard rules (MUST FAIL) and soft rules (WARN) for quality gating.
This is the single source of truth for measurement quality criteria.

Policy versioning is independent of app versioning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


POLICY_VERSION = "1.0.0"


class Verdict(str, Enum):
    """Quality gate verdict."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class Severity(str, Enum):
    """Rule severity level."""

    HARD = "hard"  # Must fail, cannot override
    SOFT = "soft"  # Warn, can proceed


@dataclass(frozen=True)
class QualityRule:
    """A single quality rule definition."""

    rule_id: str
    severity: Severity
    description: str
    message: str

    def __hash__(self) -> int:
        return hash(self.rule_id)


# =============================================================================
# HARD RULES (Q001-Q009) — Measurement MUST FAIL
# =============================================================================

Q001_CLIPPED = QualityRule(
    rule_id="Q001",
    severity=Severity.HARD,
    description="Audio is clipping",
    message="Signal is clipping. Reduce microphone gain and retry.",
)

Q002_SILENT = QualityRule(
    rule_id="Q002",
    severity=Severity.HARD,
    description="No signal detected",
    message="No audio signal detected (RMS < 0.001). Check microphone connection.",
)

Q003_NO_PEAKS = QualityRule(
    rule_id="Q003",
    severity=Severity.HARD,
    description="No dominant frequency found",
    message="No frequency peaks detected. Ensure specimen was tapped.",
)

Q004_LOW_CONFIDENCE = QualityRule(
    rule_id="Q004",
    severity=Severity.HARD,
    description="Confidence too low",
    message="Measurement confidence below threshold (< 0.3). Retry with better tap.",
)

Q005_INVALID_SAMPLE_RATE = QualityRule(
    rule_id="Q005",
    severity=Severity.HARD,
    description="Non-standard sample rate",
    message="Sample rate must be 44100, 48000, or 96000 Hz.",
)

# =============================================================================
# SOFT RULES (Q010-Q019) — Warning, can proceed
# =============================================================================

Q010_QUIET = QualityRule(
    rule_id="Q010",
    severity=Severity.SOFT,
    description="Signal is quiet",
    message="Signal is quiet (RMS < 0.01). Consider increasing microphone gain.",
)

Q011_NEAR_CLIPPING = QualityRule(
    rule_id="Q011",
    severity=Severity.SOFT,
    description="Signal near clipping",
    message="Signal is near clipping (peak > 0.9). Consider reducing gain.",
)

Q012_MARGINAL_CONFIDENCE = QualityRule(
    rule_id="Q012",
    severity=Severity.SOFT,
    description="Marginal confidence",
    message="Measurement confidence is marginal (0.3-0.5). Consider retaking.",
)

Q013_FEW_PEAKS = QualityRule(
    rule_id="Q013",
    severity=Severity.SOFT,
    description="Few peaks detected",
    message="Only {peak_count} peaks detected. May indicate poor acoustic coupling.",
)

# =============================================================================
# Rule Registry
# =============================================================================

HARD_RULES: List[QualityRule] = [
    Q001_CLIPPED,
    Q002_SILENT,
    Q003_NO_PEAKS,
    Q004_LOW_CONFIDENCE,
    Q005_INVALID_SAMPLE_RATE,
]

SOFT_RULES: List[QualityRule] = [
    Q010_QUIET,
    Q011_NEAR_CLIPPING,
    Q012_MARGINAL_CONFIDENCE,
    Q013_FEW_PEAKS,
]

ALL_RULES: List[QualityRule] = HARD_RULES + SOFT_RULES

RULES_BY_ID: dict[str, QualityRule] = {r.rule_id: r for r in ALL_RULES}


# =============================================================================
# Thresholds
# =============================================================================


@dataclass(frozen=True)
class QualityThresholds:
    """Configurable thresholds for quality rules."""

    # Hard thresholds
    rms_silent: float = 0.001
    confidence_fail: float = 0.3
    valid_sample_rates: tuple[int, ...] = (44100, 48000, 96000)

    # Soft thresholds
    rms_quiet: float = 0.01
    peak_near_clipping: float = 0.9
    confidence_marginal: float = 0.5
    min_peaks_expected: int = 3


# Default thresholds
DEFAULT_THRESHOLDS = QualityThresholds()


@dataclass
class TriggeredRule:
    """A rule that was triggered during quality check."""

    rule: QualityRule
    message: str  # May include formatted values

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule.rule_id,
            "severity": self.rule.severity.value,
            "description": self.rule.description,
            "message": self.message,
        }


@dataclass
class QualityVerdict:
    """Result of a quality check."""

    verdict: Verdict
    triggered_rules: List[TriggeredRule] = field(default_factory=list)
    policy_version: str = POLICY_VERSION

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.PASS

    @property
    def failed(self) -> bool:
        return self.verdict == Verdict.FAIL

    @property
    def warnings(self) -> List[TriggeredRule]:
        return [r for r in self.triggered_rules if r.rule.severity == Severity.SOFT]

    @property
    def errors(self) -> List[TriggeredRule]:
        return [r for r in self.triggered_rules if r.rule.severity == Severity.HARD]

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "policy_version": self.policy_version,
            "triggered_rules": [r.to_dict() for r in self.triggered_rules],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


__all__ = [
    "POLICY_VERSION",
    "Verdict",
    "Severity",
    "QualityRule",
    "QualityThresholds",
    "TriggeredRule",
    "QualityVerdict",
    "DEFAULT_THRESHOLDS",
    "HARD_RULES",
    "SOFT_RULES",
    "ALL_RULES",
    "RULES_BY_ID",
    # Individual rules for direct import
    "Q001_CLIPPED",
    "Q002_SILENT",
    "Q003_NO_PEAKS",
    "Q004_LOW_CONFIDENCE",
    "Q005_INVALID_SAMPLE_RATE",
    "Q010_QUIET",
    "Q011_NEAR_CLIPPING",
    "Q012_MARGINAL_CONFIDENCE",
    "Q013_FEW_PEAKS",
]
