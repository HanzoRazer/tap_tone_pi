#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Check a DO-103 hardware campaign directory. Read-only.

    python scripts/ttp_hardware_campaign_check.py out/nsf/campaign

Verifies that a written campaign says what its own evidence supports:

  * the campaign document deserializes and validates against its schema;
  * every study it names is present, deserializes, and validates;
  * stored digests still match the documents they were computed from;
  * run accounting agrees with the runs actually recorded;
  * every raw artifact a run retains appears in the artifact manifest;
  * an origin claim is backed by acquisition provenance;
  * promotion eligibility is reported, and never granted.

This tool writes nothing and repairs nothing. A campaign that fails here is
reported, not corrected: an automatic fix would change evidence to match a
claim, which is the failure mode the whole DO-103 evidence chain exists to make
impossible.

Exit status is 0 when every check passes and 1 when any finding is reported.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.grant_readiness.contracts import (  # noqa: E402
    CAMPAIGN_SCHEMA_VERSION,
    STUDY_SCHEMA_VERSION,
    EvidenceOrigin,
    HardwareCampaignRecordV1,
    RepeatabilityStudyV1,
)
from tap_tone_pi.grant_readiness.errors import GrantReadinessError  # noqa: E402
from tap_tone_pi.grant_readiness.validation import (  # noqa: E402
    ValidationFinding,
    evidence_digest,
    validate_artifact_manifest,
    validate_campaign_record,
    validate_repeatability_study,
    validate_witnessed_hardware_session,
)

CAMPAIGN_DOCUMENT = "ttp_hardware_campaign.json"
CONTRACTS = REPO_ROOT / "contracts"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def unwrap(payload: Any, key: str) -> Any:
    """Return the record itself, whether it was written bare or in a report."""
    if isinstance(payload, dict) and key in payload:
        return payload[key]
    return payload


def check_schema(payload: Any, schema_path: Path, label: str) -> list[str]:
    """Validate one document against its contract, where jsonschema is present."""
    try:
        import jsonschema
    except ImportError:
        return [f"NOTE: jsonschema is not installed; {label} schema not checked"]
    schema = read_json(schema_path)
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        return [f"{label} does not validate against its schema: {exc.message}"]
    return []


def check_digests(document: Any, record_key: str, digest_key: str) -> list[str]:
    """Recompute a stored digest from the document it was taken over."""
    if not isinstance(document, dict) or digest_key not in document:
        return []
    recorded = document[digest_key]
    computed = evidence_digest(document[record_key])
    if recorded != computed:
        return [
            f"{digest_key} does not match the document it was computed from "
            f"(recorded {recorded[:16]}..., computed {computed[:16]}...)"
        ]
    return []


def describe(findings: Sequence[ValidationFinding]) -> list[str]:
    return [f"[{finding.code.value}] {finding.message}" for finding in findings]


def check_campaign(directory: Path) -> tuple[list[str], list[str]]:
    """Return (problems, notes) for one campaign directory."""
    problems: list[str] = []
    notes: list[str] = []

    campaign_path = directory / CAMPAIGN_DOCUMENT
    if not campaign_path.exists():
        return ([f"no {CAMPAIGN_DOCUMENT} in {display(directory)}"], notes)

    document = read_json(campaign_path)
    payload = unwrap(document, "campaign")
    problems.extend(
        check_schema(
            payload, CONTRACTS / f"{CAMPAIGN_SCHEMA_VERSION}.schema.json", "campaign"
        )
    )
    problems.extend(check_digests(document, "campaign", "campaign_digest"))

    try:
        record = HardwareCampaignRecordV1.from_dict(payload)
    except GrantReadinessError as exc:
        problems.append(
            f"campaign document is unusable: [{exc.code.value}] {exc.message}"
        )
        return (problems, notes)

    problems.extend(describe(validate_campaign_record(record)))

    studies: list[RepeatabilityStudyV1] = []
    for outcome in record.outcomes:
        if outcome.study_id is None:
            continue
        study_path = directory / f"{outcome.study_id}.json"
        if not study_path.exists():
            problems.append(
                f"experiment {outcome.experiment_id} names study "
                f"{outcome.study_id}, which is not in {display(directory)}"
            )
            continue
        study_document = read_json(study_path)
        study_payload = unwrap(study_document, "study")
        problems.extend(
            check_schema(
                study_payload,
                CONTRACTS / f"{STUDY_SCHEMA_VERSION}.schema.json",
                f"study {outcome.study_id}",
            )
        )
        problems.extend(check_digests(study_document, "study", "study_digest"))
        try:
            study = RepeatabilityStudyV1.from_dict(study_payload)
        except GrantReadinessError as exc:
            problems.append(
                f"study {outcome.study_id} is unusable: "
                f"[{exc.code.value}] {exc.message}"
            )
            continue
        studies.append(study)
        problems.extend(describe(validate_repeatability_study(study)))

        if outcome.study_digest and outcome.study_digest != evidence_digest(
            study.to_dict()
        ):
            problems.append(
                f"campaign records a digest for study {study.study_id} that the "
                "study itself does not produce"
            )

    all_runs = [run for study in studies for run in study.runs]
    problems.extend(
        describe(validate_artifact_manifest(record.artifacts, runs=all_runs))
    )

    hardware = [
        study for study in studies if study.evidence_origin is EvidenceOrigin.HARDWARE
    ]
    witnessed = [
        study for study in hardware if not validate_witnessed_hardware_session(study)
    ]
    notes.append(f"studies: {len(studies)} ({len(hardware)} hardware-origin)")
    notes.append(f"runs: {len(all_runs)}")
    notes.append(f"artifacts: {len(record.artifacts)}")
    if witnessed:
        notes.append(
            "witnessed sessions: "
            + ", ".join(study.study_id for study in witnessed)
            + " - eligible to support a per-capability promotion, which remains "
            "a separate decision this tool does not make"
        )
    else:
        notes.append(
            "witnessed sessions: none - no capability may be promoted off "
            "NOT_VERIFIED_ON_HARDWARE on this campaign's evidence"
        )

    return (problems, notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a DO-103 hardware campaign directory (read-only)"
    )
    parser.add_argument(
        "campaign_dir", type=Path, help="directory holding the campaign"
    )
    args = parser.parse_args(argv)

    if not args.campaign_dir.is_dir():
        print(f"not a directory: {args.campaign_dir}", file=sys.stderr)
        return 1

    problems, notes = check_campaign(args.campaign_dir)

    for note in notes:
        print(note)
    for problem in problems:
        print(problem, file=sys.stderr)

    if problems:
        print(f"{len(problems)} problem(s) found", file=sys.stderr)
        return 1
    print("campaign evidence is internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
