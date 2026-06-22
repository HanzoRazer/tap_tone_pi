# INSTRUMENT CLASS: MEASUREMENT
"""Tests for pressure response mapping (DO-94).

Validates:
- PressureGridPointV1, PressureGridV1 structure
- PressureResponseSampleV1, PressureResponseMapV1 structure
- PressureResponseMappingWorkflowV1 configuration
- Assembly helpers validation
- Normalization
- Summary statistics
- Provenance linkage
- Advisory-free and mode-shape-free semantics
"""

import json
import pytest

from tap_tone_pi.pressure_map import (
    CoordinateSystem,
    PressureGridPointV1,
    PressureGridV1,
    PressureResponseSampleV1,
    PressureResponseMapV1,
    PressureResponseMappingWorkflowV1,
    PressureResponseMapSummaryV1,
    create_pressure_grid_point,
    create_pressure_grid,
    create_pressure_response_sample,
    assemble_pressure_response_map,
    normalize_pressure_response_map,
    summarize_pressure_response_map,
    create_pressure_response_mapping_workflow,
)


class TestPressureGridPoint:
    """Tests for PressureGridPointV1."""

    def test_point_is_frozen(self):
        """PressureGridPointV1 must be immutable."""
        point = PressureGridPointV1(point_id="A1")
        with pytest.raises(AttributeError):
            point.point_id = "B2"

    def test_point_has_schema_version(self):
        """PressureGridPointV1 must have schema_version."""
        point = PressureGridPointV1(point_id="A1")
        assert point.schema_version == "pressure_grid_point_v1"

    def test_point_has_epistemic_status_observed(self):
        """PressureGridPointV1 must have epistemic_status = observed."""
        point = PressureGridPointV1(point_id="A1")
        assert point.epistemic_status == "observed"

    def test_create_point(self):
        """create_pressure_grid_point must work correctly."""
        point = create_pressure_grid_point(
            point_id="A1",
            x_mm=10.0,
            y_mm=20.0,
            z_mm=5.0,
            label="Top left",
        )
        assert point.point_id == "A1"
        assert point.x_mm == 10.0
        assert point.y_mm == 20.0
        assert point.z_mm == 5.0
        assert point.label == "Top left"

    def test_point_serializes(self):
        """PressureGridPointV1 must serialize to JSON."""
        point = create_pressure_grid_point("A1", 10.0, 20.0)
        d = point.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["point_id"] == "A1"


