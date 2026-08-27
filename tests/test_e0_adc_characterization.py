"""E0 ADC characterization contract, schema, and checker (DO-106).

The line these tests hold: **an E0 record may not claim more than the bench
produced.** E0 has no pass condition, so there is nothing here about whether a
board is good — every test below is about whether the document is a truthful
account of what happened, and the failures it must refuse are the ones that
would read as evidence and not be.

Three of them recur, because they are the three ways this record could quietly
lie: a value that was never measured, a frequency the source could not generate,
and a phase that defaulted to zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness.e0_characterization import (
    E0_SCHEMA_VERSION,
    E0AdcCharacterizationV1,
    E0ArtifactRefV1,
    E0BalancedInputObservationV1,
    E0ControlGranularity,
    E0CouplingObservationV1,
    E0CouplingResultV1,
    E0DeviceIdentityV1,
    E0ExecutionStatus,
    E0FullScaleObservationV1,
    E0InputPath,
    E0LoopbackObservationV1,
    E0NoiseObservationV1,
    E0OutOfBandObservationV1,
    E0PgaObservationV1,
    E0ProvenanceV1,
    E0SourceCapability,
    E0SpurObservationV1,
)
from tap_tone_pi.grant_readiness.errors import (
    E0CharacterizationError,
    GrantReadinessErrorCode,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HARDWARE = REPO_ROOT / "docs" / "hardware"
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "e0_adc_characterization.schema.json"


def device() -> E0DeviceIdentityV1:
    return E0DeviceIdentityV1(
        local_id="ADC-001", manufacturer="HiFiBerry", model="DAC+ ADC Pro"
    )


def provenance(**overrides) -> E0ProvenanceV1:
    base = dict(performed_utc="2026-09-01T12:00:00Z", operator="Ross Echols")
    base.update(overrides)
    return E0ProvenanceV1(**base)


def prepared() -> E0AdcCharacterizationV1:
    return E0AdcCharacterizationV1(
        characterization_id="E0-TEST-PREPARED",
        device=device(),
        provenance=provenance(),
    )


def executed() -> E0AdcCharacterizationV1:
    """A complete record. Deliberately unremarkable numbers - no verdict implied."""
    return E0AdcCharacterizationV1(
        characterization_id="E0-TEST-EXECUTED",
        device=device(),
        provenance=provenance(
            source_equipment=("second laptop, 192 kHz audio out",),
            source_verified_bandwidth_hz=90000.0,
        ),
        execution_status=E0ExecutionStatus.EXECUTED,
        noise_floor=(
            E0NoiseObservationV1(48000.0, -12.0, -108.4),
            E0NoiseObservationV1(48000.0, 32.0, -84.1),
        ),
        spurs=(E0SpurObservationV1(frequency_hz=50.0, level_dbfs=-121.0),),
        pga=(
            E0PgaObservationV1(0.0, 0.0, 0.0, -108.4),
            E0PgaObservationV1(32.0, 32.0, 31.6, -108.1),
        ),
        coupling=E0CouplingResultV1(
            measured_corner_hz=18.5,
            points=(
                E0CouplingObservationV1(70.0, -0.31, 15.9),
                E0CouplingObservationV1(200.0, -0.04, 5.3),
            ),
        ),
        out_of_band=(
            E0OutOfBandObservationV1(
                injected_hz=30000.0,
                source_state=E0SourceCapability.MEASURED,
                apparent_hz=18000.0,
                attenuation_db=-6.2,
                sample_rate_hz=48000.0,
            ),
            E0OutOfBandObservationV1(
                injected_hz=200000.0,
                source_state=E0SourceCapability.BLOCKED_BY_SOURCE_CAPABILITY,
            ),
        ),
        balanced_scope=E0BalancedInputObservationV1(
            control_name="ADC Input Mode",
            granularity=E0ControlGranularity.GLOBAL,
            unbalanced_full_scale_vrms=2.05,
            balanced_full_scale_vrms=4.11,
            applies_to="Analyzer only; E1 ch0 needs unbalanced",
        ),
        full_scale=(
            E0FullScaleObservationV1(E0InputPath.UNBALANCED, 2.02, 2.11, 2.1),
            E0FullScaleObservationV1(E0InputPath.BALANCED, 4.05, 4.20, 4.2),
        ),
        loopback=E0LoopbackObservationV1(
            run_count=50,
            mean_offset_samples=1412.0,
            stddev_samples=3.1,
            within_session_stable=True,
            sample_rate_hz=48000.0,
        ),
    )


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(payload, schema) -> None:
    import jsonschema

    jsonschema.validate(payload, schema)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class TestContract:
    def test_empty_prepared_record_round_trips(self):
        record = prepared()
        assert E0AdcCharacterizationV1.from_dict(record.to_dict()) == record

    def test_complete_executed_record_round_trips(self):
        record = executed()
        assert E0AdcCharacterizationV1.from_dict(record.to_dict()) == record

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_numbers_are_refused(self, bad):
        with pytest.raises(E0CharacterizationError) as exc:
            E0NoiseObservationV1.from_dict(
                {"sample_rate_hz": 48000.0, "pga_db": 0.0, "rms_dbfs": bad}
            )
        assert "finite" in exc.value.message

    @pytest.mark.parametrize("bad", [0.0, -48000.0])
    def test_non_positive_physical_frequencies_are_refused(self, bad):
        with pytest.raises(E0CharacterizationError):
            E0NoiseObservationV1.from_dict(
                {"sample_rate_hz": bad, "pga_db": 0.0, "rms_dbfs": -100.0}
            )

    def test_unknown_execution_status_is_refused(self):
        payload = prepared().to_dict()
        payload["execution_status"] = "MOSTLY_DONE"
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_EXECUTION_STATUS_INVALID

    @pytest.mark.parametrize(
        "key",
        ["expected_noise_floor", "proposed_corner_hz", "assumed_full_scale",
         "predicted_offset", "target_attenuation_db"],
    )
    def test_a_field_naming_an_expectation_is_refused(self, key):
        # The protocol is explicit that every field is measured. A specification
        # leaking into an evidence record is how an assumption comes back later
        # wearing the clothes of a measurement.
        payload = prepared().to_dict()
        payload[key] = 1.0
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_SPECULATIVE_FIELD

    @pytest.mark.parametrize("key", ["pass", "verdict", "grade", "quality", "score"])
    def test_a_quality_judgement_field_is_refused(self, key):
        payload = prepared().to_dict()
        payload[key] = True
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_QUALITY_JUDGEMENT

    def test_prepared_may_not_carry_observations(self):
        payload = prepared().to_dict()
        payload["noise_floor"] = [
            {"sample_rate_hz": 48000.0, "pga_db": 0.0, "rms_dbfs": -108.0}
        ]
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_EXECUTION_STATUS_INVALID

    def test_executed_requires_every_observation_group(self):
        payload = executed().to_dict()
        payload["pga"] = []
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_OBSERVATION_MISSING
        assert "pga" in exc.value.message

    def test_partially_executed_is_truthful_with_a_subset(self):
        # The same incomplete document that fails as EXECUTED is fine here.
        payload = executed().to_dict()
        payload["pga"] = []
        payload["execution_status"] = "PARTIALLY_EXECUTED"
        record = E0AdcCharacterizationV1.from_dict(payload)
        assert record.execution_status is E0ExecutionStatus.PARTIALLY_EXECUTED

    def test_a_device_identity_is_required(self):
        payload = prepared().to_dict()
        payload["device"] = None
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_DEVICE_IDENTITY_INCOMPLETE


# ---------------------------------------------------------------------------
# T1 - noise floor and spurs
# ---------------------------------------------------------------------------


class TestT1NoiseFloor:
    def test_sample_rates_and_pga_settings_stay_independent(self):
        record = executed()
        cells = {(n.sample_rate_hz, n.pga_db) for n in record.noise_floor}
        assert len(cells) == len(record.noise_floor)

    def test_discrete_spurs_are_preserved_individually(self):
        # A spur table that survives is what lets a later front-end tone be
        # attributed to the front end rather than the board.
        payload = executed().to_dict()
        payload["spurs"] = [
            {"frequency_hz": 50.0, "level_dbfs": -121.0, "sample_rate_hz": None, "pga_db": None},
            {"frequency_hz": 150.0, "level_dbfs": -128.0, "sample_rate_hz": None, "pga_db": None},
        ]
        record = E0AdcCharacterizationV1.from_dict(payload)
        assert [s.frequency_hz for s in record.spurs] == [50.0, 150.0]

    def test_no_pass_field_exists_on_a_noise_observation(self):
        assert not any(
            k in E0NoiseObservationV1._FIELDS for k in ("pass", "verdict", "acceptable")
        )


# ---------------------------------------------------------------------------
# T2 - PGA
# ---------------------------------------------------------------------------


class TestT2Pga:
    def test_nominal_and_measured_change_are_both_retained(self):
        obs = E0PgaObservationV1(32.0, 32.0, 31.6)
        assert obs.nominal_change_db == 32.0
        assert obs.measured_change_db == 31.6

    def test_gain_error_is_derived_not_stored(self):
        obs = E0PgaObservationV1(32.0, 32.0, 31.6)
        assert obs.gain_error_db == pytest.approx(-0.4)
        assert "gain_error_db" not in obs.to_dict()

    def test_input_referred_noise_is_retained_per_setting(self):
        record = executed()
        noise = {p.setting_db: p.input_referred_noise_dbfs for p in record.pga}
        assert noise == {0.0: -108.4, 32.0: -108.1}

    def test_the_contract_infers_no_pga_architecture(self):
        # Whether the PGA is analog or partly digital is answered by reading the
        # table, not by a field. An incomplete T2 must not produce a conclusion.
        obs = E0PgaObservationV1(32.0, 32.0, 31.6, input_referred_noise_dbfs=None)
        assert obs.to_dict()["input_referred_noise_dbfs"] is None
        assert not hasattr(obs, "is_analog_pga")


# ---------------------------------------------------------------------------
# T3 - coupling
# ---------------------------------------------------------------------------


class TestT3Coupling:
    def test_amplitude_and_phase_are_both_required(self):
        obs = E0CouplingObservationV1.from_dict(
            {"frequency_hz": 70.0, "amplitude_db": -0.31, "phase_deg": 15.9}
        )
        assert obs.phase_deg == 15.9

    def test_missing_phase_cannot_silently_become_zero(self):
        with pytest.raises(E0CharacterizationError) as exc:
            E0CouplingObservationV1.from_dict(
                {"frequency_hz": 70.0, "amplitude_db": -0.31}
            )
        assert exc.value.code is GrantReadinessErrorCode.E0_PHASE_NOT_RECORDED

    def test_null_phase_is_refused_as_explicitly_as_a_missing_one(self):
        with pytest.raises(E0CharacterizationError) as exc:
            E0CouplingObservationV1.from_dict(
                {"frequency_hz": 70.0, "amplitude_db": -0.31, "phase_deg": None}
            )
        assert exc.value.code is GrantReadinessErrorCode.E0_PHASE_NOT_RECORDED

    def test_a_measured_corner_is_preserved(self):
        assert executed().coupling.measured_corner_hz == 18.5

    def test_zero_phase_is_a_legitimate_measurement(self):
        # Refusing a missing phase must not refuse a real zero.
        obs = E0CouplingObservationV1.from_dict(
            {"frequency_hz": 500.0, "amplitude_db": 0.0, "phase_deg": 0.0}
        )
        assert obs.phase_deg == 0.0


# ---------------------------------------------------------------------------
# T4 - out of band
# ---------------------------------------------------------------------------


class TestT4OutOfBand:
    def test_injected_and_apparent_frequencies_are_separate(self):
        row = next(o for o in executed().out_of_band if o.injected_hz == 30000.0)
        assert row.apparent_hz == 18000.0
        assert row.injected_hz != row.apparent_hz

    def test_attenuation_is_retained(self):
        row = next(o for o in executed().out_of_band if o.injected_hz == 30000.0)
        assert row.attenuation_db == -6.2

    def test_an_unsupported_frequency_cannot_be_recorded_as_measured(self):
        with pytest.raises(E0CharacterizationError) as exc:
            E0OutOfBandObservationV1.from_dict(
                {
                    "injected_hz": 200000.0,
                    "source_state": "BLOCKED_BY_SOURCE_CAPABILITY",
                    "apparent_hz": 8000.0,
                    "attenuation_db": -40.0,
                }
            )
        assert exc.value.code is GrantReadinessErrorCode.E0_SOURCE_CAPABILITY_MISREPRESENTED

    def test_a_measured_row_must_carry_its_numbers(self):
        with pytest.raises(E0CharacterizationError) as exc:
            E0OutOfBandObservationV1.from_dict(
                {"injected_hz": 30000.0, "source_state": "MEASURED"}
            )
        assert exc.value.code is GrantReadinessErrorCode.E0_SOURCE_CAPABILITY_MISREPRESENTED

    def test_partial_t4_is_represented_rather_than_fabricated(self):
        blocked = [
            o for o in executed().out_of_band
            if o.source_state is E0SourceCapability.BLOCKED_BY_SOURCE_CAPABILITY
        ]
        assert [o.injected_hz for o in blocked] == [200000.0]
        assert blocked[0].apparent_hz is None
        assert blocked[0].attenuation_db is None

    def test_a_declared_source_bandwidth_binds_every_measured_row(self):
        payload = executed().to_dict()
        payload["out_of_band"].append(
            {
                "injected_hz": 150000.0,
                "source_state": "MEASURED",
                "apparent_hz": 6000.0,
                "attenuation_db": -50.0,
                "sample_rate_hz": 48000.0,
            }
        )
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_SOURCE_CAPABILITY_MISREPRESENTED

    def test_the_contract_never_closes_b014(self):
        # A T4 section existing is not an aliasing answer. Nothing in the record
        # or its API reports a backlog disposition.
        record = executed()
        assert not hasattr(record, "b014_closed")
        assert "b014" not in json.dumps(record.to_dict()).lower()


# ---------------------------------------------------------------------------
# T5 - balanced granularity
# ---------------------------------------------------------------------------


class TestT5BalancedScope:
    @pytest.mark.parametrize("value", ["PER_CHANNEL", "GLOBAL", "UNKNOWN"])
    def test_each_canonical_granularity_is_handled(self, value):
        obs = E0BalancedInputObservationV1.from_dict({"granularity": value})
        assert obs.granularity.value == value

    def test_unknown_granularity_stays_unknown(self):
        # Not a synonym for GLOBAL: an unread control and a control shown to be
        # board-wide have different consequences for the E1 rig.
        obs = E0BalancedInputObservationV1.from_dict({})
        assert obs.granularity is E0ControlGranularity.UNKNOWN

    def test_balanced_and_unbalanced_full_scale_stay_distinguishable(self):
        obs = executed().balanced_scope
        assert obs.unbalanced_full_scale_vrms == 2.05
        assert obs.balanced_full_scale_vrms == 4.11

    def test_which_instrument_the_answer_applies_to_is_recorded(self):
        assert "E1" in executed().balanced_scope.applies_to


# ---------------------------------------------------------------------------
# T6 - full scale
# ---------------------------------------------------------------------------


class TestT6FullScale:
    def test_thd_point_and_hard_clip_remain_separate(self):
        row = next(f for f in executed().full_scale if f.path is E0InputPath.UNBALANCED)
        assert row.thd_0p1pct_vrms == 2.02
        assert row.hard_clip_vrms == 2.11
        assert row.thd_0p1pct_vrms != row.hard_clip_vrms

    def test_balanced_and_unbalanced_cannot_be_conflated(self):
        payload = executed().to_dict()
        payload["full_scale"] = [
            {"path": "UNBALANCED", "thd_0p1pct_vrms": 2.02, "hard_clip_vrms": 2.11,
             "specified_vrms": 2.1},
            {"path": "UNBALANCED", "thd_0p1pct_vrms": 4.05, "hard_clip_vrms": 4.20,
             "specified_vrms": 4.2},
        ]
        with pytest.raises(E0CharacterizationError) as exc:
            E0AdcCharacterizationV1.from_dict(payload)
        assert exc.value.code is GrantReadinessErrorCode.E0_MEASUREMENT_CONFLATED

    def test_the_specified_figure_is_recorded_beside_the_measured_one(self):
        row = next(f for f in executed().full_scale if f.path is E0InputPath.BALANCED)
        assert row.specified_vrms == 4.2
        assert row.hard_clip_vrms == 4.20


# ---------------------------------------------------------------------------
# T7 - loopback
# ---------------------------------------------------------------------------


class TestT7Loopback:
    def test_mean_and_stddev_are_retained_separately(self):
        obs = executed().loopback
        assert obs.mean_offset_samples == 1412.0
        assert obs.stddev_samples == 3.1

    def test_within_session_stability_is_explicit(self):
        assert executed().loopback.within_session_stable is True

    def test_zero_offset_is_distinguishable_from_unknown_offset(self):
        measured_zero = E0LoopbackObservationV1.from_dict({"mean_offset_samples": 0.0})
        unknown = E0LoopbackObservationV1.from_dict({})
        assert measured_zero.mean_offset_samples == 0.0
        assert unknown.mean_offset_samples is None
        assert measured_zero != unknown

    def test_negative_spread_is_refused(self):
        with pytest.raises(E0CharacterizationError):
            E0LoopbackObservationV1.from_dict({"stddev_samples": -1.0})

    def test_unknown_stability_is_not_false(self):
        assert E0LoopbackObservationV1.from_dict({}).within_session_stable is None


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------


class TestBoundaries:
    @pytest.mark.parametrize(
        "key", ["microphone_response", "plate_modes", "modal_frequencies", "wolf_note"]
    )
    def test_e0_cannot_contain_acoustic_results(self, key):
        # No plate is involved in E0 and no microphone is connected.
        payload = prepared().to_dict()
        payload[key] = [1.0]
        with pytest.raises(E0CharacterizationError):
            E0AdcCharacterizationV1.from_dict(payload)

    @pytest.mark.parametrize(
        "key", ["selected", "approved", "procurement_action", "purchase_authorized"]
    )
    def test_e0_cannot_promote_or_authorize(self, key):
        payload = prepared().to_dict()
        payload[key] = True
        with pytest.raises(E0CharacterizationError):
            E0AdcCharacterizationV1.from_dict(payload)

    def test_executed_is_not_a_selection_ruling(self):
        record = executed()
        blob = json.dumps(record.to_dict()).lower()
        for claim in ("selected", "approved", "verified_on_hardware", "recommend"):
            assert claim not in blob

    def test_the_schema_forbids_extra_fields_throughout(self, schema):
        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    assert node.get("additionalProperties") is False, node.get("title", node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(schema)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class TestTheImportedDocuments:
    @pytest.fixture(scope="class")
    def stack(self):
        return (HARDWARE / "TTP_ELECTRICAL_STACK_BOM.md").read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def protocol(self):
        return (HARDWARE / "TTP_E0_ADC_CHARACTERIZATION.md").read_text(encoding="utf-8")

    def test_the_stack_bom_remains_non_authoritative(self, stack):
        assert "Not authoritative" in stack
        assert "Nothing here authorizes procurement" in stack

    def test_the_missing_test_rig_bom_is_recorded_not_fabricated(self, stack):
        flat = " ".join(stack.replace(">", " ").split()).lower()
        assert "is not present in this repository" in flat
        assert not (HARDWARE / "TTP_TEST_RIG_BOM.md").exists()

    def test_the_two_corrections_survive_the_missing_document(self, stack):
        # The correction must not weaken just because its original is absent.
        assert "B-014" in stack
        assert "not an established exact phase reference" in stack

    def test_the_protocol_is_prepared_and_not_executed(self, protocol):
        assert "NOT EXECUTED" in protocol
        assert "Execution gate" in protocol

    def test_the_protocol_records_the_t4_source_limit(self, protocol):
        assert "BLOCKED_BY_SOURCE_CAPABILITY" in protocol
        assert "no signal-generator model is invented" in protocol

    def test_the_protocol_no_longer_claims_a_phase2_session(self, protocol):
        assert "Not a Phase 2 session" in protocol

    def test_t1_still_states_it_has_no_pass_condition(self, protocol):
        assert "**Pass condition:** none" in protocol

    def test_no_afe_filter_order_or_corner_is_asserted_anywhere(self):
        # AFE-001 stays evidence-derived. Until an executed E0 exists, no
        # document may state a filter order, corner, or stopband as a fact.
        for name in ("TTP_ELECTRICAL_STACK_BOM.md", "TTP_E0_ADC_CHARACTERIZATION.md"):
            text = (HARDWARE / name).read_text(encoding="utf-8").lower()
            assert "afe-001 is a " not in text or "derived" in text
            for claim in ("filter order 4", "corner is 20 khz", "selected filter"):
                assert claim not in text

    def test_e1_hardware_status_is_unchanged(self):
        census = (HARDWARE / "TTP_E1_OWNERSHIP_CENSUS.md").read_text(encoding="utf-8")
        assert "CONFIRMED_ABSENT" in census
        # ADC-001 is still not owned; E0 cannot run.
        adc_row = next(
            line for line in census.splitlines()
            if line.startswith("| 2 ") and "ADC-001" in line
        )
        assert "CONFIRMED_ABSENT" in adc_row


# ---------------------------------------------------------------------------
# End to end, and the tamper battery
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def _run(self, tmp_path, payload):
        import subprocess

        target = tmp_path / "e0.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return subprocess.run(
            [__import__("sys").executable, str(REPO_ROOT / "scripts" / "ttp_e0_adc_check.py"), str(target)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

    def test_a_prepared_record_passes_the_checker(self, tmp_path):
        result = self._run(tmp_path, prepared().to_dict())
        assert result.returncode == 0, result.stderr
        assert "structurally truthful" in result.stdout

    def test_an_executed_record_passes_the_checker(self, tmp_path):
        result = self._run(tmp_path, executed().to_dict())
        assert result.returncode == 0, result.stderr

    def test_the_checker_never_claims_the_adc_is_good(self, tmp_path):
        result = self._run(tmp_path, executed().to_dict())
        assert "says nothing about whether the ADC is any good" in result.stdout

    def test_tampering_with_execution_status_fails_loudly(self, tmp_path):
        payload = executed().to_dict()
        payload["execution_status"] = "PREPARED"
        result = self._run(tmp_path, payload)
        assert result.returncode == 1
        assert "PREPARED" in result.stderr

    def test_tampering_with_a_t3_phase_fails_loudly(self, tmp_path):
        payload = executed().to_dict()
        del payload["coupling"]["points"][0]["phase_deg"]
        result = self._run(tmp_path, payload)
        assert result.returncode == 1
        assert "phase" in result.stderr.lower()

    def test_tampering_with_a_t4_source_claim_fails_loudly(self, tmp_path):
        payload = executed().to_dict()
        blocked = next(
            o for o in payload["out_of_band"]
            if o["source_state"] == "BLOCKED_BY_SOURCE_CAPABILITY"
        )
        blocked["source_state"] = "MEASURED"
        blocked["apparent_hz"] = 8000.0
        blocked["attenuation_db"] = -40.0
        result = self._run(tmp_path, payload)
        assert result.returncode == 1
        assert "source" in result.stderr.lower() or "bandwidth" in result.stderr.lower()

    def test_removing_a_required_executed_observation_fails(self, tmp_path):
        payload = executed().to_dict()
        payload["full_scale"] = []
        result = self._run(tmp_path, payload)
        assert result.returncode == 1

    def test_the_same_subset_marked_partial_is_accepted(self, tmp_path):
        payload = executed().to_dict()
        payload["full_scale"] = []
        payload["execution_status"] = "PARTIALLY_EXECUTED"
        result = self._run(tmp_path, payload)
        assert result.returncode == 0, result.stderr

    def test_an_artifact_digest_mismatch_is_caught(self, tmp_path):
        wav = tmp_path / "t1.wav"
        wav.write_bytes(b"not really a wav")
        payload = executed().to_dict()
        payload["provenance"]["artifacts"] = [
            {
                "artifact_id": "T1-48k-0dB",
                "kind": "wav",
                "sha256": "0" * 64,
                "byte_length": None,
                "locator": "t1.wav",
            }
        ]
        result = self._run(tmp_path, payload)
        assert result.returncode == 1
        assert "digest mismatch" in result.stderr

    def test_the_checker_writes_nothing(self):
        source = (REPO_ROOT / "scripts" / "ttp_e0_adc_check.py").read_text(encoding="utf-8")
        assert "write_text" not in source
        assert "write_bytes" not in source

    def test_the_checker_computes_no_score(self):
        source = (REPO_ROOT / "scripts" / "ttp_e0_adc_check.py").read_text(encoding="utf-8")
        for banned in ("def score", "def grade", "def passed", "PASS_THRESHOLD"):
            assert banned not in source

    def test_the_schema_version_is_pinned(self):
        assert E0_SCHEMA_VERSION == "e0_adc_characterization_v1"
        payload = prepared().to_dict()
        payload["schema_version"] = "e0_adc_characterization_v2"
        with pytest.raises(E0CharacterizationError):
            E0AdcCharacterizationV1.from_dict(payload)


class TestTheResultsStub:
    """The results file must stay empty until a bench produces something."""

    @pytest.fixture(scope="class")
    def stub(self):
        return (HARDWARE / "TTP_E0_ADC_CHARACTERIZATION_RESULTS.md").read_text(
            encoding="utf-8"
        )

    def test_it_says_not_executed(self, stub):
        assert "STATUS: NOT EXECUTED" in stub
        assert "ADC-001 has not been characterized." in stub

    def test_b014_is_recorded_as_open(self, stub):
        assert "B-014 remains open." in stub

    def test_no_afe_requirement_is_derived(self, stub):
        assert "No AFE-001 filter requirement has been derived." in stub

    def test_no_measurement_is_pre_populated(self, stub):
        # The failure this guards is a plausible number written into an empty
        # results file, which is a specification that reads as a measurement.
        flat = stub.lower()
        for unit in ("dbfs", "vrms measured", "corner is", "attenuation of"):
            if unit == "dbfs":
                # The word may appear in prose about what E0 will produce, but
                # never attached to a number.
                import re

                assert not re.search(r"-?\d+(\.\d+)?\s*dbfs", flat), flat
            else:
                assert unit not in flat

    def test_the_acquisition_tooling_is_recorded_as_absent(self, stub):
        assert "ttp_e0_adc.py" in stub
        assert "successor development order" in stub

    def test_artifacts_are_standalone_not_phase2_sessions(self, stub):
        assert "not a Phase 2 session" in stub
        assert "synthetic" in stub


class TestStatusReconciliation:
    """DO-106 changed the software state and none of the physical state."""

    @pytest.fixture(scope="class")
    def current(self):
        return (REPO_ROOT / "docs" / "dev_orders" / "CURRENT.md").read_text(
            encoding="utf-8"
        )

    @pytest.fixture(scope="class")
    def sprints(self):
        return (REPO_ROOT / "SPRINTS.md").read_text(encoding="utf-8")

    def test_e0_is_not_executed(self, current):
        assert "**NOT EXECUTED**" in current

    def test_the_adc_procurement_state_is_unchanged(self, current):
        assert "CONFIRMED_ABSENT" in current

    def test_the_do104_deferral_still_stands(self, current):
        # DO-106 must not reopen settled DO-104 governance to express a simpler
        # build sequence.
        assert "SELECTION_DEFERRED" in current
        assert "PARKED OPEN" in current

    def test_afe_and_downstream_stay_blocked(self, current):
        assert "BLOCKED ON E0" in current
        assert "not authorized" in current

    def test_nothing_is_promoted(self, current):
        assert "Nothing is promoted" in current
        assert "PURCHASE_AUTHORIZED" not in current

    def test_b014_and_b015_remain_open(self, sprints):
        for item in ("B-014", "B-015"):
            block = sprints.split(f"### {item}")[1].split("### ")[0]
            assert "**Status:** open" in block, item

    def test_b014_records_that_e0_does_not_close_it(self, sprints):
        block = sprints.split("### B-014")[1].split("### ")[0]
        assert "did not close this" in block

    def test_b015_records_the_lead_as_a_lead(self, sprints):
        block = sprints.split("### B-015")[1].split("### ")[0]
        assert "not a closure" in block.lower()

    def test_b018_records_the_missing_acquisition_tooling(self, sprints):
        block = sprints.split("### B-018")[1].split("### ")[0]
        assert "**Status:** open" in block
        assert "ttp_e0_adc.py" in block

    def test_no_partial_acquisition_cli_was_shipped(self):
        assert not (REPO_ROOT / "scripts" / "ttp_e0_adc.py").exists()
