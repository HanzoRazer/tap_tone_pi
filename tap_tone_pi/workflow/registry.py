# INSTRUMENT CLASS: MEASUREMENT
"""Built-in measurement workflow registry.

Provides canonical workflow definitions for common acoustic measurement
procedures. These are governance artifacts that define what constitutes
a legitimate measurement for each procedure type.

Custom workflows can be defined by users, but built-in workflows
represent validated, repeatable procedures.
"""

from __future__ import annotations

from typing import Dict

from tap_tone_pi.workflow.contracts import (
    MeasurementWorkflowContractV1,
    FixtureRequirements,
    EnvironmentRequirements,
)


# -----------------------------------------------------------------------------
# Built-in workflow definitions
# -----------------------------------------------------------------------------

FREE_PLATE_TAP_V1 = MeasurementWorkflowContractV1(
    workflow_id="free_plate_tap_v1",
    display_name="Free Plate Tap",
    description=(
        "Single-mic tap-tone capture on a free (unsupported) plate. "
        "Used for mode frequency extraction before bracing."
    ),
    required_repetitions=5,
    max_frequency_variance_pct=3.0,
    sample_rate_hz=48000,
    fft_window="hann",
    fft_size=4096,
    min_snr_db=30.0,
    min_peak_prominence_db=6.0,
    max_clipping_samples=0,
    requires_calibration=True,
    max_calibration_age_days=30,
    fixture_requirements=FixtureRequirements(
        support_condition="free",
        mic_position="center",
        tap_position="antinode",
    ),
    environment_requirements=EnvironmentRequirements(
        min_temperature_c=18.0,
        max_temperature_c=28.0,
        min_humidity_pct=35.0,
        max_humidity_pct=65.0,
    ),
)

BRACED_TOP_TAP_V1 = MeasurementWorkflowContractV1(
    workflow_id="braced_top_tap_v1",
    display_name="Braced Top Tap",
    description=(
        "Single-mic tap-tone capture on a braced soundboard. "
        "Used for tracking mode shifts after brace installation."
    ),
    required_repetitions=5,
    max_frequency_variance_pct=2.5,
    sample_rate_hz=48000,
    fft_window="hann",
    fft_size=4096,
    min_snr_db=30.0,
    min_peak_prominence_db=6.0,
    max_clipping_samples=0,
    requires_calibration=True,
    max_calibration_age_days=30,
    fixture_requirements=FixtureRequirements(
        support_condition="free",
        mic_position="center",
        tap_position="center",
    ),
    environment_requirements=EnvironmentRequirements(
        min_temperature_c=18.0,
        max_temperature_c=28.0,
        min_humidity_pct=35.0,
        max_humidity_pct=65.0,
    ),
)

CLOSED_BOX_TAP_V1 = MeasurementWorkflowContractV1(
    workflow_id="closed_box_tap_v1",
    display_name="Closed Box Tap",
    description=(
        "Single-mic tap-tone capture on a closed (assembled) body. "
        "Used for air resonance and coupled mode analysis."
    ),
    required_repetitions=5,
    max_frequency_variance_pct=2.0,
    sample_rate_hz=48000,
    fft_window="hann",
    fft_size=8192,
    min_snr_db=25.0,
    min_peak_prominence_db=6.0,
    max_clipping_samples=0,
    requires_calibration=True,
    max_calibration_age_days=30,
    fixture_requirements=FixtureRequirements(
        support_condition="supported",
        mic_position="off-center",
        tap_position="center",
    ),
    environment_requirements=EnvironmentRequirements(
        min_temperature_c=18.0,
        max_temperature_c=28.0,
        min_humidity_pct=35.0,
        max_humidity_pct=65.0,
    ),
)

