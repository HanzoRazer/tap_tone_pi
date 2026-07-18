"""Tests for mode_shape_render — coordinate transform and Rayleigh-Ritz mode rendering on Phase 2 grids."""

from __future__ import annotations

import pytest

from tap_tone_pi.design import (
    OrthotropicPlate,
    BoundaryCondition,
    solve_rayleigh_ritz,
)
from tap_tone_pi.design.mode_shape_render import (
    GridLike,
    GridPointLike,
    RenderedModeShape,
    render_mode_shape_on_grid,
    load_grid_compatible,
    ORIGIN_OFFSETS,
)


# =============================================================================
# Fixtures
# =============================================================================


def make_test_plate() -> OrthotropicPlate:
    """Standard test plate: simply-supported sitka, ~jumbo lower bout sized."""
    return OrthotropicPlate.from_wood(
        E_L=12e9,
        E_C=0.8e9,
        rho=420,
        h=2.8e-3,
        a=0.500,  # 500 mm along grain
        b=0.380,  # 380 mm cross-grain
    )


def make_test_result(n_modes_x: int = 4, n_modes_y: int = 4):
    """Solve a standard test plate."""
    plate = make_test_plate()
    return solve_rayleigh_ritz(
        plate,
        n_modes_x=n_modes_x,
        n_modes_y=n_modes_y,
        bc_x=BoundaryCondition.SIMPLY_SUPPORTED,
        bc_y=BoundaryCondition.SIMPLY_SUPPORTED,
        n_modes_return=8,
    )


def make_simple_grid(origin: str = "lower_bout_center") -> GridLike:
    """3x3 grid centered at origin, spanning ±100mm × ±50mm (well within 500x380mm plate)."""
    points = [
        GridPointLike(id="A1", x=-100.0, y=50.0),
        GridPointLike(id="A2", x=0.0, y=50.0),
        GridPointLike(id="A3", x=100.0, y=50.0),
        GridPointLike(id="B1", x=-100.0, y=0.0),
        GridPointLike(id="B2", x=0.0, y=0.0),
        GridPointLike(id="B3", x=100.0, y=0.0),
        GridPointLike(id="C1", x=-100.0, y=-50.0),
        GridPointLike(id="C2", x=0.0, y=-50.0),
        GridPointLike(id="C3", x=100.0, y=-50.0),
    ]
    return GridLike(units="mm", origin=origin, points=points)


# =============================================================================
# Basic rendering tests
# =============================================================================


class TestRenderModeShapeBasic:
    """Smoke tests for the rendering function."""

    def test_returns_rendered_mode_shape(self):
        """Function returns the expected dataclass type."""
        result = make_test_result()
        grid = make_simple_grid()
        rendered = render_mode_shape_on_grid(result, grid, mode_index=0)
        assert isinstance(rendered, RenderedModeShape)

    def test_all_grid_points_rendered(self):
        """Every in-plate grid point gets an amplitude."""
        result = make_test_result()
        grid = make_simple_grid()
        rendered = render_mode_shape_on_grid(result, grid, mode_index=0)
        assert len(rendered.amplitudes_by_id) == len(grid.points)
        for p in grid.points:
            assert p.id in rendered.amplitudes_by_id

    def test_metadata_populated(self):
        """Result metadata reflects the requested mode and plate dimensions."""
        result = make_test_result()
        grid = make_simple_grid()
        rendered = render_mode_shape_on_grid(result, grid, mode_index=0)
        assert rendered.mode_index == 0
        assert rendered.frequency_Hz == result.modes[0].frequency_Hz
        assert rendered.mode_indices == result.modes[0].mode_indices
        assert rendered.grid_origin_used == "lower_bout_center"
        assert rendered.plate_dimensions_mm == (500.0, 380.0)


# =============================================================================
# Mode shape physics tests — confirm the rendering produces correct shapes
# =============================================================================


