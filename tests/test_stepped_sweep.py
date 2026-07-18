# INSTRUMENT CLASS: MEASUREMENT
"""Tests for stepped and sweep excitation records (DO-93).

Validates:
- SteppedExcitationRecordV1 structure
- SweepExcitationRecordV1 structure
- ExcitationMeasurementLinkV1 integration
- Advisory-free semantics
"""

import json
import pytest
import numpy as np

from tap_tone_pi.excitation import (
    # Stepped excitation (DO-93)
    SweepType,
    SteppedExcitationRecordV1,
    create_stepped_excitation_record,
    generate_stepped_signal,
    # Sweep excitation (DO-93)
    SweepExcitationRecordV1,
    create_sweep_excitation_record,
    # Measurement linkage (DO-91)
    create_excitation_measurement_link,
)


class TestSteppedExcitationRecord:
    """Tests for SteppedExcitationRecordV1."""

    def test_record_is_frozen(self):
        """SteppedExcitationRecordV1 must be immutable."""
        record = SteppedExcitationRecordV1(record_id="step_001")
        with pytest.raises(AttributeError):
            record.record_id = "modified"

    def test_record_has_schema_version(self):
        """SteppedExcitationRecordV1 must have schema_version."""
        record = SteppedExcitationRecordV1(record_id="step_001")
        assert record.schema_version == "stepped_excitation_record_v1"

    def test_record_has_epistemic_status_observed(self):
        """SteppedExcitationRecordV1 must have epistemic_status = observed."""
        record = SteppedExcitationRecordV1(record_id="step_001")
        assert record.epistemic_status == "observed"

    def test_create_stepped_record(self):
        """create_stepped_excitation_record must work correctly."""
        record = create_stepped_excitation_record(
            record_id="step_001",
            frequencies_hz=[80.0, 90.0, 100.0, 110.0],
            dwell_time_s=1.0,
            amplitude=0.2,
            transition_time_s=0.1,
            sample_rate_hz=48000,
            excitation_id="exc_001",
            output_device_id="speaker_001",
            source_characterization_id="char_001",
            waveform_sha256="abc123",
        )

        assert record.record_id == "step_001"
        assert record.frequencies_hz == (80.0, 90.0, 100.0, 110.0)
        assert record.step_count == 4
        assert record.dwell_time_s == 1.0
        assert record.transition_time_s == 0.1
        assert record.amplitude == 0.2
        assert record.excitation_id == "exc_001"
        assert record.waveform_sha256 == "abc123"

    def test_total_duration_computed(self):
        """create_stepped_excitation_record must compute total_duration_s."""
        record = create_stepped_excitation_record(
            record_id="step_001",
            frequencies_hz=[80.0, 90.0, 100.0],
            dwell_time_s=2.0,
            transition_time_s=0.5,
            amplitude=0.2,
        )
        # 3 steps * 2.0s dwell + 2 transitions * 0.5s = 6.0 + 1.0 = 7.0s
        assert record.total_duration_s == 7.0

    def test_record_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        record = create_stepped_excitation_record(
            record_id="step_001",
            frequencies_hz=[80.0, 90.0, 100.0],
            dwell_time_s=1.0,
            amplitude=0.2,
        )
        d = record.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["record_id"] == "step_001"
        assert parsed["frequencies_hz"] == [80.0, 90.0, 100.0]
        assert parsed["step_count"] == 3


