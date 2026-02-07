"""Tests for ttp export-pack CLI command.

Intentional stub: exporter behavior tested in scripts/export tests.
These CLI tests only verify path resolution, argv construction, guardrails,
and subprocess wiring without requiring audio hardware or running real exports.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

# Import the command handler and PROJECT_ROOT
from tap_tone_pi.cli.main import cmd_export_pack, PROJECT_ROOT


def _args(session: str, out: str, validate=False, strict=False, json=False):
    """Helper to create argparse.Namespace for export-pack tests."""
    return argparse.Namespace(
        session=session,
        out=out,
        validate=validate,
        strict=strict,
        json=json,
    )


def _get_argv_value(argv: list[str], flag: str) -> str:
    """Get the value following a flag in argv list."""
    assert flag in argv, f"Missing flag in argv: {flag}. argv={argv}"
    i = argv.index(flag)
    assert i + 1 < len(argv), f"Missing value after {flag}. argv={argv}"
    return argv[i + 1]


def _setup_fake_project_root(tmp_path: Path) -> Path:
    """Create a fake PROJECT_ROOT with required script stubs."""
    fake_root = tmp_path / "fake_repo"
    fake_root.mkdir()

    # Create script stubs that cmd_export_pack checks for existence
    export_script = fake_root / "scripts" / "export" / "viewer_pack_v1_export.py"
    export_script.parent.mkdir(parents=True)
    export_script.write_text("# stub")

    validate_script = fake_root / "scripts" / "viewer_pack_validate.py"
    validate_script.parent.mkdir(parents=True, exist_ok=True)
    validate_script.write_text("# stub")

    return fake_root


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

        # Exporter invoked with correct args (structural parsing, resolved paths)
        assert any("viewer_pack_v1_export.py" in str(x) for x in export_argv)
        assert Path(_get_argv_value(export_argv, "--session")).resolve() == session_dir.resolve()
        assert Path(_get_argv_value(export_argv, "--out")).resolve() == out_zip.resolve()

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
        """Relative session paths resolve against PROJECT_ROOT, not CWD.

        This test is hermetic: PROJECT_ROOT is patched to tmp_path.
        """
        import sys
        calls = []

        def fake_call(argv, cwd=None):
            calls.append((argv, cwd))
            return 0

        monkeypatch.setattr(subprocess, "call", fake_call)

        # Create a fake PROJECT_ROOT with script stubs
        fake_root = _setup_fake_project_root(tmp_path)

        # Patch PROJECT_ROOT in the module where it's used (via sys.modules)
        main_module = sys.modules["tap_tone_pi.cli.main"]
        monkeypatch.setattr(main_module, "PROJECT_ROOT", fake_root)

        # Create a repo-relative session under patched PROJECT_ROOT
        rel_session = Path("runs_phase2") / "session_0001"
        abs_session = fake_root / rel_session
        abs_session.mkdir(parents=True)
        (abs_session / "grid.json").write_text("{}")

        out_zip = tmp_path / "out.zip"

        rc = cmd_export_pack(_args(str(rel_session), str(out_zip), validate=False))

        assert rc == 0
        export_argv, export_cwd = calls[0]

        # Session path in argv should be resolved absolute path
        session_in_argv = _get_argv_value(export_argv, "--session")
        assert Path(session_in_argv).is_absolute()
        assert Path(session_in_argv).resolve() == abs_session.resolve()

        # Subprocess runs with patched PROJECT_ROOT as cwd
        assert Path(export_cwd).resolve() == fake_root.resolve()

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

        cmd_export_pack(_args(str(session_dir), str(tmp_path / "out.zip"), validate=False))

        _, cwd = calls[0]
        assert cwd == str(PROJECT_ROOT)


class TestExportPackReturnCodePropagation:
    """Test that subprocess return codes are correctly propagated."""

    def test_propagates_exporter_nonzero_return_code(self, monkeypatch, tmp_path):
        """Exporter exit code 2 is propagated as command exit code."""
        session_dir = tmp_path / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        def fake_call(argv, cwd=None):
            return 2  # Exporter fails with code 2

        monkeypatch.setattr(subprocess, "call", fake_call)

        rc = cmd_export_pack(_args(
            str(session_dir),
            str(tmp_path / "out.zip"),
            validate=True,
            strict=True,
            json=True,
        ))

        assert rc == 2

    def test_propagates_validator_nonzero_return_code(self, monkeypatch, tmp_path):
        """Validator exit code 3 is propagated after successful export."""
        session_dir = tmp_path / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        calls = {"n": 0}

        def fake_call(argv, cwd=None):
            calls["n"] += 1
            return 0 if calls["n"] == 1 else 3  # Export ok, validate fails with 3

        monkeypatch.setattr(subprocess, "call", fake_call)

        rc = cmd_export_pack(_args(
            str(session_dir),
            str(tmp_path / "out.zip"),
            validate=True,
            strict=True,
            json=True,
        ))

        assert rc == 3
        assert calls["n"] == 2  # Both were called


class TestExportPackMissingScripts:
    """Test that missing scripts produce clear error messages."""

    def test_missing_exporter_script_returns_error(self, monkeypatch, tmp_path, capsys):
        """Missing exporter script returns error with clear message."""
        import sys

        calls = []
        monkeypatch.setattr(subprocess, "call", lambda *a, **kw: calls.append(a) or 0)

        # Create fake PROJECT_ROOT WITHOUT script stubs
        fake_root = tmp_path / "empty_repo"
        fake_root.mkdir()

        main_module = sys.modules["tap_tone_pi.cli.main"]
        monkeypatch.setattr(main_module, "PROJECT_ROOT", fake_root)

        # Create valid session
        session_dir = fake_root / "runs_phase2" / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        rc = cmd_export_pack(_args(
            str(Path("runs_phase2") / "session_0001"),
            str(tmp_path / "out.zip"),
            validate=False,
        ))

        assert rc == 1
        assert len(calls) == 0  # subprocess never called
        captured = capsys.readouterr()
        assert "Exporter script not found" in captured.err

    def test_missing_validator_script_returns_error(self, monkeypatch, tmp_path, capsys):
        """Missing validator script returns error after successful export."""
        import sys

        call_count = [0]

        def fake_call(argv, cwd=None):
            call_count[0] += 1
            return 0

        monkeypatch.setattr(subprocess, "call", fake_call)

        # Create fake PROJECT_ROOT with ONLY exporter stub (no validator)
        fake_root = tmp_path / "partial_repo"
        fake_root.mkdir()

        export_script = fake_root / "scripts" / "export" / "viewer_pack_v1_export.py"
        export_script.parent.mkdir(parents=True)
        export_script.write_text("# stub")
        # NOTE: validator script intentionally NOT created

        main_module = sys.modules["tap_tone_pi.cli.main"]
        monkeypatch.setattr(main_module, "PROJECT_ROOT", fake_root)

        # Create valid session
        session_dir = fake_root / "runs_phase2" / "session_0001"
        session_dir.mkdir(parents=True)
        (session_dir / "grid.json").write_text("{}")

        rc = cmd_export_pack(_args(
            str(Path("runs_phase2") / "session_0001"),
            str(tmp_path / "out.zip"),
            validate=True,  # This triggers validator check
        ))

        assert rc == 1
        assert call_count[0] == 1  # Exporter called, then validator check failed
        captured = capsys.readouterr()
        assert "ZIP validator script not found" in captured.err
