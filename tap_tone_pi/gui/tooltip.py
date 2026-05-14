"""Minimal Tkinter tooltip — no dependencies, no platform hacks.

Usage::

    from tap_tone_pi.gui.tooltip import Tooltip
    Tooltip(some_button, "Helpful explanation text.")
"""

from __future__ import annotations

import tkinter as tk


class Tooltip:
    """Hover tooltip bound to a Tkinter widget."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event: object = None) -> None:
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + 20
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Helvetica", 9),
        )
        label.pack(ipadx=4, ipady=2)

    def _hide(self, _event: object = None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None
