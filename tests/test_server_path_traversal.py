"""Directory-traversal protection tests for the Phase 2 server endpoints.

Covers the ``_safe_directory`` guard used by the ``/grids`` and ``/sessions``
listing endpoints: a relative ``directory`` query param that escapes the
server working directory must be rejected, while a benign relative path is
allowed through to the normal (possibly empty) listing.
"""

import pytest

try:
    from fastapi.testclient import TestClient
    from tap_tone_pi.server.app import app, HAS_FASTAPI
except ImportError:  # pragma: no cover - exercised only without FastAPI
    HAS_FASTAPI = False
    app = None

pytestmark = pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")


@pytest.fixture
def client():
    return TestClient(app)


class TestDirectoryTraversalProtection:
    def test_grids_relative_traversal_rejected(self, client):
        resp = client.get("/grids", params={"directory": "../../../../etc"})
        assert resp.status_code == 400

    def test_sessions_relative_traversal_rejected(self, client):
        resp = client.get("/sessions", params={"directory": "../../../../etc"})
        assert resp.status_code == 400

    def test_safe_relative_directory_not_rejected(self, client):
        # A benign in-tree relative path must pass the guard (the endpoint then
        # returns a normal, possibly empty, list — never a 400 traversal error).
        resp = client.get("/grids", params={"directory": "config/grids"})
        assert resp.status_code != 400
