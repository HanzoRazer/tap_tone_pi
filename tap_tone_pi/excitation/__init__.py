# INSTRUMENT CLASS: MEASUREMENT
"""Controlled excitation contracts and provenance (DO-90, DO-91).

This package provides measurement/provenance contracts for controlled excitation:
- ExcitationContractV1: declarative excitation specification
- KnownToneRecordV1: provenance for single emitted tone event
- SourceCharacterizationRecordV1: output-side calibration record

Excitation-measurement linkage (DO-91):
- ExcitationMeasurementLinkV1: links excitation to measurement
- ExcitationResponsePairV1: provenance pair for TF computation

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
from tap_tone_pi.excitation.measurement_link import (
    ExcitationMeasurementLinkV1,
    create_excitation_measurement_link,
)
from tap_tone_pi.excitation.response_pair import (
    ExcitationResponsePairV1,
    create_excitation_response_pair,
)

__all__ = [
    # Contracts (DO-90)
    "ExcitationType",
    "WaveformType",
    "ExcitationContractV1",
    "create_excitation_contract",
    # Known tone (DO-90)
    "KnownToneRecordV1",
    "create_known_tone_record",
    "emit_tone",
    # Source characterization (DO-90)
    "SourceCharacterizationRecordV1",
    "create_source_characterization",
    # Amplitude guardrails (DO-90)
    "AmplitudeGuardrail",
    "validate_amplitude",
    "DEFAULT_AMPLITUDE",
    "MAX_SAFE_AMPLITUDE",
    "WARNING_AMPLITUDE",
    # Measurement linkage (DO-91)
    "ExcitationMeasurementLinkV1",
    "create_excitation_measurement_link",
    # Response pair (DO-91)
    "ExcitationResponsePairV1",
    "create_excitation_response_pair",
]
