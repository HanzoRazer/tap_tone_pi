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
    exit_code: int = 0  # 0 ok, 1 missing/layout, 2 parse/format

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
# E0xx: Missing/layout
E001_MISSING_REQUIRED = "E001"  # missing required artifact in attempt dir
E002_EMPTY_FILE = "E002"        # file exists but is zero bytes
E003_NO_ATTEMPTS_FOUND = "E003" # no attempt dirs discovered in session
E010_MISSING_OPTIONAL = "E010"  # optional artifact missing (WARN)

# E1xx: Parse/format
E101_JSON_PARSE_ERROR = "E101"  # json decode error
E102_JSON_NOT_OBJECT = "E102"   # json root is not dict
E103_MISSING_JSON_KEY = "E103"  # required key missing from JSON
E104_INVALID_FIELD = "E104"     # field value invalid

# E2xx: Invariants/cross-checks (WARN by default, FAIL under --strict)
E201_WAV_SUSPICIOUS_SIZE = "E201"   # WAV file size suspicious (truncated?)
E202_ANALYSIS_SEMANTIC_MISSING_KEYS = "E202"  # analysis.json missing expected keys
E203_QC_SEMANTIC_INVALID = "E203"   # quality_check.json semantic invalid
E210_ATTEMPT_NUMBERING_GAPS = "E210"  # non-monotonic attempt numbering per point
E212_INCONSISTENT_SPECTRUM_BINS = "E212"  # spectrum bin count varies across attempts


# =============================================================================
# Deterministic attempt discovery
# =============================================================================

_ATTEMPT_DIR_RE = re.compile(r"^attempt_(\d{3,})$")


def _safe_iterdir(path: Path) -> list[Path]:
    """Safe iterdir that returns empty list on error."""
    try:
        return list(path.iterdir())
    except (OSError, PermissionError):
        return []


def _discover_attempt_dirs(session_dir: Path) -> list[Path]:
    """Discover attempt directories deterministically.

    Supports:
      1) Nested layout: {session}/{point_id}/attempt_{NNN}/
      2) Flat layout:   {session}/attempt_{NNN}/

    Returns sorted list, stable and independent of OS:
      primary: point_id (or "" for flat)
      secondary: attempt number (int)
      tertiary: full relative path (string)
    """
    if not session_dir.exists() or not session_dir.is_dir():
        return []

    found: list[tuple[str, int, str, Path]] = []

    # Case A: flat attempt dirs directly under session
    for child in _safe_iterdir(session_dir):
        if not child.is_dir():
            continue
        m = _ATTEMPT_DIR_RE.match(child.name)
        if not m:
            continue
        attempt_num = int(m.group(1))
        rel = str(child.relative_to(session_dir)).replace("\\", "/")
        found.append(("", attempt_num, rel, child))

    # Case B: nested point dirs one level down
    for point_dir in _safe_iterdir(session_dir):
        if not point_dir.is_dir():
            continue
        if point_dir.name.startswith("."):
            continue
        for child in _safe_iterdir(point_dir):
            if not child.is_dir():
                continue
            m = _ATTEMPT_DIR_RE.match(child.name)
            if not m:
                continue
            attempt_num = int(m.group(1))
            point_id = point_dir.name
            rel = str(child.relative_to(session_dir)).replace("\\", "/")
            found.append((point_id, attempt_num, rel, child))

    found.sort(key=lambda t: (t[0], t[1], t[2]))
    return [p for *_rest, p in found]


# =============================================================================
# Required/optional artifact definitions
# =============================================================================

# Phase 1 (tap): per-attempt directory
TAP_REQUIRED_FILES = (
    "audio.wav",
    "analysis.json",
    "quality_check.json",
)
TAP_OPTIONAL_FILES = (
    "capture_meta.json",
    "attempt_meta.json",
    "spectrum.csv",
    "spectrum.png",
)

# JSON minimal key requirements
REQUIRED_KEYS: dict[str, list[str]] = {
    "analysis.json": ["peaks"],
    "quality_check.json": ["verdict"],
    "capture_meta.json": ["sample_rate_hz"],
    "grid.json": ["points"],
}


# =============================================================================
# File-level validators
# =============================================================================

