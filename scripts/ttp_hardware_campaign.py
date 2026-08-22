#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Assemble DO-103 hardware characterization campaign evidence.

    python scripts/ttp_hardware_campaign.py fixed-point \\
        --config campaign.json \\
        --experiment e2-fixed-point \\
        --runs runs.json \\
        --evidence-origin HARDWARE \\
        --write

Each subcommand takes runs that were **already captured and analyzed
elsewhere** and records what they say. This script performs no capture, no FFT,
and no transfer-function computation: it reads persisted
``phase2_ods_snapshot_v2`` documents produced by the existing Phase 2 path and
brings them into the grant-readiness evidence layer.

Nothing here has a default acquisition. ``--config`` and ``--evidence-origin``
are required on every experiment subcommand, because a campaign whose
configuration was implied by this script's defaults could not be reproduced or
audited afterwards.

Subcommands, one per DO-103 §7 experiment plus the campaign report:

    rig-check      E1  characterize the rig and its stinger
    fixed-point    E2  repeated captures at one point, contact unbroken
    reattach       E3  repeated captures across deliberate re-attachments
    reciprocity    E4  drive-at-A/measure-at-B against its transpose
    mass-loading   E5  known added masses against an unloaded baseline
    report             assemble the campaign record from written studies

The run manifest is a JSON document describing what was captured. It is an
input specification, not evidence:

    {
      "experiment_id": "e2-fixed-point",
      "runs": [
        {
          "run_id": "e2-001",
          "transfer": "runs/e2/001/transfer.json",
          "captured_at": "2026-09-01T14:05:00+00:00",
          "measurement_point_id": "P1",
          "evaluation_frequency_hz": 220.0,
          "session_id": "s-2026-09-01",
          "acquisition_id": "a-001",
          "raw_artifact_ids": ["art-e2-001"],
          "witnessed_by": "operator-1",
          "condition": {"contact_configuration_id": "att-1"},
          "rejected": {"reason": "CLIPPING"}
        }
      ]
    }

