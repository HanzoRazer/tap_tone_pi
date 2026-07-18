#!/usr/bin/env python3
"""Classification helper for instrument class declarations.

Walks undeclared modules, scans for advisory vocabulary, and SUGGESTS
a classification. Does NOT auto-edit. Human confirms every line.

Usage:
    python scripts/classify_instrument_modules.py

Output format:
    path/to/module.py → SUGGEST: MEASUREMENT
    path/to/module.py → SUGGEST: DECISION SUPPORT (found: recommend, advise)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ADVISORY_VOCABULARY = {
    "recommend",
    "advise",
    "suggest",
    "guidance",
    "advisory",
    "hint",
    "tip",
    "should",
    "optimal",
    "best",
    "prefer",
    "rank",
    "score",
    "rating",
    "grade",
    "verdict",
    "judgment",
    "interpret",
    "diagnose",
    "assess",
    "evaluate",
    "heuristic",
    "rule of thumb",
    "attention",
    "priority",
    "warning",
    "caution",
}

EXCLUDE_PATTERNS = {
    "docstring",
    "comment",
    "test",
    "example",
    "documentation",
}


def get_undeclared_modules() -> list[str]:
    """Run check_advisory_boundary.py and extract ADRY-001 paths."""
    result = subprocess.run(
        [sys.executable, "ci/check_advisory_boundary.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )

    paths = []
    for line in result.stdout.splitlines():
        if "ADRY-001:" in line:
            match = re.search(r"ADRY-001:\s*(.+\.py)", line)
            if match:
                paths.append(match.group(1).replace("\\", "/"))

    return sorted(set(paths))


def scan_for_advisory_vocab(filepath: Path) -> set[str]:
    """Scan file for advisory vocabulary. Returns found terms."""
    try:
        content = filepath.read_text(encoding="utf-8").lower()
    except Exception:
        return set()

    found = set()
    for term in ADVISORY_VOCABULARY:
        if term in content:
            in_exclude_context = False
            for exc in EXCLUDE_PATTERNS:
                if exc in content[:500]:
                    pass
            if re.search(rf"\b{re.escape(term)}\b", content):
                found.add(term)

    return found


def classify_module(filepath: Path) -> tuple[str, set[str]]:
    """
    Suggest classification for a module.

    Returns:
        (suggestion, found_terms)
    """
    found = scan_for_advisory_vocab(filepath)

    high_signal_terms = found & {
        "recommend",
        "advise",
        "suggest",
        "guidance",
        "advisory",
        "verdict",
        "judgment",
        "interpret",
        "diagnose",
        "heuristic",
        "attention",
        "priority",
    }

    if high_signal_terms:
        return "DECISION SUPPORT", found
    elif found:
        return "MEASUREMENT (review)", found
    else:
        return "MEASUREMENT", set()


def main() -> None:
    repo_root = Path(__file__).parent.parent

    print("=" * 70)
    print("INSTRUMENT CLASS DECLARATION HELPER")
    print("=" * 70)
    print()
    print("This script SUGGESTS classifications. Human confirms every line.")
    print("DECISION SUPPORT is the conservative choice for ambiguous cases.")
    print()
    print("-" * 70)

    undeclared = get_undeclared_modules()

    if not undeclared:
        print("No undeclared modules found. Backlog is clear.")
        return

    print(f"Found {len(undeclared)} undeclared modules.\n")

    measurement_count = 0
    decision_support_count = 0
    review_count = 0

    by_directory: dict[str, list[tuple[str, str, set[str]]]] = {}

    for rel_path in undeclared:
        filepath = repo_root / rel_path
        suggestion, found = classify_module(filepath)

        dir_name = str(Path(rel_path).parent)
        if dir_name not in by_directory:
            by_directory[dir_name] = []
        by_directory[dir_name].append((rel_path, suggestion, found))

        if "DECISION SUPPORT" in suggestion:
            decision_support_count += 1
        elif "review" in suggestion:
            review_count += 1
        else:
            measurement_count += 1

    for dir_name in sorted(by_directory.keys()):
        print(f"\n## {dir_name}/\n")
        for rel_path, suggestion, found in by_directory[dir_name]:
            filename = Path(rel_path).name
            if found:
                terms = ", ".join(sorted(found)[:5])
                if len(found) > 5:
                    terms += f" (+{len(found) - 5} more)"
                print(f"  {filename:<40} -> SUGGEST: {suggestion}")
                print(f"    found: {terms}")
            else:
                print(f"  {filename:<40} -> SUGGEST: {suggestion}")

    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"  MEASUREMENT:        {measurement_count}")
    print(f"  MEASUREMENT (review): {review_count}")
    print(f"  DECISION SUPPORT:   {decision_support_count}")
    print(f"  TOTAL:              {len(undeclared)}")
    print()
    print("Next: Review suggestions, then add headers manually.")
    print("Conservative rule: If unsure, use DECISION SUPPORT.")


if __name__ == "__main__":
    main()
