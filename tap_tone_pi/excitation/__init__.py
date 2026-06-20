# INSTRUMENT CLASS: MEASUREMENT
"""Controlled excitation contracts and provenance (DO-90).

This package provides measurement/provenance contracts for controlled excitation:
- ExcitationContractV1: declarative excitation specification
- KnownToneRecordV1: provenance for single emitted tone event
- SourceCharacterizationRecordV1: output-side calibration record

Controlled excitation reduces σ_process by replacing variable tap input
with repeatable known excitation. This is variance reduction infrastructure,
not modal-research expansion.

No advisory semantics. No tone quality judgments.
"""

from tap_tone_pi.excitation.contracts import (
    ExcitationType,
    WaveformType,
    ExcitationContractV1,
    create_excitation_contract,
)
from tap_tone_pi.excitation.known_tone import (
    KnownToneRecordV1,
    create_known_tone_record,
    emit_tone,
)
from tap_tone_pi.excitation.source_characterization import (
    SourceCharacterizationRecordV1,
    create_source_characterization,
)
from tap_tone_pi.excitation.amplitude import (
    AmplitudeGuardrail,
    validate_amplitude,
    DEFAULT_AMPLITUDE,
    MAX_SAFE_AMPLITUDE,
    WARNING_AMPLITUDE,
)

__all__ = [
    # Contracts
    "ExcitationType",
    "WaveformType",
    "ExcitationContractV1",
    "create_excitation_contract",
    # Known tone
    "KnownToneRecordV1",
    "create_known_tone_record",
    "emit_tone",
    # Source characterization
    "SourceCharacterizationRecordV1",
    "create_source_characterization",
    # Amplitude guardrails
    "AmplitudeGuardrail",
    "validate_amplitude",
    "DEFAULT_AMPLITUDE",
    "MAX_SAFE_AMPLITUDE",
    "WARNING_AMPLITUDE",
]
