"""Tests for Chladni eigenfunction computation."""
import numpy as np
import pytest

from modes.chladni.eigenfunctions import (
    PlateParams,
    compute_simply_supported_mode,
    compute_center_constrained_nodal,
    extract_nodal_contour,
    compute_mode,
)


class TestPlateParams:
    """Tests for physical plate parameter calculations."""

    def test_flexural_rigidity_aluminum(self):
        """Verify flexural rigidity formula for aluminum plate."""
        params = PlateParams(
            thickness_m=0.003,
            youngs_modulus_pa=70e9,
            poissons_ratio=0.33
        )
        D = params.flexural_rigidity
        # D = Eh³/12(1-ν²) = 70e9 * 0.003³ / 12(1-0.33²)
        expected = (70e9 * 0.003**3) / (12 * (1 - 0.33**2))
        assert abs(D - expected) < 1e-6

    def test_eigenfrequency_fundamental(self):
        """Verify eigenfrequency for (1,1) mode."""
        params = PlateParams(length_m=0.3, thickness_m=0.003)
        f11 = params.eigenfrequency_hz(1, 1)
        # Should be positive and in reasonable range
        assert f11 > 0
        assert f11 < 10000  # Sanity check

    def test_eigenfrequency_ordering(self):
        """Higher modes should have higher frequencies."""
        params = PlateParams()
        f11 = params.eigenfrequency_hz(1, 1)
        f12 = params.eigenfrequency_hz(1, 2)
        f22 = params.eigenfrequency_hz(2, 2)
        f23 = params.eigenfrequency_hz(2, 3)

        assert f11 < f12 < f22 < f23

    def test_eigenfrequency_symmetry(self):
        """f(m,n) == f(n,m) for symmetric plate."""
        params = PlateParams()
        assert params.eigenfrequency_hz(2, 3) == params.eigenfrequency_hz(3, 2)


class TestSimplySupportedMode:
    """Tests for simply supported plate eigenfunctions."""

    def test_mode_shape_basic(self):
        """Verify basic mode shape computation."""
        phi = compute_simply_supported_mode(1, 1, grid_size=64)
        assert phi.shape == (64, 64)

    def test_mode_normalized(self):
        """Output should be normalized to [-1, 1]."""
        phi = compute_simply_supported_mode(2, 3, grid_size=128)
        assert np.abs(phi).max() <= 1.0 + 1e-10

    def test_mode_boundary_zeros(self):
        """Edges should be zero for simply supported BC."""
        phi = compute_simply_supported_mode(1, 1, grid_size=100)
        # First and last rows/columns should be near zero
        assert np.allclose(phi[0, :], 0, atol=1e-10)
        assert np.allclose(phi[-1, :], 0, atol=1e-10)
        assert np.allclose(phi[:, 0], 0, atol=1e-10)
        assert np.allclose(phi[:, -1], 0, atol=1e-10)

    def test_mode_11_center_max(self):
        """Mode (1,1) should have maximum at center."""
        phi = compute_simply_supported_mode(1, 1, grid_size=101)
        center = phi[50, 50]
        assert abs(center - 1.0) < 0.01  # Should be max

    def test_mode_12_nodal_line(self):
        """Mode (1,2) should have horizontal nodal line at y=0.5."""
        phi = compute_simply_supported_mode(1, 2, grid_size=101)
        # Middle row should be near zero
        middle_row = phi[50, :]
        assert np.allclose(middle_row, 0, atol=0.05)

    def test_invalid_mode_raises(self):
        """Mode numbers < 1 should raise ValueError."""
        with pytest.raises(ValueError):
            compute_simply_supported_mode(0, 1)
        with pytest.raises(ValueError):
            compute_simply_supported_mode(1, -1)


class TestCenterConstrainedMode:
    """Tests for center-constrained plate interference patterns."""

    def test_interference_shape(self):
        """Verify basic computation."""
        phi = compute_center_constrained_nodal(2, 3, grid_size=64)
        assert phi.shape == (64, 64)

    def test_center_zero_when_m_equals_n(self):
        """When m==n, entire field should be zero."""
        phi = compute_center_constrained_nodal(2, 2, grid_size=64)
        assert np.allclose(phi, 0, atol=1e-10)

    def test_antisymmetry(self):
        """Pattern should have specific symmetry properties."""
        phi = compute_center_constrained_nodal(2, 3, grid_size=65)
        # Check antisymmetry under (m,n) swap
        phi_swap = compute_center_constrained_nodal(3, 2, grid_size=65)
        assert np.allclose(phi, -phi_swap, atol=1e-10)


class TestNodalContour:
    """Tests for nodal line extraction."""

    def test_contour_binary(self):
        """Output should be boolean mask."""
        phi = compute_simply_supported_mode(2, 2, grid_size=64)
        nodal = extract_nodal_contour(phi, threshold=0.1)
        assert nodal.dtype == bool

    def test_contour_threshold(self):
        """Higher threshold should include more points."""
        phi = compute_simply_supported_mode(2, 2, grid_size=64)
        nodal_tight = extract_nodal_contour(phi, threshold=0.01)
        nodal_loose = extract_nodal_contour(phi, threshold=0.1)
        assert nodal_tight.sum() < nodal_loose.sum()


class TestComputeMode:
    """Tests for high-level mode computation."""

    def test_simply_supported_result(self):
        """Verify result structure for simply supported."""
        result = compute_mode(2, 3, boundary="simply_supported", grid_size=64)
        assert result.m == 2
        assert result.n == 3
        assert result.boundary_condition == "simply_supported"
        assert result.displacement.shape == (64, 64)

    def test_frequency_computed_with_params(self):
        """Frequency should be computed when params provided."""
        params = PlateParams()
        result = compute_mode(
            2, 3,
            boundary="simply_supported",
            plate_params=params
        )
        assert result.frequency_hz is not None
        assert result.frequency_hz > 0

    def test_center_constrained_no_frequency(self):
        """Center constrained doesn't compute eigenfrequency."""
        params = PlateParams()
        result = compute_mode(
            2, 3,
            boundary="center_constrained",
            plate_params=params
        )
        assert result.frequency_hz is None

    def test_to_json_dict(self):
        """JSON dict should exclude displacement array."""
        result = compute_mode(1, 2, grid_size=32)
        d = result.to_json_dict()
        assert 'displacement' not in d
        assert d['m'] == 1
        assert d['n'] == 2
        assert d['shape'] == [32, 32]
