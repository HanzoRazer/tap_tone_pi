# INSTRUMENT CLASS: MEASUREMENT
"""NSF Project Pitch source material (DO-102).

Assembles repository evidence under the four NSF Project Pitch headings. This
is source material for human drafting, not a submission and not prose to be
pasted forward unread.

Two of the four sections are populated from repository evidence and every
statement in them cites what it rests on — a capability identifier, a risk
identifier, a study, or a digest. The other two are not:

**Market Opportunity** and **Company and Team** contain explicit human-input
placeholders. Code does not invent a market size, a customer count, a pricing
model, or a team credential. A placeholder that survives to submission is a
missing answer, which is the correct failure mode; a fabricated one would not
be detectable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    CapabilityStatus,
    GrantReadinessAuditV1,
    RepeatabilityStudyV1,
    TechnicalRiskV1,
)
from tap_tone_pi.grant_readiness.risks import TECHNICAL_RISKS
from tap_tone_pi.grant_readiness.validation import evidence_digest

# The research question DO-102 organizes evidence around.
CENTRAL_QUESTION = (
    "Can an affordable, portable measurement system produce repeatable, "
    "uncertainty-qualified, reference-valid structural-acoustic measurements "
    "of stringed instruments under realistic shop conditions?"
)

PROPOSAL_FRAME = (
    "Portable Structural-Acoustic Measurement Platform for Instrument "
    "Manufacturing and Research"
)

# Marker for every field a human must supply. Deliberately conspicuous: a
# placeholder that reaches a reviewer should be obvious, not plausible.
HUMAN_INPUT = "[HUMAN INPUT REQUIRED]"

MARKET_PLACEHOLDER_FIELDS: tuple[str, ...] = (
    "customer_segments",
    "customer_discovery_status",
    "market_size_evidence",
    "competing_approaches",
    "pricing_model",
    "commercialization_path",
)

TEAM_PLACEHOLDER_FIELDS: tuple[str, ...] = (
    "principal_investigator",
    "relevant_technical_experience",
    "domain_expertise",
    "advisors_and_collaborators",
    "company_status",
)


@dataclass(frozen=True)
class EvidenceStatement:
    """One claim and the repository evidence it rests on."""

    statement: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class PitchSourcePacketV1:
    """Structured source material for the four NSF Project Pitch sections."""

    packet_id: str
    generated_at: str
    central_question: str = CENTRAL_QUESTION
    proposal_frame: str = PROPOSAL_FRAME
    technology_innovation_evidence: tuple[EvidenceStatement, ...] = ()
    technical_objectives_evidence: tuple[EvidenceStatement, ...] = ()
    market_claim_placeholders: dict[str, str] = field(default_factory=dict)
    team_evidence_placeholders: dict[str, str] = field(default_factory=dict)
    source_digests: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "generated_at": self.generated_at,
            "central_question": self.central_question,
            "proposal_frame": self.proposal_frame,
            "technology_innovation_evidence": [
                s.to_dict() for s in self.technology_innovation_evidence
            ],
            "technical_objectives_evidence": [
                s.to_dict() for s in self.technical_objectives_evidence
            ],
            "market_claim_placeholders": dict(self.market_claim_placeholders),
            "team_evidence_placeholders": dict(self.team_evidence_placeholders),
            "source_digests": dict(self.source_digests),
        }


def _technology_statements(
    audit: GrantReadinessAuditV1, study: RepeatabilityStudyV1 | None
) -> tuple[EvidenceStatement, ...]:
    counts = audit.status_counts
    implemented = [
        c for c in audit.capabilities if c.status is CapabilityStatus.IMPLEMENTED
    ]

    statements = [
        EvidenceStatement(
            (
                f"A working prototype exists. Of {len(audit.capabilities)} "
                f"audited instrument-level capabilities, {counts['IMPLEMENTED']} "
                f"are IMPLEMENTED with code and tests, {counts['EXPERIMENTAL']} "
                f"are EXPERIMENTAL, {counts['PARTIAL']} are PARTIAL, and "
                f"{counts['PLANNED']} are PLANNED."
            ),
            (f"audit:{audit.audit_id}",),
        ),
        EvidenceStatement(
            (
                "The measurement path is end-to-end: audio capture, WAV "
                "persistence, spectral analysis with peak extraction, a "
                "clipping and low-signal quality gate, and structured session "
                "provenance."
            ),
            tuple(
                f"capability:{c.capability_id}"
                for c in implemented
                if c.capability_id
                in {
                    "audio_capture",
                    "wav_persistence",
                    "tap_spectral_analysis",
                    "capture_quality_gate",
                    "session_provenance",
                }
            ),
        ),
        EvidenceStatement(
            (
                "Outputs are contract-governed rather than ad hoc. Structured "
                "results validate against versioned JSON schemas in a registry "
                "with declared ownership, and reanalysis of the same inputs is "
                "deterministic."
            ),
            (
                "capability:viewer_pack_export",
                "capability:measurement_workflow_contracts",
            ),
        ),
        EvidenceStatement(
            (
                "Uncertainty machinery is present rather than aspirational: "
                "GUM-conformant budgets and propagation, and a repeatability "
                "evidence contract predating this work."
            ),
            (
                "capability:uncertainty_quantification",
                "capability:repeatability_evidence",
            ),
        ),
        EvidenceStatement(
            (
                "A guided workflow spine constrains operator procedure "
                "deterministically, which is the mechanism by which a portable "
                "instrument can be used consistently by a non-specialist."
            ),
            ("capability:guided_laboratory",),
        ),
        EvidenceStatement(
            (
                f"No capability has been witnessed executing on the intended "
                f"Raspberry Pi and microphone configuration: "
                f"{audit.hardware_verified_count} of {len(audit.capabilities)} "
                "are hardware-verified. This is stated because a reviewer will "
                "otherwise assume otherwise."
            ),
            (f"audit:{audit.audit_id}",),
        ),
    ]

    if study is not None:
        statements.append(
            EvidenceStatement(
                (
                    "A bounded repeatability experiment is defined and its "
                    "analysis path is proven end to end against deterministic "
                    f"{study.evidence_origin.value.lower()} data: "
                    f"{study.valid_run_count} valid and "
                    f"{study.rejected_run_count} rejected runs, with every "
                    "statistic traceable to the runs that produced it. This is "
                    "not hardware evidence."
                ),
                (f"study:{study.study_id}",),
            )
        )

    return tuple(statements)


def _objective_statements(
    risks: Sequence[TechnicalRiskV1],
) -> tuple[EvidenceStatement, ...]:
    statements = [
        EvidenceStatement(
            (
                "The central Phase I question is whether this system can "
                "produce repeatable, uncertainty-qualified, reference-valid "
                "measurements under realistic shop conditions. The repository "
                "can currently address the first term and not the third."
            ),
            ("question:central",),
        ),
        EvidenceStatement(
            (
                "Repeatability and accuracy are distinguished throughout. "
                "Observed spread describes agreement of the method with "
                "itself; agreement with an accepted reference is unestablished "
                "and cannot be inferred from it."
            ),
            ("risk:R10",),
        ),
    ]
    statements += [
        EvidenceStatement(
            f"{risk.title}: {risk.unresolved_question} {risk.phase_i_relevance}",
            (f"risk:{risk.risk_id}",),
        )
        for risk in risks
    ]
    return tuple(statements)


def build_pitch_source_packet(
    *,
    packet_id: str,
    generated_at: str,
    audit: GrantReadinessAuditV1,
    study: RepeatabilityStudyV1 | None = None,
    risks: Sequence[TechnicalRiskV1] = TECHNICAL_RISKS,
) -> PitchSourcePacketV1:
    """Assemble pitch source material from repository evidence.

    Technology and technical-objective sections are populated and cited. Market
    and team sections are placeholders only; nothing here writes a market or
    team claim.
    """
    digests = {"audit": evidence_digest(audit.to_dict())}
    if study is not None:
        digests["study"] = evidence_digest(study.to_dict())

    return PitchSourcePacketV1(
        packet_id=packet_id,
        generated_at=generated_at,
        technology_innovation_evidence=_technology_statements(audit, study),
        technical_objectives_evidence=_objective_statements(risks),
        market_claim_placeholders={
            field_name: HUMAN_INPUT for field_name in MARKET_PLACEHOLDER_FIELDS
        },
        team_evidence_placeholders={
            field_name: HUMAN_INPUT for field_name in TEAM_PLACEHOLDER_FIELDS
        },
        source_digests=digests,
    )


def render_pitch_source(packet: PitchSourcePacketV1) -> str:
    """Render the packet as Markdown organized under the four NSF headings."""
    lines: list[str] = [
        "# NSF Project Pitch — Source Material",
        "",
        "**This is not a submission.** It is repository evidence organized "
        "under the four Project Pitch headings, for a human to draft from. "
        "Nothing here has been reviewed for NSF fit, and the market and team "
        "sections are deliberately empty.",
        "",
        f"- Packet: `{packet.packet_id}`",
        f"- Generated: {packet.generated_at}",
        f"- Working frame: {packet.proposal_frame}",
        "",
        "## Central question",
        "",
        f"> {packet.central_question}",
        "",
        "## Source digests",
        "",
    ]
    for name, digest in sorted(packet.source_digests.items()):
        lines.append(f"- {name}: `{digest}`")
    lines.append("")

    lines += ["## 1. Technology Innovation", ""]
    for statement in packet.technology_innovation_evidence:
        refs = ", ".join(f"`{r}`" for r in statement.evidence_refs) or "—"
        lines += [f"- {statement.statement}", f"  - Evidence: {refs}"]
    lines.append("")

    lines += [
        "## 2. Technical Objectives and Challenges",
        "",
        "Each unresolved question below is a candidate Phase I objective. None "
        "is closed, and none has a success threshold attached: DO-102 "
        "deliberately sets no target repeatability or agreement figure, because "
        "the baseline observations that would justify one do not exist yet.",
        "",
    ]
    for statement in packet.technical_objectives_evidence:
        refs = ", ".join(f"`{r}`" for r in statement.evidence_refs) or "—"
        lines += [f"- {statement.statement}", f"  - Evidence: {refs}"]
    lines.append("")

    lines += [
        "## 3. Market Opportunity",
        "",
        "Not generated. Every field below requires human input; no market "
        "claim is derivable from this repository, and none has been invented.",
        "",
    ]
    for name in sorted(packet.market_claim_placeholders):
        lines.append(f"- **{name}**: {packet.market_claim_placeholders[name]}")
    lines.append("")

    lines += [
        "## 4. Company and Team",
        "",
        "Not generated. Every field below requires human input.",
        "",
    ]
    for name in sorted(packet.team_evidence_placeholders):
        lines.append(f"- **{name}**: {packet.team_evidence_placeholders[name]}")
    lines.append("")

    return "\n".join(lines)


__all__ = [
    "CENTRAL_QUESTION",
    "PROPOSAL_FRAME",
    "HUMAN_INPUT",
    "MARKET_PLACEHOLDER_FIELDS",
    "TEAM_PLACEHOLDER_FIELDS",
    "EvidenceStatement",
    "PitchSourcePacketV1",
    "build_pitch_source_packet",
    "render_pitch_source",
]
