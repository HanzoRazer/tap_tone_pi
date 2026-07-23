# INSTRUMENT CLASS: MEASUREMENT
"""
FastAPI server for tap_tone_pi.

Provides HTTP API for remote measurement triggering and data retrieval.
This is a scaffold for Phase 3 development.

Usage:
    uvicorn tap_tone_pi.server.app:app --reload --host 0.0.0.0 --port 8000

Or via CLI:
    ttp server --port 8000
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

#: Environment variable that configures the server data root when no explicit
#: ``data_root`` argument is passed to :func:`create_app` (see precedence there).
DATA_ROOT_ENV = "TTP_SERVER_DATA_ROOT"

#: Stable identifier for the filesystem-authorization policy this build enforces.
#: v2 = explicit configurable data-root containment (DO-98); v1 was the
#: cwd-anchored relative-only guard. Surfaced by ``/server/status`` and events.
POLICY_VERSION = "filesystem-auth-v2"

#: Dedicated diagnostics logger for authorization decisions. The host
#: application configures handlers/formatters; this module only emits. Records
#: never carry raw request/resolved/root paths — see :class:`AuthorizationEvent`.
_authz_logger = logging.getLogger("tap_tone_pi.server.authz")


@dataclass(frozen=True)
class AuthorizationEvent:
    """One filesystem-authorization decision, as structured diagnostics.

    Deliberately path-free: it carries a non-reversible digest of the configured
    root, the request path *type*, the endpoint/role, the result, and a stable
    reason code — never the requested path, resolved path, root path, or any
    exception text. This is the payload logged via ``extra=`` on the authz
    logger, so structured handlers can render each field.
    """

    timestamp: str
    endpoint: str
    input_role: str
    request_path_type: str  # "relative" | "absolute"
    authorization_result: str  # "allowed" | "rejected"
    policy_version: str
    root_digest: str
    reason_code: str | None = None
    error_type: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root_digest(value: str) -> str:
    """Stable, non-reversible 12-char digest of a root path (never the path)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _configured_root_value(data_root: Path | str | None) -> str | None:
    """Return the explicitly configured root value (arg or env), else ``None``.

    ``None`` means "nothing configured — default to cwd". An empty or whitespace
    environment value is treated as unset.
    """
    if data_root is not None:
        return str(data_root)
    env = os.environ.get(DATA_ROOT_ENV)
    return env if (env and env.strip()) else None


def _canonical_root(value: str) -> Path:
    """Canonicalize a configured root the same way everywhere (``~`` expanded,
    absolute, ``..`` collapsed, symlinks resolved). Digesting this — rather than
    the raw input string — makes the root digest identity-stable: ``.``,
    ``./data`` and ``foo/../data`` under the same cwd yield one digest, matching
    what ``/server/status`` reports for the live root.

    Not pure: ``resolve()`` touches the filesystem and may raise ``OSError``
    (permissions, and platform-specific conditions). Callers must never invoke
    it on an error-reporting path where a second raise could mask the original
    failure — compute once and reuse the result (see ``_InvalidDataRootError``).
    """
    return Path(value).expanduser().resolve()


def _emit_authz(event: AuthorizationEvent) -> None:
    """Log one authorization event at the level appropriate to its outcome.

    allowed → DEBUG; OUTSIDE_ROOT/SYMLINK_ESCAPE → WARNING; INVALID_ROOT and
    PATH_RESOLUTION_FAILURE → ERROR. The message and every ``extra`` field are
    path-free.
    """
    if event.authorization_result == "allowed":
        level = logging.DEBUG
    elif event.reason_code in ("INVALID_ROOT", "PATH_RESOLUTION_FAILURE"):
        level = logging.ERROR
    else:  # OUTSIDE_ROOT / SYMLINK_ESCAPE
        level = logging.WARNING
    _authz_logger.log(
        level,
        "authorization %s: endpoint=%s role=%s type=%s reason=%s",
        event.authorization_result,
        event.endpoint,
        event.input_role,
        event.request_path_type,
        event.reason_code or "-",
        extra=asdict(event),
    )


def _lexically_under(candidate: Path, root: Path) -> bool:
    """True if ``candidate`` is at/under ``root`` by path components, *without*
    resolving symlinks — used only to label SYMLINK_ESCAPE vs OUTSIDE_ROOT."""
    try:
        return candidate == root or root in candidate.parents
    except (OSError, ValueError):  # pragma: no cover - defensive
        return False


