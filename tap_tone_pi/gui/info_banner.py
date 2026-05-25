# INSTRUMENT CLASS: MEASUREMENT
"""Subtle informational banner — GUI-only, additive, fail-closed.

Usage::

    from tap_tone_pi.gui.info_banner import InfoBanner
    banner = InfoBanner(parent, text="Some message.", on_dismiss=callback)
    banner.pack(fill=tk.X, pady=(0, 8))
"""

from __future__ import annotations

import tkinter as tk


class InfoBanner(tk.Frame):
    """
    Lightweight informational banner.

    - Additive UI element; never blocks or interrupts.
    - Supports optional dismiss via close button.
    - Fail-closed: exceptions are swallowed.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        text: str,
        on_dismiss: object = None,
    ) -> None:
        super().__init__(parent, bd=0, highlightthickness=0)
        self._on_dismiss = on_dismiss

        # Light neutral styling — avoids warning / error semantics
        self.configure(bg="#f5f5f5")

        msg = tk.Label(
            self,
            text=text,
            bg="#f5f5f5",
            fg="#333",
            font=("Helvetica", 9),
            justify=tk.LEFT,
            anchor="w",
            wraplength=470,
        )
        msg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 6), pady=6)

        btn = tk.Button(
            self,
            text="\u00d7",
            bg="#f5f5f5",
            fg="#666",
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            command=self._dismiss,
            padx=6,
            pady=0,
        )
        btn.pack(side=tk.RIGHT, padx=(0, 6), pady=2)

    def _dismiss(self) -> None:
        try:
            self.pack_forget()
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass
        if callable(self._on_dismiss):
            try:
                self._on_dismiss()  # type: ignore[operator]
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                pass
