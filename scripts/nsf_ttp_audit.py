#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Generate or check the TTP grant-readiness capability audit (DO-102).

    python scripts/nsf_ttp_audit.py --check
    python scripts/nsf_ttp_audit.py --write

``--check`` validates the declared capability inventory against the repository
and exits non-zero on any finding, without writing anything. ``--write``
generates the audit artifacts under ``out/nsf/``.

This is a script, not a ``ttp`` subcommand: DO-102 adds no CLI namespace.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.grant_readiness.audit import (  # noqa: E402
    audit_findings,
    build_grant_readiness_audit,
)
from tap_tone_pi.grant_readiness.report import (  # noqa: E402
    build_audit_report,
    canonical_json,
    render_audit_report,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "out" / "nsf"


def resolve_commit() -> str | None:
    """Return the current commit SHA, or None if git is unavailable.

    The package itself runs no subprocess; resolving the commit is the
    caller's job, and an unresolvable commit is recorded as unknown rather
    than guessed.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def display(path: Path) -> str:
    """Show a path relative to the repository where it is one."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit TTP capabilities against repository evidence"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Validate the inventory against the repository; write nothing",
    )
    mode.add_argument(
        "--write", action="store_true", help="Generate audit artifacts under out/nsf/"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated artifacts (default: out/nsf)",
    )
    parser.add_argument(
        "--audit-id", default="ttp-technical-baseline", help="Identifier for this audit"
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    findings = audit_findings()
    if findings:
        print(f"Capability audit found {len(findings)} problem(s):", file=sys.stderr)
        for finding in findings:
            print(f"  [{finding.code.value}] {finding.message}", file=sys.stderr)
        return 1

    if args.check:
        print("Capability audit clean: inventory agrees with the repository.")
        return 0

    audit = build_grant_readiness_audit(
        audit_id=args.audit_id,
        generated_at=utc_now(),
        repository_commit=resolve_commit(),
    )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ttp_technical_baseline.json"
    md_path = output_dir / "ttp_technical_baseline.md"

    json_path.write_text(canonical_json(build_audit_report(audit)), encoding="utf-8")
    md_path.write_text(render_audit_report(audit), encoding="utf-8")

    counts = audit.status_counts
    print(f"Wrote {display(json_path)}")
    print(f"Wrote {display(md_path)}")
    print(
        f"{len(audit.capabilities)} capabilities: "
        + ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    )
    print(
        f"Hardware-verified: {audit.hardware_verified_count} "
        "(no hardware campaign has been executed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
