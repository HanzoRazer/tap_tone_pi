"""Hermetic CLI wiring tests for agent vs legacy output (PR 3).

These tests monkeypatch OperatorLoop to avoid any real capture, DSP, or filesystem
assumptions. They pin behavior to two mutually exclusive user-visible strings:
- agent headline ("Measurement accepted")
- legacy headline ("[PASS]")

They only fail if integration wiring breaks — exactly what we want.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

import pytest

from tap_tone_pi.cli.main import cmd_measure
from tap_tone_pi.core.quality_policy import Verdict

# --- Minimal fake LoopResult-compatible object (avoid importing numpy/AnalysisResult) ---


# Skip tests if sounddevice/PortAudio not available
try:
    import sounddevice as _sd  # noqa: F401, E402

    _HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    _HAS_SOUNDDEVICE = False

requires_sounddevice = pytest.mark.skipif(
    not _HAS_SOUNDDEVICE, reason="sounddevice/PortAudio not available"
)


@dataclass
class _FakeAttempt:
    attempt_id: str = "attempt_001"
    point_id: str = "point_001"
    attempt_number: int = 1
    succeeded: bool = True  # LoopResult.succeeded property proxies attempt.succeeded


@dataclass
class _FakeLoopResult:
    attempt: _FakeAttempt
    audio: object | None = None
    analysis: object | None = None
    verdict: object | None = None
    error: str | None = None


class _FakeQualityVerdict:
    """Minimal object that behaves like QualityVerdict for printing + agent formatting."""

    def __init__(self, v: Verdict):
        self.verdict = v
        self.triggered_rules = []

    # Agent/JSON paths sometimes read these optionally
    policy_version = "1.0.0"

    @property
    def errors(self):
        return []

    @property
    def warnings(self):
        return []


@pytest.fixture
def _stub_operator_loop(monkeypatch, tmp_path: Path):
    """
    Monkeypatch OperatorLoop to avoid any real capture, DSP, or filesystem assumptions.
    """

    class _StubLoop:
        def __init__(self, session_dir: Path, callback=None):
            self.session_dir = session_dir
            self.callback = callback
            # store/get_attempt_dir is printed in cmd_measure on accept paths
            self.store = type(
                "Store",
                (),
                {
                    "get_attempt_dir": lambda _self, attempt: session_dir
                    / attempt.attempt_id
                },
            )()

        def run_single(self, *, point_id, device, sample_rate, duration, **kwargs):
            # PASS by default; tests can monkeypatch this method per-test
            return _FakeLoopResult(
                attempt=_FakeAttempt(point_id=point_id),
                verdict=_FakeQualityVerdict(Verdict.PASS),
                error=None,
            )

        def override_failed(self, point_id: str, reason: str) -> None:
            return None

    # OperatorLoop is imported inside cmd_measure from tap_tone_pi.workflow
    monkeypatch.setattr("tap_tone_pi.workflow.operator_loop.OperatorLoop", _StubLoop)
    monkeypatch.setattr("tap_tone_pi.workflow.OperatorLoop", _StubLoop)
    return tmp_path


def _measure_args(tmp_path: Path, *, agent: bool) -> argparse.Namespace:
    # cmd_measure reads args.agent / args.expert in PR3 wiring.
    return argparse.Namespace(
        device=None,
        sample_rate=48000,
        seconds=0.1,
        out=str(tmp_path / "session_out"),
        point="point_001",
        max_attempts=1,
        agent=agent,
        expert=False,
    )


@requires_sounddevice
def test_measure_agent_enabled_uses_agent_renderer(
    _stub_operator_loop, capsys, tmp_path
):
    """
    Guardrail: when --agent is enabled, we should see the agent headline
    (e.g. 'Measurement accepted' from Verdict template), not legacy [PASS]/[WARN]/[FAIL].
    """
    args = _measure_args(tmp_path, agent=True)

    rc = cmd_measure(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "Measurement accepted" in out
    # legacy function prints '[PASS]' style header; we should not see it in agent mode
    assert "[PASS]" not in out


@requires_sounddevice
def test_measure_agent_disabled_uses_legacy_summary(
    _stub_operator_loop, capsys, tmp_path
):
    """
    Guardrail: when --agent is disabled, we should keep legacy format_verdict_summary output.
    """
    args = _measure_args(tmp_path, agent=False)

    rc = cmd_measure(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "[PASS]" in out
    assert "Measurement accepted" not in out
