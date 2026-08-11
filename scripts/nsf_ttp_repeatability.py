#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Analyze collected preliminary repeatability runs (DO-102).

    python scripts/nsf_ttp_repeatability.py \\
        --experiment experiment.json \\
        --runs path/to/run-dir \\
        --write

Reads ``phase1_tap_analysis_v1`` results already on disk and assembles them
into a repeatability study. It performs **no capture**: it analyzes runs that
were collected elsewhere. There is no capture mode and adding one needs its own
authorization.

``--evidence-origin`` must be stated and defaults to ``FIXTURE``. Claiming
``HARDWARE`` for a result marked as generated from synthetic audio fails with
NSF-305, as does a study whose runs do not all share the claimed origin.

The experiment definition file is JSON matching the ``experiment_definition``
block of ``ttp_preliminary_repeatability_study_v1``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.grant_readiness.contracts import (  # noqa: E402
    EvidenceOrigin,
    PreliminaryExperimentDefinitionV1,
)
from tap_tone_pi.grant_readiness.errors import GrantReadinessError  # noqa: E402
from tap_tone_pi.grant_readiness.experiment import (  # noqa: E402
    build_repeatability_study,
    load_phase1_analysis,
    record_experiment_run,
)
from tap_tone_pi.grant_readiness.report import (  # noqa: E402
    build_study_report,
    canonical_json,
    render_study_report,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "out" / "nsf"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def display(path: Path) -> str:
    """Show a path relative to the repository where it is one."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def discover_results(run_dir: Path) -> list[Path]:
    """Return analysis documents in deterministic order."""
    return sorted(run_dir.glob("*.json"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze collected preliminary repeatability runs"
    )
    parser.add_argument(
        "--experiment",
        type=Path,
        required=True,
        help="JSON experiment definition",
    )
    parser.add_argument(
        "--runs",
        type=Path,
        required=True,
        help="Directory of phase1_tap_analysis_v1 result documents",
    )
    parser.add_argument(
        "--evidence-origin",
        choices=[origin.value for origin in EvidenceOrigin],
        default=EvidenceOrigin.FIXTURE.value,
        help=(
            "Where the underlying data came from. Only HARDWARE is hardware "
            "evidence (default: FIXTURE)"
        ),
    )
    parser.add_argument("--study-id", default="ttp-preliminary-repeatability")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--write", action="store_true", help="Write artifacts under out/nsf/"
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        definition = PreliminaryExperimentDefinitionV1.from_dict(
            json.loads(args.experiment.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError) as exc:
        print(
            f"Could not read experiment definition ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 2
    except GrantReadinessError as exc:
        print(f"[{exc.code.value}] {exc.message}", file=sys.stderr)
        return 2

    if not args.runs.is_dir():
        print(f"Run directory not found: {args.runs.name}", file=sys.stderr)
        return 2

    origin = EvidenceOrigin(args.evidence_origin)
    results = discover_results(args.runs)
    if not results:
        print(f"No result documents found in {args.runs.name}", file=sys.stderr)
        return 2

    runs = []
    try:
        for index, path in enumerate(results, start=1):
            payload = load_phase1_analysis(path)
            runs.append(
                record_experiment_run(
                    payload,
                    run_id=f"run-{index:03d}",
                    experiment_id=definition.experiment_id,
                    evidence_origin=origin,
                    source_artifact_ids=(path.name,),
                    measurement_result_id=path.stem,
                )
            )

        study = build_repeatability_study(
            study_id=args.study_id,
            definition=definition,
            runs=runs,
            generated_at=utc_now(),
            evidence_origin=origin,
        )
    except GrantReadinessError as exc:
        print(f"[{exc.code.value}] {exc.message}", file=sys.stderr)
        return 1

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
    json_path = output_dir / "ttp_preliminary_repeatability_study.json"
    md_path = output_dir / "ttp_preliminary_repeatability_study.md"

    json_path.write_text(canonical_json(build_study_report(study)), encoding="utf-8")
    md_path.write_text(render_study_report(study), encoding="utf-8")

    print(f"Wrote {display(json_path)}")
    print(f"Wrote {display(md_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
