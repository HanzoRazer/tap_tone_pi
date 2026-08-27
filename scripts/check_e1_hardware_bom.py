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

# Rungs at or above which *physical possession* is claimed, and must therefore
# be evidenced. Named for possession rather than ownership because this whole
# order turns on the difference between choosing a component and holding one.
PHYSICAL_POSSESSION_CLAIMED_FROM = "RECEIVED"

INSPECTION_STATUSES = (
    "NOT_RECEIVED",
    "RECEIVED_UNINSPECTED",
    "INSPECTED_OK",
    "INSPECTED_PROBLEM",
)

# --- DO-104S: tiered candidates -------------------------------------------
#
# A *role row* is one of the fourteen canonical BOM rows above: a slot in the
# measurement chain that the identity register and the bench protocol key on. A
# *candidate row* is a specific purchasable product proposed to fill one role at
# one tier. They are kept apart deliberately. Downstream identity machinery must
# never come to depend on a vendor choice, because then rejecting a vendor would
# break the register.

SELECTION_TIERS = ("RESEARCH_MINIMUM", "PREFERRED_E1", "REFERENCE_GRADE")

FUNCTIONAL_CHAINS = (
    "force_measurement",
    "contact_excitation",
    "response_acquisition",
    "synchronized_acquisition",
    "mechanical_support",
    "interconnect",
)

# Which chain each class serves. A candidate filed under the wrong chain is not a
# cosmetic error: it makes a tier look complete in a chain it does not serve.
CLASS_TO_CHAIN = {
    "host": "synchronized_acquisition",
    "adc_interface": "synchronized_acquisition",
    "microphone": "response_acquisition",
    "mic_preamp": "response_acquisition",
    "force_transducer": "force_measurement",
    "force_conditioner": "force_measurement",
    "attenuator": "force_measurement",
    "shaker": "contact_excitation",
    "amplifier": "contact_excitation",
    "stinger": "contact_excitation",
    "contact_tip": "contact_excitation",
    "stand_base": "mechanical_support",
    "reference_structure": "mechanical_support",
    "cabling": "interconnect",
}

