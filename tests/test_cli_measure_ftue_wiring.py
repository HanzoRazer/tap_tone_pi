"""Tests for CLI measure command FTUE wiring.

PR5: Ensures cmd_measure uses persisted FTUE state and updates it correctly.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock


@dataclass
class _StubAnalysis:
    """Minimal analysis result for testing."""

    dominant_hz: float = 440.0
    rms: float = 0.05
    confidence: float = 0.9
    peaks: list = None

    def __post_init__(self):
        if self.peaks is None:
            self.peaks = []


@dataclass
class _StubResult:
    """Minimal loop result for testing."""

    error: str | None = None
    analysis: _StubAnalysis | None = None
    verdict: Any = None
    attempt: str = "attempt_001"


class TestCmdMeasureFtueWiring:
    """cmd_measure correctly loads, updates, and saves FTUE state."""

    def test_session_count_increments_once_per_invocation(
        self, tmp_path: Path, monkeypatch
    ):
        """session_count_lifetime increments exactly once per cmd_measure call."""
        from tap_tone_pi.core.user_config import (
            UserConfig,
            save_config,
            load_config,
        )
        from tap_tone_pi.core.quality_policy import QualityVerdict, Verdict

        # Setup: create fresh config at tmp path
        config_path = tmp_path / "config.json"
        cfg = UserConfig()
        cfg.ftue.session_count_lifetime = 0
        cfg.ftue.pass_count_lifetime = 0
        save_config(cfg, path=config_path)

        # Monkeypatch CONFIG_FILE to use tmp path
        import tap_tone_pi.core.user_config as user_config_mod

        monkeypatch.setattr(user_config_mod, "CONFIG_FILE", config_path)

        # Create a PASS verdict
        pass_verdict = QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])

        # Stub the OperatorLoop to return PASS immediately
        class _StubLoop:
            def __init__(self, **kwargs):
                self.store = MagicMock()
                self.store.get_attempt_dir.return_value = tmp_path / "attempt_001"

            def run_single(self, **kwargs):
                return _StubResult(
                    analysis=_StubAnalysis(),
                    verdict=pass_verdict,
                )

        import tap_tone_pi.workflow as workflow_mod

        monkeypatch.setattr(workflow_mod, "OperatorLoop", _StubLoop)

        # Create args namespace
        args = argparse.Namespace(
            device=0,
            sample_rate=48000,
            out=str(tmp_path / "session"),
            seconds=1.0,
            max_attempts=3,
            point="point_001",
            agent=False,  # non-agent mode to avoid extra complexity
            expert=False,
        )

        # Run cmd_measure
        from tap_tone_pi.cli.main import cmd_measure

        exit_code = cmd_measure(args)

        # Verify
        assert exit_code == 0
        reloaded = load_config(path=config_path)
        assert reloaded.ftue.session_count_lifetime == 1

    def test_pass_increments_pass_count_warn_does_not(
        self, tmp_path: Path, monkeypatch
    ):
        """pass_count_lifetime increments only on PASS, not WARN."""
        from tap_tone_pi.core.user_config import (
            UserConfig,
            save_config,
            load_config,
        )
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
            TriggeredRule,
            Q010_QUIET,
        )

        # Setup: create fresh config
        config_path = tmp_path / "config.json"
        cfg = UserConfig()
        cfg.ftue.session_count_lifetime = 0
        cfg.ftue.pass_count_lifetime = 0
        save_config(cfg, path=config_path)

        # Monkeypatch CONFIG_FILE
        import tap_tone_pi.core.user_config as user_config_mod

        monkeypatch.setattr(user_config_mod, "CONFIG_FILE", config_path)

        # Create verdicts
        pass_verdict = QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])
        warn_verdict = QualityVerdict(
            verdict=Verdict.WARN,
            triggered_rules=[TriggeredRule(rule=Q010_QUIET, message="Signal is quiet")],
        )

        # Track which verdict to return
        verdict_sequence = [pass_verdict]  # First call returns PASS

        class _StubLoop:
            def __init__(self, **kwargs):
                self.store = MagicMock()
                self.store.get_attempt_dir.return_value = tmp_path / "attempt_001"

            def run_single(self, **kwargs):
                v = verdict_sequence.pop(0) if verdict_sequence else pass_verdict
                return _StubResult(
                    analysis=_StubAnalysis(),
                    verdict=v,
                )

        import tap_tone_pi.workflow as workflow_mod

        monkeypatch.setattr(workflow_mod, "OperatorLoop", _StubLoop)

        args = argparse.Namespace(
            device=0,
            sample_rate=48000,
            out=str(tmp_path / "session1"),
            seconds=1.0,
            max_attempts=3,
            point="point_001",
            agent=True,  # Enable agent mode to trigger FTUE update path
            expert=False,
        )

        # Run 1: PASS
        from tap_tone_pi.cli.main import cmd_measure

        exit_code = cmd_measure(args)
        assert exit_code == 0

        reloaded = load_config(path=config_path)
        assert reloaded.ftue.pass_count_lifetime == 1
        assert reloaded.ftue.session_count_lifetime == 1

        # Run 2: WARN (with user accepting)
        verdict_sequence.append(warn_verdict)
        args.out = str(tmp_path / "session2")

        # Monkeypatch input to auto-accept WARN
        monkeypatch.setattr("builtins.input", lambda _: "y")

        exit_code = cmd_measure(args)
        assert exit_code == 0

        reloaded = load_config(path=config_path)
        # pass_count should still be 1 (WARN does NOT increment)
        assert reloaded.ftue.pass_count_lifetime == 1
        # session_count should be 2 (one per invocation)
        assert reloaded.ftue.session_count_lifetime == 2
        # seen_rule_ids should contain Q010
        assert "Q010" in reloaded.ftue.seen_rule_ids

    def test_agent_context_receives_ftue_counts(self, tmp_path: Path, monkeypatch):
        """AgentContext is constructed with pass_count_lifetime and session_count_lifetime."""
        from tap_tone_pi.core.user_config import (
            UserConfig,
            save_config,
        )
        from tap_tone_pi.core.quality_policy import QualityVerdict, Verdict

        # Setup: config with existing counts
        config_path = tmp_path / "config.json"
        cfg = UserConfig()
        cfg.ftue.session_count_lifetime = 5
        cfg.ftue.pass_count_lifetime = 3
        save_config(cfg, path=config_path)

        import tap_tone_pi.core.user_config as user_config_mod

        monkeypatch.setattr(user_config_mod, "CONFIG_FILE", config_path)

        pass_verdict = QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])

        class _StubLoop:
            def __init__(self, **kwargs):
                self.store = MagicMock()
                self.store.get_attempt_dir.return_value = tmp_path / "attempt_001"

            def run_single(self, **kwargs):
                return _StubResult(
                    analysis=_StubAnalysis(),
                    verdict=pass_verdict,
                )

        import tap_tone_pi.workflow as workflow_mod

        monkeypatch.setattr(workflow_mod, "OperatorLoop", _StubLoop)

        # Capture the AgentContext that gets created
        captured_ctx = []
        original_format = None

        def capture_format(ctx, verdict):
            captured_ctx.append(ctx)
            return "Measurement accepted"

        import tap_tone_pi.agent.messages as messages_mod

        _original_format = messages_mod.format_verdict_summary_agent
        monkeypatch.setattr(
            messages_mod, "format_verdict_summary_agent", capture_format
        )

        args = argparse.Namespace(
            device=0,
            sample_rate=48000,
            out=str(tmp_path / "session"),
            seconds=1.0,
            max_attempts=3,
            point="point_001",
            agent=True,
            expert=False,
        )

        from tap_tone_pi.cli.main import cmd_measure

        exit_code = cmd_measure(args)
        assert exit_code == 0

        # Verify AgentContext received the FTUE counts
        assert len(captured_ctx) == 1
        ctx = captured_ctx[0]
        # session_count was 5, then incremented to 6 at start of cmd_measure
        assert ctx.session_count_lifetime == 6
        # pass_count was 3, then incremented to 4 after PASS verdict
        assert ctx.pass_count_lifetime == 4

    def test_override_increments_override_count_mid_session(
        self, tmp_path: Path, monkeypatch
    ):
        """override_count_lifetime increments when user overrides a FAIL mid-session."""
        from tap_tone_pi.core.user_config import (
            UserConfig,
            save_config,
            load_config,
        )
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
            TriggeredRule,
            Q001_CLIPPED,
        )

        # Setup: fresh config
        config_path = tmp_path / "config.json"
        cfg = UserConfig()
        cfg.ftue.override_count_lifetime = 0
        cfg.ftue.pass_count_lifetime = 0
        save_config(cfg, path=config_path)

        import tap_tone_pi.core.user_config as user_config_mod

        monkeypatch.setattr(user_config_mod, "CONFIG_FILE", config_path)

        # Create FAIL verdict
        fail_verdict = QualityVerdict(
            verdict=Verdict.FAIL,
            triggered_rules=[
                TriggeredRule(rule=Q001_CLIPPED, message="Clipping detected")
            ],
        )

        class _StubLoop:
            def __init__(self, **kwargs):
                self.store = MagicMock()
                self.store.get_attempt_dir.return_value = tmp_path / "attempt_001"
                self.overridden = False

            def run_single(self, **kwargs):
                return _StubResult(
                    analysis=_StubAnalysis(),
                    verdict=fail_verdict,
                )

            def override_failed(self, point_id, reason):
                self.overridden = True

        import tap_tone_pi.workflow as workflow_mod

        monkeypatch.setattr(workflow_mod, "OperatorLoop", _StubLoop)

        # Input sequence: "n" to decline retry, "my reason" for override
        input_responses = iter(["n", "my override reason"])
        monkeypatch.setattr("builtins.input", lambda _: next(input_responses))

        args = argparse.Namespace(
            device=0,
            sample_rate=48000,
            out=str(tmp_path / "session"),
            seconds=1.0,
            max_attempts=3,
            point="point_001",
            agent=False,
            expert=False,
        )

        from tap_tone_pi.cli.main import cmd_measure

        exit_code = cmd_measure(args)

        assert exit_code == 0
        reloaded = load_config(path=config_path)
        assert reloaded.ftue.override_count_lifetime == 1
        # pass_count should NOT increment on override
        assert reloaded.ftue.pass_count_lifetime == 0

    def test_override_increments_override_count_max_attempts(
        self, tmp_path: Path, monkeypatch
    ):
        """override_count_lifetime increments when user overrides after max attempts."""
        from tap_tone_pi.core.user_config import (
            UserConfig,
            save_config,
            load_config,
        )
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
            TriggeredRule,
            Q001_CLIPPED,
        )

        # Setup: fresh config
        config_path = tmp_path / "config.json"
        cfg = UserConfig()
        cfg.ftue.override_count_lifetime = 0
        cfg.ftue.pass_count_lifetime = 0
        save_config(cfg, path=config_path)

        import tap_tone_pi.core.user_config as user_config_mod

        monkeypatch.setattr(user_config_mod, "CONFIG_FILE", config_path)

        # Create FAIL verdict
        fail_verdict = QualityVerdict(
            verdict=Verdict.FAIL,
            triggered_rules=[
                TriggeredRule(rule=Q001_CLIPPED, message="Clipping detected")
            ],
        )

        class _StubLoop:
            def __init__(self, **kwargs):
                self.store = MagicMock()
                self.store.get_attempt_dir.return_value = tmp_path / "attempt_001"

            def run_single(self, **kwargs):
                return _StubResult(
                    analysis=_StubAnalysis(),
                    verdict=fail_verdict,
                )

            def override_failed(self, point_id, reason):
                pass

        import tap_tone_pi.workflow as workflow_mod

        monkeypatch.setattr(workflow_mod, "OperatorLoop", _StubLoop)

        # Input: override reason at max attempts prompt
        monkeypatch.setattr("builtins.input", lambda _: "max attempts override")

        args = argparse.Namespace(
            device=0,
            sample_rate=48000,
            out=str(tmp_path / "session"),
            seconds=1.0,
            max_attempts=1,  # Single attempt = immediately at max
            point="point_001",
            agent=False,
            expert=False,
        )

        from tap_tone_pi.cli.main import cmd_measure

        exit_code = cmd_measure(args)

        assert exit_code == 0
        reloaded = load_config(path=config_path)
        assert reloaded.ftue.override_count_lifetime == 1
        # pass_count should NOT increment on override
        assert reloaded.ftue.pass_count_lifetime == 0
