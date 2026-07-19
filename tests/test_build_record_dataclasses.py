"""
Tests for build_record.py dataclasses and helper functions.

DO-004 Stage B acceptance tests:
- BuildRecord and nested dataclasses instantiate without error
- Invalid build_id pattern rejected
- build_to_dict adds schema_version
- build_from_dict reconstructs full record with nested structures
- validate_build passes for valid records
- compute_residuals computes correct values
- Round-trip dict→BuildRecord→dict preserves data
"""

import pytest

from tap_tone_pi.materials import (
    AsBuiltDimensions,
    BraceDimension,
    BuildRecord,
    MeasuredSummary,
    MeasurementPaths,
    PlayerEvaluation,
    PredictedValues,
    Residuals,
    SubjectiveEvaluation,
    WoodSelection,
    build_from_dict,
    build_to_dict,
    compute_residuals,
    validate_build,
)


class TestBuildRecord:
    """BuildRecord dataclass tests."""

    def test_minimal_instantiation(self):
        """BuildRecord with required fields only."""
        b = BuildRecord(
            build_id="CARLOS_JUMBO_001",
            design_name="Carlos Jumbo",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
        )
        assert b.build_id == "CARLOS_JUMBO_001"
        assert b.design_name == "Carlos Jumbo"
        assert isinstance(b.wood, WoodSelection)

    def test_invalid_build_id_rejected(self):
        """Bad build_id pattern raises ValueError."""
        with pytest.raises(ValueError, match="Invalid build_id"):
            BuildRecord(
                build_id="lowercase_bad",
                design_name="Test",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
            )

    def test_with_wood_selection(self):
        """BuildRecord with populated wood selection."""
        wood = WoodSelection(
            top_flitch_id="SITKA_2026_001",
            top_subid="A",
            back_flitch_id="ROSEWOOD_2026_001",
        )
        b = BuildRecord(
            build_id="TEST_001",
            design_name="Test",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
            wood=wood,
        )
        assert b.wood.top_flitch_id == "SITKA_2026_001"
        assert b.wood.back_flitch_id == "ROSEWOOD_2026_001"

    def test_with_all_sections(self):
        """BuildRecord with all optional sections."""
        b = BuildRecord(
            build_id="FULL_001",
            design_name="Full Test",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
            build_completed="2026-06-15",
            as_built_dimensions=AsBuiltDimensions(
                soundhole_diameter_mm=102.0,
                scale_length_mm=650.0,
            ),
            measurements=MeasurementPaths(
                modal_scans=["session_001/ods.json"],
            ),
            predicted=PredictedValues(T1_hz=95.0, A0_hz=100.0),
            measured_summary=MeasuredSummary(T1_hz=92.0, A0_hz=98.0),
            residuals=Residuals(T1_residual_hz=-3.0, T1_residual_pct=-3.16),
            subjective=SubjectiveEvaluation(builder_notes="Good response"),
        )
        assert b.as_built_dimensions.soundhole_diameter_mm == 102.0
        assert b.predicted.T1_hz == 95.0
        assert b.residuals.T1_residual_hz == -3.0


class TestNestedDataclasses:
    """Tests for nested dataclass structures."""

    def test_wood_selection_defaults(self):
        """WoodSelection defaults all fields to None."""
        w = WoodSelection()
        assert w.top_flitch_id is None
        assert w.back_flitch_id is None

    def test_brace_dimension(self):
        """BraceDimension with all fields."""
        bd = BraceDimension(
            name="X_bass",
            height_mm=8.0,
            width_mm=6.0,
            length_mm=240.0,
            scallop_depth_mm=2.0,
            taper_type="parabolic",
        )
        assert bd.name == "X_bass"
        assert bd.height_mm == 8.0

    def test_as_built_with_braces(self):
        """AsBuiltDimensions with brace list."""
        braces = [
            BraceDimension(name="X_bass", height_mm=8.0),
            BraceDimension(name="X_treble", height_mm=7.5),
        ]
        abd = AsBuiltDimensions(brace_dimensions=braces)
        assert len(abd.brace_dimensions) == 2

    def test_player_evaluation(self):
        """PlayerEvaluation with ratings."""
        pe = PlayerEvaluation(
            player_id="Ross",
            date="2026-06-20",
            engagement_minutes=45,
            tone_rating=8,
            playability_rating=9,
            notes="Great projection",
        )
        assert pe.tone_rating == 8
        assert pe.playability_rating == 9

    def test_subjective_with_evaluations(self):
        """SubjectiveEvaluation with player list."""
        evals = [
            PlayerEvaluation(player_id="Player1", date="2026-06-20"),
            PlayerEvaluation(player_id="Player2", date="2026-06-21"),
        ]
        se = SubjectiveEvaluation(
            builder_notes="Build went well",
            player_evaluations=evals,
        )
        assert len(se.player_evaluations) == 2


