#!/usr/bin/env python3
"""
tap_tone_pi — Minimal GUI (Tkinter), measurement-only.

Migration: Canonical location is now tap_tone_pi.gui.app
           (previously gui/app.py)

Bug Fix: The binding bug in group() has been fixed. Form values are now
         captured at callback time, not at widget construction time.

Phase 6 Enhancements:
- Direct Python imports (no subprocess for core analysis)
- Matplotlib inline spectrum visualization

Phase 8 Enhancements (UI Polish):
- StatusBar for operation feedback
- AudioLevelMeter for real-time level visualization
- SetupWizardDialog for in-GUI hardware configuration
- CaptureProgressDialog for visual feedback during capture

Runs:
- Tap-tone (live / offline WAV)
- Bending stiffness → MOE (single / batch)
- Provenance hash
- Load cell capture (serial) → load_series.json
- Dial indicator capture (serial) → displacement_series.json
- Emit manifest.json

No advisory or design logic. Facts only.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from typing import TYPE_CHECKING

# Resolve project root
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DATA = ROOT / "data"

# Optional matplotlib for spectrum visualization
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Direct imports from tap_tone_pi (Phase 6 enhancement)
try:
    from tap_tone_pi.core.analysis import analyze_tap, AnalysisResult, Peak
    from tap_tone_pi.io.wav import read_wav_mono
    HAS_DIRECT_ANALYSIS = True
except ImportError:
    HAS_DIRECT_ANALYSIS = False

# Quality gate imports (Phase 7 enhancement)
try:
    from tap_tone_pi.core.quality_gate import check_quality, format_verdict_summary
    from tap_tone_pi.core.quality_policy import Verdict, QualityVerdict, Severity
    HAS_QUALITY_GATE = True
except ImportError:
    HAS_QUALITY_GATE = False

# UI widgets (Phase 8 enhancement)
try:
    from tap_tone_pi.gui.widgets import (
        StatusBar,
        StatusLevel,
        AudioLevelMeter,
        SetupWizardDialog,
        CaptureProgressDialog,
        SessionBrowserDialog,
        PackDiffDialog,
        ToolTip,
    )
    HAS_WIDGETS = True
except ImportError:
    HAS_WIDGETS = False

# Grid widgets (Phase 9 enhancement)
try:
    from tap_tone_pi.gui.grid_widgets import (
        GridEditorDialog,
        GridProgressPanel,
        GridMeasureDialog,
    )
    from tap_tone_pi.core.grid import Grid, GridSession, PointStatus
    HAS_GRID = True
except ImportError:
    HAS_GRID = False


class SpectrumViewer(tk.Toplevel):
    """Matplotlib spectrum viewer window (Phase 6 enhancement)."""
    
    def __init__(self, parent: tk.Tk, result: "AnalysisResult", title: str = "Spectrum") -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("800x500")
        
        if not HAS_MATPLOTLIB:
            tk.Label(self, text="matplotlib not installed").pack(pady=20)
            return
        
        # Create figure
        fig = Figure(figsize=(8, 4.5), dpi=100)
        ax = fig.add_subplot(111)
        
        # Plot spectrum
        freq = result.spectrum_freq_hz
        mag = result.spectrum_mag
        ax.semilogy(freq, mag + 1e-10, 'b-', linewidth=0.5, alpha=0.7)
        
        # Mark peaks
        for peak in result.peaks:
            ax.axvline(peak.freq_hz, color='r', linestyle='--', alpha=0.5, linewidth=0.8)
            ax.annotate(
                f"{peak.freq_hz:.1f} Hz",
                xy=(peak.freq_hz, peak.magnitude),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=8,
                color='red'
            )
        
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Magnitude (log scale)")
        ax.set_xlim(20, 2000)
        ax.set_title(f"Dominant: {result.dominant_hz:.1f} Hz | Confidence: {result.confidence:.2f}")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        
        # Embed in Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Info panel
        info_frame = tk.Frame(self)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        info_text = f"Peaks: {len(result.peaks)} | RMS: {result.rms:.4f} | Clipped: {result.clipped}"
        tk.Label(info_frame, text=info_text, font=("Courier", 10)).pack(side=tk.LEFT)
        
        tk.Button(info_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT)


class QualityVerdictViewer(tk.Toplevel):
    """
    Quality gate verdict viewer window (Phase 7 + Phase 8 enhancements).

    Phase 8 improvements:
    - Better visual hierarchy with icons
    - Color-coded rule list items
    - Improved button styling
    - Dominant frequency prominently displayed
    """

    def __init__(
        self,
        parent: tk.Tk,
        verdict: "QualityVerdict",
        result: "AnalysisResult",
        on_accept: callable = None,
        on_retry: callable = None,
        on_override: callable = None,
        title: str = "Quality Gate"
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("520x480")
        self.resizable(False, False)
        self.verdict = verdict
        self.on_accept = on_accept
        self.on_retry = on_retry
        self.on_override = on_override

        # Main frame with better padding
        main = tk.Frame(self, padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        # Verdict banner with icon
        if verdict.verdict == Verdict.PASS:
            banner_bg = "#4CAF50"  # Green
            banner_text = "PASS"
            banner_icon = "✓"
        elif verdict.verdict == Verdict.WARN:
            banner_bg = "#FF9800"  # Orange (better contrast than yellow)
            banner_text = "WARNING"
            banner_icon = "⚠"
        else:
            banner_bg = "#F44336"  # Red
            banner_text = "FAIL"
            banner_icon = "✗"

        banner_frame = tk.Frame(main, bg=banner_bg)
        banner_frame.pack(fill=tk.X, pady=(0, 15))

        banner = tk.Label(
            banner_frame,
            text=f" {banner_icon}  {banner_text}",
            bg=banner_bg,
            fg="white",
            font=("Helvetica", 28, "bold"),
            pady=12,
        )
        banner.pack(fill=tk.X)

        # Dominant frequency - prominently displayed
        freq_frame = tk.Frame(main, bg="#f5f5f5", relief=tk.GROOVE, bd=1)
        freq_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            freq_frame,
            text=f"{result.dominant_hz:.1f} Hz",
            font=("Helvetica", 32, "bold"),
            fg="#1976D2",
            bg="#f5f5f5",
            pady=8,
        ).pack()

        tk.Label(
            freq_frame,
            text="Dominant Frequency",
            font=("Helvetica", 10),
            fg="#666",
            bg="#f5f5f5",
            pady=(0, 8),
        ).pack()

        # Analysis summary in a grid
        summary_frame = tk.LabelFrame(main, text="Measurement Details", padx=10, pady=8)
        summary_frame.pack(fill=tk.X, pady=5)

        details = [
            ("RMS Level", f"{result.rms:.4f}"),
            ("Confidence", f"{result.confidence:.1%}"),
            ("Peak Count", str(len(result.peaks))),
            ("Clipping", "Yes ⚠" if result.clipped else "No ✓"),
        ]

        for i, (label, value) in enumerate(details):
            row = i // 2
            col = i % 2
            cell = tk.Frame(summary_frame)
            cell.grid(row=row, column=col, sticky="w", padx=10, pady=3)

            tk.Label(cell, text=f"{label}:", font=("Helvetica", 9, "bold"), fg="#555").pack(side=tk.LEFT)

            fg_color = "#d32f2f" if "⚠" in value else "#333"
            tk.Label(cell, text=f" {value}", font=("Helvetica", 9), fg=fg_color).pack(side=tk.LEFT)

        # Triggered rules with color coding
        if verdict.triggered_rules:
            rules_frame = tk.LabelFrame(main, text="Triggered Quality Rules", padx=8, pady=8)
            rules_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            # Create a canvas with scrollbar for the rules
            canvas = tk.Canvas(rules_frame, height=100, highlightthickness=0)
            scrollbar = tk.Scrollbar(rules_frame, orient=tk.VERTICAL, command=canvas.yview)
            rules_container = tk.Frame(canvas)

            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            canvas.create_window((0, 0), window=rules_container, anchor=tk.NW)

            for tr in verdict.triggered_rules:
                is_hard = tr.rule.severity == Severity.HARD
                rule_bg = "#ffebee" if is_hard else "#fff3e0"
                rule_fg = "#c62828" if is_hard else "#e65100"
                icon = "⛔" if is_hard else "⚡"

                rule_row = tk.Frame(rules_container, bg=rule_bg, pady=4, padx=6)
                rule_row.pack(fill=tk.X, pady=2)

                tk.Label(
                    rule_row,
                    text=f"{icon} [{tr.rule.rule_id}]",
                    font=("Courier", 9, "bold"),
                    fg=rule_fg,
                    bg=rule_bg,
                ).pack(side=tk.LEFT)

                tk.Label(
                    rule_row,
                    text=f" {tr.message}",
                    font=("Helvetica", 9),
                    fg="#333",
                    bg=rule_bg,
                    wraplength=380,
                    justify=tk.LEFT,
                ).pack(side=tk.LEFT, fill=tk.X)

            rules_container.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        else:
            # No rules triggered
            no_rules = tk.Label(
                main,
                text="✓ No quality rules triggered",
                font=("Helvetica", 10),
                fg="#4CAF50",
            )
            no_rules.pack(pady=10)

        # Action buttons with improved styling
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(15, 5))

        if verdict.verdict == Verdict.PASS:
            accept_btn = tk.Button(
                btn_frame,
                text="✓ Accept",
                command=self._do_accept,
                bg="#4CAF50",
                fg="white",
                font=("Helvetica", 11, "bold"),
                width=15,
                relief=tk.FLAT,
                cursor="hand2",
            )
            accept_btn.pack(side=tk.LEFT, padx=5)
        elif verdict.verdict == Verdict.WARN:
            accept_btn = tk.Button(
                btn_frame,
                text="Accept with Warnings",
                command=self._do_accept,
                bg="#FF9800",
                fg="white",
                font=("Helvetica", 10, "bold"),
                width=20,
                relief=tk.FLAT,
                cursor="hand2",
            )
            accept_btn.pack(side=tk.LEFT, padx=5)

            retry_btn = tk.Button(
                btn_frame,
                text="↻ Retry",
                command=self._do_retry,
                bg="#607D8B",
                fg="white",
                font=("Helvetica", 10),
                width=10,
                relief=tk.FLAT,
                cursor="hand2",
            )
            retry_btn.pack(side=tk.LEFT, padx=5)
        else:  # FAIL
            retry_btn = tk.Button(
                btn_frame,
                text="↻ Retry",
                command=self._do_retry,
                bg="#2196F3",
                fg="white",
                font=("Helvetica", 11, "bold"),
                width=15,
                relief=tk.FLAT,
                cursor="hand2",
            )
            retry_btn.pack(side=tk.LEFT, padx=5)

            override_btn = tk.Button(
                btn_frame,
                text="Override...",
                command=self._do_override,
                bg="#9E9E9E",
                fg="white",
                font=("Helvetica", 10),
                width=12,
                relief=tk.FLAT,
                cursor="hand2",
            )
            override_btn.pack(side=tk.LEFT, padx=5)

        close_btn = tk.Button(
            btn_frame,
            text="Close",
            command=self.destroy,
            font=("Helvetica", 10),
            width=8,
            cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, padx=5)

    def _do_accept(self) -> None:
        if self.on_accept:
            self.on_accept()
        self.destroy()

    def _do_retry(self) -> None:
        if self.on_retry:
            self.on_retry()
        self.destroy()

    def _do_override(self) -> None:
        reason = simpledialog.askstring(
            "Override Reason",
            "Enter reason for overriding the failed quality gate:\n\n"
            "(This will be recorded in the audit trail)",
            parent=self
        )
        if reason and reason.strip():
            if self.on_override:
                self.on_override(reason.strip())
            self.destroy()


def run(cmd: str) -> None:
    """Execute a shell command and show result dialog."""
    try:
        print("> " + cmd)
        subprocess.check_call(shlex.split(cmd))
        messagebox.showinfo("Done", f"Ran:\n{cmd}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Command failed ({e.returncode}):\n{cmd}")


def default_run_id() -> str:
    """Generate a default run ID from current timestamp."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")


