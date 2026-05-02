"""
Tests for tap_tone_pi.design.comparison — DO-002 acceptance criteria.

Test categories:
1. Basic functionality — compare_mode returns ComparisonResult
2. Perfect match — predicted == measured → zero residuals
3. Mode mismatch — predicted (1,1) vs measured (2,1) → high disagreement
4. Nodal line match — predicted nodes align with measured nodes
5. Phase consistency — standing wave vs disordered phase
6. Error handling — missing data, mismatched grids
"""

from dataclasses import dataclass
from typing import List

import numpy as np
import pytest

from tap_tone_pi.design.comparison import (
    ComparisonResult,
    PointResidual,
    compare_mode,
    compare_modes_batch,
    _compute_phase_consistency,
    _compute_nodal_line_match,
)
from tap_tone_pi.design.mode_shape_render import RenderedModeShape


# =============================================================================
# Test fixtures — synthetic PointSpectrum and RenderedModeShape
# =============================================================================


@dataclass
class MockPointSpectrum:
    """Mock PointSpectrum matching scripts/phase2/metrics.py interface."""
    point_id: str
    x_mm: float
    y_mm: float
    freq_hz: np.ndarray
    H_mag: np.ndarray
    coherence: np.ndarray
    phase_deg: np.ndarray


def make_freq_axis(n_bins: int = 100, fmax: float = 500.0) -> np.ndarray:
    """Create a frequency axis from 1 Hz to fmax Hz."""
    return np.linspace(1.0, fmax, n_bins, dtype=np.float32)


def make_mock_spectrum(
    point_id: str,
    freq_axis: np.ndarray,
    amplitude_at_mode: float,
    mode_freq_hz: float,
    phase_deg: float = 0.0,
    coherence: float = 0.95,
) -> MockPointSpectrum:
    """Create a mock spectrum with a peak at the mode frequency."""
    H_mag = np.zeros_like(freq_axis, dtype=np.float32)
    phase = np.zeros_like(freq_axis, dtype=np.float32)
    coh = np.ones_like(freq_axis, dtype=np.float32) * coherence

    # Put the amplitude at the bin nearest mode_freq
    bin_idx = int(np.argmin(np.abs(freq_axis - mode_freq_hz)))
    H_mag[bin_idx] = amplitude_at_mode
    phase[bin_idx] = phase_deg

    return MockPointSpectrum(
        point_id=point_id,
        x_mm=0.0,
        y_mm=0.0,
        freq_hz=freq_axis,
        H_mag=H_mag,
        coherence=coh,
        phase_deg=phase,
    )


def make_predicted_shape(
    amplitudes: dict[str, float],
    frequency_Hz: float = 85.0,
    mode_indices: tuple[int, int] = (1, 1),
) -> RenderedModeShape:
    """Create a synthetic RenderedModeShape."""
    return RenderedModeShape(
        mode_index=0,
        mode_indices=mode_indices,
        frequency_Hz=frequency_Hz,
        amplitudes_by_id=amplitudes,
        out_of_plate_ids=set(),
        peak_amplitude_raw=1.0,
        grid_origin_used="lower_bout_center",
        plate_dimensions_mm=(500.0, 380.0),
    )


# =============================================================================
# Test class: Basic functionality
# =============================================================================


