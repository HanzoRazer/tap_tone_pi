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

Phase 10 Enhancements (Auto-Trigger):
- Auto-trigger checkbox in Quality-Gated Measurement section
- Listening state visual feedback
- Automatic tap onset detection

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
import tkinter as tk
from tkinter import filedialog, messagebox

# Resolve project root
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DATA = ROOT / "data"

# Optional matplotlib for spectrum visualization
try:
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: F401
    from matplotlib.figure import Figure  # noqa: F401

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Direct imports from tap_tone_pi (Phase 6 enhancement)
try:
    from tap_tone_pi.core.analysis import analyze_tap, AnalysisResult, Peak  # noqa: F401
    from tap_tone_pi.io.wav import read_wav_mono

    HAS_DIRECT_ANALYSIS = True
except ImportError:
    HAS_DIRECT_ANALYSIS = False

# Quality gate imports (Phase 7 enhancement)
try:
    from tap_tone_pi.core.quality_gate import check_quality, format_verdict_summary  # noqa: F401
    from tap_tone_pi.core.quality_policy import Verdict, QualityVerdict, Severity  # noqa: F401

    HAS_QUALITY_GATE = True
except ImportError:
    HAS_QUALITY_GATE = False

# Auto-trigger imports (Phase 10 enhancement)
try:
    from tap_tone_pi.core.auto_trigger import (
        record_audio_triggered,
        TriggerState,
        TriggerResult,  # noqa: F401
    )

    HAS_AUTO_TRIGGER = True
except ImportError:
    HAS_AUTO_TRIGGER = False

# UI widgets (Phase 8 enhancement)
try:
    from tap_tone_pi.gui.widgets import (
        StatusBar,
        StatusLevel,
        AudioLevelMeter,  # noqa: F401
        SetupWizardDialog,
        CaptureProgressDialog,  # noqa: F401
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
        GridProgressPanel,  # noqa: F401
        GridMeasureDialog,
    )
    from tap_tone_pi.core.grid import Grid, GridSession, PointStatus  # noqa: F401

    HAS_GRID = True
except ImportError:
    HAS_GRID = False

# Viewer pack export (Phase 11 enhancement)
try:
    from tap_tone_pi.gui.export import export_gui_session, ExportResult  # noqa: F401

    HAS_EXPORT = True
except ImportError:
    HAS_EXPORT = False

# Timeline viewer (PR #18 enhancement)
try:
    from tap_tone_pi.gui.timeline_viewer import TimelineViewerDialog

    HAS_TIMELINE_VIEWER = True
except ImportError:
    HAS_TIMELINE_VIEWER = False


