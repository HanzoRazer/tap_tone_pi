#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""CI guard for tonewood radiation-ratio contract drift (BR-045).

Modes:
  1. Local pin check (default):
       verify contracts/tonewood_radiation_ratio_v1.json matches the approved
       semantic digest embedded in tests and recomputed from content.

  2. Cross-repo candidate check:
       python scripts/check_radiation_ratio_contract_parity.py \\
         --authority contracts/tonewood_radiation_ratio_v1.json \\
         --candidate /path/to/toolbox/contract.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.bending.radiation_ratio import (
    CONTRACT_SCHEMA_VERSION,
    FORMULA_ID,
    FORMULA_VERSION,
    OUTPUT_CONVENTION,
    SCALE_FACTOR,
    radiation_ratio_contract_digest,
    require_matching_semantic_digest,
)

APPROVED_SEMANTIC_DIGEST = (
    "182320dadca871d767fbd7e2341cfbb237a492e88dacddfc0736bc323ed9b898"
)
DEFAULT_AUTHORITY = REPO_ROOT / "contracts" / "tonewood_radiation_ratio_v1.json"


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: root must be a JSON object")
    return payload


def _assert_v1_identity(payload: dict, *, label: str) -> None:
    checks = [
        ("schema_version", CONTRACT_SCHEMA_VERSION),
        ("formula_id", FORMULA_ID),
        ("formula_version", FORMULA_VERSION),
        ("output_convention", OUTPUT_CONVENTION),
        ("scale_factor", SCALE_FACTOR),
    ]
    for key, expected in checks:
        actual = payload.get(key)
        if actual != expected:
            raise SystemExit(f"{label}: {key}={actual!r}, expected {expected!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authority",
        type=Path,
        default=DEFAULT_AUTHORITY,
        help="Tap Tone Pi authority contract path",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=None,
        help="Optional mirrored contract (e.g. Luthier's Toolbox) to compare",
    )
    args = parser.parse_args(argv)

    authority = _load(args.authority)
    _assert_v1_identity(authority, label=str(args.authority))
    digest = require_matching_semantic_digest(authority)
    if digest != APPROVED_SEMANTIC_DIGEST:
        raise SystemExit(
            f"authority digest {digest} != approved pin {APPROVED_SEMANTIC_DIGEST}"
        )
    print(f"OK authority digest={digest}")

    if args.candidate is not None:
        candidate = _load(args.candidate)
        _assert_v1_identity(candidate, label=str(args.candidate))
        candidate_digest = radiation_ratio_contract_digest(candidate)
        if candidate_digest != digest:
            raise SystemExit(
                "semantic digest mismatch:\n"
                f"  authority={digest}\n"
                f"  candidate={candidate_digest}"
            )
        # Fixture round-trip on rounded display values
        auth_fix = {
            f["fixture_id"]: f["expected_radiation_ratio_rounded"]
            for f in authority["conformance_fixtures"]
        }
        cand_fix = {
            f["fixture_id"]: f["expected_radiation_ratio_rounded"]
            for f in candidate["conformance_fixtures"]
        }
        if auth_fix != cand_fix:
            raise SystemExit(
                "fixture rounded expectations differ between authority and candidate"
            )
        print(f"OK candidate digest matches authority ({args.candidate})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
