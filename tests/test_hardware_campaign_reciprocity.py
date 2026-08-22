"""Reciprocity pairing and residuals (DO-103 E4).

Reciprocity asks whether driving at A and measuring at B agrees with the
transpose. Two things have to hold for the answer to mean anything: the pairing
must be a transpose and nothing looser, and the reporting must stay free of a
threshold. DO-103 §4.6 is explicit that no acceptance figure is invented here —
a poor residual is what the experiment is for, and a setup tuned until the
result looks good would answer a question nobody asked.
"""

from __future__ import annotations

import pytest

from tap_tone_pi.grant_readiness import (
    CampaignConditionV1,
    EvidenceOrigin,
    ExperimentKind,
    GrantReadinessErrorCode,
    ObservedFeatureV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
)
from tap_tone_pi.grant_readiness.errors import (
    HardwareCampaignError,
    RepeatabilityStatisticsError,
)
from tap_tone_pi.grant_readiness.hardware_campaign import (
    pair_reciprocity_runs,
    summarize_reciprocity,
)
from tap_tone_pi.grant_readiness.phase2_experiment import (
    COHERENCE,
    EVALUATION_FREQUENCY,
    TRANSFER_MAGNITUDE,
)
from tap_tone_pi.grant_readiness.validation import validate_reciprocity_observation

UTC_NOW = "2026-08-22T12:00:00+00:00"
UNIT = "Pa/N"


def make_run(
    run_id: str,
    value: float | None,
    drive: str | None,
    response: str | None,
    *,
    coherence: float | None = 0.95,
    frequency: float | None = 220.0,
    valid: bool = True,
    unit: str = UNIT,
    kind: ExperimentKind = ExperimentKind.RECIPROCITY,
) -> PreliminaryExperimentRunV1:
    features = []
    if value is not None:
        features.append(ObservedFeatureV1(TRANSFER_MAGNITUDE, unit, value))
    if coherence is not None:
        features.append(ObservedFeatureV1(COHERENCE, "unitless", coherence))
    if frequency is not None:
        features.append(ObservedFeatureV1(EVALUATION_FREQUENCY, "Hz", frequency))
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="e4",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=valid,
        rejection_reason=None if valid else RejectionReason.CLIPPING,
        source_artifact_ids=(f"fixtures/{run_id}.json",),
        observed_features=tuple(features),
        campaign_condition=CampaignConditionV1(
            kind, drive_point_id=drive, response_point_id=response
        ),
    )


def codes(error: HardwareCampaignError) -> str:
    return error.code.value


class TestPairing:
    def test_a_transpose_pair_is_found(self):
        runs = [make_run("f1", 1.0, "A", "B"), make_run("v1", 0.9, "B", "A")]
        pairs = pair_reciprocity_runs(runs)
        assert [(f.run_id, r.run_id) for f, r in pairs] == [("f1", "v1")]

    def test_the_forward_direction_is_deterministic(self):
        # Whichever order the runs arrive in, the direction whose drive point
        # sorts first is the forward one, so a report does not change between
        # runs of the same data.
        forward_first = pair_reciprocity_runs(
            [make_run("f1", 1.0, "A", "B"), make_run("v1", 0.9, "B", "A")]
        )
        reverse_first = pair_reciprocity_runs(
            [make_run("v1", 0.9, "B", "A"), make_run("f1", 1.0, "A", "B")]
        )
        assert forward_first[0][0].run_id == reverse_first[0][0].run_id == "f1"

    def test_several_pairs_are_returned_in_a_stable_order(self):
        runs = [
            make_run("cd1", 1.0, "C", "D"),
            make_run("dc1", 1.0, "D", "C"),
            make_run("ab1", 1.0, "A", "B"),
            make_run("ba1", 1.0, "B", "A"),
        ]
        pairs = pair_reciprocity_runs(runs)
        assert [f.run_id for f, _ in pairs] == ["ab1", "cd1"]

    def test_a_missing_reverse_direction_is_refused(self):
        with pytest.raises(HardwareCampaignError) as excinfo:
            pair_reciprocity_runs([make_run("f1", 1.0, "A", "B")])
        assert codes(excinfo.value) == "NSF-503"
        assert excinfo.value.context["unpaired_run_ids"] == ["f1"]

    def test_an_unequal_number_of_directions_is_refused(self):
        runs = [
            make_run("f1", 1.0, "A", "B"),
            make_run("f2", 1.0, "A", "B"),
            make_run("v1", 0.9, "B", "A"),
        ]
        with pytest.raises(HardwareCampaignError) as excinfo:
            pair_reciprocity_runs(runs)
        assert codes(excinfo.value) == "NSF-503"
        assert excinfo.value.context["unpaired_run_ids"] == ["f2"]

    def test_a_pair_sharing_one_point_is_not_a_transpose(self):
        # A→B and B→C are different measurements, not two directions of one.
        runs = [make_run("f1", 1.0, "A", "B"), make_run("v1", 0.9, "B", "C")]
        with pytest.raises(HardwareCampaignError) as excinfo:
            pair_reciprocity_runs(runs)
        assert codes(excinfo.value) == "NSF-503"

    def test_driving_and_measuring_at_one_point_is_refused(self):
        with pytest.raises(HardwareCampaignError) as excinfo:
            pair_reciprocity_runs([make_run("f1", 1.0, "A", "A")])
        assert codes(excinfo.value) == "NSF-504"

    def test_a_run_with_no_point_pair_is_refused(self):
        with pytest.raises(HardwareCampaignError) as excinfo:
            pair_reciprocity_runs([make_run("f1", 1.0, "A", None)])
        assert codes(excinfo.value) == "NSF-502"

    def test_rejected_runs_are_not_paired(self):
        runs = [
            make_run("f1", 1.0, "A", "B"),
            make_run("v1", 0.9, "B", "A"),
            make_run("v2", None, "B", "A", valid=False),
        ]
        assert len(pair_reciprocity_runs(runs)) == 1

    def test_runs_from_another_experiment_are_not_paired(self):
        runs = [
            make_run("m1", 1.0, "A", "B", kind=ExperimentKind.MASS_LOADING),
            make_run("m2", 0.9, "B", "A", kind=ExperimentKind.MASS_LOADING),
        ]
        assert pair_reciprocity_runs(runs) == ()