class TestPressureGrid:
    """Tests for PressureGridV1."""

    def test_grid_is_frozen(self):
        """PressureGridV1 must be immutable."""
        grid = PressureGridV1(grid_id="grid_001")
        with pytest.raises(AttributeError):
            grid.grid_id = "grid_002"

    def test_grid_has_schema_version(self):
        """PressureGridV1 must have schema_version."""
        grid = PressureGridV1(grid_id="grid_001")
        assert grid.schema_version == "pressure_grid_v1"

    def test_grid_has_epistemic_status_derived(self):
        """PressureGridV1 must have epistemic_status = derived."""
        grid = PressureGridV1(grid_id="grid_001")
        assert grid.epistemic_status == "derived"

    def test_create_grid(self):
        """create_pressure_grid must work correctly."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        p2 = create_pressure_grid_point("A2", 10.0, 0.0)
        p3 = create_pressure_grid_point("B1", 0.0, 10.0)

        grid = create_pressure_grid(
            grid_id="grid_001",
            points=[p1, p2, p3],
            coordinate_system=CoordinateSystem.BODY_LOCAL_MM,
            surface_reference="soundboard top",
        )

        assert grid.grid_id == "grid_001"
        assert len(grid.points) == 3
        assert grid.coordinate_system == "body_local_mm"
        assert grid.surface_reference == "soundboard top"

    def test_grid_rejects_duplicate_points(self):
        """create_pressure_grid must reject duplicate point IDs."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        p2 = create_pressure_grid_point("A1", 10.0, 0.0)  # Duplicate ID

        with pytest.raises(ValueError, match="Duplicate point IDs"):
            create_pressure_grid(grid_id="grid_001", points=[p1, p2])

    def test_grid_serializes(self):
        """PressureGridV1 must serialize to JSON."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        grid = create_pressure_grid(grid_id="grid_001", points=[p1])
        d = grid.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["grid_id"] == "grid_001"
        assert len(parsed["points"]) == 1


class TestPressureResponseSample:
    """Tests for PressureResponseSampleV1."""

    def test_sample_is_frozen(self):
        """PressureResponseSampleV1 must be immutable."""
        sample = PressureResponseSampleV1(sample_id="s_001")
        with pytest.raises(AttributeError):
            sample.sample_id = "s_002"

    def test_sample_has_schema_version(self):
        """PressureResponseSampleV1 must have schema_version."""
        sample = PressureResponseSampleV1(sample_id="s_001")
        assert sample.schema_version == "pressure_response_sample_v1"

    def test_sample_has_epistemic_status_observed(self):
        """PressureResponseSampleV1 must have epistemic_status = observed."""
        sample = PressureResponseSampleV1(sample_id="s_001")
        assert sample.epistemic_status == "observed"

    def test_create_sample(self):
        """create_pressure_response_sample must work correctly."""
        sample = create_pressure_response_sample(
            sample_id="s_001",
            point_id="A1",
            frequency_hz=100.0,
            response_amplitude_db=-12.5,
            excitation_id="exc_001",
            response_phase_deg=45.0,
            coherence=0.95,
        )

        assert sample.sample_id == "s_001"
        assert sample.point_id == "A1"
        assert sample.frequency_hz == 100.0
        assert sample.response_amplitude_db == -12.5
        assert sample.excitation_id == "exc_001"
        assert sample.response_phase_deg == 45.0
        assert sample.coherence == 0.95

    def test_sample_allows_missing_phase_and_coherence(self):
        """create_pressure_response_sample must allow missing optional fields."""
        sample = create_pressure_response_sample(
            sample_id="s_001",
            point_id="A1",
            frequency_hz=100.0,
            response_amplitude_db=-12.5,
            excitation_id="exc_001",
        )

        assert sample.response_phase_deg is None
        assert sample.coherence is None
        assert sample.noise_floor_db is None
        assert sample.snr_db is None

    def test_sample_serializes(self):
        """PressureResponseSampleV1 must serialize to JSON."""
        sample = create_pressure_response_sample(
            sample_id="s_001",
            point_id="A1",
            frequency_hz=100.0,
            response_amplitude_db=-12.5,
            excitation_id="exc_001",
        )
        d = sample.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["sample_id"] == "s_001"


class TestPressureResponseMap:
    """Tests for PressureResponseMapV1."""

    def _create_test_grid_and_samples(self):
        """Create test grid and samples."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        p2 = create_pressure_grid_point("A2", 10.0, 0.0)
        grid = create_pressure_grid(grid_id="grid_001", points=[p1, p2])

        s1 = create_pressure_response_sample(
            "s_001", "A1", 100.0, -10.0, "exc_001"
        )
        s2 = create_pressure_response_sample(
            "s_002", "A2", 100.0, -15.0, "exc_001"
        )

        return grid, [s1, s2]

    def test_map_is_frozen(self):
        """PressureResponseMapV1 must be immutable."""
        prm = PressureResponseMapV1(map_id="map_001")
        with pytest.raises(AttributeError):
            prm.map_id = "map_002"

    def test_map_has_schema_version(self):
        """PressureResponseMapV1 must have schema_version."""
        prm = PressureResponseMapV1(map_id="map_001")
        assert prm.schema_version == "pressure_response_map_v1"

    def test_map_has_epistemic_status_derived(self):
        """PressureResponseMapV1 must have epistemic_status = derived."""
        prm = PressureResponseMapV1(map_id="map_001")
        assert prm.epistemic_status == "derived"

    def test_assemble_map_with_frequency(self):
        """assemble_pressure_response_map must work with frequency_hz."""
        grid, samples = self._create_test_grid_and_samples()

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=samples,
            frequency_hz=100.0,
        )

        assert prm.map_id == "map_001"
        assert prm.frequency_hz == 100.0
        assert prm.frequency_band_hz is None
        assert len(prm.samples) == 2

    def test_assemble_map_with_band(self):
        """assemble_pressure_response_map must work with frequency_band_hz."""
        grid, samples = self._create_test_grid_and_samples()

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=samples,
            frequency_band_hz=(80.0, 120.0),
        )

        assert prm.frequency_hz is None
        assert prm.frequency_band_hz == (80.0, 120.0)

    def test_assemble_map_rejects_both_frequency_fields(self):
        """assemble_pressure_response_map must reject both frequency fields."""
        grid, samples = self._create_test_grid_and_samples()

        with pytest.raises(ValueError, match="mutually exclusive"):
            assemble_pressure_response_map(
                map_id="map_001",
                workflow_id="wf_001",
                grid=grid,
                excitation_id="exc_001",
                samples=samples,
                frequency_hz=100.0,
                frequency_band_hz=(80.0, 120.0),
            )

    def test_assemble_map_rejects_neither_frequency_field(self):
        """assemble_pressure_response_map must reject missing frequency."""
        grid, samples = self._create_test_grid_and_samples()

        with pytest.raises(ValueError, match="must be specified"):
            assemble_pressure_response_map(
                map_id="map_001",
                workflow_id="wf_001",
                grid=grid,
                excitation_id="exc_001",
                samples=samples,
            )

    def test_assemble_map_rejects_unknown_point(self):
        """assemble_pressure_response_map must reject unknown point IDs."""
        grid, _ = self._create_test_grid_and_samples()

        # Sample with unknown point ID
        bad_sample = create_pressure_response_sample(
            "s_bad", "Z9", 100.0, -10.0, "exc_001"
        )

        with pytest.raises(ValueError, match="unknown grid points"):
            assemble_pressure_response_map(
                map_id="map_001",
                workflow_id="wf_001",
                grid=grid,
                excitation_id="exc_001",
                samples=[bad_sample],
                frequency_hz=100.0,
            )

    def test_map_serializes(self):
        """PressureResponseMapV1 must serialize to JSON."""
        grid, samples = self._create_test_grid_and_samples()

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=samples,
            frequency_hz=100.0,
        )

        d = prm.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["map_id"] == "map_001"
        assert len(parsed["samples"]) == 2

    def test_map_records_excitation_reference(self):
        """PressureResponseMapV1 must record excitation reference."""
        grid, samples = self._create_test_grid_and_samples()

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=samples,
            frequency_hz=100.0,
        )

        d = prm.to_dict()
        assert d["excitation_id"] == "exc_001"

    def test_map_records_environment_and_fixture_reference(self):
        """PressureResponseMapV1 must record environment/fixture reference."""
        grid, samples = self._create_test_grid_and_samples()

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=samples,
            frequency_hz=100.0,
            environment_id="env_001",
            fixture_id="fix_001",
        )

        d = prm.to_dict()
        assert d["environment_id"] == "env_001"
        assert d["fixture_id"] == "fix_001"


