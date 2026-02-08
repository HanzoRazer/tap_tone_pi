"""Tests for FTUE state persistence and salvage parsing.

PR4 hardening: ensures FTUE never bricks core config, bounded lists, PASS-only increments.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from tap_tone_pi.core.user_config import (
    FtueState,
    UserConfig,
    load_config,
    save_config,
    update_ftue_from_verdict,
)


class TestFtueStateFromDict:
    """FtueState.from_dict() defensively handles garbage."""

    def test_empty_dict_returns_defaults(self):
        ftue = FtueState.from_dict({})
        assert ftue.pass_count_lifetime == 0
        assert ftue.session_count_lifetime == 0
        assert ftue.seen_rule_ids == []
        assert ftue.last_seen_policy_version is None

    def test_malformed_pass_count_defaults_to_zero(self):
        ftue = FtueState.from_dict({"pass_count_lifetime": "garbage"})
        assert ftue.pass_count_lifetime == 0

    def test_malformed_session_count_defaults_to_zero(self):
        ftue = FtueState.from_dict({"session_count_lifetime": [1, 2, 3]})
        assert ftue.session_count_lifetime == 0

    def test_malformed_seen_rule_ids_defaults_to_empty(self):
        ftue = FtueState.from_dict({"seen_rule_ids": "not a list"})
        assert ftue.seen_rule_ids == []

    def test_mixed_seen_rule_ids_defaults_to_empty(self):
        """If any element is not a string, discard entire list."""
        ftue = FtueState.from_dict({"seen_rule_ids": ["ok", 123, "also_ok"]})
        assert ftue.seen_rule_ids == []

    def test_malformed_policy_version_defaults_to_none(self):
        ftue = FtueState.from_dict({"last_seen_policy_version": 42})
        assert ftue.last_seen_policy_version is None

    def test_valid_dict_parses_correctly(self):
        ftue = FtueState.from_dict({
            "pass_count_lifetime": 5,
            "session_count_lifetime": 10,
            "seen_rule_ids": ["rule_a", "rule_b"],
            "last_seen_policy_version": "1.0.0",
            "updated_at": "2026-01-15T12:00:00Z",
        })
        assert ftue.pass_count_lifetime == 5
        assert ftue.session_count_lifetime == 10
        assert ftue.seen_rule_ids == ["rule_a", "rule_b"]
        assert ftue.last_seen_policy_version == "1.0.0"
        assert ftue.updated_at == "2026-01-15T12:00:00Z"


class TestFtueStateBoundedList:
    """seen_rule_ids is capped to SEEN_RULES_CAP."""

    def test_dedupe_preserves_order(self):
        ftue = FtueState.from_dict({
            "seen_rule_ids": ["a", "b", "a", "c", "b", "d"]
        })
        assert ftue.seen_rule_ids == ["a", "b", "c", "d"]

    def test_bounded_to_cap(self):
        # 100 unique rule IDs, should be capped to 64
        big_list = [f"rule_{i:04d}" for i in range(100)]
        ftue = FtueState.from_dict({"seen_rule_ids": big_list})
        assert len(ftue.seen_rule_ids) == FtueState.SEEN_RULES_CAP


class TestUserConfigFtueRoundtrip:
    """UserConfig serialization includes ftue and survives corrupt ftue."""

    def test_ftue_in_to_dict(self):
        cfg = UserConfig()
        cfg.ftue.pass_count_lifetime = 7
        d = cfg.to_dict()
        assert "ftue" in d
        assert d["ftue"]["pass_count_lifetime"] == 7

    def test_ftue_in_from_dict(self):
        d = {
            "version": "1.1.0",
            "ftue": {"pass_count_lifetime": 12, "session_count_lifetime": 3}
        }
        cfg = UserConfig.from_dict(d)
        assert cfg.ftue.pass_count_lifetime == 12
        assert cfg.ftue.session_count_lifetime == 3

    def test_corrupt_ftue_does_not_brick_config(self):
        """Corrupt ftue block must not prevent loading core config."""
        d = {
            "version": "1.1.0",
            "audio_device": None,
            "default_capture_seconds": 3.0,
            "default_output_dir": "./recordings",
            "ftue": "completely garbage string",  # malformed
        }
        cfg = UserConfig.from_dict(d)
        # Core config fields are preserved
        assert cfg.version == "1.1.0"
        assert cfg.default_capture_seconds == 3.0
        assert cfg.default_output_dir == "./recordings"
        # ftue is defaulted, not bricked
        assert cfg.ftue.pass_count_lifetime == 0


class TestSaveLoadFtue:
    """Integration test: save and load with FTUE state."""

    def test_roundtrip_file(self, tmp_path: Path):
        cfg = UserConfig()
        cfg.ftue.pass_count_lifetime = 99
        cfg.ftue.session_count_lifetime = 42
        cfg.ftue.seen_rule_ids = ["rule_x", "rule_y"]
        cfg.ftue.last_seen_policy_version = "2.0.0"

        config_path = tmp_path / "config.json"
        save_config(cfg, path=config_path)

        loaded = load_config(path=config_path)
        assert loaded is not None
        assert loaded.ftue.pass_count_lifetime == 99
        assert loaded.ftue.session_count_lifetime == 42
        assert loaded.ftue.seen_rule_ids == ["rule_x", "rule_y"]
        assert loaded.ftue.last_seen_policy_version == "2.0.0"

    def test_atomic_write_no_temp_residue(self, tmp_path: Path):
        """Atomic write should not leave .tmp file behind."""
        cfg = UserConfig()
        config_path = tmp_path / "config.json"
        save_config(cfg, path=config_path)

        tmp_file = config_path.with_suffix(".json.tmp")
        assert not tmp_file.exists()
        assert config_path.exists()


class TestUpdateFtueFromVerdict:
    """update_ftue_from_verdict() increments correctly."""

    def test_increment_session_once(self):
        ftue = FtueState()
        assert ftue.session_count_lifetime == 0
        ftue = update_ftue_from_verdict(ftue, verdict=None, increment_session=True)
        assert ftue.session_count_lifetime == 1
        ftue = update_ftue_from_verdict(ftue, verdict=None, increment_session=False)
        assert ftue.session_count_lifetime == 1  # not incremented again

    def test_pass_increments_pass_count(self):
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
            TriggeredRule,
            QualityRule,
            Severity,
        )

        rule = QualityRule(
            rule_id="test_rule_pass",
            severity=Severity.SOFT,
            description="Test rule",
            message="ok",
        )
        verdict = QualityVerdict(
            verdict=Verdict.PASS,
            triggered_rules=[TriggeredRule(rule=rule, message="ok")],
        )

        ftue = FtueState()
        ftue = update_ftue_from_verdict(ftue, verdict=verdict)
        assert ftue.pass_count_lifetime == 1
        assert "test_rule_pass" in ftue.seen_rule_ids

    def test_warn_does_not_increment_pass_count(self):
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
            TriggeredRule,
            QualityRule,
            Severity,
        )

        rule = QualityRule(
            rule_id="test_rule_warn",
            severity=Severity.SOFT,
            description="Test rule",
            message="warning",
        )
        verdict = QualityVerdict(
            verdict=Verdict.WARN,
            triggered_rules=[TriggeredRule(rule=rule, message="warning")],
        )

        ftue = FtueState()
        ftue = update_ftue_from_verdict(ftue, verdict=verdict)
        assert ftue.pass_count_lifetime == 0  # WARN does NOT increment
        assert "test_rule_warn" in ftue.seen_rule_ids

    def test_fail_does_not_increment_pass_count(self):
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
            TriggeredRule,
            QualityRule,
            Severity,
        )

        rule = QualityRule(
            rule_id="test_rule_fail",
            severity=Severity.HARD,
            description="Test rule",
            message="failed",
        )
        verdict = QualityVerdict(
            verdict=Verdict.FAIL,
            triggered_rules=[TriggeredRule(rule=rule, message="failed")],
        )

        ftue = FtueState()
        ftue = update_ftue_from_verdict(ftue, verdict=verdict)
        assert ftue.pass_count_lifetime == 0  # FAIL does NOT increment
        assert "test_rule_fail" in ftue.seen_rule_ids

    def test_policy_version_recorded(self):
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
        )
        # Need a non-None verdict to record policy version
        verdict = QualityVerdict(verdict=Verdict.PASS)
        ftue = FtueState()
        ftue = update_ftue_from_verdict(
            ftue, verdict=verdict, policy_version="3.0.0"
        )
        assert ftue.last_seen_policy_version == "3.0.0"

    def test_seen_rule_ids_bounded_in_update(self):
        from tap_tone_pi.core.quality_policy import (
            QualityVerdict,
            Verdict,
            TriggeredRule,
            QualityRule,
            Severity,
        )

        # Pre-populate with 60 rules
        ftue = FtueState()
        ftue.seen_rule_ids = [f"old_{i:03d}" for i in range(60)]

        # Create verdict with 10 new rules
        rules = [
            QualityRule(
                rule_id=f"new_{i:03d}",
                severity=Severity.SOFT,
                description="New rule",
                message="ok",
            )
            for i in range(10)
        ]
        verdict = QualityVerdict(
            verdict=Verdict.PASS,
            triggered_rules=[TriggeredRule(rule=r, message="ok") for r in rules],
        )

        ftue = update_ftue_from_verdict(ftue, verdict=verdict)
        # Should be capped at 64
        assert len(ftue.seen_rule_ids) == FtueState.SEEN_RULES_CAP
        # Old rules preserved first (insertion order)
        assert ftue.seen_rule_ids[0] == "old_000"
