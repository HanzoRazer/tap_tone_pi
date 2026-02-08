"""Tests for CLI agent wiring (PR 3).

These are wiring tests, not agent logic tests.
They verify that --agent flag correctly routes to agent output.
"""
import pytest
from dataclasses import dataclass, field
from io import StringIO
from unittest.mock import patch, MagicMock
import numpy as np

from tap_tone_pi.core.quality_policy import (
    QualityRule,
    QualityVerdict,
    TriggeredRule,
    Verdict,
    Severity,
)
from tap_tone_pi.core.analysis import AnalysisResult, Peak
from tap_tone_pi.workflow.attempt import Attempt


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_pass_verdict():
    """A PASS verdict with no triggered rules."""
    return QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])


@pytest.fixture
def mock_fail_verdict():
    """A FAIL verdict with triggered rules."""
    rule = QualityRule("Q001", Severity.HARD, "Clipping", "Signal clipped")
    return QualityVerdict(
        verdict=Verdict.FAIL,
        triggered_rules=[TriggeredRule(rule=rule, message="Signal clipped")],
    )


@pytest.fixture
def mock_analysis():
    """A minimal analysis result."""
    return AnalysisResult(
        dominant_hz=185.0,
        peaks=[Peak(freq_hz=185.0, magnitude=0.8, bin_index=10)],
        spectrum_freq_hz=np.linspace(0, 1000, 100),
        spectrum_mag=np.zeros(100),
        rms=0.05,
        clipped=False,
        confidence=0.9,
    )


@pytest.fixture
def mock_attempt():
    """A minimal attempt object."""
    return Attempt(
        point_id="point_001",
        attempt_num=1,
        state="completed",
        succeeded=True,
    )


# =============================================================================
# Mock LoopResult
# =============================================================================

@dataclass
class MockLoopResult:
    """Matches LoopResult fields for testing."""
    attempt: Attempt
    audio: np.ndarray | None = None
    analysis: AnalysisResult | None = None
    verdict: QualityVerdict | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.attempt.succeeded

    @property
    def can_proceed(self) -> bool:
        if self.verdict is None:
            return False
        return self.verdict.verdict in (Verdict.PASS, Verdict.WARN)


# =============================================================================
# cmd_measure wiring tests
# =============================================================================

class TestMeasureAgentWiring:
    """Test that measure --agent routes to agent output."""

    def test_measure_agent_flag_produces_agent_output(
        self, mock_pass_verdict, mock_analysis, mock_attempt, tmp_path
    ):
        """With --agent, measure should print agent-formatted output."""
        from tap_tone_pi.cli.main import cmd_measure
        import argparse

        # Build a fake result
        result = MockLoopResult(
            attempt=mock_attempt,
            audio=np.zeros(1000),
            analysis=mock_analysis,
            verdict=mock_pass_verdict,
        )

        # Mock the OperatorLoop
        mock_loop = MagicMock()
        mock_loop.run_single.return_value = result
        mock_loop.store.get_attempt_dir.return_value = tmp_path

        args = argparse.Namespace(
            device=None,
            sample_rate=48000,
            seconds=2.5,
            out=str(tmp_path),
            point="point_001",
            max_attempts=1,
            agent=True,
            expert=False,
        )

        with patch("tap_tone_pi.cli.main.OperatorLoop", return_value=mock_loop):
            with patch("tap_tone_pi.core.user_config.get_saved_device", return_value=None):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    ret = cmd_measure(args)

        output = mock_stdout.getvalue()
        # Agent output includes "Measurement accepted" or similar
        assert "Measurement" in output or "accepted" in output.lower()

    def test_measure_no_agent_flag_produces_legacy_output(
        self, mock_pass_verdict, mock_analysis, mock_attempt, tmp_path
    ):
        """Without --agent, measure should print legacy format."""
        from tap_tone_pi.cli.main import cmd_measure
        import argparse

        result = MockLoopResult(
            attempt=mock_attempt,
            audio=np.zeros(1000),
            analysis=mock_analysis,
            verdict=mock_pass_verdict,
        )

        mock_loop = MagicMock()
        mock_loop.run_single.return_value = result
        mock_loop.store.get_attempt_dir.return_value = tmp_path

        args = argparse.Namespace(
            device=None,
            sample_rate=48000,
            seconds=2.5,
            out=str(tmp_path),
            point="point_001",
            max_attempts=1,
            agent=False,
            expert=False,
        )

        with patch("tap_tone_pi.cli.main.OperatorLoop", return_value=mock_loop):
            with patch("tap_tone_pi.core.user_config.get_saved_device", return_value=None):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    ret = cmd_measure(args)

        output = mock_stdout.getvalue()
        # Legacy output includes [PASS] format
        assert "PASS" in output


