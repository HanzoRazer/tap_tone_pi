"""Tests for CLI agent wiring parser flags (PR 3).

The actual wiring tests (agent vs legacy output) are in test_cli_measure_agent_output.py
which uses hermetic monkeypatching that doesn't touch DSP or hardware.

This file only tests that the parser flags exist and default correctly.
"""

from tap_tone_pi.cli.main import build_parser


# =============================================================================
# Parser tests (ensure flags exist)
# =============================================================================


class TestParserFlags:
    """Test that --agent and --expert flags are present."""

    def test_record_has_agent_flag(self):
        parser = build_parser()
        # Parse a minimal record command
        args = parser.parse_args(["record", "--out", "/tmp/test", "--agent"])
        assert args.agent is True

    def test_record_has_expert_flag(self):
        parser = build_parser()
        args = parser.parse_args(["record", "--out", "/tmp/test", "--expert"])
        assert args.expert is True

    def test_measure_has_agent_flag(self):
        parser = build_parser()
        args = parser.parse_args(["measure", "--out", "/tmp/test", "--agent"])
        assert args.agent is True

    def test_measure_has_expert_flag(self):
        parser = build_parser()
        args = parser.parse_args(["measure", "--out", "/tmp/test", "--expert"])
        assert args.expert is True

    def test_agent_defaults_to_false(self):
        parser = build_parser()
        args = parser.parse_args(["record", "--out", "/tmp/test"])
        assert args.agent is False
        args = parser.parse_args(["measure", "--out", "/tmp/test"])
        assert args.agent is False

    def test_expert_defaults_to_false(self):
        parser = build_parser()
        args = parser.parse_args(["record", "--out", "/tmp/test"])
        assert args.expert is False
        args = parser.parse_args(["measure", "--out", "/tmp/test"])
        assert args.expert is False
