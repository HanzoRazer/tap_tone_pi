# INSTRUMENT CLASS: MEASUREMENT
"""Tests for controlled excitation (DO-90).

Validates:
- ExcitationContractV1 structure and validation
- KnownToneRecordV1 provenance
- SourceCharacterizationRecordV1
- Amplitude guardrails
- CLI command structure
"""

import json
import pytest

from tap_tone_pi.excitation import (
    # Contracts
    ExcitationType,
    WaveformType,
    ExcitationContractV1,
    create_excitation_contract,
    # Known tone
    KnownToneRecordV1,
    create_known_tone_record,
    # Source characterization
    SourceCharacterizationRecordV1,
    create_source_characterization,
    # Amplitude guardrails
    AmplitudeGuardrail,
    validate_amplitude,
    DEFAULT_AMPLITUDE,
    MAX_SAFE_AMPLITUDE,
    WARNING_AMPLITUDE,
)


class TestAmplitudeGuardrails:
    """Tests for amplitude validation."""

    def test_default_amplitude_is_safe(self):
        """Default amplitude must be in normal range."""
        result = validate_amplitude(DEFAULT_AMPLITUDE)
        assert result.guardrail == AmplitudeGuardrail.NORMAL

    def test_low_amplitude_is_normal(self):
        """Low amplitudes are normal."""
        result = validate_amplitude(0.1)
        assert result.guardrail == AmplitudeGuardrail.NORMAL

    def test_medium_amplitude_is_warning(self):
        """Medium-high amplitudes generate warning."""
        result = validate_amplitude(0.4)
        assert result.guardrail == AmplitudeGuardrail.WARNING

    def test_high_amplitude_is_warning(self):
        """High amplitudes generate warning."""
        result = validate_amplitude(0.7)
        assert result.guardrail == AmplitudeGuardrail.WARNING

    def test_over_max_is_rejected(self):
        """Amplitude > 1.0 is rejected."""
        result = validate_amplitude(1.5)
        assert result.guardrail == AmplitudeGuardrail.REJECTED

    def test_negative_is_rejected(self):
        """Negative amplitude is rejected."""
        result = validate_amplitude(-0.1)
        assert result.guardrail == AmplitudeGuardrail.REJECTED

    def test_exactly_one_is_warning(self):
        """Amplitude exactly 1.0 is warning, not rejected."""
        result = validate_amplitude(1.0)
        assert result.guardrail == AmplitudeGuardrail.WARNING


