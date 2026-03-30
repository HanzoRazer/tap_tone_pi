"""
check_advisory_boundary.py — CI gate for measurement vs decision-support boundary.

Enforces ADR-0009. Checks:
  1. Every .py in tap_tone_pi/ and analyzer/analysis/ declares:
       # INSTRUMENT CLASS: MEASUREMENT
       # INSTRUMENT CLASS: DECISION SUPPORT
  2. No export pipeline module imports a DECISION SUPPORT module.
  3. viewer_pack_v1 schema does not originate from a DECISION SUPPORT module.

Exit codes:
  0  All checks passed
  1  Missing declarations (warn mode)
  2  Export pipeline imports advisory module (always fatal)

Usage:
  python ci/check_advisory_boundary.py
  python ci/check_advisory_boundary.py --strict          # treat missing decls as fatal
  python ci/check_advisory_boundary.py --report-only     # print report, always exit 0
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories that MUST have INSTRUMENT CLASS declarations
DECLARATION_REQUIRED_DIRS = [
    "tap_tone_pi",
    "analyzer/analysis",
]

# These modules are known DECISION SUPPORT — export pipeline may not import them
KNOWN_ADVISORY_MODULES = {
    "tap_tone_pi.wolf.wolf_advisor",
    "tap_tone_pi.wolf.wolf_advisor",
    "analyzer.analysis.wood_properties",
}

# Export pipeline files — must not import advisory modules
EXPORT_PIPELINE_FILES = [
    "scripts/phase2/export_viewer_pack_v1.py",
    "tap_tone_pi/export/bending.py",
    "tap_tone_pi/cli/main.py",
    "tap_tone_pi/viewer_pack",
]

# Files skipped entirely (init stubs, generated)
SKIP_PATTERNS = {"__init__.py", "conftest.py", "setup.py"}

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

DECLARATION_MARKER = "# INSTRUMENT CLASS:"
VALID_CLASSES = {"MEASUREMENT", "DECISION SUPPORT"}


@dataclass
class Finding:
    severity: str  # "error" | "warning"
    code: str
    file: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.code}: {self.file}\n  {self.message}"


@dataclass
class BoundaryReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    def summary(self) -> str:
        return (
            f"Advisory boundary check: "
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s) "
            f"across {len(self.findings)} finding(s)"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_python_files(directory: Path) -> Iterable[Path]:
    """Yield .py files under directory, skipping common non-source patterns."""
    for p in sorted(directory.rglob("*.py")):
        if any(part.startswith(".") for part in p.parts):
            continue
        if p.name in SKIP_PATTERNS:
            continue
        if "test_" in p.name or p.name.endswith("_test.py"):
            continue
        if "__pycache__" in p.parts:
            continue
        yield p


def _extract_instrument_class(path: Path) -> str | None:
    """
    Return the declared instrument class from a file, or None if absent.

    Looks for the first occurrence of:
        # INSTRUMENT CLASS: MEASUREMENT
        # INSTRUMENT CLASS: DECISION SUPPORT
    anywhere in the first 30 lines of the file.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for line in lines[:30]:
        stripped = line.strip()
        if stripped.startswith(DECLARATION_MARKER):
            declared = stripped[len(DECLARATION_MARKER):].strip().upper()
            return declared
    return None