class _InvalidDataRootError(ValueError):
    """A configured data root that resolved but is not an existing directory.

    Subclasses ``ValueError`` so existing callers/tests that expect a
    ``ValueError`` are unaffected, and carries the already-canonicalized root so
    the startup diagnostic can reuse it. That reuse is the point: recomputing
    ``_canonical_root`` on the error path would touch the filesystem again and
    could raise, masking this failure and silently dropping the INVALID_ROOT
    event.
    """

    def __init__(self, message: str, canonical_root: Path) -> None:
        super().__init__(message)
        self.canonical_root = canonical_root


def _resolve_data_root(data_root: Path | str | None) -> Path:
    """Resolve the authorized data root: explicit arg > ``$TTP_SERVER_DATA_ROOT`` > cwd.

    The returned path is absolute and canonical (symlinks resolved). A root that
    is *configured* — via the argument or the environment — but does not exist as
    a directory raises ``_InvalidDataRootError`` (a ``ValueError``) at application
    creation, carrying the canonical root, rather than silently falling back to
    the working directory. The implicit cwd default (used when nothing is
    configured) always exists and is not re-validated.
    """
    configured = _configured_root_value(data_root)
    if configured is None:
        return Path.cwd().resolve()
    root = _canonical_root(configured)
    if not root.is_dir():
        raise _InvalidDataRootError(
            "configured server data root does not exist or is not a directory: "
            f"{str(configured)!r}",
            root,
        )
    return root


try:
    from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
    from fastapi.responses import JSONResponse, FileResponse  # noqa: F401
    from pydantic import BaseModel, Field  # noqa: F401

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    # Stub for import without fastapi
    FastAPI = None
    BaseModel = object


# --- Pydantic Models ---

if HAS_FASTAPI:

    class HealthResponse(BaseModel):
        """Health check response."""

        status: str = "ok"
        version: str
        timestamp: str

    class DeviceInfo(BaseModel):
        """Audio device information."""

        index: int
        name: str
        sample_rate: int
        channels: int
        is_default: bool = False

    class CalibrationStatus(BaseModel):
        """Calibration status for a device."""

        device_index: int
        status: str  # "valid", "stale", "uncalibrated", "failed"
        calibrated_at: Optional[str] = None
        latency_ms: Optional[float] = None
        amplitude_offset_db: Optional[float] = None
        is_stale: bool = False

    class GridInfo(BaseModel):
        """Grid information."""

        name: str
        path: str
        point_count: int
        units: str
        width: float
        height: float

    class SessionInfo(BaseModel):
        """Session information."""

        session_id: str
        path: str
        grid_name: str
        point_count: int
        captured: int
        pending: int
        failed: int
        started_at: str
        last_updated: str
        is_complete: bool

    class CaptureRequest(BaseModel):
        """Request to capture a single point."""

        session_id: str
        point_id: str
        device_index: Optional[int] = None

    class CaptureResult(BaseModel):
        """Result of a capture operation."""

        success: bool
        point_id: str
        coherence: Optional[float] = None
        status: str  # "captured", "warning", "failed"
        message: str = ""

    class AnalysisRequest(BaseModel):
        """Request for tap tone analysis."""

        wav_path: Optional[str] = None
        wav_base64: Optional[str] = None
        sample_rate: int = 48000
        fft_size: int = 8192

    class AnalysisResult(BaseModel):
        """Result of tap tone analysis."""

        dominant_hz: Optional[float] = None
        peaks: List[Dict[str, float]]
        confidence: float
        clipped: bool
        rms: float

    class AuthorizationStatus(BaseModel):
        """Server filesystem-authorization status — diagnostics, no host paths.

        ``configured`` is True when the root came from an explicit argument or
        ``TTP_SERVER_DATA_ROOT``; it does not reveal which of the two (that is
        internal). ``root_digest`` is a one-way digest, not the path.
        """

        policy_version: str
        configured: bool
        root_digest: str
        started_at: str


# --- App Factory ---