class TestCompareBasic:
    """Basic compare_mode functionality."""

    def test_returns_comparison_result(self):
        """compare_mode returns a ComparisonResult dataclass."""
        freq_axis = make_freq_axis()
        predicted = make_predicted_shape({"A1": 1.0, "A2": 0.5})
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
            "A2": make_mock_spectrum("A2", freq_axis, 0.5, 85.0),
        }

        result = compare_mode(predicted, measured)

        assert isinstance(result, ComparisonResult)
        assert result.mode_label == "(1,1)"
        assert result.points_compared == 2

    def test_per_point_residuals_populated(self):
        """Per-point residuals are populated for each matched point."""
        freq_axis = make_freq_axis()
        predicted = make_predicted_shape({"A1": 1.0, "A2": 0.5, "A3": 0.3})
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
            "A2": make_mock_spectrum("A2", freq_axis, 0.5, 85.0),
            "A3": make_mock_spectrum("A3", freq_axis, 0.3, 85.0),
        }

        result = compare_mode(predicted, measured)

        assert len(result.per_point_residuals) == 3
        assert "A1" in result.per_point_residuals
        assert isinstance(result.per_point_residuals["A1"], PointResidual)

    def test_frequency_residual_computed(self):
        """Frequency residual is computed correctly."""
        freq_axis = make_freq_axis(n_bins=100, fmax=500.0)
        predicted = make_predicted_shape({"A1": 1.0}, frequency_Hz=85.0)
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 90.0),
        }

        # Use 90 Hz for measured
        result = compare_mode(predicted, measured, measured_freq_hz=90.0)

        # Nearest bin to 90 Hz
        expected_bin_freq = freq_axis[int(np.argmin(np.abs(freq_axis - 90.0)))]
        assert abs(result.measured_freq_hz - expected_bin_freq) < 0.1
        assert result.freq_residual_hz == pytest.approx(expected_bin_freq - 85.0, abs=0.1)


# =============================================================================
# Test class: Perfect match
# =============================================================================


class TestPerfectMatch:
    """Predicted == measured should give zero residuals."""

    def test_identical_amplitudes_zero_residual(self):
        """When predicted exactly matches measured, RMS residual is zero."""
        freq_axis = make_freq_axis()
        # Both normalized to peak = 1.0
        predicted = make_predicted_shape({"A1": 1.0, "A2": 0.5, "A3": -0.5, "A4": -1.0})
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
            "A2": make_mock_spectrum("A2", freq_axis, 0.5, 85.0),
            "A3": make_mock_spectrum("A3", freq_axis, 0.5, 85.0),  # sign not preserved in H_mag
            "A4": make_mock_spectrum("A4", freq_axis, 1.0, 85.0),
        }

        result = compare_mode(predicted, measured)

        # Residuals may not be exactly zero because measured doesn't preserve sign
        # but the magnitudes should match after normalization
        # For this test, let's use same-sign values
        predicted2 = make_predicted_shape({"A1": 1.0, "A2": 0.5})
        measured2 = {
            "A1": make_mock_spectrum("A1", freq_axis, 2.0, 85.0),  # will normalize to 1.0
            "A2": make_mock_spectrum("A2", freq_axis, 1.0, 85.0),  # will normalize to 0.5
        }

        result2 = compare_mode(predicted2, measured2)
        assert result2.overall_rms_amplitude_residual == pytest.approx(0.0, abs=0.01)

    def test_scaled_measured_normalizes_correctly(self):
        """Measured amplitudes are normalized before comparison."""
        freq_axis = make_freq_axis()
        predicted = make_predicted_shape({"A1": 1.0, "A2": 0.5})

        # Measured values are 10x larger but same ratio
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 10.0, 85.0),
            "A2": make_mock_spectrum("A2", freq_axis, 5.0, 85.0),
        }

        result = compare_mode(predicted, measured)

        # After normalization, should match
        assert result.overall_rms_amplitude_residual == pytest.approx(0.0, abs=0.01)


# =============================================================================
# Test class: Mode mismatch
# =============================================================================


