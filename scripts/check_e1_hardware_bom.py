#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Check the E1 hardware BOM against its own registers. Read-only.

    python scripts/check_e1_hardware_bom.py

DO-104P is a procurement order, so its integrity problems are not runtime
errors — they are a chain that cannot connect, or a document claiming something
nobody owns. This script checks the second kind, which is the kind that survives
into evidence.

The rule it exists for: **a design selection is not a possession.** The
repository's authoritative hardware stack specification names a Raspberry Pi 5,
a HiFiBerry ADC, and an OPA1612 preamp as *design* choices, and the repository
contains no evidence that any of them physically exists — every captured session
under ``runs_phase2/`` is synthetic or a demo fixture. So no component may reach
``RECEIVED`` or beyond on the strength of a design document: it needs a row in
the identity register carrying a real serial number or asset label.

This script recommends no products, infers no missing specification, and writes
nothing. It reports and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
HARDWARE = REPO_ROOT / "docs" / "hardware"

BOM_PATH = HARDWARE / "TTP_E1_HARDWARE_BOM.md"
REGISTER_PATH = HARDWARE / "TTP_E1_HARDWARE_IDENTITY_REGISTER.md"
MANIFEST_PATH = HARDWARE / "TTP_E1_DATASHEET_MANIFEST.json"
PROTOCOL_PATH = REPO_ROOT / "docs" / "NSF_TTP_E1_RIG_CHARACTERIZATION_PROTOCOL.md"

# Every class the chain needs. A missing class is a hole in the measurement
# chain, not a gap in a document.
REQUIRED_CLASSES = (
    "host",
    "adc_interface",
    "mic_preamp",
    "microphone",
    "force_transducer",
    "force_conditioner",
    "shaker",
    "amplifier",
    "stinger",
    "contact_tip",
    "stand_base",
    "reference_structure",
    "cabling",
)

# Conditional classes are permitted but never required: the attenuator exists
# only if the chosen conditioner cannot reach the ADC window on its own.
CONDITIONAL_CLASSES = ("attenuator",)

# The status ladder, in order. Each rung inherits the requirements below it.
STATUS_ORDER = (
    "TBD",
    "SELECTED",
    "ORDERED",
    "RECEIVED",
    "INSPECTED",
    "BENCH_READY",
)
TERMINAL_STATUSES = ("REJECTED",)

# Rungs at or above which physical possession is claimed, and must be evidenced.
OWNERSHIP_CLAIMED_FROM = "RECEIVED"

INSPECTION_STATUSES = (
    "NOT_RECEIVED",
    "RECEIVED_UNINSPECTED",
    "INSPECTED_OK",
    "INSPECTED_PROBLEM",
)

# Protocol inventory label -> BOM component class. Used to catch a protocol that
# still says TBD for something the BOM has already selected.
PROTOCOL_LABELS = {
    "Host": "host",
    "Mic preamp": "mic_preamp",
    "Force conditioner": "force_conditioner",
    "Shaker": "shaker",
    "Amplifier": "amplifier",
    "Force transducer": "force_transducer",
    "Audio interface": "adc_interface",
    "Microphone": "microphone",
    "Stinger stock": "stinger",
    "Contact tip": "contact_tip",
    "Rig base and stand": "stand_base",
    "Reference structure": "reference_structure",
}

# Values that mean "not filled in". A placeholder is not a value.
UNSET = {"", "tbd", "n/a", "-", "—", "none"}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def is_set(value: str) -> bool:
    return value.strip().lower() not in UNSET


def parse_table(path: Path, key: str) -> list[dict[str, str]]:
    """Read the first pipe table whose header contains ``key``.

    Deliberately strict: a row whose cell count does not match the header is
    reported rather than silently padded, because a shifted column turns one
    component's serial into another's.
    """
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if header is None:
            if key in cells:
                header = cells
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells if cell):
            continue
        if len(cells) != len(header):
            raise ValueError(
                f"{path.name}: row has {len(cells)} cells, header has "
                f"{len(header)}: {cells[:2]}"
            )
        rows.append(dict(zip(header, cells)))
    if header is None:
        raise ValueError(f"{path.name}: no table with a {key!r} column")
    return rows


def rung(status: str) -> int:
    """Position on the status ladder; -1 for terminal or unknown statuses."""
    return STATUS_ORDER.index(status) if status in STATUS_ORDER else -1


def check_bom(bom: list[dict[str, str]]) -> list[str]:
    problems: list[str] = []

    seen: dict[str, str] = {}
    for row in bom:
        local_id = row["local_id"]
        if local_id in seen:
            problems.append(f"duplicate local_id {local_id}")
        seen[local_id] = row["component_class"]

        status = row["status"]
        if status not in STATUS_ORDER and status not in TERMINAL_STATUSES:
            problems.append(f"{local_id}: unknown status {status!r}")
            continue

        level = rung(status)
        if level >= rung("SELECTED"):
            for field in ("manufacturer", "model"):
                if not is_set(row[field]):
                    problems.append(f"{local_id} is {status} but names no {field}")
        if level >= rung("ORDERED") and not is_set(row["supplier"]):
            problems.append(f"{local_id} is {status} but names no supplier")

    present = set(seen.values())
    for required in REQUIRED_CLASSES:
        if required not in present:
            problems.append(f"no BOM row for required component class {required}")
    for row in bom:
        cls = row["component_class"]
        if cls not in REQUIRED_CLASSES and cls not in CONDITIONAL_CLASSES:
            problems.append(
                f"{row['local_id']}: component_class {cls!r} is not a known class"
            )
    return problems