def create_app(*, data_root: Path | str | None = None) -> "FastAPI":
    """Create and configure FastAPI application.

    Args:
        data_root: root directory beneath which the ``/grids`` and ``/sessions``
            endpoints may read. Resolution precedence is this argument, then the
            ``TTP_SERVER_DATA_ROOT`` environment variable, then ``Path.cwd()``.
            A configured root that does not exist raises ``ValueError`` here, at
            application creation, rather than failing later per request. The
            resolved root is exposed on ``app.state.data_root``.
    """
    if not HAS_FASTAPI:
        raise ImportError(
            "FastAPI is required for the server. "
            "Install with: pip install fastapi uvicorn"
        )

    configured_value = _configured_root_value(data_root)
    is_configured = configured_value is not None
    try:
        resolved_root = _resolve_data_root(data_root)
    except _InvalidDataRootError as exc:
        # Startup authorization failure — emit a path-free diagnostic, then
        # preserve the ValueError. The canonical root is taken from the exception
        # (computed once in _resolve_data_root); this path NEVER re-canonicalizes,
        # so it cannot raise here and drop the INVALID_ROOT event. Digesting the
        # canonical form keeps the digest identity-stable and correlated with
        # /server/status. request_path_type reads only is_absolute() on the raw
        # value (no filesystem access), so it cannot raise either.
        _emit_authz(
            AuthorizationEvent(
                timestamp=_now_iso(),
                endpoint="<startup>",
                input_role="data_root",
                request_path_type=(
                    "absolute"
                    if Path(str(configured_value)).is_absolute()
                    else "relative"
                ),
                authorization_result="rejected",
                policy_version=POLICY_VERSION,
                root_digest=_root_digest(str(exc.canonical_root)),
                reason_code="INVALID_ROOT",
                error_type="ValueError",
            )
        )
        raise

    root_digest_value = _root_digest(str(resolved_root))
    started_at = _now_iso()

    app = FastAPI(
        title="tap_tone_pi API",
        description="HTTP API for tap tone acoustic measurement",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.data_root = resolved_root
    app.state.policy_version = POLICY_VERSION
    app.state.root_digest = root_digest_value
    app.state.configured = is_configured
    app.state.started_at = started_at

    # --- Path validation helper ---

    def _safe_directory(directory: str, *, endpoint: str, input_role: str) -> Path:
        """Resolve a caller-supplied directory within the authorized data root.

        Every path — relative *or* absolute — must resolve beneath the
        configured data root:

          * relative paths are resolved beneath the root;
          * absolute paths are accepted only when they resolve beneath the root;
          * containment is checked *after* resolution, so ``..`` components and
            symlink escapes that leave the root are rejected.

        Containment is a true path-component check (``is_relative_to``), not a
        string-prefix test: a string prefix would wrongly accept a sibling that
        merely shares the name prefix (root ``/srv/app`` vs ``/srv/app_evil``).

        The root is resolved once at application creation (see ``create_app``);
        escapes past it — relative or absolute — return HTTP 400. A leading ``~``
        in a request path is *not* expanded (that would leak the server user's
        home into a client-controlled value); ``~`` expansion applies only to the
        server-configured data root.

        This is the single gate for every read of a caller-supplied directory
        (``/grids``, ``/sessions``, ``/sessions/{id}``, and ``/export/{id}``).

        Each call emits exactly one structured authorization event (DO-99). The
        authorization *decision* is unchanged; the event only records it.
        """
        requested = Path(directory)
        request_path_type = "absolute" if requested.is_absolute() else "relative"
        base = requested if requested.is_absolute() else (resolved_root / requested)

        def _event(
            result: str, reason: str | None = None, error_type: str | None = None
        ):
            return AuthorizationEvent(
                timestamp=_now_iso(),
                endpoint=endpoint,
                input_role=input_role,
                request_path_type=request_path_type,
                authorization_result=result,
                policy_version=POLICY_VERSION,
                root_digest=root_digest_value,
                reason_code=reason,
                error_type=error_type,
            )

        try:
            resolved = base.resolve()
        except Exception as exc:  # resolution itself failed
            _emit_authz(
                _event("rejected", "PATH_RESOLUTION_FAILURE", type(exc).__name__)
            )
            raise  # preserve the original exception path (no HTTP conversion)

        if not resolved.is_relative_to(resolved_root):
            # Diagnostic-only distinction; the rejection is identical either way.
            lexical = Path(os.path.normpath(str(base)))
            reason = (
                "SYMLINK_ESCAPE"
                if _lexically_under(lexical, resolved_root)
                else "OUTSIDE_ROOT"
            )
            _emit_authz(_event("rejected", reason))
            raise HTTPException(
                status_code=400,
                detail="Directory must be within the configured data root.",
            )

        _emit_authz(_event("allowed"))
        return resolved

    # --- Health & Info ---

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="ok",
            version="0.1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/info", tags=["System"])
    async def system_info():
        """Get system information."""
        from tap_tone_pi.core.dsp import get_dsp_provenance

        return {
            "name": "tap_tone_pi",
            "version": "2.3.0",  # TODO: Read from package
            "dsp": get_dsp_provenance(),
            "server": {
                "framework": "FastAPI",
                "python": "3.10+",
            },
        }

    @app.get(
        "/server/status",
        response_model=AuthorizationStatus,
        tags=["System"],
    )
    async def server_status():
        """Filesystem-authorization status (DO-99) — policy metadata only.

        Reports the active policy version, whether a data root was explicitly
        configured, a one-way digest of that root, and when the app was created.
        Deliberately discloses no host path.
        """
        return AuthorizationStatus(
            policy_version=POLICY_VERSION,
            configured=is_configured,
            root_digest=root_digest_value,
            started_at=started_at,
        )

    # --- Devices ---

    @app.get("/devices", response_model=List[DeviceInfo], tags=["Devices"])
    async def list_devices():
        """List available audio devices."""
        # Stub implementation
        # TODO: Integrate with actual audio device enumeration
        return [
            DeviceInfo(
                index=0,
                name="Default Audio Device",
                sample_rate=48000,
                channels=2,
                is_default=True,
            ),
        ]

    # --- Calibration ---

    @app.get(
        "/calibration/{device_index}",
        response_model=CalibrationStatus,
        tags=["Calibration"],
    )
    async def get_calibration_status(device_index: int):
        """Get calibration status for a device."""
        try:
            from tap_tone_pi.calibration import (
                get_calibration_status as get_status,
                load_calibration,
                is_calibration_stale,
            )

            status = get_status(device_index)
            data = load_calibration(device_index)

            if data is None:
                return CalibrationStatus(
                    device_index=device_index,
                    status="uncalibrated",
                )

            return CalibrationStatus(
                device_index=device_index,
                status=status.value,
                calibrated_at=data.calibrated_at,
                latency_ms=data.loopback_latency_ms,
                amplitude_offset_db=data.amplitude_error_db,
                is_stale=is_calibration_stale(data),
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --- Grids ---

    @app.get("/grids", response_model=List[GridInfo], tags=["Grids"])
    async def list_grids(
        directory: str = Query(default="config/grids", description="Grid directory"),
    ):
        """List available measurement grids."""
        grid_dir = _safe_directory(directory, endpoint="/grids", input_role="directory")

        if not grid_dir.exists():
            return []

        grids = []
        for grid_file in grid_dir.glob("*.json"):
            try:
                with open(grid_file) as f:
                    data = json.load(f)

                points = data.get("points", [])
                xs = [p["x"] for p in points]
                ys = [p["y"] for p in points]

                grids.append(
                    GridInfo(
                        name=data.get("name", grid_file.stem),
                        path=str(grid_file),
                        point_count=len(points),
                        units=data.get("units", "mm"),
                        width=max(xs) - min(xs) if xs else 0,
                        height=max(ys) - min(ys) if ys else 0,
                    )
                )
            except Exception:
                continue

        return grids

    # --- Sessions ---

    @app.get("/sessions", response_model=List[SessionInfo], tags=["Sessions"])
    async def list_sessions(
        directory: str = Query(
            default="./runs_phase2", description="Sessions directory"
        ),
    ):
        """List Phase 2 capture sessions."""
        sessions_dir = _safe_directory(
            directory, endpoint="/sessions", input_role="directory"
        )

        if not sessions_dir.exists():
            return []

        sessions = []
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            state_file = session_dir / "session_state.json"
            if not state_file.exists():
                continue

            try:
                with open(state_file) as f:
                    state = json.load(f)

                points = state.get("points", {})
                statuses = [p.get("status", "pending") for p in points.values()]

                sessions.append(
                    SessionInfo(
                        session_id=session_dir.name,
                        path=str(session_dir),
                        grid_name=state.get("grid_path", "unknown"),
                        point_count=len(points),
                        captured=statuses.count("captured") + statuses.count("warning"),
                        pending=statuses.count("pending"),
                        failed=statuses.count("failed"),
                        started_at=state.get("started_at_utc", ""),
                        last_updated=state.get("last_updated_utc", ""),
                        is_complete=state.get("is_complete", False),
                    )
                )
            except Exception:
                continue

        return sessions

    @app.get("/sessions/{session_id}", tags=["Sessions"])
    async def get_session(session_id: str, directory: str = "./runs_phase2"):
        """Get detailed session information."""
        # Same data-root authorization as /sessions: confine the full
        # directory/session_id read path (a `..` in either escapes -> HTTP 400).
        session_dir = _safe_directory(
            str(Path(directory) / session_id),
            endpoint="/sessions/{session_id}",
            input_role="session",
        )
        state_file = session_dir / "session_state.json"

        if not state_file.exists():
            raise HTTPException(status_code=404, detail="Session not found")

        with open(state_file) as f:
            return json.load(f)

    # --- Analysis ---

    @app.post("/analyze", response_model=AnalysisResult, tags=["Analysis"])
    async def analyze_tap_tone(request: AnalysisRequest):
        """Analyze a tap tone recording."""
        try:
            from tap_tone_pi.core.analysis import analyze_tap
            from tap_tone_pi.io.wav import read_wav_mono
            import base64

            # Load audio
            if request.wav_path:
                signal, fs = read_wav_mono(Path(request.wav_path))
            elif request.wav_base64:
                # Decode base64 WAV
                wav_bytes = base64.b64decode(request.wav_base64)  # noqa: F841
                # TODO: Parse WAV from bytes
                raise HTTPException(
                    status_code=501, detail="Base64 WAV input not yet implemented"
                )
            else:
                raise HTTPException(
                    status_code=400, detail="Either wav_path or wav_base64 required"
                )

            # Analyze
            result = analyze_tap(signal, fs.sample_rate)

            return AnalysisResult(
                dominant_hz=result.dominant_hz,
                peaks=[
                    {"freq_hz": p.freq_hz, "magnitude": p.magnitude}
                    for p in result.peaks[:10]
                ],
                confidence=result.confidence,
                clipped=result.clipped,
                rms=result.rms,
            )

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="WAV file not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --- Viewer Pack Export ---

    class ExportResponse(BaseModel):
        session_id: str
        pack_path: str
        manifest_sha256: str
        file_count: int
        as_zip: bool
        status: str = "ok"

    @app.post("/export/{session_id}", tags=["Export"])
    async def export_viewer_pack(
        session_id: str,
        directory: str = "./runs_phase2",
        output_dir: str = "./exports",
        as_zip: bool = True,
        background_tasks: BackgroundTasks = None,
    ):
        """
        Export a Phase 2 session as a viewer_pack_v1 bundle.

        Locates the session directory under `directory`, runs the viewer pack
        exporter, and returns the path and manifest checksum of the output.

        Parameters:
            session_id:  Session directory name (e.g. session_20260330T120000Z)
                         or path fragment to match under `directory`.
            directory:   Root directory containing session folders.
            output_dir:  Where to write the exported pack.
            as_zip:      If true, produce a .zip bundle (default: true).

        Returns:
            ExportResponse with pack path and provenance metadata.
        """
        import hashlib
        from pathlib import Path as P

        from scripts.phase2.export_viewer_pack_v1 import export_viewer_pack as _export

        # Resolve session directory under the authorized data root (same policy
        # as /sessions). The read root and the selected session directory are
        # both confined; an escaping `directory` or `session_id` yields HTTP 400.
        sessions_root = _safe_directory(
            directory, endpoint="/export/{session_id}", input_role="directory"
        )
        # Try exact match first, then prefix match (glob results stay under root).
        session_dir = _safe_directory(
            str(sessions_root / session_id),
            endpoint="/export/{session_id}",
            input_role="session",
        )
        if not session_dir.exists():
            matches = sorted(sessions_root.glob(f"{session_id}*"))
            if not matches:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session '{session_id}' not found under {directory}",
                )
            session_dir = matches[0]

        # output_dir is a write target, not a read of app data; DO-98 governs
        # read authorization only (writes are out of scope) so it is not confined
        # to the data root. See README "HTTP API server".
        out_dir = P(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            pack_path = _export(session_dir, out_dir, as_zip=as_zip)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            # Includes ADR-0009 wolf purity gate failures
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        # Compute manifest checksum for provenance
        manifest_sha = ""
        manifest_path = pack_path / "manifest.json" if pack_path.is_dir() else None
        if manifest_path and manifest_path.exists():
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:16]
        elif pack_path.is_file():
            manifest_sha = hashlib.sha256(pack_path.read_bytes()).hexdigest()[:16]

        file_count = (
            sum(1 for _ in pack_path.rglob("*") if _.is_file())
            if pack_path.is_dir()
            else 1
        )

        return ExportResponse(
            session_id=session_id,
            pack_path=str(pack_path),
            manifest_sha256=manifest_sha,
            file_count=file_count,
            as_zip=as_zip,
        )

    @app.get("/export/{session_id}", tags=["Export"])
    async def export_viewer_pack_get(
        session_id: str,
        directory: str = "./runs_phase2",
        output_dir: str = "./exports",
        as_zip: bool = True,
    ):
        """GET convenience alias for the export endpoint. Same as POST /export/{session_id}."""
        import hashlib
        from pathlib import Path as P

        from scripts.phase2.export_viewer_pack_v1 import export_viewer_pack as _export

        # Confined to the authorized data root, same as POST /export.
        sessions_root = _safe_directory(
            directory, endpoint="/export/{session_id}", input_role="directory"
        )
        session_dir = _safe_directory(
            str(sessions_root / session_id),
            endpoint="/export/{session_id}",
            input_role="session",
        )
        if not session_dir.exists():
            matches = sorted(sessions_root.glob(f"{session_id}*"))
            if not matches:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session '{session_id}' not found under {directory}",
                )
            session_dir = matches[0]

        # output_dir is a write target; not confined (DO-98 governs reads only).
        out_dir = P(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            pack_path = _export(session_dir, out_dir, as_zip=as_zip)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        manifest_sha = ""
        manifest_path = pack_path / "manifest.json" if pack_path.is_dir() else None
        if manifest_path and manifest_path.exists():
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:16]

        file_count = (
            sum(1 for _ in pack_path.rglob("*") if _.is_file())
            if pack_path.is_dir()
            else 1
        )

        return {
            "session_id": session_id,
            "pack_path": str(pack_path),
            "manifest_sha256": manifest_sha,
            "file_count": file_count,
            "as_zip": as_zip,
            "status": "ok",
        }

    return app


