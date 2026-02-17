"""Session Timeline Viewer — read-only Toplevel dialog.

Displays the contents of ``session_timeline_v1.json`` from a viewer pack
or live session directory.  Strictly factual — no interpretation, no
quality language.

Sources (tried in order):
  1. ``<pack_or_session>/meta/session_timeline_v1.json``  (pre-exported)
  2. On-the-fly export via ``export_session_timeline()``  (live session)

Fail-closed: any load error is shown as an in-dialog message rather than
raising.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ──────────────────────────────────────────────────────────────

_TIMELINE_REL = Path("meta") / "session_timeline_v1.json"

_BOOL_YES = "✓"
_BOOL_NO = "✗"


def _fmt_bool(val: Any) -> str:
    if isinstance(val, bool):
        return _BOOL_YES if val else _BOOL_NO
    return str(val) if val is not None else "—"


def load_timeline(
    base_dir: Path,
    *,
    allow_export: bool = True,
) -> Optional[Dict[str, Any]]:
    """Load or generate a session timeline dict.

    *base_dir* may be an unpacked viewer pack **or** a live session
    directory.  Returns ``None`` on any failure.
    """
    path = base_dir / _TIMELINE_REL
    if path.is_file():
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                return obj
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            return None

    # Fallback: live-export (e.g. from a session dir that hasn't been packed)
    if allow_export:
        try:
            from tap_tone_pi.core.session_timeline import export_session_timeline

            written = export_session_timeline(base_dir)
            if written is not None and written.is_file():
                obj = json.loads(written.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    return obj
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass

    return None


# ── widget ───────────────────────────────────────────────────────────────


class TimelineViewerDialog(tk.Toplevel):
    """Read-only viewer for ``session_timeline_v1.json``.

    Parameters
    ----------
    parent : tk.Tk | tk.Toplevel
        Parent window.
    base_dir : Path
        Viewer-pack root **or** live session directory.
    allow_export : bool
        When *True* (default) and no pre-exported file is found, the
        viewer will call ``export_session_timeline()`` to generate one
        on the fly.
    """

    def __init__(
        self,
        parent: tk.Tk,
        base_dir: Path,
        *,
        allow_export: bool = True,
    ) -> None:
        super().__init__(parent)
        self.title("📋 Session Timeline")
        self.geometry("620x520")
        self.minsize(500, 400)

        self._base_dir = Path(base_dir)
        self._allow_export = allow_export
        self._data: Optional[Dict[str, Any]] = None

        self._build_chrome()
        self._load_and_render()

    # ── chrome ───────────────────────────────────────────────────────

    def _build_chrome(self) -> None:
        """Build the outer frame, header, and refresh/close buttons."""
        main = tk.Frame(self, padx=12, pady=12)
        main.pack(fill=tk.BOTH, expand=True)
        self._main = main

        # Header
        hdr = tk.Frame(main)
        hdr.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            hdr,
            text="📋 Session Timeline",
            font=("Helvetica", 14, "bold"),
        ).pack(side=tk.LEFT)

        tk.Button(
            hdr,
            text="↻ Refresh",
            command=self._load_and_render,
        ).pack(side=tk.RIGHT, padx=5)

        tk.Button(hdr, text="Close", command=self.destroy).pack(side=tk.RIGHT)

        # Content area (replaced on each load)
        self._content = tk.Frame(main)
        self._content.pack(fill=tk.BOTH, expand=True)

    # ── load / render ────────────────────────────────────────────────

    def _load_and_render(self) -> None:
        """(Re-)load the timeline JSON and rebuild the content area."""
        # Tear down previous content
        for w in self._content.winfo_children():
            w.destroy()

        self._data = load_timeline(
            self._base_dir,
            allow_export=self._allow_export,
        )

        if self._data is None:
            tk.Label(
                self._content,
                text="No timeline data available.",
                font=("Helvetica", 11),
                fg="#888",
                pady=30,
            ).pack()
            return

        self._render_header_section()
        self._render_moment_section()
        self._render_policy_trace_section()
        self._render_events_section()
        self._render_counts_section()
        self._render_ui_state_section()

    # ── sections ─────────────────────────────────────────────────────

    def _render_header_section(self) -> None:
        data = self._data
        assert data is not None

        frm = tk.LabelFrame(
            self._content,
            text="Session",
            padx=10,
            pady=6,
        )
        frm.pack(fill=tk.X, pady=(0, 6))

        pairs: List[tuple[str, str]] = [
            ("Session ID", str(data.get("session_id", "—"))),
            (
                "Schema",
                f'{data.get("schema_id", "?")} v{data.get("schema_version", "?")}',
            ),
        ]
        for lbl, val in pairs:
            row = tk.Frame(frm)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text=f"{lbl}:",
                font=("Helvetica", 9, "bold"),
                fg="#555",
                width=14,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=val,
                font=("Helvetica", 9),
                fg="#333",
            ).pack(side=tk.LEFT)

    def _render_moment_section(self) -> None:
        data = self._data
        assert data is not None
        moment = data.get("moment_latest")

        frm = tk.LabelFrame(
            self._content,
            text="Latest Moment",
            padx=10,
            pady=6,
        )
        frm.pack(fill=tk.X, pady=(0, 6))

        if not isinstance(moment, dict) or not moment.get("id"):
            tk.Label(
                frm,
                text="No moment recorded.",
                font=("Helvetica", 9),
                fg="#888",
            ).pack(anchor=tk.W)
            return

        pairs: List[tuple[str, str]] = [
            ("Moment ID", str(moment.get("id", "—"))),
            ("Confidence", f'{moment.get("confidence", "—")}'),
            ("Trigger events", str(moment.get("trigger_event_count", "—"))),
        ]
        for lbl, val in pairs:
            row = tk.Frame(frm)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text=f"{lbl}:",
                font=("Helvetica", 9, "bold"),
                fg="#555",
                width=16,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=val,
                font=("Helvetica", 9),
                fg="#333",
            ).pack(side=tk.LEFT)

    def _render_policy_trace_section(self) -> None:
        data = self._data
        assert data is not None
        trace = data.get("latest_policy_trace")

        if not isinstance(trace, dict) or not trace:
            return

        frm = tk.LabelFrame(
            self._content,
            text="Policy Trace",
            padx=10,
            pady=6,
        )
        frm.pack(fill=tk.X, pady=(0, 6))

        # Standard fields to display
        display_keys: list[tuple[str, str]] = [
            ("rule_id", "Rule ID"),
            ("max_directives", "Max directives"),
            ("soft_prompt", "Soft prompt"),
            ("suppressed_due_to_initiative", "Suppressed (initiative)"),
            ("fallback_mode", "Fallback mode"),
        ]
        for key, label in display_keys:
            if key not in trace:
                continue
            row = tk.Frame(frm)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text=f"{label}:",
                font=("Helvetica", 9, "bold"),
                fg="#555",
                width=22,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            val = trace[key]
            tk.Label(
                row,
                text=_fmt_bool(val)
                if isinstance(val, bool)
                else str(val)
                if val is not None
                else "—",
                font=("Helvetica", 9),
                fg="#333",
            ).pack(side=tk.LEFT)

        # M0: would_have_emitted summary
        whe = trace.get("would_have_emitted")
        if isinstance(whe, dict) and whe.get("summary"):
            row = tk.Frame(frm)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text="Would have emitted:",
                font=("Helvetica", 9, "bold"),
                fg="#555",
                width=22,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=str(whe["summary"]),
                font=("Helvetica", 9),
                fg="#333",
                wraplength=350,
                justify=tk.LEFT,
            ).pack(side=tk.LEFT)

    def _render_events_section(self) -> None:
        data = self._data
        assert data is not None
        events = data.get("directive_events") or []

        frm = tk.LabelFrame(
            self._content,
            text="Directive Events",
            padx=10,
            pady=6,
        )
        frm.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        if not events:
            tk.Label(
                frm,
                text="No directive events.",
                font=("Helvetica", 9),
                fg="#888",
            ).pack(anchor=tk.W)
            return

        columns = ("timestamp", "event_type", "directive_id", "component")
        tree = ttk.Treeview(
            frm,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=min(len(events), 8),
        )

        tree.heading("timestamp", text="Timestamp")
        tree.heading("event_type", text="Event Type")
        tree.heading("directive_id", text="Directive ID")
        tree.heading("component", text="Component")

        tree.column("timestamp", width=170, minwidth=120)
        tree.column("event_type", width=170, minwidth=100)
        tree.column("directive_id", width=140, minwidth=80)
        tree.column("component", width=90, minwidth=60)

        scrollbar = tk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for ev in events:
            tree.insert(
                "",
                tk.END,
                values=(
                    ev.get("timestamp", ""),
                    ev.get("event_type", ""),
                    ev.get("directive_id", ""),
                    ev.get("component", ""),
                ),
            )

    def _render_counts_section(self) -> None:
        data = self._data
        assert data is not None
        counts = data.get("counts") or {}

        frm = tk.LabelFrame(
            self._content,
            text="Counts",
            padx=10,
            pady=6,
        )
        frm.pack(fill=tk.X, pady=(0, 6))

        keys = [
            ("attention_requested", "Requested"),
            ("attention_acknowledged", "Acknowledged"),
            ("attention_dismissed", "Dismissed"),
        ]
        row = tk.Frame(frm)
        row.pack(fill=tk.X)
        for key, label in keys:
            cell = tk.Frame(row)
            cell.pack(side=tk.LEFT, padx=(0, 18))
            tk.Label(
                cell,
                text=f"{label}:",
                font=("Helvetica", 9, "bold"),
                fg="#555",
            ).pack(side=tk.LEFT)
            tk.Label(
                cell,
                text=f" {counts.get(key, 0)}",
                font=("Helvetica", 9),
                fg="#333",
            ).pack(side=tk.LEFT)

    def _render_ui_state_section(self) -> None:
        data = self._data
        assert data is not None
        ui = data.get("ui_state") or {}

        if not ui:
            return

        frm = tk.LabelFrame(
            self._content,
            text="UI State",
            padx=10,
            pady=6,
        )
        frm.pack(fill=tk.X, pady=(0, 6))

        display_keys = [
            ("responded", "Responded"),
            ("trust_banner_dismissed", "Trust banner dismissed"),
            ("show_directive_history", "Show history"),
        ]
        for key, label in display_keys:
            if key not in ui:
                continue
            row = tk.Frame(frm)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text=f"{label}:",
                font=("Helvetica", 9, "bold"),
                fg="#555",
                width=24,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=_fmt_bool(ui[key]),
                font=("Helvetica", 9),
                fg="#333",
            ).pack(side=tk.LEFT)
