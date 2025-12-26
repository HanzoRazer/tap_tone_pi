from __future__ import annotations

import json
import os
import subprocess
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

# PR must include at least one of these "phase classification" labels
REQUIRED_CLASS_LABELS: set[str] = {
    "phase2",
    "maintenance",
    "phase1-maintenance",
}

# If protected paths are touched, require this override label to proceed
OVERRIDE_LABEL: str = "phase1-approved"

# Alternative override labels (optional)
ALT_OVERRIDE_LABELS: set[str] = set()

# --- Strict experimental labeling rules ---
# Experimental scripts self-identify by prefix (NOT by folder).
# If any changed file matches these globs, require BOTH labels: phase2 + experimental.
EXPERIMENTAL_PATH_GLOBS: list[str] = [
    "scripts/wolf_*",
    "scripts/ir_*",
    "scripts/ods_*",
    "scripts/exp_*",
    "scripts/**/wolf_*",
    "scripts/**/ir_*",
    "scripts/**/ods_*",
    "scripts/**/exp_*",
]

REQUIRED_EXPERIMENTAL_LABELS: set[str] = {
    "phase2",
    "experimental",
}

# Symmetry: if PR has the `experimental` label, it must touch an experimental path
EXPERIMENTAL_LABEL: str = "experimental"

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

    # Require a classification label to avoid ambiguous intent
    if not (ctx.labels & REQUIRED_CLASS_LABELS):
        print("FAIL: Missing required PR classification label.")
        print(f"Add one of these labels: {sorted(REQUIRED_CLASS_LABELS)}")
        print(f"Current labels: {sorted(ctx.labels) if ctx.labels else '[]'}")
        return 1

    # Strict experimental rule (A): wolf_* script changes require phase2 + experimental
    experimental_touched = [p for p in changed if _match_any(p, EXPERIMENTAL_PATH_GLOBS)]
    if experimental_touched:
        missing = REQUIRED_EXPERIMENTAL_LABELS - ctx.labels
        if missing:
            print("FAIL: Experimental wolf_* scripts changed without required labels.")
            print("")
            print("Experimental paths touched:")
            for p in experimental_touched:
                print(f"  - {p}")
            print("")
            print("Required labels for this change:")
            for lbl in sorted(REQUIRED_EXPERIMENTAL_LABELS):
                print(f"  - {lbl}")
            print("")
            print("Missing labels:")
            for lbl in sorted(missing):
                print(f"  - {lbl}")
            return 1

    # Strict experimental rule (B): if PR is labeled experimental, it must touch experimental paths
    if EXPERIMENTAL_LABEL in ctx.labels and not experimental_touched:
        print("FAIL: PR has 'experimental' label but no experimental paths were changed.")
        print("")
        print("The 'experimental' label is reserved for changes under:")
        for g in EXPERIMENTAL_PATH_GLOBS:
            print(f"  - {g}")
        print("")
        print("Either remove the 'experimental' label, or ensure the change touches an experimental path.")
        return 1

    # Phase 1 protection: touching protected files requires explicit approval label
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

        print("WARN: Protected Phase 1 files changed, but override label present.")
        for p in protected_touched:
            print(f"  - {p}")

    print("OK: Phase gate passed.")
    print(f"Changed files: {len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
