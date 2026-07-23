# INSTRUMENT CLASS: MEASUREMENT
"""Authorization observability tests for the Phase 2 server (DO-99).

DO-99 adds diagnostics only — it must not change any authorization *decision*.
These tests assert the structured authorization events emitted on the
``tap_tone_pi.server.authz`` logger and the ``/server/status`` endpoint, and that
no host filesystem path ever leaks into either.

Events are inspected via ``caplog`` LogRecord attributes, never by parsing a
formatted string.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient
    from tap_tone_pi.server.app import create_app, HAS_FASTAPI
except ImportError:  # pragma: no cover
    HAS_FASTAPI = False
    create_app = None

pytestmark = pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")

AUTHZ_LOGGER = "tap_tone_pi.server.authz"
POLICY_VERSION = "filesystem-auth-v2"

# Substrings that would indicate a host path leaked into a diagnostic.
_LEAK_MARKERS = ("/tmp", "/home", "/Users", "/var", "C:\\", "\\Users")


def _authz_records(caplog):
    return [r for r in caplog.records if r.name == AUTHZ_LOGGER]


def _client_for_root(root) -> "TestClient":
    return TestClient(create_app(data_root=root))


# The authorization-event fields we inject via ``extra=`` — the diagnostic
# content *we* control. (LogRecord's own ``pathname``/``filename`` always point
# at the emitting source file, app.py, and are framework metadata, not an
# authorization data-path leak; they are intentionally not inspected.)
_AUTHZ_FIELDS = (
    "timestamp",
    "endpoint",
    "input_role",
    "request_path_type",
    "authorization_result",
    "policy_version",
    "root_digest",
    "reason_code",
    "error_type",
)


def _record_strings(record: logging.LogRecord):
    """The message plus every authz field value we set — what we could leak."""
    out = [record.getMessage()]
    for field in _AUTHZ_FIELDS:
        value = getattr(record, field, None)
        if isinstance(value, str):
            out.append(value)
    return out


class TestAuthorizationEvents:
    def test_allowed_request_emits_allowed_event(self, tmp_path, caplog):
        served = tmp_path / "served"
        served.mkdir()
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            resp = _client_for_root(tmp_path).get(
                "/grids", params={"directory": str(served)}
            )
        assert resp.status_code != 400
        recs = _authz_records(caplog)
        assert any(
            r.authorization_result == "allowed"
            and r.input_role == "directory"
            and r.request_path_type == "absolute"
            and "grids" in r.endpoint
            for r in recs
        )

    def test_outside_root_emits_outside_root_reason(self, tmp_path, caplog):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            resp = _client_for_root(root).get(
                "/grids", params={"directory": str(outside)}
            )
        assert resp.status_code == 400
        recs = _authz_records(caplog)
        assert any(
            r.authorization_result == "rejected" and r.reason_code == "OUTSIDE_ROOT"
            for r in recs
        )
        assert any(r.levelno == logging.WARNING for r in recs)

    def test_relative_traversal_is_outside_root(self, tmp_path, caplog):
        root = tmp_path / "root"
        root.mkdir()
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            _client_for_root(root).get("/grids", params={"directory": "../outside"})
        assert any(r.reason_code == "OUTSIDE_ROOT" for r in _authz_records(caplog))

    def test_symlink_escape_emits_symlink_escape_reason(self, tmp_path, caplog):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        link = root / "link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted in this environment")
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            resp = _client_for_root(root).get("/grids", params={"directory": "link"})
        assert resp.status_code == 400
        recs = _authz_records(caplog)
        assert any(
            r.authorization_result == "rejected" and r.reason_code == "SYMLINK_ESCAPE"
            for r in recs
        )

    def test_invalid_root_emits_invalid_root_and_still_raises(self, tmp_path, caplog):
        missing = tmp_path / "does_not_exist"
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            with pytest.raises(ValueError):
                create_app(data_root=missing)
        recs = _authz_records(caplog)
        assert any(
            r.reason_code == "INVALID_ROOT" and r.levelno == logging.ERROR for r in recs
        )

    def test_resolution_failure_emits_and_reraises(self, tmp_path, caplog, monkeypatch):
        root = tmp_path / "root"
        root.mkdir()
        client = _client_for_root(root)

        real_resolve = Path.resolve

        def boom(self, *a, **k):
            # Only blow up on the request path resolution, not the root's.
            if "boomdir" in str(self):
                raise OSError("simulated resolution failure")
            return real_resolve(self, *a, **k)

        monkeypatch.setattr(Path, "resolve", boom)
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            # TestClient re-raises server exceptions by default; the original
            # exception path must be preserved (no conversion to 400).
            with pytest.raises(OSError):
                client.get("/grids", params={"directory": "boomdir"})
        recs = _authz_records(caplog)
        assert any(
            r.reason_code == "PATH_RESOLUTION_FAILURE"
            and r.error_type == "OSError"
            and r.levelno == logging.ERROR
            for r in recs
        )

    def test_export_emits_one_event_per_authorization(self, tmp_path, caplog):
        root = tmp_path / "root"
        (root / "session_x").mkdir(parents=True)
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            _client_for_root(root).get("/export/session_x", params={"directory": "."})
        roles = {r.input_role for r in _authz_records(caplog) if "export" in r.endpoint}
        assert {"directory", "session"} <= roles


class TestNoPathLeakage:
    def test_events_never_contain_host_paths(self, tmp_path, caplog):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            client = _client_for_root(root)
            client.get("/grids", params={"directory": str(root / "ok")})  # allowed
            client.get("/grids", params={"directory": str(outside)})  # rejected
        for record in _authz_records(caplog):
            for text in _record_strings(record):
                assert str(tmp_path) not in text, text
                for marker in _LEAK_MARKERS:
                    assert marker not in text, (marker, text)


class TestStatusEndpoint:
    def test_status_returns_policy_metadata(self, tmp_path):
        served = tmp_path / "served"
        served.mkdir()
        resp = _client_for_root(served).get("/server/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["policy_version"] == POLICY_VERSION
        assert body["configured"] is True
        assert isinstance(body["root_digest"], str) and len(body["root_digest"]) == 12
        assert isinstance(body["started_at"], str) and body["started_at"]

    def test_status_configured_false_when_defaulted_to_cwd(self, monkeypatch):
        monkeypatch.delenv("TTP_SERVER_DATA_ROOT", raising=False)
        resp = TestClient(create_app()).get("/server/status")
        assert resp.json()["configured"] is False

    def test_status_never_reveals_host_paths(self, tmp_path):
        resp = _client_for_root(tmp_path).get("/server/status")
        text = resp.text
        assert str(tmp_path) not in text
        for marker in _LEAK_MARKERS:
            assert marker not in text
