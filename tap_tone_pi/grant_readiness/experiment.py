# INSTRUMENT CLASS: MEASUREMENT
"""Preliminary repeatability analysis from Phase 1 runs (DO-102).

Reads results the Phase 1 single-microphone tap path already produced and
assembles them into a bounded repeatability study. This module performs no
capture, no FFT, no peak picking, and no reanalysis: it consumes
``phase1_tap_analysis_v1`` documents and records what they say.

Rejection reasons are mapped from the quality gate's own stable rule
identifiers rather than inferred from a bare verdict:

    Q001 clipped             -> CLIPPING
    Q002 silent              -> INSUFFICIENT_SIGNAL
    Q003 no peaks            -> ANALYSIS_FAILURE
    Q005 invalid sample rate -> INVALID_METADATA
    any other hard rule      -> QUALITY_GATE_REJECTED

A missing file is ``MISSING_ARTIFACT``; an unreadable or wrong-contract document
is ``INVALID_METADATA``. Nothing guesses a cause the evidence does not name.

Evidence origin is supplied by the caller and then checked against the
document: a result carrying ``demo: true`` was generated from synthetic audio,
and calling it ``HARDWARE`` raises ``NSF-305``. DO-102 runs no hardware
campaign, so in practice every study built here is ``FIXTURE`` or ``SYNTHETIC``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    EnvironmentalContextV1,
    EvidenceOrigin,
    ExcitationContextV1,
    ObservedFeatureV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
    RepeatabilityMetricV1,
    RepeatabilityStudyV1,
    require_utc_timestamp,
)
from tap_tone_pi.grant_readiness.errors import (
    ExperimentRecordError,
    GrantReadinessErrorCode,
)
from tap_tone_pi.grant_readiness.statistics import summarize_runs
from tap_tone_pi.grant_readiness.validation import (
    raise_for_findings,
    validate_experiment_definition,
    validate_repeatability_study,
)

PHASE1_SCHEMA_VERSION = "phase1_tap_analysis_v1"

# Quality-gate rule identifiers mapped to the rejection reason each names. The
# gate owns these identifiers; this table reads them rather than re-deriving a
# cause from thresholds.
RULE_REJECTION_REASONS: dict[str, RejectionReason] = {
    "Q001": RejectionReason.CLIPPING,
    "Q002": RejectionReason.INSUFFICIENT_SIGNAL,
    "Q003": RejectionReason.ANALYSIS_FAILURE,
    "Q005": RejectionReason.INVALID_METADATA,
}

# The quantities the first study summarizes, in report order. Each is read
# straight out of the Phase 1 contract; none is computed here.
SUMMARIZED_QUANTITIES: tuple[tuple[str, str], ...] = (
    ("dominant_frequency", "Hz"),
    ("peak_magnitude", "normalized"),
    ("snr", "dB"),
    ("confidence", "unitless"),
)


# ---------------------------------------------------------------------------
# Definition
# ---------------------------------------------------------------------------


def build_preliminary_experiment(
    *,
    experiment_id: str,
    instrument_id: str,
    measurement_point_id: str,
    operator_id: str,
    planned_repeat_count: int,
    created_at: str,
    excitation: ExcitationContextV1 | None = None,
    sensor_position: str | None = None,
    support_condition: str | None = None,
    environmental_context: EnvironmentalContextV1 | None = None,
    analysis_profile: str = PHASE1_SCHEMA_VERSION,
) -> PreliminaryExperimentDefinitionV1:
    """Define one bounded experiment: one instrument, one measurement point.

    Raises:
        ExperimentRecordError: ``NSF-201`` for a missing identity field,
            ``NSF-202`` for fewer than two planned repeats.
    """
    definition = PreliminaryExperimentDefinitionV1(
        experiment_id=experiment_id,
        instrument_id=instrument_id,
        measurement_point_id=measurement_point_id,
        operator_id=operator_id,
        planned_repeat_count=planned_repeat_count,
        created_at=require_utc_timestamp(
            created_at,
            record="PreliminaryExperimentDefinitionV1",
            field_name="created_at",
        ),
        analysis_profile=analysis_profile,
        excitation=excitation or ExcitationContextV1(),
        sensor_position=sensor_position,
        support_condition=support_condition,
        environmental_context=environmental_context or EnvironmentalContextV1(),
    )
    raise_for_findings(
        validate_experiment_definition(definition), error_cls=ExperimentRecordError
    )
    return definition


# ---------------------------------------------------------------------------
# Reading one Phase 1 result
# ---------------------------------------------------------------------------


def load_phase1_analysis(path: Path) -> Mapping[str, Any]:
    """Read one ``phase1_tap_analysis_v1`` document.

    Raises:
        ExperimentRecordError: ``NSF-204`` if the file is absent, ``NSF-201``
            if it is unreadable or is not a Phase 1 analysis document.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ExperimentRecordError(
            GrantReadinessErrorCode.SOURCE_ARTIFACT_MISSING,
            f"analysis result not found: {path.name}",
            {"artifact": path.name},
        ) from exc
    except (OSError, ValueError) as exc:
        # ValueError covers UnicodeDecodeError. The exception class name is
        # carried; its text is not, because it would contain a host path.
        raise ExperimentRecordError(
            GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
            f"analysis result could not be read: {path.name}",
            {"artifact": path.name, "cause": type(exc).__name__},
        ) from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExperimentRecordError(
            GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
            f"analysis result is not valid JSON: {path.name}",
            {"artifact": path.name},
        ) from exc

    if not isinstance(payload, Mapping):
        raise ExperimentRecordError(
            GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
            f"analysis result is not an object: {path.name}",
            {"artifact": path.name},
        )
    return payload


