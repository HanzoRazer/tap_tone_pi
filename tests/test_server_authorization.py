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
from dataclasses import fields as _dataclass_fields
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient
    from tap_tone_pi.server.app import AuthorizationEvent, create_app, HAS_FASTAPI
except ImportError:  # pragma: no cover
    HAS_FASTAPI = False
    create_app = None
    AuthorizationEvent = None

pytestmark = pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")

AUTHZ_LOGGER = "tap_tone_pi.server.authz"
POLICY_VERSION = "filesystem-auth-v2"

# Substrings that would indicate a host path leaked into a diagnostic.
_LEAK_MARKERS = ("/tmp", "/home", "/Users", "/var", "C:\\", "\\Users")


def _authz_records(caplog):
    return [r for r in caplog.records if r.name == AUTHZ_LOGGER]


def _client_for_root(root) -> "TestClient":
    return TestClient(create_app(data_root=root))


# The record fields this patch controls == the AuthorizationEvent fields it
# injects via ``extra=asdict(event)``. Deriving the checked set from the
# dataclass (rather than from a LogRecord/logging-internals blocklist) means the
# test can neither drift from the dataclass (a new field is checked
# automatically) nor break on a Python/logging version change. The record's own
# ``pathname``/``filename`` (the emitting source file, app.py) are framework
# metadata — code location, not an authorization data path — and are not ours to
# inspect.
_AUTHZ_FIELD_NAMES = tuple(f.name for f in _dataclass_fields(AuthorizationEvent))


def _record_strings(record: logging.LogRecord):
    """The formatted message plus every AuthorizationEvent field on the record."""
    out = [record.getMessage()]
    for name in _AUTHZ_FIELD_NAMES:
        value = getattr(record, name, None)
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

    def test_status_exact_key_set(self, tmp_path):
        # Lock the public status surface: no extra fields may leak in silently.
        resp = _client_for_root(tmp_path).get("/server/status")
        assert set(resp.json().keys()) == {
            "policy_version",
            "configured",
            "root_digest",
            "started_at",
        }


class TestInvalidRootDigest:
    """INVALID_ROOT's root_digest must be identity-stable (canonical), so it
    correlates with /server/status rather than varying by input spelling."""

    def _invalid_root_digest(self, data_root, caplog):
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            with pytest.raises(ValueError):
                create_app(data_root=data_root)
        recs = [r for r in _authz_records(caplog) if r.reason_code == "INVALID_ROOT"]
        assert recs
        return recs[-1].root_digest

    def test_invalid_root_digest_is_spelling_invariant(self, tmp_path, caplog):
        base = tmp_path / "missing"
        d1 = self._invalid_root_digest(str(base), caplog)
        d2 = self._invalid_root_digest(str(tmp_path / "sub" / ".." / "missing"), caplog)
        assert d1 == d2

    def test_invalid_root_digest_is_canonical(self, tmp_path, caplog):
        import hashlib

        base = tmp_path / "missing"
        digest = self._invalid_root_digest(str(base), caplog)
        expected = hashlib.sha256(str(base.resolve()).encode("utf-8")).hexdigest()[:12]
        assert digest == expected

    def test_invalid_root_event_survives_without_recanonicalizing(
        self, tmp_path, caplog, monkeypatch
    ):
        # Unreachable-category guard: the startup error path must NOT
        # re-canonicalize. Re-canonicalizing would touch the filesystem again and
        # could raise OSError, masking the original ValueError AND silently
        # dropping the INVALID_ROOT event (an un-emitted event has no signature).
        # Make a *second* canonicalization fail; the event must still emit and the
        # original ValueError must still surface. Fails on the pre-fix code (which
        # recomputed the digest in the except block), passes on the restructure
        # that reuses the canonical root carried by _InvalidDataRootError.
        import importlib

        # NB: `import tap_tone_pi.server.app as x` resolves to the FastAPI app
        # instance (the package __init__ re-exports `app`), not the module;
        # import_module returns the real module so setattr patches the global.
        appmod = importlib.import_module("tap_tone_pi.server.app")

        real = appmod._canonical_root
        calls = {"n": 0}

        def counting(value):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError("a second canonicalization must not happen here")
            return real(value)

        monkeypatch.setattr(appmod, "_canonical_root", counting)
        with caplog.at_level(logging.DEBUG, logger=AUTHZ_LOGGER):
            with pytest.raises(ValueError):  # original failure preserved, not OSError
                appmod.create_app(data_root=str(tmp_path / "missing"))

        assert calls["n"] == 1  # canonicalized once; no error-path recompute
        assert any(r.reason_code == "INVALID_ROOT" for r in _authz_records(caplog))
