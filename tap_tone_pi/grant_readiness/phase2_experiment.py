# INSTRUMENT CLASS: MEASUREMENT
"""Preliminary repeatability analysis from Phase 2 transfer results (DO-103).

DO-102 read the Phase 1 single-microphone tap path. DO-103 §5.1 brings Phase 2
alongside it — not in place of it — because a contact-driven rig is
fundamentally a driven input/output measurement. Reducing one to scalar peaks
would discard coherence, the per-frequency trust metric, at exactly the moment
the rig is least trusted.

This module reads what the Phase 2 path already produced and records what it
says. It performs no capture, no FFT, no averaging, no peak picking, and no
reanalysis, and it does not import the Phase 2 code: it consumes the persisted
transfer-function document as a document, which is what keeps the grant layer
an evidence layer. DO-103 §15 authorizes no new signal processing, and none is
added here.

**What is read, and at which frequency.** A driven measurement is compared at a
stated drive frequency, so the caller names an evaluation frequency and this
module records what the document holds at the nearest frequency bin — together
with that bin's own frequency, so a reader sees the offset rather than having to
trust that the two matched. A frequency outside the document's range is not
snapped to an edge bin; it is a rejected run.

**Two rulings an implementer should not have to make alone.**

*The capture time comes from the caller.* A Phase 2 transfer document records
when the analysis was computed, not when the instrument was struck or driven.
Reusing the former as the latter would fabricate provenance, so ``captured_at``
is required rather than inferred.

*Coherence must be present.* §5.1 chose Phase 2 precisely because coherence
travels with the transfer function; a driven run recorded without it is not the
evidence that decision asked for, and it is rejected as ``INVALID_METADATA``.
This is a presence requirement, not a threshold — no coherence value is compared
against anything, because DO-103 §5.5 forbids inventing the very figure this
campaign exists to produce evidence for.

**What this path cannot reject for.** A Phase 2 transfer document carries no
quality gate, so the reasons this module can name are the ones the document can
support: ``INVALID_METADATA`` for a foreign or unusable contract and
``ANALYSIS_FAILURE`` for a result that does not cover the point or the frequency
asked for. ``CLIPPING``, ``INSUFFICIENT_SIGNAL``, and ``QUALITY_GATE_REJECTED``
are Phase 1 gate verdicts; an operator rejecting a driven capture for one of
them records it by constructing the rejected run directly, which the DO-102
contract already supports. Inferring a cause the evidence does not name would be
a guess dressed as a finding.

**Naming.** With a microphone response over a measured force the quantity is
acoustic pressure per unit force. It is not mobility, accelerance, or
receptance, all of which require the response to be a mechanical motion of the
structure (DO-103 §6.6). This module owns the feature names so the distinction
cannot be lost by a caller, and the unit is *derived* from the recorded
acquisition channels rather than assumed: two microphones over each other yield
a ratio, whatever the campaign expected.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    AcquisitionProvenanceV1,
    EnvironmentalContextV1,
    EvidenceOrigin,
    ObservedFeatureV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
    require_utc_timestamp,
)
from tap_tone_pi.grant_readiness.errors import (
    ExperimentRecordError,
    GrantReadinessErrorCode,
)

PHASE2_SCHEMA_VERSION = "phase2_ods_snapshot_v2"

# The unit recorded when the acquisition does not say what the two channels
# carried. H is then response over reference in whatever the document's own
# terms were, which is a ratio and nothing more.
DEFAULT_TRANSFER_UNIT = "ratio"

# Feature names this module owns. "acoustic_transfer_magnitude" is deliberately
# not "mobility": see the module docstring and DO-103 §6.6.
TRANSFER_MAGNITUDE = "acoustic_transfer_magnitude"
TRANSFER_PHASE = "acoustic_transfer_phase"
COHERENCE = "coherence"
EVALUATION_FREQUENCY = "evaluation_frequency"

# What the caller asked for, and how far the answering bin fell from it. The
# nearest-bin rule was always recorded through EVALUATION_FREQUENCY, but the
# request itself was discarded once used — so a study of ten runs could not show
# that all ten asked the same question and were answered at ten slightly
# different frequencies. Both are kept now, and the offset is signed because
# which side of the request a bin fell on is information.
NOMINAL_EVALUATION_FREQUENCY = "nominal_evaluation_frequency"
FREQUENCY_OFFSET = "frequency_offset"


def summarized_phase2_quantities(
    transfer_unit: str = DEFAULT_TRANSFER_UNIT,
) -> tuple[tuple[str, str], ...]:
    """The quantities a Phase 2 study summarizes, in report order.

    The magnitude's unit travels with the quantity because it is derived from
    what the acquisition channels carried — ``Pa/N`` for a microphone over a
    measured force. Pass the same unit the runs were recorded with;
    :func:`~.statistics.summarize_runs` refuses to mix units rather than
    silently averaging across them.
    """
    # ``frequency_offset`` is deliberately absent. Its mean is zero whenever
    # every run landed on its requested bin, and a coefficient of variation over
    # a zero mean is undefined — summarizing it would turn the best possible
    # outcome into an error. The offsets stay visible per run instead, and the
    # spread of the *actual* frequencies is what the summary reports.
    return (
        (EVALUATION_FREQUENCY, "Hz"),
        (NOMINAL_EVALUATION_FREQUENCY, "Hz"),
        (TRANSFER_MAGNITUDE, transfer_unit),
        (TRANSFER_PHASE, "deg"),
        (COHERENCE, "unitless"),
    )


def transfer_unit_for(acquisition: AcquisitionProvenanceV1 | None) -> str:
    """Units of the recorded transfer, derived from the acquisition channels.

    Falls back to :data:`DEFAULT_TRANSFER_UNIT` when the channel pair is absent
    or ambiguous. The unit is never assumed from the experiment's intent.
    """
    if acquisition is None:
        return DEFAULT_TRANSFER_UNIT
    return acquisition.transfer_unit or DEFAULT_TRANSFER_UNIT


# ---------------------------------------------------------------------------
# Reading one Phase 2 transfer result
# ---------------------------------------------------------------------------


def load_phase2_transfer(path: Path) -> Mapping[str, Any]:
    """Read one persisted Phase 2 transfer-function document.

    Raises:
        ExperimentRecordError: ``NSF-204`` if the file is absent, ``NSF-201``
            if it is unreadable or is not a JSON object.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ExperimentRecordError(
            GrantReadinessErrorCode.SOURCE_ARTIFACT_MISSING,
            f"transfer result not found: {path.name}",
            {"artifact": path.name},
        ) from exc
    except (OSError, ValueError) as exc:
        # ValueError covers UnicodeDecodeError. The exception class name is
        # carried; its text is not, because it would contain a host path.
        raise ExperimentRecordError(
            GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
            f"transfer result could not be read: {path.name}",
            {"artifact": path.name, "cause": type(exc).__name__},
        ) from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExperimentRecordError(
            GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
            f"transfer result is not valid JSON: {path.name}",
            {"artifact": path.name},
        ) from exc

    if not isinstance(payload, Mapping):
        raise ExperimentRecordError(
            GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
            f"transfer result is not an object: {path.name}",
            {"artifact": path.name},
        )
    return payload