def _rejection_from_quality(payload: Mapping[str, Any]) -> RejectionReason | None:
    """Return the reason the quality gate names, or ``None`` if it passed."""
    quality = payload.get("quality")
    if not isinstance(quality, Mapping):
        return RejectionReason.INVALID_METADATA

    verdict = quality.get("verdict")
    if verdict not in {"pass", "warn", "fail"}:
        return RejectionReason.INVALID_METADATA
    if verdict != "fail":
        return None

    triggered = quality.get("triggered_rules")
    if isinstance(triggered, Sequence) and not isinstance(triggered, (str, bytes)):
        for rule in triggered:
            if not isinstance(rule, Mapping) or rule.get("severity") != "hard":
                continue
            reason = RULE_REJECTION_REASONS.get(str(rule.get("rule_id", "")))
            if reason is not None:
                return reason

    # A hard failure the table does not name. Reporting it as the gate's own
    # verdict is honest; guessing clipping or a low signal would not be.
    return RejectionReason.QUALITY_GATE_REJECTED


def _observed_features(payload: Mapping[str, Any]) -> tuple[ObservedFeatureV1, ...]:
    """Read the summarized quantities out of a Phase 1 analysis block."""
    analysis = payload.get("analysis")
    if not isinstance(analysis, Mapping):
        return ()

    features: list[ObservedFeatureV1] = []

    dominant = analysis.get("dominant_hz")
    if isinstance(dominant, (int, float)) and not isinstance(dominant, bool):
        features.append(ObservedFeatureV1("dominant_frequency", "Hz", float(dominant)))

        # The magnitude of the dominant peak, matched by frequency. The contract
        # sorts peaks by magnitude descending, so the first entry is normally
        # the dominant one, but matching on frequency does not rely on that.
        peaks = analysis.get("peaks")
        if isinstance(peaks, Sequence) and not isinstance(peaks, (str, bytes)):
            for peak in peaks:
                if not isinstance(peak, Mapping):
                    continue
                if peak.get("freq_hz") == dominant:
                    magnitude = peak.get("magnitude")
                    if isinstance(magnitude, (int, float)) and not isinstance(
                        magnitude, bool
                    ):
                        features.append(
                            ObservedFeatureV1(
                                "peak_magnitude", "normalized", float(magnitude)
                            )
                        )
                    break

    components = analysis.get("confidence_components")
    if isinstance(components, Mapping):
        snr = components.get("snr_db")
        if isinstance(snr, (int, float)) and not isinstance(snr, bool):
            features.append(ObservedFeatureV1("snr", "dB", float(snr)))

    confidence = analysis.get("confidence")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        features.append(ObservedFeatureV1("confidence", "unitless", float(confidence)))

    return tuple(features)


