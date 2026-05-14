"""Regression guard for OperatorLoop directive extraction.

This test intentionally covers BOTH dict-based and dataclass-based directive
shapes, including mixed nested focus types, to prevent breakage when
policy._build_directive migrates output representations.
"""

from __future__ import annotations

from dataclasses import dataclass

from tap_tone_pi.workflow.operator_loop import OperatorLoop


@dataclass(frozen=True)
class FocusDC:
    target_type: str
    target_id: str
    highlight_region: object | None = None


@dataclass(frozen=True)
class DirectiveDC:
    action: str
    summary: str
    confidence: float
    focus: FocusDC | None = None


def test_directive_accessor_works_for_dict_and_dataclass():
    # Dict-style directive (current decide() output)
    directive_dict = {
        "action": "REVIEW",
        "summary": "Potential finding detected near 432 Hz",
        "confidence": 0.87,
        "focus": {
            "target_type": "spectrum",
            "target_id": "peak@432Hz",
            "highlight_region": None,
        },
    }

    # Dataclass-style directive (future-proofing)
    directive_dc = DirectiveDC(
        action="REVIEW",
        summary="Potential finding detected near 432 Hz",
        confidence=0.87,
        focus=FocusDC(
            target_type="spectrum", target_id="peak@432Hz", highlight_region=None
        ),
    )

    for d in (directive_dict, directive_dc):
        assert OperatorLoop._directive_field(d, "action") == "REVIEW"
        assert (
            OperatorLoop._directive_field(d, "summary")
            == "Potential finding detected near 432 Hz"
        )
        assert abs(float(OperatorLoop._directive_field(d, "confidence")) - 0.87) < 1e-9

        focus = OperatorLoop._directive_field(d, "focus")
        assert focus is not None
        assert OperatorLoop._directive_field(focus, "target_type") == "spectrum"
        assert OperatorLoop._directive_field(focus, "target_id") == "peak@432Hz"
        assert OperatorLoop._directive_field(focus, "highlight_region") is None


def test_directive_accessor_handles_mixed_focus_types():
    """
    Mixed-mode regression:
      - directive dataclass + focus dict
      - directive dict + focus dataclass

    These cases commonly occur during partial migrations and must remain safe.
    """

    # Dataclass directive with dict focus
    directive_dc_focus_dict = DirectiveDC(
        action="REVIEW",
        summary="Mixed focus (dc directive, dict focus)",
        confidence=0.55,
        focus={
            "target_type": "spectrum",
            "target_id": "peak@221Hz",
            "highlight_region": None,
        },
    )

    focus = OperatorLoop._directive_field(directive_dc_focus_dict, "focus")
    assert OperatorLoop._directive_field(focus, "target_type") == "spectrum"
    assert OperatorLoop._directive_field(focus, "target_id") == "peak@221Hz"

    # Dict directive with dataclass focus
    directive_dict_focus_dc = {
        "action": "REVIEW",
        "summary": "Mixed focus (dict directive, dc focus)",
        "confidence": 0.42,
        "focus": FocusDC(
            target_type="spectrum",
            target_id="peak@109Hz",
            highlight_region=None,
        ),
    }

    focus = OperatorLoop._directive_field(directive_dict_focus_dc, "focus")
    assert OperatorLoop._directive_field(focus, "target_type") == "spectrum"
    assert OperatorLoop._directive_field(focus, "target_id") == "peak@109Hz"


def test_directive_accessor_returns_default_for_missing_keys():
    assert OperatorLoop._directive_field({"a": 1}, "missing", "x") == "x"
    assert OperatorLoop._directive_field(None, "anything", "x") == "x"