class TestModeMismatch:
    """Predicted (1,1) vs measured (2,1) should show high disagreement."""

    def test_different_mode_shapes_high_residual(self):
        """Comparing (1,1) prediction to (2,1) measurement gives high residual."""
        freq_axis = make_freq_axis()

        # (1,1) mode: all positive, center is highest
        predicted_11 = make_predicted_shape(
            {"A1": 0.5, "A2": 1.0, "A3": 0.5, "B1": 0.3, "B2": 0.7, "B3": 0.3},
            mode_indices=(1, 1),
        )

        # (2,1) mode pattern: sign flip across midline
        # Simulate with left side positive, right side "negative" (but H_mag is positive)
        # We'll use different magnitudes to create disagreement
        measured_21 = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),  # left high
            "A2": make_mock_spectrum("A2", freq_axis, 0.1, 85.0),  # center low (node)
            "A3": make_mock_spectrum("A3", freq_axis, 1.0, 85.0),  # right high
            "B1": make_mock_spectrum("B1", freq_axis, 0.8, 85.0),
            "B2": make_mock_spectrum("B2", freq_axis, 0.1, 85.0),  # center low
            "B3": make_mock_spectrum("B3", freq_axis, 0.8, 85.0),
        }

        result = compare_mode(predicted_11, measured_21)

        # (1,1) has center high; (2,1) pattern has center low → significant residual
        assert result.overall_rms_amplitude_residual > 0.3

    def test_opposite_pattern_detected(self):
        """Inversely correlated patterns should have large residuals."""
        freq_axis = make_freq_axis()

        # Predicted: center high
        predicted = make_predicted_shape({"A": 0.2, "B": 1.0, "C": 0.2})

        # Measured: center low (opposite pattern)
        measured = {
            "A": make_mock_spectrum("A", freq_axis, 1.0, 85.0),
            "B": make_mock_spectrum("B", freq_axis, 0.2, 85.0),
            "C": make_mock_spectrum("C", freq_axis, 1.0, 85.0),
        }

        result = compare_mode(predicted, measured)

        # Large disagreement expected
        assert result.overall_rms_amplitude_residual > 0.5


# =============================================================================
# Test class: Nodal line match
# =============================================================================


class TestNodalLineMatch:
    """Nodal line agreement scoring."""

    def test_matching_nodes_high_score(self):
        """Predicted nodes aligning with measured nodes → high score."""
        freq_axis = make_freq_axis()

        # Predicted has node at B2 (amplitude near zero)
        predicted = make_predicted_shape({
            "A1": 1.0, "A2": 0.5,
            "B1": 0.5, "B2": 0.05,  # node
            "C1": 0.5, "C2": 1.0,
        })

        # Measured also has node at B2
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
            "A2": make_mock_spectrum("A2", freq_axis, 0.5, 85.0),
            "B1": make_mock_spectrum("B1", freq_axis, 0.5, 85.0),
            "B2": make_mock_spectrum("B2", freq_axis, 0.05, 85.0),  # node
            "C1": make_mock_spectrum("C1", freq_axis, 0.5, 85.0),
            "C2": make_mock_spectrum("C2", freq_axis, 1.0, 85.0),
        }

        result = compare_mode(predicted, measured)

        assert result.nodal_line_match is not None
        assert result.nodal_line_match > 0.8  # high agreement

    def test_mismatched_nodes_low_score(self):
        """Predicted nodes not aligning with measured → low score."""
        freq_axis = make_freq_axis()

        # Predicted has node at B2
        predicted = make_predicted_shape({
            "A1": 1.0, "B2": 0.05,  # node at B2
        })

        # Measured has node at A1 instead
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 0.05, 85.0),  # node
            "B2": make_mock_spectrum("B2", freq_axis, 1.0, 85.0),  # antinode
        }

        result = compare_mode(predicted, measured)

        assert result.nodal_line_match is not None
        assert result.nodal_line_match < 0.5  # low agreement

    def test_no_predicted_nodes_returns_none(self):
        """If no predicted nodal points, nodal_line_match is None."""
        freq_axis = make_freq_axis()

        # All predicted amplitudes well above threshold
        predicted = make_predicted_shape({"A1": 1.0, "A2": 0.8, "A3": 0.6})
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
            "A2": make_mock_spectrum("A2", freq_axis, 0.8, 85.0),
            "A3": make_mock_spectrum("A3", freq_axis, 0.6, 85.0),
        }

        result = compare_mode(predicted, measured)

        assert result.nodal_line_match is None


# =============================================================================
# Test class: Phase consistency
# =============================================================================


