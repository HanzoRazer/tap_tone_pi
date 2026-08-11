#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Build the NSF Project Pitch source packet (DO-102).

    python scripts/nsf_ttp_build_pitch_source.py --write
    python scripts/nsf_ttp_build_pitch_source.py \\
        --study out/nsf/ttp_preliminary_repeatability_study.json --write

Assembles the capability audit, the technical-risk register, and an optional
repeatability study into source material organized under the four NSF Project
Pitch headings.

The Technology Innovation and Technical Objectives sections are populated from
repository evidence and cited. Market Opportunity and Company and Team are
emitted as explicit human-input placeholders; this script writes no market or
team claim.

The output is drafting material, not a submission.
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

from tap_tone_pi.grant_readiness.audit import build_grant_readiness_audit  # noqa: E402
from tap_tone_pi.grant_readiness.contracts import RepeatabilityStudyV1  # noqa: E402
from tap_tone_pi.grant_readiness.errors import GrantReadinessError  # noqa: E402
from tap_tone_pi.grant_readiness.pitch_source import (  # noqa: E402
    build_pitch_source_packet,
    render_pitch_source,
)
from tap_tone_pi.grant_readiness.report import (  # noqa: E402
    canonical_json,
    render_risk_register,
)
from tap_tone_pi.grant_readiness.risks import TECHNICAL_RISKS  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "out" / "nsf"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def display(path: Path) -> str:
    """Show a path relative to the repository where it is one."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_study(path: Path) -> RepeatabilityStudyV1:
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Accept either a bare study document or a study report wrapping one.
    if "study" in payload and isinstance(payload["study"], dict):
        payload = payload["study"]
    return RepeatabilityStudyV1.from_dict(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build NSF Project Pitch source material from repository evidence"
    )
    parser.add_argument(
        "--study",
        type=Path,
        default=None,
        help="Optional repeatability study to cite",
    )
    parser.add_argument("--packet-id", default="ttp-pitch-source")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--write", action="store_true", help="Write artifacts under out/nsf/"
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    generated_at = utc_now()

    study = None
    if args.study is not None:
        try:
            study = load_study(args.study)
        except (OSError, ValueError) as exc:
            print(f"Could not read study ({type(exc).__name__})", file=sys.stderr)
            return 2
        except GrantReadinessError as exc:
            print(f"[{exc.code.value}] {exc.message}", file=sys.stderr)
            return 2

    try:
        audit = build_grant_readiness_audit(
            audit_id="ttp-technical-baseline", generated_at=generated_at
        )
        packet = build_pitch_source_packet(
            packet_id=args.packet_id,
            generated_at=generated_at,
            audit=audit,
            study=study,
            risks=TECHNICAL_RISKS,
        )
    except GrantReadinessError as exc:
        print(f"[{exc.code.value}] {exc.message}", file=sys.stderr)
        return 1

    placeholders = len(packet.market_claim_placeholders) + len(
        packet.team_evidence_placeholders
    )
    print(
        f"Technology statements: {len(packet.technology_innovation_evidence)}; "
        f"objective statements: {len(packet.technical_objectives_evidence)}; "
        f"open risks: {len(TECHNICAL_RISKS)}"
    )
    print(f"Human-input placeholders awaiting an answer: {placeholders}")
    if study is None:
        print("No study cited. Pass --study to include repeatability evidence.")
    elif not study.is_hardware_evidence:
        print(
            f"NOTE: cited study is {study.evidence_origin.value} data, not "
            "hardware evidence."
        )

    if not args.write:
        return 0

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ttp_pitch_source.json"
    md_path = output_dir / "ttp_pitch_source.md"
    risks_path = output_dir / "ttp_phase_i_technical_risks.md"

    json_path.write_text(canonical_json(packet.to_dict()), encoding="utf-8")
    md_path.write_text(render_pitch_source(packet), encoding="utf-8")
    risks_path.write_text(render_risk_register(TECHNICAL_RISKS), encoding="utf-8")

    for path in (json_path, md_path, risks_path):
        print(f"Wrote {display(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
