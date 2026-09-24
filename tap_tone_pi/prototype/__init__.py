# INSTRUMENT CLASS: MEASUREMENT
"""TTP-PROTOTYPE-001 prototype-commissioning evidence (PROTOTYPE track).

This package holds the read-only evidence model for the off-the-shelf prototype
signal chain: a force-free, microphone-only, manual-or-commanded physical run
used to close a first measurement loop and gather engineering evidence.

It is deliberately separate from :mod:`tap_tone_pi.grant_readiness`, whose
``ttp_hardware_campaign_v1`` contract encodes the DO-103 *measured-force*
architecture. The two share provenance vocabulary — :class:`EvidenceOrigin`,
the witnessed standard, and SHA-256 artifact identity — but not their physical
claim: a prototype run may carry no measured force channel, and nothing here
asserts reference-grade accuracy or qualified/production hardware.
"""

from tap_tone_pi.prototype.contracts import (
    PROTOTYPE_RUN_SCHEMA_VERSION,
    ExcitationMode,
    PrototypeStage,
)
from tap_tone_pi.prototype.validation import (
    PrototypeFinding,
    promotion_notes,
    validate_prototype_run,
)

__all__ = [
    "PROTOTYPE_RUN_SCHEMA_VERSION",
    "ExcitationMode",
    "PrototypeFinding",
    "PrototypeStage",
    "promotion_notes",
    "validate_prototype_run",
]
