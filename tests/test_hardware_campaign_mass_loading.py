"""Deliberate mass-loading challenge (DO-103 E5).

E5 puts a known mass on the specimen and asks whether the measurement notices.
Two rules shape every test here. The mass must be *measured* — DO-103 §4.7
forbids a nominal figure standing in for what was actually put on — and no
response size is judged, because deciding in advance how much movement would
count would answer the question the experiment exists to ask.

The comparison is between summarized groups rather than single captures, so the
spread each mean sits in travels with it. A delta smaller than that spread is
not a detection, and only a reader who can see both can tell.
"""

from __future__ import annotations

import dataclasses

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
    group_runs_by_added_mass,
    summarize_mass_loading,
)
from tap_tone_pi.grant_readiness.phase2_experiment import TRANSFER_MAGNITUDE
from tap_tone_pi.grant_readiness.validation import (
    validate_mass_loading_observation,
    validate_run_campaign_condition,
)

UTC_NOW = "2026-08-22T12:00:00+00:00"
UNIT = "Pa/N"


def make_run(
    run_id: str,
    value: float | None,
    *,
    challenge: str | None,
    added_mass_g: float | None,
    nominal: float | None = None,
    location: str | None = None,
    valid: bool = True,
    kind: ExperimentKind = ExperimentKind.MASS_LOADING,
) -> PreliminaryExperimentRunV1:
    features = ()
    if value is not None:
        features = (ObservedFeatureV1(TRANSFER_MAGNITUDE, UNIT, value),)
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="e5",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=valid,
        rejection_reason=None if valid else RejectionReason.CLIPPING,
        source_artifact_ids=(f"fixtures/{run_id}.json",),
        observed_features=features,
        campaign_condition=CampaignConditionV1(
            kind,
            mass_challenge_id=challenge,
            added_mass_g=added_mass_g,
            nominal_added_mass_g=nominal,
            mass_location_id=location,
        ),
    )


def baseline_runs(*values: float) -> list[PreliminaryExperimentRunV1]:
    return [
        make_run(f"b{i}", value, challenge="baseline", added_mass_g=0.0)
        for i, value in enumerate(values, start=1)
    ]


def challenge_runs(
    challenge: str, mass: float, *values: float, **kwargs
) -> list[PreliminaryExperimentRunV1]:
    return [
        make_run(
            f"{challenge}-{i}", value, challenge=challenge, added_mass_g=mass, **kwargs
        )
        for i, value in enumerate(values, start=1)
    ]


class TestGroupingByMass:
    def test_runs_group_by_challenge(self):
        runs = baseline_runs(1.0, 1.02) + challenge_runs("m2", 2.03, 0.9, 0.88)
        grouped = group_runs_by_added_mass(runs)
        assert set(grouped) == {"baseline", "m2"}

    def test_an_unmeasured_mass_is_refused(self):
        runs = [make_run("m1", 0.9, challenge="m2", added_mass_g=None, nominal=2.0)]
        with pytest.raises(HardwareCampaignError) as excinfo:
            group_runs_by_added_mass(runs)
        assert excinfo.value.code.value == "NSF-505"

    def test_a_negative_mass_is_refused(self):
        runs = [make_run("m1", 0.9, challenge="m2", added_mass_g=-1.0)]
        with pytest.raises(HardwareCampaignError) as excinfo:
            group_runs_by_added_mass(runs)
        assert excinfo.value.code.value == "NSF-505"

    def test_one_challenge_id_may_not_cover_two_masses(self):
        runs = challenge_runs("m2", 2.03, 0.9) + challenge_runs("m2", 5.01, 0.7)
        with pytest.raises(HardwareCampaignError) as excinfo:
            group_runs_by_added_mass(runs)
        assert excinfo.value.code.value == "NSF-506"

    def test_rejected_runs_do_not_enter_a_group(self):
        runs = baseline_runs(1.0, 1.02) + [
            make_run("b3", None, challenge="baseline", added_mass_g=0.0, valid=False)
        ]
        assert [run.run_id for run in group_runs_by_added_mass(runs)["baseline"]] == [
            "b1",
            "b2",
        ]

    def test_runs_from_another_experiment_are_ignored(self):
        runs = [
            make_run(
                "x1",
                1.0,
                challenge="m2",
                added_mass_g=2.0,
                kind=ExperimentKind.FIXED_POINT,
            )
        ]
        assert group_runs_by_added_mass(runs) == {}