class TestExcitationContract:
    """Tests for ExcitationContractV1."""

    def test_contract_is_frozen(self):
        """ExcitationContractV1 must be immutable."""
        contract = ExcitationContractV1(excitation_id="exc_001")
        with pytest.raises(AttributeError):
            contract.excitation_id = "modified"

    def test_contract_has_schema_version(self):
        """ExcitationContractV1 must have schema_version."""
        contract = ExcitationContractV1(excitation_id="exc_001")
        assert contract.schema_version == "excitation_contract_v1"

    def test_contract_has_epistemic_status(self):
        """ExcitationContractV1 must have epistemic_status = derived."""
        contract = ExcitationContractV1(excitation_id="exc_001")
        assert contract.epistemic_status == "derived"

    def test_create_tone_contract(self):
        """create_excitation_contract must work for tone type."""
        contract = create_excitation_contract(
            excitation_id="exc_001",
            excitation_type=ExcitationType.TONE,
            frequency_hz=440.0,
            duration_s=5.0,
            amplitude=0.2,
        )
        assert contract.excitation_type == ExcitationType.TONE
        assert contract.frequency_hz == 440.0
        assert contract.duration_s == 5.0

    def test_tone_requires_frequency(self):
        """Tone excitation must require frequency_hz."""
        with pytest.raises(ValueError, match="frequency_hz required"):
            create_excitation_contract(
                excitation_id="exc_001",
                excitation_type=ExcitationType.TONE,
            )

    def test_create_stepped_contract(self):
        """create_excitation_contract must work for stepped type."""
        contract = create_excitation_contract(
            excitation_id="exc_001",
            excitation_type=ExcitationType.STEPPED,
            start_frequency_hz=80.0,
            stop_frequency_hz=130.0,
            step_frequency_hz=2.0,
        )
        assert contract.excitation_type == ExcitationType.STEPPED
        assert contract.start_frequency_hz == 80.0
        assert contract.step_frequency_hz == 2.0

    def test_stepped_requires_step(self):
        """Stepped excitation must require step_frequency_hz."""
        with pytest.raises(ValueError, match="step_frequency_hz required"):
            create_excitation_contract(
                excitation_id="exc_001",
                excitation_type=ExcitationType.STEPPED,
                start_frequency_hz=80.0,
                stop_frequency_hz=130.0,
            )

    def test_create_sweep_contract(self):
        """create_excitation_contract must work for sweep type."""
        contract = create_excitation_contract(
            excitation_id="exc_001",
            excitation_type=ExcitationType.SWEEP,
            start_frequency_hz=20.0,
            stop_frequency_hz=20000.0,
            duration_s=10.0,
        )
        assert contract.excitation_type == ExcitationType.SWEEP
        assert contract.start_frequency_hz == 20.0
        assert contract.stop_frequency_hz == 20000.0

    def test_contract_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        contract = create_excitation_contract(
            excitation_id="exc_001",
            excitation_type=ExcitationType.TONE,
            frequency_hz=440.0,
        )
        d = contract.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["excitation_type"] == "tone"


class TestKnownToneRecord:
    """Tests for KnownToneRecordV1."""

    def test_record_is_frozen(self):
        """KnownToneRecordV1 must be immutable."""
        record = KnownToneRecordV1(record_id="rec_001")
        with pytest.raises(AttributeError):
            record.record_id = "modified"

    def test_record_has_schema_version(self):
        """KnownToneRecordV1 must have schema_version."""
        record = KnownToneRecordV1(record_id="rec_001")
        assert record.schema_version == "known_tone_record_v1"

    def test_record_has_epistemic_status(self):
        """KnownToneRecordV1 must have epistemic_status = derived."""
        record = KnownToneRecordV1(record_id="rec_001")
        assert record.epistemic_status == "derived"

    def test_create_known_tone_record(self):
        """create_known_tone_record must populate all fields."""
        record = create_known_tone_record(
            record_id="rec_001",
            frequency_hz=440.0,
            duration_s=5.0,
            amplitude=0.2,
            sample_rate_hz=48000,
            output_device_id="Device A",
        )
        assert record.record_id == "rec_001"
        assert record.frequency_hz == 440.0
        assert record.duration_s == 5.0
        assert record.amplitude == 0.2
        assert record.output_device_id == "Device A"
        assert record.emitted_at_utc  # Should have timestamp

    def test_record_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        record = create_known_tone_record(
            record_id="rec_001",
            frequency_hz=440.0,
            duration_s=5.0,
            amplitude=0.2,
        )
        d = record.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["frequency_hz"] == 440.0


