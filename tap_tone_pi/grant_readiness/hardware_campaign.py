# INSTRUMENT CLASS: MEASUREMENT
"""Grouping and comparison for the DO-103 hardware characterization campaign.

DO-103 asks five questions of one contact-drive rig: what the rig itself does
(E1), how much a fixed point repeats (E2), what detaching and re-attaching the
stinger costs (E3), whether driving at A and measuring at B agrees with the
transpose (E4), and whether a known added mass is visible at all (E5). Every one
of them is answered by *grouping the same run records differently* and
describing what the groups did.

That is all this module does. It computes no spectrum, reads no audio, and adds
no signal processing: the transfer functions and coherences it compares were
produced by the existing Phase 2 path and were brought into the evidence layer
by :mod:`~.phase2_experiment`, which reads them as documents. DO-103 §15
authorizes no new DSP and none is added here.

**Nothing in this module grades anything.** There is no reciprocity tolerance,
no mass-response threshold, and no acceptance figure of any kind. DO-103 §4.6
and §4.7 make that explicit and give the reason: the campaign exists to produce
the evidence a future limit could be derived from, so inventing the limit first
would decide the question the experiment was built to ask. A poor reciprocity
residual and a mass challenge that moved nothing are both valid findings, and
this module reports them the same way it reports a good one.

**What a comparison needs, it requires.** A mass challenge without a measured
mass, a reciprocity direction without its transpose, and a loaded group with no
unloaded baseline are refused rather than approximated, because each would
produce a number that looks like evidence and is not.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    AcquisitionChannelV1,
    AcquisitionProvenanceV1,
    AcquisitionRole,
    AttachmentVariationV1,
    CalibrationTraceability,
    CampaignExecutionStatus,
    CampaignExperimentOutcomeV1,
    CampaignExperimentPlanV1,
    ExcitationContextV1,
    ExperimentKind,
    ExperimentOutcomeStatus,
    ExternalArtifactV1,
    HardwareCampaignConfigV1,
    HardwareCampaignRecordV1,
    MassLoadingObservationV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    ReciprocityObservationV1,
    RepeatabilityMetricV1,
    RepeatabilityStudyV1,
    require_utc_timestamp,
)
from tap_tone_pi.grant_readiness.errors import (
    GrantReadinessErrorCode,
    HardwareCampaignError,
    RepeatabilityStatisticsError,
)
from tap_tone_pi.grant_readiness.phase2_experiment import (
    COHERENCE,
    EVALUATION_FREQUENCY,
    PHASE2_SCHEMA_VERSION,
)
from tap_tone_pi.grant_readiness.statistics import (
    ZERO_MEAN_EPSILON,
    summarize_group_spread,
    summarize_runs,
)
from tap_tone_pi.grant_readiness.validation import (
    evidence_digest,
    validate_witnessed_hardware_session,
)

# The excitation method a contact-drive rig uses. It is one of the values the
# DO-102 vocabulary already knows; nothing new is introduced here.
CONTACT_DRIVE_METHOD = "shaker_stinger"

# What the between-group spread is a spread *of*, recorded on the group record
# so a reader never has to infer that its samples are not runs.
ATTACHMENT_GROUP_KIND = "attachment"


# ---------------------------------------------------------------------------
# Configuration into evidence records
# ---------------------------------------------------------------------------


def build_rig_excitation_context(
    *,
    rig_configuration_id: str,
    shaker_id: str | None = None,
    stinger_id: str | None = None,
    contact_tip_id: str | None = None,
    fixture_id: str | None = None,
    excitation_point: str | None = None,
    contact_condition: str | None = None,
    excitation_contract_id: str | None = None,
    excitation_method: str = CONTACT_DRIVE_METHOD,
) -> ExcitationContextV1:
    """Describe one assembled rig using the existing excitation record.

    DO-103 §4.8 treats the rig as part of the measurement instrument: swapping a
    stinger or a contact tip changes the mechanical path into the specimen and
    is a configuration change, not a repeat. Naming each part separately is what
    lets a later reader tell the two apart.
    """
    return ExcitationContextV1(
        excitation_method=excitation_method,
        excitation_device_id=shaker_id,
        excitation_point=excitation_point,
        contact_condition=contact_condition,
        fixture_id=fixture_id,
        excitation_contract_id=excitation_contract_id,
        stinger_id=stinger_id,
        contact_tip_id=contact_tip_id,
        rig_configuration_id=rig_configuration_id,
    )


def build_force_channel(
    *,
    channel_index: int,
    sensor_id: str,
    unit: str,
    sensitivity_value: float | None = None,
    sensitivity_unit: str | None = None,
    calibration_traceability: CalibrationTraceability = CalibrationTraceability.UNKNOWN,
    calibration_reference: str | None = None,
    gain_setting: str | None = None,
) -> AcquisitionChannelV1:
    """The reference channel of the two-channel model, carrying measured force.

    DO-103 §4.2 requires the excitation to be measured rather than commanded,
    and the force transducer occupies the reference channel the existing Phase 2
    path already reads. No sensitivity or unit is assumed: whatever the chosen
    transducer states is what is recorded, and a sensor nobody has calibrated
    keeps ``UNKNOWN`` traceability rather than acquiring a plausible default.

    Measured is not traceable (§4.2). Claiming ``TRACEABLE`` requires a
    calibration reference, which :func:`~.validation.validate_channel_calibration`
    enforces.
    """
    return AcquisitionChannelV1(
        channel_index=channel_index,
        role=AcquisitionRole.EXCITATION,
        quantity="force",
        unit=unit,
        sensor_id=sensor_id,
        gain_setting=gain_setting,
        sensitivity_value=sensitivity_value,
        sensitivity_unit=sensitivity_unit,
        calibration_traceability=calibration_traceability,
        calibration_reference=calibration_reference,
    )


def build_response_channel(
    *,
    channel_index: int,
    sensor_id: str,
    unit: str,
    sensitivity_value: float | None = None,
    sensitivity_unit: str | None = None,
    calibration_traceability: CalibrationTraceability = CalibrationTraceability.UNKNOWN,
    calibration_reference: str | None = None,
    gain_setting: str | None = None,
) -> AcquisitionChannelV1:
    """The response channel, carrying acoustic pressure from the microphone.

    DO-103 §4.3 chooses a microphone deliberately: an accelerometer adds local
    mass, and E5 exists to measure the effect of added mass, so a response
    sensor that perturbs the specimen would confound the experiment with itself.
    """
    return AcquisitionChannelV1(
        channel_index=channel_index,
        role=AcquisitionRole.RESPONSE,
        quantity="acoustic_pressure",
        unit=unit,
        sensor_id=sensor_id,
        gain_setting=gain_setting,
        sensitivity_value=sensitivity_value,
        sensitivity_unit=sensitivity_unit,
        calibration_traceability=calibration_traceability,
        calibration_reference=calibration_reference,
    )


def build_campaign_definition(
    plan: CampaignExperimentPlanV1,
    config: HardwareCampaignConfigV1,
    *,
    created_at: str,
    analysis_profile: str = PHASE2_SCHEMA_VERSION,
) -> PreliminaryExperimentDefinitionV1:
    """Turn one planned experiment into the DO-102 experiment definition.

    The campaign adds no second definition record: this is the same
    :class:`PreliminaryExperimentDefinitionV1` DO-102 established, filled in
    from the campaign's stated configuration so that every experiment in a
    campaign shares one rig description rather than restating it.
    """
    return PreliminaryExperimentDefinitionV1(
        experiment_id=plan.experiment_id,
        instrument_id=plan.instrument_id,
        measurement_point_id=plan.measurement_point_id,
        operator_id=config.operator_id,
        planned_repeat_count=plan.planned_repeat_count,
        created_at=require_utc_timestamp(
            created_at,
            record="PreliminaryExperimentDefinitionV1",
            field_name="created_at",
        ),
        analysis_profile=analysis_profile,
        excitation=config.excitation,
        sensor_position=None,
        support_condition=config.support_condition,
        environmental_context=config.environmental_context,
    )


def build_campaign_acquisition(
    config: HardwareCampaignConfigV1,
    *,
    session_id: str,
    acquisition_id: str,
    raw_artifact_ids: Sequence[str] = (),
    drive_parameters: str | None = None,
    witnessed_by: str | None = None,
) -> AcquisitionProvenanceV1:
    """Acquisition provenance for one campaign run, from the campaign's channels.

    ``witnessed_by`` is passed through and never defaulted. DO-103 §5.4 keeps
    *witnessed* stricter than *hardware-origin*, and a session becomes witnessed
    because someone attests to it, not because a builder supplied a value.
    """
    return AcquisitionProvenanceV1(
        session_id=session_id,
        acquisition_id=acquisition_id,
        interface_id=config.interface_id,
        sample_rate_hz=config.sample_rate_hz,
        channels=config.channels,
        excitation_device_id=config.excitation.excitation_device_id,
        drive_parameters=drive_parameters,
        raw_artifact_ids=tuple(raw_artifact_ids),
        witnessed_by=witnessed_by,
    )


def elapsed_seconds_from_first(
    runs: Sequence[PreliminaryExperimentRunV1],
) -> dict[str, float]:
    """Seconds from the first acquisition to each run, by run id.

    Derived rather than stored: it is a property of a run *collection*, not of a
    run, and a stored copy could disagree with the timestamps it was taken over.
    The zero point is the earliest recorded capture, so a run that predates the
    one indexed first still reports a negative elapsed rather than being
    silently reordered — the disagreement belongs to
    :func:`~.validation.validate_run_sequence`, not to arithmetic.

    Runs whose timestamp will not parse are omitted rather than defaulted.
    """
    stamps: dict[str, datetime] = {}
    for run in runs:
        text = run.captured_at
        text = text.replace("Z", "+00:00") if text.endswith("Z") else text
        try:
            stamps[run.run_id] = datetime.fromisoformat(text)
        except ValueError:
            continue
    if not stamps:
        return {}
    origin = min(stamps.values())
    return {
        run_id: (stamp - origin).total_seconds() for run_id, stamp in stamps.items()
    }


def artifact_digest(data: bytes) -> str:
    """SHA-256 of raw bytes, as an artifact's durable identity.

    Raw audio is not committed to this repository, so a reference to it must
    survive the file being moved. The digest is what does that; a path is only
    where a copy happened to sit when it was recorded.
    """
    return hashlib.sha256(data).hexdigest()


def build_external_artifact(
    *,
    artifact_id: str,
    kind: str,
    sha256: str,
    byte_count: int,
    media_type: str,
    storage_locator: str,
    capture_run_id: str | None = None,
    local_path_hint: str | None = None,
) -> ExternalArtifactV1:
    """Record one retained raw measurement that lives outside the repository."""
    return ExternalArtifactV1(
        artifact_id=artifact_id,
        kind=kind,
        sha256=sha256,
        byte_count=byte_count,
        media_type=media_type,
        storage_locator=storage_locator,
        capture_run_id=capture_run_id,
        repository_tracked=False,
        local_path_hint=local_path_hint,
    )


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


def _valid_campaign_runs(
    runs: Iterable[PreliminaryExperimentRunV1],
    kind: ExperimentKind | None = None,
) -> tuple[PreliminaryExperimentRunV1, ...]:
    """Valid runs carrying a campaign condition, optionally of one kind.

    Rejected runs are excluded from every comparison and from none of the
    accounting: they stay in their study, are counted there, and simply cannot
    contribute a number they do not have (DO-103 §6.7).
    """
    selected = []
    for run in runs:
        if not run.valid or run.campaign_condition is None:
            continue
        if kind is not None and run.campaign_condition.experiment_kind is not kind:
            continue
        selected.append(run)
    return tuple(selected)


def group_runs_by_attachment(
    runs: Iterable[PreliminaryExperimentRunV1],
) -> dict[str, tuple[PreliminaryExperimentRunV1, ...]]:
    """Group valid runs by the attachment they were captured under.

    Runs sharing a ``contact_configuration_id`` were captured without breaking
    contact. A run that records no attachment identity is not placed in an
    arbitrary group — it is left out, and
    :func:`~.validation.validate_campaign_conditions` reports it as ``NSF-502``,
    because guessing would silently merge two attachments into one.

    Groups are returned in first-seen order so a report reads in the order the
    campaign was executed.
    """
    grouped: dict[str, list[PreliminaryExperimentRunV1]] = {}
    for run in _valid_campaign_runs(runs):
        attachment = run.campaign_condition.contact_configuration_id
        if attachment is None:
            continue
        grouped.setdefault(attachment, []).append(run)
    return {key: tuple(value) for key, value in grouped.items()}


def group_runs_by_added_mass(
    runs: Iterable[PreliminaryExperimentRunV1],
) -> dict[str, tuple[PreliminaryExperimentRunV1, ...]]:
    """Group valid mass-loading runs by their mass challenge.

    Raises:
        HardwareCampaignError: ``NSF-505`` for a challenge with no measured
            mass, a negative mass, or a nominal mass standing alone;
            ``NSF-506`` when one challenge identifier covers two different
            measured masses.
    """
    grouped: dict[str, list[PreliminaryExperimentRunV1]] = {}
    masses: dict[str, float] = {}
    for run in _valid_campaign_runs(runs, ExperimentKind.MASS_LOADING):
        condition = run.campaign_condition
        challenge = condition.mass_challenge_id
        if challenge is None:
            continue
        if condition.added_mass_g is None:
            raise HardwareCampaignError(
                GrantReadinessErrorCode.MASS_CHALLENGE_UNMEASURED,
                (
                    f"mass challenge {challenge!r} on run {run.run_id} records no "
                    "measured mass; a nominal mass may not stand in for it"
                ),
                {"run_id": run.run_id, "mass_challenge_id": challenge},
            )
        if condition.added_mass_g < 0:
            raise HardwareCampaignError(
                GrantReadinessErrorCode.MASS_CHALLENGE_UNMEASURED,
                (
                    f"mass challenge {challenge!r} on run {run.run_id} records a "
                    "negative added mass"
                ),
                {"run_id": run.run_id, "added_mass_g": condition.added_mass_g},
            )
        known = masses.get(challenge)
        if known is not None and known != condition.added_mass_g:
            raise HardwareCampaignError(
                GrantReadinessErrorCode.DUPLICATE_MASS_CHALLENGE,
                (
                    f"mass challenge {challenge!r} covers two different measured "
                    f"masses ({known} g and {condition.added_mass_g} g)"
                ),
                {
                    "mass_challenge_id": challenge,
                    "masses_g": sorted({known, condition.added_mass_g}),
                },
            )
        masses[challenge] = condition.added_mass_g
        grouped.setdefault(challenge, []).append(run)
    return {key: tuple(value) for key, value in grouped.items()}


# ---------------------------------------------------------------------------
# E2 and E3 — repeatability within and between attachments
# ---------------------------------------------------------------------------


def summarize_attachment_variation(
    runs: Sequence[PreliminaryExperimentRunV1],
    *,
    quantity: str,
    unit: str,
    variation_id: str | None = None,
) -> AttachmentVariationV1 | None:
    """Describe how one quantity moved within attachments and between them.

    The two are never combined. Repeats that never broke contact are summarized
    per attachment; the spread *between* attachments is taken over each
    attachment's own mean, and is the number E3 exists to produce.

    An attachment observed once contributes its single value to the between-
    attachment spread — a mean of one observation is that observation — but
    yields no within-attachment metric, and is named in
    ``unsummarized_attachment_ids`` so the asymmetry is visible rather than
    inferred.

    Returns ``None`` when no run records an attachment, which is a reportable
    state and not an error: it means the campaign has not run E3.
    """
    grouped = group_runs_by_attachment(runs)
    if not grouped:
        return None

    within: list[RepeatabilityMetricV1] = []
    unsummarized: list[str] = []
    group_ids: list[str] = []
    group_values: list[float] = []

    for attachment, attachment_runs in grouped.items():
        observed = [
            run.feature(quantity)
            for run in attachment_runs
            if run.feature(quantity) is not None
        ]
        if not observed:
            unsummarized.append(attachment)
            continue
        for feature in observed:
            if feature.unit != unit:
                raise RepeatabilityStatisticsError(
                    GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS,
                    (
                        f"attachment {attachment} reports {quantity} in "
                        f"{feature.unit}, not {unit}"
                    ),
                    {"quantity": quantity, "attachment": attachment},
                )
        group_ids.append(attachment)
        group_values.append(sum(f.value for f in observed) / len(observed))

        metric = summarize_runs(
            attachment_runs,
            quantity=quantity,
            unit=unit,
            metric_id=f"metric-{quantity}-{attachment}",
        )
        if metric is None:
            unsummarized.append(attachment)
        else:
            within.append(metric)

    between = None
    if len(group_values) >= 2:
        between = summarize_group_spread(
            group_values,
            group_kind=ATTACHMENT_GROUP_KIND,
            group_ids=group_ids,
            quantity=quantity,
            unit=unit,
        )

    return AttachmentVariationV1(
        variation_id=variation_id or f"variation-{quantity}",
        quantity=quantity,
        unit=unit,
        attachment_ids=tuple(grouped),
        within_attachment_metrics=tuple(within),
        between_attachment_spread=between,
        unsummarized_attachment_ids=tuple(unsummarized),
    )


# ---------------------------------------------------------------------------
# E4 — reciprocity
# ---------------------------------------------------------------------------


def pair_reciprocity_runs(
    runs: Iterable[PreliminaryExperimentRunV1],
) -> tuple[tuple[PreliminaryExperimentRunV1, PreliminaryExperimentRunV1], ...]:
    """Pair each reciprocity run with the run that measures its transpose.

    A pair is drive-at-A/measure-at-B against drive-at-B/measure-at-A, and
    nothing looser. Runs at the same pair in the same direction are repeats of
    one measurement, and a pair sharing only one point is a different
    measurement altogether.

    Within one unordered point pair the directions are matched in the order they
    were recorded, and the direction whose drive point sorts first is returned
    as the forward one, so the pairing is deterministic and a report does not
    change between runs of the same data.

    Raises:
        HardwareCampaignError: ``NSF-502`` for a reciprocity run that records no
            point pair, ``NSF-503`` when a direction has no counterpart, and
            ``NSF-504`` for a run that drives and measures at the same point.
    """
    directions: dict[
        tuple[str, str], dict[tuple[str, str], list[PreliminaryExperimentRunV1]]
    ] = {}

    for run in _valid_campaign_runs(runs, ExperimentKind.RECIPROCITY):
        pair = run.campaign_condition.point_pair
        if pair is None:
            raise HardwareCampaignError(
                GrantReadinessErrorCode.CAMPAIGN_CONDITION_INCOMPLETE,
                (f"reciprocity run {run.run_id} records no drive/response point pair"),
                {"run_id": run.run_id},
            )
        if pair[0] == pair[1]:
            raise HardwareCampaignError(
                GrantReadinessErrorCode.RECIPROCITY_POINTS_MISMATCHED,
                (
                    f"reciprocity run {run.run_id} drives and measures at the "
                    f"same point {pair[0]!r}, which has no transpose"
                ),
                {"run_id": run.run_id, "point_id": pair[0]},
            )
        # Canonical, so the same data always pairs the same way round.
        key = pair if pair[0] < pair[1] else (pair[1], pair[0])
        directions.setdefault(key, {}).setdefault(pair, []).append(run)

    paired: list[tuple[PreliminaryExperimentRunV1, PreliminaryExperimentRunV1]] = []
    for key in sorted(directions):
        forward_pair = (key[0], key[1])
        reverse_pair = (key[1], key[0])
        forward = directions[key].get(forward_pair, [])
        reverse = directions[key].get(reverse_pair, [])
        if not forward or not reverse:
            present = forward or reverse
            raise HardwareCampaignError(
                GrantReadinessErrorCode.RECIPROCITY_PAIR_INCOMPLETE,
                (
                    f"reciprocity pair {key[0]}/{key[1]} has only one direction; "
                    f"runs {', '.join(run.run_id for run in present)} have no "
                    "counterpart"
                ),
                {
                    "point_pair": list(key),
                    "unpaired_run_ids": [run.run_id for run in present],
                },
            )
        if len(forward) != len(reverse):
            longer = forward if len(forward) > len(reverse) else reverse
            unpaired = [run.run_id for run in longer[min(len(forward), len(reverse)) :]]
            raise HardwareCampaignError(
                GrantReadinessErrorCode.RECIPROCITY_PAIR_INCOMPLETE,
                (
                    f"reciprocity pair {key[0]}/{key[1]} has {len(forward)} forward "
                    f"and {len(reverse)} reverse runs; "
                    f"{', '.join(unpaired)} cannot be paired"
                ),
                {"point_pair": list(key), "unpaired_run_ids": unpaired},
            )
        paired.extend(zip(forward, reverse))

    return tuple(paired)


def _feature_value(
    run: PreliminaryExperimentRunV1, quantity: str, unit: str | None = None
) -> float | None:
    observed = run.feature(quantity)
    if observed is None:
        return None
    if unit is not None and observed.unit != unit:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS,
            f"run {run.run_id} reports {quantity} in {observed.unit}, not {unit}",
            {"quantity": quantity, "run_id": run.run_id, "unit": observed.unit},
        )
    return observed.value


def summarize_reciprocity(
    pairs: Sequence[tuple[PreliminaryExperimentRunV1, PreliminaryExperimentRunV1]],
    *,
    quantity: str,
    unit: str,
) -> tuple[ReciprocityObservationV1, ...]:
    """Report the residual between each paired direction, and nothing more.

    The residual is the absolute difference between the two directions; the
    relative residual scales it by the mean magnitude of the two, and is
    ``None`` where that mean is too small to scale by. Each direction keeps its
    own coherence, because a residual observed where one direction was poorly
    coherent means something different from the same residual where both were
    strong.

    Each direction also keeps its own evaluation frequency. The two are separate
    captures and can land on different bins, in which case the residual spans two
    slightly different frequencies; the observation records both and derives the
    gap, so the asymmetry is visible in the pair record instead of only inside
    the two runs. No limit is placed on that gap.

    No verdict is produced. DO-103 §4.6 forbids an acceptance threshold here,
    and a large residual is a finding about the measurement architecture rather
    than a failure of the run that revealed it.

    Raises:
        RepeatabilityStatisticsError: ``NSF-301`` when a paired run did not
            observe ``quantity``, ``NSF-302`` for a unit mismatch.
    """
    observations: list[ReciprocityObservationV1] = []
    for index, (forward, reverse) in enumerate(pairs, start=1):
        forward_value = _feature_value(forward, quantity, unit)
        reverse_value = _feature_value(reverse, quantity, unit)
        missing = [
            run.run_id
            for run, value in ((forward, forward_value), (reverse, reverse_value))
            if value is None
        ]
        if missing:
            raise RepeatabilityStatisticsError(
                GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                (
                    f"reciprocity pair {forward.run_id}/{reverse.run_id} cannot be "
                    f"compared: {', '.join(missing)} did not observe {quantity}"
                ),
                {"quantity": quantity, "run_ids": missing},
            )

        absolute = abs(forward_value - reverse_value)
        scale = (abs(forward_value) + abs(reverse_value)) / 2
        relative = absolute / scale if scale > ZERO_MEAN_EPSILON else None

        pair = forward.campaign_condition.point_pair
        observations.append(
            ReciprocityObservationV1(
                observation_id=f"reciprocity-{quantity}-{index:03d}",
                quantity=quantity,
                unit=unit,
                forward_run_id=forward.run_id,
                reverse_run_id=reverse.run_id,
                forward_drive_point_id=pair[0],
                forward_response_point_id=pair[1],
                forward_value=forward_value,
                reverse_value=reverse_value,
                absolute_residual=absolute,
                relative_residual=relative,
                forward_evaluation_frequency_hz=_feature_value(
                    forward, EVALUATION_FREQUENCY
                ),
                reverse_evaluation_frequency_hz=_feature_value(
                    reverse, EVALUATION_FREQUENCY
                ),
                forward_coherence=_feature_value(forward, COHERENCE),
                reverse_coherence=_feature_value(reverse, COHERENCE),
            )
        )
    return tuple(observations)


# ---------------------------------------------------------------------------
# E5 — deliberate mass loading
# ---------------------------------------------------------------------------


def summarize_mass_loading(
    runs: Sequence[PreliminaryExperimentRunV1],
    *,
    quantity: str,
    unit: str,
) -> tuple[MassLoadingObservationV1, ...]:
    """Compare each loaded group against the unloaded baseline.

    The comparison is between *summarized groups*, never between two single
    captures: a difference smaller than the spread it sits in is not a detection,
    and a reader can only see that if both spreads travel with both means. Each
    group therefore needs at least two valid runs, which is a property of what
    can be computed and not a quality bar.

    The delta keeps its sign. Which way a quantity moved under added mass is
    physical information that an absolute value would discard. It stays a
    description: nothing here says whether a response of any size is adequate,
    which DO-103 §4.7 forbids.

    Raises:
        HardwareCampaignError: ``NSF-507`` when loaded groups exist with no
            baseline, plus the grouping failures of
            :func:`group_runs_by_added_mass`.
        RepeatabilityStatisticsError: ``NSF-301`` when a group has fewer than
            two valid observations of ``quantity``.
    """
    grouped = group_runs_by_added_mass(runs)
    if not grouped:
        return ()

    baseline_runs: list[PreliminaryExperimentRunV1] = []
    challenges: dict[str, tuple[PreliminaryExperimentRunV1, ...]] = {}
    for challenge, challenge_runs in grouped.items():
        if challenge_runs[0].campaign_condition.is_mass_baseline:
            baseline_runs.extend(challenge_runs)
        else:
            challenges[challenge] = challenge_runs

    if not challenges:
        return ()

    if not baseline_runs:
        raise HardwareCampaignError(
            GrantReadinessErrorCode.MASS_BASELINE_MISSING,
            (
                "mass-loading runs carry added mass but no unloaded baseline was "
                f"recorded: {', '.join(sorted(challenges))}"
            ),
            {"mass_challenge_ids": sorted(challenges)},
        )

    baseline_metric = summarize_runs(
        baseline_runs,
        quantity=quantity,
        unit=unit,
        metric_id=f"metric-{quantity}-baseline",
    )
    if baseline_metric is None:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            (
                f"the mass-loading baseline has fewer than two valid observations "
                f"of {quantity}, so no loaded group can be compared against it"
            ),
            {"quantity": quantity, "run_count": len(baseline_runs)},
        )

    observations: list[MassLoadingObservationV1] = []
    for challenge in sorted(challenges):
        challenge_runs = challenges[challenge]
        condition = challenge_runs[0].campaign_condition
        loaded_metric = summarize_runs(
            challenge_runs,
            quantity=quantity,
            unit=unit,
            metric_id=f"metric-{quantity}-{challenge}",
        )
        if loaded_metric is None:
            raise RepeatabilityStatisticsError(
                GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                (
                    f"mass challenge {challenge!r} has fewer than two valid "
                    f"observations of {quantity}"
                ),
                {"quantity": quantity, "mass_challenge_id": challenge},
            )
        delta = loaded_metric.mean - baseline_metric.mean
        relative = (
            100.0 * delta / baseline_metric.mean
            if abs(baseline_metric.mean) > ZERO_MEAN_EPSILON
            else None
        )
        observations.append(
            MassLoadingObservationV1(
                observation_id=f"mass-loading-{quantity}-{challenge}",
                quantity=quantity,
                unit=unit,
                mass_challenge_id=challenge,
                added_mass_g=condition.added_mass_g,
                nominal_added_mass_g=condition.nominal_added_mass_g,
                mass_location_id=condition.mass_location_id,
                baseline_metric=baseline_metric,
                loaded_metric=loaded_metric,
                absolute_delta=delta,
                relative_delta_pct=relative,
            )
        )
    return tuple(observations)


# ---------------------------------------------------------------------------
# The campaign record
# ---------------------------------------------------------------------------


def build_campaign_outcome(
    plan: CampaignExperimentPlanV1,
    study: RepeatabilityStudyV1,
    *,
    note: str | None = None,
) -> CampaignExperimentOutcomeV1:
    """Record an executed experiment, summarizing the study it produced.

    The evidence origin and the witnessed flag are read *off the study*, never
    supplied. DO-103 §5.4 makes the hardware claim derived rather than declared,
    and a campaign-level summary that a caller could assert independently would
    reopen exactly the gap Stage 3 closed. The digest is recorded with them so a
    reader can check the summary against the study it summarizes, and
    ``ttp_hardware_campaign_check.py`` does check it.
    """
    return CampaignExperimentOutcomeV1(
        experiment_id=plan.experiment_id,
        kind=plan.kind,
        status=ExperimentOutcomeStatus.EXECUTED,
        study_id=study.study_id,
        study_digest=evidence_digest(study.to_dict()),
        evidence_origin=study.evidence_origin,
        witnessed=not validate_witnessed_hardware_session(study),
        note=note,
    )


def campaign_status_for(
    outcomes: Sequence[CampaignExperimentOutcomeV1],
) -> CampaignExecutionStatus:
    """The campaign status the outcomes support, without a caller's opinion.

    A campaign that ran only against fixture data is ``FIXTURE_EXECUTED`` and
    not ``EXECUTED``: rehearsing the analysis path end to end is a real and
    useful thing to have done, and it is not the physical campaign. Keeping the
    two under one word is the misreading this function exists to prevent.

    ``HALTED_AT_GATE`` wins over an execution status, because a campaign stopped
    by E1 is defined by having stopped, not by what ran before it did.
    """
    executed = [
        outcome
        for outcome in outcomes
        if outcome.status is ExperimentOutcomeStatus.EXECUTED
    ]
    if any(
        outcome.status is ExperimentOutcomeStatus.HALTED_AT_GATE for outcome in outcomes
    ):
        return CampaignExecutionStatus.HALTED_AT_GATE
    if not executed:
        return CampaignExecutionStatus.PREPARED
    if any(outcome.is_hardware_evidence for outcome in executed):
        return CampaignExecutionStatus.HARDWARE_EXECUTED
    return CampaignExecutionStatus.FIXTURE_EXECUTED


def default_campaign_limitations(
    config: HardwareCampaignConfigV1,
    execution_status: CampaignExecutionStatus,
    outcomes: Sequence[CampaignExperimentOutcomeV1] = (),
) -> tuple[str, ...]:
    """Limitations that hold for any campaign this module can assemble.

    Each one states something the campaign cannot support rather than something
    it achieved, which is the only direction a limitation is useful in.
    """
    limitations = [
        "The measured transfer quantity is acoustic pressure per unit force. It "
        "is not mobility, accelerance, or receptance: those require the response "
        "to be a mechanical motion of the structure, and the response here is a "
        "microphone.",
        "These figures describe repeatability, residuals, and deltas observed by "
        "this instrument against itself. No agreement with any reference method "
        "has been established, and none can be inferred from them.",
        "Reciprocity and mass-loading results are reported without acceptance "
        "thresholds. No figure in this campaign was compared against a limit, "
        "because the campaign exists to produce the evidence such a limit would "
        "have to be derived from.",
    ]

    force = config.force_channel
    if force is None:
        limitations.append(
            "No channel records a measured force, so the excitation is commanded "
            "rather than observed and no transfer function in this campaign has a "
            "measured input."
        )
    elif not force.claims_traceability:
        limitations.append(
            "The force channel is measured but not traceable: its scaling to "
            f"{force.unit} rests on a "
            f"{force.calibration_traceability.value.lower()} sensitivity with no "
            "chain to a standard. Magnitudes are therefore not laboratory-"
            "traceable, and only their relative behaviour is supported."
        )

    response = None
    for channel in config.channels_for(AcquisitionRole.RESPONSE):
        response = channel
        break
    if response is not None and not response.claims_traceability:
        limitations.append(
            "The microphone is not traceably calibrated, so the pressure "
            "magnitude reported here is not a laboratory-traceable sound "
            "pressure."
        )

    if execution_status is CampaignExecutionStatus.PREPARED:
        limitations.append(
            "This campaign has not been executed. The record describes the "
            "planned configuration only, contains no hardware measurement, and "
            "supports no hardware claim."
        )

    if execution_status is CampaignExecutionStatus.FIXTURE_EXECUTED:
        limitations.append(
            "This campaign was executed against fixture data, not hardware. It "
            "demonstrates that the capture-to-report path works end to end and "
            "says nothing about how the rig behaves. No study in it is hardware "
            "evidence and no capability may be promoted on it."
        )

    if execution_status is CampaignExecutionStatus.ABORTED:
        limitations.append(
            "This campaign was abandoned before completion for a reason that "
            "was not a campaign gate. Whatever it recorded is partial, and the "
            "questions its unexecuted experiments ask remain open."
        )

    blocked = sorted(
        outcome.experiment_id
        for outcome in outcomes
        if outcome.status is ExperimentOutcomeStatus.BLOCKED_BY_GATE
    )
    if blocked:
        limitations.append(
            "The following experiments were not executed because an earlier "
            f"campaign gate failed: {', '.join(blocked)}. Their questions remain "
            "entirely open."
        )

    if any(plan.subject_is_rig for plan in config.experiments):
        limitations.append(
            "One or more experiments characterize the measurement rig itself "
            "rather than an instrument. Their instrument identifier names the "
            "rig, and their results describe the excitation path, not a "
            "specimen."
        )

    return tuple(limitations)


def build_campaign_record(
    *,
    config: HardwareCampaignConfigV1,
    generated_at: str,
    execution_status: CampaignExecutionStatus | None = None,
    outcomes: Sequence[CampaignExperimentOutcomeV1] = (),
    artifacts: Sequence[ExternalArtifactV1] = (),
    attachment_variation: Sequence[AttachmentVariationV1] = (),
    reciprocity: Sequence[ReciprocityObservationV1] = (),
    mass_loading: Sequence[MassLoadingObservationV1] = (),
    limitations: Sequence[str] | None = None,
) -> HardwareCampaignRecordV1:
    """Assemble the campaign record: what was planned, what ran, what was seen.

    Experiments the caller did not account for are recorded as
    ``NOT_EXECUTED`` rather than omitted, so the record always accounts for
    every experiment its own configuration planned (DO-103 §12 criterion 11).

    ``execution_status`` defaults to what the outcomes support — see
    :func:`campaign_status_for`. A caller may state one instead, for the cases
    the outcomes cannot express on their own (an abandoned campaign, most
    obviously), and :func:`~.validation.validate_campaign_record` refuses one the
    outcomes contradict. A fixture rehearsal cannot be called a hardware
    campaign by choosing the word.
    """
    accounted = {outcome.experiment_id for outcome in outcomes}
    filled = list(outcomes)
    for plan in config.experiments:
        if plan.experiment_id not in accounted:
            filled.append(
                CampaignExperimentOutcomeV1(
                    experiment_id=plan.experiment_id,
                    kind=plan.kind,
                    status=ExperimentOutcomeStatus.NOT_EXECUTED,
                )
            )

    status = (
        campaign_status_for(filled) if execution_status is None else execution_status
    )

    return HardwareCampaignRecordV1(
        campaign_id=config.campaign_id,
        generated_at=require_utc_timestamp(
            generated_at, record="HardwareCampaignRecordV1", field_name="generated_at"
        ),
        execution_status=status,
        config=config,
        outcomes=tuple(filled),
        artifacts=tuple(artifacts),
        attachment_variation=tuple(attachment_variation),
        reciprocity=tuple(reciprocity),
        mass_loading=tuple(mass_loading),
        limitations=tuple(
            default_campaign_limitations(config, status, tuple(filled))
            if limitations is None
            else limitations
        ),
    )


def load_campaign_config(payload: Mapping[str, object]) -> HardwareCampaignConfigV1:
    """Read a campaign configuration document.

    Kept here rather than in a script so the same strict deserialization is what
    every entry point uses. DO-103 §5 requires each acquisition command to state
    its configuration explicitly; an unreadable or partially specified document
    is refused rather than completed from defaults.
    """
    return HardwareCampaignConfigV1.from_dict(payload)


__all__ = [
    "CONTACT_DRIVE_METHOD",
    "ATTACHMENT_GROUP_KIND",
    "build_rig_excitation_context",
    "build_force_channel",
    "build_response_channel",
    "build_campaign_definition",
    "build_campaign_acquisition",
    "build_campaign_outcome",
    "elapsed_seconds_from_first",
    "campaign_status_for",
    "artifact_digest",
    "build_external_artifact",
    "group_runs_by_attachment",
    "group_runs_by_added_mass",
    "summarize_attachment_variation",
    "pair_reciprocity_runs",
    "summarize_reciprocity",
    "summarize_mass_loading",
    "default_campaign_limitations",
    "build_campaign_record",
    "load_campaign_config",
]