def _environment_from_payload(payload: Mapping[str, Any]) -> EnvironmentalContextV1:
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        return EnvironmentalContextV1()
    environment = provenance.get("environment")
    if not isinstance(environment, Mapping):
        return EnvironmentalContextV1()

    def number(key: str) -> float | None:
        value = environment.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    return EnvironmentalContextV1(temp_c=number("temp_c"), rh_pct=number("rh_pct"))


def record_experiment_run(
    payload: Mapping[str, Any],
    *,
    run_id: str,
    experiment_id: str,
    evidence_origin: EvidenceOrigin,
    source_artifact_ids: Sequence[str],
    captured_at: str | None = None,
    measurement_result_id: str | None = None,
    conditions: EnvironmentalContextV1 | None = None,
) -> PreliminaryExperimentRunV1:
    """Record one capture attempt from a Phase 1 analysis document.

    A rejected run keeps its identity, artifacts, and conditions. It is returned
    as a record, not raised as an error — a failure is evidence.

    Raises:
        ExperimentRecordError: ``NSF-305`` when ``HARDWARE`` is claimed for a
            document marked as generated from synthetic audio, ``NSF-207`` for a
            non-UTC timestamp.
    """
    if evidence_origin is EvidenceOrigin.HARDWARE and payload.get("demo") is True:
        raise ExperimentRecordError(
            GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
            (
                f"run {run_id} claims HARDWARE origin but its analysis is marked "
                "as generated from synthetic audio"
            ),
            {"run_id": run_id},
        )

    timestamp = captured_at or payload.get("timestamp_utc")
    stamped = require_utc_timestamp(
        timestamp, record="PreliminaryExperimentRunV1", field_name="captured_at"
    )

    declared_version = payload.get("schema_version")
    if declared_version != PHASE1_SCHEMA_VERSION:
        # The document is not the contract this study reads. It is recorded as a
        # rejected run rather than dropped, so the attempt stays accounted for.
        return PreliminaryExperimentRunV1(
            run_id=run_id,
            experiment_id=experiment_id,
            captured_at=stamped,
            evidence_origin=evidence_origin,
            valid=False,
            rejection_reason=RejectionReason.INVALID_METADATA,
            source_artifact_ids=tuple(source_artifact_ids),
            measurement_result_id=measurement_result_id,
            conditions=conditions or _environment_from_payload(payload),
        )

    features = _observed_features(payload)
    reason = _rejection_from_quality(payload)

    # The dominant frequency is what the study is centred on. A result without
    # one has nothing to summarize whatever the gate said, and the secondary
    # quantities it did produce — SNR, confidence — must not make it look valid.
    has_dominant = any(feature.quantity == "dominant_frequency" for feature in features)
    if reason is None and not has_dominant:
        reason = RejectionReason.ANALYSIS_FAILURE

    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id=experiment_id,
        captured_at=stamped,
        evidence_origin=evidence_origin,
        valid=reason is None,
        rejection_reason=reason,
        source_artifact_ids=tuple(source_artifact_ids),
        measurement_result_id=measurement_result_id,
        observed_features=features if reason is None else (),
        conditions=conditions or _environment_from_payload(payload),
    )


def record_missing_run(
    *,
    run_id: str,
    experiment_id: str,
    evidence_origin: EvidenceOrigin,
    captured_at: str,
    source_artifact_ids: Sequence[str] = (),
) -> PreliminaryExperimentRunV1:
    """Record an attempt whose artifact never arrived.

    A capture that produced no file is still an attempt, and dropping it would
    quietly improve the study's apparent success rate.
    """
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id=experiment_id,
        captured_at=require_utc_timestamp(
            captured_at, record="PreliminaryExperimentRunV1", field_name="captured_at"
        ),
        evidence_origin=evidence_origin,
        valid=False,
        rejection_reason=RejectionReason.MISSING_ARTIFACT,
        source_artifact_ids=tuple(source_artifact_ids),
    )


