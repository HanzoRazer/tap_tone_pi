# INSTRUMENT CLASS: MEASUREMENT
"""
comparison.py — Predicted-vs-measured mode shape comparison.

Bridges DO-001 (predicted mode shapes from Rayleigh-Ritz) with Phase 2 measurement
data (PointSpectrum from scripts/phase2/metrics.py) to compute spatial residuals
and agreement metrics.

Use case:
    Given a predicted (1,1) mode at 85 Hz and measured transfer function data
    from a 16-point Phase 2 scan, compute how well the predicted amplitude
    pattern matches the measured amplitudes at the mode frequency.

Key outputs:
    - Per-point amplitude residuals (predicted - measured, normalized)
    - Overall RMS amplitude residual
    - Phase consistency score (how coherent is the measured phase pattern)
    - Nodal line match score (do predicted zeros align with measured zeros)

Normalization convention:
    Both predicted and measured amplitudes are normalized so peak |amplitude| = 1.0
    before computing residuals. This makes residuals interpretable as fractions
    of peak amplitude.

Phase comparison:
    PointSpectrum includes phase_deg. We compute phase consistency as the circular
    variance of the phase values. A perfect standing wave has all points either
    in-phase or 180 deg out of phase (low phase disorder). Wolf tones and coupled
    modes show high phase disorder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from tap_tone_pi.design.mode_shape_render import RenderedModeShape


@dataclass(frozen=True)
class PointResidual:
    """Residual data for a single grid point.

    Attributes:
        point_id: Grid point identifier (e.g., "A1").
        predicted_amplitude_norm: Predicted amplitude, normalized to peak = 1.0.
        measured_amplitude_norm: Measured amplitude at mode freq, normalized.
        residual: measured - predicted (positive = measured > predicted).
        measured_phase_deg: Phase at mode frequency, in degrees.
        measured_coherence: Coherence at mode frequency.
        is_at_predicted_node: True if |predicted| < 0.1 (near a nodal line).
        is_at_measured_node: True if |measured| < 0.1.
    """

    point_id: str
    predicted_amplitude_norm: float
    measured_amplitude_norm: float
    residual: float
    measured_phase_deg: float
    measured_coherence: float
    is_at_predicted_node: bool
    is_at_measured_node: bool


@dataclass(frozen=True)
class ComparisonResult:
    """Result of comparing predicted vs measured mode shapes.

    Attributes:
        grid_id: Identifier for the measurement grid used.
        mode_label: Mode shape label, e.g., "(1,1)" or "(2,1)".
        predicted_freq_hz: Frequency from Rayleigh-Ritz solver.
        measured_freq_hz: Frequency bin used from measured data.
        freq_residual_hz: measured - predicted frequency.
        freq_residual_pct: Frequency residual as percentage of predicted.
        per_point_residuals: Dict mapping point_id to PointResidual.
        overall_rms_amplitude_residual: RMS of per-point amplitude residuals.
        overall_phase_consistency: Phase coherence score in [0, 1].
            1.0 = all points in-phase or exactly 180 deg out of phase.
            0.0 = random phase distribution.
        nodal_line_match: Agreement between predicted and measured nodal regions.
            1.0 = perfect match, 0.0 = no agreement.
            None if no predicted nodes exist.
        mean_coherence: Mean coherence across all points at mode freq.
        points_compared: Number of points with valid comparison data.
        points_skipped: Point IDs that were skipped (missing from one side).
    """

    grid_id: str
    mode_label: str
    predicted_freq_hz: float
    measured_freq_hz: float
    freq_residual_hz: float
    freq_residual_pct: float
    per_point_residuals: dict[str, PointResidual]
    overall_rms_amplitude_residual: float
    overall_phase_consistency: float
    nodal_line_match: Optional[float]
    mean_coherence: float
    points_compared: int
    points_skipped: list[str] = field(default_factory=list)


# Type alias for measured spectra from Phase 2
class PointSpectrumLike:
    """Protocol for PointSpectrum compatibility.

    Avoids hard import from scripts/phase2/metrics.py.
    Any object with these attributes works.
    """
    point_id: str
    x_mm: float
    y_mm: float
    freq_hz: NDArray[np.floating]
    H_mag: NDArray[np.floating]
    coherence: NDArray[np.floating]
    phase_deg: NDArray[np.floating]


def compare_mode(
    predicted_shape: RenderedModeShape,
    measured_spectra: dict[str, PointSpectrumLike],
    measured_freq_hz: Optional[float] = None,
    grid_id: str = "unknown",
    node_threshold: float = 0.1,
) -> ComparisonResult:
    """Compare a predicted mode shape against measured Phase 2 data.

    Args:
        predicted_shape: Output from render_mode_shape_on_grid() (DO-001).
        measured_spectra: Dict mapping point_id to PointSpectrum.
            All spectra must share the same frequency axis.
        measured_freq_hz: Frequency to extract from measured data.
            If None, uses the nearest bin to predicted_shape.frequency_Hz.
        grid_id: Identifier for the measurement grid (for traceability).
        node_threshold: Amplitude threshold for nodal line detection.
            Points with |amplitude| < threshold are considered at a node.

    Returns:
        ComparisonResult with per-point residuals and aggregate metrics.

    Raises:
        ValueError: If no spectra provided or frequency axes don't match.
    """
    if not measured_spectra:
        raise ValueError("No measured spectra provided")

    # Get frequency axis from first spectrum
    first_spectrum = next(iter(measured_spectra.values()))
    freq_axis = first_spectrum.freq_hz

    # Find frequency bin to use
    predicted_freq = predicted_shape.frequency_Hz
    target_freq = measured_freq_hz if measured_freq_hz is not None else predicted_freq
    bin_idx = _find_nearest_bin(freq_axis, target_freq)
    actual_measured_freq = float(freq_axis[bin_idx])

    # Frequency residual
    freq_residual_hz = actual_measured_freq - predicted_freq
    freq_residual_pct = (freq_residual_hz / predicted_freq * 100.0) if predicted_freq > 0 else 0.0

    # Extract measured amplitudes at the target frequency
    measured_amps: dict[str, float] = {}
    measured_phases: dict[str, float] = {}
    measured_coherences: dict[str, float] = {}
    skipped: list[str] = []

    predicted_ids = set(predicted_shape.amplitudes_by_id.keys())

    for point_id, spectrum in measured_spectra.items():
        if point_id not in predicted_ids:
            skipped.append(point_id)
            continue
        # Verify frequency axis matches
        if spectrum.freq_hz.shape != freq_axis.shape:
            skipped.append(point_id)
            continue
        measured_amps[point_id] = float(spectrum.H_mag[bin_idx])
        measured_phases[point_id] = float(spectrum.phase_deg[bin_idx])
        measured_coherences[point_id] = float(spectrum.coherence[bin_idx])

    # Also check for predicted points missing from measured
    for point_id in predicted_ids:
        if point_id not in measured_spectra and point_id not in skipped:
            skipped.append(point_id)

    # Normalize measured amplitudes to peak = 1.0
    if measured_amps:
        peak_measured = max(abs(v) for v in measured_amps.values())
        if peak_measured > 0:
            measured_amps_norm = {k: v / peak_measured for k, v in measured_amps.items()}
        else:
            measured_amps_norm = {k: 0.0 for k in measured_amps}
    else:
        measured_amps_norm = {}

    # Predicted amplitudes are already normalized by DO-001
    predicted_amps = predicted_shape.amplitudes_by_id

    # Compute per-point residuals
    per_point: dict[str, PointResidual] = {}
    residuals_list: list[float] = []

    for point_id in predicted_amps:
        if point_id not in measured_amps_norm:
            continue

        pred_amp = predicted_amps[point_id]
        meas_amp = measured_amps_norm[point_id]
        residual = meas_amp - pred_amp

        per_point[point_id] = PointResidual(
            point_id=point_id,
            predicted_amplitude_norm=pred_amp,
            measured_amplitude_norm=meas_amp,
            residual=residual,
            measured_phase_deg=measured_phases.get(point_id, 0.0),
            measured_coherence=measured_coherences.get(point_id, 0.0),
            is_at_predicted_node=abs(pred_amp) < node_threshold,
            is_at_measured_node=abs(meas_amp) < node_threshold,
        )
        residuals_list.append(residual)

    # Aggregate metrics
    if residuals_list:
        rms_residual = float(np.sqrt(np.mean(np.array(residuals_list) ** 2)))
    else:
        rms_residual = 0.0

    # Phase consistency: circular variance of phase values
    # For a standing wave, phases should cluster around two values 180 deg apart
    phase_values = [pr.measured_phase_deg for pr in per_point.values()]
    phase_consistency = _compute_phase_consistency(phase_values)

    # Nodal line match
    nodal_match = _compute_nodal_line_match(per_point, node_threshold)

    # Mean coherence
    coherence_values = [pr.measured_coherence for pr in per_point.values()]
    mean_coh = float(np.mean(coherence_values)) if coherence_values else 0.0

    # Mode label from indices
    m, n = predicted_shape.mode_indices
    mode_label = f"({m},{n})"

    return ComparisonResult(
        grid_id=grid_id,
        mode_label=mode_label,
        predicted_freq_hz=predicted_freq,
        measured_freq_hz=actual_measured_freq,
        freq_residual_hz=freq_residual_hz,
        freq_residual_pct=freq_residual_pct,
        per_point_residuals=per_point,
        overall_rms_amplitude_residual=rms_residual,
        overall_phase_consistency=phase_consistency,
        nodal_line_match=nodal_match,
        mean_coherence=mean_coh,
        points_compared=len(per_point),
        points_skipped=skipped,
    )


def compare_modes_batch(
    predicted_shapes: list[RenderedModeShape],
    measured_spectra: dict[str, PointSpectrumLike],
    measured_freqs_hz: Optional[list[float]] = None,
    grid_id: str = "unknown",
    node_threshold: float = 0.1,
) -> list[ComparisonResult]:
    """Compare multiple predicted modes against measured data.

    Convenience function that calls compare_mode() for each predicted shape.

    Args:
        predicted_shapes: List of RenderedModeShape from render_mode_shape_on_grid().
        measured_spectra: Dict mapping point_id to PointSpectrum.
        measured_freqs_hz: Optional list of frequencies to use for each mode.
            If None, uses predicted frequencies.
        grid_id: Identifier for the measurement grid.
        node_threshold: Amplitude threshold for nodal line detection.

    Returns:
        List of ComparisonResult, one per predicted shape.
    """
    results = []
    for i, shape in enumerate(predicted_shapes):
        meas_freq = measured_freqs_hz[i] if measured_freqs_hz else None
        result = compare_mode(
            predicted_shape=shape,
            measured_spectra=measured_spectra,
            measured_freq_hz=meas_freq,
            grid_id=grid_id,
            node_threshold=node_threshold,
        )
        results.append(result)
    return results


def _find_nearest_bin(freq_axis: NDArray[np.floating], target_hz: float) -> int:
    """Find index of frequency bin nearest to target."""
    return int(np.argmin(np.abs(freq_axis - target_hz)))


def _compute_phase_consistency(phases_deg: list[float]) -> float:
    """Compute phase consistency score for a standing wave.

    A perfect standing wave has all points either in-phase (0 deg) or
    anti-phase (180 deg). We measure how well the phases cluster around
    two values 180 deg apart.

    Returns:
        Score in [0, 1]. 1.0 = perfect standing wave, 0.0 = random phases.
    """
    if len(phases_deg) < 2:
        return 1.0  # trivially consistent

    # Convert to radians
    phases_rad = np.array(phases_deg) * (np.pi / 180.0)

    # For a standing wave, double the angles and check clustering
    # If phases are 0 or 180 deg, doubled phases are 0 or 360 deg (same point)
    doubled = 2.0 * phases_rad

    # Circular mean resultant length of doubled phases
    # R = 1 means all doubled phases point the same direction
    # (i.e., original phases were clustered at two points 180 deg apart)
    v = np.exp(1j * doubled)
    R = float(np.abs(np.mean(v)))

    return R


def _compute_nodal_line_match(
    per_point: dict[str, PointResidual],
    threshold: float,
) -> Optional[float]:
    """Compute agreement between predicted and measured nodal regions.

    Returns:
        Score in [0, 1], or None if no predicted nodes exist.
        1.0 = all predicted nodes are also measured nodes (and vice versa).
        0.0 = no agreement.
    """
    if not per_point:
        return None

    predicted_nodes = {p.point_id for p in per_point.values() if p.is_at_predicted_node}
    measured_nodes = {p.point_id for p in per_point.values() if p.is_at_measured_node}

    if not predicted_nodes:
        # No predicted nodal points — can't compute match
        return None

    # Jaccard similarity between predicted and measured node sets
    intersection = len(predicted_nodes & measured_nodes)
    union = len(predicted_nodes | measured_nodes)

    if union == 0:
        return 1.0  # both empty (shouldn't happen given the check above)

    return float(intersection / union)