def _read_json(path: Path) -> tuple[dict[str, Any] | None, Finding | None]:
    """Helper: parse JSON with stable error reporting.

    Returns (data, finding).  Exactly one is non-None.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return None, Finding(
            code=E101_JSON_PARSE_ERROR,
            severity=FindingSeverity.FAIL,
            message=f"Could not read JSON file: {e}",
            path=str(path),
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, Finding(
            code=E101_JSON_PARSE_ERROR,
            severity=FindingSeverity.FAIL,
            message=f"JSON parse error: {e.msg} (line {e.lineno}, col {e.colno})",
            path=str(path),
        )

    if not isinstance(data, dict):
        return None, Finding(
            code=E102_JSON_NOT_OBJECT,
            severity=FindingSeverity.FAIL,
            message=f"JSON root must be an object/dict, got {type(data).__name__}.",
            path=str(path),
            meta={"root_type": type(data).__name__},
        )

    return data, None


def _check_file_exists(
    parent: Path, filename: str, *, required: bool = True,
) -> list[Finding]:
    """Check that a file exists and is non-empty."""
    findings: list[Finding] = []
    fpath = parent / filename

    if not fpath.exists():
        sev = FindingSeverity.FAIL if required else FindingSeverity.WARN
        code = E001_MISSING_REQUIRED if required else E010_MISSING_OPTIONAL
        findings.append(Finding(
            code=code,
            severity=sev,
            message=f"{'Required' if required else 'Optional'} file missing: {filename}",
            path=str(fpath),
            hint=(
                "Re-run capture/analysis for this attempt."
                if required
                else None
            ),
            meta={"missing": filename},
        ))
        return findings

    if fpath.stat().st_size == 0:
        sev = FindingSeverity.FAIL if required else FindingSeverity.WARN
        findings.append(Finding(
            code=E002_EMPTY_FILE,
            severity=sev,
            message=f"File is empty (zero bytes): {filename}",
            path=str(fpath),
        ))
    return findings


# =============================================================================
# E2xx validators — invariant / cross-check (WARN by default)
# =============================================================================

def _attempt_number(attempt_dir: Path) -> int | None:
    """Parse attempt_NNN from directory name.  Return None if not parseable."""
    m = _ATTEMPT_DIR_RE.match(attempt_dir.name)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _point_id_for_attempt(session_dir: Path, attempt_dir: Path) -> str:
    """Determine point_id for an attempt dir.

    - Flat layout:   session/attempt_### → ""
    - Nested layout:  session/<point>/attempt_### → "<point>"
    """
    rel = attempt_dir.relative_to(session_dir)
    parts = rel.parts
    if len(parts) >= 2 and parts[-1].startswith("attempt_"):
        return parts[-2]
    return ""


def _validate_wav_suspicious_size(attempt_dir: Path) -> list[Finding]:
    """E201: WAV exists but size looks wrong (cheap, no WAV parsing)."""
    wav = attempt_dir / "audio.wav"
    if not wav.exists():
        return []  # missing handled by E001
    try:
        size = wav.stat().st_size
    except Exception:
        return []
    # Heuristic: WAV header alone is ~44 bytes; anything below ~1 KB is suspicious.
    if size < 1024:
        return [
            Finding(
                code=E201_WAV_SUSPICIOUS_SIZE,
                severity=FindingSeverity.WARN,
                message=f"audio.wav size is suspiciously small ({size} bytes).",
                path=str(wav),
                hint="Re-record this attempt; file may be truncated.",
                meta={"size_bytes": size},
            )
        ]
    return []


def _validate_analysis_semantics(attempt_dir: Path) -> list[Finding]:
    """E202: analysis.json parses, but lacks minimal expected keys.

    Lightweight check — does NOT replicate full schema validation.
    """
    path = attempt_dir / "analysis.json"
    if not path.exists():
        return []
    data, parse_finding = _read_json(path)
    if parse_finding:
        return []  # E101/E102 already reported by parse validator
    assert data is not None

    required_keys = ("dominant_hz", "rms", "confidence", "clipped", "peaks")
    missing = [k for k in required_keys if k not in data]
    if missing:
        return [
            Finding(
                code=E202_ANALYSIS_SEMANTIC_MISSING_KEYS,
                severity=FindingSeverity.WARN,
                message=f"analysis.json missing expected keys: {', '.join(missing)}",
                path=str(path),
                hint="Re-run analysis for this attempt; analysis.json should include minimal result fields.",
                meta={"missing_keys": missing},
            )
        ]
    return []


def _validate_quality_check_semantics(attempt_dir: Path) -> list[Finding]:
    """E203: quality_check.json parses, but values/types are unexpected."""
    path = attempt_dir / "quality_check.json"
    if not path.exists():
        return []
    data, parse_finding = _read_json(path)
    if parse_finding:
        return []
    assert data is not None

    verdict = data.get("verdict")
    triggered = data.get("triggered_rules")
    ok_verdict = verdict in ("pass", "warn", "fail")
    ok_triggered = isinstance(triggered, list)

    problems: list[str] = []
    if not ok_verdict:
        problems.append("verdict must be one of {pass,warn,fail}")
    if not ok_triggered:
        problems.append("triggered_rules must be a list")

    if problems:
        return [
            Finding(
                code=E203_QC_SEMANTIC_INVALID,
                severity=FindingSeverity.WARN,
                message="quality_check.json has unexpected values/types: " + "; ".join(problems),
                path=str(path),
                hint="This attempt may have been produced by an older or corrupted tool run; consider re-running measurement.",
                meta={"verdict": verdict, "triggered_rules_type": type(triggered).__name__},
            )
        ]
    return []


def _check_json_keys(filepath: Path, data: dict[str, Any]) -> list[Finding]:
    """Check that required keys are present in parsed JSON."""
    findings: list[Finding] = []
    required_keys = REQUIRED_KEYS.get(filepath.name, [])
    for key in required_keys:
        if key not in data:
            findings.append(Finding(
                code=E103_MISSING_JSON_KEY,
                severity=FindingSeverity.FAIL,
                message=f"Missing required key '{key}' in {filepath.name}",
                path=str(filepath),
            ))

    return findings


# =============================================================================
# Per-attempt validator
# =============================================================================

def validate_attempt(attempt_dir: Path) -> list[Finding]:
    """Validate a single attempt directory (all checks)."""
    findings: list[Finding] = []

    # Required files
    for fname in TAP_REQUIRED_FILES:
        findings.extend(_check_file_exists(attempt_dir, fname, required=True))

    # Optional files
    for fname in TAP_OPTIONAL_FILES:
        findings.extend(_check_file_exists(attempt_dir, fname, required=False))

    # JSON parse + key checks for files that exist
    for fname in ("analysis.json", "quality_check.json", "capture_meta.json",
                   "attempt_meta.json"):
        fpath = attempt_dir / fname
        if not fpath.exists() or fpath.stat().st_size == 0:
            continue
        data, parse_finding = _read_json(fpath)
        if parse_finding:
            findings.append(parse_finding)
        elif data is not None:
            findings.extend(_check_json_keys(fpath, data))

    # E2xx attempt-local invariants
    findings.extend(_validate_wav_suspicious_size(attempt_dir))
    findings.extend(_validate_analysis_semantics(attempt_dir))
    findings.extend(_validate_quality_check_semantics(attempt_dir))

    return findings


# =============================================================================
# Session-level E2xx validators
# =============================================================================

def _validate_attempt_numbering_by_point(
    session_dir: Path,
    attempt_dirs: list[Path],
) -> list[Finding]:
    """E210: Warn if attempt numbering has gaps per point.

    Flat layout point_id is "" and is treated as one group.
    """
    by_point: dict[str, list[int]] = {}
    for ad in attempt_dirs:
        n = _attempt_number(ad)
        if n is None:
            continue
        pid = _point_id_for_attempt(session_dir, ad)
        by_point.setdefault(pid, []).append(n)

    findings: list[Finding] = []
    for pid, nums in by_point.items():
        nums_sorted = sorted(set(nums))
        if not nums_sorted:
            continue
        expected = list(range(nums_sorted[0], nums_sorted[-1] + 1))
        if nums_sorted != expected:
            missing = sorted(set(expected) - set(nums_sorted))
            where = str(session_dir / pid) if pid else str(session_dir)
            findings.append(
                Finding(
                    code=E210_ATTEMPT_NUMBERING_GAPS,
                    severity=FindingSeverity.WARN,
                    message=f"Attempt numbering has gaps for point '{pid or 'flat'}': missing {missing}",
                    path=where,
                    hint="This is allowed, but can confuse downstream tools. Prefer monotonic attempt_001..N per point.",
                    meta={"point_id": pid, "present": nums_sorted, "missing": missing},
                )
            )
    return findings


def _spectrum_len_from_analysis(data: dict[str, Any]) -> int | None:
    """Extract spectrum-bin count from analysis.json.

    Adapt field names to canonical AnalysisResult serialization.
    """
    freq = data.get("spectrum_freq_hz")
    mag = data.get("spectrum_mag")
    if isinstance(freq, list):
        return len(freq)
    if isinstance(mag, list):
        return len(mag)
    return None


def _validate_consistent_spectrum_bins(
    session_dir: Path,
    attempt_dirs: list[Path],
) -> list[Finding]:
    """E212: Warn if spectrum bin length differs across attempts in a session."""
    lens: dict[str, int] = {}
    for ad in attempt_dirs:
        path = ad / "analysis.json"
        if not path.exists():
            continue
        data, parse_finding = _read_json(path)
        if parse_finding or data is None:
            continue
        n = _spectrum_len_from_analysis(data)
        if n is not None:
            lens[str(ad)] = n

    if not lens:
        return []

    values = sorted(set(lens.values()))
    if len(values) <= 1:
        return []

    # Choose the most common length as "baseline"
    baseline = max(values, key=lambda v: sum(1 for x in lens.values() if x == v))
    offenders = []
    for attempt_path, n in list(lens.items())[:8]:
        if n != baseline:
            offenders.append({"attempt": attempt_path, "bins": n})
        if len(offenders) >= 5:
            break

    return [
        Finding(
            code=E212_INCONSISTENT_SPECTRUM_BINS,
            severity=FindingSeverity.WARN,
            message=f"Inconsistent spectrum bin counts across attempts (baseline={baseline}, seen={values}).",
            path=str(session_dir),
            hint="Ensure all attempts use the same analyzer configuration/windowing; re-run analysis if needed.",
            meta={"baseline_bins": baseline, "seen_bins": values, "examples": offenders},
        )
    ]


# =============================================================================
# Scan session (glue)
# =============================================================================

def scan_session(
    session_dir: Path,
    *,
    strict: bool = False,
    fail_on_warn: bool = False,
) -> EvidenceReport:
    """Scan a session directory and return an EvidenceReport.

    Deterministic ordering: attempt dirs and findings are sorted.
    """
    _strict = bool(strict or fail_on_warn)
    session_dir = Path(session_dir).resolve()

    # Handle non-existent / non-directory
    if not session_dir.exists():
        return EvidenceReport(
            session_dir=str(session_dir),
            session_type="unknown",
            strict=_strict,
            findings=(Finding(
                code=E003_NO_ATTEMPTS_FOUND,
                severity=FindingSeverity.FAIL,
                message="Session directory does not exist",
                path=str(session_dir),
            ),),
            summary=EvidenceSummary(0, 1, 0, 0),
            exit_code=1,
        )

    if not session_dir.is_dir():
        return EvidenceReport(
            session_dir=str(session_dir),
            session_type="unknown",
            strict=_strict,
            findings=(Finding(
                code=E003_NO_ATTEMPTS_FOUND,
                severity=FindingSeverity.FAIL,
                message="Path is not a directory",
                path=str(session_dir),
            ),),
            summary=EvidenceSummary(0, 1, 0, 0),
            exit_code=1,
        )

    attempt_dirs = _discover_attempt_dirs(session_dir)

    findings: list[Finding] = []

    # Session-level: must have attempts
    if not attempt_dirs:
        findings.append(Finding(
            code=E003_NO_ATTEMPTS_FOUND,
            severity=FindingSeverity.FAIL,
            message="No attempt directories found (expected attempt_###).",
            path=str(session_dir),
            hint=(
                "Ensure captures are written under "
                "session/<point>/attempt_### or session/attempt_###."
            ),
        ))

    # Per-attempt validation
    for attempt_dir in attempt_dirs:
        findings.extend(validate_attempt(attempt_dir))

    # E2xx session/point-level invariants
    if attempt_dirs:
        findings.extend(
            _validate_attempt_numbering_by_point(session_dir, attempt_dirs)
        )
        findings.extend(
            _validate_consistent_spectrum_bins(session_dir, attempt_dirs)
        )

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

    fail_count = sum(
        1 for f in findings_sorted if f.severity == FindingSeverity.FAIL
    )
    warn_count = sum(
        1 for f in findings_sorted if f.severity == FindingSeverity.WARN
    )
    info_count = sum(
        1 for f in findings_sorted if f.severity == FindingSeverity.INFO
    )

    summary = EvidenceSummary(
        attempts_scanned=len(attempt_dirs),
        fail_count=fail_count,
        warn_count=warn_count,
        info_count=info_count,
    )

    # Exit code policy:
    # - Any FAIL with E1xx => 2
    # - Else any FAIL with E0xx/E2xx => 1
    # - Else WARN + strict => 1
    # - Else 0
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
        f"Type: {report.session_type}  "
        f"Attempts: {report.summary.attempts_scanned}"
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


def render_json(report: EvidenceReport) -> str:
    """Render report as JSON string."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=False)
