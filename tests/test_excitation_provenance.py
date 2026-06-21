# INSTRUMENT CLASS: MEASUREMENT
"""Tests for excitation provenance and transfer function workflow (DO-91).

Validates:
- ExcitationMeasurementLinkV1 structure
- ExcitationResponsePairV1 structure
- TransferFunctionResultV1 structure
- Provenance linkage
- Advisory-free semantics
"""

import json
import pytest
import numpy as np

from tap_tone_pi.excitation import (
    # DO-91 contracts
    ExcitationMeasurementLinkV1,
    create_excitation_measurement_link,
    ExcitationResponsePairV1,
    create_excitation_response_pair,
)

from tap_tone_pi.transfer_function import (
    TransferFunctionResultV1,
    CoherenceSummaryV1,
    UncertaintySummaryV1,
    create_transfer_function_result,
)


class TestExcitationMeasurementLink:
    """Tests for ExcitationMeasurementLinkV1."""

    def test_link_is_frozen(self):
        """ExcitationMeasurementLinkV1 must be immutable."""
        link = ExcitationMeasurementLinkV1(link_id="link_001")
        with pytest.raises(AttributeError):
            link.link_id = "modified"

    def test_link_has_schema_version(self):
        """ExcitationMeasurementLinkV1 must have schema_version."""
        link = ExcitationMeasurementLinkV1(link_id="link_001")
        assert link.schema_version == "excitation_measurement_link_v1"

    def test_link_has_epistemic_status(self):
        """ExcitationMeasurementLinkV1 must have epistemic_status = derived."""
        link = ExcitationMeasurementLinkV1(link_id="link_001")
        assert link.epistemic_status == "derived"

    def test_create_link_with_tone(self):
        """create_excitation_measurement_link must work for tone."""
        link = create_excitation_measurement_link(
            link_id="link_001",
            measurement_id="meas_001",
            excitation_id="exc_001",
            known_tone_record_id="tone_001",
            source_characterization_id="char_001",
        )
        assert link.link_id == "link_001"
        assert link.measurement_id == "meas_001"
        assert link.known_tone_record_id == "tone_001"
        assert link.linked_at_utc  # Should have timestamp

    def test_create_link_with_sweep(self):
        """create_excitation_measurement_link must work for sweep."""
        link = create_excitation_measurement_link(
            link_id="link_001",
            measurement_id="meas_001",
            excitation_id="exc_001",
            sweep_record_id="sweep_001",
        )
        assert link.sweep_record_id == "sweep_001"
        assert link.known_tone_record_id is None

    def test_link_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        link = create_excitation_measurement_link(
            link_id="link_001",
            measurement_id="meas_001",
            excitation_id="exc_001",
            known_tone_record_id="tone_001",
        )
        d = link.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["link_id"] == "link_001"


class TestExcitationResponsePair:
    """Tests for ExcitationResponsePairV1."""

    def test_pair_is_frozen(self):
        """ExcitationResponsePairV1 must be immutable."""
        pair = ExcitationResponsePairV1(pair_id="pair_001")
        with pytest.raises(AttributeError):
            pair.pair_id = "modified"

    def test_pair_has_schema_version(self):
        """ExcitationResponsePairV1 must have schema_version."""
        pair = ExcitationResponsePairV1(pair_id="pair_001")
        assert pair.schema_version == "excitation_response_pair_v1"

    def test_pair_has_epistemic_status(self):
        """ExcitationResponsePairV1 must have epistemic_status = derived."""
        pair = ExcitationResponsePairV1(pair_id="pair_001")
        assert pair.epistemic_status == "derived"

    def test_create_pair_for_tone(self):
        """create_excitation_response_pair must work for tone."""
        pair = create_excitation_response_pair(
            pair_id="pair_001",
            excitation_id="exc_001",
            excitation_record_id="tone_001",
            response_measurement_id="meas_001",
            excitation_type="tone",
            duration_s=5.0,
            frequency_hz=440.0,
        )
        assert pair.pair_id == "pair_001"
        assert pair.excitation_type == "tone"
        assert pair.frequency_hz == 440.0
        assert pair.captured_at_utc  # Should have timestamp

    def test_create_pair_for_sweep(self):
        """create_excitation_response_pair must work for sweep."""
        pair = create_excitation_response_pair(
            pair_id="pair_001",
            excitation_id="exc_001",
            excitation_record_id="sweep_001",
            response_measurement_id="meas_001",
            excitation_type="sweep",
            duration_s=10.0,
            start_frequency_hz=20.0,
            stop_frequency_hz=20000.0,
        )
        assert pair.excitation_type == "sweep"
        assert pair.start_frequency_hz == 20.0
        assert pair.stop_frequency_hz == 20000.0

    def test_pair_with_environment(self):
        """create_excitation_response_pair must accept environment."""
        pair = create_excitation_response_pair(
            pair_id="pair_001",
            excitation_id="exc_001",
            excitation_record_id="tone_001",
            response_measurement_id="meas_001",
            excitation_type="tone",
            duration_s=5.0,
            environment_temp_c=22.5,
            environment_rh_pct=45.0,
        )
        assert pair.environment_temp_c == 22.5
        assert pair.environment_rh_pct == 45.0

    def test_pair_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        pair = create_excitation_response_pair(
            pair_id="pair_001",
            excitation_id="exc_001",
            excitation_record_id="tone_001",
            response_measurement_id="meas_001",
            excitation_type="tone",
            duration_s=5.0,
        )
        d = pair.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["pair_id"] == "pair_001"


