# INSTRUMENT CLASS: MEASUREMENT
"""The declared TTP capability inventory (DO-102).

A bounded, instrument-level list of what the analyzer does — not a module
census. Each entry is a claim: a status from the four-state vocabulary, the
repository evidence behind it, whether execution on the intended hardware has
been witnessed, and why the status is what it is.

The inventory is declared here and checked against the repository by
:mod:`tap_tone_pi.grant_readiness.audit`. It is deliberately not inferred from
filenames: a capability is what someone is prepared to claim, and the audit's
job is to test that claim against the tree, not to generate it.

``tests/test_nsf_capability_baseline.py`` holds the same declaration, frozen
before this module existed, and a test asserts the two agree. That is what keeps
the audit from being quietly rewritten to agree with itself.

Every entry here is ``NOT_VERIFIED_ON_HARDWARE`` or ``NOT_APPLICABLE``. DO-102
executes no hardware campaign, so nothing may claim witnessed execution on the
intended Pi/microphone configuration.
"""

from __future__ import annotations

from tap_tone_pi.grant_readiness.contracts import (
    CapabilityEvidenceV1,
    CapabilityStatus,
    HardwareVerification,
)

_IMPLEMENTED = CapabilityStatus.IMPLEMENTED
_EXPERIMENTAL = CapabilityStatus.EXPERIMENTAL
_PARTIAL = CapabilityStatus.PARTIAL

_UNWITNESSED = HardwareVerification.NOT_VERIFIED_ON_HARDWARE
_NO_HARDWARE = HardwareVerification.NOT_APPLICABLE