def _numeric_sequence(value: Any) -> list[float] | None:
    """Return ``value`` as finite floats, or ``None`` if it is not one."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return None
    numbers: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        numbers.append(number)
    return numbers


def _point_for(payload: Mapping[str, Any], point_id: str) -> Mapping[str, Any] | None:
    points = payload.get("points")
    if isinstance(points, (str, bytes)) or not isinstance(points, Sequence):
        return None
    for point in points:
        if isinstance(point, Mapping) and point.get("point_id") == point_id:
            return point
    return None


def _nearest_index(frequencies: Sequence[float], target_hz: float) -> int:
    """Index of the frequency bin closest to ``target_hz``.

    Selection, not signal processing. ``scripts/phase2/dsp.nearest_bin`` does the
    same arithmetic, and this is not that call: package code does not import
    from ``scripts/``, and the grant layer does not import the Phase 2 package
    at all — that separation is what keeps this an evidence layer.
    """
    best = 0
    best_distance = abs(frequencies[0] - target_hz)
    for index in range(1, len(frequencies)):
        distance = abs(frequencies[index] - target_hz)
        if distance < best_distance:
            best = index
            best_distance = distance
    return best


def _rejected(
    *,
    run_id: str,
    experiment_id: str,
    captured_at: str,
    evidence_origin: EvidenceOrigin,
    reason: RejectionReason,
    source_artifact_ids: Sequence[str],
    measurement_result_id: str | None,
    conditions: EnvironmentalContextV1,
    acquisition: AcquisitionProvenanceV1 | None,
    sequence_index: int | None = None,
) -> PreliminaryExperimentRunV1:
    """A rejected attempt keeps its identity, artifacts, provenance, and place.

    Its place in the acquisition order included: a failed attempt still happened,
    and it happened somewhere in the sequence. Dropping the index would leave a
    gap that reads as a run nobody recorded.
    """
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id=experiment_id,
        captured_at=captured_at,
        evidence_origin=evidence_origin,
        valid=False,
        rejection_reason=reason,
        source_artifact_ids=tuple(source_artifact_ids),
        measurement_result_id=measurement_result_id,
        conditions=conditions,
        acquisition=acquisition,
        sequence_index=sequence_index,
    )


def record_phase2_run(
    payload: Mapping[str, Any],
    *,
    run_id: str,
    experiment_id: str,
    measurement_point_id: str,
    evaluation_frequency_hz: float,
    captured_at: str,
    evidence_origin: EvidenceOrigin,
    source_artifact_ids: Sequence[str],
    measurement_result_id: str | None = None,
    conditions: EnvironmentalContextV1 | None = None,
    acquisition: AcquisitionProvenanceV1 | None = None,
    sequence_index: int | None = None,
) -> PreliminaryExperimentRunV1:
    """Record one driven capture from a Phase 2 transfer-function document.

    ``captured_at`` is required: the document records when the analysis was
    computed, not when the capture happened, and inferring one from the other
    would fabricate provenance.

    A rejected run is returned as a record, not raised as an error — a failure is
    evidence, and it keeps its acquisition provenance so a hardware campaign's
    accounting stays complete (DO-103 §6.7).

    Raises:
        ExperimentRecordError: ``NSF-207`` for a non-UTC ``captured_at``.
    """
    stamped = require_utc_timestamp(
        captured_at, record="PreliminaryExperimentRunV1", field_name="captured_at"
    )
    recorded_conditions = conditions or EnvironmentalContextV1()

    def reject(reason: RejectionReason) -> PreliminaryExperimentRunV1:
        return _rejected(
            run_id=run_id,
            experiment_id=experiment_id,
            captured_at=stamped,
            evidence_origin=evidence_origin,
            reason=reason,
            source_artifact_ids=source_artifact_ids,
            measurement_result_id=measurement_result_id,
            conditions=recorded_conditions,
            acquisition=acquisition,
            sequence_index=sequence_index,
        )

    if payload.get("schema_version") != PHASE2_SCHEMA_VERSION:
        # Not the contract this study reads. Recorded as a rejected run rather
        # than dropped, so the attempt stays accounted for.
        return reject(RejectionReason.INVALID_METADATA)

    frequencies = _numeric_sequence(payload.get("freqs_hz"))
    if not frequencies:
        return reject(RejectionReason.INVALID_METADATA)

    point = _point_for(payload, measurement_point_id)
    if point is None:
        # The document is well-formed; it simply produced nothing for the point
        # this experiment is centred on.
        return reject(RejectionReason.ANALYSIS_FAILURE)

    magnitude = _numeric_sequence(point.get("H_mag"))
    phase = _numeric_sequence(point.get("H_phase_deg"))
    coherence = _numeric_sequence(point.get("coherence"))
    if magnitude is None or phase is None:
        return reject(RejectionReason.INVALID_METADATA)
    if coherence is None:
        # §5.1 chose Phase 2 because coherence travels with the transfer
        # function. A driven run recorded without its own trust metric is not
        # the evidence that decision asked for.
        return reject(RejectionReason.INVALID_METADATA)

    expected = len(frequencies)
    if not (len(magnitude) == len(phase) == len(coherence) == expected):
        return reject(RejectionReason.INVALID_METADATA)

    if not math.isfinite(evaluation_frequency_hz) or not (
        min(frequencies) <= evaluation_frequency_hz <= max(frequencies)
    ):
        # Snapping an out-of-range request to an edge bin would report a number
        # from a frequency nobody asked about, as though it answered.
        return reject(RejectionReason.ANALYSIS_FAILURE)

    index = _nearest_index(frequencies, evaluation_frequency_hz)
    unit = transfer_unit_for(acquisition)

    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id=experiment_id,
        captured_at=stamped,
        evidence_origin=evidence_origin,
        valid=True,
        source_artifact_ids=tuple(source_artifact_ids),
        measurement_result_id=measurement_result_id,
        observed_features=(
            # The bin's own frequency, so a reader sees where the value was read
            # rather than trusting that it matched what was asked for — beside
            # the frequency that was asked for, and the signed gap between them.
            ObservedFeatureV1(EVALUATION_FREQUENCY, "Hz", frequencies[index]),
            ObservedFeatureV1(
                NOMINAL_EVALUATION_FREQUENCY, "Hz", evaluation_frequency_hz
            ),
            ObservedFeatureV1(
                FREQUENCY_OFFSET, "Hz", frequencies[index] - evaluation_frequency_hz
            ),
            ObservedFeatureV1(TRANSFER_MAGNITUDE, unit, magnitude[index]),
            ObservedFeatureV1(TRANSFER_PHASE, "deg", phase[index]),
            ObservedFeatureV1(COHERENCE, "unitless", coherence[index]),
        ),
        conditions=recorded_conditions,
        acquisition=acquisition,
        sequence_index=sequence_index,
    )


__all__ = [
    "PHASE2_SCHEMA_VERSION",
    "NOMINAL_EVALUATION_FREQUENCY",
    "FREQUENCY_OFFSET",
    "DEFAULT_TRANSFER_UNIT",
    "TRANSFER_MAGNITUDE",
    "TRANSFER_PHASE",
    "COHERENCE",
    "EVALUATION_FREQUENCY",
    "summarized_phase2_quantities",
    "transfer_unit_for",
    "load_phase2_transfer",
    "record_phase2_run",
]
