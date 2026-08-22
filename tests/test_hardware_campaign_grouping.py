"""Fixed-point and detach/reattach grouping (DO-103 E2 and E3).

E2 asks how much a point repeats when nothing is disturbed. E3 breaks the
contact deliberately and asks what that costs. They are the same runs, grouped
differently, and the whole value of E3 is that the two numbers stay apart: a
within-attachment spread and a between-attachment spread averaged together
would hide exactly the term the experiment exists to expose.

These tests run on deterministic fixture evidence, before any rig exists.
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
from tap_tone_pi.grant_readiness.errors import RepeatabilityStatisticsError
from tap_tone_pi.grant_readiness.hardware_campaign import (
    ATTACHMENT_GROUP_KIND,
    group_runs_by_attachment,
    summarize_attachment_variation,
)
from tap_tone_pi.grant_readiness.statistics import (
    summarize_group_spread,
    summarize_runs,
)

UTC_NOW = "2026-08-22T12:00:00+00:00"
QUANTITY = "acoustic_transfer_magnitude"
UNIT = "Pa/N"


def make_run(
    run_id: str,
    value: float | None,
    *,
    attachment: str | None = None,
    kind: ExperimentKind = ExperimentKind.DETACH_REATTACH,
    valid: bool = True,
    unit: str = UNIT,
    with_condition: bool = True,
) -> PreliminaryExperimentRunV1:
    features = ()
    if value is not None:
        features = (ObservedFeatureV1(QUANTITY, unit, value),)
    condition = (
        CampaignConditionV1(kind, contact_configuration_id=attachment)
        if with_condition
        else None
    )
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="e3",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=valid,
        rejection_reason=None if valid else RejectionReason.CLIPPING,
        source_artifact_ids=(f"fixtures/{run_id}.json",),
        observed_features=features,
        campaign_condition=condition,
    )


class TestGroupingByAttachment:
    def test_runs_group_by_the_attachment_they_record(self):
        runs = [
            make_run("r1", 1.0, attachment="att-1"),
            make_run("r2", 1.1, attachment="att-1"),
            make_run("r3", 1.3, attachment="att-2"),
        ]
        grouped = group_runs_by_attachment(runs)
        assert {
            key: [run.run_id for run in value] for key, value in grouped.items()
        } == {
            "att-1": ["r1", "r2"],
            "att-2": ["r3"],
        }

    def test_groups_keep_the_order_they_were_executed_in(self):
        runs = [
            make_run("r1", 1.0, attachment="att-2"),
            make_run("r2", 1.1, attachment="att-1"),
        ]
        assert list(group_runs_by_attachment(runs)) == ["att-2", "att-1"]

    def test_a_run_without_an_attachment_is_left_out_not_guessed(self):
        # Placing it in an arbitrary group would silently merge two attachments.
        runs = [make_run("r1", 1.0, attachment="att-1"), make_run("r2", 1.1)]
        grouped = group_runs_by_attachment(runs)
        assert [run.run_id for run in grouped["att-1"]] == ["r1"]
        assert len(grouped) == 1

    def test_rejected_runs_do_not_enter_a_group(self):
        runs = [
            make_run("r1", 1.0, attachment="att-1"),
            make_run("r2", None, attachment="att-1", valid=False),
        ]
        assert [run.run_id for run in group_runs_by_attachment(runs)["att-1"]] == ["r1"]

    def test_a_do102_run_without_a_campaign_condition_is_ignored(self):
        runs = [make_run("r1", 1.0, with_condition=False)]
        assert group_runs_by_attachment(runs) == {}


class TestWithinAndBetween:
    def make_two_attachments(self):
        return [
            make_run("a1", 1.00, attachment="att-1"),
            make_run("a2", 1.02, attachment="att-1"),
            make_run("b1", 1.30, attachment="att-2"),
            make_run("b2", 1.34, attachment="att-2"),
        ]

    def test_within_attachment_metrics_are_per_attachment(self):
        variation = summarize_attachment_variation(
            self.make_two_attachments(), quantity=QUANTITY, unit=UNIT
        )
        assert len(variation.within_attachment_metrics) == 2
        assert {m.sample_count for m in variation.within_attachment_metrics} == {2}

    def test_each_within_metric_names_the_runs_it_came_from(self):
        variation = summarize_attachment_variation(
            self.make_two_attachments(), quantity=QUANTITY, unit=UNIT
        )
        cited = {
            run_id
            for metric in variation.within_attachment_metrics
            for run_id in metric.source_run_ids
        }
        assert cited == {"a1", "a2", "b1", "b2"}

    def test_between_attachment_spread_is_over_attachment_means(self):
        variation = summarize_attachment_variation(
            self.make_two_attachments(), quantity=QUANTITY, unit=UNIT
        )
        spread = variation.between_attachment_spread
        assert spread.group_kind == ATTACHMENT_GROUP_KIND
        assert spread.group_ids == ("att-1", "att-2")
        assert spread.group_values == pytest.approx((1.01, 1.32))

    def test_the_two_spreads_are_not_combined(self):
        # The between-attachment CV here is far larger than either within-
        # attachment CV. Averaging them would erase the finding.
        variation = summarize_attachment_variation(
            self.make_two_attachments(), quantity=QUANTITY, unit=UNIT
        )
        within = [
            m.coefficient_of_variation_pct for m in variation.within_attachment_metrics
        ]
        between = variation.between_attachment_spread.coefficient_of_variation_pct
        assert between > max(within)

    def test_an_attachment_seen_once_contributes_a_mean_and_no_metric(self):
        runs = self.make_two_attachments() + [make_run("c1", 1.5, attachment="att-3")]
        variation = summarize_attachment_variation(runs, quantity=QUANTITY, unit=UNIT)
        assert variation.unsummarized_attachment_ids == ("att-3",)
        assert len(variation.within_attachment_metrics) == 2
        assert variation.between_attachment_spread.group_count == 3

    def test_one_attachment_yields_no_between_spread(self):
        runs = [
            make_run("a1", 1.0, attachment="att-1"),
            make_run("a2", 1.1, attachment="att-1"),
        ]
        variation = summarize_attachment_variation(runs, quantity=QUANTITY, unit=UNIT)
        assert variation.between_attachment_spread is None
        assert variation.attachment_count == 1

    def test_no_attachment_at_all_is_reportable_not_an_error(self):
        runs = [make_run("r1", 1.0), make_run("r2", 1.1)]
        assert (
            summarize_attachment_variation(runs, quantity=QUANTITY, unit=UNIT) is None
        )

    def test_rejected_runs_are_excluded_from_every_statistic(self):
        runs = self.make_two_attachments() + [
            make_run("a3", None, attachment="att-1", valid=False)
        ]
        variation = summarize_attachment_variation(runs, quantity=QUANTITY, unit=UNIT)
        cited = {
            run_id
            for metric in variation.within_attachment_metrics
            for run_id in metric.source_run_ids
        }
        assert "a3" not in cited

    def test_a_unit_mismatch_is_refused_rather_than_averaged(self):
        runs = self.make_two_attachments() + [
            make_run("d1", 1.4, attachment="att-4", unit="ratio"),
            make_run("d2", 1.5, attachment="att-4", unit="ratio"),
        ]
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_attachment_variation(runs, quantity=QUANTITY, unit=UNIT)
        assert excinfo.value.code is (
            GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS
        )

    def test_the_variation_carries_no_acceptance_field(self):
        variation = summarize_attachment_variation(
            self.make_two_attachments(), quantity=QUANTITY, unit=UNIT
        )
        payload = variation.to_dict()
        assert not {"passed", "is_acceptable", "verdict"} & set(payload)


class TestFixedPointUsesTheExistingSummary:
    def test_a_fixed_point_experiment_needs_no_new_machinery(self):
        # E2 is the shape DO-102 already summarizes: one point, repeated. The
        # campaign adds grouping, not a second statistics path.
        runs = [
            make_run("f1", 1.00, attachment="att-1", kind=ExperimentKind.FIXED_POINT),
            make_run("f2", 1.02, attachment="att-1", kind=ExperimentKind.FIXED_POINT),
            make_run("f3", 0.99, attachment="att-1", kind=ExperimentKind.FIXED_POINT),
        ]
        metric = summarize_runs(runs, quantity=QUANTITY, unit=UNIT)
        assert metric.sample_count == 3
        assert metric.source_run_ids == ("f1", "f2", "f3")

    def test_one_valid_run_yields_no_statistic(self):
        runs = [make_run("f1", 1.0, kind=ExperimentKind.FIXED_POINT)]
        assert summarize_runs(runs, quantity=QUANTITY, unit=UNIT) is None


class TestGroupSpread:
    def test_it_refuses_fewer_than_two_groups(self):
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_group_spread(
                [1.0],
                group_kind="attachment",
                group_ids=("att-1",),
                quantity=QUANTITY,
                unit=UNIT,
            )
        assert excinfo.value.code is (
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS
        )

    def test_every_value_must_name_its_group(self):
        with pytest.raises(RepeatabilityStatisticsError):
            summarize_group_spread(
                [1.0, 2.0],
                group_kind="attachment",
                group_ids=("att-1",),
                quantity=QUANTITY,
                unit=UNIT,
            )

    def test_a_repeated_group_is_refused(self):
        with pytest.raises(RepeatabilityStatisticsError):
            summarize_group_spread(
                [1.0, 2.0],
                group_kind="attachment",
                group_ids=("att-1", "att-1"),
                quantity=QUANTITY,
                unit=UNIT,
            )

    def test_a_blank_unit_is_refused(self):
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_group_spread(
                [1.0, 2.0],
                group_kind="attachment",
                group_ids=("att-1", "att-2"),
                quantity=QUANTITY,
                unit="  ",
            )
        assert excinfo.value.code is (
            GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS
        )

    def test_a_zero_mean_is_refused_rather_than_reported_as_perfect(self):
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_group_spread(
                [1.0, -1.0],
                group_kind="attachment",
                group_ids=("att-1", "att-2"),
                quantity=QUANTITY,
                unit=UNIT,
            )
        assert excinfo.value.code is (
            GrantReadinessErrorCode.UNDEFINED_COEFFICIENT_OF_VARIATION
        )

    def test_a_non_finite_value_is_refused(self):
        with pytest.raises(RepeatabilityStatisticsError) as excinfo:
            summarize_group_spread(
                [1.0, float("inf")],
                group_kind="attachment",
                group_ids=("att-1", "att-2"),
                quantity=QUANTITY,
                unit=UNIT,
            )
        assert excinfo.value.code is GrantReadinessErrorCode.NON_FINITE_STATISTIC

    def test_it_reports_the_same_arithmetic_as_the_run_level_summary(self):
        # Both delegate to the DO-085 helper; only what a sample *is* differs.
        values = [1.0, 1.2, 0.9]
        spread = summarize_group_spread(
            values,
            group_kind="attachment",
            group_ids=("a", "b", "c"),
            quantity=QUANTITY,
            unit=UNIT,
        )
        runs = [
            make_run("r1", 1.0, attachment="att-1"),
            make_run("r2", 1.2, attachment="att-1"),
            make_run("r3", 0.9, attachment="att-1"),
        ]
        metric = summarize_runs(runs, quantity=QUANTITY, unit=UNIT)
        assert spread.mean == pytest.approx(metric.mean)
        assert spread.standard_deviation == pytest.approx(metric.standard_deviation)
        assert spread.range_value == pytest.approx(metric.range_value)