``rejected`` is optional and records an operator's own verdict on a capture the
Phase 2 document cannot speak to. A rejected run keeps its identity, its
artifacts, and its provenance; it is excluded from the statistics and included
in the accounting.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.grant_readiness.contracts import (  # noqa: E402
    CampaignConditionV1,
    CampaignExecutionStatus,
    CampaignExperimentOutcomeV1,
    EnvironmentalContextV1,
    EvidenceOrigin,
    ExperimentKind,
    ExternalArtifactV1,
    HardwareCampaignConfigV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
    RepeatabilityStudyV1,
)
from tap_tone_pi.grant_readiness.errors import GrantReadinessError  # noqa: E402
from tap_tone_pi.grant_readiness.experiment import (  # noqa: E402
    build_repeatability_study,
)
from tap_tone_pi.grant_readiness.hardware_campaign import (  # noqa: E402
    build_campaign_acquisition,
    build_campaign_definition,
    build_campaign_record,
    load_campaign_config,
    pair_reciprocity_runs,
    summarize_attachment_variation,
    summarize_mass_loading,
    summarize_reciprocity,
)
from tap_tone_pi.grant_readiness.phase2_experiment import (  # noqa: E402
    TRANSFER_MAGNITUDE,
    load_phase2_transfer,
    record_phase2_run,
    summarized_phase2_quantities,
    transfer_unit_for,
)
from tap_tone_pi.grant_readiness.report import (  # noqa: E402
    build_campaign_report,
    build_study_report,
    canonical_json,
    render_campaign_report,
    render_study_report,
)
from tap_tone_pi.grant_readiness.validation import (  # noqa: E402
    raise_for_findings,
    validate_campaign_config,
    validate_campaign_record,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "out" / "nsf" / "campaign"

# Which experiment each subcommand records. The subcommands differ only in the
# kind they assert, which is what keeps five experiments on one ingestion path.
SUBCOMMAND_KINDS = {
    "rig-check": ExperimentKind.RIG_CHARACTERIZATION,
    "fixed-point": ExperimentKind.FIXED_POINT,
    "reattach": ExperimentKind.DETACH_REATTACH,
    "reciprocity": ExperimentKind.RECIPROCITY,
    "mass-loading": ExperimentKind.MASS_LOADING,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def display(path: Path) -> str:
    """Show a path relative to the repository where it is one."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path: Path) -> HardwareCampaignConfigV1:
    config = load_campaign_config(read_json(path))
    raise_for_findings(validate_campaign_config(config))
    return config


def _condition(entry: Mapping[str, Any], kind: ExperimentKind) -> CampaignConditionV1:
    """Build the run's campaign condition, with its kind supplied by the command.

    The manifest never names the experiment kind: the subcommand does. A
    manifest that could disagree with the command that read it would let one
    experiment's runs be filed under another.
    """
    payload = dict(entry.get("condition") or {})
    payload["experiment_kind"] = kind.value
    return CampaignConditionV1.from_dict(payload)


def _rejected_run(
    entry: Mapping[str, Any],
    *,
    experiment_id: str,
    origin: EvidenceOrigin,
    acquisition,
    condition: CampaignConditionV1,
) -> PreliminaryExperimentRunV1:
    """Record a capture the operator rejected, keeping everything it carried."""
    rejection = entry["rejected"]
    return PreliminaryExperimentRunV1(
        run_id=entry["run_id"],
        experiment_id=experiment_id,
        captured_at=entry["captured_at"],
        evidence_origin=origin,
        valid=False,
        rejection_reason=RejectionReason(rejection["reason"]),
        source_artifact_ids=tuple(entry.get("source_artifact_ids", ())),
        measurement_result_id=entry.get("measurement_result_id"),
        conditions=EnvironmentalContextV1.from_dict(entry.get("conditions")),
        acquisition=acquisition,
        campaign_condition=condition,
    )


def build_runs(
    manifest: Mapping[str, Any],
    *,
    config: HardwareCampaignConfigV1,
    experiment_id: str,
    kind: ExperimentKind,
    origin: EvidenceOrigin,
    manifest_dir: Path,
) -> list[PreliminaryExperimentRunV1]:
    """Record every run the manifest describes, valid and rejected alike."""
    runs: list[PreliminaryExperimentRunV1] = []
    for entry in manifest.get("runs", []):
        condition = _condition(entry, kind)
        acquisition = build_campaign_acquisition(
            config,
            session_id=entry["session_id"],
            acquisition_id=entry["acquisition_id"],
            raw_artifact_ids=tuple(entry.get("raw_artifact_ids", ())),
            drive_parameters=entry.get("drive_parameters"),
            witnessed_by=entry.get("witnessed_by"),
        )
        if entry.get("rejected"):
            runs.append(
                _rejected_run(
                    entry,
                    experiment_id=experiment_id,
                    origin=origin,
                    acquisition=acquisition,
                    condition=condition,
                )
            )
            continue

        transfer_path = (manifest_dir / entry["transfer"]).resolve()
        payload = load_phase2_transfer(transfer_path)
        run = record_phase2_run(
            payload,
            run_id=entry["run_id"],
            experiment_id=experiment_id,
            measurement_point_id=entry["measurement_point_id"],
            evaluation_frequency_hz=float(entry["evaluation_frequency_hz"]),
            captured_at=entry["captured_at"],
            evidence_origin=origin,
            source_artifact_ids=tuple(
                entry.get("source_artifact_ids", (entry["transfer"],))
            ),
            measurement_result_id=entry.get("measurement_result_id"),
            conditions=EnvironmentalContextV1.from_dict(entry.get("conditions")),
            acquisition=acquisition,
        )
        # record_phase2_run returns a rejected run where the document cannot
        # answer for the point or the frequency. The campaign condition is
        # attached either way, so a rejected run still groups correctly.
        runs.append(dataclasses.replace(run, campaign_condition=condition))
    return runs


def run_experiment(args: argparse.Namespace, kind: ExperimentKind) -> int:
    config = load_config(args.config)
    plan = config.plan_for(args.experiment)
    if plan is None:
        print(
            f"experiment {args.experiment!r} is not planned by {display(args.config)}",
            file=sys.stderr,
        )
        return 1
    if plan.kind is not kind:
        print(
            f"experiment {args.experiment!r} is a {plan.kind.value} experiment; "
            f"this command records {kind.value}",
            file=sys.stderr,
        )
        return 1

    manifest = read_json(args.runs)
    if manifest.get("experiment_id") != args.experiment:
        print(
            f"run manifest names experiment {manifest.get('experiment_id')!r}, "
            f"not {args.experiment!r}",
            file=sys.stderr,
        )
        return 1

    origin = EvidenceOrigin(args.evidence_origin)
    definition = build_campaign_definition(plan, config, created_at=config.created_at)
    runs = build_runs(
        manifest,
        config=config,
        experiment_id=args.experiment,
        kind=kind,
        origin=origin,
        manifest_dir=args.runs.resolve().parent,
    )

    unit = transfer_unit_for(runs[0].acquisition if runs else None)
    study = build_repeatability_study(
        study_id=args.study_id or f"study-{args.experiment}",
        definition=definition,
        runs=runs,
        generated_at=utc_now(),
        evidence_origin=origin,
        quantities=summarized_phase2_quantities(unit),
    )

    print(f"Experiment: {args.experiment} ({kind.value})")
    print(f"Runs recorded: {len(study.runs)}")
    print(f"  valid:    {study.valid_run_count}")
    print(f"  rejected: {study.rejected_run_count}")
    for reason, count in sorted(study.rejection_counts.items()):
        if count:
            print(f"    {reason}: {count}")
    for metric in study.metrics:
        print(
            f"  {metric.quantity}: n={metric.sample_count} "
            f"mean={metric.mean:.6g} {metric.unit} "
            f"CV={metric.coefficient_of_variation_pct:.4g}%"
        )
    if not study.is_hardware_evidence:
        print(
            f"NOTE: evidence origin is {origin.value}. This is not hardware "
            "evidence and must not be reported as a hardware campaign."
        )

    if not args.write:
        return 0

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{study.study_id}.json"
    md_path = output_dir / f"{study.study_id}.md"
    json_path.write_text(canonical_json(build_study_report(study)), encoding="utf-8")
    md_path.write_text(render_study_report(study), encoding="utf-8")
    print(f"Wrote {display(json_path)}")
    print(f"Wrote {display(md_path)}")
    return 0


def _load_studies(paths: Sequence[Path]) -> list[RepeatabilityStudyV1]:
    studies: list[RepeatabilityStudyV1] = []
    for path in paths:
        payload = read_json(path)
        # Study documents are written as reports; the study itself is nested.
        studies.append(RepeatabilityStudyV1.from_dict(payload.get("study", payload)))
    return studies


def _runs_of_kind(
    studies: Sequence[RepeatabilityStudyV1], kind: ExperimentKind
) -> list[PreliminaryExperimentRunV1]:
    return [
        run for study in studies for run in study.runs if run.experiment_kind is kind
    ]


def run_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    study_paths = sorted(args.studies.glob("study-*.json")) if args.studies else []
    studies = _load_studies(study_paths)

    outcomes: list[CampaignExperimentOutcomeV1] = []
    by_experiment = {
        study.experiment_definition.experiment_id: study for study in studies
    }
    for plan in config.experiments:
        study = by_experiment.get(plan.experiment_id)
        if study is None:
            continue
        outcomes.append(
            CampaignExperimentOutcomeV1(
                experiment_id=plan.experiment_id,
                kind=plan.kind,
                status=CampaignExecutionStatus.EXECUTED,
                study_id=study.study_id,
                study_digest=build_study_report(study)["study_digest"],
            )
        )

    unit = None
    for study in studies:
        for metric in study.metrics:
            if metric.quantity == TRANSFER_MAGNITUDE:
                unit = metric.unit
                break

    attachment = ()
    reciprocity = ()
    mass_loading = ()
    if unit is not None:
        reattach_runs = _runs_of_kind(studies, ExperimentKind.DETACH_REATTACH)
        variation = summarize_attachment_variation(
            reattach_runs, quantity=TRANSFER_MAGNITUDE, unit=unit
        )
        attachment = (variation,) if variation is not None else ()
        reciprocity = summarize_reciprocity(
            pair_reciprocity_runs(_runs_of_kind(studies, ExperimentKind.RECIPROCITY)),
            quantity=TRANSFER_MAGNITUDE,
            unit=unit,
        )
        mass_loading = summarize_mass_loading(
            _runs_of_kind(studies, ExperimentKind.MASS_LOADING),
            quantity=TRANSFER_MAGNITUDE,
            unit=unit,
        )

    artifacts = ()
    if args.artifacts is not None:
        artifacts = tuple(
            ExternalArtifactV1.from_dict(item)
            for item in read_json(args.artifacts).get("artifacts", [])
        )

    record = build_campaign_record(
        config=config,
        generated_at=utc_now(),
        execution_status=CampaignExecutionStatus(args.execution_status),
        outcomes=tuple(outcomes),
        artifacts=artifacts,
        attachment_variation=attachment,
        reciprocity=reciprocity,
        mass_loading=mass_loading,
    )
    raise_for_findings(validate_campaign_record(record))

    print(f"Campaign: {record.campaign_id}")
    print(f"Execution status: {record.execution_status.value}")
    for outcome in record.outcomes:
        print(f"  {outcome.experiment_id}: {outcome.status.value}")
    print(f"Reciprocity observations: {len(record.reciprocity)}")
    print(f"Mass-loading observations: {len(record.mass_loading)}")
    if not record.is_executed:
        print(
            "NOTE: no experiment in this campaign has been executed. The record "
            "describes a planned configuration and supports no hardware claim."
        )

    if not args.write:
        return 0

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ttp_hardware_campaign.json"
    md_path = output_dir / "ttp_hardware_campaign.md"
    json_path.write_text(
        canonical_json(build_campaign_report(record, studies)), encoding="utf-8"
    )
    md_path.write_text(render_campaign_report(record, studies), encoding="utf-8")
    print(f"Wrote {display(json_path)}")
    print(f"Wrote {display(md_path)}")
    return 0


def add_experiment_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=Path, required=True, help="campaign configuration JSON"
    )
    parser.add_argument(
        "--experiment", required=True, help="experiment id planned by the config"
    )
    parser.add_argument("--runs", type=Path, required=True, help="run manifest JSON")
    parser.add_argument(
        "--evidence-origin",
        required=True,
        choices=[member.value for member in EvidenceOrigin],
        help="where the underlying data came from; stated, never inferred",
    )
    parser.add_argument(
        "--study-id", help="study identifier (default: study-<experiment>)"
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--write", action="store_true", help="write the study documents"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble DO-103 hardware characterization campaign evidence"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, kind in SUBCOMMAND_KINDS.items():
        sub = subparsers.add_parser(name, help=f"record a {kind.value} experiment")
        add_experiment_arguments(sub)

    report = subparsers.add_parser("report", help="assemble the campaign record")
    report.add_argument("--config", type=Path, required=True)
    report.add_argument(
        "--studies", type=Path, help="directory of written study documents"
    )
    report.add_argument(
        "--artifacts", type=Path, help="external artifact manifest JSON"
    )
    report.add_argument(
        "--execution-status",
        required=True,
        choices=[member.value for member in CampaignExecutionStatus],
        help="what actually happened to this campaign; stated, never inferred",
    )
    report.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    report.add_argument("--write", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "report":
            return run_report(args)
        return run_experiment(args, SUBCOMMAND_KINDS[args.command])
    except GrantReadinessError as exc:
        print(f"[{exc.code.value}] {exc.message}", file=sys.stderr)
        return 1
    except (KeyError, ValueError) as exc:
        print(f"campaign input is unusable: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