def _extract_imports(path: Path) -> list[str]:
    """Return list of module names imported in a Python file (best-effort)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _to_module_path(path: Path, repo_root: Path) -> str:
    """Convert a file path to a dotted module string relative to repo root."""
    try:
        rel = path.relative_to(repo_root)
        parts = list(rel.with_suffix("").parts)
        return ".".join(parts)
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Check 1 — Declaration coverage
# ---------------------------------------------------------------------------


def check_declarations(report: BoundaryReport, repo_root: Path) -> None:
    """Every module in DECLARATION_REQUIRED_DIRS must have a class declaration."""
    for rel_dir in DECLARATION_REQUIRED_DIRS:
        directory = repo_root / rel_dir
        if not directory.exists():
            continue
        for py_file in _iter_python_files(directory):
            declared = _extract_instrument_class(py_file)
            rel_path = str(py_file.relative_to(repo_root))

            if declared is None:
                report.add(Finding(
                    severity="warning",
                    code="ADRY-001",
                    file=rel_path,
                    message=(
                        f"Missing instrument class declaration. "
                        f"Add '# INSTRUMENT CLASS: MEASUREMENT' or "
                        f"'# INSTRUMENT CLASS: DECISION SUPPORT' "
                        f"as the first comment in the module docstring. "
                        f"See docs/ADR-0009-advisory-boundary.md"
                    ),
                ))
            elif declared not in VALID_CLASSES:
                report.add(Finding(
                    severity="warning",
                    code="ADRY-002",
                    file=rel_path,
                    message=(
                        f"Unknown instrument class: '{declared}'. "
                        f"Valid values: {sorted(VALID_CLASSES)}"
                    ),
                ))


# ---------------------------------------------------------------------------
# Check 2 — Export pipeline isolation
# ---------------------------------------------------------------------------


def check_export_isolation(report: BoundaryReport, repo_root: Path) -> None:
    """Export pipeline files must not import known advisory modules."""
    for rel_path in EXPORT_PIPELINE_FILES:
        target = repo_root / rel_path
        # If it's a directory, scan all Python files in it
        if target.is_dir():
            files = list(_iter_python_files(target))
        elif target.is_file():
            files = [target]
        else:
            continue

        for py_file in files:
            imports = _extract_imports(py_file)
            file_rel = str(py_file.relative_to(repo_root))
            for imp in imports:
                for advisory_mod in KNOWN_ADVISORY_MODULES:
                    if imp == advisory_mod or imp.startswith(advisory_mod + "."):
                        report.add(Finding(
                            severity="error",
                            code="ADRY-010",
                            file=file_rel,
                            message=(
                                f"Export pipeline file imports advisory module: "
                                f"'{imp}'. "
                                f"Advisory outputs must not appear in viewer_pack_v1. "
                                f"See docs/ADR-0009-advisory-boundary.md"
                            ),
                        ))


# ---------------------------------------------------------------------------
# Check 3 — Hardcoded advisory module scan (belt-and-suspenders)
# ---------------------------------------------------------------------------


def check_no_advisory_in_instrument_core(
    report: BoundaryReport, repo_root: Path
) -> None:
    """
    Scan tap_tone_pi/core/, tap_tone_pi/capture/, tap_tone_pi/phase2/,
    tap_tone_pi/calibration/, tap_tone_pi/export/ for imports of known
    advisory modules. These are measurement-only zones.
    """
    measurement_only_dirs = [
        "tap_tone_pi/core",
        "tap_tone_pi/capture",
        "tap_tone_pi/phase2",
        "tap_tone_pi/calibration",
        "tap_tone_pi/export",
        "tap_tone_pi/bending",
    ]
    for rel_dir in measurement_only_dirs:
        directory = repo_root / rel_dir
        if not directory.exists():
            continue
        for py_file in _iter_python_files(directory):
            imports = _extract_imports(py_file)
            file_rel = str(py_file.relative_to(repo_root))
            for imp in imports:
                for advisory_mod in KNOWN_ADVISORY_MODULES:
                    if imp == advisory_mod or imp.startswith(advisory_mod + "."):
                        report.add(Finding(
                            severity="error",
                            code="ADRY-011",
                            file=file_rel,
                            message=(
                                f"Measurement-only module imports advisory module: "
                                f"'{imp}'. "
                                f"This violates the measurement boundary. "
                                f"See docs/ADR-0009-advisory-boundary.md"
                            ),
                        ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Enforce ADR-0009 measurement vs decision-support boundary"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat ADRY-001/002 (missing declarations) as errors, not warnings",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print report but always exit 0 (useful for auditing)",
    )
    args = parser.parse_args(argv or sys.argv[1:])

    report = BoundaryReport()

    check_declarations(report, REPO_ROOT)
    check_export_isolation(report, REPO_ROOT)
    check_no_advisory_in_instrument_core(report, REPO_ROOT)

    # Print findings
    if report.findings:
        print("\n=== Advisory Boundary Check ===\n")
        for f in report.findings:
            print(str(f))
            print()

    print(report.summary())

    if args.report_only:
        return 0

    # Determine exit code
    has_errors = bool(report.errors)
    has_warnings_as_errors = args.strict and bool(report.warnings)

    if has_errors or has_warnings_as_errors:
        return 2 if has_errors else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