class TestBuildToDict:
    """Tests for build_to_dict()."""

    def test_adds_schema_version(self):
        """Output dict has schema_version field."""
        b = BuildRecord(
            build_id="TEST_001",
            design_name="Test",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
        )
        d = build_to_dict(b)
        assert d["schema_version"] == "instrument_build_record_v1"

    def test_converts_nested_structures(self):
        """Nested dataclasses become dicts."""
        b = BuildRecord(
            build_id="TEST_001",
            design_name="Test",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
            wood=WoodSelection(top_flitch_id="SITKA_001"),
            predicted=PredictedValues(T1_hz=95.0),
        )
        d = build_to_dict(b)
        assert isinstance(d["wood"], dict)
        assert d["wood"]["top_flitch_id"] == "SITKA_001"
        assert isinstance(d["predicted"], dict)
        assert d["predicted"]["T1_hz"] == 95.0


class TestBuildFromDict:
    """Tests for build_from_dict()."""

    def test_reconstructs_minimal(self):
        """Minimal dict becomes BuildRecord."""
        d = {
            "schema_version": "instrument_build_record_v1",
            "build_id": "TEST_001",
            "design_name": "Test",
            "build_started": "2026-05-01",
            "created_at_utc": "2026-05-01T10:00:00Z",
            "wood": {},
        }
        b = build_from_dict(d)
        assert isinstance(b, BuildRecord)
        assert b.build_id == "TEST_001"

    def test_reconstructs_with_nested(self):
        """Dict with nested structures reconstructs correctly."""
        d = {
            "schema_version": "instrument_build_record_v1",
            "build_id": "TEST_001",
            "design_name": "Test",
            "build_started": "2026-05-01",
            "created_at_utc": "2026-05-01T10:00:00Z",
            "wood": {"top_flitch_id": "SITKA_001", "top_subid": "A"},
            "as_built_dimensions": {
                "soundhole_diameter_mm": 102.0,
                "brace_dimensions": [
                    {"name": "X_bass", "height_mm": 8.0},
                ],
            },
            "predicted": {"T1_hz": 95.0},
            "subjective": {
                "builder_notes": "Good",
                "player_evaluations": [
                    {"player_id": "Test", "date": "2026-06-01"},
                ],
            },
        }
        b = build_from_dict(d)
        assert b.wood.top_flitch_id == "SITKA_001"
        assert b.as_built_dimensions.brace_dimensions[0].name == "X_bass"
        assert b.predicted.T1_hz == 95.0
        assert b.subjective.player_evaluations[0].player_id == "Test"


class TestValidateBuild:
    """Tests for validate_build()."""

    def test_valid_build_passes(self):
        """Valid BuildRecord passes schema validation."""
        b = BuildRecord(
            build_id="TEST_001",
            design_name="Test",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
        )
        validate_build(b)  # Should not raise

    def test_full_build_passes(self):
        """Full BuildRecord passes validation."""
        b = BuildRecord(
            build_id="FULL_001",
            design_name="Full Test",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
            wood=WoodSelection(top_flitch_id="SITKA_001"),
            predicted=PredictedValues(T1_hz=95.0, A0_hz=100.0),
            measured_summary=MeasuredSummary(T1_hz=92.0),
            subjective=SubjectiveEvaluation(
                player_evaluations=[
                    PlayerEvaluation(player_id="Test", date="2026-06-01"),
                ],
            ),
        )
        validate_build(b)  # Should not raise


