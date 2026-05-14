"""
tap_tone_pi.gui — Tkinter GUI for measurement workflows.

Migrated from: gui/app.py

Bug Fix: The binding bug has been fixed. Form values are now captured
         at callback time using StringVar.get(), not at construction time.

Usage:
    python -m tap_tone_pi.gui.app
    # or via CLI:
    ttp gui
"""

try:
    from .app import App

    __all__ = ["App"]
except (ImportError, OSError):
    # GUI requires optional dependencies (sounddevice, PortAudio, etc.)
    App = None  # type: ignore[assignment,misc]
    __all__ = []
