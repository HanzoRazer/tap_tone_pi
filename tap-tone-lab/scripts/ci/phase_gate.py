from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Iterable, List, Set


# ---- Policy knobs (edit these to match your repo) ----

# If any of these paths/globs are touched, PR requires OVERRIDE_LABEL.
PROTECTED_GLOBS: list[str] = [
    "tap_tone/capture.py",
    "tap_tone/analysis.py",
    "tap_tone/storage.py",
    "tap_tone/main.py",
    "tap_tone/ui_simple.py",
    "schemas/measurement.schema.json",
    "schemas/analysis.schema.json",
    "BASELINE.md",
]

# Optional: protect whole directories as well (uncomment if desired)
# PROTECTED_GLOBS += [
#     "tap_tone/*.py",
#     "schemas/*.json",
# ]

# PR must include at least one of these "phase classification" labels
REQUIRED_CLASS_LABELS: set[str] = {
    "phase2",
    "maintenance",
    "phase1-maintenance",
}

# If protected paths are touched, require this override label to proceed
OVERRIDE_LABEL: str = "phase1-approved"

# When protected paths touched, this label is also acceptable (if you want)
ALT_OVERRIDE_LABELS: set[str] = {
    # e.g. "maintainer-approved",
}

# ------------------------------------------------------


@dataclass(frozen=True)
class PRContext:
    number: int
    labels: Set[str]
    base_sha: str
    head_sha: str


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout.strip()


def _load_event(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_pr_context(event: dict) -> PRContext:
    pr = event.get("pull_request") or {}
    number = int(pr.get("number") or 0)

    labels = set()
    for lbl in pr.get("labels") or []:
        name = (lbl.get("name") or "").strip()
        if name:
            labels.add(name)

    base_sha = (pr.get("base") or {}).get("sha") or ""
    head_sha = (pr.get("head") or {}).get("sha") or ""

    if not base_sha or not head_sha:
        raise RuntimeError("Could not determine base/head SHA from GitHub event payload.")

    return PRContext(number=number, labels=labels, base_sha=base_sha, head_sha=head_sha)


def _match_any(path: str, globs: Iterable[str]) -> bool:
    return any(fnmatch(path, g) for g in globs)


def _git_changed_files(base_sha: str, head_sha: str) -> List[str]:
    # Ensure both SHAs exist locally (checkout fetch-depth:0 should handle this)
    # Use three-dot to compare PR head vs base merge-base behavior.
    out = _run(["git", "diff", "--name-only", f"{base_sha}...{head_sha}"])
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return files


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path:
        print("ERROR: GITHUB_EVENT_PATH not set.")
        return 2

    event = _load_event(event_path)
    ctx = _get_pr_context(event)

    changed = _git_changed_files(ctx.base_sha, ctx.head_sha)

    if not changed:
        print("OK: No changed files detected.")
        return 0

    # Phase classification label check (soft but useful)
    if not (ctx.labels & REQUIRED_CLASS_LABELS):
        print("FAIL: Missing required PR classification label.")
        print(f"Add one of these labels: {sorted(REQUIRED_CLASS_LABELS)}")
        print(f"Current labels: {sorted(ctx.labels) if ctx.labels else '[]'}")
        return 1

    protected_touched = [p for p in changed if _match_any(p, PROTECTED_GLOBS)]

    if protected_touched:
        override_ok = (OVERRIDE_LABEL in ctx.labels) or bool(ctx.labels & ALT_OVERRIDE_LABELS)
        if not override_ok:
            print("FAIL: Protected Phase 1 surface was modified without approval label.")
            print("")
            print("Protected files touched:")
            for p in protected_touched:
                print(f"  - {p}")
            print("")
            print("To proceed, add the override label:")
            print(f"  - {OVERRIDE_LABEL}")
            if ALT_OVERRIDE_LABELS:
                print("Or one of:")
                for lbl in sorted(ALT_OVERRIDE_LABELS):
                    print(f"  - {lbl}")
            print("")
            print("Rationale: Phase 1 baseline is frozen; touching protected files requires explicit approval.")
            return 1

        # If override label present, still warn loudly
        print("WARN: Protected Phase 1 files changed, but override label present.")
        for p in protected_touched:
            print(f"  - {p}")

    # Optional: If labeled phase2 AND touches protected, require override (already handled)
    # Optional: enforce experimental labeling rules via content checks (not implemented here)

    print("OK: Phase gate passed.")
    print(f"Changed files: {len(changed)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}")
        raise
