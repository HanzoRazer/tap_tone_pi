"""Directory-traversal protection tests for the Phase 2 server endpoints.

Covers the ``_safe_directory`` guard used by the ``/grids`` and ``/sessions``
listing endpoints. Every caller-supplied ``directory`` — relative *or* absolute
— must resolve beneath the working-directory anchor; anything that escapes it
(``..`` traversal, sibling-prefix, an absolute path outside the anchor, or a
symlink resolving outside it) is rejected with HTTP 400, while a benign in-root
path is allowed through to the normal (possibly empty) listing.
"""

from pathlib import Path

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

    def test_sibling_prefix_directory_rejected(self, client):
        # A relative path that resolves to a *sibling* of the working directory
        # sharing its name prefix (CWD ".../repo" -> ".../repo_evil_sibling")
        # must be rejected. A naive str-prefix containment check would wrongly
        # accept it because the sibling's path string starts with the CWD string;
        # a true path-component check rejects it. Regresses the prefix-bypass bug.
        sibling = f"../{Path.cwd().name}_evil_sibling"
        resp = client.get("/grids", params={"directory": sibling})
        assert resp.status_code == 400

    # --- absolute-path containment (unified policy: same rule as relative) ---

    @pytest.mark.parametrize("endpoint", ["/grids", "/sessions"])
    def test_absolute_path_outside_root_rejected(self, client, endpoint):
        # An absolute path whose target is outside the working-directory anchor
        # must be rejected exactly like relative traversal. Constructed from the
        # anchor's parent so it is deterministic and platform-neutral (no /etc).
        cwd = Path.cwd().resolve()
        outside = str(cwd.parent / "ttp_outside_root_dir")
        resp = client.get(endpoint, params={"directory": outside})
        assert resp.status_code == 400

    @pytest.mark.parametrize("endpoint", ["/grids", "/sessions"])
    def test_absolute_path_inside_root_accepted(self, client, endpoint):
        # An absolute path that resolves beneath the anchor is accepted; the
        # endpoint then returns its normal (possibly empty) listing, never 400.
        cwd = Path.cwd().resolve()
        inside = str(cwd / "config" / "grids")
        resp = client.get(endpoint, params={"directory": inside})
        assert resp.status_code != 400

    @pytest.mark.parametrize("endpoint", ["/grids", "/sessions"])
    def test_symlink_escape_rejected(self, client, endpoint, tmp_path):
        # A path lexically beneath the anchor but symlinked to a target *outside*
        # it must be rejected. Containment is checked after resolution, so the
        # symlink cannot smuggle access out of the root. The link must live under
        # the anchor (the app's fixed cwd), so it is created and cleaned up there.
        cwd = Path.cwd().resolve()
        outside = tmp_path.resolve()
        if outside.is_relative_to(cwd):  # pragma: no cover - env-dependent
            pytest.skip("temp dir is inside the working directory; cannot test escape")

        link = cwd / "_ttp_escape_link_test"
        try:
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                pytest.skip("symlink creation not permitted in this environment")
            resp = client.get(endpoint, params={"directory": link.name})
            assert resp.status_code == 400
        finally:
            if link.is_symlink() or link.exists():
                link.unlink()
