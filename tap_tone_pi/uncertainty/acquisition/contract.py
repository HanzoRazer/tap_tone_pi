# INSTRUMENT CLASS: MEASUREMENT
"""Semantic invariants for an ``acquisition_budget_v1`` payload.

JSON Schema checks shape. These check *meaning*, and they live here rather than
being contorted into the schema because expressing them there would produce
conditional constructs nobody could read and a validator nobody could debug.

The invariants:

1. ``evidence_grade`` is true **iff** no reason is blocking. The boolean and the
   reasons cannot disagree.
2. ``combined_hz`` is the root-sum-square of the serialized frequency
   contributors and of nothing else.
3. An unavailable section carries **no numeric field** — nothing to mistake for
   a result, nothing fabricated.
4. A modulus result whose aggregation is not canonical identifies itself as such,
   and the corresponding advisory condition is disclosed.

**Duplicate contributors are legal.** A known composition defect is deliberately
represented rather than repaired, and a contract that refused to serialize the
computation's actual state would force a choice between lying and staying silent.

**Standard library only** — no ``jsonschema`` import here. Structural validation
belongs to whoever holds the schema file; this runs on the instrument.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

__all__ = ["validate_acquisition_budget", "SCHEMA_VERSION", "SCHEMA_FILE"]

SCHEMA_VERSION = "acquisition_budget_v1"
SCHEMA_FILE = "acquisition_budget_v1.schema.json"

_RSS_RELATIVE_TOLERANCE = 1e-9


def validate_acquisition_budget(payload: Mapping[str, Any]) -> list[str]:
    """Return semantic problems with a serialized budget. Empty means consistent.

    Read-only. Reports; never repairs, fills, or normalizes.
    """
    problems: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"schema_version must be {SCHEMA_VERSION!r}, "
            f"not {payload.get('schema_version')!r}"
        )

    problems += _check_evidence_consistency(payload)
    problems += _check_frequency_aggregate(payload)
    problems += _check_unavailable_sections(payload)
    problems += _check_aggregation_disclosure(payload)
    return problems


def _check_evidence_consistency(payload: Mapping[str, Any]) -> list[str]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, Mapping):
        return ["evidence section is missing"]

    reasons = evidence.get("reasons", [])
    blocking = [r for r in reasons if isinstance(r, Mapping) and r.get("blocking")]
    graded = bool(evidence.get("evidence_grade"))

    if graded and blocking:
        names = ", ".join(str(r.get("condition")) for r in blocking)
        return [
            f"evidence_grade is true while {len(blocking)} blocking condition(s) "
            f"are present: {names}"
        ]
    if not graded and not blocking:
        return [
            "evidence_grade is false but no reason is marked blocking - a false "
            "grade must say what blocked it"
        ]
    return []


def _check_frequency_aggregate(payload: Mapping[str, Any]) -> list[str]:
    frequency = payload.get("results", {}).get("frequency")
    if not isinstance(frequency, Mapping):
        return []

    contributors = frequency.get("combined_contributors")
    if not isinstance(contributors, list) or not contributors:
        return [
            "frequency.combined_contributors is empty, so combined_hz asserts a "
            "combination of nothing"
        ]

    values = []
    for index, entry in enumerate(contributors):
        if not isinstance(entry, Mapping) or "value_hz" not in entry:
            return [f"frequency.combined_contributors[{index}] records no value_hz"]
        values.append(float(entry["value_hz"]))

    expected = math.sqrt(sum(v * v for v in values))
    actual = float(frequency.get("combined_hz", float("nan")))
    if not math.isfinite(actual):
        return ["frequency.combined_hz is not a finite number"]
    tolerance = max(abs(expected) * _RSS_RELATIVE_TOLERANCE, 1e-18)
    if abs(actual - expected) > tolerance:
        return [
            f"frequency.combined_hz is {actual!r} but the root-sum-square of its "
            f"own contributors is {expected!r}. The combination must contain "
            "these values and nothing else"
        ]
    return []


def _check_unavailable_sections(payload: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for name, section in payload.get("results", {}).items():
        if not isinstance(section, Mapping):
            continue
        if section.get("availability") != "unavailable":
            continue
        if not section.get("reason_code") or not section.get("reason"):
            problems.append(
                f"results.{name} is unavailable but records no reason_code/reason"
            )
        numeric = sorted(
            key
            for key, value in section.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )
        if numeric:
            problems.append(
                f"results.{name} is unavailable but carries numeric field(s) "
                f"{', '.join(numeric)} - an unavailable section fabricates nothing"
            )
    return problems


def _check_aggregation_disclosure(payload: Mapping[str, Any]) -> list[str]:
    modulus = payload.get("results", {}).get("modulus")
    if not isinstance(modulus, Mapping):
        return []
    if modulus.get("availability") != "available":
        return []

    aggregation = modulus.get("aggregation", "")
    if aggregation == "canonical":
        return []

    if not aggregation:
        return ["results.modulus records no aggregation identity"]

    reasons = payload.get("evidence", {}).get("reasons", [])
    disclosed = any(
        isinstance(r, Mapping)
        and r.get("condition") == "aggregate_authority_workaround"
        for r in reasons
    )
    if not disclosed:
        return [
            f"results.modulus uses a non-canonical aggregation ({aggregation!r}) "
            "but no aggregate_authority_workaround condition is disclosed in the "
            "evidence reasons"
        ]
    return []
