"""
tap_tone_pi.server — HTTP API server.

Provides FastAPI-based HTTP API for remote access to tap_tone_pi functionality.

Usage:
    # Start server
    ttp server --port 8000

    # Or directly with uvicorn
    uvicorn tap_tone_pi.server.app:app --reload

API Documentation:
    http://localhost:8000/docs     (Swagger UI)
    http://localhost:8000/redoc    (ReDoc)
"""

try:
    from tap_tone_pi.server.app import (
        app,
        create_app,
        add_server_subcommand,
    )
    HAS_SERVER = True
except ImportError:
    HAS_SERVER = False
    app = None
    create_app = None
    add_server_subcommand = None

__all__ = [
    "app",
    "create_app",
    "add_server_subcommand",
    "HAS_SERVER",
]
