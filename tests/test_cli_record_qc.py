"""Tests for cmd_record quality gate integration.

Verifies that cmd_record emits quality_check.json alongside other artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from tap_tone_pi.core.analysis import AnalysisResult, Peak
from tap_tone_pi.core.quality_policy import Verdict

# Import the actual module (not the function shadowed by __init__.py)
from tap_tone_pi.cli.main import cmd_record


# =============================================================================
# Fixtures
# =============================================================================

@dataclass
class FakeCaptureResult:
    """Stub for capture result."""
    audio: np.ndarray
    sample_rate: int


@dataclass
class FakePersistedCapture:
    """Stub for persist_capture return value."""
    capture_dir: Path


def _make_analysis(
    *,
    dominant_hz: float | None = 440.0,
    clipped: bool = False,
    rms: float = 0.05,
    confidence: float = 0.8,
) -> AnalysisResult:
    """Create a fake AnalysisResult for testing."""
    return AnalysisResult(
        dominant_hz=dominant_hz,
        peaks=[
            Peak(freq_hz=440.0, magnitude=1.0),
            Peak(freq_hz=880.0, magnitude=0.5),
            Peak(freq_hz=1320.0, magnitude=0.25),
        ],
        clipped=clipped,
        rms=rms,
        confidence=confidence,
        spectrum_freq_hz=np.array([100.0, 200.0, 300.0]),
        spectrum_mag=np.array([0.1, 0.2, 0.3]),
    )


def _args(out_dir: str, label: str = "test_tap") -> argparse.Namespace:
    """Create args namespace for cmd_record."""
    return argparse.Namespace(
        device=0,
        sample_rate=48000,
        channels=1,
        seconds=1.0,
        out=out_dir,
        label=label,
    )


# =============================================================================
# Tests
# =============================================================================

class TestCmdRecordQualityCheck:
    """Test that cmd_record emits quality_check.json."""

    def test_emits_quality_check_json(self, monkeypatch, tmp_path):
        """cmd_record writes quality_check.json into capture directory."""
        capture_dir = tmp_path / "captures" / "capture_20260101T000000Z"
        capture_dir.mkdir(parents=True)

        # Stub record_audio
        fake_audio = np.zeros(48000, dtype=np.float32)
        fake_capture = FakeCaptureResult(audio=fake_audio, sample_rate=48000)
        monkeypatch.setattr(
            "tap_tone_pi.capture.record_audio",
            lambda **kw: fake_capture,
        )

        # Stub analyze_tap
        fake_analysis = _make_analysis()
        monkeypatch.setattr(
            "tap_tone_pi.core.analysis.analyze_tap",
            lambda *a, **kw: fake_analysis,
        )

        # Stub persist_capture
        fake_persisted = FakePersistedCapture(capture_dir=capture_dir)
        monkeypatch.setattr(
            "tap_tone_pi.io.storage.persist_capture",
            lambda **kw: fake_persisted,
        )

        # Stub get_saved_device
        monkeypatch.setattr(
            "tap_tone_pi.core.user_config.get_saved_device",
            lambda: None,
        )

        # Run cmd_record
        rc = cmd_record(_args(str(tmp_path / "out")))

        assert rc == 0

        # Verify quality_check.json exists
        qc_path = capture_dir / "quality_check.json"
        assert qc_path.exists(), "quality_check.json should be written"

        # Verify structure
        qc_data = json.loads(qc_path.read_text())
        assert "verdict" in qc_data
        assert "triggered_rules" in qc_data
        assert "policy_version" in qc_data

    def test_quality_check_contains_pass_verdict(self, monkeypatch, tmp_path):
        """Good measurement produces PASS verdict in quality_check.json."""
        capture_dir = tmp_path / "captures" / "capture_20260101T000000Z"
        capture_dir.mkdir(parents=True)

        fake_audio = np.zeros(48000, dtype=np.float32)
        fake_capture = FakeCaptureResult(audio=fake_audio, sample_rate=48000)
        monkeypatch.setattr("tap_tone_pi.capture.record_audio", lambda **kw: fake_capture)

        # Good measurement: high confidence, not clipped, has peaks
        fake_analysis = _make_analysis(confidence=0.9, clipped=False, rms=0.05)
        monkeypatch.setattr("tap_tone_pi.core.analysis.analyze_tap", lambda *a, **kw: fake_analysis)

        fake_persisted = FakePersistedCapture(capture_dir=capture_dir)
        monkeypatch.setattr("tap_tone_pi.io.storage.persist_capture", lambda **kw: fake_persisted)
        monkeypatch.setattr("tap_tone_pi.core.user_config.get_saved_device", lambda: None)

        cmd_record(_args(str(tmp_path / "out")))

        qc_data = json.loads((capture_dir / "quality_check.json").read_text())
        assert qc_data["verdict"] == "pass"
        assert qc_data["error_count"] == 0

    def test_quality_check_contains_fail_verdict_on_clipping(self, monkeypatch, tmp_path):
        """Clipped measurement produces FAIL verdict with Q001 in quality_check.json."""
        capture_dir = tmp_path / "captures" / "capture_20260101T000000Z"
        capture_dir.mkdir(parents=True)

        fake_audio = np.zeros(48000, dtype=np.float32)
        fake_capture = FakeCaptureResult(audio=fake_audio, sample_rate=48000)
        monkeypatch.setattr("tap_tone_pi.capture.record_audio", lambda **kw: fake_capture)

        # Clipped measurement
        fake_analysis = _make_analysis(clipped=True)
        monkeypatch.setattr("tap_tone_pi.core.analysis.analyze_tap", lambda *a, **kw: fake_analysis)

        fake_persisted = FakePersistedCapture(capture_dir=capture_dir)
        monkeypatch.setattr("tap_tone_pi.io.storage.persist_capture", lambda **kw: fake_persisted)
        monkeypatch.setattr("tap_tone_pi.core.user_config.get_saved_device", lambda: None)

        cmd_record(_args(str(tmp_path / "out")))

        qc_data = json.loads((capture_dir / "quality_check.json").read_text())
        assert qc_data["verdict"] == "fail"
        assert qc_data["error_count"] >= 1

        # Q001 should be in triggered rules
        rule_ids = [r["rule_id"] for r in qc_data["triggered_rules"]]
        assert "Q001" in rule_ids

    def test_quality_check_contains_warn_verdict_on_low_confidence(self, monkeypatch, tmp_path):
        """Marginal confidence produces WARN verdict with Q012 in quality_check.json."""
        capture_dir = tmp_path / "captures" / "capture_20260101T000000Z"
        capture_dir.mkdir(parents=True)

        fake_audio = np.zeros(48000, dtype=np.float32)
        fake_capture = FakeCaptureResult(audio=fake_audio, sample_rate=48000)
        monkeypatch.setattr("tap_tone_pi.capture.record_audio", lambda **kw: fake_capture)

        # Marginal confidence (0.3 <= conf < 0.5)
        fake_analysis = _make_analysis(confidence=0.4, clipped=False, rms=0.05)
        monkeypatch.setattr("tap_tone_pi.core.analysis.analyze_tap", lambda *a, **kw: fake_analysis)

        fake_persisted = FakePersistedCapture(capture_dir=capture_dir)
        monkeypatch.setattr("tap_tone_pi.io.storage.persist_capture", lambda **kw: fake_persisted)
        monkeypatch.setattr("tap_tone_pi.core.user_config.get_saved_device", lambda: None)

        cmd_record(_args(str(tmp_path / "out")))

        qc_data = json.loads((capture_dir / "quality_check.json").read_text())
        assert qc_data["verdict"] == "warn"
        assert qc_data["warning_count"] >= 1

        # Q012 should be in triggered rules
        rule_ids = [r["rule_id"] for r in qc_data["triggered_rules"]]
        assert "Q012" in rule_ids