class TestComputeResiduals:
    """Tests for compute_residuals()."""

    def test_computes_correctly(self):
        """Residuals computed as measured - predicted."""
        pred = PredictedValues(T1_hz=100.0, A0_hz=100.0)
        meas = MeasuredSummary(T1_hz=95.0, A0_hz=102.0)

        res = compute_residuals(pred, meas)

        assert res.T1_residual_hz == -5.0
        assert res.T1_residual_pct == -5.0
        assert res.A0_residual_hz == 2.0
        assert res.A0_residual_pct == 2.0
        assert res.computed_at_utc is not None

    def test_handles_none_values(self):
        """None inputs produce None outputs."""
        pred = PredictedValues(T1_hz=100.0, A0_hz=None)
        meas = MeasuredSummary(T1_hz=None, A0_hz=98.0)

        res = compute_residuals(pred, meas)

        assert res.T1_residual_hz is None
        assert res.T1_residual_pct is None
        assert res.A0_residual_hz is None
        assert res.A0_residual_pct is None

    def test_bridge_deflection(self):
        """Bridge deflection residual computed."""
        pred = PredictedValues(bridge_deflection_mm_at_string_load=0.8)
        meas = MeasuredSummary(bridge_deflection_mm=0.75)

        res = compute_residuals(pred, meas)

        assert res.bridge_deflection_residual_mm == pytest.approx(-0.05, rel=1e-6)
        assert res.bridge_deflection_residual_pct == pytest.approx(-6.25, rel=1e-6)


class TestRoundTrip:
    """Round-trip conversion tests."""

    def test_full_round_trip(self):
        """dict → BuildRecord → dict preserves data."""
        original = {
            "schema_version": "instrument_build_record_v1",
            "build_id": "ROUNDTRIP_001",
            "design_name": "Round Trip Test",
            "build_started": "2026-05-01",
            "build_completed": "2026-06-15",
            "created_at_utc": "2026-05-01T10:00:00Z",
            "updated_at_utc": None,
            "design_blueprint_path": "designs/test.pdf",
            "wood": {
                "top_flitch_id": "SITKA_001",
                "top_subid": "A",
                "back_flitch_id": None,
                "back_subid": None,
                "sides_flitch_id": None,
                "sides_subid": None,
                "neck_flitch_id": None,
                "neck_subid": None,
                "brace_stock_flitch_id": None,
                "brace_stock_subid": None,
                "fretboard_flitch_id": None,
                "fretboard_subid": None,
                "bridge_flitch_id": None,
                "bridge_subid": None,
            },
            "as_built_dimensions": {
                "top_thickness_grid_mm": [[2.8, 2.9], [2.9, 3.0]],
                "back_thickness_grid_mm": None,
                "brace_dimensions": [
                    {
                        "name": "X_bass",
                        "height_mm": 8.0,
                        "width_mm": 6.0,
                        "length_mm": 240.0,
                        "scallop_depth_mm": None,
                        "taper_type": None,
                        "notes": "",
                    },
                ],
                "soundhole_diameter_mm": 102.0,
                "soundhole_position_mm": None,
                "body_depth_mm": None,
                "body_width_lower_bout_mm": None,
                "body_width_upper_bout_mm": None,
                "scale_length_mm": 650.0,
                "tornavoz_spec": None,
            },
            "measurements": {
                "modal_scans": ["session_001/ods.json"],
                "deflection_measurements": None,
                "tap_tone_measurements": None,
                "bending_measurements": None,
                "setup_measurements": None,
            },
            "predicted": {
                "T1_hz": 95.0,
                "A0_hz": 100.0,
                "T2_hz": None,
                "T3_hz": None,
                "bridge_deflection_mm_at_string_load": 0.8,
                "top_monopole_mobility": None,
                "prediction_session_path": None,
            },
            "measured_summary": {
                "T1_hz": 92.0,
                "A0_hz": 98.0,
                "T2_hz": None,
                "T3_hz": None,
                "bridge_deflection_mm": 0.75,
                "top_monopole_mobility": None,
                "measurement_date": "2026-06-20",
            },
            "residuals": None,
            "subjective": {
                "builder_notes": "Good build",
                "player_evaluations": [
                    {
                        "player_id": "Ross",
                        "date": "2026-06-20",
                        "engagement_minutes": 45.0,
                        "tone_rating": 8,
                        "playability_rating": 9,
                        "notes": "Great response",
                    },
                ],
            },
            "notes": "Test build",
        }

        b = build_from_dict(original)
        result = build_to_dict(b)

        # Core fields match
        assert result["build_id"] == original["build_id"]
        assert result["design_name"] == original["design_name"]
        assert result["wood"]["top_flitch_id"] == original["wood"]["top_flitch_id"]

        # Nested structures match
        assert result["as_built_dimensions"]["soundhole_diameter_mm"] == 102.0
        assert result["as_built_dimensions"]["brace_dimensions"][0]["height_mm"] == 8.0
        assert result["predicted"]["T1_hz"] == 95.0
        assert result["measured_summary"]["T1_hz"] == 92.0
        assert result["subjective"]["player_evaluations"][0]["tone_rating"] == 8
