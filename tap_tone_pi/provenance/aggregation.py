# INSTRUMENT CLASS: MEASUREMENT
"""Measurement set aggregation helpers (Dev Order 89).

Pure functions for collecting and summarizing measurements.
These are deterministic aggregations — no quality judgment.

Aggregation computes counts, means, standard deviations.
It does not evaluate quality, success, or recommend actions.
"""

from __future__ import annotations

import math
from typing import Sequence

from tap_tone_pi.provenance.measurement_links import MeasurementLineageV1
from tap_tone_pi.provenance.measurement_set import (
    MeasurementSetV1,
    MeasurementSetSummaryV1,
)


def collect_measurements_for_campaign(
    lineages: Sequence[MeasurementLineageV1],
    campaign_id: str,
    *,
    measurement_set_id: str | None = None,
) -> MeasurementSetV1:
    """Collect all measurements belonging to a campaign.

    Args:
        lineages: Sequence of measurement lineages to search
        campaign_id: The campaign ID to filter by
        measurement_set_id: Optional set ID (defaults to "campaign_{campaign_id}")

    Returns:
        MeasurementSetV1 containing matching measurement IDs
    """
    matching_ids = tuple(
        lineage.measurement_id
        for lineage in lineages
        if lineage.campaign_id == campaign_id
    )

    return MeasurementSetV1(
        measurement_set_id=measurement_set_id or f"campaign_{campaign_id}",
        campaign_id=campaign_id,
        measurement_ids=matching_ids,
    )


def collect_measurements_for_revision(
    lineages: Sequence[MeasurementLineageV1],
    revision_id: str,
    *,
    measurement_set_id: str | None = None,
) -> MeasurementSetV1:
    """Collect all measurements belonging to a revision.

    Args:
        lineages: Sequence of measurement lineages to search
        revision_id: The revision ID to filter by
        measurement_set_id: Optional set ID (defaults to "revision_{revision_id}")

    Returns:
        MeasurementSetV1 containing matching measurement IDs
    """
    matching_ids = tuple(
        lineage.measurement_id
        for lineage in lineages
        if lineage.revision_id == revision_id
    )

    # Also capture campaign_id from the first matching lineage
    campaign_id = None
    for lineage in lineages:
        if lineage.revision_id == revision_id and lineage.campaign_id:
            campaign_id = lineage.campaign_id
            break

    return MeasurementSetV1(
        measurement_set_id=measurement_set_id or f"revision_{revision_id}",
        campaign_id=campaign_id,
        revision_id=revision_id,
        measurement_ids=matching_ids,
    )


def collect_measurements_for_workflow(
    lineages: Sequence[MeasurementLineageV1],
    workflow_id: str,
    *,
    measurement_set_id: str | None = None,
) -> MeasurementSetV1:
    """Collect all measurements produced by a workflow.

    Args:
        lineages: Sequence of measurement lineages to search
        workflow_id: The workflow ID to filter by
        measurement_set_id: Optional set ID (defaults to "workflow_{workflow_id}")

    Returns:
        MeasurementSetV1 containing matching measurement IDs
    """
    matching_ids = tuple(
        lineage.measurement_id
        for lineage in lineages
        if lineage.workflow_id == workflow_id
    )

    return MeasurementSetV1(
        measurement_set_id=measurement_set_id or f"workflow_{workflow_id}",
        workflow_id=workflow_id,
        measurement_ids=matching_ids,
    )


def _compute_stats(values: Sequence[float]) -> tuple[float, float, float, float]:
    """Compute mean, std, min, max for a sequence of values.

    Returns:
        (mean, std, min, max) tuple
    """
    if not values:
        raise ValueError("Cannot compute stats for empty sequence")

    n = len(values)
    mean = sum(values) / n
    min_val = min(values)
    max_val = max(values)

    if n == 1:
        std = 0.0
    else:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)

    return mean, std, min_val, max_val


def summarize_measurement_set(
    measurement_set: MeasurementSetV1,
    *,
    dominant_frequencies_hz: Sequence[float] | None = None,
    repeatability_scores: Sequence[float] | None = None,
) -> MeasurementSetSummaryV1:
    """Compute summary statistics for a measurement set.

    Args:
        measurement_set: The measurement set to summarize
        dominant_frequencies_hz: Optional sequence of frequency values (Hz)
        repeatability_scores: Optional sequence of repeatability scores [0, 1]

    Returns:
        MeasurementSetSummaryV1 with computed statistics
    """
    freq_mean = freq_std = freq_min = freq_max = None
    rep_mean = rep_std = rep_min = rep_max = None

    if dominant_frequencies_hz and len(dominant_frequencies_hz) > 0:
        freq_mean, freq_std, freq_min, freq_max = _compute_stats(dominant_frequencies_hz)

    if repeatability_scores and len(repeatability_scores) > 0:
        rep_mean, rep_std, rep_min, rep_max = _compute_stats(repeatability_scores)

    return MeasurementSetSummaryV1(
        measurement_count=measurement_set.measurement_count,
        campaign_id=measurement_set.campaign_id,
        revision_id=measurement_set.revision_id,
        workflow_id=measurement_set.workflow_id,
        dominant_frequency_mean_hz=freq_mean,
        dominant_frequency_std_hz=freq_std,
        dominant_frequency_min_hz=freq_min,
        dominant_frequency_max_hz=freq_max,
        repeatability_score_mean=rep_mean,
        repeatability_score_std=rep_std,
        repeatability_score_min=rep_min,
        repeatability_score_max=rep_max,
    )


def create_measurement_set(
    measurement_set_id: str,
    measurement_ids: Sequence[str],
    *,
    campaign_id: str | None = None,
    revision_id: str | None = None,
    workflow_id: str | None = None,
    notes: str | None = None,
) -> MeasurementSetV1:
    """Create a measurement set directly.

    Args:
        measurement_set_id: Unique identifier (caller-provided)
        measurement_ids: Sequence of measurement IDs
        campaign_id: Optional campaign ID
        revision_id: Optional revision ID
        workflow_id: Optional workflow ID
        notes: Optional notes

    Returns:
        New MeasurementSetV1 instance
    """
    return MeasurementSetV1(
        measurement_set_id=measurement_set_id,
        campaign_id=campaign_id,
        revision_id=revision_id,
        workflow_id=workflow_id,
        measurement_ids=tuple(measurement_ids),
        notes=notes,
    )


__all__ = [
    "collect_measurements_for_campaign",
    "collect_measurements_for_revision",
    "collect_measurements_for_workflow",
    "summarize_measurement_set",
    "create_measurement_set",
]