# =============================================================================
# cmd_record wiring tests
# =============================================================================

class TestRecordAgentWiring:
    """Test that record --agent routes to agent output."""

    def test_record_agent_flag_produces_agent_output(
        self, mock_pass_verdict, mock_analysis, tmp_path
    ):
        """With --agent, record should print agent-formatted output."""
        from tap_tone_pi.cli.main import cmd_record
        import argparse

        # Mock the capture and analysis chain
        mock_cap = MagicMock()
        mock_cap.audio = np.zeros(1000)
        mock_cap.sample_rate = 48000

        mock_persisted = MagicMock()
        mock_persisted.capture_dir = tmp_path

        args = argparse.Namespace(
            device=None,
            sample_rate=48000,
            channels=1,
            seconds=2.5,
            out=str(tmp_path),
            label="test_point",
            agent=True,
            expert=False,
        )

        with patch("tap_tone_pi.cli.main.record_audio", return_value=mock_cap):
            with patch("tap_tone_pi.cli.main.analyze_tap", return_value=mock_analysis):
                with patch("tap_tone_pi.cli.main.check_quality", return_value=mock_pass_verdict):
                    with patch("tap_tone_pi.cli.main.persist_capture", return_value=mock_persisted):
                        with patch("tap_tone_pi.core.user_config.get_saved_device", return_value=None):
                            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                                # Mock the QC JSON write
                                with patch.object(tmp_path.__class__, "__truediv__", return_value=MagicMock()):
                                    ret = cmd_record(args)

        output = mock_stdout.getvalue()
        # Agent output includes "Measurement" or verdict info
        assert "Measurement" in output or "accepted" in output.lower() or "passed" in output.lower()

    def test_record_no_agent_flag_produces_legacy_output(
        self, mock_pass_verdict, mock_analysis, tmp_path
    ):
        """Without --agent, record should print legacy QC: format."""
        from tap_tone_pi.cli.main import cmd_record
        import argparse

        mock_cap = MagicMock()
        mock_cap.audio = np.zeros(1000)
        mock_cap.sample_rate = 48000

        mock_persisted = MagicMock()
        mock_persisted.capture_dir = tmp_path

        args = argparse.Namespace(
            device=None,
            sample_rate=48000,
            channels=1,
            seconds=2.5,
            out=str(tmp_path),
            label="test_point",
            agent=False,
            expert=False,
        )

        with patch("tap_tone_pi.cli.main.record_audio", return_value=mock_cap):
            with patch("tap_tone_pi.cli.main.analyze_tap", return_value=mock_analysis):
                with patch("tap_tone_pi.cli.main.check_quality", return_value=mock_pass_verdict):
                    with patch("tap_tone_pi.cli.main.persist_capture", return_value=mock_persisted):
                        with patch("tap_tone_pi.core.user_config.get_saved_device", return_value=None):
                            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                                with patch.object(tmp_path.__class__, "__truediv__", return_value=MagicMock()):
                                    ret = cmd_record(args)

        output = mock_stdout.getvalue()
        # Legacy format is "QC: PASS rules=none"
        assert "QC:" in output and "PASS" in output


# =============================================================================
# Parser tests (ensure flags exist)
# =============================================================================

class TestParserFlags:
    """Test that --agent and --expert flags are present."""

    def test_record_has_agent_flag(self):
        from tap_tone_pi.cli.main import build_parser
        parser = build_parser()
        # Parse a minimal record command
        args = parser.parse_args(["record", "--out", "/tmp/test", "--agent"])
        assert args.agent is True

    def test_record_has_expert_flag(self):
        from tap_tone_pi.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["record", "--out", "/tmp/test", "--expert"])
        assert args.expert is True

    def test_measure_has_agent_flag(self):
        from tap_tone_pi.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["measure", "--out", "/tmp/test", "--agent"])
        assert args.agent is True

    def test_measure_has_expert_flag(self):
        from tap_tone_pi.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["measure", "--out", "/tmp/test", "--expert"])
        assert args.expert is True

    def test_agent_defaults_to_false(self):
        from tap_tone_pi.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["record", "--out", "/tmp/test"])
        assert args.agent is False
        args = parser.parse_args(["measure", "--out", "/tmp/test"])
        assert args.agent is False