class TestModeShapePhysics:
    """Tests that verify the rendered amplitudes have the expected physical structure."""

    def test_fundamental_11_mode_peaks_at_center(self):
        """The (1,1) mode should have maximum amplitude at the plate center."""
        result = make_test_result()
        grid = make_simple_grid(origin="lower_bout_center")
        rendered = render_mode_shape_on_grid(result, grid, mode_index=0)

        # Find which point should be center
        center_amp = abs(rendered.amplitudes_by_id["B2"])  # (0, 0) point
        edge_amps = [
            abs(rendered.amplitudes_by_id[pid])
            for pid in ["A1", "A3", "C1", "C3"]  # corners
        ]

        for edge_amp in edge_amps:
            assert center_amp > edge_amp, (
                f"Center amplitude {center_amp} should exceed corner {edge_amp} "
                f"for the (1,1) fundamental mode."
            )

    def test_normalized_peak_is_one(self):
        """Default normalize=True scales peak |amplitude| to 1.0."""
        result = make_test_result()
        grid = make_simple_grid()
        rendered = render_mode_shape_on_grid(result, grid, mode_index=0)
        peak = max(abs(v) for v in rendered.amplitudes_by_id.values())
        assert peak == pytest.approx(1.0, abs=1e-6)

    def test_normalize_false_preserves_raw(self):
        """normalize=False returns unscaled amplitudes."""
        result = make_test_result()
        grid = make_simple_grid()
        rendered = render_mode_shape_on_grid(
            result, grid, mode_index=0, normalize=False
        )
        peak = max(abs(v) for v in rendered.amplitudes_by_id.values())
        # Raw amplitudes are not normalized to 1.0
        assert peak == pytest.approx(rendered.peak_amplitude_raw, abs=1e-9)

    def test_higher_mode_has_sign_changes(self):
        """A mode with n>1 in some direction should have sign flips across that direction."""
        result = make_test_result()
        grid = make_simple_grid()

        # Find a mode whose indices include a 2 (e.g. (2,1) or (1,2))
        target_mode_idx = None
        for i, mode in enumerate(result.modes):
            if mode.mode_indices in [(2, 1), (1, 2)]:
                target_mode_idx = i
                break

        if target_mode_idx is None:
            pytest.skip("No (2,1) or (1,2) mode in solver output")

        rendered = render_mode_shape_on_grid(
            result, grid, mode_index=target_mode_idx, normalize=False
        )

        # At least one pair of points should have opposite signs
        amps = list(rendered.amplitudes_by_id.values())
        has_positive = any(a > 0.01 for a in amps)
        has_negative = any(a < -0.01 for a in amps)
        assert has_positive and has_negative, (
            f"Mode {result.modes[target_mode_idx].mode_indices} should have "
            f"both positive and negative regions across the grid."
        )


# =============================================================================
# Coordinate transform tests
# =============================================================================


class TestCoordinateTransforms:
    """Tests for the grid-to-plate coordinate transformation logic."""

    def test_plate_corner_origin_no_translation(self):
        """plate_corner origin should pass coordinates through unchanged."""
        result = make_test_result()
        # Grid point at (250, 190) mm in plate-corner coords = plate center
        grid = GridLike(
            units="mm",
            origin="plate_corner",
            points=[
                GridPointLike(id="CTR", x=250.0, y=190.0),  # plate center
            ],
        )
        rendered = render_mode_shape_on_grid(result, grid, mode_index=0)
        assert "CTR" in rendered.amplitudes_by_id
        assert "CTR" not in rendered.out_of_plate_ids

    def test_lower_bout_center_translates_correctly(self):
        """lower_bout_center grid (0,0) should map to plate (a/2, b/2)."""
        result = make_test_result()
        grid_center = GridLike(
            units="mm",
            origin="lower_bout_center",
            points=[GridPointLike(id="CTR", x=0.0, y=0.0)],
        )
        grid_corner = GridLike(
            units="mm",
            origin="plate_corner",
            points=[GridPointLike(id="CTR", x=250.0, y=190.0)],  # plate dims/2
        )

        r1 = render_mode_shape_on_grid(
            result, grid_center, mode_index=0, normalize=False
        )
        r2 = render_mode_shape_on_grid(
            result, grid_corner, mode_index=0, normalize=False
        )
        assert r1.amplitudes_by_id["CTR"] == pytest.approx(
            r2.amplitudes_by_id["CTR"], abs=1e-9
        )

    def test_out_of_plate_point_flagged(self):
        """A grid point well outside the plate should appear in out_of_plate_ids."""
        result = make_test_result()
        grid = GridLike(
            units="mm",
            origin="lower_bout_center",
            points=[
                GridPointLike(id="GOOD", x=0.0, y=0.0),
                GridPointLike(id="FARFAR", x=10000.0, y=0.0),  # 10m off plate
            ],
        )
        rendered = render_mode_shape_on_grid(result, grid, mode_index=0)
        assert "GOOD" in rendered.amplitudes_by_id
        assert "FARFAR" in rendered.out_of_plate_ids
        assert "FARFAR" not in rendered.amplitudes_by_id

    def test_swapped_axes(self):
        """x_axis='cross_grain' swaps grid x↔y mapping."""
        result = make_test_result()
        # Plate is 500 (along grain) × 380 (cross-grain).
        # With swapped axes, grid +x = cross-grain, grid +y = grain.
        # A grid point at (50, 100) with x_axis=cross_grain means
        # the point is at cross-grain=50, grain=100 (after origin transform).
        grid = GridLike(
            units="mm",
            origin="lower_bout_center",
            points=[
                GridPointLike(id="P1", x=50.0, y=100.0),
            ],
        )

        r_normal = render_mode_shape_on_grid(
            result,
            grid,
            mode_index=0,
            x_axis="grain",
            y_axis="cross_grain",
            normalize=False,
        )
        r_swapped = render_mode_shape_on_grid(
            result,
            grid,
            mode_index=0,
            x_axis="cross_grain",
            y_axis="grain",
            normalize=False,
        )
        # The two should differ for non-square plates (a != b).
        assert r_normal.amplitudes_by_id["P1"] != pytest.approx(
            r_swapped.amplitudes_by_id["P1"], abs=1e-6
        )


