"""Tests for ttp export-pack CLI command.

Intentional stub: exporter behavior tested in scripts/export tests.
These CLI tests only verify path resolution, argv construction, guardrails,
and subprocess wiring without requiring audio hardware or running real exports.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

# Import the command handler and PROJECT_ROOT
from tap_tone_pi.cli.main import cmd_export_pack, PROJECT_ROOT


class TestExportPackSubprocessWiring:
    """Test that export-pack correctly invokes exporter and validator scripts."""

    def test_invokes_exporter_and_validator(self, monkeypatch, tmp_path):
        """With --validate, both exporter and validator are invoked."""
        calls = []

        def fake_call(argv, cwd=None):
            calls.append((argv, cwd))
            return 0

        monkeypatch.setattr(subprocess, "call", fake_call)

        # Mimic a Phase 2 session folder
        session_dir = tmp_path / "runs_phase2" / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        out_zip = tmp_path / "out.zip"

        args = argparse.Namespace(
            session=str(session_dir),
            out=str(out_zip),
            validate=True,
            strict=True,
            json=True,
        )

        rc = cmd_export_pack(args)

        assert rc == 0
        assert len(calls) == 2

        export_argv, export_cwd = calls[0]
        validate_argv, validate_cwd = calls[1]

        # Exporter invoked with correct args
        assert any("viewer_pack_v1_export.py" in str(x) for x in export_argv)
        assert "--session" in export_argv
        assert str(session_dir) in export_argv
        assert "--out" in export_argv
        assert str(out_zip) in export_argv

        # Validator invoked with passthrough flags
        assert any("viewer_pack_validate.py" in str(x) for x in validate_argv)
        assert "--strict" in validate_argv
        assert "--json" in validate_argv

    def test_skips_validator_without_validate_flag(self, monkeypatch, tmp_path):
        """Without --validate, only exporter is invoked."""
        calls = []

        def fake_call(argv, cwd=None):
            calls.append((argv, cwd))
            return 0

        monkeypatch.setattr(subprocess, "call", fake_call)

        session_dir = tmp_path / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        out_zip = tmp_path / "out.zip"

        args = argparse.Namespace(
            session=str(session_dir),
            out=str(out_zip),
            validate=False,
            strict=False,
            json=False,
        )

        rc = cmd_export_pack(args)

        assert rc == 0
        assert len(calls) == 1  # Only exporter, no validator
        assert any("viewer_pack_v1_export.py" in str(x) for x in calls[0][0])

    def test_propagates_exporter_failure(self, monkeypatch, tmp_path):
        """Exporter failure (non-zero rc) is propagated, validator not called."""
        calls = []

        def fake_call(argv, cwd=None):
            calls.append((argv, cwd))
            # Exporter fails
            return 1

        monkeypatch.setattr(subprocess, "call", fake_call)

        session_dir = tmp_path / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        args = argparse.Namespace(
            session=str(session_dir),
            out=str(tmp_path / "out.zip"),
            validate=True,
            strict=False,
            json=False,
        )

        rc = cmd_export_pack(args)

        assert rc == 1
        assert len(calls) == 1  # Validator never called

    def test_propagates_validator_failure(self, monkeypatch, tmp_path):
        """Validator failure is propagated after successful export."""
        call_count = [0]

        def fake_call(argv, cwd=None):
            call_count[0] += 1
            # Exporter succeeds, validator fails
            if call_count[0] == 1:
                return 0  # exporter
            else:
                return 1  # validator

        monkeypatch.setattr(subprocess, "call", fake_call)

        session_dir = tmp_path / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        args = argparse.Namespace(
            session=str(session_dir),
            out=str(tmp_path / "out.zip"),
            validate=True,
            strict=False,
            json=False,
        )

        rc = cmd_export_pack(args)

        assert rc == 1
        assert call_count[0] == 2  # Both called


class TestExportPackGuardrails:
    """Test that export-pack validates inputs before invoking scripts."""

    def test_missing_session_returns_error(self, monkeypatch, tmp_path, capsys):
        """Non-existent session directory returns error without invoking exporter."""
        calls = []
        monkeypatch.setattr(subprocess, "call", lambda *a, **kw: calls.append(a) or 0)

        args = argparse.Namespace(
            session=str(tmp_path / "nonexistent_session"),
            out=str(tmp_path / "out.zip"),
            validate=False,
            strict=False,
            json=False,
        )

        rc = cmd_export_pack(args)

        assert rc == 1
        assert len(calls) == 0  # Exporter never invoked
        captured = capsys.readouterr()
        assert "Session not found" in captured.err

    def test_missing_grid_json_returns_error(self, monkeypatch, tmp_path, capsys):
        """Session without grid.json returns error (Phase 1 session guard)."""
        calls = []
        monkeypatch.setattr(subprocess, "call", lambda *a, **kw: calls.append(a) or 0)

        # Session exists but no grid.json
        session_dir = tmp_path / "session_0001"
        session_dir.mkdir(parents=True)

        args = argparse.Namespace(
            session=str(session_dir),
            out=str(tmp_path / "out.zip"),
            validate=False,
            strict=False,
            json=False,
        )

        rc = cmd_export_pack(args)

        assert rc == 1
        assert len(calls) == 0  # Exporter never invoked
        captured = capsys.readouterr()
        assert "Phase 2 session" in captured.err
        assert "grid.json" in captured.err


class TestExportPackPathResolution:
    """Test that session and output paths are resolved correctly."""

    def test_relative_session_resolved_against_project_root(self, monkeypatch, tmp_path):
        """Relative session paths resolve against PROJECT_ROOT, not CWD."""
        calls = []

        def fake_call(argv, cwd=None):
            calls.append((argv, cwd))
            return 0

        monkeypatch.setattr(subprocess, "call", fake_call)

        # Create session relative to PROJECT_ROOT
        session_name = "runs_phase2/test_session"
        session_dir = PROJECT_ROOT / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "grid.json").write_text("{}")

        try:
            args = argparse.Namespace(
                session=session_name,  # Relative path
                out=str(tmp_path / "out.zip"),
                validate=False,
                strict=False,
                json=False,
            )

            rc = cmd_export_pack(args)

            assert rc == 0
            export_argv = calls[0][0]
            # Session path in argv should be resolved absolute path
            session_in_argv = export_argv[export_argv.index("--session") + 1]
            assert Path(session_in_argv).is_absolute()
            assert session_name.replace("/", "\\") in session_in_argv or session_name in session_in_argv

        finally:
            # Cleanup: remove test session from PROJECT_ROOT
            import shutil
            if session_dir.exists():
                shutil.rmtree(session_dir)

    def test_cwd_used_for_subprocess(self, monkeypatch, tmp_path):
        """subprocess.call is invoked with PROJECT_ROOT as cwd."""
        calls = []

        def fake_call(argv, cwd=None):
            calls.append((argv, cwd))
            return 0

        monkeypatch.setattr(subprocess, "call", fake_call)

        session_dir = tmp_path / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        args = argparse.Namespace(
            session=str(session_dir),
            out=str(tmp_path / "out.zip"),
            validate=False,
            strict=False,
            json=False,
        )

        cmd_export_pack(args)

        _, cwd = calls[0]
        assert cwd == str(PROJECT_ROOT)
