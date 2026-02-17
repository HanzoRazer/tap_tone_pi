"""
Grid UI widgets for tap_tone_pi GUI (Phase 9).

Provides:
- GridEditorDialog: Create/edit measurement grids
- GridProgressPanel: Visual grid with point status colors
- GridMeasureDialog: Manage grid measurement sessions
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from typing import Callable

try:
    from tap_tone_pi.core.grid import (
        Grid,
        GridPoint,
        GridSession,
        PointStatus,
        PointProgress,
    )

    HAS_GRID = True
except ImportError:
    HAS_GRID = False

    # Stub classes for type hints
    class Grid:
        pass

    class GridPoint:
        pass

    class GridSession:
        pass

    class PointStatus:
        pass


# Status colors
STATUS_COLORS = {
    "pending": "#9E9E9E",  # Gray
    "passed": "#4CAF50",  # Green
    "warned": "#FF9800",  # Orange
    "failed": "#F44336",  # Red
    "skipped": "#607D8B",  # Blue-gray
}


class GridEditorDialog(tk.Toplevel):
    """
    Dialog for creating or editing measurement grids.

    Features:
    - Pattern presets (rectangular, circular, line)
    - Custom point editing
    - Live preview canvas
    - Save/load grid files
    """

    PATTERNS = ["Rectangular", "Circular", "Line", "Custom"]

    def __init__(
        self,
        parent: tk.Tk,
        grid: Grid | None = None,
        on_save: Callable[[Grid], None] | None = None,
    ):
        super().__init__(parent)
        self.title("Grid Editor")
        self.geometry("600x550")
        self.resizable(True, True)
        self.minsize(500, 450)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self.on_save = on_save
        self._grid = grid
        self._points: list[GridPoint] = []

        self._build_ui()

        if grid:
            self._load_grid(grid)
        else:
            self._generate_preview()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main = tk.Frame(self, padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        tk.Label(
            main,
            text="Grid Editor",
            font=("Helvetica", 14, "bold"),
        ).pack(anchor=tk.W, pady=(0, 10))

        # Pattern selection
        pattern_frame = tk.LabelFrame(main, text="Grid Pattern", padx=10, pady=10)
        pattern_frame.pack(fill=tk.X, pady=5)

        # Pattern type
        row1 = tk.Frame(pattern_frame)
        row1.pack(fill=tk.X, pady=3)

        tk.Label(row1, text="Pattern:", width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.pattern_var = tk.StringVar(value="Rectangular")
        self.pattern_combo = ttk.Combobox(
            row1,
            textvariable=self.pattern_var,
            values=self.PATTERNS,
            state="readonly",
            width=15,
        )
        self.pattern_combo.pack(side=tk.LEFT, padx=5)
        self.pattern_combo.bind("<<ComboboxSelected>>", self._on_pattern_change)

        # Parameters frame
        self.params_frame = tk.Frame(pattern_frame)
        self.params_frame.pack(fill=tk.X, pady=5)

        # Rectangular params (default)
        self._rows_var = tk.IntVar(value=3)
        self._cols_var = tk.IntVar(value=4)
        self._spacing_var = tk.DoubleVar(value=50.0)
        self._radius_var = tk.DoubleVar(value=100.0)
        self._num_points_var = tk.IntVar(value=8)
        self._length_var = tk.DoubleVar(value=200.0)
        self._include_center_var = tk.BooleanVar(value=True)
        self._orientation_var = tk.StringVar(value="horizontal")

        self._setup_rect_params()

        # Grid name
        row_name = tk.Frame(pattern_frame)
        row_name.pack(fill=tk.X, pady=3)

        tk.Label(row_name, text="Name:", width=10, anchor=tk.W).pack(side=tk.LEFT)
        self._name_var = tk.StringVar(value="My Grid")
        tk.Entry(row_name, textvariable=self._name_var, width=30).pack(
            side=tk.LEFT, padx=5
        )

        # Generate button
        tk.Button(
            pattern_frame,
            text="Generate Preview",
            command=self._generate_preview,
            bg="#2196F3",
            fg="white",
        ).pack(pady=5)

        # Preview canvas
        preview_frame = tk.LabelFrame(main, text="Preview", padx=10, pady=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.canvas = tk.Canvas(preview_frame, bg="white", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Point count label
        self.point_count_label = tk.Label(preview_frame, text="Points: 0", fg="#666")
        self.point_count_label.pack(anchor=tk.W)

        # Buttons
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            btn_frame,
            text="Load Grid...",
            command=self._load_from_file,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="Save Grid...",
            command=self._save_to_file,
        ).pack(side=tk.LEFT, padx=5)

        self.ok_btn = tk.Button(
            btn_frame,
            text="Use This Grid",
            command=self._on_ok,
            bg="#4CAF50",
            fg="white",
        )
        self.ok_btn.pack(side=tk.RIGHT, padx=5)

        tk.Button(
            btn_frame,
            text="Cancel",
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=5)

    def _setup_rect_params(self) -> None:
        """Setup rectangular grid parameters."""
        for w in self.params_frame.winfo_children():
            w.destroy()

        row = tk.Frame(self.params_frame)
        row.pack(fill=tk.X, pady=2)

        tk.Label(row, text="Rows:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(row, from_=1, to=20, textvariable=self._rows_var, width=5).pack(
            side=tk.LEFT, padx=5
        )

        tk.Label(row, text="Cols:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(row, from_=1, to=20, textvariable=self._cols_var, width=5).pack(
            side=tk.LEFT, padx=5
        )

        tk.Label(row, text="Spacing (mm):", width=12, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(row, from_=1, to=500, textvariable=self._spacing_var, width=8).pack(
            side=tk.LEFT, padx=5
        )

    def _setup_circular_params(self) -> None:
        """Setup circular grid parameters."""
        for w in self.params_frame.winfo_children():
            w.destroy()

        row = tk.Frame(self.params_frame)
        row.pack(fill=tk.X, pady=2)

        tk.Label(row, text="Points:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(
            row, from_=3, to=24, textvariable=self._num_points_var, width=5
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(row, text="Radius (mm):", width=12, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(row, from_=10, to=500, textvariable=self._radius_var, width=8).pack(
            side=tk.LEFT, padx=5
        )

        tk.Checkbutton(
            row, text="Include Center", variable=self._include_center_var
        ).pack(side=tk.LEFT, padx=10)

    def _setup_line_params(self) -> None:
        """Setup line grid parameters."""
        for w in self.params_frame.winfo_children():
            w.destroy()

        row = tk.Frame(self.params_frame)
        row.pack(fill=tk.X, pady=2)

        tk.Label(row, text="Points:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(
            row, from_=2, to=50, textvariable=self._num_points_var, width=5
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(row, text="Length (mm):", width=12, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(row, from_=10, to=1000, textvariable=self._length_var, width=8).pack(
            side=tk.LEFT, padx=5
        )

        tk.Label(row, text="Orientation:", width=10, anchor=tk.W).pack(side=tk.LEFT)
        ttk.Combobox(
            row,
            textvariable=self._orientation_var,
            values=["horizontal", "vertical"],
            state="readonly",
            width=10,
        ).pack(side=tk.LEFT, padx=5)

    def _setup_custom_params(self) -> None:
        """Setup custom grid parameters."""
        for w in self.params_frame.winfo_children():
            w.destroy()

        tk.Label(
            self.params_frame,
            text="Load a grid file or start with another pattern",
            fg="#666",
        ).pack(pady=5)

    def _on_pattern_change(self, event=None) -> None:
        """Handle pattern type change."""
        pattern = self.pattern_var.get()
        if pattern == "Rectangular":
            self._setup_rect_params()
        elif pattern == "Circular":
            self._setup_circular_params()
        elif pattern == "Line":
            self._setup_line_params()
        else:
            self._setup_custom_params()

        self._generate_preview()

    def _generate_preview(self) -> None:
        """Generate grid preview."""
        if not HAS_GRID:
            messagebox.showerror("Error", "Grid module not available")
            return

        pattern = self.pattern_var.get()
        name = self._name_var.get() or "Grid"

        try:
            if pattern == "Rectangular":
                self._grid = Grid.rectangular(
                    rows=self._rows_var.get(),
                    cols=self._cols_var.get(),
                    spacing=self._spacing_var.get(),
                    name=name,
                )
            elif pattern == "Circular":
                self._grid = Grid.circular(
                    num_points=self._num_points_var.get(),
                    radius=self._radius_var.get(),
                    include_center=self._include_center_var.get(),
                    name=name,
                )
            elif pattern == "Line":
                self._grid = Grid.line(
                    num_points=self._num_points_var.get(),
                    length=self._length_var.get(),
                    orientation=self._orientation_var.get(),
                    name=name,
                )

            if self._grid:
                self._points = list(self._grid.points)
                self._draw_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Could not generate grid: {e}")

    def _draw_preview(self) -> None:
        """Draw grid preview on canvas."""
        self.canvas.delete("all")

        if not self._grid or not self._points:
            return

        # Get canvas size
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w < 10 or h < 10:
            return

        # Calculate bounds and scale
        min_x, min_y, max_x, max_y = self._grid.bounds()

        # Add padding
        grid_w = max_x - min_x or 1
        grid_h = max_y - min_y or 1

        padding = 40
        scale = min((w - 2 * padding) / grid_w, (h - 2 * padding) / grid_h)

        # Transform function
        def transform(x: float, y: float) -> tuple[float, float]:
            tx = padding + (x - min_x) * scale
            ty = h - padding - (y - min_y) * scale  # Flip Y
            return tx, ty

        # Draw points
        point_radius = max(5, min(15, scale * 5))

        for point in self._points:
            tx, ty = transform(point.x, point.y)

            self.canvas.create_oval(
                tx - point_radius,
                ty - point_radius,
                tx + point_radius,
                ty + point_radius,
                fill="#2196F3",
                outline="#1976D2",
                width=2,
            )

            # Label
            self.canvas.create_text(
                tx,
                ty - point_radius - 8,
                text=point.id,
                font=("Helvetica", 9),
                fill="#333",
            )

        # Update point count
        self.point_count_label.configure(text=f"Points: {len(self._points)}")

    def _load_grid(self, grid: Grid) -> None:
        """Load an existing grid."""
        self._grid = grid
        self._points = list(grid.points)
        self._name_var.set(grid.name)
        self.pattern_var.set("Custom")
        self._setup_custom_params()
        self._draw_preview()

    def _load_from_file(self) -> None:
        """Load grid from file."""
        if not HAS_GRID:
            return

        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Grid",
        )

        if not filepath:
            return

        try:
            grid = Grid.load(Path(filepath))
            self._load_grid(grid)
            messagebox.showinfo("Loaded", f"Loaded grid: {grid.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load grid: {e}")

    def _save_to_file(self) -> None:
        """Save grid to file."""
        if not self._grid or not HAS_GRID:
            messagebox.showwarning("No Grid", "Generate or load a grid first")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"{self._grid.grid_id}.json",
            title="Save Grid",
        )

        if not filepath:
            return

        try:
            self._grid.save(Path(filepath))
            messagebox.showinfo("Saved", f"Grid saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save grid: {e}")

    def _on_ok(self) -> None:
        """Handle OK button."""
        if not self._grid:
            messagebox.showwarning("No Grid", "Generate or load a grid first")
            return

        if self.on_save:
            self.on_save(self._grid)

        self.destroy()


class GridProgressPanel(tk.Frame):
    """
    Visual grid panel showing measurement progress.

    Features:
    - Canvas with clickable points
    - Color-coded status (pending/passed/warned/failed/skipped)
    - Progress bar
    - Current point highlight
    """

    def __init__(
        self,
        parent: tk.Widget,
        session: GridSession | None = None,
        on_point_click: Callable[[str], None] | None = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)

        self.session = session
        self.on_point_click = on_point_click
        self._point_items: dict[str, int] = {}  # point_id -> canvas item id

        self._build_ui()

        if session:
            self.set_session(session)

    def _build_ui(self) -> None:
        """Build the panel UI."""
        # Header
        header = tk.Frame(self)
        header.pack(fill=tk.X, pady=(0, 5))

        tk.Label(
            header,
            text="Grid Progress",
            font=("Helvetica", 11, "bold"),
        ).pack(side=tk.LEFT)

        self.progress_label = tk.Label(header, text="0/0", fg="#666")
        self.progress_label.pack(side=tk.RIGHT)

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self,
            orient=tk.HORIZONTAL,
            mode="determinate",
        )
        self.progress_bar.pack(fill=tk.X, pady=5)

        # Canvas
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", self._on_resize)

        # Legend
        legend = tk.Frame(self)
        legend.pack(fill=tk.X, pady=(5, 0))

        for status, color in STATUS_COLORS.items():
            f = tk.Frame(legend)
            f.pack(side=tk.LEFT, padx=5)
            tk.Canvas(f, width=12, height=12, bg=color, highlightthickness=0).pack(
                side=tk.LEFT
            )
            tk.Label(f, text=status.title(), font=("Helvetica", 8), fg="#666").pack(
                side=tk.LEFT, padx=2
            )

    def set_session(self, session: GridSession) -> None:
        """Set the grid session to display."""
        self.session = session
        self._draw_grid()
        self._update_progress()

    def refresh(self) -> None:
        """Refresh the display."""
        if self.session:
            self._draw_grid()
            self._update_progress()

    def _draw_grid(self) -> None:
        """Draw the grid on canvas."""
        self.canvas.delete("all")
        self._point_items.clear()

        if not self.session:
            return

        grid = self.session.grid
        if not grid.points:
            return

        # Get canvas size
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w < 10 or h < 10:
            return

        # Calculate bounds and scale
        min_x, min_y, max_x, max_y = grid.bounds()

        grid_w = max_x - min_x or 1
        grid_h = max_y - min_y or 1

        padding = 30
        scale = min((w - 2 * padding) / grid_w, (h - 2 * padding) / grid_h)

        # Transform function
        def transform(x: float, y: float) -> tuple[float, float]:
            tx = padding + (x - min_x) * scale
            ty = h - padding - (y - min_y) * scale
            return tx, ty

        # Draw points
        point_radius = max(8, min(20, scale * 8))

        for point in grid.points:
            tx, ty = transform(point.x, point.y)

            # Get status color
            progress = self.session.progress.get(point.id)
            status = progress.status.value if progress else "pending"
            color = STATUS_COLORS.get(status, STATUS_COLORS["pending"])

            # Highlight current point
            outline_color = "#333"
            outline_width = 2
            if self.session.current_point and point.id == self.session.current_point.id:
                outline_color = "#FFD700"  # Gold
                outline_width = 4

            # Draw point
            item_id = self.canvas.create_oval(
                tx - point_radius,
                ty - point_radius,
                tx + point_radius,
                ty + point_radius,
                fill=color,
                outline=outline_color,
                width=outline_width,
                tags=f"point_{point.id}",
            )
            self._point_items[point.id] = item_id

            # Label
            self.canvas.create_text(
                tx,
                ty,
                text=point.id,
                font=("Helvetica", 9, "bold"),
                fill="white",
            )

    def _update_progress(self) -> None:
        """Update progress bar and label."""
        if not self.session:
            self.progress_label.configure(text="0/0")
            self.progress_bar["value"] = 0
            return

        total = self.session.total_points
        completed = self.session.completed_count

        self.progress_label.configure(text=f"{completed}/{total}")
        self.progress_bar["value"] = (completed / total * 100) if total > 0 else 0

    def _on_canvas_click(self, event) -> None:
        """Handle canvas click."""
        if not self.session or not self.on_point_click:
            return

        # Find clicked item
        items = self.canvas.find_withtag(tk.CURRENT)
        if not items:
            return

        # Get point ID from tags
        tags = self.canvas.gettags(items[0])
        for tag in tags:
            if tag.startswith("point_"):
                point_id = tag[6:]  # Remove "point_" prefix
                self.on_point_click(point_id)
                break

    def _on_resize(self, event) -> None:
        """Handle canvas resize."""
        self._draw_grid()


class GridMeasureDialog(tk.Toplevel):
    """
    Dialog for managing grid measurement sessions.

    Features:
    - Grid progress panel
    - Current point info
    - Measure/Skip/Retry buttons
    - Session save/resume
    """

    def __init__(
        self,
        parent: tk.Tk,
        session: GridSession,
        on_measure: Callable[[str], None] | None = None,
        on_skip: Callable[[str], None] | None = None,
        on_retry: Callable[[str], None] | None = None,
        on_complete: Callable[[GridSession], None] | None = None,
    ):
        super().__init__(parent)
        self.title(f"Grid Measurement - {session.grid.name}")
        self.geometry("600x500")
        self.resizable(True, True)
        self.minsize(450, 400)

        self.session = session
        self.on_measure = on_measure
        self.on_skip = on_skip
        self.on_retry = on_retry
        self.on_complete = on_complete

        self._build_ui()
        self._update_current_point()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main = tk.Frame(self, padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        # Grid progress panel
        self.progress_panel = GridProgressPanel(
            main,
            session=self.session,
            on_point_click=self._on_point_click,
        )
        self.progress_panel.pack(fill=tk.BOTH, expand=True)

        # Current point info
        info_frame = tk.LabelFrame(main, text="Current Point", padx=10, pady=10)
        info_frame.pack(fill=tk.X, pady=10)

        self.point_label = tk.Label(
            info_frame,
            text="No point selected",
            font=("Helvetica", 12, "bold"),
        )
        self.point_label.pack(anchor=tk.W)

        self.status_label = tk.Label(info_frame, text="", fg="#666")
        self.status_label.pack(anchor=tk.W)

        self.result_label = tk.Label(info_frame, text="", fg="#666")
        self.result_label.pack(anchor=tk.W)

        # Action buttons
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.measure_btn = tk.Button(
            btn_frame,
            text="Measure",
            command=self._do_measure,
            bg="#4CAF50",
            fg="white",
            width=12,
            font=("Helvetica", 10, "bold"),
        )
        self.measure_btn.pack(side=tk.LEFT, padx=5)

        self.skip_btn = tk.Button(
            btn_frame,
            text="Skip",
            command=self._do_skip,
            width=10,
        )
        self.skip_btn.pack(side=tk.LEFT, padx=5)

        self.retry_btn = tk.Button(
            btn_frame,
            text="Retry",
            command=self._do_retry,
            width=10,
        )
        self.retry_btn.pack(side=tk.LEFT, padx=5)

        # Save/Close
        tk.Button(
            btn_frame,
            text="Save & Close",
            command=self._save_and_close,
        ).pack(side=tk.RIGHT, padx=5)

        # Status bar
        self.status_bar = tk.Label(
            main,
            text="Ready",
            fg="#666",
            anchor=tk.W,
            relief=tk.SUNKEN,
            padx=5,
        )
        self.status_bar.pack(fill=tk.X)

    def _update_current_point(self) -> None:
        """Update current point display."""
        point = self.session.current_point
        if not point:
            # Check if session is complete
            if self.session.is_complete:
                self.point_label.configure(text="Session Complete!")
                self.status_label.configure(
                    text=f"All {self.session.total_points} points measured"
                )
                self.result_label.configure(text="")
                self.measure_btn.configure(state=tk.DISABLED)
                self.skip_btn.configure(state=tk.DISABLED)

                if self.on_complete:
                    self.on_complete(self.session)
            else:
                # Find next pending
                next_point = self.session.next_pending()
                if next_point:
                    self.point_label.configure(text=f"Point: {next_point.id}")
                    self.status_label.configure(
                        text=f"Position: ({next_point.x:.1f}, {next_point.y:.1f})"
                    )
                else:
                    self.point_label.configure(text="No pending points")
            return

        self.point_label.configure(text=f"Point: {point.id}")

        progress = self.session.progress.get(point.id)
        if progress:
            status_text = f"Status: {progress.status.value.upper()}"
            if progress.attempt_count > 0:
                status_text += f" (attempt {progress.attempt_count})"
            self.status_label.configure(text=status_text)

            if progress.dominant_hz:
                self.result_label.configure(
                    text=f"Dominant frequency: {progress.dominant_hz:.1f} Hz"
                )
            else:
                self.result_label.configure(text="")

        # Update button states
        if progress and progress.status in (PointStatus.PASSED, PointStatus.WARNED):
            self.measure_btn.configure(state=tk.DISABLED)
            self.retry_btn.configure(state=tk.NORMAL)
        elif progress and progress.status == PointStatus.FAILED:
            self.measure_btn.configure(state=tk.NORMAL)
            self.retry_btn.configure(state=tk.NORMAL)
        else:
            self.measure_btn.configure(state=tk.NORMAL)
            self.retry_btn.configure(state=tk.DISABLED)

        self.progress_panel.refresh()

    def _on_point_click(self, point_id: str) -> None:
        """Handle point click."""
        # Find point index and update current
        for i, point in enumerate(self.session.grid.points):
            if point.id == point_id:
                self.session.current_index = i
                self._update_current_point()
                break

    def _do_measure(self) -> None:
        """Trigger measurement for current point."""
        point = self.session.current_point
        if not point:
            point = self.session.next_pending()
            if point:
                # Update current index
                for i, p in enumerate(self.session.grid.points):
                    if p.id == point.id:
                        self.session.current_index = i
                        break

        if point and self.on_measure:
            self.status_bar.configure(text=f"Measuring {point.id}...")
            self.update()
            self.on_measure(point.id)
            self._update_current_point()

    def _do_skip(self) -> None:
        """Skip current point."""
        point = self.session.current_point or self.session.next_pending()
        if point:
            if self.on_skip:
                self.on_skip(point.id)
            self._update_current_point()

    def _do_retry(self) -> None:
        """Retry current point."""
        point = self.session.current_point
        if point and self.on_retry:
            self.session.reset_point(point.id)
            self.on_retry(point.id)
            self._update_current_point()

    def _save_and_close(self) -> None:
        """Save session and close dialog."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"session_{self.session.session_id}.json",
            title="Save Session",
        )

        if filepath:
            try:
                self.session.save(Path(filepath))
                messagebox.showinfo("Saved", f"Session saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save session: {e}")

        self.destroy()

    def update_point_result(
        self,
        point_id: str,
        status: str,
        dominant_hz: float | None = None,
    ) -> None:
        """Update a point's result from external measurement."""
        if not HAS_GRID:
            return

        if status == "passed":
            self.session.mark_passed(point_id, dominant_hz or 0)
        elif status == "warned":
            self.session.mark_warned(point_id, dominant_hz or 0)
        elif status == "failed":
            self.session.mark_failed(point_id)
        elif status == "skipped":
            self.session.mark_skipped(point_id)

        self._update_current_point()
        self.status_bar.configure(text=f"{point_id}: {status.upper()}")


__all__ = [
    "GridEditorDialog",
    "GridProgressPanel",
    "GridMeasureDialog",
    "STATUS_COLORS",
    "HAS_GRID",
]
