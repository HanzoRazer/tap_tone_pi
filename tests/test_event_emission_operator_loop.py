"""Tests for AgentEventV1 emission from OperatorLoop.

Validates:
1. events.jsonl is created during run_single()
2. Every line is a valid AgentEventV1 JSON with required keys
3. Replay harness accepts the produced file without errors
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tap_tone_pi.workflow.operator_loop import OperatorLoop, LoopState
from tap_tone_pi.workflow.attempt import AttemptStatus
from tap_tone_pi.core.quality_policy import QualityVerdict, Verdict, TriggeredRule, Severity, QualityRule
from tap_tone_pi.core.analysis import AnalysisResult, Peak


# ---------------------------------------------------------------------------
# Required keys per AgentEventV1 schema v1
# ---------------------------------------------------------------------------
REQUIRED_EVENT_KEYS = {
    "event_id",
    "event_type",
    "source",
    "payload",
    "privacy_layer",
    "occurred_at",
    "schema_version",
}

# ---------------------------------------------------------------------------
# Fakes (matching the existing test_workflow_operator_loop.py stubs)
# ---------------------------------------------------------------------------

_Q001_FAKE = QualityRule(
    rule_id="Q001",
    severity=Severity.HARD,
    description="Audio is clipping",
    message="Audio clipped during capture",
)


class _FakeCaptureResult:
    def __init__(self, audio: np.ndarray, sample_rate: int):
        self.audio = audio
        self.sample_rate = sample_rate


def _fake_device_list():
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
    t = np.linspace(0, seconds, int(sample_rate * seconds), dtype=np.float32)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    return _FakeCaptureResult(audio=audio, sample_rate=sample_rate)


def _fake_analyze_tap(audio, sample_rate, **kwargs):
    return AnalysisResult(
        dominant_hz=440.0,
        peaks=[Peak(freq_hz=440.0, magnitude=0.9), Peak(freq_hz=880.0, magnitude=0.5)],
        clipped=False,
        rms=0.05,
        confidence=0.85,
        spectrum_freq_hz=np.array([100.0, 200.0, 300.0]),
        spectrum_mag=np.array([0.1, 0.2, 0.3]),
    )


def _fake_check_quality_pass(analysis, sample_rate, audio=None, thresholds=None):
    return QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])


def _fake_check_quality_fail(analysis, sample_rate, audio=None, thresholds=None):
    return QualityVerdict(
        verdict=Verdict.FAIL,
        triggered_rules=[TriggeredRule(rule=_Q001_FAKE, message="Audio clipped")],
    )


def _fake_analyze_tap_raise(audio, sample_rate, **kwargs):
    raise RuntimeError("Synthetic DSP failure")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def patch_passing(monkeypatch):
    """Patch hardware deps for a PASS path."""
    import tap_tone_pi.workflow.operator_loop as ol
    monkeypatch.setattr(ol, "list_devices", _fake_device_list)
    monkeypatch.setattr(ol, "record_audio", _fake_record_audio)
    monkeypatch.setattr(ol, "analyze_tap", _fake_analyze_tap)
    monkeypatch.setattr(ol, "check_quality", _fake_check_quality_pass)


@pytest.fixture
def patch_failing(monkeypatch):
    """Patch hardware deps for a FAIL path."""
    import tap_tone_pi.workflow.operator_loop as ol
    monkeypatch.setattr(ol, "list_devices", _fake_device_list)
    monkeypatch.setattr(ol, "record_audio", _fake_record_audio)
    monkeypatch.setattr(ol, "analyze_tap", _fake_analyze_tap)
    monkeypatch.setattr(ol, "check_quality", _fake_check_quality_fail)


@pytest.fixture
def patch_analysis_error(monkeypatch):
    """Patch to trigger analysis exception path."""
    import tap_tone_pi.workflow.operator_loop as ol
    monkeypatch.setattr(ol, "list_devices", _fake_device_list)
    monkeypatch.setattr(ol, "record_audio", _fake_record_audio)
    monkeypatch.setattr(ol, "analyze_tap", _fake_analyze_tap_raise)
    monkeypatch.setattr(ol, "check_quality", _fake_check_quality_pass)


# =========================================================================
# Test 1 — events.jsonl is created
# =========================================================================

class TestEventsFileCreated:
    """events.jsonl must exist after a successful run_single()."""

    def test_events_jsonl_exists_after_pass(self, tmp_path, patch_passing):
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_01", device=0, sample_rate=48000, duration=2.5)

        events_path = tmp_path / "events.jsonl"
        assert events_path.exists(), "events.jsonl not created"

    def test_events_jsonl_has_minimum_lines(self, tmp_path, patch_passing):
        """A passing run emits at least 5 events:
        ANALYSIS_STARTED, 3x ARTIFACT_CREATED, ANALYSIS_COMPLETED."""
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_02", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 5, f"Expected >=5 event lines, got {len(lines)}"

    def test_events_jsonl_exists_after_fail(self, tmp_path, patch_failing):
        """Events are emitted even when the quality gate fails."""
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_03", device=0, sample_rate=48000, duration=2.5)

        events_path = tmp_path / "events.jsonl"
        assert events_path.exists()

    def test_fail_path_emits_decision_required(self, tmp_path, patch_failing):
        """FAIL verdict must emit a DECISION_REQUIRED event."""
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_04", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        event_types = [json.loads(line)["event_type"] for line in lines]
        assert "decision_required" in event_types

    def test_analysis_error_emits_analysis_failed(self, tmp_path, patch_analysis_error):
        """Analysis exception must produce ANALYSIS_FAILED event."""
        loop = OperatorLoop(session_dir=tmp_path)
        result = loop.run_single("pt_err", device=0, sample_rate=48000, duration=2.5)

        assert result.error is not None
        events_path = tmp_path / "events.jsonl"
        assert events_path.exists()

        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        event_types = [json.loads(line)["event_type"] for line in lines]
        assert "analysis_failed" in event_types


# =========================================================================
# Test 2 — valid AgentEventV1 JSON
# =========================================================================

class TestEventJsonValidity:
    """Every line must be valid AgentEventV1 JSON with required keys."""

    def test_all_lines_are_valid_json(self, tmp_path, patch_passing):
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_json", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        for i, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                pytest.fail(f"Line {i} is not valid JSON: {line!r}")
            assert isinstance(obj, dict), f"Line {i} is not a JSON object"

    def test_required_keys_present(self, tmp_path, patch_passing):
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_keys", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        for i, line in enumerate(lines):
            obj = json.loads(line)
            missing = REQUIRED_EVENT_KEYS - set(obj.keys())
            assert not missing, f"Line {i} missing keys: {missing}"

    def test_privacy_layer_is_zero(self, tmp_path, patch_passing):
        """All events must have privacy_layer=0 per PR spec."""
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_priv", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        for i, line in enumerate(lines):
            obj = json.loads(line)
            assert obj["privacy_layer"] == 0, f"Line {i}: privacy_layer={obj['privacy_layer']}, expected 0"

    def test_event_types_are_from_vocabulary(self, tmp_path, patch_passing):
        """All event_type values must be from the known vocabulary."""
        valid_types = {
            "analysis_started",
            "analysis_completed",
            "analysis_failed",
            "artifact_created",
            "decision_required",
        }
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_vocab", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        for i, line in enumerate(lines):
            obj = json.loads(line)
            assert obj["event_type"] in valid_types, (
                f"Line {i}: unexpected event_type={obj['event_type']!r}"
            )

    def test_correlation_id_consistent(self, tmp_path, patch_passing):
        """All events from one run_single share the same correlation_id."""
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_corr", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        corr_ids = {json.loads(line)["correlation_id"] for line in lines}
        assert len(corr_ids) == 1, f"Expected 1 correlation_id, got {corr_ids}"


# =========================================================================
# Test 3 — replay compatibility
# =========================================================================

class TestReplayCompatibility:
    """events.jsonl must be loadable by the spine replay harness."""

    def test_replay_load_events_accepts_file(self, tmp_path, patch_passing):
        """replay.load_events() must parse the produced JSONL without error."""
        from tap_tone_pi.agentic.spine.replay import load_events

        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_replay", device=0, sample_rate=48000, duration=2.5)

        events_path = tmp_path / "events.jsonl"
        events = load_events(events_path)

        assert len(events) >= 5
        for e in events:
            assert "event_type" in e
            assert "source" in e

    def test_replay_group_by_session_works(self, tmp_path, patch_passing):
        """group_by_session() must handle the produced events."""
        from tap_tone_pi.agentic.spine.replay import load_events, group_by_session

        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_grp", device=0, sample_rate=48000, duration=2.5)

        events = load_events(tmp_path / "events.jsonl")
        sessions = group_by_session(events)

        assert len(sessions) >= 1
        for sid, evs in sessions.items():
            assert len(evs) >= 5

    def test_multi_attempt_appends(self, tmp_path, patch_passing):
        """Multiple run_single() calls append to the same events.jsonl."""
        loop = OperatorLoop(session_dir=tmp_path)
        loop.run_single("pt_a", device=0, sample_rate=48000, duration=2.5)
        loop.run_single("pt_b", device=0, sample_rate=48000, duration=2.5)

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        # Each passing run emits 5 events → 10+ total
        assert len(lines) >= 10, f"Expected >=10 lines for 2 runs, got {len(lines)}"


# =========================================================================
# Test — No CLI output changes (behavioral guardrail)
# =========================================================================

class TestNoBehavioralChange:
    """Event emission must not change LoopResult or attempt status."""

    def test_pass_result_unchanged(self, tmp_path, patch_passing):
        loop = OperatorLoop(session_dir=tmp_path)
        result = loop.run_single("pt_nochange", device=0, sample_rate=48000, duration=2.5)

        assert result.succeeded is True
        assert result.verdict.verdict == Verdict.PASS
        assert result.attempt.status == AttemptStatus.PASSED
        assert result.error is None

    def test_fail_result_unchanged(self, tmp_path, patch_failing):
        loop = OperatorLoop(session_dir=tmp_path)
        result = loop.run_single("pt_nochange_f", device=0, sample_rate=48000, duration=2.5)

        assert result.succeeded is False
        assert result.verdict.verdict == Verdict.FAIL
        assert result.attempt.status == AttemptStatus.FAILED
