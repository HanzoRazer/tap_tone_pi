"""Message specification — rule explanations, verdict templates, FTUE hints.

This is the canonical mapping from rule IDs to operator-facing messages.
The agent uses these tables; it never invents new explanations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import ActionId

from .types import ActionId, SuggestedAction


@dataclass
class RuleSpec:
    """Specification for a single quality rule."""

    rule_id: str
    severity: str  # "HARD" or "SOFT"
    operator_explanation: str
    why_it_matters: str
    first_fix: str
    fallback_fix: str
    advanced_note: str
    agent_actions: list[SuggestedAction] = field(default_factory=list)


# =============================================================================
# HARD RULES (Q001–Q005) — trigger FAIL verdict
# =============================================================================

RULE_Q001 = RuleSpec(
    rule_id="Q001",
    severity="HARD",
    operator_explanation="The signal clipped (hit the recorder's maximum). This capture is distorted.",
    why_it_matters="Clipping changes the spectrum and can produce false peaks.",
    first_fix="Reduce input gain or move the mic farther away.",
    fallback_fix="Use a shorter capture / softer tap if gain can't be changed.",
    advanced_note="If clipping persists at low gain, check OS mic boost / auto gain control.",
    agent_actions=[
        SuggestedAction(
            ActionId.ADJUST_GAIN_DOWN, "Lower gain and retry", "Prevents distortion"
        ),
        SuggestedAction(ActionId.RETRY, "Retry capture", "Need an unclipped waveform"),
        SuggestedAction(ActionId.ABORT, "Abort", "Cannot proceed with clipped data"),
    ],
)

RULE_Q002 = RuleSpec(
    rule_id="Q002",
    severity="HARD",
    operator_explanation="No usable signal was detected.",
    why_it_matters="Without sufficient signal, peaks and confidence are meaningless.",
    first_fix="Check the mic is the selected input device and tap closer / harder.",
    fallback_fix="Increase input gain and confirm the level meter moves.",
    advanced_note="On Pi, wrong default device is common after USB reconnect.",
    agent_actions=[
        SuggestedAction(
            ActionId.CHECK_DEVICE,
            "Check input device",
            "Wrong input looks like silence",
        ),
        SuggestedAction(
            ActionId.RETRY, "Retry with a harder tap", "Need a measurable impulse"
        ),
        SuggestedAction(
            ActionId.RUN_SETUP, "Run setup wizard", "Persist the right device"
        ),
    ],
)

RULE_Q003 = RuleSpec(
    rule_id="Q003",
    severity="HARD",
    operator_explanation="The analyzer couldn't identify a clear resonance in the capture.",
    why_it_matters="No clear peak means the measurement can't be trusted.",
    first_fix="Improve coupling: tap on a solid support point and reduce room noise.",
    fallback_fix="Increase capture duration slightly (e.g., 2.5s → 4s).",
    advanced_note="If highpass/peak range excludes the true mode, adjust analysis config later—do not change during baseline.",
    agent_actions=[
        SuggestedAction(
            ActionId.RETRY,
            "Retry with better coupling",
            "Cleaner impulse yields clear peaks",
        ),
        SuggestedAction(
            ActionId.ADJUST_DURATION_UP,
            "Increase duration and retry",
            "Gives more usable decay",
        ),
        SuggestedAction(
            ActionId.HELP, "Show tapping tips", "Reduce operator variability"
        ),
    ],
)

RULE_Q004 = RuleSpec(
    rule_id="Q004",
    severity="HARD",
    operator_explanation="The peak detection confidence is too low for a reliable reading.",
    why_it_matters="Low confidence often means noise, clipping, or weak coupling.",
    first_fix="Retry after addressing signal level and coupling.",
    fallback_fix="Try a second capture to confirm repeatability.",
    advanced_note="If confidence is consistently low across attempts, check environment noise and mic placement.",
    agent_actions=[
        SuggestedAction(ActionId.RETRY, "Retry capture", "Need higher confidence"),
        SuggestedAction(
            ActionId.CHECK_ENVIRONMENT,
            "Reduce noise and retry",
            "Noise lowers confidence",
        ),
        SuggestedAction(ActionId.ABORT, "Abort", "Cannot proceed under threshold"),
    ],
)

RULE_Q005 = RuleSpec(
    rule_id="Q005",
    severity="HARD",
    operator_explanation="The capture sample rate is not supported by policy.",
    why_it_matters="Non-standard rates can break comparability across sessions.",
    first_fix="Switch to 48k or 44.1k and retry.",
    fallback_fix="Run setup wizard to save a compatible device/rate combination.",
    advanced_note="If the device rejects rates, fall back to its supported default.",
    agent_actions=[
        SuggestedAction(
            ActionId.SET_SAMPLERATE_STANDARD,
            "Use 48k and retry",
            "Policy-approved rate",
        ),
        SuggestedAction(ActionId.RUN_SETUP, "Run setup wizard", "Persist correct rate"),
        SuggestedAction(
            ActionId.ABORT, "Abort", "Cannot proceed with non-standard rate"
        ),
    ],
)


# =============================================================================
# SOFT RULES (Q010–Q013) — trigger WARN verdict
# =============================================================================

RULE_Q010 = RuleSpec(
    rule_id="Q010",
    severity="SOFT",
    operator_explanation="Signal is quiet. This may still be usable, but repeatability can suffer.",
    why_it_matters="Quiet signals are more sensitive to noise and coupling variation.",
    first_fix="Increase gain slightly or tap closer.",
    fallback_fix="Retake once to see if confidence improves.",
    advanced_note="If confidence remains high, accepting is usually fine.",
    agent_actions=[
        SuggestedAction(
            ActionId.ACCEPT, "Accept with warning", "Measurement may still be valid"
        ),
        SuggestedAction(
            ActionId.RETRY, "Retry with slightly higher level", "Improve repeatability"
        ),
    ],
)

RULE_Q011 = RuleSpec(
    rule_id="Q011",
    severity="SOFT",
    operator_explanation="Signal is near clipping. This capture is usable, but margin is small.",
    why_it_matters="A slightly harder tap could clip and invalidate the next capture.",
    first_fix="Reduce gain slightly, then retake for safety margin.",
    fallback_fix="Accept if consistent and confidence is strong.",
    advanced_note="Aim for headroom; avoid any automatic mic boost features.",
    agent_actions=[
        SuggestedAction(
            ActionId.RETRY,
            "Retry with slightly lower gain",
            "Avoid clipping next attempt",
        ),
        SuggestedAction(
            ActionId.ACCEPT, "Accept with warning", "Current capture is not clipped"
        ),
    ],
)

RULE_Q012 = RuleSpec(
    rule_id="Q012",
    severity="SOFT",
    operator_explanation="Confidence is marginal. The reading may be correct but less stable.",
    why_it_matters="Low stability increases the chance of drift between attempts.",
    first_fix="Retry once to see if confidence improves.",
    fallback_fix="Accept if dominant peak repeats across attempts.",
    advanced_note="If repeated, treat as environment/coupling problem rather than algorithm error.",
    agent_actions=[
        SuggestedAction(ActionId.RETRY, "Retry once", "Try for higher confidence"),
        SuggestedAction(
            ActionId.ACCEPT, "Accept with warning", "If repeatable, usable"
        ),
    ],
)

RULE_Q013 = RuleSpec(
    rule_id="Q013",
    severity="SOFT",
    operator_explanation="Only a few peaks were detected.",
    why_it_matters="Can indicate weak coupling or insufficient excitation of harmonics/modes.",
    first_fix="Tap with firmer coupling and ensure consistent support.",
    fallback_fix="Accept if dominant frequency is stable across attempts.",
    advanced_note="This is not necessarily bad; some structures naturally show fewer peaks.",
    agent_actions=[
        SuggestedAction(
            ActionId.RETRY,
            "Retry with improved coupling",
            "May reveal clearer peak structure",
        ),
        SuggestedAction(
            ActionId.ACCEPT, "Accept with warning", "Dominant peak may still be valid"
        ),
    ],
)


# =============================================================================
# RULE REGISTRY
# =============================================================================

RULE_SPECS: dict[str, RuleSpec] = {
    "Q001": RULE_Q001,
    "Q002": RULE_Q002,
    "Q003": RULE_Q003,
    "Q004": RULE_Q004,
    "Q005": RULE_Q005,
    "Q010": RULE_Q010,
    "Q011": RULE_Q011,
    "Q012": RULE_Q012,
    "Q013": RULE_Q013,
}


def get_rule_spec(rule_id: str) -> RuleSpec | None:
    """Look up rule specification by ID."""
    return RULE_SPECS.get(rule_id)


# =============================================================================
# VERDICT TEMPLATES
# =============================================================================


@dataclass
class VerdictTemplate:
    """Template for verdict-level messaging."""

    title: str
    summary: str
    default_actions: list[SuggestedAction] = field(default_factory=list)


VERDICT_PASS = VerdictTemplate(
    title="Measurement accepted",
    summary="Quality checks passed. You can proceed to the next point.",
    default_actions=[
        SuggestedAction(ActionId.ADVANCE, "Next point", "Proceed in workflow"),
    ],
)

VERDICT_WARN = VerdictTemplate(
    title="Measurement usable with warnings",
    summary="Capture is usable, but conditions may reduce repeatability.",
    default_actions=[
        SuggestedAction(ActionId.ACCEPT, "Accept", "Proceed with warning noted"),
        SuggestedAction(ActionId.RETRY, "Retry", "Try to improve quality"),
    ],
)

VERDICT_FAIL = VerdictTemplate(
    title="Measurement failed quality gate",
    summary="Capture is not acceptable under policy.",
    default_actions=[
        SuggestedAction(ActionId.RETRY, "Retry", "Correct conditions and retake"),
        SuggestedAction(ActionId.ABORT, "Abort", "Stop and troubleshoot"),
        SuggestedAction(
            ActionId.OVERRIDE,
            "Override (requires reason)",
            "Log exception explicitly",
            requires_input=True,
        ),
    ],
)

VERDICT_TEMPLATES: dict[str, VerdictTemplate] = {
    "pass": VERDICT_PASS,
    "warn": VERDICT_WARN,
    "fail": VERDICT_FAIL,
}


def get_verdict_template(verdict: str) -> VerdictTemplate:
    """Look up verdict template by name."""
    return VERDICT_TEMPLATES.get(verdict.lower(), VERDICT_PASS)
