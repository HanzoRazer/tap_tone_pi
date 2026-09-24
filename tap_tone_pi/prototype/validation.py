# INSTRUMENT CLASS: MEASUREMENT
"""Read-only validation for a ``ttp_prototype_run_v1`` record.

Every function here reads a record and returns findings; nothing mutates a
record, repairs a claim, or promotes a component. The invariants are the
P01-P10 boundary of TTP-PROTOTYPE-001, and each is a check on what a run
*claims* against what it *carries* — never a judgement of a physical quantity,
for which this order forbids inventing a threshold.

The record is validated as a mapping rather than parsed into a dataclass: the
checker's job is to report what an externally authored JSON says, so a
malformed field must become a finding, not an exception. Structural typing is
enforced separately by the JSON Schema; this module holds the cross-field rules
a schema cannot express.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from tap_tone_pi.grant_readiness.contracts import ExternalArtifactV1
from tap_tone_pi.grant_readiness.errors import GrantReadinessError
from tap_tone_pi.grant_readiness.validation import validate_external_artifact
from tap_tone_pi.prototype.contracts import (
    STAGE_EXCITATION_MODE,
    ExcitationMode,
    PrototypeStage,
)

# Statuses that mean a run stopped and must say why, rather than an absence.
_HALTED_STATUSES = {"HALTED_AT_GATE", "BLOCKED_BY_GATE"}


@dataclass(frozen=True)
class PrototypeFinding:
    """One problem found in a prototype run. Never carries a host path."""

    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.context:
            payload["context"] = {k: self.context[k] for k in sorted(self.context)}
        return payload


def promotion_notes() -> tuple[str, ...]:
    """The standing notes this checker always reports and never overrides.

    P05 and P10: a prototype run is evidence of what the prototype chain did.
    It never qualifies a component and never promotes production/PCB readiness.
    Those are separate decisions this tool does not make, and the record carries
    no field through which it could.
    """
    return (
        (
            "prototype evidence does not qualify any component: a candidate "
            "remains a candidate, whatever a run observed"
        ),
        (
            "prototype evidence does not promote custom-PCB or production "
            "readiness; that is a separate decision this tool does not make"
        ),
    )


def _stage(payload: Mapping[str, Any]) -> PrototypeStage | None:
    try:
        return PrototypeStage(payload.get("stage"))
    except ValueError:
        return None


def _mode(excitation: Mapping[str, Any]) -> ExcitationMode | None:
    try:
        return ExcitationMode(excitation.get("excitation_mode"))
    except ValueError:
        return None


def _validate_stage_excitation(
    stage: PrototypeStage | None, excitation: Mapping[str, Any]
) -> list[PrototypeFinding]:
    """P01/P03: the stage bounds the excitation a run may claim."""
    findings: list[PrototypeFinding] = []
    if stage is None:
        return findings

    mode = _mode(excitation)
    expected = STAGE_EXCITATION_MODE[stage]
    if mode is not None and mode is not expected:
        findings.append(
            PrototypeFinding(
                "PROTO_STAGE_EXCITATION_CONFLICT",
                (
                    f"stage {stage.value} requires {expected.value} excitation but "
                    f"the run records {mode.value}"
                ),
                {"stage": stage.value, "excitation_mode": mode.value},
            )
        )

    controlled_fields = ("output_device_id", "amplifier_id", "exciter_id")
    if stage is PrototypeStage.R0:
        # P01: a manual acquisition cannot carry a controlled-excitation chain.
        if excitation.get("commanded_amplitude") is not None:
            findings.append(
                PrototypeFinding(
                    "PROTO_STAGE_EXCITATION_CONFLICT",
                    "R0 is a manual tap and cannot record a commanded amplitude",
                    {"stage": "R0"},
                )
            )
        if excitation.get("emission_provenance") is not None:
            findings.append(
                PrototypeFinding(
                    "PROTO_STAGE_EXCITATION_CONFLICT",
                    "R0 is a manual tap and cannot carry emission provenance",
                    {"stage": "R0"},
                )
            )
        present = [f for f in controlled_fields if excitation.get(f) is not None]
        if present:
            findings.append(
                PrototypeFinding(
                    "PROTO_STAGE_EXCITATION_CONFLICT",
                    (
                        "R0 is a manual tap and cannot name a controlled-excitation "
                        f"chain: {', '.join(present)}"
                    ),
                    {"stage": "R0", "fields": present},
                )
            )

    if stage is PrototypeStage.R2:
        # P03: the commanded loop must be able to say what it emitted.
        emission = excitation.get("emission_provenance")
        if not isinstance(emission, Mapping) or not emission.get("emitted_signal_id"):
            findings.append(
                PrototypeFinding(
                    "PROTO_EMISSION_PROVENANCE_MISSING",
                    (
                        "R2 is a commanded closed loop but records no emission "
                        "provenance (an emitted_signal_id)"
                    ),
                    {"stage": "R2"},
                )
            )
        if excitation.get("output_device_id") is None:
            findings.append(
                PrototypeFinding(
                    "PROTO_EMISSION_PROVENANCE_MISSING",
                    "R2 commands a signal but names no output device it was emitted through",
                    {"stage": "R2"},
                )
            )

    return findings


def _validate_added_mass(
    stage: PrototypeStage | None, payload: Mapping[str, Any]
) -> list[PrototypeFinding]:
    """P02: an R1 run is the known-mass challenge and must measure the mass."""
    if stage is not PrototypeStage.R1:
        return []
    added = payload.get("added_mass")
    if not isinstance(added, Mapping):
        return [
            PrototypeFinding(
                "PROTO_ADDED_MASS_MISSING",
                "R1 is the known-mass challenge but records no added mass",
                {"stage": "R1"},
            )
        ]
    mass = added.get("added_mass_g")
    if not isinstance(mass, (int, float)) or isinstance(mass, bool) or mass <= 0:
        return [
            PrototypeFinding(
                "PROTO_ADDED_MASS_MISSING",
                (
                    "R1 records an added mass that is not a positive measured "
                    f"quantity: {mass!r}"
                ),
                {"stage": "R1"},
            )
        ]
    return []


def _validate_force_boundary(payload: Mapping[str, Any]) -> list[PrototypeFinding]:
    """P04: a measured-force claim must carry a force chain that could back it."""
    findings: list[PrototypeFinding] = []
    force = payload.get("force")
    if not isinstance(force, Mapping):
        return findings
    if not force.get("measured_force_claimed"):
        return findings

    chain = force.get("force_chain")
    if not isinstance(chain, Mapping) or not chain.get("force_sensor_id"):
        findings.append(
            PrototypeFinding(
                "PROTO_FORCE_CLAIM_UNSUBSTANTIATED",
                (
                    "the run claims measured force but carries no force chain; a "
                    "commanded electrical signal is not an applied mechanical force"
                ),
            )
        )
        return findings

    if chain.get("calibration_traceability") == "TRACEABLE" and not chain.get(
        "calibration_reference"
    ):
        findings.append(
            PrototypeFinding(
                "PROTO_FORCE_CLAIM_UNSUBSTANTIATED",
                (
                    "the force chain claims traceable calibration but names no "
                    "calibration reference"
                ),
            )
        )
    return findings


def _validate_evidence_and_artifacts(
    payload: Mapping[str, Any],
) -> list[PrototypeFinding]:
    """P06/P08/P09 plus the executed/origin agreement the others rest on."""
    findings: list[PrototypeFinding] = []
    status = payload.get("status")
    origin = payload.get("evidence_origin")
    witnessed = bool(payload.get("witnessed", False))
    artifacts = payload.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, list) else []

    if status == "EXECUTED" and origin is None:
        findings.append(
            PrototypeFinding(
                "PROTO_EXECUTED_WITHOUT_ORIGIN",
                "an executed run names no evidence origin",
            )
        )

    if status == "NOT_EXECUTED" and origin is not None:
        findings.append(
            PrototypeFinding(
                "PROTO_NOT_EXECUTED_CLAIMS_ORIGIN",
                f"a not-executed run names evidence origin {origin!r}",
            )
        )

    # P06: only hardware-origin evidence may be witnessed.
    if witnessed and origin != "HARDWARE":
        findings.append(
            PrototypeFinding(
                "PROTO_WITNESS_WITHOUT_HARDWARE",
                (
                    f"the run is marked witnessed over {origin!r} evidence; only "
                    "HARDWARE-origin evidence can be witnessed"
                ),
            )
        )

    # P08: a run that stopped at a gate is recorded, and says why.
    if status in _HALTED_STATUSES and not payload.get("halt_reason"):
        findings.append(
            PrototypeFinding(
                "PROTO_HALT_WITHOUT_REASON",
                f"a {status} run names no halt reason",
            )
        )

    # P09: hardware evidence must lead back to retained raw bytes.
    if status == "EXECUTED" and origin == "HARDWARE" and not artifacts:
        findings.append(
            PrototypeFinding(
                "PROTO_HARDWARE_WITHOUT_ARTIFACT",
                "the run claims HARDWARE origin but retains no raw artifact",
            )
        )

    # Artifact identity, reusing the campaign's artifact validator verbatim.
    seen: set[str] = set()
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, Mapping):
            findings.append(
                PrototypeFinding(
                    "PROTO_ARTIFACT_MALFORMED",
                    f"artifact at index {index} is not an object",
                    {"index": index},
                )
            )
            continue
        try:
            artifact = ExternalArtifactV1.from_dict(entry)
        except GrantReadinessError as exc:
            findings.append(
                PrototypeFinding(
                    "PROTO_ARTIFACT_MALFORMED",
                    f"artifact is unusable: [{exc.code.value}] {exc.message}",
                    {"index": index},
                )
            )
            continue
        if artifact.artifact_id in seen:
            findings.append(
                PrototypeFinding(
                    "PROTO_ARTIFACT_MALFORMED",
                    f"artifact {artifact.artifact_id} appears more than once",
                    {"artifact_id": artifact.artifact_id},
                )
            )
        seen.add(artifact.artifact_id)
        for shared in validate_external_artifact(artifact):
            findings.append(
                PrototypeFinding(
                    f"PROTO_{shared.code.value}",
                    shared.message,
                    {"artifact_id": artifact.artifact_id},
                )
            )
    return findings


def validate_prototype_run(payload: Mapping[str, Any]) -> list[PrototypeFinding]:
    """Validate one prototype run against the P01-P10 boundary.

    Deliberately reads nothing from ``notes`` or any narrative field: P07 holds
    that disclosure or guidance text may explain a run but can never change what
    it is, so this function's findings are a function of the measurement record
    alone. Reordering or rewriting ``notes`` cannot move a single finding.
    """
    findings: list[PrototypeFinding] = []
    stage = _stage(payload)
    excitation = payload.get("excitation")
    excitation = excitation if isinstance(excitation, Mapping) else {}

    findings.extend(_validate_stage_excitation(stage, excitation))
    findings.extend(_validate_added_mass(stage, payload))
    findings.extend(_validate_force_boundary(payload))
    findings.extend(_validate_evidence_and_artifacts(payload))
    return findings


__all__ = [
    "PrototypeFinding",
    "promotion_notes",
    "validate_prototype_run",
]