class TestPhaseConsistency:
    """Phase coherence scoring for standing waves."""

    def test_in_phase_high_consistency(self):
        """All points in-phase → high consistency score."""
        phases = [0.0, 0.0, 0.0, 0.0]
        consistency = _compute_phase_consistency(phases)
        assert consistency > 0.95

    def test_antiphase_high_consistency(self):
        """Points at 0 and 180 deg (standing wave) → high consistency."""
        phases = [0.0, 180.0, 0.0, 180.0]
        consistency = _compute_phase_consistency(phases)
        assert consistency > 0.95

    def test_random_phases_low_consistency(self):
        """Random phase distribution → low consistency."""
        phases = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
        consistency = _compute_phase_consistency(phases)
        assert consistency < 0.3

    def test_single_point_trivially_consistent(self):
        """Single point is trivially consistent."""
        consistency = _compute_phase_consistency([45.0])
        assert consistency == 1.0

    def test_phase_consistency_in_result(self):
        """Phase consistency is computed and included in result."""
        freq_axis = make_freq_axis()
        predicted = make_predicted_shape({"A1": 1.0, "A2": 0.5})
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0, phase_deg=0.0),
            "A2": make_mock_spectrum("A2", freq_axis, 0.5, 85.0, phase_deg=180.0),
        }

        result = compare_mode(predicted, measured)

        assert 0.0 <= result.overall_phase_consistency <= 1.0


# =============================================================================
# Test class: Error handling
# =============================================================================


class TestErrorHandling:
    """Edge cases and error conditions."""

    def test_empty_spectra_raises(self):
        """Empty measured_spectra raises ValueError."""
        predicted = make_predicted_shape({"A1": 1.0})

        with pytest.raises(ValueError, match="No measured spectra"):
            compare_mode(predicted, {})

    def test_missing_points_tracked(self):
        """Points in predicted but not measured are tracked."""
        freq_axis = make_freq_axis()
        predicted = make_predicted_shape({"A1": 1.0, "A2": 0.5, "A3": 0.3})
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
            # A2 and A3 missing
        }

        result = compare_mode(predicted, measured)

        assert result.points_compared == 1
        assert "A2" in result.points_skipped
        assert "A3" in result.points_skipped

    def test_extra_measured_points_skipped(self):
        """Points in measured but not predicted are skipped."""
        freq_axis = make_freq_axis()
        predicted = make_predicted_shape({"A1": 1.0})
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
            "B1": make_mock_spectrum("B1", freq_axis, 0.5, 85.0),  # not in predicted
        }

        result = compare_mode(predicted, measured)

        assert result.points_compared == 1
        assert "B1" in result.points_skipped


# =============================================================================
# Test class: Batch comparison
# =============================================================================


class TestBatchComparison:
    """compare_modes_batch functionality."""

    def test_batch_returns_list_of_results(self):
        """Batch comparison returns one result per predicted shape."""
        freq_axis = make_freq_axis()
        shapes = [
            make_predicted_shape({"A1": 1.0}, frequency_Hz=85.0, mode_indices=(1, 1)),
            make_predicted_shape({"A1": 0.5}, frequency_Hz=150.0, mode_indices=(2, 1)),
        ]
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 85.0),
        }

        results = compare_modes_batch(shapes, measured)

        assert len(results) == 2
        assert results[0].mode_label == "(1,1)"
        assert results[1].mode_label == "(2,1)"

    def test_batch_with_custom_freqs(self):
        """Batch can use custom measured frequencies per mode."""
        freq_axis = make_freq_axis()
        shapes = [
            make_predicted_shape({"A1": 1.0}, frequency_Hz=85.0),
            make_predicted_shape({"A1": 1.0}, frequency_Hz=150.0),
        ]
        measured = {
            "A1": make_mock_spectrum("A1", freq_axis, 1.0, 90.0),
        }

        results = compare_modes_batch(shapes, measured, measured_freqs_hz=[90.0, 155.0])

        # Both should use the specified frequencies
        assert abs(results[0].measured_freq_hz - 90.0) < 5.0
        assert abs(results[1].measured_freq_hz - 155.0) < 5.0