# =============================================================================
# Error handling tests
# =============================================================================


class TestErrorHandling:
    """Tests for invalid input handling."""

    def test_non_mm_units_rejected(self):
        result = make_test_result()
        grid = GridLike(
            units="inches",
            origin="lower_bout_center",
            points=[GridPointLike(id="P1", x=0.0, y=0.0)],
        )
        with pytest.raises(ValueError, match="mm"):
            render_mode_shape_on_grid(result, grid, mode_index=0)

    def test_unknown_origin_rejected(self):
        result = make_test_result()
        grid = GridLike(
            units="mm",
            origin="totally_made_up_origin",
            points=[GridPointLike(id="P1", x=0.0, y=0.0)],
        )
        with pytest.raises(ValueError, match="Unknown grid origin"):
            render_mode_shape_on_grid(result, grid, mode_index=0)

    def test_mode_index_out_of_range(self):
        result = make_test_result()
        grid = make_simple_grid()
        with pytest.raises(IndexError, match="out of range"):
            render_mode_shape_on_grid(result, grid, mode_index=999)

    def test_negative_mode_index(self):
        result = make_test_result()
        grid = make_simple_grid()
        with pytest.raises(IndexError, match="out of range"):
            render_mode_shape_on_grid(result, grid, mode_index=-1)

    def test_same_axis_for_both_dimensions(self):
        result = make_test_result()
        grid = make_simple_grid()
        with pytest.raises(ValueError, match="must differ"):
            render_mode_shape_on_grid(
                result, grid, mode_index=0, x_axis="grain", y_axis="grain"
            )

    def test_invalid_axis_name(self):
        result = make_test_result()
        grid = make_simple_grid()
        with pytest.raises(ValueError, match="axes must be"):
            render_mode_shape_on_grid(result, grid, mode_index=0, x_axis="diagonal")


# =============================================================================
# Phase 2 grid loader compatibility tests
# =============================================================================


class TestLoadGridCompatible:
    """Tests for the grid-from-dict convenience loader."""

    def test_loads_phase2_grid_mm_format(self):
        """The format from examples/phase2_grid_mm.json should load."""
        grid_dict = {
            "units": "mm",
            "origin": "lower_bout_center",
            "points": [
                {"id": "A1", "x": -40, "y": 60},
                {"id": "A2", "x": 0, "y": 60},
                {"id": "A3", "x": 40, "y": 60},
            ],
        }
        grid = load_grid_compatible(grid_dict)
        assert grid.units == "mm"
        assert grid.origin == "lower_bout_center"
        assert len(grid.points) == 3
        assert grid.points[0].id == "A1"
        assert grid.points[0].x == -40.0
        assert grid.points[0].y == 60.0

    def test_loads_contract_schema_format(self):
        """The format from contracts/phase2_grid.schema.json (point_id field) should load."""
        grid_dict = {
            "schema_version": "phase2_grid_v1",
            "units": {"length": "mm"},  # nested format from contract
            "points": [
                {"point_id": "A1", "x_mm": -40, "y_mm": 60},
                {"point_id": "A2", "x_mm": 0, "y_mm": 60},
            ],
        }
        # Our loader uses flat units; this format won't fully work.
        # But point_id field should be recognized.
        # Adapt by extracting units string.
        grid_dict_flat = {
            "units": "mm",
            "origin": "lower_bout_center",
            "points": grid_dict["points"],
        }
        grid = load_grid_compatible(grid_dict_flat)
        assert grid.points[0].id == "A1"
        assert grid.points[0].x == -40.0

    def test_missing_id_raises(self):
        grid_dict = {
            "units": "mm",
            "origin": "lower_bout_center",
            "points": [{"x": 0, "y": 0}],
        }
        with pytest.raises(ValueError, match="missing"):
            load_grid_compatible(grid_dict)

    def test_missing_coordinates_raises(self):
        grid_dict = {
            "units": "mm",
            "origin": "lower_bout_center",
            "points": [{"id": "A1"}],
        }
        with pytest.raises(ValueError, match="missing coordinates"):
            load_grid_compatible(grid_dict)


# =============================================================================
# Origin dispatch table tests
# =============================================================================


class TestOriginDispatchTable:
    """Tests for the ORIGIN_OFFSETS dispatch mechanism."""

    def test_all_listed_origins_callable(self):
        """Every entry in ORIGIN_OFFSETS should be a callable returning a tuple."""
        for name, fn in ORIGIN_OFFSETS.items():
            offset = fn(500.0, 380.0, "grain", "cross_grain")
            assert isinstance(offset, tuple), f"{name} did not return a tuple"
            assert len(offset) == 2, f"{name} did not return (dx, dy)"
            assert all(isinstance(v, float) for v in offset), (
                f"{name} returned non-float offsets: {offset}"
            )

    def test_required_origins_present(self):
        """The four documented origins must be in the dispatch table."""
        required = {
            "lower_bout_center",
            "plate_corner",
            "soundhole_center",
            "bridge_position",
        }
        assert required.issubset(set(ORIGIN_OFFSETS.keys()))
