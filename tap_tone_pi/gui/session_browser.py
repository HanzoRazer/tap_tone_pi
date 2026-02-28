"""Session browser dialog for viewing past measurement sessions."""

from __future__ import annotations

import platform
import subprocess
import tkinter as tk
from tkinter import ttk
from typing import Callable
from pathlib import Path

from tap_tone_pi.gui.session_info import SessionInfo


class SessionBrowserDialog(tk.Toplevel):
    """
    Session browser dialog for viewing past measurement sessions.

    Features:
    - List all sessions in out/ directory
    - Show session metadata (type, date, files, size)
    - Open session folder in file manager
    - View session details
    - Refresh session list
    """

    def __init__(
        self,
        parent: tk.Tk,
        output_dir: Path | str,
        on_session_selected: Callable[[SessionInfo], None] | None = None,
    ):
        super().__init__(parent)
        self.title("Session Browser")
        self.geometry("750x500")
        self.minsize(600, 400)

        self.output_dir = Path(output_dir)
        self.on_session_selected = on_session_selected
        self._sessions: list[SessionInfo] = []
        self._selected_session: SessionInfo | None = None

        self._build_ui()
        self._load_sessions()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main container
        main = tk.Frame(self, padx=10, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            header,
            text="📂 Session Browser",
            font=("Helvetica", 14, "bold"),
        ).pack(side=tk.LEFT)

        tk.Button(
            header,
            text="↻ Refresh",
            command=self._load_sessions,
        ).pack(side=tk.RIGHT, padx=5)

        tk.Button(
            header,
            text="Open Folder",
            command=self._open_output_folder,
        ).pack(side=tk.RIGHT, padx=5)

        # Session list with scrollbar
        list_frame = tk.Frame(main)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview for session list
        columns = ("type", "name", "modified", "points", "files", "size", "status")
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", selectmode="browse"
        )

        # Configure columns
        self.tree.heading("type", text="")
        self.tree.heading("name", text="Session Name")
        self.tree.heading("modified", text="Last Modified")
        self.tree.heading("points", text="Points")
        self.tree.heading("files", text="Files")
        self.tree.heading("size", text="Size")
        self.tree.heading("status", text="Status")

        self.tree.column("type", width=30, anchor=tk.CENTER)
        self.tree.column("name", width=200)
        self.tree.column("modified", width=140)
        self.tree.column("points", width=60, anchor=tk.CENTER)
        self.tree.column("files", width=60, anchor=tk.CENTER)
        self.tree.column("size", width=80, anchor=tk.E)
        self.tree.column("status", width=80, anchor=tk.CENTER)

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)

        # Detail panel
        self.detail_frame = tk.LabelFrame(
            main, text="Session Details", padx=10, pady=10
        )
        self.detail_frame.pack(fill=tk.X, pady=(10, 0))

        self.detail_label = tk.Label(
            self.detail_frame,
            text="Select a session to view details",
            justify=tk.LEFT,
            anchor=tk.W,
            fg="#666",
        )
        self.detail_label.pack(fill=tk.X)

        # Action buttons
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.open_btn = tk.Button(
            btn_frame,
            text="Open Session Folder",
            command=self._open_session_folder,
            state=tk.DISABLED,
        )
        self.open_btn.pack(side=tk.LEFT, padx=5)

        self.select_btn = tk.Button(
            btn_frame,
            text="Select Session",
            command=self._select_session,
            state=tk.DISABLED,
            bg="#2196F3",
            fg="white",
        )
        self.select_btn.pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="Close",
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=5)

    def _load_sessions(self) -> None:
        """Load sessions from output directory."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        self._sessions = []

        if not self.output_dir.exists():
            self.detail_label.configure(text="Output directory does not exist")
            return

        # Find all session directories
        for item in sorted(
            self.output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            if item.is_dir() and not item.name.startswith("."):
                try:
                    session = SessionInfo.from_path(item)
                    self._sessions.append(session)

                    # Format status
                    status = ""
                    if session.latest_verdict:
                        if session.latest_verdict.upper() == "PASS":
                            status = "✓ PASS"
                        elif session.latest_verdict.upper() == "WARN":
                            status = "⚠ WARN"
                        elif session.latest_verdict.upper() == "FAIL":
                            status = "✗ FAIL"
                        else:
                            status = session.latest_verdict
                    elif session.has_manifest:
                        status = "📋"

                    # Insert into tree
                    self.tree.insert(
                        "",
                        tk.END,
                        values=(
                            session.type_icon,
                            session.name,
                            session.modified.strftime("%Y-%m-%d %H:%M"),
                            session.point_count if session.point_count > 0 else "-",
                            session.file_count,
                            session.size_display,
                            status,
                        ),
                    )
                except (ImportError, OSError, ValueError, KeyError, AttributeError):
                    pass

        # Update summary
        total = len(self._sessions)
        self.detail_label.configure(
            text=f"Found {total} session(s) in {self.output_dir}",
            fg="#666",
        )

    def _on_select(self, event) -> None:
        """Handle session selection."""
        selection = self.tree.selection()
        if not selection:
            self._selected_session = None
            self.open_btn.configure(state=tk.DISABLED)
            self.select_btn.configure(state=tk.DISABLED)
            return

        # Get selected session
        idx = self.tree.index(selection[0])
        if 0 <= idx < len(self._sessions):
            self._selected_session = self._sessions[idx]
            self.open_btn.configure(state=tk.NORMAL)
            self.select_btn.configure(state=tk.NORMAL)
            self._update_detail()

    def _on_double_click(self, event) -> None:
        """Handle double-click to open folder."""
        if self._selected_session:
            self._open_session_folder()

    def _update_detail(self) -> None:
        """Update detail panel with selected session info."""
        if not self._selected_session:
            return

        s = self._selected_session
        detail_text = (
            f"Path: {s.path}\n"
            f"Type: {s.session_type.replace('_', ' ').title()}\n"
            f"Modified: {s.modified.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Files: {s.file_count} ({s.size_display})"
        )

        if s.point_count > 0:
            detail_text += f"\nMeasurement Points: {s.point_count}"
            detail_text += f"\nTotal Attempts: {s.attempt_count}"

        if s.latest_verdict:
            detail_text += f"\nLatest Verdict: {s.latest_verdict.upper()}"

        self.detail_label.configure(text=detail_text, fg="#333")

    def _open_session_folder(self) -> None:
        """Open selected session folder in file manager."""
        if not self._selected_session:
            return

        folder = self._selected_session.path
        if platform.system() == "Windows":
            subprocess.run(["explorer", str(folder)])
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    def _open_output_folder(self) -> None:
        """Open the output folder in file manager."""
        folder = self.output_dir
        if platform.system() == "Windows":
            subprocess.run(["explorer", str(folder)])
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    def _select_session(self) -> None:
        """Select the current session and close dialog."""
        if self._selected_session and self.on_session_selected:
            self.on_session_selected(self._selected_session)
        self.destroy()