BACK_TAP_V1 = MeasurementWorkflowContractV1(
    workflow_id="back_tap_v1",
    display_name="Back Plate Tap",
    description=(
        "Single-mic tap-tone capture on a back plate. "
        "Used for back mode frequency extraction."
    ),
    required_repetitions=5,
    max_frequency_variance_pct=3.0,
    sample_rate_hz=48000,
    fft_window="hann",
    fft_size=4096,
    min_snr_db=30.0,
    min_peak_prominence_db=6.0,
    max_clipping_samples=0,
    requires_calibration=True,
    max_calibration_age_days=30,
    fixture_requirements=FixtureRequirements(
        support_condition="free",
        mic_position="center",
        tap_position="antinode",
    ),
    environment_requirements=EnvironmentRequirements(
        min_temperature_c=18.0,
        max_temperature_c=28.0,
        min_humidity_pct=35.0,
        max_humidity_pct=65.0,
    ),
)

AIR_RESONANCE_CHECK_V1 = MeasurementWorkflowContractV1(
    workflow_id="air_resonance_check_v1",
    display_name="Air Resonance Check",
    description=(
        "Quick air resonance (Helmholtz) measurement on closed body. "
        "Fewer repetitions, focused on A0 mode."
    ),
    required_repetitions=3,
    max_frequency_variance_pct=1.5,
    sample_rate_hz=48000,
    fft_window="hann",
    fft_size=8192,
    min_snr_db=20.0,
    min_peak_prominence_db=10.0,
    max_clipping_samples=0,
    requires_calibration=True,
    max_calibration_age_days=30,
    fixture_requirements=FixtureRequirements(
        support_condition="supported",
        mic_position="soundhole",
        tap_position="bridge",
    ),
    environment_requirements=EnvironmentRequirements(
        min_temperature_c=18.0,
        max_temperature_c=28.0,
    ),
)

CALIBRATION_PASS_V1 = MeasurementWorkflowContractV1(
    workflow_id="calibration_pass_v1",
    display_name="Calibration Pass",
    description=(
        "Reference tone and loopback calibration workflow. "
        "Used to establish signal chain validity."
    ),
    required_repetitions=3,
    max_frequency_variance_pct=0.5,
    sample_rate_hz=48000,
    fft_window="hann",
    fft_size=4096,
    min_snr_db=40.0,
    min_peak_prominence_db=20.0,
    max_clipping_samples=0,
    requires_calibration=False,  # This IS the calibration
    max_calibration_age_days=30,
    fixture_requirements=FixtureRequirements(
        fixture_id="calibration_jig",
    ),
    environment_requirements=EnvironmentRequirements(
        max_ambient_noise_dbfs=-50.0,
    ),
)


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------

BUILTIN_WORKFLOWS: Dict[str, MeasurementWorkflowContractV1] = {
    FREE_PLATE_TAP_V1.workflow_id: FREE_PLATE_TAP_V1,
    BRACED_TOP_TAP_V1.workflow_id: BRACED_TOP_TAP_V1,
    CLOSED_BOX_TAP_V1.workflow_id: CLOSED_BOX_TAP_V1,
    BACK_TAP_V1.workflow_id: BACK_TAP_V1,
    AIR_RESONANCE_CHECK_V1.workflow_id: AIR_RESONANCE_CHECK_V1,
    CALIBRATION_PASS_V1.workflow_id: CALIBRATION_PASS_V1,
}


def get_workflow(workflow_id: str) -> MeasurementWorkflowContractV1 | None:
    """Look up a workflow by ID. Returns None if not found."""
    return BUILTIN_WORKFLOWS.get(workflow_id)


def list_workflow_ids() -> list[str]:
    """Return sorted list of all registered workflow IDs."""
    return sorted(BUILTIN_WORKFLOWS.keys())


def validate_registry() -> list[str]:
    """Validate all registered workflows. Returns list of errors."""
    errors: list[str] = []
    seen_ids: set[str] = set()

    for wf_id, wf in BUILTIN_WORKFLOWS.items():
        # Check ID consistency
        if wf.workflow_id != wf_id:
            errors.append(f"Registry key {wf_id} != workflow_id {wf.workflow_id}")

        # Check for duplicates
        if wf_id in seen_ids:
            errors.append(f"Duplicate workflow_id: {wf_id}")
        seen_ids.add(wf_id)

        # Validate workflow invariants
        wf_errors = wf.validate()
        for err in wf_errors:
            errors.append(f"{wf_id}: {err}")

    return errors
