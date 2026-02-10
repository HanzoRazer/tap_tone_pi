"""Tests for directive history formatting helper (PR #14 Seg 2)."""
from tap_tone_pi.agentic.spine.directive_history import DirectiveEventRow
from tap_tone_pi.gui.directive_history_view import format_directive_history


def test_format_with_moment_and_rows():
    rows = [
        DirectiveEventRow(
            timestamp="t1",
            event_type="attention_requested",
            directive_id="d1",
            component="spine",
        ),
        DirectiveEventRow(
            timestamp="t2",
            event_type="attention_acknowledged",
            directive_id="d1",
            component="cli",
        ),
    ]
    lines = format_directive_history(rows, moment_id="TRUST_EROSION", limit=10)
    assert lines[0] == "Moment: TRUST_EROSION"
    assert lines[1] == "Recent directive events:"
    joined = "\n".join(lines)
    assert "attention_requested" in joined
    assert "directive_id=d1" in joined
    assert "component=spine" in joined


def test_format_no_rows_but_moment_present():
    lines = format_directive_history([], moment_id="FINDING")
    assert lines == ("Moment: FINDING",)


def test_format_missing_fields_render_as_dashes():
    rows = [
        DirectiveEventRow(
            timestamp="",
            event_type="attention_dismissed",
            directive_id=None,
            component=None,
        ),
    ]
    lines = format_directive_history(rows, moment_id=None, limit=10)
    joined = "\n".join(lines)
    assert "directive_id=-" in joined
    assert "component=-" in joined


def test_format_empty_inputs():
    """No rows, no moment → empty tuple."""
    lines = format_directive_history([], moment_id=None)
    assert lines == ()


def test_format_respects_limit():
    rows = [
        DirectiveEventRow(timestamp=f"t{i}", event_type="attention_requested")
        for i in range(20)
    ]
    lines = format_directive_history(rows, limit=3)
    # 1 header ("Recent directive events:") + 3 event lines
    assert len(lines) == 4
