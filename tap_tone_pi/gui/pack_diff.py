# INSTRUMENT CLASS: MEASUREMENT
"""Pack diff dialog for comparing two measurement sessions."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


class PackDiffDialog(tk.Toplevel):
    """
    Pack diff dialog for comparing two measurement sessions.

    Shows before/after comparison with:
    - Session selectors (dropdown or browse)
    - Peak frequency changes with delta indicators
    - Metric changes with percentage change
    - Visual status indicators (added/removed/changed)
    """

    def __init__(
        self,
        parent: tk.Tk,
        output_dir: Path | str,
        initial_session_a: str | None = None,
        initial_session_b: str | None = None,
    ):
        super().__init__(parent)
        self.title("Pack Diff - Before/After Comparison")
        self.geometry("800x600")
        self.minsize(700, 500)

        self.output_dir = Path(output_dir)
        self._sessions: list[str] = []
        self._diff_result = None

        self._build_ui()
        self._load_sessions()

        # Set initial selections if provided
        if initial_session_a:
            self._set_combo(self.combo_a, initial_session_a)
        if initial_session_b:
            self._set_combo(self.combo_b, initial_session_b)

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main = tk.Frame(self, padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            header,
            text="📊 Session Comparison",
            font=("Helvetica", 14, "bold"),
        ).pack(side=tk.LEFT)

        # Session selection frame
        select_frame = tk.LabelFrame(main, text="Select Sessions", padx=10, pady=10)
        select_frame.pack(fill=tk.X, pady=(0, 10))

        # Session A (Before)
        row_a = tk.Frame(select_frame)
        row_a.pack(fill=tk.X, pady=3)

        tk.Label(row_a, text="Before (A):", width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.combo_a = ttk.Combobox(row_a, state="readonly", width=50)
        self.combo_a.pack(side=tk.LEFT, padx=5)

        # Session B (After)
        row_b = tk.Frame(select_frame)
        row_b.pack(fill=tk.X, pady=3)

        tk.Label(row_b, text="After (B):", width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.combo_b = ttk.Combobox(row_b, state="readonly", width=50)
        self.combo_b.pack(side=tk.LEFT, padx=5)

        # Swap button
        tk.Button(
            row_b,
            text="⇅ Swap",
            command=self._swap_sessions,
        ).pack(side=tk.LEFT, padx=10)

        # Compare button
        btn_row = tk.Frame(select_frame)
        btn_row.pack(fill=tk.X, pady=(10, 0))

        self.compare_btn = tk.Button(
            btn_row,
            text="Compare Sessions",
            command=self._do_compare,
            bg="#2196F3",
            fg="white",
            font=("Helvetica", 10, "bold"),
        )
        self.compare_btn.pack(side=tk.LEFT)

        self.status_label = tk.Label(btn_row, text="", fg="#666")
        self.status_label.pack(side=tk.LEFT, padx=15)

        # Results frame (with notebook for tabs)
        self.results_frame = tk.LabelFrame(
            main, text="Comparison Results", padx=10, pady=10
        )
        self.results_frame.pack(fill=tk.BOTH, expand=True)

        # Notebook for different views
        self.notebook = ttk.Notebook(self.results_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Summary tab
        self.summary_frame = tk.Frame(self.notebook)
        self.notebook.add(self.summary_frame, text="Summary")

        self.summary_text = tk.Text(
            self.summary_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            state=tk.DISABLED,
            height=8,
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)

        # Peaks tab
        self.peaks_frame = tk.Frame(self.notebook)
        self.notebook.add(self.peaks_frame, text="Peaks")

        # Peaks treeview
        peaks_columns = ("label", "freq_a", "freq_b", "delta", "delta_pct", "status")
        self.peaks_tree = ttk.Treeview(
            self.peaks_frame, columns=peaks_columns, show="headings"
        )

        self.peaks_tree.heading("label", text="Peak")
        self.peaks_tree.heading("freq_a", text="Freq A (Hz)")
        self.peaks_tree.heading("freq_b", text="Freq B (Hz)")
        self.peaks_tree.heading("delta", text="Δ Hz")
        self.peaks_tree.heading("delta_pct", text="Δ %")
        self.peaks_tree.heading("status", text="Status")

        self.peaks_tree.column("label", width=80)
        self.peaks_tree.column("freq_a", width=100, anchor=tk.E)
        self.peaks_tree.column("freq_b", width=100, anchor=tk.E)
        self.peaks_tree.column("delta", width=80, anchor=tk.E)
        self.peaks_tree.column("delta_pct", width=80, anchor=tk.E)
        self.peaks_tree.column("status", width=100)

        peaks_scroll = ttk.Scrollbar(
            self.peaks_frame, orient=tk.VERTICAL, command=self.peaks_tree.yview
        )
        self.peaks_tree.configure(yscrollcommand=peaks_scroll.set)

        self.peaks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        peaks_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Metrics tab
        self.metrics_frame = tk.Frame(self.notebook)
        self.notebook.add(self.metrics_frame, text="Metrics")

        # Metrics treeview
        metrics_columns = ("name", "value_a", "value_b", "delta", "delta_pct")
        self.metrics_tree = ttk.Treeview(
            self.metrics_frame, columns=metrics_columns, show="headings"
        )

        self.metrics_tree.heading("name", text="Metric")
        self.metrics_tree.heading("value_a", text="Before")
        self.metrics_tree.heading("value_b", text="After")
        self.metrics_tree.heading("delta", text="Δ")
        self.metrics_tree.heading("delta_pct", text="Δ %")

        self.metrics_tree.column("name", width=150)
        self.metrics_tree.column("value_a", width=120, anchor=tk.E)
        self.metrics_tree.column("value_b", width=120, anchor=tk.E)
        self.metrics_tree.column("delta", width=100, anchor=tk.E)
        self.metrics_tree.column("delta_pct", width=80, anchor=tk.E)

        metrics_scroll = ttk.Scrollbar(
            self.metrics_frame, orient=tk.VERTICAL, command=self.metrics_tree.yview
        )
        self.metrics_tree.configure(yscrollcommand=metrics_scroll.set)

        self.metrics_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        metrics_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom buttons
        bottom = tk.Frame(main)
        bottom.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            bottom,
            text="Export Report",
            command=self._export_report,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            bottom,
            text="Close",
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=5)

    def _load_sessions(self) -> None:
        """Load available sessions from output directory."""
        self._sessions = []

        if not self.output_dir.exists():
            return

        for item in sorted(
            self.output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            if item.is_dir() and not item.name.startswith("."):
                self._sessions.append(item.name)

        self.combo_a["values"] = self._sessions
        self.combo_b["values"] = self._sessions

    def _set_combo(self, combo: ttk.Combobox, value: str) -> None:
        """Set combobox selection by value."""
        if value in self._sessions:
            idx = self._sessions.index(value)
            combo.current(idx)

    def _swap_sessions(self) -> None:
        """Swap session A and B."""
        idx_a = self.combo_a.current()
        idx_b = self.combo_b.current()

        if idx_a >= 0:
            self.combo_b.current(idx_a)
        if idx_b >= 0:
            self.combo_a.current(idx_b)

    def _do_compare(self) -> None:
        """Run the comparison."""
        idx_a = self.combo_a.current()
        idx_b = self.combo_b.current()

        if idx_a < 0 or idx_b < 0:
            self.status_label.configure(text="Select both sessions", fg="#f44336")
            return

        if idx_a == idx_b:
            self.status_label.configure(text="Select different sessions", fg="#f44336")
            return

        session_a = self._sessions[idx_a]
        session_b = self._sessions[idx_b]

        self.status_label.configure(text="Comparing...", fg="#2196F3")
        self.update()

        try:
            from tap_tone_pi.core.session_diff import compare_sessions

            path_a = self.output_dir / session_a
            path_b = self.output_dir / session_b

            self._diff_result = compare_sessions(path_a, path_b)

            self._display_results()

            if self._diff_result.errors:
                self.status_label.configure(
                    text=f"Compared with {len(self._diff_result.errors)} warning(s)",
                    fg="#ff9800",
                )
            else:
                self.status_label.configure(text="Comparison complete", fg="#4CAF50")

        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}", fg="#f44336")

    def _display_results(self) -> None:
        """Display comparison results in the UI."""
        if not self._diff_result:
            return

        diff = self._diff_result

        # Update summary
        self.summary_text.configure(state=tk.NORMAL)
        self.summary_text.delete("1.0", tk.END)

        from tap_tone_pi.core.session_diff import format_diff_report

        report = format_diff_report(diff)
        self.summary_text.insert("1.0", report)
        self.summary_text.configure(state=tk.DISABLED)

        # Update peaks tree
        for item in self.peaks_tree.get_children():
            self.peaks_tree.delete(item)

        for p in diff.peaks:
            freq_a = f"{p.freq_a:.1f}" if p.freq_a else "-"
            freq_b = f"{p.freq_b:.1f}" if p.freq_b else "-"
            delta = f"{p.freq_delta:+.1f}" if p.freq_delta else "-"
            delta_pct = f"{p.freq_delta_pct:+.1f}%" if p.freq_delta_pct else "-"

            # Status with icon
            status_icons = {
                "added": "➕ Added",
                "removed": "➖ Removed",
                "changed": "🔄 Changed",
                "unchanged": "= Same",
            }
            status = status_icons.get(p.status, p.status)

            self.peaks_tree.insert(
                "", tk.END, values=(p.label, freq_a, freq_b, delta, delta_pct, status)
            )

        # Update metrics tree
        for item in self.metrics_tree.get_children():
            self.metrics_tree.delete(item)

        for m in diff.metrics:
            value_a = f"{m.value_a:.4f}" if m.value_a else "-"
            value_b = f"{m.value_b:.4f}" if m.value_b else "-"
            delta = f"{m.delta:+.4f}" if m.delta else "-"
            delta_pct = f"{m.delta_pct:+.1f}%" if m.delta_pct else "-"

            self.metrics_tree.insert(
                "", tk.END, values=(m.name, value_a, value_b, delta, delta_pct)
            )

    def _export_report(self) -> None:
        """Export the diff report to a file."""
        if not self._diff_result:
            messagebox.showwarning("No Data", "Run a comparison first")
            return

        from tkinter import filedialog
        from tap_tone_pi.core.session_diff import format_diff_report

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json")],
            initialfile=f"diff_{self._diff_result.session_a}_vs_{self._diff_result.session_b}.txt",
        )

        if not filepath:
            return

        try:
            if filepath.endswith(".json"):
                with open(filepath, "w") as f:
                    json.dump(self._diff_result.to_dict(), f, indent=2)
            else:
                with open(filepath, "w") as f:
                    f.write(format_diff_report(self._diff_result))

            messagebox.showinfo("Exported", f"Report saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not save report: {e}")
