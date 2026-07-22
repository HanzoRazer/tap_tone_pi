"""Directory-traversal protection tests for the Phase 2 server endpoints.

Two layers are covered:

* ``TestDirectoryTraversalProtection`` — the relative-traversal + sibling-prefix
  guarantees established in PR #10, evaluated against the default cwd-anchored
  application.
* ``TestDataRootAuthorization`` / ``TestDataRootPrecedence`` (DO-98) — the
  configurable-root policy: every caller-supplied ``directory``, relative *or*
  absolute, must resolve beneath the configured ``data_root``; escapes (``..``,
  sibling-prefix, absolute-outside-root, symlink-out) return HTTP 400, while
  paths beneath the root are accepted. Authorization precedence is
  ``create_app(data_root=...)`` > ``TTP_SERVER_DATA_ROOT`` > ``Path.cwd()``.
"""

from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient
    from tap_tone_pi.server.app import app, create_app, HAS_FASTAPI
except ImportError:  # pragma: no cover - exercised only without FastAPI
    HAS_FASTAPI = False
    app = None
    create_app = None

pytestmark = pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def client_for_root():
    """Build a TestClient whose app authorizes exactly the given data root.

    Each test declares its own authorization root explicitly, so the security
    boundary is visible in the test and endpoint tests don't share a hidden
    fixture layout.
    """

    def build(root) -> "TestClient":
        return TestClient(create_app(data_root=root))

    return build


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


# --- DO-98: configurable data-root authorization -----------------------------

ENDPOINTS = ["/grids", "/sessions"]


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestDataRootAuthorization:
    """Every caller-supplied directory must resolve beneath the configured root.

    The root is set explicitly per test via ``client_for_root`` so the policy is
    exercised through the real endpoint wiring, independent of ``Path.cwd()``.
    """

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_absolute_path_beneath_root_accepted(
        self, client_for_root, endpoint, tmp_path
    ):
        served = tmp_path / "served"
        served.mkdir()
        client = client_for_root(tmp_path)
        resp = client.get(endpoint, params={"directory": str(served)})
        assert resp.status_code != 400

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_absolute_path_outside_root_rejected(
        self, client_for_root, endpoint, tmp_path
    ):
        # Principal DO-98 assertion: an absolute path outside the configured root
        # is rejected. Under PR #10 behavior (absolute paths accepted as-is) this
        # would be a 200 -> this test is the evidence DO-98 closes the gap.
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        client = client_for_root(root)
        resp = client.get(endpoint, params={"directory": str(outside)})
        assert resp.status_code == 400

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_relative_traversal_outside_root_rejected(
        self, client_for_root, endpoint, tmp_path
    ):
        root = tmp_path / "root"
        root.mkdir()
        client = client_for_root(root)
        resp = client.get(endpoint, params={"directory": "../outside"})
        assert resp.status_code == 400

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_sibling_prefix_outside_root_rejected(
        self, client_for_root, endpoint, tmp_path
    ):
        root = tmp_path / "root"
        root.mkdir()
        client = client_for_root(root)
        resp = client.get(endpoint, params={"directory": f"../{root.name}_evil"})
        assert resp.status_code == 400

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_normalized_in_root_path_accepted(
        self, client_for_root, endpoint, tmp_path
    ):
        # `..` alone is not the violation; escaping the root is. A path that
        # normalizes back inside the root must be accepted.
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        client = client_for_root(tmp_path)
        resp = client.get(endpoint, params={"directory": "a/../b"})
        assert resp.status_code != 400

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_symlink_escape_rejected(self, client_for_root, endpoint, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        link = root / "link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted in this environment")
        client = client_for_root(root)
        resp = client.get(endpoint, params={"directory": "link"})
        assert resp.status_code == 400

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_symlink_inside_root_accepted(self, client_for_root, endpoint, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = root / "real"
        target.mkdir()
        link = root / "current"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted in this environment")
        client = client_for_root(root)
        resp = client.get(endpoint, params={"directory": "current"})
        assert resp.status_code != 400

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_authorization_independent_of_cwd(
        self, client_for_root, endpoint, tmp_path
    ):
        # Root differs from cwd: an in-root relative path is accepted, while an
        # absolute path under cwd (but outside the configured root) is rejected.
        # Proves authorization follows configuration, not the launch directory.
        root = tmp_path / "root"
        (root / "runs").mkdir(parents=True)
        client = client_for_root(root)
        assert client.get(endpoint, params={"directory": "runs"}).status_code != 400
        under_cwd = str(Path.cwd() / "config")
        assert client.get(endpoint, params={"directory": under_cwd}).status_code == 400

    @pytest.mark.parametrize("endpoint", ["/sessions/some_id", "/export/some_id"])
    def test_adjacent_read_endpoints_reject_outside_root(
        self, client_for_root, endpoint, tmp_path
    ):
        # The session-detail and export read endpoints share the same data-root
        # boundary as the list endpoints — their `directory` read param routes
        # through the same guard — so an absolute directory outside the root is
        # rejected (HTTP 400), not silently read. Regresses the bypass where only
        # /grids and /sessions were confined.
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        client = client_for_root(root)
        resp = client.get(endpoint, params={"directory": str(outside)})
        assert resp.status_code == 400


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestDataRootPrecedence:
    """Root resolution precedence: explicit arg > env var > Path.cwd()."""

    def test_explicit_arg_overrides_env(self, tmp_path, monkeypatch):
        env_root = tmp_path / "env"
        arg_root = tmp_path / "arg"
        env_root.mkdir()
        arg_root.mkdir()
        monkeypatch.setenv("TTP_SERVER_DATA_ROOT", str(env_root))
        app_ = create_app(data_root=arg_root)
        assert app_.state.data_root == arg_root.resolve()

    def test_env_used_when_arg_omitted(self, tmp_path, monkeypatch):
        env_root = tmp_path / "env"
        env_root.mkdir()
        monkeypatch.setenv("TTP_SERVER_DATA_ROOT", str(env_root))
        app_ = create_app()
        assert app_.state.data_root == env_root.resolve()

    def test_cwd_used_when_neither(self, monkeypatch):
        monkeypatch.delenv("TTP_SERVER_DATA_ROOT", raising=False)
        app_ = create_app()
        assert app_.state.data_root == Path.cwd().resolve()

    def test_invalid_root_fails_at_creation(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TTP_SERVER_DATA_ROOT", raising=False)
        missing = tmp_path / "does_not_exist"
        with pytest.raises(ValueError):
            create_app(data_root=missing)