def check_ownership(
    bom: list[dict[str, str]], register: list[dict[str, str]]
) -> list[str]:
    """Possession claims must be backed by the identity register.

    This is the check the whole script exists for. A component reaches RECEIVED
    because someone has it, never because a design document names it.
    """
    problems: list[str] = []
    by_id = {row["local_id"]: row for row in register}

    for row in bom:
        local_id = row["local_id"]
        if rung(row["status"]) < rung(OWNERSHIP_CLAIMED_FROM):
            continue

        entry = by_id.get(local_id)
        if entry is None:
            problems.append(
                f"{local_id} is {row['status']} but has no identity-register entry"
            )
            continue

        if not (is_set(entry["serial_number"]) or is_set(entry["asset_label"])):
            problems.append(
                f"{local_id} is {row['status']} but its register entry carries "
                "neither a serial number nor an asset label - a design "
                "selection is not a possession"
            )
        if not is_set(entry["received_date"]):
            problems.append(
                f"{local_id} is {row['status']} but records no received_date"
            )
        if entry["inspection_status"] == "NOT_RECEIVED":
            problems.append(
                f"{local_id} is {row['status']} but its register entry says "
                "NOT_RECEIVED"
            )
        if (
            entry["inspection_status"] == "INSPECTED_PROBLEM"
            and row["status"] == "BENCH_READY"
        ):
            problems.append(
                f"{local_id} is BENCH_READY but was inspected with a problem"
            )
    return problems


def check_register(register: list[dict[str, str]]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for row in register:
        local_id = row["local_id"]
        if local_id in seen:
            problems.append(f"duplicate identity-register entry for {local_id}")
        seen.add(local_id)
        if row["inspection_status"] not in INSPECTION_STATUSES:
            problems.append(
                f"{local_id}: unknown inspection_status {row['inspection_status']!r}"
            )
    return problems


def check_manifest(manifest: dict, bom: list[dict[str, str]]) -> list[str]:
    problems: list[str] = []
    known = {row["local_id"] for row in bom}
    seen: set[tuple[str, str]] = set()

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return ["datasheet manifest has no entries list"]

    for entry in entries:
        component = entry.get("component_id", "")
        digest = entry.get("sha256", "")
        if component not in known:
            problems.append(
                f"datasheet manifest references {component!r}, which is not a "
                "BOM local_id"
            )
        if not _SHA256.match(str(digest)):
            problems.append(
                f"datasheet entry for {component!r} carries no SHA-256 digest"
            )
        if not entry.get("source_url") and not entry.get("local_archive_ref"):
            problems.append(
                f"datasheet entry for {component!r} names neither a source nor "
                "a local archive"
            )
        identity = (component, str(digest))
        if identity in seen:
            problems.append(f"duplicate datasheet identity for {component!r}")
        seen.add(identity)
    return problems


def check_protocol(bom: list[dict[str, str]]) -> list[str]:
    """The bench protocol must not still say TBD for a selected component."""
    if not PROTOCOL_PATH.exists():
        return [f"{PROTOCOL_PATH.name} is missing"]

    problems: list[str] = []
    try:
        inventory = parse_table(PROTOCOL_PATH, "Component")
    except ValueError as exc:
        return [f"cannot read the protocol inventory table: {exc}"]

    protocol_status = {row["Component"]: row.get("Status", "") for row in inventory}
    selected = {
        row["component_class"]
        for row in bom
        if rung(row["status"]) >= rung("SELECTED") and is_set(row["model"])
    }

    for label, cls in PROTOCOL_LABELS.items():
        if cls not in selected:
            continue
        status = protocol_status.get(label)
        if status is None:
            problems.append(
                f"protocol inventory has no {label!r} row, but the BOM selects a {cls}"
            )
        elif not is_set(status):
            problems.append(
                f"protocol inventory still says TBD for {label!r} while the BOM "
                f"has selected a {cls}"
            )
    return problems


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
        description="Check the E1 hardware BOM and its registers (read-only)"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print a status count per component class",
    )
    args = parser.parse_args(argv)

    try:
        bom = parse_table(BOM_PATH, "local_id")
        register = parse_table(REGISTER_PATH, "local_id")
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"cannot read the hardware documents: {exc}", file=sys.stderr)
        return 1

    count = 0
    count += report("bom", check_bom(bom))
    count += report("register", check_register(register))
    count += report("ownership", check_ownership(bom, register))
    count += report("datasheets", check_manifest(manifest, bom))
    count += report("protocol", check_protocol(bom))

    if args.summary:
        print()
        print(f"{'component_class':<22} {'local_id':<16} status")
        for row in bom:
            print(f"{row['component_class']:<22} {row['local_id']:<16} {row['status']}")
        owned = [
            row["local_id"]
            for row in bom
            if rung(row["status"]) >= rung(OWNERSHIP_CLAIMED_FROM)
        ]
        print()
        print(f"components claimed as physically in hand: {len(owned)}")
        if not owned:
            print("nothing is owned; DO-104E cannot begin bench bring-up")

    if count:
        print(f"\n{count} problem(s) found", file=sys.stderr)
        return 1
    print("\nhardware documents are internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
