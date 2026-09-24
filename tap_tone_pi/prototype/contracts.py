# INSTRUMENT CLASS: MEASUREMENT
"""Vocabulary for a ``ttp_prototype_run_v1`` prototype-commissioning run.

Only two ideas are new here, because they are the two the DO-103 campaign
contract cannot express without becoming false: the prototype *stage*
(``R0``/``R1``/``R2``) and the *excitation mode* (a hand tap versus a commanded
waveform). Everything else — evidence origin, the witnessed standard, run
status, calibration traceability, and external-artifact identity — is imported
from :mod:`tap_tone_pi.grant_readiness.contracts` rather than re-defined, so the
prototype record and the campaign record cannot drift into two vocabularies for
the same idea.
"""

from __future__ import annotations

from enum import Enum

# Re-exported so callers of this package get one import site for the shared
# vocabulary without reaching into grant_readiness, and so a reader sees exactly
# which concepts are reused rather than reinvented.
from tap_tone_pi.grant_readiness.contracts import (
    CalibrationTraceability,
    EvidenceOrigin,
    ExperimentOutcomeStatus,
    ExternalArtifactV1,
)

PROTOTYPE_RUN_SCHEMA_VERSION = "ttp_prototype_run_v1"


class PrototypeStage(str, Enum):
    """Which stage of the first closed measurement loop a run belongs to.

    The stages are a deliberate order of increasing physical commitment, not a
    severity ranking. ``R0`` acquires a real specimen's response to a manual
    tap; ``R1`` repeats it under a known added mass; ``R2`` closes the loop with
    a TTP-commanded excitation. The stage bounds what a run may truthfully
    claim, which is why a run records it rather than leaving it to be inferred.
    """

    R0 = "R0"
    R1 = "R1"
    R2 = "R2"


class ExcitationMode(str, Enum):
    """How the specimen was excited.

    ``MANUAL`` is a hand tap: there is no commanded signal and no output/
    amplifier/exciter chain to name. ``COMMANDED`` is a TTP-emitted waveform
    driven through an output device, amplifier and exciter, and it must carry
    emission provenance. Neither mode is a measured force: a commanded
    electrical amplitude is an input the operator set, not a mechanical force
    the specimen received.
    """

    MANUAL = "MANUAL"
    COMMANDED = "COMMANDED"


# The excitation mode each stage is allowed to use. R0 and R1 are manual-tap
# acquisitions (R1 is R0 under a known added mass); R2 is the commanded loop.
STAGE_EXCITATION_MODE: dict[PrototypeStage, ExcitationMode] = {
    PrototypeStage.R0: ExcitationMode.MANUAL,
    PrototypeStage.R1: ExcitationMode.MANUAL,
    PrototypeStage.R2: ExcitationMode.COMMANDED,
}


__all__ = [
    "PROTOTYPE_RUN_SCHEMA_VERSION",
    "STAGE_EXCITATION_MODE",
    "CalibrationTraceability",
    "EvidenceOrigin",
    "ExcitationMode",
    "ExperimentOutcomeStatus",
    "ExternalArtifactV1",
    "PrototypeStage",
]
