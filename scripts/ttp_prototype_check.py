#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Check a TTP-PROTOTYPE-001 prototype-commissioning run. Read-only.

    python scripts/ttp_prototype_check.py out/prototype/run.json
    python scripts/ttp_prototype_check.py out/prototype/   # reads ttp_prototype_run.json

Verifies that a prototype run says only what its own record supports:

  * the document deserializes and validates against ttp_prototype_run_v1;
  * an R0 run does not claim controlled excitation, and an R2 run carries
    emission provenance for the signal it commanded;
  * an R1 run measures the mass it added;
  * a measured-force claim carries a force chain that could back it;
  * only HARDWARE-origin evidence is witnessed;
  * a run halted at a gate is recorded and names why;
  * a HARDWARE run retains raw artifacts, identified by digest.

This tool writes nothing, repairs nothing, and promotes nothing: it reports
that prototype evidence never qualifies a component or promotes PCB/production
readiness, and it never grants either. A run that fails here is reported, not
corrected.

Exit status is 0 when every check passes and 1 when any finding is reported.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.prototype.contracts import (
    PROTOTYPE_RUN_SCHEMA_VERSION,
)
from tap_tone_pi.prototype.validation import (
    promotion_notes,
    validate_prototype_run,
)

RUN_DOCUMENT = "ttp_prototype_run.json"
CONTRACTS = REPO_ROOT / "contracts"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def unwrap(payload: Any) -> Any:
    """Return the record itself, whether written bare or under a key."""
    if isinstance(payload, dict) and "prototype_run" in payload:
        return payload["prototype_run"]
    return payload


def check_schema(payload: Any) -> list[str]:
    """Validate the document against its contract, where jsonschema is present."""
    try:
        import jsonschema
    except ImportError:
        return ["NOTE: jsonschema is not installed; schema not checked"]
    schema_path = CONTRACTS / f"{PROTOTYPE_RUN_SCHEMA_VERSION}.schema.json"
    schema = read_json(schema_path)
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        return [f"run does not validate against its schema: {exc.message}"]
    return []


def check_run(path: Path) -> tuple[list[str], list[str]]:
    """Return (problems, notes) for one prototype run document."""
    problems: list[str] = []
    notes: list[str] = []

    document = read_json(path)
    payload = unwrap(document)
    if not isinstance(payload, dict):
        return (["prototype run document is not an object"], notes)

    problems.extend(check_schema(payload))
    problems.extend(
        f"[{finding.code}] {finding.message}"
        for finding in validate_prototype_run(payload)
    )

    notes.append(f"stage: {payload.get('stage')}")
    notes.append(f"status: {payload.get('status')}")
    notes.append(f"evidence origin: {payload.get('evidence_origin')}")
    notes.append(f"witnessed: {bool(payload.get('witnessed', False))}")
    notes.extend(promotion_notes())
    return (problems, notes)


def resolve(target: Path) -> Path | None:
    if target.is_dir():
        candidate = target / RUN_DOCUMENT
        return candidate if candidate.exists() else None
    return target if target.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a TTP-PROTOTYPE-001 prototype run (read-only)"
    )
    parser.add_argument(
        "run",
        type=Path,
        help=f"a {PROTOTYPE_RUN_SCHEMA_VERSION} JSON file, or a directory holding {RUN_DOCUMENT}",
    )
    args = parser.parse_args(argv)

    path = resolve(args.run)
    if path is None:
        print(f"no prototype run document at {args.run}", file=sys.stderr)
        return 1

    problems, notes = check_run(path)

    for note in notes:
        print(note)
    for problem in problems:
        print(problem, file=sys.stderr)

    if problems:
        print(f"{len(problems)} problem(s) found", file=sys.stderr)
        return 1
    print("prototype run evidence is internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
