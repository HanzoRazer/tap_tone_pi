"""Evidence preflight validator for session directories.

Answers four questions deterministically:
1. Is this session structurally valid (layout)?
2. Are required artifacts present per attempt/point?
3. Do the JSON artifacts parse and meet minimal invariants?
4. If not, what exactly is missing, where, and what should I do next?

Usage:
    ttp evidence-check --session <dir> [--strict] [--json]

This module has NO DSP, NO advisory logic, NO external deps.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# =============================================================================
# Finding codes
# =============================================================================

class Severity(str, Enum):
    """Finding severity."""
    FAIL = "fail"
    WARN = "warn"
    INFO = "info"


# Error code ranges:
#   E0xx — missing files
#   E1xx — parse errors / invalid content
#   E2xx — cross-file invariant violations
#   E3xx — layout issues

FINDING_DESCRIPTIONS = {
    # Missing files
    "E001": "Missing required file",
    "E002": "Empty file (zero bytes)",
    # Parse errors
    "E100": "JSON parse error",
    "E101": "JSON is not a dict",
    "E102": "Missing required JSON key",
    "E103": "Invalid field value",
    # Cross-file invariants
    "E200": "Sample rate mismatch between artifacts",
    "E201": "Attempt numbering gap",
    # Layout
    "E300": "No attempt directories found for point",
    "E301": "No points found in session",
    "E302": "Unrecognized session layout",
}


@dataclass(frozen=True)
class Finding:
    """A single validation finding."""
    severity: Severity
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


# =============================================================================
# Session types
# =============================================================================

class SessionType(str, Enum):
    """Detected session type."""
    PHASE1 = "phase1"       # ttp measure layout: <session>/<point>/attempt_NNN/
    PHASE2 = "phase2"       # Phase 2 layout: <session>/points/point_<ID>/
    RECORD = "record"       # ttp record layout: <session>/capture_<ts>/
    UNKNOWN = "unknown"


# =============================================================================
# Report
# =============================================================================

@dataclass
class EvidenceReport:
    """Complete validation report for a session."""
    session_path: str
    session_type: SessionType
    points_scanned: int = 0
    attempts_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def fail_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARN)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    @property
    def ok(self) -> bool:
        return self.fail_count == 0

    def exit_code(self, *, strict: bool = False) -> int:
        """Compute exit code.

        0 = OK
        1 = missing required artifacts / invalid layout
        2 = parse errors / invalid JSON / required fields missing
        """
        if self.fail_count > 0:
            # Distinguish parse errors from missing files
            has_parse = any(
                f.code.startswith("E1") and f.severity == Severity.FAIL
                for f in self.findings
            )
            if has_parse:
                return 2
            return 1
        if strict and self.warn_count > 0:
            return 1
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": "evidence-check",
            "version": "1.0.0",
            "session": self.session_path,
            "session_type": self.session_type.value,
            "summary": {
                "points": self.points_scanned,
                "attempts": self.attempts_scanned,
                "fail": self.fail_count,
                "warn": self.warn_count,
                "info": self.info_count,
                "ok": self.ok,
            },
            "findings": [f.to_dict() for f in self.findings],
        }


# =============================================================================
# Required artifacts per session type
# =============================================================================

# Phase 1 (ttp measure): per-attempt directory
PHASE1_REQUIRED = ("audio.wav", "analysis.json", "quality_check.json")
PHASE1_OPTIONAL = ("attempt_meta.json", "spectrum.csv", "spectrum.png")

# Phase 2: per-point directory
PHASE2_REQUIRED = ("audio.wav",)
PHASE2_OPTIONAL = ("analysis.json", "capture_meta.json", "spectrum.csv")

# Record (ttp record): per-capture directory
RECORD_REQUIRED = ("audio.wav", "analysis.json", "spectrum.csv")
RECORD_OPTIONAL = ("quality_check.json",)

# Phase 2 session-level required
PHASE2_SESSION_REQUIRED = ("grid.json",)
PHASE2_SESSION_OPTIONAL = ("metadata.json", "session_meta.json")


# =============================================================================
# JSON minimal key checks
# =============================================================================

REQUIRED_KEYS: dict[str, list[str]] = {
    "analysis.json": ["peaks"],
    "quality_check.json": ["verdict"],
    "capture_meta.json": ["sample_rate_hz"],
    "grid.json": ["points"],
}


# =============================================================================
# Detection
# =============================================================================

def detect_session_type(session_dir: Path) -> SessionType:
    """Detect session type from directory structure.

    - Phase 2: has grid.json or points/ subdirectory
    - Phase 1 (measure): has <point>/attempt_NNN/ structure
    - Record: has capture_<ts>/ structure
    """
    if (session_dir / "grid.json").exists():
        return SessionType.PHASE2
    if (session_dir / "points").is_dir():
        return SessionType.PHASE2

    # Check for Phase 1 attempt_NNN dirs
    for child in _safe_iterdir(session_dir):
        if child.is_dir() and not child.name.startswith("."):
            for sub in _safe_iterdir(child):
                if sub.is_dir() and sub.name.startswith("attempt_"):
                    return SessionType.PHASE1

    # Check for record capture_<ts> dirs
    for child in _safe_iterdir(session_dir):
        if child.is_dir() and child.name.startswith("capture_"):
            return SessionType.RECORD

    return SessionType.UNKNOWN


def _safe_iterdir(path: Path) -> list[Path]:
    """Safe iterdir that returns empty list on error."""
    try:
        return list(path.iterdir())
    except (OSError, PermissionError):
        return []


# =============================================================================
# File validators
# =============================================================================

def _check_file_exists(
    artifact_dir: Path,
    filename: str,
    required: bool = True,
) -> list[Finding]:
    """Check that a file exists and is non-empty."""
    findings: list[Finding] = []
    fpath = artifact_dir / filename
    rel = str(fpath)

    if not fpath.exists():
        sev = Severity.FAIL if required else Severity.WARN
        findings.append(Finding(
            severity=sev,
            code="E001",
            path=rel,
            message=f"{'Required' if required else 'Optional'} file missing: {filename}",
        ))
        return findings

    if fpath.stat().st_size == 0:
        sev = Severity.FAIL if required else Severity.WARN
        findings.append(Finding(
            severity=sev,
            code="E002",
            path=rel,
            message=f"File is empty (zero bytes): {filename}",
        ))
    return findings


def _check_json_parseable(filepath: Path) -> list[Finding]:
    """Check that a JSON file parses and is a dict with required keys."""
    findings: list[Finding] = []
    rel = str(filepath)

    if not filepath.exists() or filepath.stat().st_size == 0:
        return findings  # Already reported by _check_file_exists

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        findings.append(Finding(
            severity=Severity.FAIL,
            code="E100",
            path=rel,
            message=f"JSON parse error: {e}",
        ))
        return findings

    if not isinstance(data, dict):
        findings.append(Finding(
            severity=Severity.FAIL,
            code="E101",
            path=rel,
            message=f"JSON root is {type(data).__name__}, expected dict",
        ))
        return findings

    # Check required keys
    required_keys = REQUIRED_KEYS.get(filepath.name, [])
    for key in required_keys:
        if key not in data:
            findings.append(Finding(
                severity=Severity.FAIL,
                code="E102",
                path=rel,
                message=f"Missing required key '{key}' in {filepath.name}",
            ))

    # Check verdict value for quality_check.json
    if filepath.name == "quality_check.json" and "verdict" in data:
        if data["verdict"] not in ("pass", "warn", "fail",
                                    "PASS", "WARN", "FAIL"):
            findings.append(Finding(
                severity=Severity.FAIL,
                code="E103",
                path=rel,
                message=f"Invalid verdict value: {data['verdict']!r} "
                        f"(expected pass/warn/fail)",
            ))

    return findings


def _check_wav_header(filepath: Path) -> list[Finding]:
    """Minimal WAV header check: file exists, non-empty, starts with RIFF."""
    findings: list[Finding] = []
    rel = str(filepath)

    if not filepath.exists() or filepath.stat().st_size == 0:
        return findings  # Already reported

    try:
        with open(filepath, "rb") as f:
            header = f.read(12)
        if len(header) < 12:
            findings.append(Finding(
                severity=Severity.FAIL,
                code="E100",
                path=rel,
                message="WAV file too short to contain valid header",
            ))
        elif header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            findings.append(Finding(
                severity=Severity.FAIL,
                code="E100",
                path=rel,
                message="Not a valid WAV file (missing RIFF/WAVE header)",
            ))
    except OSError as e:
        findings.append(Finding(
            severity=Severity.FAIL,
            code="E100",
            path=rel,
            message=f"Cannot read WAV file: {e}",
        ))
    return findings


def _check_sample_rate_consistency(artifact_dir: Path) -> list[Finding]:
    """WARN if sample_rate differs between capture_meta and analysis."""
    findings: list[Finding] = []

    meta_path = artifact_dir / "capture_meta.json"
    analysis_path = artifact_dir / "analysis.json"

    if not meta_path.exists() or not analysis_path.exists():
        return findings

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    except (json.JSONDecodeError, OSError):
        return findings  # Parse errors already reported

    meta_sr = meta.get("sample_rate_hz") or meta.get("sample_rate")
    analysis_sr = analysis.get("sample_rate")

    if meta_sr and analysis_sr and meta_sr != analysis_sr:
        findings.append(Finding(
            severity=Severity.WARN,
            code="E200",
            path=str(artifact_dir),
            message=f"Sample rate mismatch: capture_meta={meta_sr}, "
                    f"analysis={analysis_sr}",
        ))
    return findings


# =============================================================================
# Per-directory validators
# =============================================================================

def validate_phase1_attempt(attempt_dir: Path) -> list[Finding]:
    """Validate a single Phase 1 attempt directory."""
    findings: list[Finding] = []

    for fname in PHASE1_REQUIRED:
        findings.extend(_check_file_exists(attempt_dir, fname, required=True))

    for fname in PHASE1_OPTIONAL:
        findings.extend(_check_file_exists(attempt_dir, fname, required=False))

    # JSON parse checks for files that exist
    for fname in ("analysis.json", "quality_check.json", "attempt_meta.json"):
        fpath = attempt_dir / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            findings.extend(_check_json_parseable(fpath))

    # WAV header check
    wav = attempt_dir / "audio.wav"
    findings.extend(_check_wav_header(wav))

    return findings


def validate_phase2_point(point_dir: Path) -> list[Finding]:
    """Validate a single Phase 2 point directory."""
    findings: list[Finding] = []

    for fname in PHASE2_REQUIRED:
        findings.extend(_check_file_exists(point_dir, fname, required=True))

    for fname in PHASE2_OPTIONAL:
        findings.extend(_check_file_exists(point_dir, fname, required=False))

    # JSON parse checks
    for fname in ("analysis.json", "capture_meta.json"):
        fpath = point_dir / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            findings.extend(_check_json_parseable(fpath))

    # WAV header
    wav = point_dir / "audio.wav"
    findings.extend(_check_wav_header(wav))

    # Cross-file invariants
    findings.extend(_check_sample_rate_consistency(point_dir))

    return findings


def validate_record_capture(capture_dir: Path) -> list[Finding]:
    """Validate a single ttp record capture directory."""
    findings: list[Finding] = []

    for fname in RECORD_REQUIRED:
        findings.extend(_check_file_exists(capture_dir, fname, required=True))

    for fname in RECORD_OPTIONAL:
        findings.extend(_check_file_exists(capture_dir, fname, required=False))

    # JSON parse checks
    for fname in ("analysis.json", "quality_check.json"):
        fpath = capture_dir / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            findings.extend(_check_json_parseable(fpath))

    # WAV header
    wav = capture_dir / "audio.wav"
    findings.extend(_check_wav_header(wav))

    return findings


# =============================================================================
# Session scanner
# =============================================================================

def scan_session(session_dir: Path) -> EvidenceReport:
    """Scan a session directory and validate all artifacts.

    Auto-detects session type (Phase 1, Phase 2, record) and applies
    the appropriate validation rules.

    Args:
        session_dir: Path to session root directory.

    Returns:
        EvidenceReport with all findings.
    """
    session_dir = Path(session_dir).resolve()
    report = EvidenceReport(
        session_path=str(session_dir),
        session_type=SessionType.UNKNOWN,
    )

    if not session_dir.exists():
        report.findings.append(Finding(
            severity=Severity.FAIL,
            code="E302",
            path=str(session_dir),
            message="Session directory does not exist",
        ))
        return report

    if not session_dir.is_dir():
        report.findings.append(Finding(
            severity=Severity.FAIL,
            code="E302",
            path=str(session_dir),
            message="Path is not a directory",
        ))
        return report

    session_type = detect_session_type(session_dir)
    report.session_type = session_type

    if session_type == SessionType.UNKNOWN:
        report.findings.append(Finding(
            severity=Severity.FAIL,
            code="E302",
            path=str(session_dir),
            message="Cannot detect session type (no attempt_NNN dirs, "
                    "no points/ dir, no capture_ dirs, no grid.json)",
        ))
        return report

    if session_type == SessionType.PHASE1:
        _scan_phase1(session_dir, report)
    elif session_type == SessionType.PHASE2:
        _scan_phase2(session_dir, report)
    elif session_type == SessionType.RECORD:
        _scan_record(session_dir, report)

    return report


def _scan_phase1(session_dir: Path, report: EvidenceReport) -> None:
    """Scan Phase 1 (ttp measure) session."""
    point_dirs = sorted([
        d for d in _safe_iterdir(session_dir)
        if d.is_dir() and not d.name.startswith(".")
    ])

    if not point_dirs:
        report.findings.append(Finding(
            severity=Severity.FAIL,
            code="E301",
            path=str(session_dir),
            message="No point directories found",
        ))
        return

    for point_dir in point_dirs:
        attempt_dirs = sorted([
            d for d in _safe_iterdir(point_dir)
            if d.is_dir() and d.name.startswith("attempt_")
        ])

        if not attempt_dirs:
            report.findings.append(Finding(
                severity=Severity.FAIL,
                code="E300",
                path=str(point_dir),
                message=f"No attempt directories for point {point_dir.name}",
            ))
            report.points_scanned += 1
            continue

        # Check attempt numbering continuity
        attempt_nums = []
        for ad in attempt_dirs:
            try:
                num = int(ad.name.split("_")[1])
                attempt_nums.append(num)
            except (IndexError, ValueError):
                pass
        if attempt_nums:
            expected = list(range(1, max(attempt_nums) + 1))
            if sorted(attempt_nums) != expected:
                report.findings.append(Finding(
                    severity=Severity.WARN,
                    code="E201",
                    path=str(point_dir),
                    message=f"Attempt numbering gaps: found {sorted(attempt_nums)}, "
                            f"expected {expected}",
                ))

        report.points_scanned += 1
        for attempt_dir in attempt_dirs:
            report.attempts_scanned += 1
            report.findings.extend(validate_phase1_attempt(attempt_dir))


def _scan_phase2(session_dir: Path, report: EvidenceReport) -> None:
    """Scan Phase 2 session."""
    # Session-level required artifacts
    for fname in PHASE2_SESSION_REQUIRED:
        report.findings.extend(
            _check_file_exists(session_dir, fname, required=True)
        )
        fpath = session_dir / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            report.findings.extend(_check_json_parseable(fpath))

    # Session-level optional
    for fname in PHASE2_SESSION_OPTIONAL:
        report.findings.extend(
            _check_file_exists(session_dir, fname, required=False)
        )

    # Find points directory
    points_root = session_dir / "points"
    if not points_root.is_dir():
        # Some sessions have point dirs directly under session root
        points_root = session_dir

    point_dirs = sorted([
        d for d in _safe_iterdir(points_root)
        if d.is_dir() and (
            d.name.startswith("point_")
            or d.name.startswith("pt_")
        )
    ])

    if not point_dirs:
        report.findings.append(Finding(
            severity=Severity.FAIL,
            code="E301",
            path=str(points_root),
            message="No point directories found (expected point_* dirs)",
        ))
        return

    for point_dir in point_dirs:
        report.points_scanned += 1
        report.attempts_scanned += 1  # Phase 2 has one "attempt" per point
        report.findings.extend(validate_phase2_point(point_dir))


def _scan_record(session_dir: Path, report: EvidenceReport) -> None:
    """Scan ttp record session."""
    capture_dirs = sorted([
        d for d in _safe_iterdir(session_dir)
        if d.is_dir() and d.name.startswith("capture_")
    ])

    if not capture_dirs:
        report.findings.append(Finding(
            severity=Severity.FAIL,
            code="E301",
            path=str(session_dir),
            message="No capture directories found (expected capture_* dirs)",
        ))
        return

    report.points_scanned = len(capture_dirs)
    for capture_dir in capture_dirs:
        report.attempts_scanned += 1
        report.findings.extend(validate_record_capture(capture_dir))


# =============================================================================
# Renderers
# =============================================================================

def render_human(report: EvidenceReport) -> str:
    """Render report as human-readable text."""
    lines: list[str] = []

    # Header
    lines.append(f"Evidence Check: {report.session_path}")
    lines.append(f"Session type:   {report.session_type.value}")
    lines.append(f"Points:         {report.points_scanned}")
    lines.append(f"Attempts:       {report.attempts_scanned}")
    lines.append("")

    # Summary
    if report.ok:
        lines.append("Result: OK")
    else:
        lines.append("Result: PROBLEMS FOUND")

    lines.append(
        f"  FAIL: {report.fail_count}  "
        f"WARN: {report.warn_count}  "
        f"INFO: {report.info_count}"
    )

    # Findings grouped by severity
    if report.findings:
        lines.append("")

        for sev in (Severity.FAIL, Severity.WARN, Severity.INFO):
            group = [f for f in report.findings if f.severity == sev]
            if not group:
                continue
            for finding in group:
                tag = sev.value.upper()
                lines.append(
                    f"  {tag}: [{finding.code}] {finding.message}"
                )
                lines.append(f"         {finding.path}")

    return "\n".join(lines)


def render_json(report: EvidenceReport) -> str:
    """Render report as JSON string."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=False)
