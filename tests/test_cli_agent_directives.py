"""Tests for CLI advisory directive co-render (PR #3).

Validates:
1. Co-render prints both AgentMessage and directive block when files exist
2. --agent-directives without file does not change output
3. Parse failure is non-fatal
4. Color and verbose mode variants
"""

from __future__ import annotations

import json


from tap_tone_pi.agent.render import render_cli_shadow_record
from tap_tone_pi.agentic.spine.shadow_record import (
    load_latest_shadow_record,
    write_shadow_record,
)


# ---------------------------------------------------------------------------
# Minimal valid shadow record fixture
# ---------------------------------------------------------------------------


def _make_shadow_record(
    *,
    moment_id: str = "MOMENT_FINDING",
    confidence: float = 0.87,
    action: str = "REVIEW",
    summary: str = "Potential finding detected near 432 Hz",
    mode: str = "M0",
) -> dict:
    """Build a minimal valid spine_shadow_record v1 dict."""
    return {
        "schema_id": "spine_shadow_record",
        "schema_version": 1,
        "timestamp": "2026-02-09T12:00:00.000Z",
        "session_id": "test_session",
        "run_id": "attempt_001",
        "mode": mode,
        "moment": {
            "id": moment_id,
            "confidence": confidence,
            "trigger_event_count": 5,
        },
        "advisory": {
            "action": action,
            "summary": summary,
            "focus": {
                "target_type": "spectrum",
                "target_id": "peak@432Hz",
                "highlight_region": None,
            },
            "confidence": confidence,
        },
        "commands": {"count": 0},
        "error": None,
    }


def _make_none_record() -> dict:
    """Shadow record with no moment detected."""
    return {
        "schema_id": "spine_shadow_record",
        "schema_version": 1,
        "timestamp": "2026-02-09T12:00:00.000Z",
        "session_id": "test_session",
        "run_id": "attempt_001",
        "mode": "M0",
        "moment": {
            "id": "NONE",
            "confidence": 0.0,
            "trigger_event_count": 0,
        },
        "advisory": None,
        "commands": {"count": 0},
        "error": None,
    }


# =========================================================================
# Test 1 — render_cli_shadow_record produces expected output
# =========================================================================


class TestRenderShadowRecord:
    """render_cli_shadow_record formats the advisory block correctly."""

    def test_renders_header_and_summary(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec)

        assert output is not None
        assert "Advisory directive (M0)" in output
        assert "=" * len("Advisory directive (M0)") in output
        assert "Potential finding detected near 432 Hz" in output

    def test_renders_action(self):
        rec = _make_shadow_record(action="REVIEW")
        output = render_cli_shadow_record(rec)
        assert "  Action: REVIEW" in output

    def test_renders_focus(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec)
        assert "  Focus: spectrum:peak@432Hz" in output

    def test_renders_confidence(self):
        rec = _make_shadow_record(confidence=0.87)
        output = render_cli_shadow_record(rec)
        assert "  Confidence: 0.87" in output

    def test_returns_none_for_no_moment(self):
        rec = _make_none_record()
        output = render_cli_shadow_record(rec)
        assert output is None, (
            "Should not render when moment is NONE and advisory is None"
        )

    def test_returns_none_for_bad_input(self):
        assert render_cli_shadow_record(None) is None
        assert render_cli_shadow_record("not a dict") is None
        assert render_cli_shadow_record(42) is None


# =========================================================================
# Test 2 — color mode
# =========================================================================


class TestColorMode:
    """Color flag controls ANSI escape sequences."""

    def test_no_color_no_escapes(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec, color=False)
        assert "\x1b[" not in output
        assert "Advisory directive (M0)" in output

    def test_color_has_escapes(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec, color=True)
        assert "\x1b[" in output

    def test_color_header_uses_colorize(self):
        rec = _make_shadow_record(action="REVIEW")
        output = render_cli_shadow_record(rec, color=True)
        # REVIEW maps to warn severity → yellow (\x1b[33m)
        assert "\x1b[33m" in output


# =========================================================================
# Test 3 — verbose mode
# =========================================================================


class TestVerboseMode:
    """Verbose flag adds debug fields."""

    def test_verbose_shows_triggers(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec, verbose=True)
        assert "  Triggers: 5" in output

    def test_verbose_shows_moment_id(self):
        rec = _make_shadow_record(moment_id="MOMENT_FINDING")
        output = render_cli_shadow_record(rec, verbose=True)
        assert "  Moment: MOMENT_FINDING" in output

    def test_verbose_shows_commands_count(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec, verbose=True)
        assert "  Commands: 0" in output

    def test_verbose_shows_session_and_run(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec, verbose=True)
        assert "  Session: test_session" in output
        assert "  Run: attempt_001" in output

    def test_non_verbose_hides_debug(self):
        rec = _make_shadow_record()
        output = render_cli_shadow_record(rec, verbose=False)
        assert "  Triggers:" not in output
        assert "  Moment:" not in output
        assert "  Commands:" not in output


# =========================================================================
# Test 4 — loader integration
# =========================================================================


