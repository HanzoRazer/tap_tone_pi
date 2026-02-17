"""Tests for the operator loop state machine.

Tests OperatorLoop state transitions, retry logic, and override behavior.
Uses monkeypatch to stub hardware-dependent functions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pytest

from tap_tone_pi.workflow.operator_loop import (
    OperatorLoop,
    LoopState,
    LoopResult,
)
from tap_tone_pi.workflow.attempt import AttemptStatus
from tap_tone_pi.core.quality_policy import (
    QualityVerdict,
    Verdict,
    TriggeredRule,
    Severity,
    QualityRule,
)
from tap_tone_pi.core.analysis import AnalysisResult, Peak


# =============================================================================
# Fixtures
# =============================================================================

# Define fake rules for testing
_Q010_FAKE = QualityRule(
    rule_id="Q010",
    severity=Severity.SOFT,
    description="Confidence below threshold",
    message="Confidence is low",
)

_Q001_FAKE = QualityRule(
    rule_id="Q001",
    severity=Severity.HARD,
    description="Audio is clipping",
    message="Audio clipped during capture",
)


@dataclass
class FakeCaptureResult:
    """Stub for capture result."""

    audio: np.ndarray
    sample_rate: int


def _fake_device_list():
    """Return fake device list with one input device."""
    return [
        {
            "index": 0,
            "name": "Test Mic",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
        }
    ]


def _fake_record_audio(device=None, sample_rate=48000, channels=1, seconds=2.5):
    """Fake record_audio returning synthetic sine wave."""
    t = np.linspace(0, seconds, int(sample_rate * seconds), dtype=np.float32)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    return FakeCaptureResult(audio=audio, sample_rate=sample_rate)


def _fake_analyze_tap(audio, sample_rate, **kwargs):
    """Fake analyze_tap returning valid results."""
    return AnalysisResult(
        dominant_hz=440.0,
        peaks=[
            Peak(freq_hz=440.0, magnitude=0.9),
            Peak(freq_hz=880.0, magnitude=0.5),
        ],
        clipped=False,
        rms=0.05,
        confidence=0.85,
        spectrum_freq_hz=np.array([100.0, 200.0, 300.0]),
        spectrum_mag=np.array([0.1, 0.2, 0.3]),
    )


def _fake_check_quality_pass(analysis, sample_rate, audio=None, thresholds=None):
    """Fake check_quality returning PASS verdict."""
    return QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])


def _fake_check_quality_warn(analysis, sample_rate, audio=None, thresholds=None):
    """Fake check_quality returning WARN verdict."""
    return QualityVerdict(
        verdict=Verdict.WARN,
        triggered_rules=[
            TriggeredRule(
                rule=_Q010_FAKE,
                message="Confidence is low",
            )
        ],
    )


def _fake_check_quality_fail(analysis, sample_rate, audio=None, thresholds=None):
    """Fake check_quality returning FAIL verdict."""
    return QualityVerdict(
        verdict=Verdict.FAIL,
        triggered_rules=[
            TriggeredRule(
                rule=_Q001_FAKE,
                message="Audio clipped during capture",
            )
        ],
    )


@pytest.fixture
def patch_all_passing(monkeypatch):
    """Patch all hardware functions with passing stubs."""
    import tap_tone_pi.workflow.operator_loop as ol_module

    monkeypatch.setattr(ol_module, "list_devices", _fake_device_list)
    monkeypatch.setattr(ol_module, "record_audio", _fake_record_audio)
    monkeypatch.setattr(ol_module, "analyze_tap", _fake_analyze_tap)
    monkeypatch.setattr(ol_module, "check_quality", _fake_check_quality_pass)


@pytest.fixture
def patch_with_warn(monkeypatch):
    """Patch with WARN verdict."""
    import tap_tone_pi.workflow.operator_loop as ol_module

    monkeypatch.setattr(ol_module, "list_devices", _fake_device_list)
    monkeypatch.setattr(ol_module, "record_audio", _fake_record_audio)
    monkeypatch.setattr(ol_module, "analyze_tap", _fake_analyze_tap)
    monkeypatch.setattr(ol_module, "check_quality", _fake_check_quality_warn)


@pytest.fixture
def patch_with_fail(monkeypatch):
    """Patch with FAIL verdict."""
    import tap_tone_pi.workflow.operator_loop as ol_module

    monkeypatch.setattr(ol_module, "list_devices", _fake_device_list)
    monkeypatch.setattr(ol_module, "record_audio", _fake_record_audio)
    monkeypatch.setattr(ol_module, "analyze_tap", _fake_analyze_tap)
    monkeypatch.setattr(ol_module, "check_quality", _fake_check_quality_fail)


# =============================================================================
# OperatorLoop Initialization Tests
# =============================================================================


class TestOperatorLoopInit:
    """Test OperatorLoop initialization."""

    def test_init_creates_session_dir(self, tmp_path, patch_all_passing):
        """OperatorLoop creates session directory if missing."""
        session_dir = tmp_path / "new_session"
        assert not session_dir.exists()

        _loop = OperatorLoop(session_dir=session_dir)

        assert session_dir.exists()

    def test_init_starts_in_idle(self, tmp_path, patch_all_passing):
        """OperatorLoop starts in IDLE state."""
        _loop = OperatorLoop(session_dir=tmp_path)
        assert loop.state == LoopState.IDLE


# =============================================================================
# Preflight Tests
# =============================================================================


class TestPreflight:
    """Test preflight checks."""

    def test_preflight_passes_with_device(self, tmp_path, patch_all_passing):
        """preflight() passes when input device exists."""
        _loop = OperatorLoop(session_dir=tmp_path)

        ok, msg = loop.preflight()

        assert ok is True
        assert "input device" in msg.lower() or "device" in msg.lower()

    def test_preflight_no_devices(self, tmp_path, monkeypatch):
        """preflight() fails when no devices available."""
        import tap_tone_pi.workflow.operator_loop as ol_module

        monkeypatch.setattr(ol_module, "list_devices", lambda: [])

        _loop = OperatorLoop(session_dir=tmp_path)

        ok, msg = loop.preflight()

        assert ok is False
        assert "no" in msg.lower()


# =============================================================================
# run_single Tests (PASS Path)
# =============================================================================


class TestRunSinglePassPath:
    """Test run_single() when quality passes."""

    def test_run_single_pass_returns_success(self, tmp_path, patch_all_passing):
        """run_single returns success when quality passes."""
        _loop = OperatorLoop(session_dir=tmp_path)

        result = loop.run_single(
            point_id="test_point",
            device=0,
            sample_rate=48000,
            duration=2.5,
        )

        assert result.succeeded is True
        assert result.verdict.verdict == Verdict.PASS
        assert result.attempt is not None
        assert result.attempt.status == AttemptStatus.PASSED

    def test_run_single_creates_attempt_dir(self, tmp_path, patch_all_passing):
        """run_single creates attempt directory."""
        _loop = OperatorLoop(session_dir=tmp_path)

        loop.run_single(point_id="pt_A", device=0, sample_rate=48000, duration=2.5)

        attempt_dir = tmp_path / "pt_A" / "attempt_001"
        assert attempt_dir.exists()

    def test_run_single_writes_audio(self, tmp_path, patch_all_passing):
        """run_single saves audio.wav to attempt directory."""
        _loop = OperatorLoop(session_dir=tmp_path)

        loop.run_single(point_id="pt_B", device=0, sample_rate=48000, duration=2.5)

        audio_path = tmp_path / "pt_B" / "attempt_001" / "audio.wav"
        assert audio_path.exists()

    def test_run_single_writes_analysis(self, tmp_path, patch_all_passing):
        """run_single saves analysis.json to attempt directory."""
        _loop = OperatorLoop(session_dir=tmp_path)

        loop.run_single(point_id="pt_C", device=0, sample_rate=48000, duration=2.5)

        analysis_path = tmp_path / "pt_C" / "attempt_001" / "analysis.json"
        assert analysis_path.exists()

        # Verify structure
        data = json.loads(analysis_path.read_text())
        assert "dominant_hz" in data
        assert "peaks" in data

    def test_run_single_writes_quality_check(self, tmp_path, patch_all_passing):
        """run_single saves quality_check.json to attempt directory."""
        _loop = OperatorLoop(session_dir=tmp_path)

        loop.run_single(point_id="pt_D", device=0, sample_rate=48000, duration=2.5)

        qc_path = tmp_path / "pt_D" / "attempt_001" / "quality_check.json"
        assert qc_path.exists()

        # Verify structure
        data = json.loads(qc_path.read_text())
        assert data["verdict"] == "pass"


# =============================================================================
# run_single Tests (WARN Path)
# =============================================================================


class TestRunSingleWarnPath:
    """Test run_single() when quality warns."""

    def test_run_single_warn_returns_success(self, tmp_path, patch_with_warn):
        """run_single with WARN verdict still succeeds."""
        _loop = OperatorLoop(session_dir=tmp_path)

        result = loop.run_single(
            point_id="warn_point",
            device=0,
            sample_rate=48000,
            duration=2.5,
        )

        assert result.succeeded is True
        assert result.verdict.verdict == Verdict.WARN
        assert result.attempt.status == AttemptStatus.WARNED


# =============================================================================
# run_single Tests (FAIL Path)
# =============================================================================


class TestRunSingleFailPath:
    """Test run_single() when quality fails."""

    def test_run_single_fail_returns_failure(self, tmp_path, patch_with_fail):
        """run_single with FAIL verdict returns failure."""
        _loop = OperatorLoop(session_dir=tmp_path)

        result = loop.run_single(
            point_id="fail_point",
            device=0,
            sample_rate=48000,
            duration=2.5,
        )

        assert result.succeeded is False
        assert result.verdict.verdict == Verdict.FAIL
        assert result.attempt.status == AttemptStatus.FAILED

    def test_run_single_fail_still_saves_artifacts(self, tmp_path, patch_with_fail):
        """Failed attempts still save their artifacts."""
        _loop = OperatorLoop(session_dir=tmp_path)

        loop.run_single(point_id="fail_save", device=0, sample_rate=48000, duration=2.5)

        # Artifacts should exist even for failed attempts
        assert (tmp_path / "fail_save" / "attempt_001" / "audio.wav").exists()
        assert (tmp_path / "fail_save" / "attempt_001" / "analysis.json").exists()
        assert (tmp_path / "fail_save" / "attempt_001" / "quality_check.json").exists()


# =============================================================================
# Retry Tests
# =============================================================================


class TestRetryBehavior:
    """Test retry behavior for failed attempts."""

    def test_retry_increments_attempt_number(self, tmp_path, monkeypatch):
        """Retrying creates attempt_002, attempt_003, etc."""
        import tap_tone_pi.workflow.operator_loop as ol_module

        call_count = [0]

        def check_first_fail(analysis, sample_rate, audio=None, thresholds=None):
            call_count[0] += 1
            if call_count[0] < 3:
                return QualityVerdict(verdict=Verdict.FAIL, triggered_rules=[])
            return QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])

        monkeypatch.setattr(ol_module, "list_devices", _fake_device_list)
        monkeypatch.setattr(ol_module, "record_audio", _fake_record_audio)
        monkeypatch.setattr(ol_module, "analyze_tap", _fake_analyze_tap)
        monkeypatch.setattr(ol_module, "check_quality", check_first_fail)

        _loop = OperatorLoop(session_dir=tmp_path)

        # First two attempts fail
        r1 = loop.run_single("retry_pt", 0, 48000, 2.5)
        assert r1.succeeded is False
        assert (tmp_path / "retry_pt" / "attempt_001").exists()

        r2 = loop.run_single("retry_pt", 0, 48000, 2.5)
        assert r2.succeeded is False
        assert (tmp_path / "retry_pt" / "attempt_002").exists()

        # Third attempt passes
        r3 = loop.run_single("retry_pt", 0, 48000, 2.5)
        assert r3.succeeded is True
        assert (tmp_path / "retry_pt" / "attempt_003").exists()


# =============================================================================
# Override Tests
# =============================================================================


class TestOverrideBehavior:
    """Test operator override for failed attempts."""

    def test_override_failed_succeeds(self, tmp_path, patch_with_fail):
        """override_failed marks failed attempt as overridden."""
        _loop = OperatorLoop(session_dir=tmp_path)

        result = loop.run_single("override_pt", 0, 48000, 2.5)
        assert result.succeeded is False

        # Override the failed attempt
        overridden = loop.override_failed(
            point_id="override_pt",
            reason="Operator override: acceptable noise floor",
        )

        assert overridden is not None
        assert overridden.status == AttemptStatus.OVERRIDDEN
        assert "acceptable noise floor" in overridden.override_reason

    def test_override_nonexistent_returns_none(self, tmp_path, patch_all_passing):
        """override_failed returns None for nonexistent point."""
        _loop = OperatorLoop(session_dir=tmp_path)

        result = loop.override_failed(
            point_id="no_such_point",
            reason="Should fail",
        )

        assert result is None

    def test_override_passed_returns_none(self, tmp_path, patch_all_passing):
        """override_failed returns None for passed attempt."""
        _loop = OperatorLoop(session_dir=tmp_path)

        loop.run_single("pass_pt", 0, 48000, 2.5)

        result = loop.override_failed(
            point_id="pass_pt",
            reason="Should fail - already passed",
        )

        assert result is None

    def test_override_requires_reason(self, tmp_path, patch_with_fail):
        """override_failed raises ValueError for empty reason."""
        _loop = OperatorLoop(session_dir=tmp_path)

        loop.run_single("reason_test", 0, 48000, 2.5)

        with pytest.raises(ValueError, match="[Rr]eason"):
            loop.override_failed(point_id="reason_test", reason="")


# =============================================================================
# State Tracking Tests
# =============================================================================


class TestStateTracking:
    """Test state tracking via callback."""

    def test_callback_receives_state_changes(self, tmp_path, patch_all_passing):
        """Callback is called for each state change."""
        states_seen = []

        def callback(state, data):
            states_seen.append(state)

        _loop = OperatorLoop(session_dir=tmp_path, callback=callback)
        loop.run_single("cb_test", 0, 48000, 2.5)

        # Should see: PREFLIGHT, READY, CAPTURING, ANALYZING, GATING, PASSED
        assert LoopState.PREFLIGHT in states_seen
        assert LoopState.READY in states_seen
        assert LoopState.CAPTURING in states_seen
        assert LoopState.ANALYZING in states_seen
        assert LoopState.GATING in states_seen
        assert LoopState.PASSED in states_seen


# =============================================================================
# LoopResult Tests
# =============================================================================


class TestLoopResult:
    """Test LoopResult dataclass."""

    def test_loop_result_from_success(self, tmp_path, patch_all_passing):
        """LoopResult contains correct fields on success."""
        _loop = OperatorLoop(session_dir=tmp_path)

        result = loop.run_single("lr_test", 0, 48000, 2.5)

        assert isinstance(result, LoopResult)
        assert result.succeeded is True
        assert result.can_proceed is True
        assert result.verdict.verdict == Verdict.PASS
        assert result.attempt is not None
        assert result.audio is not None
        assert result.analysis is not None
        assert result.error is None

    def test_loop_result_from_failure(self, tmp_path, patch_with_fail):
        """LoopResult contains correct fields on failure."""
        _loop = OperatorLoop(session_dir=tmp_path)

        result = loop.run_single("lr_fail", 0, 48000, 2.5)

        assert result.succeeded is False
        assert result.can_proceed is False
        assert result.verdict.verdict == Verdict.FAIL
        assert result.attempt is not None
        assert result.audio is not None  # Audio still captured
        assert result.analysis is not None  # Analysis still run