# Singleton app instance
app = create_app() if HAS_FASTAPI else None


# --- CLI Integration ---


def add_server_subcommand(subparsers) -> None:
    """Add server subcommand to CLI."""

    parser = subparsers.add_parser(
        "server",
        help="Start HTTP API server",
        description="Start the tap_tone_pi HTTP API server.",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help=(
            "Root directory from which server grid and session data may be read. "
            "Relative and absolute request paths must resolve beneath it "
            "(default: current working directory)."
        ),
    )

    parser.set_defaults(fn=cmd_server)


def cmd_server(args) -> int:
    """CLI handler for server command."""
    if not HAS_FASTAPI:
        print("Error: FastAPI is required for the server.")
        print("Install with: pip install fastapi uvicorn")
        return 1

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required for the server.")
        print("Install with: pip install uvicorn")
        return 1

    print(f"Starting tap_tone_pi server on {args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")

    # The app is launched by import string ("...:app") so uvicorn --reload can
    # re-import it, which means the configured root must reach create_app()
    # through the environment rather than a factory argument. Set it only around
    # the (blocking) run and restore the previous value afterward so a direct
    # unit test of cmd_server cannot leak the override into the parent process.
    data_root = getattr(args, "data_root", None)
    previous = os.environ.get(DATA_ROOT_ENV)
    try:
        if data_root is not None:
            os.environ[DATA_ROOT_ENV] = data_root
        uvicorn.run(
            "tap_tone_pi.server.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    finally:
        if previous is None:
            os.environ.pop(DATA_ROOT_ENV, None)
        else:
            os.environ[DATA_ROOT_ENV] = previous

    return 0