class TestLoaderIntegration:
    """load_latest_shadow_record reads files correctly."""

    def test_loads_from_latest_json(self, tmp_path):
        rec = _make_shadow_record()
        latest = tmp_path / "spine_shadow_latest.json"
        latest.write_text(json.dumps(rec), encoding="utf-8")

        loaded = load_latest_shadow_record(tmp_path)
        assert loaded is not None
        assert loaded["session_id"] == "test_session"

    def test_falls_back_to_jsonl(self, tmp_path):
        rec = _make_shadow_record()
        jsonl = tmp_path / "spine_shadow.jsonl"
        jsonl.write_text(json.dumps(rec) + "\n", encoding="utf-8")

        loaded = load_latest_shadow_record(tmp_path)
        assert loaded is not None
        assert loaded["mode"] == "M0"

    def test_returns_none_if_no_files(self, tmp_path):
        loaded = load_latest_shadow_record(tmp_path)
        assert loaded is None

    def test_invalid_json_returns_none(self, tmp_path):
        latest = tmp_path / "spine_shadow_latest.json"
        latest.write_text("{{{INVALID", encoding="utf-8")

        loaded = load_latest_shadow_record(tmp_path)
        assert loaded is None


# =========================================================================
# Test 5 — writer integration
# =========================================================================


class TestWriterIntegration:
    """write_shadow_record persists correctly."""

    def test_write_creates_both_files(self, tmp_path):
        write_shadow_record(
            session_dir=tmp_path,
            session_id="sess_001",
            run_id="attempt_001",
            mode="M0",
            moment_id="MOMENT_FINDING",
            moment_confidence=0.85,
            trigger_event_count=3,
            advisory_action="REVIEW",
            advisory_summary="Test finding",
            advisory_confidence=0.85,
            commands_count=0,
        )

        assert (tmp_path / "spine_shadow.jsonl").exists()
        assert (tmp_path / "spine_shadow_latest.json").exists()

    def test_write_none_moment(self, tmp_path):
        rec = write_shadow_record(
            session_dir=tmp_path,
            session_id="sess_001",
            run_id="attempt_001",
            mode="M0",
            moment_id="NONE",
            moment_confidence=0.0,
            trigger_event_count=0,
            commands_count=0,
        )

        assert rec["moment"]["id"] == "NONE"
        assert rec["advisory"] is None

    def test_write_with_error(self, tmp_path):
        rec = write_shadow_record(
            session_dir=tmp_path,
            session_id="sess_001",
            run_id="attempt_001",
            mode="M0",
            moment_id="NONE",
            moment_confidence=0.0,
            trigger_event_count=0,
            commands_count=0,
            error={
                "type": "ParseError",
                "message": "bad json",
                "stage": "load_events",
            },
        )

        assert rec["error"] is not None
        assert rec["error"]["type"] == "ParseError"


# =========================================================================
# Test 6 — error rendering
# =========================================================================


class TestErrorRendering:
    """Error records render a note line instead of advisory."""

    def test_error_renders_note(self):
        rec = _make_shadow_record()
        rec["error"] = {
            "type": "ParseError",
            "message": "bad json",
            "stage": "load_events",
        }
        rec["advisory"] = None
        rec["moment"]["id"] = "NONE"
        rec["moment"]["confidence"] = 0.0

        # Error record still has non-NONE error, so render should show note
        output = render_cli_shadow_record(rec)
        # With error + NONE moment + no advisory, it won't render (returns None)
        # But if we give it a non-NONE moment it will.
        rec["moment"]["id"] = "ERROR"
        output = render_cli_shadow_record(rec)
        assert output is not None
        assert "Note: ParseError: bad json" in output

    def test_error_verbose_shows_stage(self):
        rec = _make_shadow_record()
        rec["error"] = {
            "type": "PolicyError",
            "message": "something broke",
            "stage": "decide",
        }
        rec["moment"]["id"] = "ERROR"
        rec["advisory"] = None

        output = render_cli_shadow_record(rec, verbose=True)
        assert output is not None
        assert "  Stage: decide" in output


# =========================================================================
# Test 7 — _maybe_render_directive CLI helper
# =========================================================================


class TestMaybeRenderDirective:
    """The CLI helper reads shadow files and renders conditionally."""

    def test_no_flag_no_output(self, tmp_path, capsys):
        """Without --agent-directives, nothing prints."""
        import argparse
        from tap_tone_pi.cli.main import _maybe_render_directive

        args = argparse.Namespace(agent_directives=False, verbose_directives=False)
        _maybe_render_directive(args, tmp_path)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_flag_with_file_prints_block(self, tmp_path, capsys):
        """With --agent-directives and a shadow file, directive block prints."""
        import argparse
        from tap_tone_pi.cli.main import _maybe_render_directive

        rec = _make_shadow_record()
        (tmp_path / "spine_shadow_latest.json").write_text(
            json.dumps(rec),
            encoding="utf-8",
        )

        args = argparse.Namespace(
            agent_directives=True,
            verbose_directives=False,
            color=False,
        )
        _maybe_render_directive(args, tmp_path)

        captured = capsys.readouterr()
        assert "Advisory directive (M0)" in captured.out
        assert "Potential finding detected near 432 Hz" in captured.out

    def test_flag_without_file_silent(self, tmp_path, capsys):
        """With --agent-directives but no shadow files, output is empty."""
        import argparse
        from tap_tone_pi.cli.main import _maybe_render_directive

        args = argparse.Namespace(
            agent_directives=True,
            verbose_directives=False,
            color=False,
        )
        _maybe_render_directive(args, tmp_path)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_invalid_json_non_fatal(self, tmp_path, capsys):
        """Corrupted shadow file does not crash."""
        import argparse
        from tap_tone_pi.cli.main import _maybe_render_directive

        (tmp_path / "spine_shadow_latest.json").write_text(
            "{{{INVALID JSON",
            encoding="utf-8",
        )

        args = argparse.Namespace(
            agent_directives=True,
            verbose_directives=False,
            color=False,
        )
        # Must not raise
        _maybe_render_directive(args, tmp_path)

        captured = capsys.readouterr()
        # No crash, no output
        assert "Traceback" not in captured.out
