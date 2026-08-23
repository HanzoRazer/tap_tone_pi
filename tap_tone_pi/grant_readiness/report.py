# INSTRUMENT CLASS: MEASUREMENT
"""Deterministic grant-readiness reports (DO-102).

Renders an audit and a repeatability study as JSON and Markdown. The same
inputs always produce byte-identical output, so a report can be cited by digest.

The reports are constrained in what they may say. A study built from anything
but ``HARDWARE`` data is labelled as such in its title, its summary line, and
its first limitation, and :func:`render_study_report` raises ``NSF-305`` rather
than emit a document that would let fixture data read as a hardware result.
The prose this module *generates* never writes the words "calibrated",
"accurate to", or "validated against"; that generated vocabulary is asserted by
the test suite. Caller-supplied free text — a study's ``limitations`` and the
identifiers and notes carried on its records — is rendered verbatim and is not
sanitised here; keeping such fields free of overclaim language is the
responsibility of whatever constructs the study, not of this renderer.

DO-103 adds the campaign report. It follows the same rules and one more: every
value it shows is marked observed, derived, assumed, or unknown, and a campaign
that has not been executed says so in its title, its banner, and its
limitations rather than reading as an empty result.

No market language belongs in this module.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    AcquisitionRole,
    CampaignExecutionStatus,
    CapabilityStatus,
    EvidenceOrigin,
    GrantReadinessAuditV1,
    HardwareCampaignRecordV1,
    HardwareVerification,
    RepeatabilityMetricV1,
    RepeatabilityStudyV1,
    TechnicalRiskV1,
)
from tap_tone_pi.grant_readiness.errors import (
    RepeatabilityStatisticsError,
)
from tap_tone_pi.grant_readiness.validation import (
    evidence_digest,
    validate_run_acquisition_provenance,
    validate_study_evidence_origin,
    validate_witnessed_hardware_session,
)

# The standard-deviation convention every report states, so a reader never has
# to guess which one produced the number.
SD_CONVENTION = (
    "Standard deviation is the sample standard deviation with Bessel's "
    "correction (n-1), computed by tap_tone_pi.core.statistics."
)

# Fixed in every study report. Repeatability describes agreement of a method
# with itself; accuracy would require a reference this project does not have.
REPEATABILITY_IS_NOT_ACCURACY = (
    "These figures describe repeatability, not accuracy. They say how much "
    "repeated observations varied under the recorded conditions. They do not "
    "say how close any of them is to the true value, because no comparison "
    "against a reference method has been performed."
)


def _origin_label(origin: EvidenceOrigin) -> str:
    return {
        EvidenceOrigin.HARDWARE: "witnessed hardware capture",
        EvidenceOrigin.FIXTURE: "deterministic fixture data (not hardware evidence)",
        EvidenceOrigin.SYNTHETIC: "synthetic audio (not hardware evidence)",
    }[origin]


def _number(value: float) -> str:
    """Format a statistic at six significant figures without trailing noise."""
    text = f"{value:.6g}"
    return text


def canonical_json(payload: Any) -> str:
    """Serialize deterministically: sorted keys, two-space indent, no NaN."""
    return json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"


# ---------------------------------------------------------------------------
# Technical baseline
# ---------------------------------------------------------------------------


def build_audit_report(audit: GrantReadinessAuditV1) -> dict[str, Any]:
    """Return the audit as a JSON-ready report payload with its digest."""
    payload = audit.to_dict()
    return {
        "report_type": "nsf_ttp_technical_baseline",
        "generated_at": audit.generated_at,
        "repository_commit": audit.repository_commit,
        "audit_digest": evidence_digest(payload),
        "audit": payload,
    }


def render_audit_report(audit: GrantReadinessAuditV1) -> str:
    """Render the technical baseline as Markdown."""
    counts = audit.status_counts
    lines: list[str] = [
        "# TTP Technical Baseline",
        "",
        f"- Audit: `{audit.audit_id}`",
        f"- Generated: {audit.generated_at}",
        f"- Repository commit: `{audit.repository_commit or 'unrecorded'}`",
        f"- Audit digest: `{evidence_digest(audit.to_dict())}`",
        f"- Capabilities audited: {len(audit.capabilities)}",
        "",
        "This document records what the repository implements. It records no "
        "measurement accuracy, no calibration status, and no agreement with "
        "any reference method.",
        "",
        "## Status summary",
        "",
        "| Status | Count |",
        "| --- | --- |",
    ]
    for status in CapabilityStatus:
        lines.append(f"| {status.value} | {counts[status.value]} |")

    lines += [
        "",
        f"Capabilities witnessed on the intended hardware: "
        f"**{audit.hardware_verified_count}**.",
        "",
    ]

    for status in CapabilityStatus:
        selected = [c for c in audit.capabilities if c.status is status]
        lines.append(f"## {status.value}")
        lines.append("")
        if not selected:
            lines.append(f"No capability currently carries {status.value} status.")
            lines.append("")
            continue
        for capability in selected:
            lines.append(f"### {capability.name}")
            lines.append("")
            lines.append(f"- Identifier: `{capability.capability_id}`")
            lines.append(f"- Hardware: {capability.hardware_verified.value}")
            if capability.implementation_paths:
                joined = ", ".join(f"`{p}`" for p in capability.implementation_paths)
                lines.append(f"- Implementation: {joined}")
            if capability.test_paths:
                joined = ", ".join(f"`{p}`" for p in capability.test_paths)
                lines.append(f"- Tests: {joined}")
            if capability.evidence_refs:
                joined = ", ".join(f"`{r}`" for r in capability.evidence_refs)
                lines.append(f"- Evidence: {joined}")
            lines.append("")
            lines.append(capability.notes)
            lines.append("")

    lines.append("## Hardware verification status")
    lines.append("")
    unwitnessed = [
        c
        for c in audit.capabilities
        if c.hardware_verified is HardwareVerification.NOT_VERIFIED_ON_HARDWARE
    ]
    lines.append(
        f"**Hardware verification status:** None of the {len(audit.capabilities)} "
        "audited capabilities has been witnessed end-to-end on the intended TTP "
        "hardware configuration during DO-102. Software implementation status "
        "and hardware verification are tracked independently."
    )
    lines.append("")
    lines.append(
        f"{len(unwitnessed)} capability(ies) carry NOT_VERIFIED_ON_HARDWARE: "
        "code exists and a hardware dependency exists, but execution on the "
        "intended Raspberry Pi and microphone configuration has not been "
        "witnessed. The preliminary hardware campaign is a deferred execution "
        "gate that has not run."
    )
    lines.append("")
    for capability in unwitnessed:
        lines.append(f"- `{capability.capability_id}` — {capability.name}")
    lines.append("")

    lines.append("## What this audit does not establish")
    lines.append("")
    for limitation in audit.limitations:
        lines.append(f"- {limitation}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Repeatability study
# ---------------------------------------------------------------------------


def _metric_row(metric: RepeatabilityMetricV1) -> str:
    return (
        f"| {metric.quantity} | {metric.unit} | {metric.sample_count} | "
        f"{_number(metric.mean)} | {_number(metric.median)} | "
        f"{_number(metric.standard_deviation)} | "
        f"{_number(metric.coefficient_of_variation_pct)} | "
        f"{_number(metric.minimum)} | {_number(metric.maximum)} | "
        f"{_number(metric.range_value)} | "
        f"{_number(metric.median_absolute_deviation)} |"
    )


def _guard_origin(study: RepeatabilityStudyV1) -> None:
    """Refuse to render a study whose origin claim the validator would reject.

    Delegates to :func:`validate_study_evidence_origin` and
    :func:`validate_run_acquisition_provenance` so the renderer enforces the
    *exact same* invariants as the validator rather than a second copy of them.
    Two directions of mislabelling are refused — a ``HARDWARE`` label over
    non-hardware runs, and a non-``HARDWARE`` label over hardware runs — and so
    is a ``HARDWARE`` claim that no acquisition provenance backs (DO-103 §5.4).

    That last one matters here specifically. A study can be assembled with
    ``strict=False``, so without this the renderer would be the one place a
    hardware claim could reach a document without the evidence that makes it
    derivable. The renderer must never emit what the validator would reject.
    """
    findings = validate_study_evidence_origin(study)
    for run in study.runs:
        findings.extend(validate_run_acquisition_provenance(run))
    if findings:
        finding = findings[0]
        raise RepeatabilityStatisticsError(
            finding.code,
            f"refusing to render an unsupported origin claim: {finding.message}",
            finding.context,
        )


def build_study_report(study: RepeatabilityStudyV1) -> dict[str, Any]:
    """Return the study as a JSON-ready report payload with its digest."""
    _guard_origin(study)
    payload = study.to_dict()
    return {
        "report_type": "ttp_preliminary_repeatability",
        "generated_at": study.generated_at,
        "evidence_origin": study.evidence_origin.value,
        "is_hardware_evidence": study.is_hardware_evidence,
        "standard_deviation_convention": SD_CONVENTION,
        "repeatability_is_not_accuracy": REPEATABILITY_IS_NOT_ACCURACY,
        "study_digest": evidence_digest(payload),
        "study": payload,
    }


def render_study_report(study: RepeatabilityStudyV1) -> str:
    """Render the preliminary repeatability study as Markdown."""
    _guard_origin(study)
    definition = study.experiment_definition
    environment = definition.environmental_context
    excitation = definition.excitation

    suffix = "" if study.is_hardware_evidence else " (Non-Hardware Evidence)"
    lines: list[str] = [
        f"# Preliminary Repeatability Study{suffix}",
        "",
        f"- Study: `{study.study_id}`",
        f"- Experiment: `{definition.experiment_id}`",
        f"- Generated: {study.generated_at}",
        f"- Evidence origin: **{study.evidence_origin.value}** — "
        f"{_origin_label(study.evidence_origin)}",
        f"- Study digest: `{evidence_digest(study.to_dict())}`",
        "",
    ]

    if not study.is_hardware_evidence:
        lines += [
            "> **This study is not hardware evidence.** It is built from "
            f"{study.evidence_origin.value.lower()} data and demonstrates that "
            "the contract and the analysis path work. It says nothing about "
            "how the instrument behaves under shop conditions. The preliminary "
            "hardware campaign is a deferred execution gate that has not run.",
            "",
        ]

    lines += [
        "## Experiment definition",
        "",
        f"- Instrument: `{definition.instrument_id}`",
        f"- Measurement point: `{definition.measurement_point_id}`",
        f"- Operator: `{definition.operator_id}`",
        f"- Planned repeats: {definition.planned_repeat_count}",
        f"- Analysis profile: `{definition.analysis_profile}`",
        f"- Sensor position: {definition.sensor_position or 'unrecorded'}",
        f"- Support condition: {definition.support_condition or 'unrecorded'}",
        "",
        "### Excitation",
        "",
        f"- Method: `{excitation.excitation_method}`",
        f"- Device: {excitation.excitation_device_id or 'unrecorded'}",
        f"- Drive point: {excitation.excitation_point or 'unrecorded'}",
        f"- Contact condition: {excitation.contact_condition or 'unrecorded'}",
        f"- Fixture: {excitation.fixture_id or 'unrecorded'}",
        f"- Excitation contract: {excitation.excitation_contract_id or 'none'}",
        "",
        "### Recorded conditions",
        "",
        "Conditions are recorded as supplied and are not corrected for. A field "
        "shown as unknown was not supplied and remains unknown.",
        "",
        f"- Temperature (C): {environment.temp_c if environment.temp_c is not None else 'unknown'}",
        f"- Relative humidity (%): {environment.rh_pct if environment.rh_pct is not None else 'unknown'}",
        f"- Specimen moisture (%): "
        f"{environment.specimen_moisture_pct if environment.specimen_moisture_pct is not None else 'unknown'}",
        f"- Ambient noise: {environment.ambient_noise_note or 'unknown'}",
        "",
        "## Run accounting",
        "",
        f"- Runs recorded: {len(study.runs)}",
        f"- Valid: {study.valid_run_count}",
        f"- Rejected: {study.rejected_run_count}",
        "",
    ]

    if study.rejected_run_count:
        lines += ["| Rejection reason | Count |", "| --- | --- |"]
        for reason, count in sorted(study.rejection_counts.items()):
            if count:
                lines.append(f"| {reason} | {count} |")
        lines.append("")

    lines += [
        "| Run | Valid | Reason | Captured | Source artifacts |",
        "| --- | --- | --- | --- | --- |",
    ]
    for run in study.runs:
        artifacts = ", ".join(f"`{a}`" for a in run.source_artifact_ids) or "none"
        reason = run.rejection_reason.value if run.rejection_reason else "—"
        lines.append(
            f"| `{run.run_id}` | {'yes' if run.valid else 'no'} | {reason} | "
            f"{run.captured_at} | {artifacts} |"
        )
    lines.append("")

    lines += [
        "## Repeatability metrics",
        "",
        REPEATABILITY_IS_NOT_ACCURACY,
        "",
        SD_CONVENTION,
        "",
    ]

    if not study.metrics:
        lines += [
            "No quantity had two or more valid observations, so no statistic "
            "is reported. This is a result, not an omission.",
            "",
        ]
    else:
        lines += [
            "| Quantity | Unit | n | Mean | Median | SD | CV% | Min | Max | Range | MAD |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        lines += [_metric_row(metric) for metric in study.metrics]
        lines.append("")
        lines.append("### Source runs")
        lines.append("")
        for metric in study.metrics:
            joined = ", ".join(f"`{r}`" for r in metric.source_run_ids)
            lines.append(f"- **{metric.quantity}** ({metric.sample_count}): {joined}")
        lines.append("")

    if study.referenced_repeatability_evidence_ids:
        lines += ["## Cross-referenced evidence", ""]
        lines.append(
            "The following DO-085 repeatability_evidence_v1 records cover the "
            "same runs. They are referenced for traceability; this study does "
            "not inherit their acceptance gate, and that gate is not an NSF "
            "success criterion."
        )
        lines.append("")
        for reference in study.referenced_repeatability_evidence_ids:
            lines.append(f"- `{reference}`")
        lines.append("")

    lines += ["## Limitations", ""]
    for limitation in study.limitations:
        lines.append(f"- {limitation}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hardware campaign (DO-103)
# ---------------------------------------------------------------------------

# Every value in a campaign report is one of four things, and a reader should
# never have to work out which. DO-103 §5 requires the distinction to be carried
# in the document rather than left to the prose around it.
EVIDENCE_STATUS_LEGEND = (
    "Each value below is marked **observed** (read from a recorded "
    "measurement), **derived** (computed from observed values by a stated "
    "rule), **assumed** (taken from a specification rather than measured), or "
    "**unknown** (not recorded). An unknown is never filled in from a default."
)

# The one risk this campaign structurally cannot touch, stated in every report
# so it is never quietly dropped from the evidence package.
REFERENCE_AGREEMENT_REMAINS_OPEN = (
    "R10 reference-method agreement remains entirely open. Every figure in this "
    "campaign compares this instrument against itself; no external reference "
    "method has been used, so no statement about agreement with one is "
    "supported."
)

# What p/F is, and what it is not, in every campaign document (DO-103 §6.6).
ACOUSTIC_TRANSFER_NOTE = (
    "The transfer quantity is acoustic pressure per unit measured force. It is "
    "not mobility, accelerance, or receptance: each of those requires the "
    "response to be a mechanical motion of the structure, and the response here "
    "is a microphone."
)


# What a campaign's title says about itself, so the distinction between
# rehearsing the analysis path and running the rig survives being read alone.
CAMPAIGN_TITLE_SUFFIX = {
    CampaignExecutionStatus.PREPARED: " (Not Executed)",
    CampaignExecutionStatus.FIXTURE_EXECUTED: " (Fixture Rehearsal — Not Hardware)",
    CampaignExecutionStatus.HARDWARE_EXECUTED: "",
    CampaignExecutionStatus.HALTED_AT_GATE: " (Halted at a Campaign Gate)",
    CampaignExecutionStatus.ABORTED: " (Abandoned)",
}

CAMPAIGN_BANNER = {
    CampaignExecutionStatus.PREPARED: (
        "> **This campaign has not been executed.** The document below describes "
        "a planned configuration and the structure results will be reported in. "
        "It contains no hardware measurement, no witnessed session, and no "
        "repeatability, reciprocity, or mass-loading result, and it supports no "
        "hardware claim of any kind."
    ),
    CampaignExecutionStatus.FIXTURE_EXECUTED: (
        "> **No hardware evidence.** The experiments below were executed against "
        "fixture or synthetic data. That demonstrates the campaign path end to "
        "end and says nothing about how the rig behaves: no study here is "
        "hardware evidence, and no capability may be promoted on it."
    ),
    CampaignExecutionStatus.HALTED_AT_GATE: (
        "> **This campaign was halted at a gate.** An experiment that gates the "
        "ones after it did not produce usable evidence, so the downstream "
        "experiments were not run. That is a result about the measurement "
        "architecture, and the questions those experiments ask remain open."
    ),
    CampaignExecutionStatus.ABORTED: (
        "> **This campaign was abandoned before completion**, for a reason that "
        "was not a campaign gate. Whatever it recorded is partial."
    ),
}


def _shown(value: Any, status: str = "observed") -> str:
    """Render one field with its evidence status, or as unknown."""
    if value is None or value == "":
        return "unknown"
    return f"{value} ({status})"


def _campaign_studies(
    record: HardwareCampaignRecordV1, studies: Sequence[RepeatabilityStudyV1]
) -> dict[str, RepeatabilityStudyV1]:
    """Index supplied studies by identity, refusing any the validator would."""
    indexed: dict[str, RepeatabilityStudyV1] = {}
    for study in studies:
        _guard_origin(study)
        indexed[study.study_id] = study
    return indexed


def build_campaign_report(
    record: HardwareCampaignRecordV1,
    studies: Sequence[RepeatabilityStudyV1] = (),
) -> dict[str, Any]:
    """Return the campaign as a JSON-ready report payload with its digest.

    Studies are referenced by identity and digest rather than copied, so the
    campaign document stays an index over evidence instead of a second copy of
    it that could drift from the first.
    """
    indexed = _campaign_studies(record, studies)
    payload = record.to_dict()
    return {
        "report_type": "ttp_hardware_measurement_campaign",
        "generated_at": record.generated_at,
        "campaign_id": record.campaign_id,
        "execution_status": record.execution_status.value,
        "is_executed": record.is_executed,
        "is_hardware_evidence": record.is_hardware_evidence,
        "witnessed_experiment_ids": list(record.witnessed_experiment_ids),
        "acoustic_transfer_note": ACOUSTIC_TRANSFER_NOTE,
        "reference_agreement_remains_open": REFERENCE_AGREEMENT_REMAINS_OPEN,
        "repeatability_is_not_accuracy": REPEATABILITY_IS_NOT_ACCURACY,
        "standard_deviation_convention": SD_CONVENTION,
        "campaign_digest": evidence_digest(payload),
        "study_digests": {
            study_id: evidence_digest(study.to_dict())
            for study_id, study in sorted(indexed.items())
        },
        "campaign": payload,
    }


def _rig_section(record: HardwareCampaignRecordV1) -> list[str]:
    excitation = record.config.excitation
    lines = [
        "## Rig configuration",
        "",
        "The rig is part of the measurement instrument. Changing any part named "
        "here is a configuration change, not a repeat.",
        "",
        "| Part | Identity |",
        "| --- | --- |",
    ]
    labels = {
        "rig_configuration_id": "Rig configuration",
        "excitation_device_id": "Shaker",
        "stinger_id": "Stinger",
        "contact_tip_id": "Contact tip",
        "fixture_id": "Fixture",
    }
    for field_name, label in labels.items():
        lines.append(f"| {label} | {_shown(excitation.rig_identity[field_name])} |")
    lines += [
        f"| Excitation method | {_shown(excitation.excitation_method)} |",
        f"| Drive point | {_shown(excitation.excitation_point)} |",
        f"| Contact condition | {_shown(excitation.contact_condition)} |",
        f"| Support condition | {_shown(record.config.support_condition)} |",
        "",
    ]
    return lines


def _channel_rows(channel) -> list[str]:
    traceability = channel.calibration_traceability.value
    sensitivity = (
        f"{channel.sensitivity_value} {channel.sensitivity_unit}"
        if channel.sensitivity_is_recorded
        else None
    )
    return [
        f"| Sensor | {_shown(channel.sensor_id)} |",
        f"| Channel index | {_shown(channel.channel_index)} |",
        f"| Quantity | {_shown(channel.quantity)} |",
        f"| Unit | {_shown(channel.unit)} |",
        f"| Sensitivity | {_shown(sensitivity, 'assumed')} |",
        f"| Calibration traceability | {_shown(traceability)} |",
        f"| Calibration reference | {_shown(channel.calibration_reference)} |",
        f"| Gain setting | {_shown(channel.gain_setting)} |",
    ]


def _channels_section(record: HardwareCampaignRecordV1) -> list[str]:
    config = record.config
    force = config.force_channel
    response = next(iter(config.channels_for(AcquisitionRole.RESPONSE)), None)

    lines = ["## Force input and acoustic response", "", ACOUSTIC_TRANSFER_NOTE, ""]

    if force is None:
        lines += [
            "No channel records a measured force. The excitation is commanded "
            "rather than observed, and no transfer function from this "
            "configuration has a measured input.",
            "",
        ]
    else:
        lines += ["### Force input (reference channel)", "", "| Field | Value |"]
        lines += ["| --- | --- |"]
        lines += _channel_rows(force)
        lines += [
            "",
            "Force is measured here. Measured is not traceable: a sensitivity "
            "taken from a specification supports the relative behaviour of the "
            "recorded values and does not establish the newton they are scaled "
            "to against any standard.",
            "",
        ]

    if response is None:
        lines += ["No response channel is recorded.", ""]
    else:
        lines += ["### Acoustic response", "", "| Field | Value |", "| --- | --- |"]
        lines += _channel_rows(response)
        lines.append("")

    if force is not None and response is not None:
        lines += [
            f"Derived transfer unit: **{response.unit}/{force.unit}** (derived "
            "from the recorded channel pair, not assumed).",
            "",
        ]
    return lines


def _accounting_section(record: HardwareCampaignRecordV1) -> list[str]:
    lines = [
        "## Experiment accounting",
        "",
        "Every planned experiment appears here. An experiment that did not run "
        "because an earlier gate failed names the gate that stopped it; that is "
        "a result, not a gap. An experiment that did run names what it ran "
        "against, so *executed* is never read without *against what*.",
        "",
        "| Experiment | Kind | Status | Evidence origin | Witnessed | Study | "
        "Blocked by |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for outcome in record.outcomes:
        study = f"`{outcome.study_id}`" if outcome.study_id else "—"
        blocked = (
            f"`{outcome.blocked_by_experiment_id}`"
            if outcome.blocked_by_experiment_id
            else "—"
        )
        origin = outcome.evidence_origin.value if outcome.evidence_origin else "—"
        lines.append(
            f"| `{outcome.experiment_id}` | {outcome.kind.value} | "
            f"{outcome.status.value} | {origin} | "
            f"{'yes' if outcome.witnessed else 'no'} | {study} | {blocked} |"
        )
    lines.append("")
    return lines


def _study_sections(
    record: HardwareCampaignRecordV1, indexed: dict[str, RepeatabilityStudyV1]
) -> list[str]:
    lines = ["## Repeatability by experiment", ""]
    if not indexed:
        lines += [
            "No study accompanies this campaign, so no repeatability figure is "
            "reported. Nothing is inferred from the absence.",
            "",
        ]
        return lines

    lines += [REPEATABILITY_IS_NOT_ACCURACY, "", SD_CONVENTION, ""]
    for outcome in record.outcomes:
        study = indexed.get(outcome.study_id or "")
        if study is None:
            continue
        lines += [
            f"### {outcome.experiment_id} — {outcome.kind.value}",
            "",
            f"- Study: `{study.study_id}`",
            f"- Study digest: `{evidence_digest(study.to_dict())}`",
            f"- Evidence origin: **{study.evidence_origin.value}**",
            f"- Runs: {len(study.runs)} recorded, {study.valid_run_count} valid, "
            f"{study.rejected_run_count} rejected",
            "",
        ]
        if study.metrics:
            lines += [
                "| Quantity | Unit | n | Mean | Median | SD | CV% | Min | Max | "
                "Range | MAD |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
            lines += [_metric_row(metric) for metric in study.metrics]
        else:
            lines.append(
                "No quantity had two or more valid observations, so no statistic "
                "is reported. This is a result, not an omission."
            )
        lines.append("")
    return lines


def _attachment_section(record: HardwareCampaignRecordV1) -> list[str]:
    lines = [
        "## Detach and re-attach variation",
        "",
        "Repeats that never broke contact are summarized per attachment. The "
        "spread *between* attachments is taken over each attachment's own mean, "
        "and the two are never combined.",
        "",
    ]
    if not record.attachment_variation:
        lines += ["Not observed: no run records an attachment identity.", ""]
        return lines

    for variation in record.attachment_variation:
        lines += [
            f"### {variation.quantity} ({variation.unit})",
            "",
            f"- Attachments: {variation.attachment_count} "
            f"({', '.join(f'`{a}`' for a in variation.attachment_ids)})",
            "",
        ]
        if variation.within_attachment_metrics:
            lines += [
                "| Attachment | n | Mean | SD | CV% |",
                "| --- | --- | --- | --- | --- |",
            ]
            for metric in variation.within_attachment_metrics:
                lines.append(
                    f"| `{metric.metric_id}` | {metric.sample_count} | "
                    f"{_number(metric.mean)} | {_number(metric.standard_deviation)} | "
                    f"{_number(metric.coefficient_of_variation_pct)} |"
                )
            lines.append("")
        spread = variation.between_attachment_spread
        if spread is None:
            lines += [
                "Between-attachment spread is not observable: fewer than two "
                "attachments produced a value.",
                "",
            ]
        else:
            lines += [
                f"Between-attachment spread (derived over {spread.group_count} "
                "attachment means):",
                "",
                f"- Mean: {_number(spread.mean)} {spread.unit}",
                f"- SD: {_number(spread.standard_deviation)} {spread.unit}",
                f"- CV: {_number(spread.coefficient_of_variation_pct)}%",
                f"- Range: {_number(spread.range_value)} {spread.unit}",
                "",
            ]
        if variation.unsummarized_attachment_ids:
            joined = ", ".join(f"`{a}`" for a in variation.unsummarized_attachment_ids)
            lines += [
                f"Attachments with fewer than two valid observations: {joined}. "
                "They contribute a mean to the between-attachment spread and no "
                "within-attachment statistic.",
                "",
            ]
    return lines


def _reciprocity_section(record: HardwareCampaignRecordV1) -> list[str]:
    lines = [
        "## Reciprocity",
        "",
        "Reported without a threshold. DO-103 sets no acceptance figure for "
        "reciprocity, and a large residual is a finding about the measurement "
        "architecture rather than a failed run.",
        "",
    ]
    if not record.reciprocity:
        lines += ["Not executed: no reciprocity pair was recorded.", ""]
        return lines

    lines += [
        "| Pair | Forward run | Reverse run | Forward | Reverse | Residual | "
        "Relative | Coh. fwd | Coh. rev | Freq fwd (Hz) | Freq rev (Hz) | "
        "Freq gap (Hz) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for observation in record.reciprocity:
        relative = (
            _number(observation.relative_residual)
            if observation.relative_residual is not None
            else "unknown"
        )
        forward_coh = (
            _number(observation.forward_coherence)
            if observation.forward_coherence is not None
            else "unknown"
        )
        reverse_coh = (
            _number(observation.reverse_coherence)
            if observation.reverse_coherence is not None
            else "unknown"
        )
        forward_hz = (
            _number(observation.forward_evaluation_frequency_hz)
            if observation.forward_evaluation_frequency_hz is not None
            else "unknown"
        )
        reverse_hz = (
            _number(observation.reverse_evaluation_frequency_hz)
            if observation.reverse_evaluation_frequency_hz is not None
            else "unknown"
        )
        mismatch = (
            _number(observation.frequency_mismatch_hz)
            if observation.frequency_mismatch_hz is not None
            else "unknown"
        )
        lines.append(
            f"| {observation.forward_drive_point_id}→"
            f"{observation.forward_response_point_id} | "
            f"`{observation.forward_run_id}` | `{observation.reverse_run_id}` | "
            f"{_number(observation.forward_value)} | "
            f"{_number(observation.reverse_value)} | "
            f"{_number(observation.absolute_residual)} | {relative} | "
            f"{forward_coh} | {reverse_coh} | {forward_hz} | {reverse_hz} | "
            f"{mismatch} |"
        )
    lines += [
        "",
        "Residuals are in the quantity's own unit; the relative residual is the "
        "residual over the mean magnitude of the two directions (derived). Each "
        "direction keeps its own coherence: a residual observed where one "
        "direction was poorly coherent is not the same finding as the same "
        "residual where both were strong.",
        "",
        "Each direction also keeps its own evaluation frequency, and the gap "
        "between them is derived. Where that gap is non-zero the residual spans "
        "two slightly different frequencies, which is a property of the "
        "comparison a reader should see before reading the residual. No limit is "
        "placed on it here.",
        "",
    ]
    return lines


def _mass_loading_section(record: HardwareCampaignRecordV1) -> list[str]:
    lines = [
        "## Mass-loading challenge",
        "",
        "Reported without a threshold. The measured mass is what every delta is "
        "computed from; an intended mass is recorded beside it and never "
        "substituted for it.",
        "",
    ]
    if not record.mass_loading:
        lines += ["Not executed: no mass challenge was recorded.", ""]
        return lines

    lines += [
        "| Challenge | Added mass (g) | Intended (g) | Location | Baseline mean "
        "(n) | Loaded mean (n) | Delta | Relative % |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for observation in record.mass_loading:
        nominal = (
            _number(observation.nominal_added_mass_g)
            if observation.nominal_added_mass_g is not None
            else "unknown"
        )
        relative = (
            _number(observation.relative_delta_pct)
            if observation.relative_delta_pct is not None
            else "unknown"
        )
        baseline = observation.baseline_metric
        loaded = observation.loaded_metric
        lines.append(
            f"| `{observation.mass_challenge_id}` | "
            f"{_number(observation.added_mass_g)} | {nominal} | "
            f"{observation.mass_location_id or 'unknown'} | "
            f"{_number(baseline.mean)} ({baseline.sample_count}) | "
            f"{_number(loaded.mean)} ({loaded.sample_count}) | "
            f"{_number(observation.absolute_delta)} | {relative} |"
        )
    lines += [
        "",
        "The delta keeps its sign: which way the quantity moved under added "
        "mass is physical information. Read each delta against the spread of "
        "the groups it was computed from — a difference smaller than that "
        "spread is not a detection.",
        "",
    ]
    return lines


def _rejected_runs_section(indexed: dict[str, RepeatabilityStudyV1]) -> list[str]:
    lines = [
        "## Failed and abandoned runs",
        "",
        "Rejected runs stay in the evidence. They are excluded from the "
        "statistics and included in the accounting, and none of them is deleted "
        "because of what it showed.",
        "",
    ]
    rows: list[str] = []
    for study_id in sorted(indexed):
        for run in indexed[study_id].runs:
            if run.valid:
                continue
            reason = run.rejection_reason.value if run.rejection_reason else "unknown"
            rows.append(
                f"| `{study_id}` | `{run.run_id}` | {reason} | {run.captured_at} |"
            )
    if not rows:
        lines += ["No run in the supplied studies was rejected.", ""]
        return lines
    lines += ["| Study | Run | Reason | Captured |", "| --- | --- | --- | --- |"]
    lines += rows
    lines.append("")
    return lines


def _artifact_section(record: HardwareCampaignRecordV1) -> list[str]:
    lines = [
        "## Retained raw artifacts",
        "",
        "Raw measurements are retained outside this repository. The digest is "
        "the durable identity; the locator is where a copy may currently be "
        "found and is not what identifies it.",
        "",
    ]
    if not record.artifacts:
        lines += ["No raw artifact is registered for this campaign.", ""]
        return lines
    lines += [
        "| Artifact | Kind | SHA-256 | Bytes | Run | Locator |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for artifact in record.artifacts:
        lines.append(
            f"| `{artifact.artifact_id}` | {artifact.kind} | `{artifact.sha256}` | "
            f"{artifact.byte_count} | `{artifact.capture_run_id or 'unknown'}` | "
            f"`{artifact.storage_locator}` |"
        )
    lines.append("")
    return lines


def _promotion_section(
    record: HardwareCampaignRecordV1, indexed: dict[str, RepeatabilityStudyV1]
) -> list[str]:
    lines = [
        "## Capability promotion evidence",
        "",
        "This report promotes nothing. It states what the campaign's evidence "
        "would support, and promotion remains a separate, per-capability "
        "decision requiring a witnessed session, preserved artifacts, evidence "
        "references, the exercising experiment named in the capability's notes, "
        "and the inventory and frozen baseline changed together.",
        "",
    ]
    witnessed = sorted(
        study_id
        for study_id, study in indexed.items()
        if not validate_witnessed_hardware_session(study)
    )
    if witnessed:
        joined = ", ".join(f"`{study_id}`" for study_id in witnessed)
        lines += [
            f"Studies meeting the witnessed-session standard: {joined}.",
            "",
        ]
    else:
        lines += [
            "No study in this campaign meets the witnessed-session standard, so "
            "no capability is eligible for promotion off "
            "`NOT_VERIFIED_ON_HARDWARE` on this evidence.",
            "",
        ]
    return lines


def _risk_section(record: HardwareCampaignRecordV1) -> list[str]:
    lines = ["## Technical risks", "", REFERENCE_AGREEMENT_REMAINS_OPEN, ""]
    if not record.is_hardware_evidence:
        lines += [
            "No risk is narrowed by this campaign: no experiment in it ran "
            "against hardware. Excitation variability, contact variability, "
            "sensor positioning, environment, operator variability, and "
            "between-session repeatability all remain exactly as open as they "
            "were.",
            "",
        ]
    else:
        lines += [
            "Only the risks an executed experiment actually addressed may be "
            "narrowed, and only in the risk register itself. This section does "
            "not alter risk states.",
            "",
        ]
    return lines


def render_campaign_report(
    record: HardwareCampaignRecordV1,
    studies: Sequence[RepeatabilityStudyV1] = (),
) -> str:
    """Render the hardware characterization campaign as Markdown.

    The document reports what happened and refuses to imply more. A campaign
    that has not been executed says so in its title and its first paragraph; an
    experiment that was blocked names the gate that blocked it; and no section
    compares any observed value against a limit.
    """
    indexed = _campaign_studies(record, studies)
    suffix = CAMPAIGN_TITLE_SUFFIX[record.execution_status]

    lines: list[str] = [
        f"# Hardware Measurement Campaign{suffix}",
        "",
        f"- Campaign: `{record.campaign_id}`",
        f"- Generated: {record.generated_at}",
        f"- Execution status: **{record.execution_status.value}**",
        f"- Operator: `{record.config.operator_id}`",
        f"- Campaign digest: `{evidence_digest(record.to_dict())}`",
        "",
        EVIDENCE_STATUS_LEGEND,
        "",
    ]

    banner = CAMPAIGN_BANNER.get(record.execution_status)
    if banner is not None:
        lines += [banner, ""]

    lines += _rig_section(record)
    lines += _channels_section(record)
    lines += _accounting_section(record)
    lines += _study_sections(record, indexed)
    lines += _attachment_section(record)
    lines += _reciprocity_section(record)
    lines += _mass_loading_section(record)
    lines += _rejected_runs_section(indexed)
    lines += _artifact_section(record)
    lines += _promotion_section(record, indexed)
    lines += _risk_section(record)

    lines += ["## Limitations", ""]
    for limitation in record.limitations:
        lines.append(f"- {limitation}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Technical risks
# ---------------------------------------------------------------------------


def render_risk_register(risks: Sequence[TechnicalRiskV1]) -> str:
    """Render the Phase I technical-risk register as Markdown."""
    lines: list[str] = [
        "# Phase I Technical Risks",
        "",
        "Each entry states what is known, what is not, and what would settle "
        "it. An open risk is not a defect; it is the reason Phase I research "
        "is needed.",
        "",
    ]
    for risk in risks:
        lines += [
            f"## {risk.risk_id} — {risk.title}",
            "",
            f"- Status: {risk.status.value}",
            "",
            f"**What is known.** {risk.current_evidence}",
            "",
            f"**What is unknown.** {risk.unresolved_question}",
            "",
            f"**Why Phase I needs it.** {risk.phase_i_relevance}",
            "",
            f"**Proposed test.** {risk.proposed_validation_method}",
            "",
        ]
    return "\n".join(lines)


__all__ = [
    "SD_CONVENTION",
    "REPEATABILITY_IS_NOT_ACCURACY",
    "canonical_json",
    "build_audit_report",
    "render_audit_report",
    "build_study_report",
    "render_study_report",
    "render_risk_register",
]