class App(tk.Tk):
    """Main GUI application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("tap_tone_pi — Measurement GUI (v2.1.0)")
        self.geometry("680x600")
        self.run_id = tk.StringVar(value=default_run_id())

        # Menu bar
        self._create_menu()

        # Main content frame
        frm = tk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # Status bar at bottom (Phase 8)
        if HAS_WIDGETS:
            self.status_bar = StatusBar(self)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        else:
            self.status_bar = None

        # Run ID row with Setup button
        rrow = tk.Frame(frm)
        rrow.pack(fill="x", pady=4)
        tk.Label(rrow, text="Run ID (folder under out/)").pack(side="left")
        tk.Entry(rrow, textvariable=self.run_id, width=20).pack(side="left", padx=6)

        # Toolbar buttons (Phase 8)
        if HAS_WIDGETS:
            tk.Button(
                rrow,
                text="Setup Wizard",
                command=self.do_setup_wizard,
                bg="#9C27B0",
                fg="white",
            ).pack(side="right", padx=5)

            tk.Button(
                rrow,
                text="Compare",
                command=self.do_pack_diff,
                bg="#FF5722",
                fg="white",
            ).pack(side="right", padx=5)

            tk.Button(
                rrow,
                text="Browse Sessions",
                command=self.do_browse_sessions,
                bg="#607D8B",
                fg="white",
            ).pack(side="right", padx=5)

        # Grid Measurement button (Phase 9)
        if HAS_GRID:
            tk.Button(
                rrow,
                text="Grid Measure",
                command=self.do_grid_measure,
                bg="#00BCD4",
                fg="white",
            ).pack(side="right", padx=5)

        # --- Quality-gated measurement (Phase 7 - recommended)
        if HAS_QUALITY_GATE and HAS_DIRECT_ANALYSIS:
            self.measure_vars = group(frm, "Quality-Gated Measurement (recommended)", [
                ("Duration (s)", "2.5"),
                ("Sample rate", "48000"),
                ("Point ID", "point_001"),
            ], self.do_quality_measure)

        # --- Tap-tone live
        self.tap_live_vars = group(frm, "Tap-tone (live)", [
            ("Duration (s)", "4"),
            ("Sample rate", "44100")
        ], self.do_tap_live)

        # --- Tap-tone offline
        self.wav_path = tk.StringVar(value=str((DATA / "sample_tap.wav").as_posix()))
        group_file(frm, "Tap-tone (offline WAV)", self.wav_path, self.do_tap_offline)

        # --- MOE single (with entry vars for live capture)
        self.moe_vars: dict[str, tk.StringVar] = {}
        group_with_binds(frm, "Bending → MOE (single)", [
            ("method", "Method (3point/4point)", "3point"),
            ("span", "Span mm", "400"),
            ("width", "Width mm", "20"),
            ("thickness", "Thickness mm", "3.0"),
            ("force", "Force N", "5.0"),
            ("deflection", "Deflection mm", "0.62"),
            ("density", "Density g/cm^3 (optional)", ""),
        ], self.moe_vars, self.do_moe_single)

        # --- MOE batch
        self.csv_path = tk.StringVar(value=str((ROOT / "data/deflection_runs.csv").as_posix()))
        group_file(frm, "Bending → MOE (batch CSV)", self.csv_path, self.do_moe_batch)

        # --- Provenance hash
        self.prov_path = tk.StringVar(value=str((ROOT / "data/grain_field.png").as_posix()))
        group_file(frm, "Provenance import (hash only)", self.prov_path, self.do_provenance)

        # --- Load cell capture
        self.load_cfg = tk.StringVar(
            value=str((ROOT / "config/devices/loadcell_example.json").as_posix())
        )
        group_file(frm, "Load cell capture (serial) → load_series.json", self.load_cfg, self.do_loadcell)

        # --- Dial indicator capture
        self.dial_port = tk.StringVar(value="COM3" if os.name == "nt" else "/dev/ttyUSB0")
        group_entry(frm, "Dial indicator serial port", self.dial_port, self.do_dial)

        # --- Manifest
        tk.Button(
            frm,
            text="Emit manifest.json (hash everything in out/<RunID>)",
            command=self.do_manifest,
            width=50
        ).pack(pady=6)

        # --- Chladni Wizard
        tk.Button(
            frm,
            text="Chladni Wizard (WAV → peaks → images → run + manifest)",
            command=self.do_chladni_wizard,
            width=50
        ).pack(pady=4)

    def _create_menu(self) -> None:
        """Create the application menu bar with keyboard shortcuts."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        if HAS_WIDGETS:
            file_menu.add_command(
                label="Browse Sessions...",
                command=self.do_browse_sessions,
                accelerator="Ctrl+B",
            )
        file_menu.add_command(
            label="Open Output Folder",
            command=self._open_output_folder,
            accelerator="Ctrl+O",
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit, accelerator="Ctrl+Q")

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        if HAS_WIDGETS:
            tools_menu.add_command(
                label="Setup Wizard...",
                command=self.do_setup_wizard,
                accelerator="Ctrl+W",
            )
            tools_menu.add_command(
                label="Compare Sessions...",
                command=self.do_pack_diff,
                accelerator="Ctrl+D",
            )
            tools_menu.add_separator()
        if HAS_GRID:
            tools_menu.add_command(label="Grid Editor...", command=self.do_grid_editor)
            tools_menu.add_command(
                label="Grid Measurement...",
                command=self.do_grid_measure,
                accelerator="Ctrl+G",
            )
            tools_menu.add_separator()
        tools_menu.add_command(label="Chladni Wizard...", command=self.do_chladni_wizard)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about, accelerator="F1")

        # Bind keyboard shortcuts
        self._bind_shortcuts()

    def _open_output_folder(self) -> None:
        """Open the output folder in file manager."""
        import subprocess
        import platform

        folder = self.outdir()
        if platform.system() == "Windows":
            subprocess.run(["explorer", str(folder)])
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    def _show_about(self) -> None:
        """Show about dialog."""
        messagebox.showinfo(
            "About tap_tone_pi",
            "tap_tone_pi — Measurement GUI\n"
            "Version 2.1.0\n\n"
            "Acoustic measurement and quality control\n"
            "for lutherie applications.\n\n"
            "Grid + Quality Gate"
        )

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts to commands."""
        # File menu shortcuts
        if HAS_WIDGETS:
            self.bind_all("<Control-b>", lambda e: self.do_browse_sessions())
        self.bind_all("<Control-o>", lambda e: self._open_output_folder())
        self.bind_all("<Control-q>", lambda e: self.quit())

        # Tools menu shortcuts
        if HAS_WIDGETS:
            self.bind_all("<Control-w>", lambda e: self.do_setup_wizard())
            self.bind_all("<Control-d>", lambda e: self.do_pack_diff())
        if HAS_GRID:
            self.bind_all("<Control-g>", lambda e: self.do_grid_measure())

        # Help
        self.bind_all("<F1>", lambda e: self._show_about())

    def _set_status(self, text: str, level: str = "info") -> None:
        """Set status bar message."""
        if self.status_bar:
            level_map = {
                "info": StatusLevel.INFO,
                "success": StatusLevel.SUCCESS,
                "warning": StatusLevel.WARNING,
                "error": StatusLevel.ERROR,
                "progress": StatusLevel.PROGRESS,
            }
            self.status_bar.set(text, level_map.get(level, StatusLevel.INFO))

    def do_setup_wizard(self) -> None:
        """Open the hardware setup wizard."""
        if not HAS_WIDGETS:
            messagebox.showerror("Error", "Widgets module not available")
            return

        def on_complete(device_config):
            self._set_status(f"Configured: {device_config.name}", "success")

        SetupWizardDialog(self, on_complete=on_complete)

    def do_browse_sessions(self) -> None:
        """Open the session browser dialog."""
        if not HAS_WIDGETS:
            messagebox.showerror("Error", "Widgets module not available")
            return

        def on_session_selected(session_info):
            # Set the run ID to the selected session
            self.run_id.set(session_info.name)
            self._set_status(f"Selected: {session_info.name}", "success")

        SessionBrowserDialog(
            self,
            output_dir=OUT,
            on_session_selected=on_session_selected,
        )

    def do_pack_diff(self) -> None:
        """Open the pack diff dialog for comparing sessions."""
        if not HAS_WIDGETS:
            messagebox.showerror("Error", "Widgets module not available")
            return

        # Pre-select current run if it exists
        current_run = self.run_id.get().strip()
        initial_b = current_run if (OUT / current_run).exists() else None

        PackDiffDialog(
            self,
            output_dir=OUT,
            initial_session_b=initial_b,
        )

    def do_grid_editor(self) -> None:
        """Open the grid editor dialog (Phase 9)."""
        if not HAS_GRID:
            messagebox.showerror("Error", "Grid module not available")
            return

        def on_save(grid: Grid):
            # Save grid to output directory
            grid_path = self.outdir() / f"{grid.grid_id}.json"
            grid.save(grid_path)
            self._set_status(f"Grid saved: {grid.name}", "success")
            messagebox.showinfo("Grid Saved", f"Grid saved to:\n{grid_path}")

        GridEditorDialog(self, on_save=on_save)

    def do_grid_measure(self) -> None:
        """Open the grid measurement dialog (Phase 9)."""
        if not HAS_GRID:
            messagebox.showerror("Error", "Grid module not available")
            return

        # Check if quality gate is available
        if not HAS_QUALITY_GATE or not HAS_DIRECT_ANALYSIS:
            messagebox.showerror("Error", "Quality gate modules required for grid measurement")
            return

        # Ask user to select or create a grid
        choice = messagebox.askyesnocancel(
            "Grid Measurement",
            "Do you want to create a new grid?\n\n"
            "Yes = Create new grid\n"
            "No = Load existing grid\n"
            "Cancel = Cancel"
        )

        if choice is None:
            return

        grid = None
        if choice:  # Create new grid
            def on_grid_created(g: Grid):
                nonlocal grid
                grid = g

            editor = GridEditorDialog(self, on_save=on_grid_created)
            self.wait_window(editor)
        else:  # Load existing grid
            filepath = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Load Grid",
                initialdir=str(self.outdir()),
            )
            if not filepath:
                return
            try:
                grid = Grid.load(pathlib.Path(filepath))
            except Exception as e:
                messagebox.showerror("Error", f"Could not load grid: {e}")
                return

        if not grid:
            return

        # Create a new session
        session_id = f"{self.run_id.get()}_{grid.grid_id}"
        session = GridSession(session_id=session_id, grid=grid)

        # Define measurement callback
        def on_measure(point_id: str):
            self._do_grid_point_measure(session, point_id, measure_dlg)

        def on_skip(point_id: str):
            session.mark_skipped(point_id)
            self._set_status(f"Skipped {point_id}", "info")

        def on_retry(point_id: str):
            session.reset_point(point_id)
            on_measure(point_id)

        def on_complete(s: GridSession):
            # Save session
            session_path = self.outdir() / f"session_{s.session_id}.json"
            s.save(session_path)
            self._set_status(f"Grid session complete: {s.completed_count}/{s.total_points}", "success")
            messagebox.showinfo(
                "Session Complete",
                f"All {s.total_points} points measured!\n\nSession saved to:\n{session_path}"
            )

        # Open the measurement dialog
        measure_dlg = GridMeasureDialog(
            self,
            session=session,
            on_measure=on_measure,
            on_skip=on_skip,
            on_retry=on_retry,
            on_complete=on_complete,
        )

    def _do_grid_point_measure(self, session: "GridSession", point_id: str, measure_dlg) -> None:
        """Perform measurement for a single grid point."""
        from tap_tone_pi.capture import record_audio
        from tap_tone_pi.core.user_config import get_saved_device

        outdir = self.outdir()

        # Get measurement parameters (use defaults)
        duration = 2.5
        sample_rate = 48000

        saved = get_saved_device()
        device = saved.index if saved else None
        if saved:
            sample_rate = saved.sample_rate

        # Create point directory
        point_dir = outdir / point_id
        point_dir.mkdir(parents=True, exist_ok=True)

        # Find next attempt number
        existing = [d for d in point_dir.iterdir() if d.name.startswith("attempt_")] if point_dir.exists() else []
        attempt_num = len(existing) + 1
        attempt_dir = point_dir / f"attempt_{attempt_num:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._set_status(f"Capturing {point_id}...", "progress")
            self.update()

            cap = record_audio(
                device=device,
                sample_rate=sample_rate,
                channels=1,
                seconds=duration,
            )

            self._set_status(f"Analyzing {point_id}...", "progress")
            self.update()

            result = analyze_tap(cap.audio, cap.sample_rate)
            verdict = check_quality(
                analysis=result,
                sample_rate=cap.sample_rate,
                audio=cap.audio,
            )

            # Save audio and analysis
            from scipy.io import wavfile
            wavfile.write(str(attempt_dir / "audio.wav"), cap.sample_rate, cap.audio)

            with open(attempt_dir / "analysis.json", "w") as f:
                json.dump({
                    "dominant_hz": result.dominant_hz,
                    "rms": float(result.rms),
                    "confidence": float(result.confidence),
                    "clipped": result.clipped,
                }, f, indent=2)

            # Update session based on verdict
            if verdict.verdict == Verdict.PASS:
                session.mark_passed(point_id, result.dominant_hz)
                status = "passed"
                self._set_status(f"{point_id}: PASSED ({result.dominant_hz:.1f} Hz)", "success")
            elif verdict.verdict == Verdict.WARN:
                session.mark_warned(point_id, result.dominant_hz)
                status = "warned"
                self._set_status(f"{point_id}: WARNING ({result.dominant_hz:.1f} Hz)", "warning")
            else:
                session.mark_failed(point_id)
                status = "failed"
                self._set_status(f"{point_id}: FAILED", "error")

            # Update the dialog
            measure_dlg.update_point_result(point_id, status, result.dominant_hz)

        except Exception as e:
            session.mark_failed(point_id)
            self._set_status(f"Error measuring {point_id}: {e}", "error")
            measure_dlg.update_point_result(point_id, "failed", None)

    def outdir(self) -> pathlib.Path:
        """Get or create the output directory for current run."""
        p = OUT / self.run_id.get().strip()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # --- Callbacks ---

    def do_quality_measure(self, entry_vars: list[tk.StringVar]) -> None:
        """Run quality-gated measurement (Phase 7 + Phase 8 enhancements)."""
        if not HAS_QUALITY_GATE or not HAS_DIRECT_ANALYSIS:
            messagebox.showerror("Error", "Quality gate modules not available")
            return

        from tap_tone_pi.capture import record_audio
        from tap_tone_pi.core.user_config import get_saved_device

        outdir = self.outdir()
        duration = float(entry_vars[0].get())
        sample_rate = int(entry_vars[1].get())
        point_id = entry_vars[2].get().strip() or "point_001"

        # Try to use saved device
        saved = get_saved_device()
        device = saved.index if saved else None
        if saved:
            sample_rate = saved.sample_rate

        # Create point directory
        point_dir = outdir / point_id
        point_dir.mkdir(parents=True, exist_ok=True)

        # Find next attempt number
        existing = [d for d in point_dir.iterdir() if d.name.startswith("attempt_")] if point_dir.exists() else []
        attempt_num = len(existing) + 1
        attempt_dir = point_dir / f"attempt_{attempt_num:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        # Phase 8: Show progress dialog
        progress_dlg = None
        if HAS_WIDGETS:
            progress_dlg = CaptureProgressDialog(
                self,
                title=f"Capturing: {point_id} (attempt {attempt_num})"
            )

        try:
            # Stage 0: Preflight
            self._set_status(f"Preflight check for {point_id}...", "progress")
            if progress_dlg:
                progress_dlg.set_stage(0, "Checking device...")
                self.update()

            # Stage 1: Capture
            self._set_status(f"Capturing {point_id}...", "progress")
            if progress_dlg:
                progress_dlg.set_stage(1, f"Recording for {duration}s...")
                self.update()

            cap = record_audio(
                device=device,
                sample_rate=sample_rate,
                channels=1,
                seconds=duration,
            )

            # Stage 2: Analyze
            self._set_status(f"Analyzing {point_id}...", "progress")
            if progress_dlg:
                progress_dlg.set_stage(2, "Running FFT analysis...")
                self.update()

            result = analyze_tap(cap.audio, cap.sample_rate)

            # Stage 3: Quality check
            self._set_status(f"Quality check for {point_id}...", "progress")
            if progress_dlg:
                progress_dlg.set_stage(3, "Evaluating quality rules...")
                self.update()

            verdict = check_quality(
                analysis=result,
                sample_rate=cap.sample_rate,
                audio=cap.audio,
            )

            # Close progress dialog
            if progress_dlg:
                progress_dlg.destroy()
                progress_dlg = None

            # Save audio
            from scipy.io import wavfile
            audio_path = attempt_dir / "audio.wav"
            wavfile.write(str(audio_path), cap.sample_rate, cap.audio)

            # Save analysis
            analysis_path = attempt_dir / "analysis.json"
            with open(analysis_path, "w") as f:
                json.dump({
                    "dominant_hz": result.dominant_hz,
                    "rms": float(result.rms),
                    "confidence": float(result.confidence),
                    "clipped": result.clipped,
                    "peaks": [{"freq_hz": p.freq_hz, "magnitude": float(p.magnitude)} for p in result.peaks[:20]],
                }, f, indent=2)

            # Save quality check
            quality_path = attempt_dir / "quality_check.json"
            with open(quality_path, "w") as f:
                json.dump(verdict.to_dict(), f, indent=2)

            # Update status based on verdict
            if verdict.verdict == Verdict.PASS:
                self._set_status(f"{point_id}: PASSED ({result.dominant_hz:.1f} Hz)", "success")
            elif verdict.verdict == Verdict.WARN:
                self._set_status(f"{point_id}: WARNING - review required", "warning")
            else:
                self._set_status(f"{point_id}: FAILED - retry or override", "error")

            # Show verdict viewer
            def on_accept():
                self._set_status(f"{point_id} accepted", "success")
                messagebox.showinfo("Accepted", f"Measurement saved to:\n{attempt_dir}")
                # Show spectrum too
                if HAS_MATPLOTLIB:
                    SpectrumViewer(self, result, title=f"Spectrum: {point_id}")

            def on_retry():
                # Re-run the measurement
                self.do_quality_measure(entry_vars)

            def on_override(reason: str):
                # Save override reason
                override_path = attempt_dir / "override.json"
                with open(override_path, "w") as f:
                    json.dump({"reason": reason, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}, f, indent=2)
                self._set_status(f"{point_id} overridden", "warning")
                messagebox.showinfo("Overridden", f"Measurement overridden and saved to:\n{attempt_dir}")

            QualityVerdictViewer(
                self,
                verdict=verdict,
                result=result,
                on_accept=on_accept,
                on_retry=on_retry,
                on_override=on_override,
                title=f"Quality Gate: {point_id} (attempt {attempt_num})"
            )

        except Exception as e:
            if progress_dlg:
                progress_dlg.destroy()
            self._set_status(f"Error: {e}", "error")
            messagebox.showerror("Error", f"Measurement failed: {e}")

    def do_tap_live(self, entry_vars: list[tk.StringVar]) -> None:
        """Run live tap-tone capture."""
        outdir = self.outdir()
        dur = entry_vars[0].get()
        sr = entry_vars[1].get()
        cmd = (
            f"python modes/tap_tone/tap_fft_logger.py "
            f"--outfile {outdir/'tap_tone.json'} "
            f"--plot {outdir/'spectrum.png'} "
            f"--duration {dur} --sr {sr} --labels A0 T11 B11"
        )
        run(cmd)

    def do_tap_offline(self, path_var: tk.StringVar) -> None:
        """Run offline tap-tone analysis on a WAV file.
        
        Phase 6 Enhancement: Uses direct Python imports when available,
        with inline matplotlib spectrum visualization.
        """
        wav_path = pathlib.Path(path_var.get())
        outdir = self.outdir()
        
        if HAS_DIRECT_ANALYSIS and HAS_MATPLOTLIB:
            # Direct analysis with spectrum viewer (Phase 6)
            try:
                audio, sr = read_wav_mono(wav_path)
                result = analyze_tap(audio, sr)
                
                # Save JSON result
                out_json = outdir / "tap_tone_offline.json"
                result_dict = {
                    "dominant_hz": result.dominant_hz,
                    "peaks": [{"freq_hz": p.freq_hz, "magnitude": p.magnitude} for p in result.peaks],
                    "clipped": result.clipped,
                    "rms": result.rms,
                    "confidence": result.confidence,
                    "source_wav": str(wav_path),
                }
                with open(out_json, "w") as f:
                    json.dump(result_dict, f, indent=2)
                
                # Show spectrum viewer
                SpectrumViewer(self, result, title=f"Spectrum: {wav_path.name}")
                messagebox.showinfo("Done", f"Analysis saved to:\n{out_json}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Analysis failed: {e}")
        else:
            # Fallback to subprocess
            cmd = (
                f"python modes/tap_tone/offline_from_wav.py "
                f"--wav {path_var.get()} "
                f"--outfile {outdir/'tap_tone_offline.json'} --labels A0 T11 B11"
            )
            run(cmd)

    def do_moe_single(self, var_dict: dict[str, tk.StringVar]) -> None:
        """Calculate MOE from single measurement.
        
        BUG FIX: Now reads .get() at callback time, not construction time.
        """
        outdir = self.outdir()
        # Read current values from StringVars at callback time
        method = var_dict["method"].get()
        span = var_dict["span"].get()
        width = var_dict["width"].get()
        thickness = var_dict["thickness"].get()
        force = var_dict["force"].get()
        deflection = var_dict["deflection"].get()
        density = var_dict["density"].get()
        
        cmd = (
            f"python modes/bending_stiffness/deflection_to_moe.py "
            f"--method {method} --span {span} --width {width} "
            f"--thickness {thickness} --force {force} --deflection {deflection} "
            f"--out {outdir/'bending_test.json'}"
        )
        if density.strip():
            cmd += f" --density {density}"
        run(cmd)

    def do_moe_batch(self, path_var: tk.StringVar) -> None:
        """Calculate MOE from batch CSV."""
        outdir = self.outdir()
        cmd = (
            f"python modes/bending_stiffness/deflection_to_moe.py "
            f"--csv {path_var.get()} --out {outdir/'moe_results.csv'}"
        )
        run(cmd)

    def do_provenance(self, path_var: tk.StringVar) -> None:
        """Hash a file for provenance tracking."""
        outdir = self.outdir()
        cmd = (
            f"python modes/provenance_import/attach_grain_provenance.py "
            f"--file {path_var.get()} --out {outdir/'provenance.json'}"
        )
        run(cmd)

    def do_loadcell(self, cfg_var: tk.StringVar) -> None:
        """Capture load cell data via serial."""
        outdir = self.outdir()
        cmd = (
            f"python modes/acquisition/loadcell_serial.py "
            f"--config {cfg_var.get()} --out {outdir/'load_series.json'}"
        )
        run(cmd)

    def do_dial(self, port_var: tk.StringVar) -> None:
        """Capture dial indicator data via serial."""
        outdir = self.outdir()
        cmd = (
            f"python modes/acquisition/dial_indicator_serial.py "
            f"--port {port_var.get()} --out {outdir/'displacement_series.json'}"
        )
        run(cmd)

    def do_manifest(self) -> None:
        """Emit manifest.json for all artifacts in run directory."""
        outdir = self.outdir()
        artifacts = []
        for p in sorted(outdir.glob("*")):
            if p.suffix.lower() in {".json", ".csv", ".png", ".wav"}:
                artifacts += ["--artifact", p.as_posix()]
        rig = ["--rig", "operator=Shop"]
        cmd = [
            "python", "modes/_shared/emit_manifest.py",
            "--out", (outdir / "manifest.json").as_posix(),
            *artifacts, *rig
        ]
        run(" ".join(shlex.quote(c) for c in cmd))

    def do_chladni_wizard(self) -> None:
        """
        Chladni pattern analysis wizard:
        1) Ask for a sweep/stepped-tone WAV
        2) Run peaks_from_wav.py → peaks.json
        3) Multi-select Chladni images (F####.png/JPG filenames embed Hz)
        4) Ask Plate ID + (optional) Temp/RH
        5) Run index_patterns.py → chladni_run.json
        6) Emit manifest.json for the Chladni set
        """
        try:
            run_dir = self.outdir() / "chladni"
            run_dir.mkdir(parents=True, exist_ok=True)

            # 1) Pick WAV
            wav_path = filedialog.askopenfilename(
                title="Select Chladni sweep WAV",
                filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
            )
            if not wav_path:
                return

            peaks_json = run_dir / "peaks.json"

            # 2) Run peaks_from_wav.py
            cmd_peaks = [
                sys.executable, "-m", "tap_tone_pi.chladni.peaks_from_wav",
                "--wav", wav_path,
                "--out", peaks_json.as_posix(),
                "--min-hz", "50", "--max-hz", "2000", "--prominence", "0.02"
            ]
            subprocess.check_call(cmd_peaks, cwd=str(ROOT))

            # 3) Pick images (multi-select)
            img_paths = filedialog.askopenfilenames(
                title="Select Chladni pattern images (name like F0148.png)",
                filetypes=[
                    ("Images", "*.png;*.jpg;*.jpeg;*.PNG;*.JPG;*.JPEG"),
                    ("All files", "*.*")
                ]
            )
            if not img_paths:
                messagebox.showwarning(
                    "No images selected",
                    "Peaks were extracted, but no images were chosen."
                )
                return

            # 4) Plate ID + Env
            default_plate = f"{self.run_id.get()}_PLATE"
            plate_id = simpledialog.askstring(
                "Plate ID", "Enter plate ID:", initialvalue=default_plate
            ) or default_plate
            
            try:
                temp_str = simpledialog.askstring(
                    "Temperature (C)", "Enter temperature C (optional):", initialvalue=""
                )
                temp_c = float(temp_str) if temp_str else None
            except (TypeError, ValueError):
                temp_c = None
            
            try:
                rh_str = simpledialog.askstring(
                    "RH (%)", "Enter relative humidity % (optional):", initialvalue=""
                )
                rh = float(rh_str) if rh_str else None
            except (TypeError, ValueError):
                rh = None

            chladni_run_json = run_dir / "chladni_run.json"

            # 5) Run index_patterns.py
            cmd_idx = [
                sys.executable, "-m", "tap_tone_pi.chladni.index_patterns",
                "--peaks-json", peaks_json.as_posix(),
                "--plate-id", plate_id,
                "--out", chladni_run_json.as_posix(),
                "--images",
            ]
            cmd_idx += [pathlib.Path(p).as_posix() for p in img_paths]
            if temp_c is not None:
                cmd_idx += ["--tempC", str(temp_c)]
            if rh is not None:
                cmd_idx += ["--rh", str(rh)]

            subprocess.check_call(cmd_idx, cwd=str(ROOT))

            # 6) Emit manifest
            manifest_json = run_dir / "manifest.json"
            art_args = [
                "--artifact", peaks_json.as_posix(),
                "--artifact", chladni_run_json.as_posix(),
                "--artifact", pathlib.Path(wav_path).as_posix(),
            ]
            for p in img_paths:
                art_args += ["--artifact", pathlib.Path(p).as_posix()]

            rig_kvs = ["--rig", f"plate_id={plate_id}"]
            notes = ["--notes", f"Chladni v1 wizard (run={self.outdir().name})"]

            cmd_manifest = [
                sys.executable, "modes/_shared/emit_manifest.py",
                "--out", manifest_json.as_posix(),
                *art_args, *rig_kvs, *notes
            ]
            subprocess.check_call(cmd_manifest, cwd=str(ROOT))

            messagebox.showinfo(
                "Chladni v1",
                f"Peaks: {peaks_json}\nRun: {chladni_run_json}\nManifest: {manifest_json}"
            )

        except subprocess.CalledProcessError as e:
            messagebox.showerror("Chladni wizard failed", f"Step failed with exit code {e.returncode}")
        except Exception as ex:
            messagebox.showerror("Chladni wizard error", str(ex))


# --- Helper functions for building form groups ---

def group(
    parent: tk.Widget,
    title: str,
    fields: list[tuple[str, str]],
    callback
) -> list[tk.StringVar]:
    """
    Create a labeled frame with entry fields and a Run button.
    
    Returns the list of StringVars so they can be read at callback time.
    The callback receives this list and should call .get() on each var.
    """
    f = tk.LabelFrame(parent, text=title)
    f.pack(fill="x", pady=4)
    
    entry_vars: list[tk.StringVar] = []
    for label, default in fields:
        row = tk.Frame(f)
        row.pack(fill="x")
        tk.Label(row, text=label, width=28, anchor="w").pack(side="left")
        var = tk.StringVar(value=default)
        tk.Entry(row, textvariable=var, width=16).pack(side="left")
        entry_vars.append(var)
    
    # Pass the list of vars to callback - caller reads .get() at call time
    tk.Button(f, text="Run", command=lambda: callback(entry_vars)).pack(pady=3)
    return entry_vars


def group_with_binds(
    parent: tk.Widget,
    title: str,
    fields: list[tuple[str, str, str]],  # (key, label, default)
    var_dict: dict[str, tk.StringVar],
    callback
) -> None:
    """
    Create a labeled frame with named entry fields.
    
    BUG FIX: Stores StringVar objects in var_dict, not their values.
    The callback receives var_dict and should call var.get() at call time.
    
    Args:
        fields: List of (key, label, default) tuples
        var_dict: Dictionary to populate with key -> StringVar mappings
        callback: Function to call with var_dict on Run button click
    """
    f = tk.LabelFrame(parent, text=title)
    f.pack(fill="x", pady=4)
    
    for key, label, default in fields:
        row = tk.Frame(f)
        row.pack(fill="x")
        tk.Label(row, text=label, width=28, anchor="w").pack(side="left")
        var = tk.StringVar(value=default)
        tk.Entry(row, textvariable=var, width=16).pack(side="left")
        # Store the StringVar, not its current value
        var_dict[key] = var
    
    tk.Button(f, text="Run", command=lambda: callback(var_dict)).pack(pady=3)


def group_file(
    parent: tk.Widget,
    title: str,
    path_var: tk.StringVar,
    callback
) -> None:
    """Create a labeled frame with file path entry and browse button."""
    f = tk.LabelFrame(parent, text=title)
    f.pack(fill="x", pady=4)
    
    row = tk.Frame(f)
    row.pack(fill="x")
    tk.Entry(row, textvariable=path_var, width=48).pack(side="left")
    tk.Button(
        row,
        text="Browse",
        command=lambda: path_var.set(filedialog.askopenfilename() or path_var.get())
    ).pack(side="left", padx=6)
    
    tk.Button(f, text="Run", command=lambda: callback(path_var)).pack(pady=3)


def group_entry(
    parent: tk.Widget,
    title: str,
    var: tk.StringVar,
    callback
) -> None:
    """Create a labeled frame with a single entry field."""
    f = tk.LabelFrame(parent, text=title)
    f.pack(fill="x", pady=4)
    
    row = tk.Frame(f)
    row.pack(fill="x")
    tk.Entry(row, textvariable=var, width=32).pack(side="left")
    
    tk.Button(f, text="Run", command=lambda: callback(var)).pack(pady=3)


if __name__ == "__main__":
    App().mainloop()