class TestDeltas:
    def test_the_delta_is_computed_against_the_baseline(self):
        runs = baseline_runs(1.00, 1.02) + challenge_runs("m2", 2.03, 0.90, 0.88)
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        assert observation.baseline_metric.mean == pytest.approx(1.01)
        assert observation.loaded_metric.mean == pytest.approx(0.89)
        assert observation.absolute_delta == pytest.approx(-0.12)

    def test_the_delta_keeps_its_sign(self):
        runs = baseline_runs(1.00, 1.02) + challenge_runs("m2", 2.03, 1.20, 1.22)
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        assert observation.absolute_delta > 0

    def test_the_relative_delta_is_scaled_by_the_baseline(self):
        runs = baseline_runs(1.00, 1.00) + challenge_runs("m2", 2.03, 0.90, 0.90)
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        assert observation.relative_delta_pct == pytest.approx(-10.0)

    def test_the_measured_mass_is_what_is_reported(self):
        runs = baseline_runs(1.0, 1.0) + challenge_runs(
            "m2", 2.03, 0.9, 0.9, nominal=2.0, location="bridge"
        )
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        assert observation.added_mass_g == 2.03
        assert observation.nominal_added_mass_g == 2.0
        assert observation.mass_location_id == "bridge"

    def test_every_challenge_is_compared_and_ordered_stably(self):
        runs = (
            baseline_runs(1.0, 1.0)
            + challenge_runs("m5", 5.01, 0.7, 0.72)
            + challenge_runs("m2", 2.03, 0.9, 0.88)
        )
        observations = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )
        assert [o.mass_challenge_id for o in observations] == ["m2", "m5"]

    def test_a_challenge_that_moved_nothing_is_still_reported(self):
        # A null result is a finding about the measurement architecture.
        runs = baseline_runs(1.0, 1.0) + challenge_runs("m2", 2.03, 1.0, 1.0)
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        assert observation.absolute_delta == pytest.approx(0.0)
        assert not {"detected", "passed", "verdict"} & set(observation.to_dict())

    def test_loaded_runs_with_no_baseline_are_refused(self):
        with pytest.raises(HardwareCampaignError) as excinfo:
            summarize_mass_loading(
                challenge_runs("m2", 2.03, 0.9, 0.88),
                quantity=TRANSFER_MAGNITUDE,
                unit=UNIT,
            )
        assert excinfo.value.code.value == "NSF-507"

    def test_a_baseline_alone_yields_no_observation(self):
        assert (
            summarize_mass_loading(
                baseline_runs(1.0, 1.02), quantity=TRANSFER_MAGNITUDE, unit=UNIT
            )
            == ()
        )

    def test_no_mass_loading_runs_yields_no_observation(self):
        assert summarize_mass_loading([], quantity=TRANSFER_MAGNITUDE, unit=UNIT) == ()

    def test_a_single_baseline_capture_cannot_anchor_a_comparison(self):
        runs = baseline_runs(1.0) + challenge_runs("m2", 2.03, 0.9, 0.88)
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_mass_loading(runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT)
        assert excinfo.value.code is (
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS
        )

    def test_a_single_loaded_capture_cannot_be_compared(self):
        runs = baseline_runs(1.0, 1.02) + challenge_runs("m2", 2.03, 0.9)
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_mass_loading(runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT)
        assert excinfo.value.code is (
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS
        )

    def test_both_groups_keep_their_spread(self):
        runs = baseline_runs(1.00, 1.02, 0.99) + challenge_runs(
            "m2", 2.03, 0.90, 0.88, 0.91
        )
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        assert observation.baseline_metric.sample_count == 3
        assert observation.loaded_metric.sample_count == 3
        assert observation.baseline_metric.standard_deviation > 0
        assert observation.loaded_metric.standard_deviation > 0

    def test_each_metric_names_the_runs_behind_it(self):
        runs = baseline_runs(1.0, 1.02) + challenge_runs("m2", 2.03, 0.9, 0.88)
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        assert observation.baseline_metric.source_run_ids == ("b1", "b2")
        assert observation.loaded_metric.source_run_ids == ("m2-1", "m2-2")


class TestConditionValidation:
    def test_a_mass_run_must_record_its_challenge_and_mass(self):
        run = make_run("m1", 0.9, challenge=None, added_mass_g=None)
        findings = validate_run_campaign_condition(run)
        assert [f.code.value for f in findings] == ["NSF-502"]

    def test_an_intended_mass_without_a_measured_one_is_refused(self):
        run = make_run("m1", 0.9, challenge="m2", added_mass_g=None, nominal=2.0)
        codes = [f.code.value for f in validate_run_campaign_condition(run)]
        assert "NSF-505" in codes

    def test_a_negative_mass_is_refused(self):
        run = make_run("m1", 0.9, challenge="m2", added_mass_g=-2.0)
        codes = [f.code.value for f in validate_run_campaign_condition(run)]
        assert "NSF-505" in codes

    def test_a_well_formed_challenge_validates(self):
        run = make_run("m1", 0.9, challenge="m2", added_mass_g=2.03, nominal=2.0)
        assert validate_run_campaign_condition(run) == []

    def test_a_baseline_validates(self):
        run = make_run("b1", 1.0, challenge="baseline", added_mass_g=0.0)
        assert validate_run_campaign_condition(run) == []


class TestObservationValidation:
    def make(self, **overrides):
        runs = baseline_runs(1.0, 1.02) + challenge_runs("m2", 2.03, 0.9, 0.88)
        observation = summarize_mass_loading(
            runs, quantity=TRANSFER_MAGNITUDE, unit=UNIT
        )[0]
        return dataclasses.replace(observation, **overrides)

    def test_a_well_formed_observation_validates(self):
        assert validate_mass_loading_observation(self.make()) == []

    def test_a_challenge_that_adds_no_mass_is_refused(self):
        findings = validate_mass_loading_observation(self.make(added_mass_g=0.0))
        assert [f.code.value for f in findings] == ["NSF-505"]

    def test_a_group_of_one_is_refused(self):
        observation = self.make()
        thin = dataclasses.replace(
            observation.baseline_metric, sample_count=1, source_run_ids=("b1",)
        )
        findings = validate_mass_loading_observation(self.make(baseline_metric=thin))
        assert [f.code.value for f in findings] == ["NSF-301"]

    def test_a_unit_mismatch_between_groups_is_refused(self):
        observation = self.make()
        other = dataclasses.replace(observation.loaded_metric, unit="ratio")
        findings = validate_mass_loading_observation(self.make(loaded_metric=other))
        assert [f.code.value for f in findings] == ["NSF-302"]

    def test_no_response_size_is_judged(self):
        # A challenge that produced a vanishing delta is valid evidence.
        tiny = self.make(absolute_delta=1e-9, relative_delta_pct=1e-7)
        assert validate_mass_loading_observation(tiny) == []