class TestSourceCharacterization:
    """Tests for SourceCharacterizationRecordV1."""

    def test_record_is_frozen(self):
        """SourceCharacterizationRecordV1 must be immutable."""
        record = SourceCharacterizationRecordV1(characterization_id="char_001")
        with pytest.raises(AttributeError):
            record.characterization_id = "modified"

    def test_record_has_schema_version(self):
        """SourceCharacterizationRecordV1 must have schema_version."""
        record = SourceCharacterizationRecordV1(characterization_id="char_001")
        assert record.schema_version == "source_characterization_record_v1"

    def test_create_source_characterization(self):
        """create_source_characterization must populate fields."""
        record = create_source_characterization(
            characterization_id="char_001",
            output_device_name="USB Audio Device",
            measurement_method="loopback",
            transducer_model="Surface Speaker",
            usable_frequency_range_hz=(50.0, 15000.0),
        )
        assert record.characterization_id == "char_001"
        assert record.output_device_name == "USB Audio Device"
        assert record.transducer_model == "Surface Speaker"
        assert record.usable_frequency_range_hz == (50.0, 15000.0)

    def test_source_characterization_with_frequency_response(self):
        """Source characterization can include frequency response."""
        record = create_source_characterization(
            characterization_id="char_001",
            output_device_name="USB Audio Device",
            measurement_method="reference_mic",
            frequency_response=[
                (100.0, -3.0),
                (1000.0, 0.0),
                (10000.0, -6.0),
            ],
        )
        assert len(record.frequency_response) == 3
        assert record.frequency_response[0].frequency_hz == 100.0
        assert record.frequency_response[0].magnitude_db == -3.0

    def test_record_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        record = create_source_characterization(
            characterization_id="char_001",
            output_device_name="USB Audio Device",
            measurement_method="loopback",
        )
        d = record.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["characterization_id"] == "char_001"


class TestAdvisoryFreeSemantics:
    """Tests for advisory-free semantics in excitation contracts."""

    FORBIDDEN_ADVISORY_TERMS = {
        "recommended",
        "optimal",
        "best",
        "preferred",
        "approved",
        "good",
        "bad",
        "quality",
        "grade",
        "verdict",
        "pass",
        "fail",
        "should",
        "must",
        "proceed",
        "stop",
        "acceptable",
    }

    def test_excitation_contract_is_advisory_free(self):
        """ExcitationContractV1 output must not contain advisory terms."""
        contract = create_excitation_contract(
            excitation_id="exc_001",
            excitation_type=ExcitationType.TONE,
            frequency_hz=440.0,
        )
        d = contract.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Contract contains forbidden advisory term '{term}'"
            )

    def test_known_tone_record_is_advisory_free(self):
        """KnownToneRecordV1 output must not contain advisory terms."""
        record = create_known_tone_record(
            record_id="rec_001",
            frequency_hz=440.0,
            duration_s=5.0,
            amplitude=0.2,
        )
        d = record.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Record contains forbidden advisory term '{term}'"
            )


class TestWaveformTypes:
    """Tests for excitation type enums."""

    def test_excitation_types(self):
        """ExcitationType enum must have expected values."""
        assert ExcitationType.TONE.value == "tone"
        assert ExcitationType.STEPPED.value == "stepped"
        assert ExcitationType.SWEEP.value == "sweep"

    def test_waveform_types(self):
        """WaveformType enum must have expected values."""
        assert WaveformType.SINE.value == "sine"

    def test_string_conversion(self):
        """Excitation type must be creatable from string."""
        contract = create_excitation_contract(
            excitation_id="exc_001",
            excitation_type="tone",
            frequency_hz=440.0,
        )
        assert contract.excitation_type == ExcitationType.TONE


class TestDefaultValues:
    """Tests for default values."""

    def test_default_amplitude_is_0_2(self):
        """DEFAULT_AMPLITUDE must be 0.2."""
        assert DEFAULT_AMPLITUDE == 0.2

    def test_warning_amplitude_is_0_5(self):
        """WARNING_AMPLITUDE must be 0.5."""
        assert WARNING_AMPLITUDE == 0.5

    def test_max_safe_amplitude_is_1_0(self):
        """MAX_SAFE_AMPLITUDE must be 1.0."""
        assert MAX_SAFE_AMPLITUDE == 1.0

    def test_contract_uses_default_amplitude(self):
        """ExcitationContractV1 default amplitude must be 0.2."""
        contract = ExcitationContractV1(excitation_id="exc_001")
        assert contract.amplitude == 0.2

    def test_record_uses_default_amplitude(self):
        """KnownToneRecordV1 default amplitude must be 0.2."""
        record = KnownToneRecordV1(record_id="rec_001")
        assert record.amplitude == 0.2
