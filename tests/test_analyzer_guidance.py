"""
tests/test_analyzer_guidance.py

Tests for AnalyzerGuidanceEngine (Claude-backed, with fallback).
All tests run without an API key — they verify the fallback path,
stage suppression, history, and threading behaviour.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Any, List

import pytest

from tap_tone_pi.agent.types import UserStage
from tap_tone_pi.agentic.contracts.analyzer_attention import (
    AttentionAction,
    AttentionDirectiveV1,
)
from analyzer.guidance.engine import AnalyzerGuidanceEngine


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    """Ensure tests run without API key to test fallback path."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


PACK = {"metadata": {"session": {"specimen_id": "SP_001", "calibration": {"status": "valid"}}}}
PEAKS = [{"freq_hz": 203.1, "magnitude": 0.85}, {"freq_hz": 378.4, "magnitude": 0.52}]
POOR_COH = {"mean": 0.52, "min": 0.31, "problem_frequencies": [220.0, 350.0]}
GOOD_COH  = {"mean": 0.95, "min": 0.88, "problem_frequencies": []}
PROPS = {"radiation_coefficient": 12.8, "density_kg_m3": 430.0, "confidence": 0.82}


def _engine(stage=UserStage.NOVICE):
    received = []
    engine = AnalyzerGuidanceEngine(stage=stage)
    engine.on_directive = received.append
    return engine, received


def _wait(received, n=1, timeout=2.0):
    """Wait for n directives to arrive from background thread."""
    deadline = time.time() + timeout
    while len(received) < n and time.time() < deadline:
        time.sleep(0.05)
    return received


class TestEngineEmits:

    def test_pack_loaded_emits_directive(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_pack_loaded(PACK)
        _wait(received)
        assert len(received) == 1
        assert isinstance(received[0], AttentionDirectiveV1)

    def test_directive_has_source_tool(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_pack_loaded(PACK)
        _wait(received)
        assert received[0].source_tool == "analyzer_guidance_claude"

    def test_peaks_emits_directive(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_peaks_found(PEAKS)
        _wait(received)
        assert len(received) == 1

    def test_empty_peaks_no_directive(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_peaks_found([])
        time.sleep(0.3)
        assert len(received) == 0

    def test_poor_coherence_emits_directive(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_coherence_analyzed(POOR_COH)
        _wait(received)
        assert len(received) == 1

    def test_good_coherence_no_directive(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_coherence_analyzed(GOOD_COH)
        time.sleep(0.3)
        assert len(received) == 0

    def test_wood_props_emits_directive(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_wood_properties_estimated(PROPS)
        _wait(received)
        assert len(received) == 1

    def test_empty_wood_props_no_directive(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_wood_properties_estimated({})
        time.sleep(0.3)
        assert len(received) == 0


class TestExpertSuppression:

    def test_expert_pack_suppressed(self):
        engine, received = _engine(UserStage.EXPERT)
        engine.on_pack_loaded(PACK)
        time.sleep(0.4)
        assert len(received) == 0

    def test_expert_peaks_suppressed(self):
        engine, received = _engine(UserStage.EXPERT)
        engine.on_peaks_found(PEAKS)
        time.sleep(0.4)
        assert len(received) == 0

    def test_expert_good_coherence_suppressed(self):
        engine, received = _engine(UserStage.EXPERT)
        engine.on_coherence_analyzed(GOOD_COH)
        time.sleep(0.3)
        assert len(received) == 0


class TestHistory:

    def test_history_accumulates(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_pack_loaded(PACK)
        engine.on_peaks_found(PEAKS)
        engine.on_coherence_analyzed(POOR_COH)
        _wait(received, n=3, timeout=3.0)
        assert len(engine.history) == 3

    def test_history_is_readonly_copy(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_pack_loaded(PACK)
        _wait(received)
        h = engine.history
        h.clear()
        assert len(engine.history) == 1

    def test_directive_ids_unique(self):
        engine, received = _engine(UserStage.NOVICE)
        engine.on_pack_loaded(PACK)
        engine.on_peaks_found(PEAKS)
        engine.on_wood_properties_estimated(PROPS)
        _wait(received, n=3, timeout=3.0)
        ids = [d.directive_id for d in engine.history]
        assert len(ids) == len(set(ids))


class TestStageAndCallback:

    def test_set_stage_changes_stage(self):
        engine, _ = _engine(UserStage.REGULAR)
        engine.set_stage(UserStage.EXPERT)
        assert engine.stage == UserStage.EXPERT

    def test_no_callback_does_not_crash(self):
        engine = AnalyzerGuidanceEngine(stage=UserStage.NOVICE)
        engine.on_pack_loaded(PACK)
        engine.on_peaks_found(PEAKS)
        time.sleep(0.4)  # should not raise

    def test_wolf_does_not_crash(self):
        engine, received = _engine(UserStage.NOVICE)
        try:
            engine.on_wolf_detected(wsi=0.72, beat_hz=8.3, freq_hz=247.0)
        except Exception as e:
            pytest.fail(f"on_wolf_detected raised: {e}")


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("PyQt6"),
    reason="PyQt6 not available"
)
class TestPanelSmoke:

    @pytest.fixture(scope="class")
    def app(self):
        import sys
        from PyQt6.QtWidgets import QApplication
        return QApplication.instance() or QApplication(sys.argv)

    def test_panel_constructs(self, app):
        from analyzer.guidance.panel import GuidancePanelWidget
        panel = GuidancePanelWidget()
        assert panel is not None

    def test_panel_shows_directive(self, app):
        from analyzer.guidance.panel import GuidancePanelWidget
        engine, received = _engine(UserStage.NOVICE)
        engine.on_pack_loaded(PACK)
        _wait(received)
        panel = GuidancePanelWidget()
        panel.show_directive(received[0])
