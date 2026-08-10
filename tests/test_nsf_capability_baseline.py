"""Frozen NSF grant-readiness baseline (DO-102, Commit 1).

This module characterizes the repository state that DO-102's grant-readiness
evidence layer will depend on. It is deliberately written *before* the
``tap_tone_pi.grant_readiness`` package exists so the audit cannot later be
written to agree with itself: the inventory below is the declared claim, and
these tests check it against the actual working tree.

Three things are frozen here:

1. **The capability inventory fixture.** A bounded, instrument-level list of
   what TTP does, each entry carrying a status from the four-state vocabulary
   and the repository evidence that supports it. Commit 5 promotes this to
   ``tap_tone_pi/grant_readiness/inventory.py``; a test there checks the two
   agree, so the production inventory cannot drift from this baseline silently.

2. **The DO-085 reuse surface.** DO-102 delegates mean, sample standard
   deviation, coefficient of variation, and range to
   ``tap_tone_pi.core.statistics.compute_repeatability``. These tests pin the
   fields that delegation depends on, and pin the two acceptance fields that
   must *not* propagate into NSF evidence.

3. **The Phase 1 ingestion surface.** The preliminary experiment reads
   ``phase1_tap_analysis_v1`` results. These tests pin the fields the
   repeatability path reads out of that contract.

Nothing here changes production behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The four-state capability vocabulary (DO-102 §4.2). No other value is legal.
VALID_STATUSES = frozenset({"IMPLEMENTED", "EXPERIMENTAL", "PARTIAL", "PLANNED"})

# Secondary hardware-verification state. ``NOT_VERIFIED_ON_HARDWARE`` means code
# exists but execution on the intended Pi/hardware configuration has not been
# witnessed. ``NOT_APPLICABLE`` means the capability has no hardware dependency
# to witness (pure computation, desktop UI).
VALID_HARDWARE_STATES = frozenset(
    {"VERIFIED_ON_HARDWARE", "NOT_VERIFIED_ON_HARDWARE", "NOT_APPLICABLE"}
)

# The bounded inventory: instrument-level capabilities, not a module census.
# Every path below was checked against the working tree when this baseline was
# frozen. Statuses are drafted from repository evidence and carry a human
# ratification step before the DO-102 documentation commit.
CAPABILITY_BASELINE: tuple[dict, ...] = (
    {
        "capability_id": "audio_capture",
        "name": "Audio capture (single and multi-channel)",
        "status": "PARTIAL",
        "implementation_paths": (
            "tap_tone_pi/capture/__init__.py",
            "tap_tone_pi/core/auto_trigger.py",
        ),
        "test_paths": ("tests/test_cli_record_qc.py", "tests/test_auto_trigger.py"),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Software path implemented and exercised with simulated input; the "
            "intended Pi and microphone acquisition chain has not been "
            "witnessed. Device enumeration and streaming go through "
            "sounddevice. Recorded PARTIAL rather than IMPLEMENTED because "
            "IMPLEMENTED would read as 'the system can currently capture real "
            "measurements', which this repository cannot show."
        ),
    },
    {
        "capability_id": "wav_persistence",
        "name": "WAV persistence and round-trip integrity",
        "status": "IMPLEMENTED",
        "implementation_paths": ("tap_tone_pi/io/wav.py", "modes/_shared/wav_io.py"),
        "test_paths": (
            "tests/test_wav_io.py",
            "tests/test_wav_roundtrip.py",
            "tests/test_storage_wav_roundtrip.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Two readers exist. The one under test is modes/_shared/wav_io.py, "
            "which tap_tone_pi.chladni.peaks_from_wav also imports; "
            "tap_tone_pi/io/wav.py holds the writer used by the Phase 1 path."
        ),
    },
    {
        "capability_id": "tap_spectral_analysis",
        "name": "Tap spectral analysis and peak extraction",
        "status": "IMPLEMENTED",
        "implementation_paths": ("tap_tone_pi/core/analysis.py",),
        "test_paths": (
            "tests/test_analysis_parametric.py",
            "tests/test_dsp_cross_validation.py",
            "tests/test_config_and_analysis.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Extracted peaks are spectral feature candidates. This repository "
            "holds no evidence establishing them as identified structural modes."
        ),
    },
    {
        "capability_id": "capture_quality_gate",
        "name": "Capture quality gate (clipping and low-signal safeguards)",
        "status": "IMPLEMENTED",
        "implementation_paths": ("tap_tone_pi/core/quality_gate.py",),
        "test_paths": ("tests/test_quality_gate.py",),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Emits pass/warn/fail verdicts against a versioned rule policy. "
            "Thresholds are workflow policy, not established performance limits."
        ),
    },
    {
        "capability_id": "phase1_tap_workflow",
        "name": "Phase 1 single-microphone tap workflow",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/phase1/demo.py",
            "contracts/phase1_tap_analysis_v1.schema.json",
        ),
        "test_paths": (
            "tests/test_phase1_pipeline_integration.py",
            "tests/test_phase1_demo.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "The end-to-end path is exercised by synthetic impulse generation. "
            "This is the ingestion surface for the DO-102 preliminary "
            "repeatability experiment."
        ),
    },
    {
        "capability_id": "phase2_ods_scanning",
        "name": "Phase 2 roving-grid ODS scanning",
        "status": "IMPLEMENTED",
        "implementation_paths": ("tap_tone_pi/phase2", "scripts/phase2"),
        "test_paths": (
            "tests/test_phase2_schemas.py",
            "tests/test_phase2_session_loader.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Two archived sessions exist under runs_phase2/, each holding one "
            "capture per grid point. Neither contains repeated captures of a "
            "single point, so neither can serve as a repeatability dataset."
        ),
    },
    {
        "capability_id": "transfer_function_coherence",
        "name": "Transfer function and coherence estimation",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/transfer_function/welch.py",
            "tap_tone_pi/transfer_function/estimators.py",
            "tap_tone_pi/transfer_function/quality.py",
        ),
        "test_paths": (
            "tests/test_production_physics.py",
            "tests/test_excitation_provenance.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": "Deliberately outside the DO-102 first study (Phase 1 only).",
    },
    {
        "capability_id": "controlled_excitation",
        "name": "Controlled excitation contracts and signal generation",
        "status": "PARTIAL",
        "implementation_paths": (
            "tap_tone_pi/excitation/contracts.py",
            "tap_tone_pi/excitation/stepped_sweep.py",
            "tap_tone_pi/excitation/source_characterization.py",
            "tap_tone_pi/signal_gen/generators.py",
        ),
        "test_paths": (
            "tests/test_excitation.py",
            "tests/test_stepped_sweep.py",
            "tests/test_signal_gen.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "ExcitationContractV1 describes driven electrical excitation (tone, "
            "stepped, sweep) through an output device — the speaker-air "
            "approach the excitation architecture has since moved away from. "
            "The grounded shaker and stinger contact drive is not implemented; "
            "DO-102 can record that arrangement but recording a method is not "
            "building it. Recorded PARTIAL so a software abstraction is not "
            "read as the proposed excitation architecture having been "
            "delivered."
        ),
    },
    {
        "capability_id": "calibration",
        "name": "Loopback, reference-tone, and frequency-response calibration",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/calibration/loopback.py",
            "tap_tone_pi/calibration/reference_tone.py",
            "tap_tone_pi/calibration/compensation.py",
            "tap_tone_pi/calibration/gate.py",
        ),
        "test_paths": (
            "tests/test_calibration.py",
            "tests/test_calibration_loopback.py",
            "tests/test_calibration_reference_tone.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Limited to internal signal-chain consistency: loopback, reference "
            "tone, and frequency-response compensation. This is not traceable "
            "calibration and is not evidence of external metrological "
            "validity. No traceability to a calibrated acoustic reference is "
            "claimed anywhere in this repository."
        ),
    },
    {
        "capability_id": "bending_stiffness_rig",
        "name": "Static bending stiffness rig (EI, MOE)",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/bending/merge_and_moe.py",
            "tap_tone_pi/capture/dial_indicator_serial.py",
            "tap_tone_pi/capture/loadcell_serial.py",
        ),
        "test_paths": (
            "tests/test_merge_and_moe_canonical.py",
            "tests/test_whole_plate_bending.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Archived runs exist under out/bend_*. Serial capture from the "
            "dial indicator and load cell has simulator coverage in-repo."
        ),
    },
    {
        "capability_id": "uncertainty_quantification",
        "name": "GUM uncertainty budgets and descriptive statistics",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/uncertainty/budget.py",
            "tap_tone_pi/uncertainty/propagation.py",
            "tap_tone_pi/core/statistics.py",
            "tap_tone_pi/bending/qa_lab_spec.py",
        ),
        "test_paths": (
            "tests/test_uncertainty.py",
            "tests/test_statistics.py",
            "tests/test_qa_lab_spec.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "GUM-conformant uncertainty machinery exists and is exercised. A "
            "populated and reviewed acoustic-chain uncertainty budget does not "
            "yet exist; that gap is a DO-102 technical risk."
        ),
    },
    {
        "capability_id": "repeatability_evidence",
        "name": "Repeatability evidence and validity envelope (DO-085)",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/core/repeatability.py",
            "contracts/schemas/repeatability_evidence_v1.schema.json",
        ),
        "test_paths": (
            "tests/test_repeatability.py",
            "tests/test_repeatability_evidence.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Carries a workflow acceptance gate (default 3% frequency "
            "variance). That threshold is DO-085 workflow policy and is not an "
            "established performance limit; DO-102 references this evidence but "
            "does not inherit its gate."
        ),
    },
    {
        "capability_id": "damping_q_estimation",
        "name": "Damping and Q-factor estimation",
        "status": "EXPERIMENTAL",
        "implementation_paths": (
            "tap_tone_pi/damping/modes.py",
            "tap_tone_pi/damping/extraction.py",
        ),
        "test_paths": ("tests/test_production_physics.py",),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Covered only indirectly, through the production-physics suite. "
            "No dedicated test module and no stability evidence across repeats."
        ),
    },
    {
        "capability_id": "multitap_statistics",
        "name": "Multi-tap statistical aggregation",
        "status": "PARTIAL",
        "implementation_paths": (
            "tap_tone_pi/multitap/statistical.py",
            "tap_tone_pi/multitap/comparison.py",
            "tap_tone_pi/multitap/quality.py",
        ),
        "test_paths": ("tests/test_production_physics.py",),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Aggregation helpers exist but no dedicated test module covers "
            "them, and no workflow drives repeated taps end to end. This is the "
            "nearest existing neighbour to the DO-102 experiment path."
        ),
    },
    {
        "capability_id": "wolf_tone_detection",
        "name": "Wolf-tone candidate detection",
        "status": "EXPERIMENTAL",
        "implementation_paths": ("tap_tone_pi/wolf/wolf_beat.py",),
        "test_paths": ("tests/test_wolf_beat.py",),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "Detection only. The sibling wolf_advisor module is classified "
            "DECISION SUPPORT and is outside the measurement inventory."
        ),
    },
    {
        "capability_id": "chladni_pattern_indexing",
        "name": "Chladni pattern indexing and tolerance policy",
        "status": "PARTIAL",
        "implementation_paths": (
            "tap_tone_pi/chladni/index_patterns.py",
            "tap_tone_pi/chladni/policy.py",
        ),
        "test_paths": (
            "tests/test_chladni_policy.py",
            "tests/test_chladni_pipeline_integration.py",
        ),
        "hardware_verified": "NOT_VERIFIED_ON_HARDWARE",
        "notes": (
            "The tests exercise the legacy modes/chladni copy rather than the "
            "tap_tone_pi.chladni package this inventory names as canonical. The "
            "duplication is real and unreconciled."
        ),
    },
    {
        "capability_id": "plate_dynamics_prediction",
        "name": "Rayleigh-Ritz plate dynamics prediction",
        "status": "IMPLEMENTED",
        "implementation_paths": ("tap_tone_pi/design/rayleigh_ritz.py",),
        "test_paths": ("tests/test_rayleigh_ritz.py",),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Solver and mode-shape evaluation exist and are covered by tests. "
            "Predicted-versus-measured agreement remains unestablished."
        ),
    },
    {
        "capability_id": "session_provenance",
        "name": "Session, environment, and campaign provenance",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/provenance/lineage.py",
            "tap_tone_pi/provenance/environment.py",
            "tap_tone_pi/provenance/build_session.py",
        ),
        "test_paths": (
            "tests/test_experiment_lineage.py",
            "tests/test_build_session.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Environmental fields are recorded as supplied. No temperature or "
            "humidity normalization exists anywhere in the pipeline."
        ),
    },
    {
        "capability_id": "measurement_workflow_contracts",
        "name": "Measurement workflow contracts and procedural provenance",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/workflow/contracts.py",
            "tap_tone_pi/workflow/operator_loop.py",
            "contracts/schemas/measurement_workflow_contract_v1.schema.json",
        ),
        "test_paths": (
            "tests/test_workflow_contracts.py",
            "tests/test_measurement_workflow_contracts.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": "Declares procedural requirements a legitimate measurement must meet.",
    },
    {
        "capability_id": "experiment_design",
        "name": "Experiment design, cohort planning, and process variance",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/experiment/experiment_design.py",
            "tap_tone_pi/experiment/process_variance.py",
            "tap_tone_pi/experiment/cohort_regression.py",
        ),
        "test_paths": (
            "tests/test_experiment_design.py",
            "tests/test_process_variance.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Planning and variance-decomposition contracts exist. No executed "
            "campaign has populated them with hardware data."
        ),
    },
    {
        "capability_id": "viewer_pack_export",
        "name": "Viewer Pack evidence export",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/viewer_pack/manifest.py",
            "scripts/phase2/export_viewer_pack_v1.py",
            "contracts/viewer_pack_v1.schema.json",
        ),
        "test_paths": (
            "tests/test_viewer_pack_v1_validator.py",
            "tests/test_viewer_pack_export.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Two archived sessions fail viewer-pack validation on a missing "
            "'bending' key; these are documented baseline failures predating "
            "DO-102."
        ),
    },
    {
        "capability_id": "guided_laboratory",
        "name": "Guided digital laboratory workflow spine (DO-100)",
        "status": "IMPLEMENTED",
        "implementation_paths": (
            "tap_tone_pi/guided_lab/engine.py",
            "tap_tone_pi/guided_lab/validation.py",
            "contracts/guided_lab_session_v1.schema.json",
        ),
        "test_paths": (
            "tests/test_guided_lab_engine.py",
            "tests/test_guided_lab_validation.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "CLI-proven and deterministic. No session persistence layer, no "
            "GUI, and no adapter to the tap_tone_pi.workflow measurement "
            "contracts yet."
        ),
    },
    {
        "capability_id": "desktop_analyzer",
        "name": "Desktop analyzer GUI",
        "status": "IMPLEMENTED",
        "implementation_paths": ("analyzer/main_window.py",),
        "test_paths": ("tests/test_gui_widgets.py",),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": (
            "Software UI only; the intended hardware workflow has not been "
            "witnessed. Loads measurement outputs for visualization. Unchanged "
            "by DO-102."
        ),
    },
    {
        "capability_id": "http_api_server",
        "name": "HTTP API server with filesystem authorization",
        "status": "IMPLEMENTED",
        "implementation_paths": ("tap_tone_pi/server/app.py",),
        "test_paths": (
            "tests/test_server_app.py",
            "tests/test_server_authorization.py",
        ),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": "Read-only session and export endpoints beneath a configured data root.",
    },
    {
        "capability_id": "unified_cli",
        "name": "Unified ttp command-line interface",
        "status": "IMPLEMENTED",
        "implementation_paths": ("tap_tone_pi/cli/main.py",),
        "test_paths": ("tests/test_cli_validators.py", "tests/test_cli_preflight.py"),
        "hardware_verified": "NOT_APPLICABLE",
        "notes": "Single argparse entry point; DO-102 adds scripts only, no subcommand.",
    },
)


# ---------------------------------------------------------------------------
# Inventory shape
# ---------------------------------------------------------------------------


class TestCapabilityInventoryShape:
    """The declared inventory is well-formed and bounded."""

    def test_inventory_is_bounded(self):
        # DO-102 authorizes an instrument-level inventory, not a module census.
        assert 15 <= len(CAPABILITY_BASELINE) <= 25

    def test_capability_ids_unique(self):
        ids = [entry["capability_id"] for entry in CAPABILITY_BASELINE]
        assert len(ids) == len(set(ids))

    def test_every_status_is_one_of_four(self):
        for entry in CAPABILITY_BASELINE:
            assert entry["status"] in VALID_STATUSES, entry["capability_id"]

    def test_every_hardware_state_is_known(self):
        for entry in CAPABILITY_BASELINE:
            assert entry["hardware_verified"] in VALID_HARDWARE_STATES

    def test_every_entry_carries_notes(self):
        # A status with no explanation is not evidence.
        for entry in CAPABILITY_BASELINE:
            assert entry["notes"].strip()

    def test_no_capability_claims_hardware_verification(self):
        # DO-102 executes no hardware campaign. Nothing in this repository may
        # claim witnessed execution on the intended Pi configuration.
        for entry in CAPABILITY_BASELINE:
            assert entry["hardware_verified"] != "VERIFIED_ON_HARDWARE"


# ---------------------------------------------------------------------------
# Inventory vs. repository state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", CAPABILITY_BASELINE, ids=lambda e: e["capability_id"])
class TestCapabilityEvidenceExists:
    """Declared evidence resolves against the actual working tree."""

    def test_implementation_paths_exist(self, entry):
        for rel in entry["implementation_paths"]:
            assert (REPO_ROOT / rel).exists(), f"{entry['capability_id']}: {rel}"

    def test_test_paths_exist(self, entry):
        for rel in entry["test_paths"]:
            assert (REPO_ROOT / rel).exists(), f"{entry['capability_id']}: {rel}"

    def test_implemented_requires_code_and_tests(self, entry):
        # An IMPLEMENTED claim with no code or no test is a contradiction.
        if entry["status"] == "IMPLEMENTED":
            assert entry["implementation_paths"]
            assert entry["test_paths"]

    def test_planned_declares_no_implementation(self, entry):
        if entry["status"] == "PLANNED":
            assert not entry["implementation_paths"]


# ---------------------------------------------------------------------------
# DO-085 reuse surface
# ---------------------------------------------------------------------------


class TestRepeatabilityReuseSurface:
    """Pin what DO-102 delegates to, and what it must refuse to inherit."""

    def test_delegated_fields_are_present(self):
        from tap_tone_pi.core.statistics import compute_repeatability

        result = compute_repeatability([440.2, 440.1, 440.3, 440.2, 440.2])

        # The four quantities DO-102 does not recompute.
        assert result.mean == pytest.approx(440.2, abs=1e-9)
        assert result.repeatability_std_dev > 0.0
        assert result.coefficient_of_variation_pct > 0.0
        assert result.range_value == pytest.approx(0.2, abs=1e-9)
        assert result.n_measurements == 5

    def test_sample_standard_deviation_convention(self):
        from tap_tone_pi.core.statistics import compute_repeatability

        # Bessel-corrected (n-1). For [1, 2, 3] the sample SD is exactly 1.0;
        # the population SD would be 0.8165. DO-102 inherits this convention and
        # states it in the report.
        result = compute_repeatability([1.0, 2.0, 3.0])
        assert result.repeatability_std_dev == pytest.approx(1.0, abs=1e-12)

    def test_acceptance_fields_exist_and_are_not_nsf_criteria(self):
        from tap_tone_pi.core.statistics import compute_repeatability

        result = compute_repeatability([440.2, 440.1, 440.3])

        # These two exist in DO-085 and must not propagate into NSF evidence.
        # Pinned so their removal or renaming is noticed rather than silently
        # changing what DO-102 is excluding.
        assert hasattr(result, "is_acceptable")
        assert hasattr(result, "acceptance_threshold_pct")

    def test_fewer_than_two_measurements_rejected(self):
        from tap_tone_pi.core.statistics import compute_repeatability

        with pytest.raises(ValueError):
            compute_repeatability([440.0])

    def test_zero_mean_returns_sentinel_cv(self):
        from tap_tone_pi.core.statistics import compute_repeatability

        # A zero mean makes CV undefined, but the DO-085 helper reports 0.0 —
        # indistinguishable from perfect repeatability. DO-102 must refuse to
        # publish this value rather than pass it through.
        result = compute_repeatability([-1.0, 0.0, 1.0])
        assert result.mean == pytest.approx(0.0, abs=1e-12)
        assert result.coefficient_of_variation_pct == 0.0

    def test_do085_evidence_contract_is_importable(self):
        # DO-102 cross-references this record by identity; it does not inherit
        # from it and does not depend on it for its own serialization.
        from tap_tone_pi.core.repeatability import RepeatabilityEvidenceV1

        evidence = RepeatabilityEvidenceV1()
        assert evidence.schema_version == "repeatability_evidence_v1"
        assert hasattr(evidence, "passed_repeatability_gate")


# ---------------------------------------------------------------------------
# Phase 1 ingestion surface
# ---------------------------------------------------------------------------


class TestPhase1IngestionSurface:
    """Pin the phase1_tap_analysis_v1 fields the experiment path reads."""

    @pytest.fixture(scope="class")
    def schema(self) -> dict:
        path = REPO_ROOT / "contracts" / "phase1_tap_analysis_v1.schema.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_schema_version_const(self, schema):
        assert (
            schema["properties"]["schema_version"]["const"] == "phase1_tap_analysis_v1"
        )

    def test_observed_feature_fields_present(self, schema):
        analysis = schema["properties"]["analysis"]["properties"]
        # Dominant frequency, peak magnitude, and SNR are the three quantities
        # the first study summarizes.
        assert "dominant_hz" in analysis
        assert "magnitude" in analysis["peaks"]["items"]["properties"]
        assert "snr_db" in analysis["confidence_components"]["properties"]

    def test_rejection_signal_fields_present(self, schema):
        analysis = schema["properties"]["analysis"]["properties"]
        assert analysis["clipped"]["type"] == "boolean"
        assert "rms" in analysis

        quality = schema["properties"]["quality"]["properties"]
        assert quality["verdict"]["enum"] == ["pass", "warn", "fail"]

    def test_provenance_fields_present(self, schema):
        provenance = schema["properties"]["provenance"]["properties"]
        assert provenance["audio_sha256"]["pattern"] == "^[a-f0-9]{64}$"

        environment = provenance["environment"]["properties"]
        assert "temp_c" in environment
        assert "rh_pct" in environment

    def test_demo_flag_distinguishes_synthetic_audio(self, schema):
        # The contract already marks synthetic input. DO-102 relies on this to
        # keep fixture evidence from being presented as hardware evidence.
        assert schema["properties"]["demo"]["type"] == "boolean"
