"""First-Time User Experience (FTUE) — stage inference and progressive disclosure.

Controls how much detail the agent shows based on user experience level.
"""

from __future__ import annotations

from .types import UserStage


# =============================================================================
# FTUE LEARNING HINTS (stage-specific tips)
# =============================================================================

FTUE_HINTS: dict[UserStage, list[str]] = {
    UserStage.FIRST_RUN: [
        "Tip: Run 'ttp setup' once to lock the right input device (USB indices change).",
        "Tip: Aim for a strong signal without clipping; near-clipping warnings are common at first.",
        "Tip: Consistent support and tap point matter more than tap strength.",
    ],
    UserStage.NOVICE: [
        "Tip: If the same warning repeats, adjust setup once rather than retrying many times.",
    ],
    UserStage.REGULAR: [],
    UserStage.EXPERT: [],
}


def get_ftue_hint(stage: UserStage, attempt_num: int = 1) -> str | None:
    """Select an appropriate learning hint for the user stage.

    Rotates through hints based on attempt number to avoid repetition.
    """
    hints = FTUE_HINTS.get(stage, [])
    if not hints:
        return None
    return hints[(attempt_num - 1) % len(hints)]


# =============================================================================
# PROGRESSIVE DISCLOSURE RULES
# =============================================================================


def max_rules_to_show(stage: UserStage) -> int:
    """How many rule explanations to show at once."""
    if stage == UserStage.FIRST_RUN:
        return 2
    elif stage == UserStage.NOVICE:
        return 4
    return 10  # Show all for regular/expert


def max_actions_to_show(stage: UserStage) -> int:
    """How many suggested actions to show."""
    if stage == UserStage.FIRST_RUN:
        return 2  # Primary action + Help
    elif stage == UserStage.NOVICE:
        return 3
    return 5  # Show all for regular/expert


def show_why_it_matters(stage: UserStage, severity: str) -> bool:
    """Whether to include 'why it matters' in rule explanation."""
    if stage == UserStage.EXPERT:
        return False  # Experts don't need handholding
    if stage == UserStage.FIRST_RUN:
        return severity == "HARD"  # Only for failures
    return True  # Novice/regular see it


def show_advanced_note(stage: UserStage) -> bool:
    """Whether to include advanced notes."""
    return stage == UserStage.EXPERT


def show_metrics(stage: UserStage) -> bool:
    """Whether to include raw metrics (rms, peak_level, thresholds)."""
    return stage == UserStage.EXPERT


# =============================================================================
# STAGE INFERENCE
# =============================================================================


def infer_user_stage(
    total_sessions: int = 0,
    total_passes: int = 0,
    explicit_stage: UserStage | None = None,
) -> UserStage:
    """Infer user stage from usage history.

    Args:
        total_sessions: Number of sessions the user has started
        total_passes: Number of PASS verdicts ever achieved
        explicit_stage: If set, overrides inference (e.g., --expert flag)

    Returns:
        UserStage for progressive disclosure
    """
    # Explicit override wins
    if explicit_stage is not None:
        return explicit_stage

    # Never had a PASS → first run experience
    if total_passes == 0:
        return UserStage.FIRST_RUN

    # Low usage → novice
    if total_sessions <= 5 or total_passes <= 20:
        return UserStage.NOVICE

    return UserStage.REGULAR