class TestTransferFunctionResultV1:
    """Tests for TransferFunctionResultV1."""

    def test_result_is_frozen(self):
        """TransferFunctionResultV1 must be immutable."""
        result = TransferFunctionResultV1(result_id="tf_001")
        with pytest.raises(AttributeError):
            result.result_id = "modified"

    def test_result_has_schema_version(self):
        """TransferFunctionResultV1 must have schema_version."""
        result = TransferFunctionResultV1(result_id="tf_001")
        assert result.schema_version == "transfer_function_result_v1"

    def test_result_has_epistemic_status(self):
        """TransferFunctionResultV1 must have epistemic_status = derived."""
        result = TransferFunctionResultV1(result_id="tf_001")
        assert result.epistemic_status == "derived"

    def test_create_result_from_arrays(self):
        """create_transfer_function_result must compute summaries."""
        frequencies = np.linspace(20, 2000, 100)
        magnitude = np.ones(100)
        magnitude[50] = 10.0  # Peak at bin 50
        coherence = np.full(100, 0.95)

        result = create_transfer_function_result(
            result_id="tf_001",
            excitation_response_pair_id="pair_001",
            estimator_used="H1",
            frequencies=frequencies,
            magnitude=magnitude,
            coherence=coherence,
            num_averages=10,
        )

        assert result.result_id == "tf_001"
        assert result.excitation_response_pair_id == "pair_001"
        assert result.estimator_used == "H1"
        assert result.num_frequency_bins == 100
        assert result.peak_magnitude == 10.0
        assert result.peak_frequency_hz == frequencies[50]

    def test_coherence_summary_computed(self):
        """create_transfer_function_result must compute coherence summary."""
        frequencies = np.linspace(20, 2000, 100)
        magnitude = np.ones(100)
        coherence = np.full(100, 0.9)
        coherence[10:20] = 0.5  # Low coherence region

        result = create_transfer_function_result(
            result_id="tf_001",
            excitation_response_pair_id="pair_001",
            estimator_used="H1",
            frequencies=frequencies,
            magnitude=magnitude,
            coherence=coherence,
        )

        assert result.coherence_summary is not None
        assert result.coherence_summary.mean_coherence < 0.9
        assert result.coherence_summary.min_coherence == 0.5
        assert result.coherence_summary.coherent_fraction < 1.0

    def test_uncertainty_summary_computed(self):
        """create_transfer_function_result must compute uncertainty."""
        frequencies = np.linspace(20, 2000, 100)
        magnitude = np.ones(100)
        coherence = np.full(100, 0.9)

        result = create_transfer_function_result(
            result_id="tf_001",
            excitation_response_pair_id="pair_001",
            estimator_used="H1",
            frequencies=frequencies,
            magnitude=magnitude,
            coherence=coherence,
            num_averages=10,
        )

        assert result.uncertainty_summary is not None
        assert result.uncertainty_summary.num_averages == 10
        assert result.uncertainty_summary.uncertainty_method == "coherence_based"

    def test_result_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        frequencies = np.linspace(20, 2000, 100)
        magnitude = np.ones(100)
        coherence = np.full(100, 0.9)

        result = create_transfer_function_result(
            result_id="tf_001",
            excitation_response_pair_id="pair_001",
            estimator_used="H1",
            frequencies=frequencies,
            magnitude=magnitude,
            coherence=coherence,
        )

        d = result.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["result_id"] == "tf_001"
        assert "coherence_summary" in parsed


