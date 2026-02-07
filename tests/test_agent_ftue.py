"""Tests for FTUE (First-Time User Experience) logic."""
import pytest
from tap_tone_pi.agent import (
    UserStage,
    FTUE_HINTS,
    get_ftue_hint,
    infer_user_stage,
    max_rules_to_show,
    max_actions_to_show,
    show_why_it_matters,
    show_advanced_note,
    show_metrics,
)


class TestFTUEHints:
    """Tests for FTUE learning hints."""

    def test_first_run_has_hints(self):
        hints = FTUE_HINTS[UserStage.FIRST_RUN]
        assert len(hints) >= 2
        # Should mention setup
        assert any("setup" in h.lower() for h in hints)

    def test_novice_has_hints(self):
        hints = FTUE_HINTS[UserStage.NOVICE]
        assert len(hints) >= 1

    def test_regular_has_no_hints(self):
        hints = FTUE_HINTS[UserStage.REGULAR]
        assert len(hints) == 0

    def test_expert_has_no_hints(self):
        hints = FTUE_HINTS[UserStage.EXPERT]
        assert len(hints) == 0


class TestGetFTUEHint:
    """Tests for hint selection."""

    def test_first_run_gets_hint(self):
        hint = get_ftue_hint(UserStage.FIRST_RUN, attempt_num=1)
        assert hint is not None
        assert "Tip:" in hint

    def test_hints_rotate_by_attempt(self):
        hint1 = get_ftue_hint(UserStage.FIRST_RUN, attempt_num=1)
        hint2 = get_ftue_hint(UserStage.FIRST_RUN, attempt_num=2)
        hint4 = get_ftue_hint(UserStage.FIRST_RUN, attempt_num=4)
        
        # Should cycle through hints
        assert hint1 != hint2
        # Attempt 4 should wrap around (3 hints → back to first)
        assert hint4 == hint1

    def test_regular_gets_no_hint(self):
        hint = get_ftue_hint(UserStage.REGULAR, attempt_num=1)
        assert hint is None

    def test_expert_gets_no_hint(self):
        hint = get_ftue_hint(UserStage.EXPERT, attempt_num=1)
        assert hint is None


class TestInferUserStage:
    """Tests for user stage inference."""

    def test_never_passed_is_first_run(self):
        stage = infer_user_stage(total_sessions=5, total_passes=0)
        assert stage == UserStage.FIRST_RUN

    def test_few_passes_is_novice(self):
        stage = infer_user_stage(total_sessions=3, total_passes=10)
        assert stage == UserStage.NOVICE

    def test_many_sessions_is_regular(self):
        stage = infer_user_stage(total_sessions=20, total_passes=100)
        assert stage == UserStage.REGULAR

    def test_explicit_override_wins(self):
        stage = infer_user_stage(
            total_sessions=0,
            total_passes=0,
            explicit_stage=UserStage.EXPERT,
        )
        assert stage == UserStage.EXPERT

    def test_boundary_conditions(self):
        # Exactly 5 sessions, 20 passes → still novice
        stage = infer_user_stage(total_sessions=5, total_passes=20)
        assert stage == UserStage.NOVICE
        
        # 6 sessions, 21 passes → regular
        stage = infer_user_stage(total_sessions=6, total_passes=21)
        assert stage == UserStage.REGULAR


class TestProgressiveDisclosure:
    """Tests for progressive disclosure rules."""

    def test_max_rules_first_run(self):
        assert max_rules_to_show(UserStage.FIRST_RUN) == 2

    def test_max_rules_novice(self):
        assert max_rules_to_show(UserStage.NOVICE) == 4

    def test_max_rules_regular(self):
        assert max_rules_to_show(UserStage.REGULAR) >= 10

    def test_max_rules_expert(self):
        assert max_rules_to_show(UserStage.EXPERT) >= 10

    def test_max_actions_first_run(self):
        assert max_actions_to_show(UserStage.FIRST_RUN) == 2

    def test_max_actions_novice(self):
        assert max_actions_to_show(UserStage.NOVICE) == 3

    def test_max_actions_regular(self):
        assert max_actions_to_show(UserStage.REGULAR) >= 5


class TestShowFlags:
    """Tests for detail visibility flags."""

    def test_show_why_it_matters_first_run_hard(self):
        assert show_why_it_matters(UserStage.FIRST_RUN, "HARD") is True

    def test_show_why_it_matters_first_run_soft(self):
        assert show_why_it_matters(UserStage.FIRST_RUN, "SOFT") is False

    def test_show_why_it_matters_novice(self):
        assert show_why_it_matters(UserStage.NOVICE, "HARD") is True
        assert show_why_it_matters(UserStage.NOVICE, "SOFT") is True

    def test_show_why_it_matters_expert(self):
        # Experts don't need handholding
        assert show_why_it_matters(UserStage.EXPERT, "HARD") is False
        assert show_why_it_matters(UserStage.EXPERT, "SOFT") is False

    def test_show_advanced_note(self):
        assert show_advanced_note(UserStage.FIRST_RUN) is False
        assert show_advanced_note(UserStage.NOVICE) is False
        assert show_advanced_note(UserStage.REGULAR) is False
        assert show_advanced_note(UserStage.EXPERT) is True

    def test_show_metrics(self):
        assert show_metrics(UserStage.FIRST_RUN) is False
        assert show_metrics(UserStage.REGULAR) is False
        assert show_metrics(UserStage.EXPERT) is True
