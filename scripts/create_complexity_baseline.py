#!/usr/bin/env python3
"""Create complexity baseline for tap_tone_pi."""

import json
import os
from pathlib import Path

try:
    from radon.complexity import cc_visit
except ImportError:
    print("Installing radon...")
    import subprocess

    subprocess.run(["python", "-m", "pip", "install", "radon", "-q"])
    from radon.complexity import cc_visit

THRESHOLD = 25
SKIP_DIRS = ["venv", "__pycache__", ".git", "node_modules", "site-packages", ".eggs"]


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)

    violations = []

    for pyfile in Path(".").rglob("*.py"):
        rel = str(pyfile)
        if any(skip in rel for skip in SKIP_DIRS):
            continue
        try:
            code = pyfile.read_text(encoding="utf-8")
            blocks = cc_visit(code)
            for block in blocks:
                if block.complexity > THRESHOLD:
                    violations.append(
                        {
                            "file": rel.replace(os.sep, "/"),
                            "function": block.name,
                            "complexity": block.complexity,
                            "line": block.lineno,
                            "letter": block.letter,
                        }
                    )
        except (SyntaxError, OSError, UnicodeDecodeError):
            pass

    violations.sort(key=lambda x: -x["complexity"])

    baseline = {
        "threshold": THRESHOLD,
        "violation_count": len(violations),
        "violations": violations,
    }

    out_path = root / "complexity_baseline.json"
    out_path.write_text(json.dumps(baseline, indent=2))
    print(
        f"Created {out_path.name} with {len(violations)} violations at threshold {THRESHOLD}"
    )

    for v in violations[:15]:
        print(f"  {v['complexity']:3d}  {v['file']}:{v['line']} - {v['function']}")
    if len(violations) > 15:
        print(f"  ... and {len(violations) - 15} more")


if __name__ == "__main__":
    main()