class TestCoherenceSummary:
    """Tests for CoherenceSummaryV1."""

    def test_summary_to_dict(self):
        """CoherenceSummaryV1 must serialize correctly."""
        summary = CoherenceSummaryV1(
            mean_coherence=0.85,
            min_coherence=0.5,
            max_coherence=0.99,
            coherent_fraction=0.9,
            coherence_threshold=0.8,
            frequency_range_hz=(20.0, 2000.0),
        )
        d = summary.to_dict()
        assert d["mean_coherence"] == 0.85
        assert d["frequency_range_hz"] == [20.0, 2000.0]


class TestUncertaintySummary:
    """Tests for UncertaintySummaryV1."""

    def test_summary_to_dict(self):
        """UncertaintySummaryV1 must serialize correctly."""
        summary = UncertaintySummaryV1(
            mean_relative_uncertainty=0.1,
            max_relative_uncertainty=0.3,
            num_averages=10,
            uncertainty_method="coherence_based",
        )
        d = summary.to_dict()
        assert d["mean_relative_uncertainty"] == 0.1
        assert d["num_averages"] == 10


class TestAdvisoryFreeSemantics:
    """Tests for advisory-free semantics."""

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

    def test_link_is_advisory_free(self):
        """ExcitationMeasurementLinkV1 must not contain advisory terms."""
        link = create_excitation_measurement_link(
            link_id="link_001",
            measurement_id="meas_001",
            excitation_id="exc_001",
        )
        d = link.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Link contains forbidden advisory term '{term}'"
            )

    def test_pair_is_advisory_free(self):
        """ExcitationResponsePairV1 must not contain advisory terms."""
        pair = create_excitation_response_pair(
            pair_id="pair_001",
            excitation_id="exc_001",
            excitation_record_id="tone_001",
            response_measurement_id="meas_001",
            excitation_type="tone",
            duration_s=5.0,
        )
        d = pair.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Pair contains forbidden advisory term '{term}'"
            )

    def test_tf_result_is_advisory_free(self):
        """TransferFunctionResultV1 must not contain advisory terms."""
        frequencies = np.linspace(20, 2000, 100)
        magnitude = np.ones(100)
        coherence = np.full(100, 0.9)

        result = create_transfer_function_result(
            result_id="tf_001",
            excitation_response_pair_id="pair_001",
            estimator_used="H1",
            frequencies=frequencies,
            magnitude=magnitude,
            coherence=coherence,
        )
        d = result.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Result contains forbidden advisory term '{term}'"
            )


class TestProvenanceLinkage:
    """Tests for provenance chain integrity."""

    def test_link_connects_excitation_to_measurement(self):
        """Link must connect excitation to measurement."""
        link = create_excitation_measurement_link(
            link_id="link_001",
            measurement_id="meas_001",
            excitation_id="exc_001",
            known_tone_record_id="tone_001",
        )
        d = link.to_dict()
        assert d["measurement_id"] == "meas_001"
        assert d["excitation_id"] == "exc_001"
        assert d["known_tone_record_id"] == "tone_001"

    def test_pair_bundles_excitation_and_response(self):
        """Pair must bundle excitation and response IDs."""
        pair = create_excitation_response_pair(
            pair_id="pair_001",
            excitation_id="exc_001",
            excitation_record_id="tone_001",
            response_measurement_id="meas_001",
            excitation_type="tone",
            duration_s=5.0,
        )
        d = pair.to_dict()
        assert d["excitation_id"] == "exc_001"
        assert d["excitation_record_id"] == "tone_001"
        assert d["response_measurement_id"] == "meas_001"

    def test_tf_result_links_to_pair(self):
        """TF result must link to excitation-response pair."""
        frequencies = np.linspace(20, 2000, 100)
        magnitude = np.ones(100)

        result = create_transfer_function_result(
            result_id="tf_001",
            excitation_response_pair_id="pair_001",
            estimator_used="H1",
            frequencies=frequencies,
            magnitude=magnitude,
        )
        d = result.to_dict()
        assert d["excitation_response_pair_id"] == "pair_001"