class TestResiduals:
    def observe(self, forward: float, reverse: float, **kwargs):
        runs = [
            make_run("f1", forward, "A", "B", **kwargs.pop("forward_kwargs", {})),
            make_run("v1", reverse, "B", "A", **kwargs.pop("reverse_kwargs", {})),
        ]
        return summarize_reciprocity(
            pair_reciprocity_runs(runs), quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]

    def test_the_residual_is_the_absolute_difference(self):
        assert self.observe(1.0, 0.9).absolute_residual == pytest.approx(0.1)

    def test_the_residual_does_not_depend_on_the_direction_order(self):
        assert self.observe(0.9, 1.0).absolute_residual == pytest.approx(0.1)

    def test_the_relative_residual_scales_by_the_mean_magnitude(self):
        observation = self.observe(1.0, 0.9)
        assert observation.relative_residual == pytest.approx(0.1 / 0.95)

    def test_a_relative_residual_is_unknown_where_it_cannot_be_scaled(self):
        observation = self.observe(0.0, 0.0)
        assert observation.relative_residual is None
        assert observation.absolute_residual == 0.0

    def test_both_coherences_are_kept_separately(self):
        observation = self.observe(
            1.0,
            0.9,
            forward_kwargs={"coherence": 0.98},
            reverse_kwargs={"coherence": 0.31},
        )
        assert observation.forward_coherence == 0.98
        assert observation.reverse_coherence == 0.31

    def test_a_missing_coherence_stays_unknown(self):
        observation = self.observe(1.0, 0.9, reverse_kwargs={"coherence": None})
        assert observation.forward_coherence == 0.95
        assert observation.reverse_coherence is None

    def test_the_forward_evaluation_frequency_is_recorded(self):
        assert self.observe(1.0, 0.9).evaluation_frequency_hz == 220.0

    def test_the_points_are_recorded_in_the_forward_direction(self):
        observation = self.observe(1.0, 0.9)
        assert observation.forward_drive_point_id == "A"
        assert observation.forward_response_point_id == "B"

    def test_a_large_residual_is_reported_not_flagged(self):
        # The whole point of E4: a bad result is evidence, and nothing here
        # turns it into a failure.
        observation = self.observe(1.0, 0.05)
        assert observation.relative_residual > 1.0
        assert not {"passed", "is_acceptable", "verdict"} & set(observation.to_dict())

    def test_a_run_that_observed_nothing_is_refused(self):
        runs = [make_run("f1", None, "A", "B"), make_run("v1", 0.9, "B", "A")]
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_reciprocity(
                pair_reciprocity_runs(runs), quantity=TRANSFER_MAGNITUDE, unit=UNIT
            )
        assert excinfo.value.code is (
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS
        )

    def test_a_unit_mismatch_is_refused(self):
        runs = [
            make_run("f1", 1.0, "A", "B"),
            make_run("v1", 0.9, "B", "A", unit="ratio"),
        ]
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_reciprocity(
                pair_reciprocity_runs(runs), quantity=TRANSFER_MAGNITUDE, unit=UNIT
            )
        assert excinfo.value.code is (
            GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS
        )

    def test_observation_ids_are_stable_and_distinct(self):
        runs = [
            make_run("ab1", 1.0, "A", "B"),
            make_run("ba1", 0.9, "B", "A"),
            make_run("cd1", 1.0, "C", "D"),
            make_run("dc1", 0.8, "D", "C"),
        ]
        observations = summarize_reciprocity(
            pair_reciprocity_runs(runs), quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )
        ids = [observation.observation_id for observation in observations]
        assert ids == sorted(set(ids))


class TestObservationValidation:
    def make(self, **overrides):
        runs = [make_run("f1", 1.0, "A", "B"), make_run("v1", 0.9, "B", "A")]
        observation = summarize_reciprocity(
            pair_reciprocity_runs(runs), quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        import dataclasses

        return dataclasses.replace(observation, **overrides)

    def test_a_well_formed_observation_validates(self):
        assert validate_reciprocity_observation(self.make()) == []

    def test_a_run_paired_with_itself_is_refused(self):
        findings = validate_reciprocity_observation(self.make(reverse_run_id="f1"))
        assert [f.code.value for f in findings] == ["NSF-503"]

    def test_a_self_pair_is_refused(self):
        findings = validate_reciprocity_observation(
            self.make(forward_response_point_id="A")
        )
        assert [f.code.value for f in findings] == ["NSF-504"]

    def test_a_negative_residual_is_refused(self):
        findings = validate_reciprocity_observation(self.make(absolute_residual=-0.1))
        assert [f.code.value for f in findings] == ["NSF-303"]

    @pytest.mark.parametrize("value", [-0.1, 1.5])
    def test_a_coherence_outside_its_own_interval_is_refused(self, value):
        # Coherence is defined on [0, 1]. This checks that a record is a record;
        # it is not a quality threshold, and no coherence inside the interval is
        # ever compared against anything.
        findings = validate_reciprocity_observation(self.make(forward_coherence=value))
        assert [f.code.value for f in findings] == ["NSF-303"]

    @pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
    def test_every_defined_coherence_is_accepted(self, value):
        assert (
            validate_reciprocity_observation(self.make(reverse_coherence=value)) == []
        )
