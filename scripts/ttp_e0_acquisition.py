#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Report what an E0 record supplies to an acquisition budget. Read-only.

    python scripts/ttp_e0_acquisition.py E0.json --sample-rate 48000 --pga-db -12
    python scripts/ttp_e0_acquisition.py E0.json --sample-rate 48000 --pga-db -12 \\
        --budget baseline_acquisition_budget.json

**Exit 0 means the report was produced. It does not mean the instrument is
evidence-grade, and it does not mean the ADC passed anything.** E0 has no pass
condition — its own protocol says so — and this script adds none: no threshold,
no score, no verdict about the device. A budget that is not evidence-grade is a
normal and expected result, not a failure of this command, so it does not change
the exit code.

Two modes, both read-only:

*Mapping.* With an E0 record alone, report which observations this repository
knows how to consume, which of them the record actually carries, and which E0
evidence stays characterization evidence with the reason it does.

*Budget.* Given a baseline ``acquisition_budget_v1`` as well, rebuild it with
E0's measured inputs and report the measured and non-measured inputs, any
unavailable section, and every blocking and advisory condition on the result.

Nothing is written. The baseline budget file is not modified, no session is
touched, and no acquisition happens: computing what a chain could resolve is not
measuring anything with it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.grant_readiness.e0_characterization import (  # noqa: E402
    E0AdcCharacterizationV1,
    E0InputPath,
)
from tap_tone_pi.grant_readiness.errors import E0CharacterizationError  # noqa: E402
from tap_tone_pi.uncertainty.acquisition import (  # noqa: E402
    AcquisitionBudgetV1,
    E0AdapterError,
    E0MappingStatus,
    E0OperatingPoint,
    Quantity,
    adapt_e0_characterization,
    build_acquisition_budget_from_e0,
    compare_budget_inputs,
    validate_acquisition_budget,
)
from tap_tone_pi.uncertainty.acquisition.quantities import (  # noqa: E402
    Provenance,
    ResultAvailability,
)

_RULE = "-" * 72


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: top level must be an object")
    return payload


def _section(title: str, lines: Iterable[str]) -> list[str]:
    body = list(lines)
    out = [title, _RULE]
    out += body if body else ["  (none)"]
    out.append("")
    return out


def _quantity_line(name: str, quantity: Quantity) -> str:
    return (
        f"  {name:<44} {quantity.value:>14.6g} {quantity.unit:<8} "
        f"{quantity.provenance.value}"
    )


def _input_quantities(budget: AcquisitionBudgetV1) -> list[tuple[str, Quantity]]:
    """Every input quantity in the budget, named by section and field."""
    found: list[tuple[str, Quantity]] = []
    for section in ("converter", "clock", "front_end", "capture", "sweep", "specimen"):
        spec = getattr(budget, section)
        if spec is None:
            continue
        for field in spec.__dataclass_fields__:
            value = getattr(spec, field)
            if isinstance(value, Quantity):
                found.append((f"{section}.{field}", value))
    return found


def report_mapping(adaptation) -> list[str]:
    """What the E0 record supplies, and what it deliberately does not."""
    lines = [
        f"E0 record          {adaptation.characterization_id}",
        f"execution status   {adaptation.execution_status.value}",
        "operating point    "
        + ", ".join(
            f"{k}={v}" for k, v in adaptation.operating_point.as_dict().items()
        ),
        "",
    ]

    lines += _section(
        "MEASURED INPUTS",
        [
            f"  {o.mapping.target:<32} {o.quantity.value:>12.6g} "
            f"{o.quantity.unit:<6}  {o.source}"
            for o in adaptation.outcomes
            if o.status is E0MappingStatus.CONSUMED and o.quantity is not None
        ],
    )

    lines += _section(
        "NOT SUPPLIED BY THIS RECORD",
        [
            f"  {o.mapping.target:<32} {o.status.value}\n      {o.detail}"
            for o in adaptation.outcomes
            if o.status is not E0MappingStatus.CONSUMED
        ],
    )

    lines += _section(
        "E0 EVIDENCE THAT IS NOT A BUDGET INPUT",
        [f"  {u.test} {u.group}\n      {u.reason}" for u in adaptation.unmapped],
    )
    return lines