class TestSweepExcitationRecord:
    """Tests for SweepExcitationRecordV1."""

    def test_record_is_frozen(self):
        """SweepExcitationRecordV1 must be immutable."""
        record = SweepExcitationRecordV1(record_id="sweep_001")
        with pytest.raises(AttributeError):
            record.record_id = "modified"

    def test_record_has_schema_version(self):
        """SweepExcitationRecordV1 must have schema_version."""
        record = SweepExcitationRecordV1(record_id="sweep_001")
        assert record.schema_version == "sweep_excitation_record_v1"

    def test_record_has_epistemic_status_observed(self):
        """SweepExcitationRecordV1 must have epistemic_status = observed."""
        record = SweepExcitationRecordV1(record_id="sweep_001")
        assert record.epistemic_status == "observed"

    def test_create_sweep_record_logarithmic(self):
        """create_sweep_excitation_record must work for logarithmic."""
        record = create_sweep_excitation_record(
            record_id="sweep_001",
            start_frequency_hz=70.0,
            stop_frequency_hz=130.0,
            duration_s=5.0,
            amplitude=0.2,
            sweep_type="logarithmic",
            sample_rate_hz=48000,
            excitation_id="exc_001",
            output_device_id="speaker_001",
            waveform_sha256="def456",
        )

        assert record.record_id == "sweep_001"
        assert record.start_frequency_hz == 70.0
        assert record.stop_frequency_hz == 130.0
        assert record.sweep_type == "logarithmic"
        assert record.duration_s == 5.0
        assert record.amplitude == 0.2
        assert record.waveform_sha256 == "def456"

    def test_create_sweep_record_linear(self):
        """create_sweep_excitation_record must work for linear."""
        record = create_sweep_excitation_record(
            record_id="sweep_001",
            start_frequency_hz=20.0,
            stop_frequency_hz=20000.0,
            duration_s=10.0,
            amplitude=0.3,
            sweep_type="linear",
        )

        assert record.sweep_type == "linear"
        assert record.duration_s == 10.0

    def test_record_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        record = create_sweep_excitation_record(
            record_id="sweep_001",
            start_frequency_hz=70.0,
            stop_frequency_hz=130.0,
            duration_s=5.0,
            amplitude=0.2,
        )
        d = record.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["record_id"] == "sweep_001"
        assert parsed["start_frequency_hz"] == 70.0
        assert parsed["stop_frequency_hz"] == 130.0


class TestSweepTypeEnum:
    """Tests for SweepType enum."""

    def test_linear_value(self):
        """SweepType.LINEAR must have value 'linear'."""
        assert SweepType.LINEAR.value == "linear"

    def test_logarithmic_value(self):
        """SweepType.LOGARITHMIC must have value 'logarithmic'."""
        assert SweepType.LOGARITHMIC.value == "logarithmic"


class TestGenerateSteppedSignal:
    """Tests for generate_stepped_signal function."""

    def test_generates_correct_length(self):
        """generate_stepped_signal must produce correct length."""
        signal = generate_stepped_signal(
            frequencies_hz=[100.0, 200.0],
            dwell_time_s=1.0,
            transition_time_s=0.1,
            amplitude=0.5,
            sample_rate_hz=1000,
        )
        # 2 dwells * 1.0s * 1000 Hz + 1 transition * 0.1s * 1000 Hz = 2100 samples
        assert len(signal) == 2100

    def test_amplitude_respected(self):
        """generate_stepped_signal must respect amplitude."""
        signal = generate_stepped_signal(
            frequencies_hz=[100.0],
            dwell_time_s=1.0,
            transition_time_s=0.0,
            amplitude=0.3,
            sample_rate_hz=48000,
        )
        assert np.max(np.abs(signal)) <= 0.3 + 0.01  # Small tolerance

    def test_empty_frequencies_returns_empty(self):
        """generate_stepped_signal must handle empty frequencies."""
        signal = generate_stepped_signal(
            frequencies_hz=[],
            dwell_time_s=1.0,
            transition_time_s=0.1,
            amplitude=0.5,
            sample_rate_hz=48000,
        )
        assert len(signal) == 0


