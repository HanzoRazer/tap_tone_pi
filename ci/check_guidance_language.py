#!/usr/bin/env python3
"""Guidance language authority guard.

Scans advisory/decision-support modules for forbidden authority-claiming
language. Uses AST extraction for Python files to focus on user-facing
strings (string literals, docstrings) rather than all text.

Usage:
    python ci/check_guidance_language.py                    # default targets, non-strict
    python ci/check_guidance_language.py --strict           # exit 1 on findings
    python ci/check_guidance_language.py path/to/module     # custom target

Exemption:
    Add this marker to a file to skip scanning:
    # EXEMPT: guidance_language_guard

See: docs/AGE_CONSTITUTIONAL_CONTRACT.md
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Set


FORBIDDEN_TERMS: Set[str] = {
    "confirmed",
    "verified",
    "diagnosed",
    "resolved",
    "proven",
    "certified",
    "validated",
    "optimal",
    "correct",
    "approved",
    "canonical",
    "best",
    "fixed",
}

DEFAULT_TARGETS = [
    "tap_tone_pi/agent",
    "tap_tone_pi/agentic",
    "tap_tone_pi/wolf",
    "analyzer/guidance",
]

EXEMPT_MARKER = "EXEMPT: guidance_language_guard"


@dataclass(frozen=True)
class Finding:
    path: Path
    line_no: int
    term: str
    context: str


def iter_files(
    root: Path, extensions: tuple[str, ...] = (".py", ".md")
) -> Iterator[Path]:
    """Iterate over files with given extensions under root."""
    if root.is_file():
        if root.suffix in extensions:
            yield root
        return
    if not root.exists():
        return
    for ext in extensions:
        yield from root.rglob(f"*{ext}")


def file_is_exempt(text: str) -> bool:
    """Check if file contains exemption marker."""
    return EXEMPT_MARKER in text


def extract_user_facing_strings_from_python(source: str) -> List[tuple[int, str]]:
    """Extract user-facing strings from Python source using AST.

    Returns list of (line_number, string_content) tuples.
    Extracts:
    - Module/class/function docstrings
    - String literals in assignments (e.g., summary="...")
    - String literals in function calls (e.g., print("..."))
    - F-strings (extracted as their string parts)
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    strings: List[tuple[int, str]] = []

    for node in ast.walk(tree):
        # Docstrings (module, class, function)
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            docstring = ast.get_docstring(node)
            if docstring:
                # Find the line number of the docstring
                if node.body and isinstance(node.body[0], ast.Expr):
                    if isinstance(node.body[0].value, ast.Constant):
                        strings.append((node.body[0].lineno, docstring))

        # String constants in expressions
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.append((node.lineno, node.value))

        # JoinedStr (f-strings) - extract string parts
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    strings.append((node.lineno, value.value))

    return strings


def scan_python_file(path: Path) -> List[Finding]:
    """Scan Python file for forbidden terms in user-facing strings."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    if file_is_exempt(text):
        return []

    findings: List[Finding] = []
    patterns = {
        term: re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for term in FORBIDDEN_TERMS
    }

    for line_no, string_content in extract_user_facing_strings_from_python(text):
        for term, pattern in patterns.items():
            if pattern.search(string_content):
                # Truncate context for display
                context = string_content[:80].replace("\n", " ")
                if len(string_content) > 80:
                    context += "..."
                findings.append(Finding(path, line_no, term, context))

    return findings


def scan_markdown_file(path: Path) -> List[Finding]:
    """Scan Markdown file for forbidden terms."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    if file_is_exempt(text):
        return []

    findings: List[Finding] = []
    patterns = {
        term: re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for term in FORBIDDEN_TERMS
    }

    for i, line in enumerate(text.splitlines(), start=1):
        for term, pattern in patterns.items():
            if pattern.search(line):
                context = line.strip()[:80]
                if len(line.strip()) > 80:
                    context += "..."
                findings.append(Finding(path, i, term, context))

    return findings


def scan_file(path: Path) -> List[Finding]:
    """Scan a single file for forbidden terms."""
    if path.suffix == ".py":
        return scan_python_file(path)
    elif path.suffix == ".md":
        return scan_markdown_file(path)
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan advisory modules for forbidden authority-claiming language"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any findings (default: exit 0 with report)",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_TARGETS,
        help="Paths to scan (default: advisory module directories)",
    )
    args = parser.parse_args()

    findings: List[Finding] = []
    for raw in args.paths:
        root = Path(raw)
        for path in iter_files(root):
            findings.extend(scan_file(path))

    if findings:
        print(f"[guidance_language] {len(findings)} finding(s):\n")
        for f in findings:
            print(f"  {f.path}:{f.line_no}: forbidden '{f.term}'")
            print(f"    {f.context}\n")

        if args.strict:
            print("[guidance_language] FAIL (--strict mode)")
            return 1
        else:
            print("[guidance_language] WARN (use --strict to fail)")
            return 0

    print("[guidance_language] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