# Roles every tier advertised as complete must fill.
MANDATORY_ROLE_CLASSES = (
    "host",
    "adc_interface",
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

# Required only when a tier's own selections make them necessary: an attenuator
# only if that tier's level budget overruns the input window, and a phantom
# preamp only if that tier's microphone is phantom-powered. A CCP microphone is
# conditioned by the ICP conditioner, so a tier choosing one legitimately has no
# preamp row - and padding one in to satisfy a count would be a false chain.
CONDITIONAL_ROLE_CLASSES = ("attenuator", "mic_preamp")

# Ownership is a statement about a physical object. UNKNOWN means nobody has
# looked; it does not mean absent.
OWNERSHIP_STATES = ("UNKNOWN", "CONFIRMED_PRESENT", "CONFIRMED_ABSENT")

PROCUREMENT_ACTIONS = (
    "HOLD",
    "VERIFY_POSSESSION",
    "RECOMMEND_PURCHASE",
    "USE_OWNED",
    "NO_PURCHASE_REQUIRED",
    "FABRICATE",
    "REJECTED",
)

# Actions that assert something about possession, and the state each needs.
# Both directions are guarded: you may not recommend buying what you have not
# established you lack, and you may not plan to use what you do not have.
ACTION_REQUIRES_OWNERSHIP = {
    "RECOMMEND_PURCHASE": "CONFIRMED_ABSENT",
    "USE_OWNED": "CONFIRMED_PRESENT",
    "NO_PURCHASE_REQUIRED": "CONFIRMED_PRESENT",
}

# Cost cells that are honest non-values. Neither is zero, and neither may be
# summed into a tier total.
COST_NON_VALUES = ("UNKNOWN", "QUOTE_REQUIRED")

# Availability states that are not market observations. A fabricated part has no
# vendor and no stock level, and demanding a distributor for one would push a
# document toward inventing a supplier for something nobody sells.
NON_MARKET_AVAILABILITY = ("UNKNOWN", "FABRICATED")

# Claims a selection order cannot confer. Selection is not possession, purchase
# is not validation, and a vendor listing is not a receipt.
FORBIDDEN_CANDIDATE_CLAIMS = (
    "RECEIVED",
    "INSPECTED",
    "BENCH_READY",
    "ASSEMBLED",
    "CALIBRATED",
    "VERIFIED_ON_HARDWARE",
)

# --- DO-104R: the physical ownership census ---------------------------------
#
# The census is the only thing in this repository that can establish possession.
# Everything else - a design document, a device profile, a prior selection, a
# recommendation - is forbidden as a source by DO-104O 4.4, so the checks here
# are mostly about stopping the census from claiming more than it observed.
#
# Note what is deliberately NOT here. The DO-104R model locks an observation
# axis for the identity register and inverts its orphan rule so it can hold
# observed assets no BOM row references. Both exist to represent *owned*
# hardware. The census found none, so building either would be adding a schema
# for data that does not exist - the error avoided by holding the state-model
# work until after the census. They land with the first owned asset.

CENSUS_PATH = HARDWARE / "TTP_E1_OWNERSHIP_CENSUS.md"

CENSUS_STATUSES = ("NOT_PERFORMED", "PERFORMED")

# How an observation was made. Kept separate from who made it, because a
# photograph establishes a visible marking and a hands-on inspection
# establishes rather more, and a single witnessed flag loses that.
OBSERVATION_METHODS = (
    "DIRECT_PHYSICAL_INSPECTION",
    "PHOTOGRAPHIC_EVIDENCE",
    "OPERATOR_ATTESTATION",
)

COMPATIBILITY_DISPOSITIONS = (
    "COMPATIBLE",
    "COMPATIBILITY_REQUIRES_VERIFICATION",
    "INCOMPATIBLE",
    "NOT_APPLICABLE",
)

# The ten categories DO-104O 3.1 requires. Nine map to a BOM role; the speaker
# is carried because a census will encounter it and its state must not be
# inferred from its absence from the BOM.
CENSUS_REQUIRED_ROLES = (
    "HOST-001",
    "ADC-001",
    "PREAMP-001",
    "MIC-001",
    "AMP-001",
    "FORCE-001",
    "PRECOND-001",
    "SHAKER-001",
    "STAND-001",
)
CENSUS_REQUIRED_CATEGORY_COUNT = 10

CENSUS_KEY = "Category"
REQUIRED_CENSUS_COLUMNS = (
    "Category",
    "BOM role",
    "Ownership",
    "Manufacturer",
    "Model",
    "Serial / asset ID",
    "Observation method",
    "Disposition",
)

CANDIDATE_KEY = "candidate_id"
SPEC_KEY = "spec_for"

REQUIRED_CANDIDATE_COLUMNS = (
    "candidate_id",
    "role_local_id",
    "component_class",
    "functional_chain",
    "selection_tier",
    "quantity",
    "unit_cost_usd",
    "extended_cost_usd",
    "availability",
    "lead_time",
    "commercial_source",
    "checked_date",
    "procurement_action",
    "ownership",
)
REQUIRED_SPEC_COLUMNS = (
    "spec_for",
    "manufacturer",
    "model",
    "powering",
    "key_specification",
    "technical_source",
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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

# Columns each document must carry. A dropped column is a document-integrity
# problem and gets reported as one: without this the first row access raises a
# KeyError, and a traceback names the column but not the document, the row, or
# what a reader should do about it.
REQUIRED_BOM_COLUMNS = (
    "local_id",
    "component_class",
    "manufacturer",
    "model",
    "status",
    "supplier",
)
REQUIRED_REGISTER_COLUMNS = (
    "local_id",
    "serial_number",
    "asset_label",
    "received_date",
    "inspection_status",
)

# Values that mean "not filled in". A placeholder is not a value.
UNSET = {"", "tbd", "n/a", "-", "—", "none"}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def is_set(value: object) -> bool:
    """Whether a cell carries a real value rather than a placeholder.

    Accepts any type: a malformed document can put ``null`` or a number where a
    string belongs, and a validator that crashes on bad input reports nothing
    about the input that broke it.
    """
    if value is None:
        return False
    return str(value).strip().lower() not in UNSET


def parse_table(
    path: Path, key: str, required: tuple[str, ...] = ()
) -> list[dict[str, str]]:
    """Read the first pipe table whose header contains ``key``.

    Deliberately strict in two ways. A row whose cell count does not match the
    header is reported rather than silently padded, because a shifted column
    turns one component's serial into another's. And a table missing a required
    column is refused up front, so a dropped column is reported as the document
    problem it is instead of surfacing later as a ``KeyError`` naming neither
    the document nor the row.
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
    missing = [column for column in required if column not in header]
    if missing:
        raise ValueError(
            f"{path.name}: table is missing column(s) {', '.join(missing)}"
        )
    return rows


def rung(status: str) -> int:
    """Position on the status ladder; -1 for terminal or unknown statuses."""
    return STATUS_ORDER.index(status) if status in STATUS_ORDER else -1


def check_bom(bom: list[dict[str, str]]) -> list[str]:
    problems: list[str] = []

    seen: dict[str, str] = {}
    for row in bom:
        local_id = row.get("local_id", "")
        if local_id in seen:
            problems.append(f"duplicate local_id {local_id}")
        seen[local_id] = row.get("component_class", "")

        status = row.get("status", "")
        if status not in STATUS_ORDER and status not in TERMINAL_STATUSES:
            problems.append(f"{local_id}: unknown status {status!r}")
            continue

        level = rung(status)
        if level >= rung("SELECTED"):
            for field in ("manufacturer", "model"):
                if not is_set(row.get(field)):
                    problems.append(f"{local_id} is {status} but names no {field}")
        if level >= rung("ORDERED") and not is_set(row.get("supplier")):
            problems.append(f"{local_id} is {status} but names no supplier")

    present = set(seen.values())
    for required in REQUIRED_CLASSES:
        if required not in present:
            problems.append(f"no BOM row for required component class {required}")
    for row in bom:
        cls = row.get("component_class", "")
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
        if rung(row["status"]) < rung(PHYSICAL_POSSESSION_CLAIMED_FROM):
            continue

        entry = by_id.get(local_id)
        if entry is None:
            problems.append(
                f"{local_id} is {row['status']} but has no identity-register entry"
            )
            continue

        if not (is_set(entry.get("serial_number")) or is_set(entry.get("asset_label"))):
            problems.append(
                f"{local_id} is {row['status']} but its register entry carries "
                "neither a serial number nor an asset label - a design "
                "selection is not a possession"
            )
        if not is_set(entry.get("received_date")):
            problems.append(
                f"{local_id} is {row['status']} but records no received_date"
            )
        if entry.get("inspection_status") == "NOT_RECEIVED":
            problems.append(
                f"{local_id} is {row['status']} but its register entry says "
                "NOT_RECEIVED"
            )
        if (
            entry.get("inspection_status") == "INSPECTED_PROBLEM"
            and row["status"] == "BENCH_READY"
        ):
            problems.append(
                f"{local_id} is BENCH_READY but was inspected with a problem"
            )
    return problems


def check_register(
    register: list[dict[str, str]], bom: list[dict[str, str]]
) -> list[str]:
    """The register describes physical objects, so every row must name a real one.

    An orphan row — a mistyped ``FORSE-001``, or an entry left behind after a
    component was renumbered — is not harmless. The register is what an
    ownership claim is checked against, so a row nobody can trace to a BOM
    component is a place where a serial number can attach to nothing.
    """
    problems: list[str] = []
    known = {row["local_id"] for row in bom}
    seen: set[str] = set()

    for row in register:
        local_id = row["local_id"]
        if local_id in seen:
            problems.append(f"duplicate identity-register entry for {local_id}")
        seen.add(local_id)

        if local_id not in known:
            problems.append(
                f"identity register names {local_id}, which is not a BOM component"
            )

        status = row.get("inspection_status", "")
        if status not in INSPECTION_STATUSES:
            problems.append(f"{local_id}: unknown inspection_status {status!r}")

    return problems


def check_manifest(manifest: dict, bom: list[dict[str, str]]) -> list[str]:
    problems: list[str] = []
    known = {row["local_id"] for row in bom}
    seen: set[tuple[str, str]] = set()

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return ["datasheet manifest has no entries list"]

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"datasheet entry {index} is not an object")
            continue
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

    # Only classes the protocol actually tracks, and only the status question:
    # ``check_bom`` already refuses a SELECTED row with no model, so testing the
    # model here again would make this check depend on that one silently.
    tracked = set(PROTOCOL_LABELS.values())
    selected = {
        row["component_class"]
        for row in bom
        if row["component_class"] in tracked and rung(row["status"]) >= rung("SELECTED")
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


def parse_optional_table(
    path: Path, key: str, required: tuple[str, ...] = ()
) -> list[dict[str, str]] | None:
    """Read a table that a DO-104P-shaped document is allowed not to have yet.

    Returns ``None`` when no table carries ``key``, so a BOM predating the
    tiered candidates still validates. A table that *is* present is held to the
    full column contract: a half-present candidate table is a document error,
    not an earlier revision.
    """
    try:
        return parse_table(path, key, required)
    except ValueError as exc:
        if f"no table with a {key!r} column" in str(exc):
            return None
        raise


def as_money(value: str) -> float | None:
    """Parse a currency cell, or ``None`` if it is not a number.

    A non-numeric cell is never coerced to 0.0. That coercion is the specific
    failure this whole cost section exists to prevent: an unpriced part summing
    into a tier total as free.
    """
    text = str(value).strip().lstrip("$").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def group_candidates_by_tier(
    candidates: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Bucket candidates by selection tier, preserving document order."""
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        grouped.setdefault(row.get("selection_tier", ""), []).append(row)
    return grouped


def validate_tier_vocabulary(candidates: list[dict[str, str]]) -> list[str]:
    problems: list[str] = []
    for row in candidates:
        tier = row.get("selection_tier", "")
        if tier not in SELECTION_TIERS:
            problems.append(
                f"{row.get(CANDIDATE_KEY, '?')}: unknown selection_tier {tier!r}"
            )
    return problems


def validate_candidate_identity(
    candidates: list[dict[str, str]], bom: list[dict[str, str]]
) -> list[str]:
    """Candidate ids are unique, and each names a role that actually exists."""
    problems: list[str] = []
    roles = {row["local_id"]: row.get("component_class", "") for row in bom}
    seen: set[str] = set()

    for row in candidates:
        cid = row.get(CANDIDATE_KEY, "")
        if not is_set(cid):
            problems.append("a candidate row carries no candidate_id")
            continue
        if cid in seen:
            problems.append(f"duplicate candidate_id {cid}")
        seen.add(cid)

        role = row.get("role_local_id", "")
        if role not in roles:
            problems.append(f"{cid}: role_local_id {role!r} is not a canonical BOM row")
            continue

        cls = row.get("component_class", "")
        if cls != roles[role]:
            problems.append(
                f"{cid}: component_class {cls!r} does not match role {role}, "
                f"which is a {roles[role]!r}"
            )
    return problems


def validate_functional_chain(candidates: list[dict[str, str]]) -> list[str]:
    """Each candidate sits in the chain its component class actually serves."""
    problems: list[str] = []
    for row in candidates:
        cid = row.get(CANDIDATE_KEY, "?")
        chain = row.get("functional_chain", "")
        cls = row.get("component_class", "")
        if chain not in FUNCTIONAL_CHAINS:
            problems.append(f"{cid}: unknown functional_chain {chain!r}")
            continue
        expected = CLASS_TO_CHAIN.get(cls)
        if expected is None:
            continue
        if chain != expected:
            problems.append(
                f"{cid}: a {cls} belongs to the {expected} chain, not {chain!r}"
            )
    return problems


def validate_measured_force(
    candidates: list[dict[str, str]], specs: dict[str, dict[str, str]]
) -> list[str]:
    """The measured-force role is filled by something that measures force.

    A drive-side component cannot satisfy it. Commanded voltage is not force,
    amplifier output is not force, and a microphone relabelled onto ch0 is not
    force - so a candidate whose class belongs to the excitation or response
    chain may not be filed against the force transducer role.
    """
    problems: list[str] = []
    for row in candidates:
        cid = row.get(CANDIDATE_KEY, "?")
        if row.get("role_local_id") != "FORCE-001":
            continue
        cls = row.get("component_class", "")
        if cls != "force_transducer":
            problems.append(
                f"{cid}: a {cls!r} cannot fill the measured-force role - "
                "commanded excitation is not a force measurement"
            )
        spec = specs.get(cid, {})
        powering = str(spec.get("powering", "")).lower()
        model = str(spec.get("model", "")).lower()
        for banned in ("commanded", "dac output", "amplifier output"):
            if banned in model or banned in powering:
                problems.append(
                    f"{cid}: {banned!r} appears in the measured-force "
                    "candidate's own specification"
                )
    return problems


def validate_tier_completeness(
    candidates: list[dict[str, str]], specs: dict[str, dict[str, str]]
) -> list[str]:
    """A tier presented as complete supplies every mandatory role.

    The phantom preamp is the interesting case. It is required only when that
    tier's microphone is phantom-powered; a CCP microphone is conditioned by the
    ICP conditioner instead. Deciding this from the tier's own microphone spec is
    the point - it means a tier cannot look complete by carrying a preamp its
    chain never uses, nor incomplete for correctly omitting one.
    """
    problems: list[str] = []
    for tier, rows in sorted(group_candidates_by_tier(candidates).items()):
        if tier not in SELECTION_TIERS:
            continue
        present = {row.get("component_class", "") for row in rows}

        for required in MANDATORY_ROLE_CLASSES:
            if required not in present:
                problems.append(
                    f"{tier} is incomplete: no candidate for the required role "
                    f"{required}"
                )

        mics = [row for row in rows if row.get("component_class") == "microphone"]
        for mic in mics:
            powering = str(
                specs.get(mic.get(CANDIDATE_KEY, ""), {}).get("powering", "")
            ).lower()
            if not is_set(powering):
                problems.append(
                    f"{mic.get(CANDIDATE_KEY, '?')}: microphone powering is not "
                    "recorded, so the tier's response conditioning cannot be "
                    "resolved"
                )
                continue
            if "phantom" in powering and "mic_preamp" not in present:
                problems.append(
                    f"{tier} is incomplete: its microphone is phantom-powered "
                    "but the tier has no mic_preamp candidate"
                )
    return problems


def validate_cost_fields(candidates: list[dict[str, str]]) -> list[str]:
    """Cost arithmetic, and the rule that an unknown price is not zero."""
    problems: list[str] = []
    for row in candidates:
        cid = row.get(CANDIDATE_KEY, "?")
        quantity_text = str(row.get("quantity", "")).strip()
        unit_text = str(row.get("unit_cost_usd", "")).strip()
        extended_text = str(row.get("extended_cost_usd", "")).strip()

        try:
            quantity = int(quantity_text)
        except ValueError:
            problems.append(f"{cid}: quantity {quantity_text!r} is not a number")
            continue
        if quantity <= 0:
            problems.append(f"{cid}: quantity must be greater than zero")

        unit = as_money(unit_text)
        extended = as_money(extended_text)

        if unit is None:
            if unit_text not in COST_NON_VALUES:
                problems.append(
                    f"{cid}: unit_cost_usd {unit_text!r} is neither a number nor "
                    f"one of {', '.join(COST_NON_VALUES)}"
                )
            elif extended_text != unit_text:
                problems.append(
                    f"{cid}: unit cost is {unit_text} but extended cost is "
                    f"{extended_text!r} - an unpriced row must stay unpriced "
                    "rather than resolve to a number"
                )
            continue

        if extended is None:
            problems.append(
                f"{cid}: unit cost is numeric but extended cost {extended_text!r} "
                "is not"
            )
            continue
        if abs(extended - unit * quantity) > 0.005:
            problems.append(
                f"{cid}: extended cost {extended:.2f} does not equal quantity "
                f"{quantity} x unit cost {unit:.2f}"
            )
    return problems


def validate_source_provenance(
    candidates: list[dict[str, str]], specs: dict[str, dict[str, str]]
) -> list[str]:
    """Every candidate has technical authority; every market claim has a date.

    The two are deliberately separate. A distributor establishes price and
    stock; it does not become technical authority by being the only page that
    loaded.
    """
    problems: list[str] = []
    for row in candidates:
        cid = row.get(CANDIDATE_KEY, "?")
        spec = specs.get(cid)
        if spec is None:
            problems.append(f"{cid}: no specification row (no spec_for entry)")
            continue
        if not is_set(spec.get("technical_source")):
            problems.append(f"{cid}: names no technical source")
        for field in ("manufacturer", "model"):
            if not is_set(spec.get(field)):
                problems.append(f"{cid}: specification names no {field}")

        availability = str(row.get("availability", "")).strip()
        commercial_claimed = as_money(row.get("unit_cost_usd", "")) is not None or (
            is_set(availability) and availability not in NON_MARKET_AVAILABILITY
        )
        if commercial_claimed:
            if not is_set(row.get("commercial_source")):
                problems.append(
                    f"{cid}: records price or availability but names no "
                    "commercial source"
                )
            checked = str(row.get("checked_date", "")).strip()
            if not _ISO_DATE.match(checked):
                problems.append(
                    f"{cid}: records price or availability but its checked_date "
                    f"{checked!r} is not an ISO-8601 date - a market observation "
                    "without a date is not an observation"
                )
    return problems


def validate_procurement_semantics(candidates: list[dict[str, str]]) -> list[str]:
    """Ownership, procurement action, and selection tier stay independent.

    The rule that matters: purchase may only be recommended for something
    established as absent. Recommending a purchase against UNKNOWN ownership is
    the inference error - UNKNOWN means nobody looked, and buying on that basis
    is how a lab ends up with two of something it already had.
    """
    problems: list[str] = []
    for row in candidates:
        cid = row.get(CANDIDATE_KEY, "?")
        ownership = row.get("ownership", "")
        action = row.get("procurement_action", "")

        if ownership not in OWNERSHIP_STATES:
            problems.append(f"{cid}: unknown ownership state {ownership!r}")
        if action not in PROCUREMENT_ACTIONS:
            problems.append(f"{cid}: unknown procurement_action {action!r}")

        required = ACTION_REQUIRES_OWNERSHIP.get(action)
        if required is not None and ownership != required:
            problems.append(
                f"{cid}: {action} with ownership {ownership!r}, which requires "
                f"{required}. An action that asserts possession must be backed "
                "by an observation - UNKNOWN means nobody has looked yet"
            )

        for cell, value in row.items():
            if cell in ("key_specification", "commercial_source"):
                continue
            for claim in FORBIDDEN_CANDIDATE_CLAIMS:
                if str(value).strip().upper() == claim:
                    problems.append(
                        f"{cid}: {cell} claims {claim} - a selection order "
                        "cannot confer physical or verification status"
                    )
    return problems


def check_candidates(
    candidates: list[dict[str, str]] | None,
    specs: list[dict[str, str]] | None,
    bom: list[dict[str, str]],
) -> list[str]:
    """Run the DO-104S candidate checks, if the document carries candidates."""
    if candidates is None:
        return []
    if specs is None:
        return ["the BOM carries candidate rows but no specification table"]

    by_id: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for spec in specs:
        key = spec.get(SPEC_KEY, "")
        if key in by_id:
            problems.append(f"duplicate specification row for {key}")
        by_id[key] = spec

    known = {row.get(CANDIDATE_KEY, "") for row in candidates}
    for key in by_id:
        if key not in known:
            problems.append(
                f"specification table describes {key!r}, which is not a candidate"
            )

    problems += validate_tier_vocabulary(candidates)
    problems += validate_candidate_identity(candidates, bom)
    problems += validate_functional_chain(candidates)
    problems += validate_measured_force(candidates, by_id)
    problems += validate_tier_completeness(candidates, by_id)
    problems += validate_cost_fields(candidates)
    problems += validate_source_provenance(candidates, by_id)
    problems += validate_procurement_semantics(candidates)
    return problems


def check_candidate_datasheets(
    manifest: dict,
    candidates: list[dict[str, str]] | None,
    specs: list[dict[str, str]] | None,
) -> list[str]:
    """Preferred candidates resting on manufacturer documents must be covered.

    Coverage is declared by the manifest rather than inferred, and it is checked
    only for the preferred tier: a rejected or reference-only candidate may
    legitimately rest on a page that was read but not retrievable as a document.
    """
    if candidates is None or specs is None:
        return []

    problems: list[str] = []
    covered: set[str] = set()
    all_ids = {row.get(CANDIDATE_KEY, "") for row in candidates}

    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            continue
        for cid in entry.get("covers_candidates", []) or []:
            if cid not in all_ids:
                problems.append(
                    f"datasheet manifest claims to cover {cid!r}, which is not a "
                    "candidate"
                )
            covered.add(cid)

    fabricated = {"fabricated", "assorted", "custom build"}
    by_id = {spec.get(SPEC_KEY, ""): spec for spec in specs}
    for row in candidates:
        if row.get("selection_tier") != "PREFERRED_E1":
            continue
        cid = row.get(CANDIDATE_KEY, "")
        maker = str(by_id.get(cid, {}).get("manufacturer", "")).strip().lower()
        if maker in fabricated:
            continue
        if cid not in covered:
            problems.append(
                f"{cid} is a PREFERRED_E1 candidate from {maker!r} but no "
                "datasheet manifest entry covers it"
            )
    return problems


def census_status(text: str) -> str:
    """The declared status from the census document header."""
    match = re.search(r"^\*\*Status:\*\*\s*`([A-Z_]+)`", text, re.MULTILINE)
    return match.group(1) if match else ""


def validate_census_role_coverage(census: list[dict[str, str]]) -> list[str]:
    """Every required category appears. Silence is not absence.

    The failure this prevents is an item going unmentioned and later being read
    as CONFIRMED_ABSENT - which would be a purchase recommendation built on
    nobody having looked.
    """
    problems: list[str] = []
    roles = {row.get("BOM role", "").strip() for row in census}
    for required in CENSUS_REQUIRED_ROLES:
        if required not in roles:
            problems.append(f"census has no row for required role {required}")
    if len(census) < CENSUS_REQUIRED_CATEGORY_COUNT:
        problems.append(
            f"census covers {len(census)} categories; "
            f"{CENSUS_REQUIRED_CATEGORY_COUNT} are required"
        )
    return problems


def validate_owned_asset_identity(
    census: list[dict[str, str]], register: list[dict[str, str]]
) -> list[str]:
    """Possession claims carry identity; absences carry none.

    Both directions matter. An owned item with no identity cannot be
    distinguished from another unit of the same model, and an absent item
    carrying a serial number is a fabricated observation.
    """
    problems: list[str] = []
    known = {row["local_id"] for row in register}

    for row in census:
        category = row.get("Category", "?")
        ownership = row.get("Ownership", "").strip()
        role = row.get("BOM role", "").strip()
        identity = row.get("Serial / asset ID", "")
        maker = row.get("Manufacturer", "")
        model = row.get("Model", "")

        if ownership not in OWNERSHIP_STATES:
            problems.append(f"{category}: unknown ownership {ownership!r}")
            continue

        if ownership == "CONFIRMED_PRESENT":
            for field, value in (("manufacturer", maker), ("model", model)):
                if not is_set(value):
                    problems.append(
                        f"{category} is CONFIRMED_PRESENT but records no {field}"
                    )
            if not is_set(identity):
                problems.append(
                    f"{category} is CONFIRMED_PRESENT but carries no serial or "
                    "asset identifier - an owned unit must be distinguishable "
                    "from another of the same model"
                )
            if role in known and role not in {r["local_id"] for r in register}:
                problems.append(f"{category}: role {role} is not in the register")
        else:
            if is_set(identity):
                problems.append(
                    f"{category} is {ownership} but carries the identity "
                    f"{identity!r} - an absent item has no serial number"
                )
    return problems


def validate_census_observation_method(census: list[dict[str, str]]) -> list[str]:
    """Any established possession state records how it was established."""
    problems: list[str] = []
    for row in census:
        category = row.get("Category", "?")
        ownership = row.get("Ownership", "").strip()
        method = row.get("Observation method", "").strip()
        if ownership == "UNKNOWN":
            continue
        if method not in OBSERVATION_METHODS:
            problems.append(
                f"{category} is {ownership} but its observation method "
                f"{method!r} is not one of {', '.join(OBSERVATION_METHODS)}"
            )
    return problems


def validate_ownership_compatibility_pair(census: list[dict[str, str]]) -> list[str]:
    """Ownership and compatibility are independent, and neither implies the other.

    OWNED != COMPATIBLE. An owned item still needs a real disposition, and an
    item nobody owns cannot have been assessed.
    """
    problems: list[str] = []
    for row in census:
        category = row.get("Category", "?")
        ownership = row.get("Ownership", "").strip()
        disposition = row.get("Disposition", "").strip()

        if disposition not in COMPATIBILITY_DISPOSITIONS:
            problems.append(
                f"{category}: unknown compatibility disposition {disposition!r}"
            )
            continue

        if ownership == "CONFIRMED_PRESENT" and disposition == "NOT_APPLICABLE":
            problems.append(
                f"{category} is owned but its compatibility is NOT_APPLICABLE - "
                "an owned item needs a real disposition, even if that "
                "disposition is COMPATIBILITY_REQUIRES_VERIFICATION"
            )
        if ownership != "CONFIRMED_PRESENT" and disposition != "NOT_APPLICABLE":
            problems.append(
                f"{category} is {ownership} but records compatibility "
                f"{disposition} - nothing unowned has been assessed"
            )
    return problems


def check_census(
    census: list[dict[str, str]] | None,
    register: list[dict[str, str]],
    status: str,
) -> list[str]:
    """Census integrity, and the rule that it may not claim more than it saw."""
    if census is None:
        return ["the census document carries no census record table"]

    problems: list[str] = []
    if status not in CENSUS_STATUSES:
        problems.append(f"unknown census status {status!r}")

    established = [
        row for row in census if row.get("Ownership", "").strip() != "UNKNOWN"
    ]
    if status == "NOT_PERFORMED" and established:
        problems.append(
            f"census reads NOT_PERFORMED but {len(established)} row(s) claim an "
            "established ownership state"
        )
    if status == "PERFORMED" and not established:
        problems.append(
            "census reads PERFORMED but establishes nothing - a performed census "
            "resolves at least one category"
        )

    problems += validate_census_role_coverage(census)
    problems += validate_owned_asset_identity(census, register)
    problems += validate_census_observation_method(census)
    problems += validate_ownership_compatibility_pair(census)
    return problems


def validate_census_bom_agreement(
    census: list[dict[str, str]] | None, candidates: list[dict[str, str]] | None
) -> list[str]:
    """The census and the BOM must tell the same possession story.

    A reader deciding what to buy may open either document. If one says a role
    is absent and the other still says nobody has looked, they get two answers
    to the only question that gates a purchase.

    The census is authoritative here: it is the observation, and the BOM's
    ownership column is a copy of it.
    """
    if census is None or candidates is None:
        return []

    problems: list[str] = []
    observed = {
        row.get("BOM role", "").strip(): row.get("Ownership", "").strip()
        for row in census
    }

    for row in candidates:
        role = row.get("role_local_id", "").strip()
        truth = observed.get(role)
        if truth is None:
            continue
        recorded = row.get("ownership", "").strip()
        if recorded != truth:
            problems.append(
                f"{row.get(CANDIDATE_KEY, '?')}: ownership {recorded!r} disagrees "
                f"with the census, which observed {truth!r} for {role}"
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
        bom = parse_table(BOM_PATH, "local_id", REQUIRED_BOM_COLUMNS)
        register = parse_table(REGISTER_PATH, "local_id", REQUIRED_REGISTER_COLUMNS)
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        candidates = parse_optional_table(
            BOM_PATH, CANDIDATE_KEY, REQUIRED_CANDIDATE_COLUMNS
        )
        specs = parse_optional_table(BOM_PATH, SPEC_KEY, REQUIRED_SPEC_COLUMNS)
        census_text = CENSUS_PATH.read_text(encoding="utf-8")
        census = parse_optional_table(CENSUS_PATH, CENSUS_KEY, REQUIRED_CENSUS_COLUMNS)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"cannot read the hardware documents: {exc}", file=sys.stderr)
        return 1

    count = 0
    count += report("bom", check_bom(bom))
    count += report("register", check_register(register, bom))
    count += report("ownership", check_ownership(bom, register))
    count += report("datasheets", check_manifest(manifest, bom))
    count += report("protocol", check_protocol(bom))
    count += report(
        "census", check_census(census, register, census_status(census_text))
    )
    count += report(
        "census-bom-agreement", validate_census_bom_agreement(census, candidates)
    )
    count += report("candidates", check_candidates(candidates, specs, bom))
    count += report(
        "candidate-datasheets",
        check_candidate_datasheets(manifest, candidates, specs),
    )

    if args.summary:
        print()
        print(f"{'component_class':<22} {'local_id':<16} status")
        for row in bom:
            print(f"{row['component_class']:<22} {row['local_id']:<16} {row['status']}")
        received = [
            row["local_id"]
            for row in bom
            if rung(row["status"]) >= rung(PHYSICAL_POSSESSION_CLAIMED_FROM)
        ]
        design_selected = [
            row["local_id"] for row in bom if row["status"] == "SELECTED"
        ]
        print()
        print(f"design-selected, possession unconfirmed: {len(design_selected)}")
        print(f"recorded as physically received:         {len(received)}")
        if not received:
            print(
                "\nNo component is recorded as physically received. Design "
                "selections above are choices on paper and are not evidence of "
                "possession, so DO-104E cannot begin bench bring-up."
            )

        if candidates:
            print()
            print(f"{'tier':<20} {'roles':<7} priced / quoted / unknown")
            for tier in SELECTION_TIERS:
                rows = group_candidates_by_tier(candidates).get(tier, [])
                if not rows:
                    continue
                priced = [r for r in rows if as_money(r["unit_cost_usd"]) is not None]
                quoted = [
                    r for r in rows if r["unit_cost_usd"].strip() == "QUOTE_REQUIRED"
                ]
                unknown = [r for r in rows if r["unit_cost_usd"].strip() == "UNKNOWN"]
                total = sum(as_money(r["extended_cost_usd"]) or 0.0 for r in priced)
                print(
                    f"{tier:<20} {len(rows):<7} "
                    f"{len(priced)} / {len(quoted)} / {len(unknown)}"
                    f"   partial ${total:,.2f}"
                )
            print(
                "\nPartial totals cover priced rows only. An unpriced row is not "
                "free, and these totals cannot rank the tiers."
            )

    if count:
        print(f"\n{count} problem(s) found", file=sys.stderr)
        return 1
    print("\nhardware documents are internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