class TestNormalization:
    """Tests for normalize_pressure_response_map."""

    def test_normalize_sets_max_to_zero(self):
        """normalize_pressure_response_map must set max to 0 dB."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        p2 = create_pressure_grid_point("A2", 10.0, 0.0)
        grid = create_pressure_grid(grid_id="grid_001", points=[p1, p2])

        s1 = create_pressure_response_sample(
            "s_001", "A1", 100.0, -10.0, "exc_001"
        )
        s2 = create_pressure_response_sample(
            "s_002", "A2", 100.0, -15.0, "exc_001"
        )

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=[s1, s2],
            frequency_hz=100.0,
        )

        normalized = normalize_pressure_response_map(prm)

        # Find max amplitude in normalized map
        max_amp = max(s.response_amplitude_db for s in normalized.samples)
        assert max_amp == 0.0

        # Check relative amplitudes preserved
        # Original: A1=-10, A2=-15. Max=-10, so A1->0, A2->-5
        for s in normalized.samples:
            if s.point_id == "A1":
                assert s.response_amplitude_db == 0.0
            elif s.point_id == "A2":
                assert s.response_amplitude_db == -5.0


class TestSummary:
    """Tests for summarize_pressure_response_map."""

    def test_summary_uses_max_not_best_language(self):
        """Summary must use max_response_point_id, not best_point_id."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        p2 = create_pressure_grid_point("A2", 10.0, 0.0)
        grid = create_pressure_grid(grid_id="grid_001", points=[p1, p2])

        s1 = create_pressure_response_sample(
            "s_001", "A1", 100.0, -10.0, "exc_001"
        )
        s2 = create_pressure_response_sample(
            "s_002", "A2", 100.0, -15.0, "exc_001"
        )

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=[s1, s2],
            frequency_hz=100.0,
        )

        summary = summarize_pressure_response_map(prm)

        # Check field names
        d = summary.to_dict()
        assert "max_response_point_id" in d
        assert "best_point_id" not in d
        assert "best" not in json.dumps(d).lower()

        # Check values
        assert summary.max_response_point_id == "A1"  # -10 dB is higher than -15 dB
        assert summary.min_response_point_id == "A2"
        assert summary.max_response_db == -10.0
        assert summary.min_response_db == -15.0