def report_budget(
    budget: AcquisitionBudgetV1, baseline: AcquisitionBudgetV1
) -> list[str]:
    """The five sections DO-107B §16 asks a reader to be able to tell apart."""
    inputs = _input_quantities(budget)
    evidence = budget.evidence()

    lines = [f"PROFILE            {budget.profile}", ""]

    lines += _section(
        "MEASURED INPUTS",
        [
            _quantity_line(name, q) + (f"\n      {q.source}" if q.source else "")
            for name, q in inputs
            if q.provenance is Provenance.MEASURED
        ],
    )
    lines += _section(
        "NON-MEASURED INPUTS",
        [
            _quantity_line(name, q) + (f"   ({q.source})" if q.source else "")
            for name, q in inputs
            if q.provenance is not Provenance.MEASURED
        ],
    )

    unavailable = []
    for name, section in budget.as_dict()["results"].items():
        if (
            isinstance(section, dict)
            and section.get("availability") == ResultAvailability.UNAVAILABLE.value
        ):
            unavailable.append(
                f"  {name:<20} {section.get('reason_code', '')}\n      "
                f"{section.get('reason', '')}"
            )
    lines += _section("UNAVAILABLE SECTIONS", unavailable)

    lines += _section(
        "BLOCKING CONDITIONS",
        [
            f"  {r.condition.value}"
            + (f"  [{r.reference}]" if r.reference else "")
            + f"\n      {r.detail}"
            for r in evidence.reasons
            if r.blocking
        ],
    )
    lines += _section(
        "ADVISORIES",
        [
            f"  {r.condition.value}"
            + (f"  [{r.reference}]" if r.reference else "")
            + f"\n      {r.detail}"
            for r in evidence.reasons
            if not r.blocking
        ],
    )

    changed = compare_budget_inputs(baseline, budget)
    lines += _section(
        "WHAT CHARACTERIZATION CHANGED",
        [
            f"  {name}\n      {c['before']['value']:.6g} {c['before']['unit']} "
            f"({c['before']['provenance']})  ->  {c['after']['value']:.6g} "
            f"{c['after']['unit']} ({c['after']['provenance']})"
            if c["before"] is not None
            else f"  {name}\n      unset  ->  {c['after']['value']:.6g} "
            f"{c['after']['unit']} ({c['after']['provenance']})"
            for name, c in sorted(changed.items())
        ],
    )

    lines += [
        f"evidence grade     {str(evidence.evidence_grade).lower()}",
        "",
        "Evidence grade states whether this computation is valid on inputs that",
        "qualify. It is not a verdict on the converter, and E0 has no pass",
        "condition to report.",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report what an E0 characterization supplies to an acquisition "
            "budget (read-only)"
        )
    )
    parser.add_argument("record", type=Path, help="path to an E0 record JSON")
    parser.add_argument(
        "--sample-rate",
        type=float,
        required=True,
        help="sample rate the budget is written for; selects the T1 row exactly",
    )
    parser.add_argument(
        "--pga-db",
        type=float,
        required=True,
        help="PGA setting the budget is written for; selects the T1 row exactly",
    )
    parser.add_argument(
        "--input-path",
        choices=[p.value.lower() for p in E0InputPath],
        default=E0InputPath.UNBALANCED.value.lower(),
        help="input path the budget is written for; selects the T6 row",
    )
    parser.add_argument(
        "--budget",
        type=Path,
        help=(
            "baseline acquisition_budget_v1 JSON to inform. Without it, only the "
            "mapping is reported"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "emit the canonical serialized budget, or the mapping audit when no "
            "baseline budget is given"
        ),
    )
    args = parser.parse_args(argv)

    try:
        payload = _load_json(args.record)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot read {args.record}: {exc}", file=sys.stderr)
        return 1

    try:
        record = E0AdcCharacterizationV1.from_dict(payload)
    except E0CharacterizationError as exc:
        print(f"contract: [{exc.code.value}] {exc.message}", file=sys.stderr)
        return 1

    point = E0OperatingPoint(
        sample_rate_hz=args.sample_rate,
        pga_db=args.pga_db,
        input_path=E0InputPath(args.input_path.upper()),
    )

    if args.budget is None:
        try:
            adaptation = adapt_e0_characterization(record, point)
        except E0AdapterError as exc:
            print(f"adapter: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(adaptation.as_dict(), indent=2, sort_keys=True))
        else:
            print("\n".join(report_mapping(adaptation)))
        return 0

    try:
        baseline_payload = _load_json(args.budget)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot read {args.budget}: {exc}", file=sys.stderr)
        return 1

    problems = validate_acquisition_budget(baseline_payload)
    if problems:
        # A baseline that contradicts itself would carry that contradiction into
        # everything computed from it.
        for problem in problems:
            print(f"baseline: {problem}", file=sys.stderr)
        return 1

    try:
        baseline = AcquisitionBudgetV1.from_dict(baseline_payload)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"baseline: not an acquisition_budget_v1 record: {exc}", file=sys.stderr)
        return 1

    try:
        informed = build_acquisition_budget_from_e0(baseline, record, point)
    except E0AdapterError as exc:
        print(f"adapter: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(informed.budget.as_dict(), indent=2, sort_keys=True))
        return 0

    print("\n".join(report_mapping(informed.adaptation)))
    print(_RULE)
    print()
    print("\n".join(report_budget(informed.budget, baseline)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
