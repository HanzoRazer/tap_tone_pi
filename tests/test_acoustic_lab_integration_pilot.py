# INSTRUMENT CLASS: MEASUREMENT
"""Guard tests for the acoustic lab integration pilot (Phase 1).

Verifies that the synthetic Flat Plate Resonance Pilot fixture renders through the
*existing* cohort execution-plan renderer, produces all nine renderer sections,
and introduces no advisory / build-prescription language. These tests do not
exercise renderer internals (covered by tests/test_execution_plan.py); they guard
the pilot fixture and its measurement-boundary compliance.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PILOT_PATH = _REPO_ROOT / "examples" / "acoustic_lab" / "flat_plate_resonance_pilot_v1.py"


def _load_pilot_module():
    spec = importlib.util.spec_from_file_location("flat_plate_resonance_pilot_v1", _PILOT_PATH)
    assert spec and spec.loader, f"could not load pilot module from {_PILOT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rendered_markdown() -> str:
    pilot = _load_pilot_module()
    return pilot.render_pilot_markdown()


def test_pilot_fixture_renders_successfully(rendered_markdown: str) -> None:
    assert isinstance(rendered_markdown, str)
    assert rendered_markdown.strip(), "rendered plan is empty"
    assert "# Cohort Execution Plan: Flat Plate Resonance Pilot V1" in rendered_markdown
    assert "**INSTRUMENT CLASS: MEASUREMENT**" in rendered_markdown


def test_rendered_plan_contains_all_nine_sections(rendered_markdown: str) -> None:
    # The renderer emits sections numbered "## 1." through "## 9.".
    for n in range(1, 10):
        assert f"## {n}." in rendered_markdown, f"missing section {n}"


def test_rendered_plan_declares_flat_plate_response_variables(rendered_markdown: str) -> None:
    # Flat-plate variables only; A0 (air-cavity mode) must NOT appear.
    assert "T1 frequency" in rendered_markdown
    assert "decay time" in rendered_markdown
    assert "| Q |" in rendered_markdown
    assert "A0" not in rendered_markdown, "A0 is not a flat-plate variable and must be omitted"


def test_rendered_plan_has_no_advisory_or_prescriptive_language(rendered_markdown: str) -> None:
    haystack = rendered_markdown.lower()
    forbidden = [
        "recommend",
        "you should",
        "advis",          # advise / advisory
        "prescrib",       # prescribe / prescription
        "optimal",
        "high quality",
        "good tone",
        "proves quality",
        "thin this",
        "thin the brace",
        "is acoustically correct",
    ]
    hits = [term for term in forbidden if term in haystack]
    assert not hits, f"advisory/prescriptive language leaked into rendered plan: {hits}"
