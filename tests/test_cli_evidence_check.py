"""PR8 CLI-level tests for ``ttp evidence-check``.

Tests exercise ``cmd_evidence_check`` directly (fast + hermetic).
``PROJECT_ROOT`` is monkeypatched so repo-relative path resolution
is deterministic and isolated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

# We test the CLI handler directly (fast + hermetic).
# The cli __init__ re-exports main() which shadows the module name,
# so we grab the module from sys.modules after import.
import importlib
import sys

importlib.import_module("tap_tone_pi.cli.main")
cli_main_mod = sys.modules["tap_tone_pi.cli.main"]


def _args(
    *,
    session: str,
    strict: bool = False,
    fail_on_warn: bool = False,
    json_out: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        session=session,
        strict=strict,
        fail_on_warn=fail_on_warn,
        json=json_out,
    )


def _write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _write_bytes(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def _make_attempt_dir(base: Path, rel_attempt_dir: Path) -> Path:
    d = base / rel_attempt_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_wav_stub(p: Path) -> None:
    """Write a minimal WAV stub."""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"RIFF" + b"\x00" * 100)


def _write_required_attempt_artifacts(attempt_dir: Path) -> None:
    """Write all four required artifacts for a valid attempt.

    Required: audio.wav, analysis.json, capture_meta.json, quality_check.json.
    """
    _write_wav_stub(attempt_dir / "audio.wav")
    _write_text(
        attempt_dir / "analysis.json",
        json.dumps(
            {
                "peaks": [{"freq_hz": 192.3, "magnitude": 0.88}],
            }
        ),
    )
    _write_text(
        attempt_dir / "capture_meta.json",
        json.dumps(
            {
                "sample_rate_hz": 48000,
                "device_id": "test_mic",
            }
        ),
    )
    _write_text(
        attempt_dir / "quality_check.json",
        json.dumps(
            {
                "verdict": "pass",
                "triggered_rules": [],
            }
        ),
    )


@pytest.fixture()
def fake_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Patch PROJECT_ROOT so repo-relative session paths resolve hermetically."""
    root = tmp_path / "fake_repo"
    root.mkdir(parents=True)
    monkeypatch.setattr(cli_main_mod, "PROJECT_ROOT", root)
    return root


class TestCmdEvidenceCheck:
    """CLI handler: cmd_evidence_check."""

    def test_nested_layout_ok_returns_zero(
        self,
        fake_repo_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Nested layout: session/point_001/attempt_001/{required files}."""
        session_dir = fake_repo_root / "out" / "session_0001"
        attempt_dir = _make_attempt_dir(
            session_dir,
            Path("point_001") / "attempt_001",
        )
        _write_required_attempt_artifacts(attempt_dir)

        args = _args(session=str(Path("out/session_0001")))
        rc = cli_main_mod.cmd_evidence_check(args)

        out = capsys.readouterr().out
        assert rc == 0
        assert "Evidence check:" in out
        assert "FAIL=0" in out

    def test_flat_layout_ok_returns_zero(
        self,
        fake_repo_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Flat layout: session/attempt_001/{required files}."""
        session_dir = fake_repo_root / "out" / "session_0002"
        attempt_dir = _make_attempt_dir(session_dir, Path("attempt_001"))
        _write_required_attempt_artifacts(attempt_dir)

        args = _args(session=str(Path("out/session_0002")))
        rc = cli_main_mod.cmd_evidence_check(args)

        out = capsys.readouterr().out
        assert rc == 0
        assert "FAIL=0" in out

    def test_missing_required_file_returns_one_and_reports_e001(
        self,
        fake_repo_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        session_dir = fake_repo_root / "out" / "session_missing"
        attempt_dir = _make_attempt_dir(session_dir, Path("attempt_001"))

        # Write everything except analysis.json
        _write_wav_stub(attempt_dir / "audio.wav")
        _write_text(
            attempt_dir / "capture_meta.json",
            json.dumps({"sample_rate_hz": 48000, "device_id": "test_mic"}),
        )
        _write_text(
            attempt_dir / "quality_check.json",
            json.dumps({"verdict": "pass", "triggered_rules": []}),
        )

        args = _args(session=str(Path("out/session_missing")))
        rc = cli_main_mod.cmd_evidence_check(args)

        out = capsys.readouterr().out
        assert rc == 1
        assert "E001" in out
        assert "analysis.json" in out

    def test_json_parse_error_returns_two_and_reports_e101(
        self,
        fake_repo_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        session_dir = fake_repo_root / "out" / "session_bad_json"
        attempt_dir = _make_attempt_dir(session_dir, Path("attempt_001"))
        _write_required_attempt_artifacts(attempt_dir)

        # Corrupt analysis.json
        _write_text(attempt_dir / "analysis.json", "{this is not json")

        args = _args(session=str(Path("out/session_bad_json")))
        rc = cli_main_mod.cmd_evidence_check(args)

        out = capsys.readouterr().out
        assert rc == 2
        assert "E101" in out
        assert "analysis.json" in out

    def test_json_root_not_dict_returns_two_and_reports_e102(
        self,
        fake_repo_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        session_dir = fake_repo_root / "out" / "session_list"
        attempt_dir = _make_attempt_dir(session_dir, Path("attempt_001"))
        _write_required_attempt_artifacts(attempt_dir)

        # JSON root is list, not dict
        _write_text(attempt_dir / "analysis.json", "[1, 2, 3]")

        args = _args(session=str(Path("out/session_list")))
        rc = cli_main_mod.cmd_evidence_check(args)

        out = capsys.readouterr().out
        assert rc == 2
        assert "E102" in out

    def test_discovery_counts_nested_and_flat_deterministically_json_output(
        self,
        fake_repo_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Mixed nested + flat layout; JSON output; attempts_scanned == 2."""
        session_dir = fake_repo_root / "out" / "session_mixed"

        flat_attempt = _make_attempt_dir(session_dir, Path("attempt_001"))
        nested_attempt = _make_attempt_dir(
            session_dir,
            Path("point_001") / "attempt_002",
        )

        _write_required_attempt_artifacts(flat_attempt)
        _write_required_attempt_artifacts(nested_attempt)

        args = _args(
            session=str(Path("out/session_mixed")),
            json_out=True,
        )
        rc = cli_main_mod.cmd_evidence_check(args)
        assert rc == 0

        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["tool"] == "evidence-check"
        assert payload["summary"]["attempts_scanned"] == 2
        assert payload["summary"]["fail_count"] == 0
        assert payload["exit_code"] == 0

    def test_nonexistent_session_returns_one_stderr(
        self,
        fake_repo_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Session directory not found → exit 1, stderr message."""
        args = _args(session=str(Path("out/does_not_exist")))
        rc = cli_main_mod.cmd_evidence_check(args)

        err = capsys.readouterr().err
        assert rc == 1
        assert "not found" in err.lower() or "Session not found" in err

    def test_absolute_path_bypasses_project_root(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Absolute session path is used directly, no PROJECT_ROOT join."""
        session_dir = tmp_path / "abs_session"
        attempt_dir = _make_attempt_dir(session_dir, Path("attempt_001"))
        _write_required_attempt_artifacts(attempt_dir)

        args = _args(session=str(session_dir))
        rc = cli_main_mod.cmd_evidence_check(args)

        out = capsys.readouterr().out
        assert rc == 0
        assert "FAIL=0" in out