# ---------------------------------------------------------------------------
# Study
# ---------------------------------------------------------------------------


def default_study_limitations(
    definition: PreliminaryExperimentDefinitionV1,
    runs: Sequence[PreliminaryExperimentRunV1],
    evidence_origin: EvidenceOrigin,
) -> tuple[str, ...]:
    """Limitations that hold for any study this module can build today."""
    valid = sum(1 for run in runs if run.valid)
    limitations = [
        "These figures describe repeatability: the spread of repeated "
        "observations under the recorded conditions. They are not an accuracy, "
        "and no agreement with any reference method has been established.",
        f"The sample is {valid} valid run(s) from a single measurement point on "
        "a single instrument by a single operator. It does not describe "
        "between-point, between-instrument, between-operator, or "
        "between-session variation.",
        "Environmental conditions are recorded as supplied and are not "
        "corrected for. Where a field is unknown it is recorded as unknown.",
        "Extracted peaks are spectral feature candidates, not identified "
        "structural modes.",
    ]

    if evidence_origin is not EvidenceOrigin.HARDWARE:
        limitations.insert(
            0,
            f"This study is built from {evidence_origin.value} data. It proves "
            "the contract and the analysis path. It is not hardware evidence "
            "and says nothing about how the instrument behaves in a shop.",
        )

    if definition.environmental_context.is_fully_unknown:
        limitations.append(
            "No environmental conditions were supplied for this experiment, so "
            "any environmental contribution to the observed spread is unknown."
        )

    return tuple(limitations)


def build_repeatability_study(
    *,
    study_id: str,
    definition: PreliminaryExperimentDefinitionV1,
    runs: Sequence[PreliminaryExperimentRunV1],
    generated_at: str,
    evidence_origin: EvidenceOrigin,
    quantities: Sequence[tuple[str, str]] = SUMMARIZED_QUANTITIES,
    limitations: Sequence[str] | None = None,
    referenced_repeatability_evidence_ids: Sequence[str] = (),
    strict: bool = True,
) -> RepeatabilityStudyV1:
    """Assemble a study from recorded runs, summarizing the valid ones.

    Rejected runs are carried into the study and counted; only valid runs reach
    a metric. A quantity observed by fewer than two valid runs is omitted rather
    than summarized from one number.

    Raises:
        ExperimentRecordError: When ``strict`` and the assembled study fails
            validation — for example an origin its runs do not support.
    """
    ordered = tuple(runs)
    metrics: list[RepeatabilityMetricV1] = []
    for quantity, unit in quantities:
        metric = summarize_runs(ordered, quantity=quantity, unit=unit)
        if metric is not None:
            metrics.append(metric)

    study = RepeatabilityStudyV1(
        study_id=study_id,
        experiment_definition=definition,
        generated_at=require_utc_timestamp(
            generated_at, record="RepeatabilityStudyV1", field_name="generated_at"
        ),
        evidence_origin=evidence_origin,
        runs=ordered,
        metrics=tuple(metrics),
        limitations=tuple(
            default_study_limitations(definition, ordered, evidence_origin)
            if limitations is None
            else limitations
        ),
        referenced_repeatability_evidence_ids=tuple(
            referenced_repeatability_evidence_ids
        ),
    )

    if strict:
        raise_for_findings(
            validate_repeatability_study(study), error_cls=ExperimentRecordError
        )
    return study


__all__ = [
    "PHASE1_SCHEMA_VERSION",
    "RULE_REJECTION_REASONS",
    "SUMMARIZED_QUANTITIES",
    "build_preliminary_experiment",
    "load_phase1_analysis",
    "record_experiment_run",
    "record_missing_run",
    "default_study_limitations",
    "build_repeatability_study",
]
