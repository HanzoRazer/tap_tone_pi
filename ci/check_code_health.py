#!/usr/bin/env python3
"""CI code-health gates — complexity, maintainability, security, dead code.

Usage (individual gates):
    python ci/check_code_health.py complexity
    python ci/check_code_health.py maintainability
    python ci/check_code_health.py security
    python ci/check_code_health.py deadcode

Usage (all gates):
    python ci/check_code_health.py all

Exit codes: 0 = pass, 1 = gate failure, 2 = tool error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Thresholds (edit here to tighten gates over time)
# ---------------------------------------------------------------------------
# Complexity: no function worse than this grade
MAX_COMPLEXITY_GRADE = "D"            # reject E / F
MAX_AVG_COMPLEXITY = 16.0             # reject if average rises above this

# Maintainability: no file worse than this grade
MIN_MI_GRADE = "B"                    # reject C / D / F  (B = MI ≥ 10)

# Directories to scan
SCAN_DIRS = ["tap_tone_pi/", "scripts/", "modes/"]

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable  # Use the same interpreter that's running this script


def _run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    # Replace bare "python" with the current interpreter to respect venv
    if cmd and cmd[0] == "python":
        cmd = [PYTHON] + cmd[1:]
    return subprocess.run(
        cmd, capture_output=capture, text=True, cwd=ROOT,
    )


# ---------------------------------------------------------------------------
# Gate: Complexity (radon cc)
# ---------------------------------------------------------------------------
def check_complexity() -> bool:
    """Fail if any function is E/F grade or average CC exceeds threshold."""

    # Check for functions worse than the allowed grade
    worse_grade = chr(ord(MAX_COMPLEXITY_GRADE) + 1)  # e.g., "E" if max is "D"
    result = _run(
        ["python", "-m", "radon", "cc"] + SCAN_DIRS + ["-n", worse_grade, "-s", "-a"]
    )
    if result.returncode not in (0, 1):
        print(f"ERROR: radon cc failed: {result.stderr}")
        return False

    lines = result.stdout.strip().splitlines()
    # Last line is "Average complexity: X (N.N)" — parse it
    violations = []
    # avg_line initialized below in loop
    for line in lines:
        if line.strip().startswith("Average complexity:"):
            _avg_line = line.strip()  # noqa: F841
        elif " - " in line and "(" in line:
            # This is a function line like "    F 201:0 match_phases - D (22)"
            violations.append(line.strip())

    passed = True

    if violations:
        print(f"FAIL: {len(violations)} function(s) exceed grade {MAX_COMPLEXITY_GRADE}:")
        for v in violations:
            print(f"  {v}")
        passed = False
    else:
        print(f"PASS: No functions exceed grade {MAX_COMPLEXITY_GRADE}")

    # Check average CC from the full scan (all grades, no per-function output)
    full = _run(["python", "-m", "radon", "cc"] + SCAN_DIRS + ["-a"])
    combined = (full.stdout or "") + "\n" + (full.stderr or "")
    avg_found = False
    for line in reversed(combined.strip().splitlines()):
        if line.strip().startswith("Average complexity:"):
            # "Average complexity: C (14.33)"
            try:
                avg = float(line.split("(")[1].rstrip(")"))
                if avg > MAX_AVG_COMPLEXITY:
                    print(f"FAIL: Average CC {avg:.2f} exceeds threshold {MAX_AVG_COMPLEXITY}")
                    passed = False
                else:
                    print(f"PASS: Average CC {avg:.2f} <= {MAX_AVG_COMPLEXITY}")
                avg_found = True
            except (IndexError, ValueError):
                print(f"WARN: Could not parse average CC from: {line}")
            break
    if not avg_found:
        print("WARN: Could not determine average CC")

    return passed


# ---------------------------------------------------------------------------
# Gate: Maintainability (radon mi)
# ---------------------------------------------------------------------------
def check_maintainability() -> bool:
    """Fail if any file is below the minimum MI grade."""
    worse_grade = chr(ord(MIN_MI_GRADE) + 1)  # e.g., "C" if min is "B"
    result = _run(
        ["python", "-m", "radon", "mi"] + SCAN_DIRS + ["-n", worse_grade, "-s"]
    )
    if result.returncode not in (0, 1):
        print(f"ERROR: radon mi failed: {result.stderr}")
        return False

    violations = [
        line.strip()
        for line in result.stdout.strip().splitlines()
        if line.strip() and " - " in line
    ]

    if violations:
        print(f"FAIL: {len(violations)} file(s) below MI grade {MIN_MI_GRADE}:")
        for v in violations:
            print(f"  {v}")
        return False

    print(f"PASS: All files at MI grade {MIN_MI_GRADE} or better")
    return True


# ---------------------------------------------------------------------------
# Gate: Security (bandit)
# ---------------------------------------------------------------------------
def check_security() -> bool:
    """Fail if bandit finds any MEDIUM+ severity issue."""
    result = _run(
        ["python", "-m", "bandit", "-r", "tap_tone_pi/",
         "--severity-level", "medium", "-f", "json", "-q"]
    )

    if result.returncode == 2:
        print(f"ERROR: bandit crashed: {result.stderr}")
        return False

    # Exit code 0 = no findings. Bandit may or may not emit JSON.
    stdout = result.stdout.strip()
    if not stdout or result.returncode == 0:
        # Try to parse; if empty or no results, it's a clean pass.
        if not stdout:
            print("PASS: No MEDIUM+ security findings")
            return True
        try:
            data = json.loads(stdout)
            findings = data.get("results", [])
            if not findings:
                print("PASS: No MEDIUM+ security findings")
                return True
        except json.JSONDecodeError:
            print("PASS: No MEDIUM+ security findings")
            return True

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print("ERROR: Could not parse bandit output")
        return False

    findings = data.get("results", [])
    if findings:
        print(f"FAIL: {len(findings)} MEDIUM+ security finding(s):")
        for f in findings:
            print(f"  {f['test_id']} {f['severity']} "
                  f"{f['filename']}:{f['line_number']} — {f['issue_text'][:80]}")
        return False

    print("PASS: No MEDIUM+ security findings")
    return True


# ---------------------------------------------------------------------------
# Gate: Dead Code (vulture)
# ---------------------------------------------------------------------------
def check_deadcode() -> bool:
    """Fail if vulture finds any dead code at ≥90% confidence."""
    result = _run(
        ["python", "-m", "vulture",
         "tap_tone_pi/", "tests/", "vulture_whitelist.py",
         "--min-confidence", "90"]
    )

    findings = [
        line.strip()
        for line in result.stdout.strip().splitlines()
        if line.strip()
    ]

    if findings:
        print(f"FAIL: {len(findings)} dead-code finding(s):")
        for f in findings:
            print(f"  {f}")
        return False

    print("PASS: No dead code at ≥90% confidence")
    return True


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
GATES = {
    "complexity": check_complexity,
    "maintainability": check_maintainability,
    "security": check_security,
    "deadcode": check_deadcode,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0

    target = sys.argv[1]

    if target == "all":
        gates = list(GATES.values())
    elif target in GATES:
        gates = [GATES[target]]
    else:
        print(f"Unknown gate: {target!r}. Choose from: {', '.join(GATES)} or 'all'")
        return 2

    print(f"{'=' * 60}")
    print("Code Health Gates")
    print(f"{'=' * 60}")

    all_passed = True
    for gate_fn in gates:
        print(f"\n--- {gate_fn.__name__} ---")
        if not gate_fn():
            all_passed = False

    print(f"\n{'=' * 60}")
    if all_passed:
        print("ALL GATES PASSED")
    else:
        print("SOME GATES FAILED")
    print(f"{'=' * 60}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
