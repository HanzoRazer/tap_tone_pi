#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Check an E0 ADC characterization record for truthfulness. Read-only.

    python scripts/ttp_e0_adc_check.py path/to/e0_adc_characterization.json

**Exit 0 means the record is a structurally truthful account of a bench. It does
not mean the ADC is good.** E0 has no pass condition — T1 says so outright — and
this script computes no score, applies no threshold, and reaches no conclusion
about the device. A board that characterizes badly produces a perfectly valid
record; that is the point of running the protocol.

What it does check is whether the document claims more than it observed:

- the schema, and the typed contract behind it;
- that a ``PREPARED`` record carries no observations, and an ``EXECUTED`` one
  carries all of them;
- that T3 kept phase, not just amplitude;
- that T4 recorded nothing the source could not generate, and dropped nothing it
  could not reach;
- that T6 kept balanced and unbalanced apart;
- that referenced artifacts resolve and their digests agree, where the bytes are
  available to check.

It writes nothing, fills nothing in, smooths nothing, and closes no backlog item.
**B-014 in particular is not closed by the existence of a T4 section** — the
aliasing question is answered by reading the attenuation table, by a human.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.grant_readiness.e0_characterization import (  # noqa: E402
    E0_SCHEMA_VERSION,
    E0AdcCharacterizationV1,
    E0ControlGranularity,
    E0ExecutionStatus,
    E0InputPath,
    E0SourceCapability,
)
from tap_tone_pi.grant_readiness.errors import E0CharacterizationError  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "e0_adc_characterization.schema.json"

# The seven tests, and the field that shows one was run.
TEST_FIELDS = {
    "T1 noise floor": "noise_floor",
    "T2 PGA": "pga",
    "T3 coupling": "coupling",
    "T4 out of band": "out_of_band",
    "T5 balanced scope": "balanced_scope",
    "T6 full scale": "full_scale",
    "T7 loopback": "loopback",
}


def load_schema() -> dict[str, Any] | None:
    if not SCHEMA_PATH.exists():
        return None
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def check_schema(payload: Any) -> list[str]:
    schema = load_schema()
    if schema is None:
        return [f"schema not found at {SCHEMA_PATH.relative_to(REPO_ROOT)}"]
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - environment without the dependency
        return ["jsonschema is not installed; schema validation skipped"]
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"schema: {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    ]


def check_coverage(record: E0AdcCharacterizationV1) -> list[str]:
    """Report which tests are unrun. Not an error below EXECUTED."""
    observed = record.observed_groups()
    missing = [name for name, key in TEST_FIELDS.items() if not observed[key]]
    if record.execution_status is E0ExecutionStatus.EXECUTED and missing:
        return [
            "claims EXECUTED but has no observations for "
            + ", ".join(missing)
        ]
    return []


def check_source_capability(record: E0AdcCharacterizationV1) -> list[str]:
    """T4 must not answer a frequency the source could not ask.

    The contract already refuses a measured row above a declared bandwidth. This
    adds the softer half: if any row is blocked, the record should say what the
    source actually was, or a later reader cannot tell whether the limit was real.
    """
    problems: list[str] = []
    blocked = [
        o for o in record.out_of_band
        if o.source_state is E0SourceCapability.BLOCKED_BY_SOURCE_CAPABILITY
    ]
    if blocked and not record.provenance.source_equipment:
        problems.append(
            f"{len(blocked)} out-of-band frequenc(ies) are "
            "BLOCKED_BY_SOURCE_CAPABILITY but provenance.source_equipment is "
            "empty - a limit nobody can attribute to a source is not a finding"
        )
    if blocked and record.provenance.source_verified_bandwidth_hz is None:
        problems.append(
            "out-of-band rows are blocked on source capability but "
            "provenance.source_verified_bandwidth_hz is unset - the bandwidth "
            "the claim rests on is unrecorded"
        )
    return problems


def check_artifacts(record: E0AdcCharacterizationV1, base: Path) -> list[str]:
    """Verify digests where the bytes are reachable; say so where they are not."""
    problems: list[str] = []
    for artifact in record.provenance.artifacts:
        if not artifact.locator:
            continue
        path = (base / artifact.locator).resolve()
        if not path.exists():
            problems.append(
                f"artifact {artifact.artifact_id} names locator {artifact.locator!r}, "
                "which does not resolve"
            )
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != artifact.sha256:
            problems.append(
                f"artifact {artifact.artifact_id} digest mismatch: recorded "
                f"{artifact.sha256[:12]}..., file is {digest[:12]}..."
            )
    return problems


def summarize(record: E0AdcCharacterizationV1) -> list[str]:
    observed = record.observed_groups()
    lines = [
        f"characterization   {record.characterization_id}",
        f"device             {record.device.manufacturer} {record.device.model} "
        f"({record.device.local_id})",
        f"execution status   {record.execution_status.value}",
        "",
        "test                observations",
    ]
    for name, key in TEST_FIELDS.items():
        lines.append(f"  {name:<18} {'recorded' if observed[key] else '-'}")

    blocked = [
        o.injected_hz for o in record.out_of_band
        if o.source_state is E0SourceCapability.BLOCKED_BY_SOURCE_CAPABILITY
    ]
    if blocked:
        lines += [
            "",
            f"T4 blocked by source capability at "
            f"{', '.join(f'{hz:g}' for hz in sorted(blocked))} Hz.",
            "B-014 stays open across the untested range.",
        ]

    if record.balanced_scope.granularity is E0ControlGranularity.UNKNOWN:
        lines.append("")
        lines.append("T5 input-mode granularity is UNKNOWN - not the same as GLOBAL.")

    paths = {f.path for f in record.full_scale}
    if paths == {E0InputPath.UNBALANCED, E0InputPath.BALANCED}:
        lines.append("")
        lines.append("T6 recorded both input paths separately.")

    lines += [
        "",
        "This record is structurally truthful. It carries no judgement of the",
        "device: E0 has no pass condition, and none was computed.",
    ]
    return lines


def report(title: str, problems: Iterable[str]) -> int:
    found = list(problems)
    if not found:
        print(f"{title}: ok")
        return 0
    for problem in found:
        print(f"{title}: {problem}", file=sys.stderr)
    return len(found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check an E0 ADC characterization record (read-only)"
    )
    parser.add_argument("result", type=Path, help="path to e0_adc_characterization.json")
    parser.add_argument(
        "--summary", action="store_true", help="print what the record contains"
    )
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.result.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read {args.result}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print(f"{args.result}: top level must be an object", file=sys.stderr)
        return 1

    count = report("schema", check_schema(payload))

    try:
        record = E0AdcCharacterizationV1.from_dict(payload)
    except E0CharacterizationError as exc:
        print(f"contract: [{exc.code.value}] {exc.message}", file=sys.stderr)
        print("\n1 problem(s) found", file=sys.stderr)
        return 1
    print("contract: ok")

    count += report("coverage", check_coverage(record))
    count += report("source-capability", check_source_capability(record))
    count += report("artifacts", check_artifacts(record, args.result.parent))

    if args.summary:
        print()
        print("\n".join(summarize(record)))

    if count:
        print(f"\n{count} problem(s) found", file=sys.stderr)
        return 1
    print(f"\nE0 record is structurally truthful ({E0_SCHEMA_VERSION}).")
    print("This says nothing about whether the ADC is any good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
