# INSTRUMENT CLASS: MEASUREMENT
"""Flat Plate Resonance Pilot V1 — acoustic lab integration pilot (Phase 1).

This is a *synthetic* experiment fixture whose only purpose is to exercise the
existing TTP experiment-design / execution-plan machinery end to end and render
a baseline cohort execution plan as Markdown. It does NOT modify renderer
behaviour and it introduces no advisory or build-prescriptive logic.

It composes the existing public contracts:

    create_response_variable / create_minimum_interesting_effect
    create_covariate
    create_randomization_plan
    create_reference_body
    create_experiment_design
        -> create_cohort_execution_plan
        -> render_cohort_execution_plan_markdown

Run:

    python examples/acoustic_lab/flat_plate_resonance_pilot_v1.py

Outputs (overwritten on each run):

    docs/handoffs/FLAT_PLATE_RESONANCE_PILOT_EXECUTION_PLAN.md   (baseline render)
    examples/acoustic_lab/flat_plate_resonance_pilot_v1.json     (design + plan dump)

Measurement boundary: this fixture declares *what* is measured. It never states
that any value is good, correct, optimal, or proof of quality.
"""

from __future__ import annotations

import json
from pathlib import Path

from tap_tone_pi.experiment.response_variables import (
    create_response_variable,
    create_minimum_interesting_effect,
)
from tap_tone_pi.experiment.covariates import create_covariate
from tap_tone_pi.experiment.randomization import create_randomization_plan
from tap_tone_pi.experiment.reference_body import create_reference_body
from tap_tone_pi.experiment.experiment_design import (
    ExperimentDesignV1,
    create_experiment_design,
)
from tap_tone_pi.experiment.execution_plan import (
    CohortExecutionPlanV1,
    create_cohort_execution_plan,
    render_cohort_execution_plan_markdown,
)
from tap_tone_pi.experiment.reference_body import ReferenceBodyRecordV1

# Fixed timestamp so the *design* fixture is reproducible run to run. (The plan's
# created_utc is stamped by the renderer with the current time and is expected to
# vary; nothing asserts on it.)
PILOT_TIMESTAMP_UTC = "2026-06-29T00:00:00+00:00"

# Shared measurement workflow id referenced by every response variable. The fact
# that this single opaque id stands in for the entire bench procedure (support,
# excitation, mic, calibration, repeats) is itself a documented gap — see the
# gap report.
TAP_MODAL_WORKFLOW_ID = "tap_modal_capture_v1"


def build_flat_plate_pilot_design() -> ExperimentDesignV1:
    """Build the synthetic Flat Plate Resonance Pilot V1 experiment design.

    Flat-plate variables only. A0 (Helmholtz air-cavity mode) is deliberately
    omitted: a free-free flat plate has no enclosed air volume, so A0 is not a
    flat-plate response variable. Including it would be physically dishonest.
    """
    response_variables = [
        create_response_variable(
            "rv_t1_freq",
            "T1 frequency",
            "Hz",
            measurement_workflow_id=TAP_MODAL_WORKFLOW_ID,
            minimum_interesting_effect=create_minimum_interesting_effect(
                3.0, "percent", "Smallest T1 shift treated as worth recording."
            ),
            description="First cross-dipole (T1) modal frequency of the free-free plate.",
        ),
        create_response_variable(
            "rv_q",
            "Q",
            "ratio",
            measurement_workflow_id=TAP_MODAL_WORKFLOW_ID,
            minimum_interesting_effect=create_minimum_interesting_effect(
                10.0, "percent", "Smallest Q change treated as worth recording."
            ),
            description="Quality factor (f0 / bandwidth) of the T1 resonance.",
        ),
        create_response_variable(
            "rv_decay_time",
            "decay time",
            "s",
            measurement_workflow_id=TAP_MODAL_WORKFLOW_ID,
            minimum_interesting_effect=create_minimum_interesting_effect(
                10.0, "percent", "Smallest T60-style decay change worth recording."
            ),
            description="Free decay time of the tapped plate (envelope -60 dB style).",
        ),
    ]

    covariates = [
        create_covariate("cov_density", "density", "kg/m3", source="wood_database"),
        create_covariate(
            "cov_moisture", "moisture content", "percent", source="measured"
        ),
        create_covariate("cov_species", "species", "category", source="wood_database"),
        create_covariate(
            "cov_support", "support method", "category", source="fixture_log"
        ),
        create_covariate(
            "cov_humidity", "humidity", "percent_rh", source="environment_log"
        ),
        create_covariate(
            "cov_temperature", "temperature", "deg_C", source="environment_log"
        ),
    ]

    randomization_plan = create_randomization_plan(
        "flat_plate_rand_v1",
        "blocked",
        seed=20260629,
        description="Blocked by species; measurement order randomized within block.",
    )

    return create_experiment_design(
        "flat_plate_resonance_pilot_v1",
        "Flat Plate Resonance Pilot V1",
        target_cohort_size=12,
        description=(
            "Synthetic pilot cohort of ~12 cypress/spruce free-free flat plates, "
            "tap-excited, to exercise the cohort execution-plan renderer end to end. "
            "Measurement-only: no acoustic quality is asserted."
        ),
        response_variables=response_variables,
        covariates=covariates,
        randomization_plan=randomization_plan,
        # baseline_rebuild_plan intentionally omitted: its fields
        # (rebuild_at_build_numbers, baseline_recipe_id) are instrument-BUILD
        # vocabulary with no analog for a flat-plate cohort. See gap report.
        baseline_rebuild_plan=None,
        tags=["acoustic_lab", "flat_plate", "pilot", "synthetic"],
        timestamp_utc=PILOT_TIMESTAMP_UTC,
    )