TTP_CAPABILITY_INVENTORY: tuple[CapabilityEvidenceV1, ...] = (
    CapabilityEvidenceV1(
        capability_id="audio_capture",
        name="Audio capture (single and multi-channel)",
        status=_PARTIAL,
        implementation_paths=(
            "tap_tone_pi/capture/__init__.py",
            "tap_tone_pi/core/auto_trigger.py",
        ),
        test_paths=("tests/test_cli_record_qc.py", "tests/test_auto_trigger.py"),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Software path implemented and exercised with simulated input; the "
            "intended Pi and microphone acquisition chain has not been "
            "witnessed. Device enumeration and streaming go through "
            "sounddevice. Recorded PARTIAL rather than IMPLEMENTED because "
            "IMPLEMENTED would read as 'the system can currently capture real "
            "measurements', which this repository cannot show."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="wav_persistence",
        name="WAV persistence and round-trip integrity",
        status=_IMPLEMENTED,
        implementation_paths=("tap_tone_pi/io/wav.py", "modes/_shared/wav_io.py"),
        test_paths=(
            "tests/test_wav_io.py",
            "tests/test_wav_roundtrip.py",
            "tests/test_storage_wav_roundtrip.py",
        ),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Two readers exist. The one under test is modes/_shared/wav_io.py, "
            "which tap_tone_pi.chladni.peaks_from_wav also imports; "
            "tap_tone_pi/io/wav.py holds the writer used by the Phase 1 path."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="tap_spectral_analysis",
        name="Tap spectral analysis and peak extraction",
        status=_IMPLEMENTED,
        implementation_paths=("tap_tone_pi/core/analysis.py",),
        test_paths=(
            "tests/test_analysis_parametric.py",
            "tests/test_dsp_cross_validation.py",
            "tests/test_config_and_analysis.py",
        ),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Extracted peaks are spectral feature candidates. This repository "
            "holds no evidence establishing them as identified structural modes."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="capture_quality_gate",
        name="Capture quality gate (clipping and low-signal safeguards)",
        status=_IMPLEMENTED,
        implementation_paths=("tap_tone_pi/core/quality_gate.py",),
        test_paths=("tests/test_quality_gate.py",),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Emits pass/warn/fail verdicts against a versioned rule policy. "
            "Thresholds are workflow policy, not established performance limits."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="phase1_tap_workflow",
        name="Phase 1 single-microphone tap workflow",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/phase1/demo.py",
            "contracts/phase1_tap_analysis_v1.schema.json",
        ),
        test_paths=(
            "tests/test_phase1_pipeline_integration.py",
            "tests/test_phase1_demo.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes=(
            "The end-to-end path is exercised by synthetic impulse generation. "
            "This is the ingestion surface for the DO-102 preliminary "
            "repeatability experiment."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="phase2_ods_scanning",
        name="Phase 2 roving-grid ODS scanning",
        status=_IMPLEMENTED,
        implementation_paths=("tap_tone_pi/phase2", "scripts/phase2"),
        test_paths=(
            "tests/test_phase2_schemas.py",
            "tests/test_phase2_session_loader.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Two archived sessions exist under runs_phase2/, each holding one "
            "capture per grid point. Neither contains repeated captures of a "
            "single point, so neither can serve as a repeatability dataset."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="transfer_function_coherence",
        name="Transfer function and coherence estimation",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/transfer_function/welch.py",
            "tap_tone_pi/transfer_function/estimators.py",
            "tap_tone_pi/transfer_function/quality.py",
        ),
        test_paths=(
            "tests/test_production_physics.py",
            "tests/test_excitation_provenance.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes="Deliberately outside the DO-102 first study (Phase 1 only).",
    ),
    CapabilityEvidenceV1(
        capability_id="controlled_excitation",
        name="Controlled excitation contracts and signal generation",
        status=_PARTIAL,
        implementation_paths=(
            "tap_tone_pi/excitation/contracts.py",
            "tap_tone_pi/excitation/stepped_sweep.py",
            "tap_tone_pi/excitation/source_characterization.py",
            "tap_tone_pi/signal_gen/generators.py",
        ),
        test_paths=(
            "tests/test_excitation.py",
            "tests/test_stepped_sweep.py",
            "tests/test_signal_gen.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes=(
            "ExcitationContractV1 describes driven electrical excitation (tone, "
            "stepped, sweep) through an output device — the speaker-air "
            "approach the excitation architecture has since moved away from. "
            "The grounded shaker and stinger contact drive is not implemented; "
            "DO-102 can record that arrangement but recording a method is not "
            "building it. Recorded PARTIAL so a software abstraction is not "
            "read as the proposed excitation architecture having been "
            "delivered."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="calibration",
        name="Loopback, reference-tone, and frequency-response calibration",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/calibration/loopback.py",
            "tap_tone_pi/calibration/reference_tone.py",
            "tap_tone_pi/calibration/compensation.py",
            "tap_tone_pi/calibration/gate.py",
        ),
        test_paths=(
            "tests/test_calibration.py",
            "tests/test_calibration_loopback.py",
            "tests/test_calibration_reference_tone.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Limited to internal signal-chain consistency: loopback, reference "
            "tone, and frequency-response compensation. This is not traceable "
            "calibration and is not evidence of external metrological "
            "validity. No traceability to a calibrated acoustic reference is "
            "claimed anywhere in this repository."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="bending_stiffness_rig",
        name="Static bending stiffness rig (EI, MOE)",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/bending/merge_and_moe.py",
            "tap_tone_pi/capture/dial_indicator_serial.py",
            "tap_tone_pi/capture/loadcell_serial.py",
        ),
        test_paths=(
            "tests/test_merge_and_moe_canonical.py",
            "tests/test_whole_plate_bending.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Archived runs exist under out/bend_*. Serial capture from the "
            "dial indicator and load cell has simulator coverage in-repo."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="uncertainty_quantification",
        name="GUM uncertainty budgets and descriptive statistics",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/uncertainty/budget.py",
            "tap_tone_pi/uncertainty/propagation.py",
            "tap_tone_pi/core/statistics.py",
            "tap_tone_pi/bending/qa_lab_spec.py",
        ),
        test_paths=(
            "tests/test_uncertainty.py",
            "tests/test_statistics.py",
            "tests/test_qa_lab_spec.py",
        ),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "GUM-conformant uncertainty machinery exists and is exercised. A "
            "populated and reviewed acoustic-chain uncertainty budget does not "
            "yet exist; that gap is a DO-102 technical risk."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="repeatability_evidence",
        name="Repeatability evidence and validity envelope (DO-085)",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/core/repeatability.py",
            "contracts/schemas/repeatability_evidence_v1.schema.json",
        ),
        test_paths=(
            "tests/test_repeatability.py",
            "tests/test_repeatability_evidence.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Carries a workflow acceptance gate (default 3% frequency "
            "variance). That threshold is DO-085 workflow policy and is not an "
            "established performance limit; DO-102 references this evidence but "
            "does not inherit its gate."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="damping_q_estimation",
        name="Damping and Q-factor estimation",
        status=_EXPERIMENTAL,
        implementation_paths=(
            "tap_tone_pi/damping/modes.py",
            "tap_tone_pi/damping/extraction.py",
        ),
        test_paths=("tests/test_production_physics.py",),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Covered only indirectly, through the production-physics suite. "
            "No dedicated test module and no stability evidence across repeats."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="multitap_statistics",
        name="Multi-tap statistical aggregation",
        status=_PARTIAL,
        implementation_paths=(
            "tap_tone_pi/multitap/statistical.py",
            "tap_tone_pi/multitap/comparison.py",
            "tap_tone_pi/multitap/quality.py",
        ),
        test_paths=("tests/test_production_physics.py",),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Aggregation helpers exist but no dedicated test module covers "
            "them, and no workflow drives repeated taps end to end. This is the "
            "nearest existing neighbour to the DO-102 experiment path."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="wolf_tone_detection",
        name="Wolf-tone candidate detection",
        status=_EXPERIMENTAL,
        implementation_paths=("tap_tone_pi/wolf/wolf_beat.py",),
        test_paths=("tests/test_wolf_beat.py",),
        hardware_verified=_UNWITNESSED,
        notes=(
            "Detection only. The sibling wolf_advisor module is classified "
            "DECISION SUPPORT and is outside the measurement inventory."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="chladni_pattern_indexing",
        name="Chladni pattern indexing and tolerance policy",
        status=_PARTIAL,
        implementation_paths=(
            "tap_tone_pi/chladni/index_patterns.py",
            "tap_tone_pi/chladni/policy.py",
        ),
        test_paths=(
            "tests/test_chladni_policy.py",
            "tests/test_chladni_pipeline_integration.py",
        ),
        hardware_verified=_UNWITNESSED,
        notes=(
            "The tests exercise the legacy modes/chladni copy rather than the "
            "tap_tone_pi.chladni package this inventory names as canonical. The "
            "duplication is real and unreconciled."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="plate_dynamics_prediction",
        name="Rayleigh-Ritz plate dynamics prediction",
        status=_IMPLEMENTED,
        implementation_paths=("tap_tone_pi/design/rayleigh_ritz.py",),
        test_paths=("tests/test_rayleigh_ritz.py",),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Solver and mode-shape evaluation exist and are covered by tests. "
            "Predicted-versus-measured agreement remains unestablished."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="session_provenance",
        name="Session, environment, and campaign provenance",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/provenance/lineage.py",
            "tap_tone_pi/provenance/environment.py",
            "tap_tone_pi/provenance/build_session.py",
        ),
        test_paths=("tests/test_experiment_lineage.py", "tests/test_build_session.py"),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Environmental fields are recorded as supplied. No temperature or "
            "humidity normalization exists anywhere in the pipeline."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="measurement_workflow_contracts",
        name="Measurement workflow contracts and procedural provenance",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/workflow/contracts.py",
            "tap_tone_pi/workflow/operator_loop.py",
            "contracts/schemas/measurement_workflow_contract_v1.schema.json",
        ),
        test_paths=(
            "tests/test_workflow_contracts.py",
            "tests/test_measurement_workflow_contracts.py",
        ),
        hardware_verified=_NO_HARDWARE,
        notes="Declares procedural requirements a legitimate measurement must meet.",
    ),
    CapabilityEvidenceV1(
        capability_id="experiment_design",
        name="Experiment design, cohort planning, and process variance",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/experiment/experiment_design.py",
            "tap_tone_pi/experiment/process_variance.py",
            "tap_tone_pi/experiment/cohort_regression.py",
        ),
        test_paths=(
            "tests/test_experiment_design.py",
            "tests/test_process_variance.py",
        ),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Planning and variance-decomposition contracts exist. No executed "
            "campaign has populated them with hardware data."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="viewer_pack_export",
        name="Viewer Pack evidence export",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/viewer_pack/manifest.py",
            "scripts/phase2/export_viewer_pack_v1.py",
            "contracts/viewer_pack_v1.schema.json",
        ),
        test_paths=(
            "tests/test_viewer_pack_v1_validator.py",
            "tests/test_viewer_pack_export.py",
        ),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Two archived sessions fail viewer-pack validation on a missing "
            "'bending' key; these are documented baseline failures predating "
            "DO-102."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="guided_laboratory",
        name="Guided digital laboratory workflow spine (DO-100)",
        status=_IMPLEMENTED,
        implementation_paths=(
            "tap_tone_pi/guided_lab/engine.py",
            "tap_tone_pi/guided_lab/validation.py",
            "contracts/guided_lab_session_v1.schema.json",
        ),
        test_paths=(
            "tests/test_guided_lab_engine.py",
            "tests/test_guided_lab_validation.py",
        ),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "CLI-proven and deterministic. No session persistence layer, no "
            "GUI, and no adapter to the tap_tone_pi.workflow measurement "
            "contracts yet."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="desktop_analyzer",
        name="Desktop analyzer GUI",
        status=_IMPLEMENTED,
        implementation_paths=("analyzer/main_window.py",),
        test_paths=("tests/test_gui_widgets.py",),
        hardware_verified=_NO_HARDWARE,
        notes=(
            "Software UI only; the intended hardware workflow has not been "
            "witnessed. Loads measurement outputs for visualization. Unchanged "
            "by DO-102."
        ),
    ),
    CapabilityEvidenceV1(
        capability_id="http_api_server",
        name="HTTP API server with filesystem authorization",
        status=_IMPLEMENTED,
        implementation_paths=("tap_tone_pi/server/app.py",),
        test_paths=("tests/test_server_app.py", "tests/test_server_authorization.py"),
        hardware_verified=_NO_HARDWARE,
        notes="Read-only session and export endpoints beneath a configured data root.",
    ),
    CapabilityEvidenceV1(
        capability_id="unified_cli",
        name="Unified ttp command-line interface",
        status=_IMPLEMENTED,
        implementation_paths=("tap_tone_pi/cli/main.py",),
        test_paths=("tests/test_cli_validators.py", "tests/test_cli_preflight.py"),
        hardware_verified=_NO_HARDWARE,
        notes="Single argparse entry point; DO-102 adds scripts only, no subcommand.",
    ),
)


# What this audit does not establish. These travel with every generated audit so
# a reader cannot take the capability list for a performance claim.
INVENTORY_LIMITATIONS: tuple[str, ...] = (
    "None of the audited capabilities has been witnessed end-to-end on the "
    "intended TTP hardware configuration during DO-102. Software "
    "implementation status and hardware verification are tracked "
    "independently.",
    "IMPLEMENTED means the capability exists in the repository and is "
    "exercised by automated tests. It does not imply intended-hardware "
    "verification, calibrated accuracy, or external validation unless "
    "separately stated.",
    "No comparison against a calibrated reference instrument or an accredited "
    "laboratory has been performed, so no traceability is claimed.",
    "Extracted spectral peaks are feature candidates. No evidence in this "
    "repository establishes them as identified structural modes.",
    "Test coverage is evidence that code runs as written. It is not evidence "
    "that the quantity computed is the physical quantity intended.",
)


__all__ = ["TTP_CAPABILITY_INVENTORY", "INVENTORY_LIMITATIONS"]