class TestWorkflow:
    """Tests for PressureResponseMappingWorkflowV1."""

    def test_workflow_is_frozen(self):
        """PressureResponseMappingWorkflowV1 must be immutable."""
        wf = PressureResponseMappingWorkflowV1(workflow_id="wf_001")
        with pytest.raises(AttributeError):
            wf.workflow_id = "wf_002"

    def test_workflow_has_schema_version(self):
        """PressureResponseMappingWorkflowV1 must have schema_version."""
        wf = PressureResponseMappingWorkflowV1(workflow_id="wf_001")
        assert wf.schema_version == "pressure_response_mapping_workflow_v1"

    def test_create_workflow(self):
        """create_pressure_response_mapping_workflow must work correctly."""
        wf = create_pressure_response_mapping_workflow(
            workflow_id="wf_001",
            grid_id="grid_001",
            excitation_id="exc_001",
            target_frequencies_hz=[100.0, 200.0, 300.0],
            minimum_repetitions=5,
        )

        assert wf.workflow_id == "wf_001"
        assert wf.grid_id == "grid_001"
        assert wf.excitation_id == "exc_001"
        assert wf.target_frequencies_hz == (100.0, 200.0, 300.0)
        assert wf.minimum_repetitions == 5

    def test_workflow_serializes(self):
        """PressureResponseMappingWorkflowV1 must serialize to JSON."""
        wf = create_pressure_response_mapping_workflow(
            workflow_id="wf_001",
            grid_id="grid_001",
            excitation_id="exc_001",
            target_frequencies_hz=[100.0],
        )
        d = wf.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["workflow_id"] == "wf_001"


class TestAdvisoryFreeSemantics:
    """Tests for advisory-free and mode-shape-free semantics."""

    # Forbidden terms in artifacts
    FORBIDDEN_TERMS = {
        "best",
        "optimal",
        "recommended",
        "antinode",
        "mode_shape",
        "soundhole_recommendation",
    }

    def test_map_contains_no_forbidden_terms(self):
        """PressureResponseMapV1 must not contain forbidden terms."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        grid = create_pressure_grid(grid_id="grid_001", points=[p1])
        s1 = create_pressure_response_sample(
            "s_001", "A1", 100.0, -10.0, "exc_001"
        )

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=[s1],
            frequency_hz=100.0,
        )

        d = prm.to_dict()
        json_str = json.dumps(d).lower()

        for term in self.FORBIDDEN_TERMS:
            assert term not in json_str, (
                f"Map contains forbidden term '{term}'"
            )

    def test_summary_contains_no_forbidden_terms(self):
        """PressureResponseMapSummaryV1 must not contain forbidden terms."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        grid = create_pressure_grid(grid_id="grid_001", points=[p1])
        s1 = create_pressure_response_sample(
            "s_001", "A1", 100.0, -10.0, "exc_001"
        )

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=[s1],
            frequency_hz=100.0,
        )

        summary = summarize_pressure_response_map(prm)
        d = summary.to_dict()
        json_str = json.dumps(d).lower()

        for term in self.FORBIDDEN_TERMS:
            assert term not in json_str, (
                f"Summary contains forbidden term '{term}'"
            )

    def test_workflow_contains_no_forbidden_terms(self):
        """PressureResponseMappingWorkflowV1 must not contain forbidden terms."""
        wf = create_pressure_response_mapping_workflow(
            workflow_id="wf_001",
            grid_id="grid_001",
            excitation_id="exc_001",
            target_frequencies_hz=[100.0],
        )

        d = wf.to_dict()
        json_str = json.dumps(d).lower()

        for term in self.FORBIDDEN_TERMS:
            assert term not in json_str, (
                f"Workflow contains forbidden term '{term}'"
            )

    def test_map_contains_no_mode_shape_claims(self):
        """Artifacts must not claim to identify mode shapes."""
        p1 = create_pressure_grid_point("A1", 0.0, 0.0)
        grid = create_pressure_grid(grid_id="grid_001", points=[p1])
        s1 = create_pressure_response_sample(
            "s_001", "A1", 100.0, -10.0, "exc_001"
        )

        prm = assemble_pressure_response_map(
            map_id="map_001",
            workflow_id="wf_001",
            grid=grid,
            excitation_id="exc_001",
            samples=[s1],
            frequency_hz=100.0,
        )

        d = prm.to_dict()
        json_str = json.dumps(d).lower()

        # No mode shape claims
        assert "mode" not in json_str or "pressure" in json_str
        assert "antinode" not in json_str
        assert "node" not in json_str or "point" in json_str


class TestCoordinateSystem:
    """Tests for CoordinateSystem enum."""

    def test_body_local_mm(self):
        """CoordinateSystem.BODY_LOCAL_MM must have correct value."""
        assert CoordinateSystem.BODY_LOCAL_MM.value == "body_local_mm"

    def test_plate_local_mm(self):
        """CoordinateSystem.PLATE_LOCAL_MM must have correct value."""
        assert CoordinateSystem.PLATE_LOCAL_MM.value == "plate_local_mm"

    def test_fixture_local_mm(self):
        """CoordinateSystem.FIXTURE_LOCAL_MM must have correct value."""
        assert CoordinateSystem.FIXTURE_LOCAL_MM.value == "fixture_local_mm"

    def test_microphone_grid_mm(self):
        """CoordinateSystem.MICROPHONE_GRID_MM must have correct value."""
        assert CoordinateSystem.MICROPHONE_GRID_MM.value == "microphone_grid_mm"