def build_reference_plate() -> ReferenceBodyRecordV1:
    """A kept reference plate, re-measured to isolate sigma_measurement.

    NOTE: ReferenceBodyRecordV1 was designed for assembled instrument *bodies*
    (body_style = "dreadnought", state = "unstrung_assembled"). Re-using it for a
    bare plate forces those fields out of their intended meaning. That mismatch
    is documented in the gap report rather than hidden.
    """
    return create_reference_body(
        "flat_plate_ref_001",
        body_style="flat_plate_reference",
        description="Kept reference flat plate, re-measured each session for repeatability.",
        state="free_free_unclamped",
        wood_species_top="sitka_spruce",
        timestamp_utc=PILOT_TIMESTAMP_UTC,
    )


def build_pilot_plan() -> CohortExecutionPlanV1:
    """Render the pilot into a CohortExecutionPlanV1 using the existing factory."""
    design = build_flat_plate_pilot_design()
    reference_body = build_reference_plate()
    return create_cohort_execution_plan(
        "flat_plate_resonance_pilot_v1_plan",
        design,
        reference_body=reference_body,
        plan_version="1",
    )


def render_pilot_markdown() -> str:
    """Render the baseline execution plan to Markdown (renderer unchanged)."""
    return render_cohort_execution_plan_markdown(build_pilot_plan())


_GENERATED_BANNER = (
    "<!-- GENERATED BASELINE OUTPUT — do not hand-edit.\n"
    "     Source: examples/acoustic_lab/flat_plate_resonance_pilot_v1.py\n"
    "     Regenerate: python examples/acoustic_lab/flat_plate_resonance_pilot_v1.py\n"
    "     This is the unmodified render of the existing cohort execution-plan\n"
    "     renderer for the synthetic Flat Plate Resonance Pilot V1 fixture. -->\n\n"
)


def _repo_root() -> Path:
    # examples/acoustic_lab/<this file> -> parents[2] == repo root
    return Path(__file__).resolve().parents[2]


def main() -> int:
    root = _repo_root()
    design = build_flat_plate_pilot_design()
    plan = build_pilot_plan()
    markdown = render_cohort_execution_plan_markdown(plan)

    plan_md_path = (
        root / "docs" / "handoffs" / "FLAT_PLATE_RESONANCE_PILOT_EXECUTION_PLAN.md"
    )
    plan_md_path.parent.mkdir(parents=True, exist_ok=True)
    plan_md_path.write_text(_GENERATED_BANNER + markdown + "\n", encoding="utf-8")

    json_path = (
        root / "examples" / "acoustic_lab" / "flat_plate_resonance_pilot_v1.json"
    )
    json_path.write_text(
        json.dumps(
            {"experiment_design": design.to_dict(), "execution_plan": plan.to_dict()},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote baseline execution plan: {plan_md_path}")
    print(f"Wrote design/plan JSON dump:   {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
