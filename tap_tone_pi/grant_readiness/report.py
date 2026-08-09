# INSTRUMENT CLASS: MEASUREMENT
"""Deterministic grant-readiness reports (DO-102).

Renders an audit and a repeatability study as JSON and Markdown. The same
inputs always produce byte-identical output, so a report can be cited by digest.

The reports are constrained in what they may say. A study built from anything
but ``HARDWARE`` data is labelled as such in its title, its summary line, and
its first limitation, and :func:`render_study_report` raises ``NSF-305`` rather
than emit a document that would let fixture data read as a hardware result.
Nothing here writes the words "calibrated", "accurate to", or "validated
against"; the vocabulary the reports do use is asserted by the test suite.

No market language belongs in this module.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    CapabilityStatus,
    EvidenceOrigin,
    GrantReadinessAuditV1,
    HardwareVerification,
    RepeatabilityMetricV1,
    RepeatabilityStudyV1,
    TechnicalRiskV1,
)
from tap_tone_pi.grant_readiness.errors import (
    GrantReadinessErrorCode,
    RepeatabilityStatisticsError,
)
from tap_tone_pi.grant_readiness.validation import evidence_digest

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
        f"{len(unwitnessed)} capability(ies) are recorded "
        "NOT_VERIFIED_ON_HARDWARE: code exists, but execution on the intended "
        "Raspberry Pi and microphone configuration has not been witnessed. The "
        "preliminary hardware campaign is a deferred execution gate that has "
        "not run."
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
    """Refuse to render a study whose label disagrees with its runs."""
    if not study.runs:
        return
    origins = {run.evidence_origin for run in study.runs}
    if study.evidence_origin is EvidenceOrigin.HARDWARE and origins != {
        EvidenceOrigin.HARDWARE
    }:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
            (
                "refusing to render a report describing non-hardware runs as "
                "hardware evidence"
            ),
            {"study_id": study.study_id},
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