# --- Extracted to quality_verdict.py (Phase 4 restructuring) ---
from tap_tone_pi.gui.quality_verdict import (  # noqa: E402
    SpectrumViewer,
    QualityVerdictViewer,  # noqa: F401 — used by measurement_flow
)


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
        self.title("tap_tone_pi — Measurement GUI (v2.2.0)")
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

        # Toolbar buttons (Phase 8) with tooltips
        if HAS_WIDGETS:
            btn_setup = tk.Button(
                rrow,
                text="Setup Wizard",
                command=self.do_setup_wizard,
                bg="#9C27B0",
                fg="white",
            )
            btn_setup.pack(side="right", padx=5)
            ToolTip(btn_setup, "Configure audio hardware (Ctrl+W)")

            btn_compare = tk.Button(
                rrow,
                text="Compare",
                command=self.do_pack_diff,
                bg="#FF5722",
                fg="white",
            )
            btn_compare.pack(side="right", padx=5)
            ToolTip(btn_compare, "Compare two sessions (Ctrl+D)")

            btn_browse = tk.Button(
                rrow,
                text="Browse Sessions",
                command=self.do_browse_sessions,
                bg="#607D8B",
                fg="white",
            )
            btn_browse.pack(side="right", padx=5)
            ToolTip(btn_browse, "Browse past measurement sessions (Ctrl+B)")

        # Grid Measurement button (Phase 9)
        if HAS_GRID:
            btn_grid = tk.Button(
                rrow,
                text="Grid Measure",
                command=self.do_grid_measure,
                bg="#00BCD4",
                fg="white",
            )
            btn_grid.pack(side="right", padx=5)
            if HAS_WIDGETS:
                ToolTip(btn_grid, "Multi-point grid measurement (Ctrl+G)")

        # Export Viewer Pack button (Phase 11)
        if HAS_EXPORT:
            btn_export = tk.Button(
                rrow,
                text="Export Pack",
                command=self.do_export_viewer_pack,
                bg="#8BC34A",
                fg="white",
            )
            btn_export.pack(side="right", padx=5)
            if HAS_WIDGETS:
                ToolTip(btn_export, "Export session as viewer pack ZIP (Ctrl+E)")

        # --- Quality-gated measurement (Phase 7 - recommended)
        if HAS_QUALITY_GATE and HAS_DIRECT_ANALYSIS:
            # Create custom frame to include auto-trigger checkbox
            measure_frame = tk.LabelFrame(
                frm, text="Quality-Gated Measurement (recommended)"
            )
            measure_frame.pack(fill="x", pady=4)

            # Standard entry fields
            self.measure_vars: list[tk.StringVar] = []
            for label, default in [
                ("Duration (s)", "2.5"),
                ("Sample rate", "48000"),
                ("Point ID", "point_001"),
            ]:
                row = tk.Frame(measure_frame)
                row.pack(fill="x")
                tk.Label(row, text=label, width=28, anchor="w").pack(side="left")
                var = tk.StringVar(value=default)
                tk.Entry(row, textvariable=var, width=16).pack(side="left")
                self.measure_vars.append(var)

            # Auto-trigger checkbox (Phase 10)
            self.auto_trigger_var = tk.BooleanVar(value=False)
            trigger_row = tk.Frame(measure_frame)
            trigger_row.pack(fill="x", pady=(4, 0))

            trigger_cb = tk.Checkbutton(
                trigger_row,
                text="Auto-trigger (wait for tap)",
                variable=self.auto_trigger_var,
                command=self._on_auto_trigger_toggle,
            )
            trigger_cb.pack(side="left", padx=4)

            # Auto-trigger indicator label (Phase 10)
            self.trigger_status_label = tk.Label(
                trigger_row,
                text="",
                font=("Helvetica", 9),
                fg="#666",
            )
            self.trigger_status_label.pack(side="left", padx=10)

            # Disable if auto-trigger not available
            if not HAS_AUTO_TRIGGER:
                trigger_cb.configure(state=tk.DISABLED)
                self.trigger_status_label.configure(
                    text="(sounddevice required)", fg="#999"
                )

            tk.Button(
                measure_frame,
                text="Run",
                command=lambda: self.do_quality_measure(self.measure_vars),
            ).pack(pady=3)

        # --- Tap-tone live
        self.tap_live_vars = group(
            frm,
            "Tap-tone (live)",
            [("Duration (s)", "4"), ("Sample rate", "44100")],
            self.do_tap_live,
        )

        # --- Tap-tone offline
        self.wav_path = tk.StringVar(value=str((DATA / "sample_tap.wav").as_posix()))
        group_file(frm, "Tap-tone (offline WAV)", self.wav_path, self.do_tap_offline)

        # --- MOE single (with entry vars for live capture)
        self.moe_vars: dict[str, tk.StringVar] = {}
        group_with_binds(
            frm,
            "Bending → MOE (single)",
            [
                ("method", "Method (3point/4point)", "3point"),
                ("span", "Span mm", "400"),
                ("width", "Width mm", "20"),
                ("thickness", "Thickness mm", "3.0"),
                ("force", "Force N", "5.0"),
                ("deflection", "Deflection mm", "0.62"),
                ("density", "Density g/cm^3 (optional)", ""),
            ],
            self.moe_vars,
            self.do_moe_single,
        )

        # --- MOE batch
        self.csv_path = tk.StringVar(
            value=str((ROOT / "data/deflection_runs.csv").as_posix())
        )
        group_file(frm, "Bending → MOE (batch CSV)", self.csv_path, self.do_moe_batch)

        # --- Provenance hash
        self.prov_path = tk.StringVar(
            value=str((ROOT / "data/grain_field.png").as_posix())
        )
        group_file(
            frm, "Provenance import (hash only)", self.prov_path, self.do_provenance
        )

        # --- Load cell capture
        self.load_cfg = tk.StringVar(
            value=str((ROOT / "config/devices/loadcell_example.json").as_posix())
        )
        group_file(
            frm,
            "Load cell capture (serial) → load_series.json",
            self.load_cfg,
            self.do_loadcell,
        )

        # --- Dial indicator capture
        self.dial_port = tk.StringVar(
            value="COM3" if os.name == "nt" else "/dev/ttyUSB0"
        )
        group_entry(frm, "Dial indicator serial port", self.dial_port, self.do_dial)

        # --- Manifest
        tk.Button(
            frm,
            text="Emit manifest.json (hash everything in out/<RunID>)",
            command=self.do_manifest,
            width=50,
        ).pack(pady=6)

        # --- Chladni Wizard
        tk.Button(
            frm,
            text="Chladni Wizard (WAV → peaks → images → run + manifest)",
            command=self.do_chladni_wizard,
            width=50,
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
        if HAS_EXPORT:
            tools_menu.add_command(
                label="Export Viewer Pack...",
                command=self.do_export_viewer_pack,
                accelerator="Ctrl+E",
            )
            tools_menu.add_separator()
        if HAS_TIMELINE_VIEWER:
            tools_menu.add_command(
                label="View Session Timeline...",
                command=self.do_view_timeline,
                accelerator="Ctrl+T",
            )
            tools_menu.add_separator()
        tools_menu.add_command(
            label="Chladni Wizard...", command=self.do_chladni_wizard
        )

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
            "Grid + Quality Gate",
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
        if HAS_EXPORT:
            self.bind_all("<Control-e>", lambda e: self.do_export_viewer_pack())
        if HAS_TIMELINE_VIEWER:
            self.bind_all("<Control-t>", lambda e: self.do_view_timeline())

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

    def _on_auto_trigger_toggle(self) -> None:
        """Handle auto-trigger checkbox toggle (Phase 10)."""
        if hasattr(self, "trigger_status_label"):
            if self.auto_trigger_var.get():
                self.trigger_status_label.configure(
                    text="Will wait for tap onset",
                    fg="#1976D2",
                )
            else:
                self.trigger_status_label.configure(text="", fg="#666")

    def _update_trigger_listening_state(self, listening: bool) -> None:
        """Update visual state for listening mode (Phase 10)."""
        if hasattr(self, "trigger_status_label"):
            if listening:
                self.trigger_status_label.configure(
                    text="🎤 Listening for tap...",
                    fg="#4CAF50",
                    font=("Helvetica", 10, "bold"),
                )
            else:
                if self.auto_trigger_var.get():
                    self.trigger_status_label.configure(
                        text="Will wait for tap onset",
                        fg="#1976D2",
                        font=("Helvetica", 9),
                    )
                else:
                    self.trigger_status_label.configure(
                        text="",
                        fg="#666",
                        font=("Helvetica", 9),
                    )

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

    def do_export_viewer_pack(self) -> None:
        """Export current session as viewer pack ZIP (Phase 11)."""
        if not HAS_EXPORT:
            messagebox.showerror("Error", "Export module not available")
            return

        session_dir = self.outdir()
        run_id = self.run_id.get().strip()

        # Check if session has any measurements
        point_dirs = [
            d
            for d in session_dir.iterdir()
            if d.is_dir() and not d.name.startswith(("_", "."))
        ]
        if not point_dirs:
            messagebox.showwarning(
                "No Measurements",
                f"No measurement points found in session:\n{session_dir}\n\n"
                "Run a measurement first, then export.",
            )
            return

        # Confirm export
        result = messagebox.askyesno(
            "Export Viewer Pack",
            f"Export session '{run_id}' as viewer pack ZIP?\n\n"
            f"Found {len(point_dirs)} measurement point(s).\n\n"
            "The ZIP will be created in the output folder.",
        )
        if not result:
            return

        # Show progress
        self._set_status(f"Exporting viewer pack for {run_id}...", "progress")
        self.update()

        try:
            export_result = export_gui_session(session_dir, as_zip=True)

            if export_result.success:
                self._set_status(
                    f"Exported: {export_result.output_path.name}", "success"
                )

                # Show success with warnings if any
                msg = "Viewer pack exported successfully!\n\n"
                msg += f"Points: {export_result.point_count}\n"
                msg += f"Output: {export_result.output_path}"

                if export_result.warnings:
                    msg += f"\n\nWarnings ({len(export_result.warnings)}):\n"
                    for w in export_result.warnings[:5]:
                        msg += f"  \u2022 {w}\n"
                    if len(export_result.warnings) > 5:
                        msg += f"  ... and {len(export_result.warnings) - 5} more"

                messagebox.showinfo("Export Complete", msg)

                # Offer to open the folder
                if messagebox.askyesno("Open Folder", "Open the output folder?"):
                    self._open_output_folder()
            else:
                self._set_status(f"Export failed: {export_result.error}", "error")
                messagebox.showerror(
                    "Export Failed",
                    f"Could not export viewer pack:\n\n{export_result.error}",
                )

        except Exception as e:
            self._set_status(f"Export error: {e}", "error")
            messagebox.showerror(
                "Export Error", f"Unexpected error during export:\n\n{e}"
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
            messagebox.showerror(
                "Error", "Quality gate modules required for grid measurement"
            )
            return

        # Ask user to select or create a grid
        choice = messagebox.askyesnocancel(
            "Grid Measurement",
            "Do you want to create a new grid?\n\n"
            "Yes = Create new grid\n"
            "No = Load existing grid\n"
            "Cancel = Cancel",
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
            self._set_status(
                f"Grid session complete: {s.completed_count}/{s.total_points}",
                "success",
            )
            messagebox.showinfo(
                "Session Complete",
                f"All {s.total_points} points measured!\n\nSession saved to:\n{session_path}",
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

    def _do_grid_point_measure(
        self, session: "GridSession", point_id: str, measure_dlg
    ) -> None:
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
        existing = (
            [d for d in point_dir.iterdir() if d.name.startswith("attempt_")]
            if point_dir.exists()
            else []
        )
        attempt_num = len(existing) + 1
        attempt_dir = point_dir / f"attempt_{attempt_num:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Check if auto-trigger is enabled (Phase 10)
            use_auto_trigger = (
                hasattr(self, "auto_trigger_var")
                and self.auto_trigger_var.get()
                and HAS_AUTO_TRIGGER
            )

            if use_auto_trigger:
                self._set_status(f"Listening for tap ({point_id})...", "progress")
                self._update_trigger_listening_state(True)
                self.update()

                trigger_result = record_audio_triggered(
                    device=device,
                    sample_rate=sample_rate,
                    post_trigger_seconds=duration,
                    timeout_seconds=30.0,
                )

                self._update_trigger_listening_state(False)

                if not trigger_result.triggered:
                    if trigger_result.state == TriggerState.TIMEOUT:
                        session.mark_failed(point_id)
                        self._set_status(
                            f"Timeout waiting for tap on {point_id}", "error"
                        )
                        measure_dlg.update_point_result(point_id, "failed", None)
                    return

                self._set_status(f"Tap captured ({point_id})", "success")
                self.update()

                class _CapResult:
                    def __init__(self, audio, sr):
                        self.audio = audio
                        self.sample_rate = sr

                cap = _CapResult(trigger_result.audio, trigger_result.sample_rate)
            else:
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
            from tap_tone_pi.io.wav import write_wav_int16

            write_wav_int16(attempt_dir / "audio.wav", cap.audio, cap.sample_rate)

            with open(attempt_dir / "analysis.json", "w") as f:
                json.dump(
                    {
                        "dominant_hz": result.dominant_hz,
                        "rms": float(result.rms),
                        "confidence": float(result.confidence),
                        "clipped": result.clipped,
                    },
                    f,
                    indent=2,
                )

            # Update session based on verdict
            if verdict.verdict == Verdict.PASS:
                session.mark_passed(point_id, result.dominant_hz)
                status = "passed"
                self._set_status(
                    f"{point_id}: PASSED ({result.dominant_hz:.1f} Hz)", "success"
                )
            elif verdict.verdict == Verdict.WARN:
                session.mark_warned(point_id, result.dominant_hz)
                status = "warned"
                self._set_status(
                    f"{point_id}: WARNING ({result.dominant_hz:.1f} Hz)", "warning"
                )
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


    def do_quality_measure(self, entry_vars: list) -> None:
        """Run quality-gated measurement (delegated to measurement_flow module)."""
        from tap_tone_pi.gui.measurement_flow import do_quality_measure as _impl
        _impl(self, entry_vars)

    def do_tap_live(self, entry_vars: list[tk.StringVar]) -> None:
        """Run live tap-tone capture."""
        outdir = self.outdir()
        dur = entry_vars[0].get()
        sr = entry_vars[1].get()
        cmd = (
            f"python modes/tap_tone/tap_fft_logger.py "
            f"--outfile {outdir / 'tap_tone.json'} "
            f"--plot {outdir / 'spectrum.png'} "
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
                    "peaks": [
                        {"freq_hz": p.freq_hz, "magnitude": p.magnitude}
                        for p in result.peaks
                    ],
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
                f"--outfile {outdir / 'tap_tone_offline.json'} --labels A0 T11 B11"
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
            f"--out {outdir / 'bending_test.json'}"
        )
        if density.strip():
            cmd += f" --density {density}"
        run(cmd)

    def do_moe_batch(self, path_var: tk.StringVar) -> None:
        """Calculate MOE from batch CSV."""
        outdir = self.outdir()
        cmd = (
            f"python modes/bending_stiffness/deflection_to_moe.py "
            f"--csv {path_var.get()} --out {outdir / 'moe_results.csv'}"
        )
        run(cmd)

    def do_provenance(self, path_var: tk.StringVar) -> None:
        """Hash a file for provenance tracking."""
        outdir = self.outdir()
        cmd = (
            f"python modes/provenance_import/attach_grain_provenance.py "
            f"--file {path_var.get()} --out {outdir / 'provenance.json'}"
        )
        run(cmd)

    def do_loadcell(self, cfg_var: tk.StringVar) -> None:
        """Capture load cell data via serial."""
        outdir = self.outdir()
        cmd = (
            f"python modes/acquisition/loadcell_serial.py "
            f"--config {cfg_var.get()} --out {outdir / 'load_series.json'}"
        )
        run(cmd)

    def do_dial(self, port_var: tk.StringVar) -> None:
        """Capture dial indicator data via serial."""
        outdir = self.outdir()
        cmd = (
            f"python modes/acquisition/dial_indicator_serial.py "
            f"--port {port_var.get()} --out {outdir / 'displacement_series.json'}"
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
            "python",
            "modes/_shared/emit_manifest.py",
            "--out",
            (outdir / "manifest.json").as_posix(),
            *artifacts,
            *rig,
        ]
        run(" ".join(shlex.quote(c) for c in cmd))

    def do_view_timeline(self) -> None:
        """Open the session timeline viewer for the current session."""
        if not HAS_TIMELINE_VIEWER:
            messagebox.showerror("Error", "Timeline viewer module not available")
            return

        run = self.run_id.get().strip()
        session_dir = self.outdir()
        if run:
            session_dir = OUT / run

        if not session_dir.exists():
            messagebox.showwarning(
                "No Session",
                "No active session directory found.\n"
                "Run a measurement first or select a session.",
            )
            return

        TimelineViewerDialog(self, session_dir)

    def do_chladni_wizard(self) -> None:
        """Chladni pattern analysis wizard (delegated to chladni_flow module)."""
        from tap_tone_pi.gui.chladni_flow import do_chladni_wizard as _impl
        _impl(self)

# --- Helper functions for building form groups ---


def group(
    parent: tk.Widget, title: str, fields: list[tuple[str, str]], callback
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
    callback,
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


def group_file(parent: tk.Widget, title: str, path_var: tk.StringVar, callback) -> None:
    """Create a labeled frame with file path entry and browse button."""
    f = tk.LabelFrame(parent, text=title)
    f.pack(fill="x", pady=4)

    row = tk.Frame(f)
    row.pack(fill="x")
    tk.Entry(row, textvariable=path_var, width=48).pack(side="left")
    tk.Button(
        row,
        text="Browse",
        command=lambda: path_var.set(filedialog.askopenfilename() or path_var.get()),
    ).pack(side="left", padx=6)

    tk.Button(f, text="Run", command=lambda: callback(path_var)).pack(pady=3)


def group_entry(parent: tk.Widget, title: str, var: tk.StringVar, callback) -> None:
    """Create a labeled frame with a single entry field."""
    f = tk.LabelFrame(parent, text=title)
    f.pack(fill="x", pady=4)

    row = tk.Frame(f)
    row.pack(fill="x")
    tk.Entry(row, textvariable=var, width=32).pack(side="left")

    tk.Button(f, text="Run", command=lambda: callback(var)).pack(pady=3)


if __name__ == "__main__":
    App().mainloop()