class TestExcitationMeasurementLinkIntegration:
    """Tests for ExcitationMeasurementLinkV1 with stepped/sweep records."""

    def test_link_with_stepped_record(self):
        """ExcitationMeasurementLinkV1 must work with stepped_record_id."""
        link = create_excitation_measurement_link(
            link_id="link_001",
            measurement_id="meas_001",
            excitation_id="exc_001",
            stepped_record_id="step_001",
        )

        assert link.stepped_record_id == "step_001"
        assert link.sweep_record_id is None
        assert link.known_tone_record_id is None

        d = link.to_dict()
        assert d["stepped_record_id"] == "step_001"

    def test_link_with_sweep_record(self):
        """ExcitationMeasurementLinkV1 must work with sweep_record_id."""
        link = create_excitation_measurement_link(
            link_id="link_001",
            measurement_id="meas_001",
            excitation_id="exc_001",
            sweep_record_id="sweep_001",
        )

        assert link.sweep_record_id == "sweep_001"
        assert link.stepped_record_id is None
        assert link.known_tone_record_id is None

        d = link.to_dict()
        assert d["sweep_record_id"] == "sweep_001"

    def test_link_distinguishes_record_types(self):
        """ExcitationMeasurementLinkV1 must distinguish record types."""
        # Tone link
        tone_link = create_excitation_measurement_link(
            link_id="link_tone",
            measurement_id="meas_001",
            excitation_id="exc_001",
            known_tone_record_id="tone_001",
        )

        # Stepped link
        stepped_link = create_excitation_measurement_link(
            link_id="link_stepped",
            measurement_id="meas_002",
            excitation_id="exc_002",
            stepped_record_id="step_001",
        )

        # Sweep link
        sweep_link = create_excitation_measurement_link(
            link_id="link_sweep",
            measurement_id="meas_003",
            excitation_id="exc_003",
            sweep_record_id="sweep_001",
        )

        # Each has only its record type set
        assert tone_link.known_tone_record_id == "tone_001"
        assert tone_link.stepped_record_id is None
        assert tone_link.sweep_record_id is None

        assert stepped_link.known_tone_record_id is None
        assert stepped_link.stepped_record_id == "step_001"
        assert stepped_link.sweep_record_id is None

        assert sweep_link.known_tone_record_id is None
        assert sweep_link.stepped_record_id is None
        assert sweep_link.sweep_record_id == "sweep_001"


class TestAdvisoryFreeSemantics:
    """Tests for advisory-free semantics."""

    # Note: "stop" excluded because "stop_frequency_hz" is technical terminology
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
        "acceptable",
    }

    def test_stepped_record_is_advisory_free(self):
        """SteppedExcitationRecordV1 must not contain advisory terms."""
        record = create_stepped_excitation_record(
            record_id="step_001",
            frequencies_hz=[80.0, 90.0, 100.0],
            dwell_time_s=1.0,
            amplitude=0.2,
        )
        d = record.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Stepped record contains forbidden advisory term '{term}'"
            )

    def test_sweep_record_is_advisory_free(self):
        """SweepExcitationRecordV1 must not contain advisory terms."""
        record = create_sweep_excitation_record(
            record_id="sweep_001",
            start_frequency_hz=70.0,
            stop_frequency_hz=130.0,
            duration_s=5.0,
            amplitude=0.2,
        )
        d = record.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Sweep record contains forbidden advisory term '{term}'"
            )


class TestProvenanceLinkage:
    """Tests for provenance chain integrity."""

    def test_stepped_record_links_to_excitation(self):
        """SteppedExcitationRecordV1 must link to excitation contract."""
        record = create_stepped_excitation_record(
            record_id="step_001",
            frequencies_hz=[80.0, 90.0, 100.0],
            dwell_time_s=1.0,
            amplitude=0.2,
            excitation_id="exc_001",
            source_characterization_id="char_001",
        )

        d = record.to_dict()
        assert d["excitation_id"] == "exc_001"
        assert d["source_characterization_id"] == "char_001"

    def test_sweep_record_links_to_excitation(self):
        """SweepExcitationRecordV1 must link to excitation contract."""
        record = create_sweep_excitation_record(
            record_id="sweep_001",
            start_frequency_hz=70.0,
            stop_frequency_hz=130.0,
            duration_s=5.0,
            amplitude=0.2,
            excitation_id="exc_001",
            source_characterization_id="char_001",
        )

        d = record.to_dict()
        assert d["excitation_id"] == "exc_001"
        assert d["source_characterization_id"] == "char_001"

    def test_waveform_hash_recorded(self):
        """Records must store waveform SHA-256."""
        stepped = create_stepped_excitation_record(
            record_id="step_001",
            frequencies_hz=[80.0, 90.0],
            dwell_time_s=1.0,
            amplitude=0.2,
            waveform_sha256="abc123def456",
        )

        sweep = create_sweep_excitation_record(
            record_id="sweep_001",
            start_frequency_hz=70.0,
            stop_frequency_hz=130.0,
            duration_s=5.0,
            amplitude=0.2,
            waveform_sha256="789ghi012jkl",
        )

        assert stepped.to_dict()["waveform_sha256"] == "abc123def456"
        assert sweep.to_dict()["waveform_sha256"] == "789ghi012jkl"
