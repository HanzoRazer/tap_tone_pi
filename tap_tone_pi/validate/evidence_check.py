"""Evidence preflight validator for session directories.

Answers four questions deterministically:
1. Is this session structurally valid (layout)?
2. Are required artifacts present per attempt/point?
3. Do the JSON artifacts parse and meet minimal invariants?
4. If not, what exactly is missing, where, and what should I do next?

Usage:
    ttp evidence-check --session <dir> [--strict | --fail-on-warn] [--json]

This module has NO DSP, NO advisory logic, NO external deps.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# Types
# =============================================================================


class FindingSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class Finding:
    """A single validation finding.

    Attributes:
        code: Stable identifier (E0xx/E1xx/E2xx).
        severity: info/warn/fail.
        message: Short human-readable description.
        path: Filesystem path (attempt dir or file).
        hint: Optional recommended action (human-friendly).
        meta: Optional machine-friendly details.
    """

    code: str
    severity: FindingSeverity
    message: str
    path: str | None = None
    hint: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.path is not None:
            d["path"] = self.path
        if self.hint is not None:
            d["hint"] = self.hint
        if self.meta:
            d["meta"] = self.meta
        return d


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    """Small summary counts for quick CLI output and exit-code logic."""

    attempts_scanned: int
    fail_count: int
    warn_count: int
    info_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempts_scanned": int(self.attempts_scanned),
            "fail_count": int(self.fail_count),
            "warn_count": int(self.warn_count),
            "info_count": int(self.info_count),
        }


@dataclass(frozen=True, slots=True)
class EvidenceReport:
    """Output of evidence-check.  Immutable, deterministic ordering.

    exit_code is computed once in scan_session() and stored here.
    """

    tool: str = "evidence-check"
    version: str = "1.0.0"

    session_dir: str = ""
    session_type: str = "unknown"  # "tap" | "phase2" | "unknown"

    strict: bool = False
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    summary: EvidenceSummary = field(
        default_factory=lambda: EvidenceSummary(0, 0, 0, 0),
    )
    exit_code: int = 0  # 0 ok, 1 missing/layout, 2 parse/format, 4 unexpected

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "version": self.version,
            "session_dir": self.session_dir,
            "session_type": self.session_type,
            "strict": bool(self.strict),
            "exit_code": int(self.exit_code),
            "summary": self.summary.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
        }


# =============================================================================
# Error codes
# =============================================================================

# E0xx: Missing / layout
E001_MISSING_REQUIRED = "E001"  # missing required artifact in attempt dir
E003_NO_ATTEMPTS_FOUND = "E003"  # no attempt dirs discovered in session

# E1xx: Parse / format
E101_JSON_PARSE_ERROR = "E101"  # json decode error
E102_JSON_NOT_OBJECT = "E102"  # json root is not dict

# E2xx: reserved for future invariant / cross-check validators


# =============================================================================
# Required artifact definitions
# =============================================================================

REQUIRED_FILES = (
    "audio.wav",
    "analysis.json",
    "capture_meta.json",
    "quality_check.json",
)


# =============================================================================
# Deterministic attempt discovery
# =============================================================================

_ATTEMPT_DIR_RE = re.compile(r"^attempt_(\d{3,})$")


def discover_attempt_dirs(session_dir: Path) -> list[Path]:
    """Discover attempt directories deterministically.

    Supports:
      1) Nested layout: {session}/{point_id}/attempt_{NNN}/
      2) Flat layout:   {session}/attempt_{NNN}/

    Returns sorted list, stable and independent of OS:
      primary:   point_id  (or "" for flat)
      secondary: attempt number (int)
      tertiary:  full relative path (string)
    """
    if not session_dir.exists() or not session_dir.is_dir():
        return []

    found: list[tuple[str, int, str, Path]] = []

    for child in session_dir.iterdir():
        if not child.is_dir():
            continue
        m = _ATTEMPT_DIR_RE.match(child.name)
        if m:
            # flat attempt
            attempt_num = int(m.group(1))
            rel = str(child.relative_to(session_dir)).replace("\\", "/")
            found.append(("", attempt_num, rel, child))
            continue
        if child.name.startswith("."):
            continue
        # potential point dir
        for sub in child.iterdir():
            if not sub.is_dir():
                continue
            m2 = _ATTEMPT_DIR_RE.match(sub.name)
            if m2:
                attempt_num = int(m2.group(1))
                rel = str(sub.relative_to(session_dir)).replace("\\", "/")
                found.append((child.name, attempt_num, rel, sub))

    found.sort(key=lambda t: (t[0], t[1], t[2]))
    return [p for *_rest, p in found]


# =============================================================================
# Per-file validators
# =============================================================================


def _validate_required_files_present(attempt_dir: Path) -> list[Finding]:
    """E001: Check required files exist in an attempt directory."""
    findings: list[Finding] = []
    for name in REQUIRED_FILES:
        if not (attempt_dir / name).exists():
            findings.append(
                Finding(
                    code=E001_MISSING_REQUIRED,
                    severity=FindingSeverity.FAIL,
                    message=f"Missing required artifact: {name}",
                    path=str(attempt_dir / name),
                    hint="Re-run capture/analysis for this attempt.",
                )
            )
    return findings


def _validate_analysis_json_parse(attempt_dir: Path) -> list[Finding]:
    """E101/E102: Parse analysis.json and verify root type."""
    return _validate_json_parse(attempt_dir / "analysis.json")


def _validate_capture_meta_json_parse(attempt_dir: Path) -> list[Finding]:
    """E101/E102: Parse capture_meta.json and verify root type."""
    return _validate_json_parse(attempt_dir / "capture_meta.json")


def _validate_quality_check_json_parse(attempt_dir: Path) -> list[Finding]:
    """E101/E102: Parse quality_check.json and verify root type."""
    return _validate_json_parse(attempt_dir / "quality_check.json")


def _validate_json_parse(path: Path) -> list[Finding]:
    """Generic JSON parse + root-type check."""
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return [
            Finding(
                code=E101_JSON_PARSE_ERROR,
                severity=FindingSeverity.FAIL,
                message=f"Could not read JSON file: {e}",
                path=str(path),
            )
        ]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [
            Finding(
                code=E101_JSON_PARSE_ERROR,
                severity=FindingSeverity.FAIL,
                message=f"JSON parse error: {e.msg} (line {e.lineno}, col {e.colno})",
                path=str(path),
            )
        ]
    if not isinstance(data, dict):
        return [
            Finding(
                code=E102_JSON_NOT_OBJECT,
                severity=FindingSeverity.FAIL,
                message=f"JSON root must be an object/dict, got {type(data).__name__}.",
                path=str(path),
                meta={"root_type": type(data).__name__},
            )
        ]
    return []


# =============================================================================
# Session-level validators
# =============================================================================


def _validate_session_has_attempts(
    session_dir: Path,
    attempt_dirs: list[Path],
) -> list[Finding]:
    """E003: Fail if no attempt directories were discovered."""
    if attempt_dirs:
        return []
    return [
        Finding(
            code=E003_NO_ATTEMPTS_FOUND,
            severity=FindingSeverity.FAIL,
            message="No attempt directories found (expected attempt_###).",
            path=str(session_dir),
            hint=(
                "Ensure captures are written under "
                "session/<point>/attempt_### or session/attempt_###."
            ),
        )
    ]


# =============================================================================
# Scan session (glue)
# =============================================================================


def scan_session(
    session_dir: Path,
    strict: bool = False,
    fail_on_warn: bool = False,
) -> EvidenceReport:
    """Scan a session directory and return an EvidenceReport.

    Deterministic ordering: attempt dirs and findings are sorted.
    """
    _strict = bool(strict or fail_on_warn)

    # Handle non-existent / non-directory
    if not session_dir.exists():
        return EvidenceReport(
            session_dir=str(session_dir),
            session_type="unknown",
            strict=_strict,
            findings=(
                Finding(
                    code=E003_NO_ATTEMPTS_FOUND,
                    severity=FindingSeverity.FAIL,
                    message="Session directory does not exist",
                    path=str(session_dir),
                ),
            ),
            summary=EvidenceSummary(0, 1, 0, 0),
            exit_code=1,
        )

    if not session_dir.is_dir():
        return EvidenceReport(
            session_dir=str(session_dir),
            session_type="unknown",
            strict=_strict,
            findings=(
                Finding(
                    code=E003_NO_ATTEMPTS_FOUND,
                    severity=FindingSeverity.FAIL,
                    message="Path is not a directory",
                    path=str(session_dir),
                ),
            ),
            summary=EvidenceSummary(0, 1, 0, 0),
            exit_code=1,
        )

    attempt_dirs = discover_attempt_dirs(session_dir)
    findings: list[Finding] = []

    # Session-level: must have attempts
    findings.extend(_validate_session_has_attempts(session_dir, attempt_dirs))

    # Per-attempt validation
    for attempt_dir in attempt_dirs:
        findings.extend(_validate_required_files_present(attempt_dir))
        findings.extend(_validate_analysis_json_parse(attempt_dir))
        findings.extend(_validate_capture_meta_json_parse(attempt_dir))
        findings.extend(_validate_quality_check_json_parse(attempt_dir))

    # Stable ordering: severity (FAIL, WARN, INFO), then code, then path
    severity_rank = {
        FindingSeverity.FAIL: 0,
        FindingSeverity.WARN: 1,
        FindingSeverity.INFO: 2,
    }
    findings_sorted = sorted(
        findings,
        key=lambda f: (severity_rank[f.severity], f.code, f.path or ""),
    )

    fail_count = sum(1 for f in findings_sorted if f.severity == FindingSeverity.FAIL)
    warn_count = sum(1 for f in findings_sorted if f.severity == FindingSeverity.WARN)
    info_count = sum(1 for f in findings_sorted if f.severity == FindingSeverity.INFO)

    summary = EvidenceSummary(
        attempts_scanned=len(attempt_dirs),
        fail_count=fail_count,
        warn_count=warn_count,
        info_count=info_count,
    )

    # Exit code policy
    exit_code = 0
    if fail_count:
        has_parse_fail = any(
            f.code.startswith("E1")
            for f in findings_sorted
            if f.severity == FindingSeverity.FAIL
        )
        exit_code = 2 if has_parse_fail else 1
    elif warn_count and _strict:
        exit_code = 1

    # Session type inference
    session_type = "phase2" if (session_dir / "grid.json").exists() else "tap"

    return EvidenceReport(
        session_dir=str(session_dir),
        session_type=session_type,
        strict=_strict,
        findings=tuple(findings_sorted),
        summary=summary,
        exit_code=exit_code,
    )


# =============================================================================
# Renderers
# =============================================================================


def render_human(report: EvidenceReport) -> str:
    """Human-readable report.  Deterministic: grouped by severity/code/path."""
    lines: list[str] = []
    lines.append(f"Evidence check: {report.session_dir}")
    lines.append(
        f"Type: {report.session_type}  " f"Attempts: {report.summary.attempts_scanned}"
    )
    lines.append(
        f"FAIL={report.summary.fail_count} "
        f"WARN={report.summary.warn_count} "
        f"INFO={report.summary.info_count}"
    )
    lines.append("")

    for f in report.findings:
        p = f" ({f.path})" if f.path else ""
        lines.append(f"[{f.severity.value.upper()}] {f.code}: {f.message}{p}")
        if f.hint:
            lines.append(f"  hint: {f.hint}")

    return "\n".join(lines).rstrip()


__all__ = [
    "FindingSeverity",
    "Finding",
    "EvidenceSummary",
    "EvidenceReport",
    "discover_attempt_dirs",
    "scan_session",
    "render_human",
]
