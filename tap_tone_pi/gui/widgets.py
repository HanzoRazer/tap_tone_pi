# INSTRUMENT CLASS: MEASUREMENT
"""
UI widgets for tap_tone_pi GUI.

Provides polished, reusable components:
- AudioLevelMeter: Real-time audio level visualization
- StatusBar: Operation progress feedback
- DeviceSelector: Audio device dropdown with test button
- CaptureProgressDialog: Progress dialog for capture operations
- ToolTip / create_tooltip: Simple tooltip for Tkinter widgets

Extracted dialog classes (backward-compatible re-exports):
- SetupWizardDialog → tap_tone_pi.gui.setup_wizard
- SessionInfo → tap_tone_pi.gui.session_info
- SessionBrowserDialog → tap_tone_pi.gui.session_browser
- PackDiffDialog → tap_tone_pi.gui.pack_diff
"""

from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk, messagebox
from typing import Callable
from enum import Enum

# Optional audio imports
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from tap_tone_pi.capture import list_devices, record_audio

    HAS_CAPTURE = True
except ImportError:
    HAS_CAPTURE = False

try:
    from tap_tone_pi.core.user_config import (
        AudioDeviceConfig,  # noqa: F401
        UserConfig,  # noqa: F401
        save_config,  # noqa: F401
        load_config,  # noqa: F401
    )

    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False


class StatusLevel(str, Enum):
    """Status bar message levels."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"


@dataclass
class StatusMessage:
    """Status bar message."""

    text: str
    level: StatusLevel = StatusLevel.INFO
    progress: float | None = None  # 0.0 - 1.0 for progress bar


class StatusBar(tk.Frame):
    """
    Status bar with message display and optional progress bar.

    Usage:
        status = StatusBar(root)
        status.pack(side=tk.BOTTOM, fill=tk.X)

        status.set("Ready", StatusLevel.INFO)
        status.set("Processing...", StatusLevel.PROGRESS, progress=0.5)
        status.set("Done!", StatusLevel.SUCCESS)
    """

    COLORS = {
        StatusLevel.INFO: ("#333", "#f0f0f0"),
        StatusLevel.SUCCESS: ("#155724", "#d4edda"),
        StatusLevel.WARNING: ("#856404", "#fff3cd"),
        StatusLevel.ERROR: ("#721c24", "#f8d7da"),
        StatusLevel.PROGRESS: ("#004085", "#cce5ff"),
    }

    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(parent, **kwargs)

        self.configure(relief=tk.SUNKEN, bd=1)

        # Message label
        self.message_var = tk.StringVar(value="Ready")
        self.label = tk.Label(
            self,
            textvariable=self.message_var,
            anchor=tk.W,
            padx=8,
            pady=4,
            font=("Helvetica", 9),
        )
        self.label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Progress bar (hidden by default)
        self.progress = ttk.Progressbar(
            self,
            orient=tk.HORIZONTAL,
            length=120,
            mode="determinate",
        )
        self._progress_visible = False

    def set(
        self,
        text: str,
        level: StatusLevel = StatusLevel.INFO,
        progress: float | None = None,
    ) -> None:
        """Set status message and optional progress."""
        fg, bg = self.COLORS.get(level, self.COLORS[StatusLevel.INFO])

        self.message_var.set(text)
        self.label.configure(fg=fg, bg=bg)
        self.configure(bg=bg)

        if progress is not None and level == StatusLevel.PROGRESS:
            self.progress["value"] = progress * 100
            if not self._progress_visible:
                self.progress.pack(side=tk.RIGHT, padx=8)
                self._progress_visible = True
        elif self._progress_visible:
            self.progress.pack_forget()
            self._progress_visible = False

    def clear(self) -> None:
        """Clear status to default."""
        self.set("Ready", StatusLevel.INFO)


class AudioLevelMeter(tk.Canvas):
    """
    Real-time audio level meter with peak hold.

    Usage:
        meter = AudioLevelMeter(parent, width=200, height=20)
        meter.pack()

        # Update with RMS level (0.0 - 1.0)
        meter.set_level(0.5)

        # Or with dB value
        meter.set_level_db(-12)
    """

    # Color thresholds (level, color)
    COLORS = [
        (0.0, "#2ecc71"),  # Green
        (0.6, "#2ecc71"),  # Green
        (0.75, "#f1c40f"),  # Yellow
        (0.9, "#e74c3c"),  # Red
        (1.0, "#e74c3c"),  # Red
    ]

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 200,
        height: int = 20,
        show_peak: bool = True,
        peak_hold_ms: int = 1000,
        **kwargs,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg="#1a1a1a",
            highlightthickness=0,
            **kwargs,
        )

        self._width = width
        self._height = height
        self._level = 0.0
        self._peak = 0.0
        self._peak_time = 0.0
        self._show_peak = show_peak
        self._peak_hold_ms = peak_hold_ms

        # Draw initial state
        self._draw()

    def set_level(self, level: float) -> None:
        """Set level (0.0 - 1.0, clamped)."""
        self._level = max(0.0, min(1.0, level))

        # Update peak
        now = time.time() * 1000
        if self._level > self._peak or (now - self._peak_time) > self._peak_hold_ms:
            self._peak = self._level
            self._peak_time = now

        self._draw()

    def set_level_db(self, db: float, min_db: float = -60, max_db: float = 0) -> None:
        """Set level from dB value."""
        # Normalize to 0-1
        level = (db - min_db) / (max_db - min_db)
        self.set_level(level)

    def _get_color(self, level: float) -> str:
        """Get color for level."""
        for threshold, color in reversed(self.COLORS):
            if level >= threshold:
                return color
        return self.COLORS[0][1]

    def _draw(self) -> None:
        """Redraw the meter."""
        try:
            self.delete("all")
        except tk.TclError:
            # Widget was destroyed
            return

        # Background
        self.create_rectangle(
            0, 0, self._width, self._height, fill="#1a1a1a", outline=""
        )

        # Draw segments
        segment_count = 20
        segment_width = (self._width - 4) / segment_count
        segment_gap = 2

        filled_segments = int(self._level * segment_count)

        for i in range(segment_count):
            x1 = 2 + i * segment_width + segment_gap / 2
            x2 = x1 + segment_width - segment_gap

            level_at_segment = (i + 1) / segment_count
            color = self._get_color(level_at_segment)

            if i < filled_segments:
                self.create_rectangle(
                    x1, 2, x2, self._height - 2, fill=color, outline=""
                )
            else:
                # Dim version for unfilled
                self.create_rectangle(
                    x1, 2, x2, self._height - 2, fill="#333", outline=""
                )

        # Peak indicator
        if self._show_peak and self._peak > 0:
            peak_x = 2 + (self._peak * (self._width - 4))
            self.create_line(peak_x, 0, peak_x, self._height, fill="#fff", width=2)


class DeviceSelector(tk.Frame):
    """
    Audio device dropdown with refresh and test buttons.

    Usage:
        selector = DeviceSelector(parent)
        selector.pack()

        # Get selected device
        device = selector.get_selected()  # Returns device dict or None
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_device_changed: Callable[[dict | None], None] | None = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)

        self.on_device_changed = on_device_changed
        self._devices: list[dict] = []
        self._selected_index = tk.IntVar(value=-1)

        # Device dropdown
        self.combo = ttk.Combobox(self, state="readonly", width=40)
        self.combo.pack(side=tk.LEFT, padx=(0, 5))
        self.combo.bind("<<ComboboxSelected>>", self._on_select)

        # Refresh button
        self.refresh_btn = tk.Button(
            self, text="Refresh", command=self.refresh_devices, width=8
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=2)

        # Test button
        self.test_btn = tk.Button(self, text="Test", command=self._test_device, width=6)
        self.test_btn.pack(side=tk.LEFT, padx=2)

        # Initial load
        self.refresh_devices()

    def refresh_devices(self) -> None:
        """Refresh the device list."""
        if not HAS_CAPTURE:
            self.combo["values"] = ["(capture module not available)"]
            self.combo.current(0)
            return

        self._devices = list_devices()
        input_devices = [d for d in self._devices if d.get("max_input_channels", 0) > 0]

        if not input_devices:
            self.combo["values"] = ["(no input devices found)"]
            self.combo.current(0)
            self._devices = []
            return

        values = [f"[{d['index']}] {d['name']}" for d in input_devices]
        self.combo["values"] = values

        self._devices = input_devices
        if values:
            self.combo.current(0)
            self._selected_index.set(0)

    def get_selected(self) -> dict | None:
        """Get the selected device dict."""
        idx = self.combo.current()
        if 0 <= idx < len(self._devices):
            return self._devices[idx]
        return None

    def set_selected(self, device_index: int) -> bool:
        """Set selection by device index."""
        for i, d in enumerate(self._devices):
            if d.get("index") == device_index:
                self.combo.current(i)
                self._selected_index.set(i)
                return True
        return False

    def _on_select(self, event) -> None:
        """Handle device selection."""
        if self.on_device_changed:
            self.on_device_changed(self.get_selected())

    def _test_device(self) -> None:
        """Test the selected device with a short recording."""
        device = self.get_selected()
        if not device:
            messagebox.showwarning("No Device", "Please select a device first.")
            return

        if not HAS_CAPTURE or not HAS_NUMPY:
            messagebox.showerror("Error", "Audio capture not available.")
            return

        try:
            # Short test recording
            result = record_audio(
                device=device["index"],
                sample_rate=48000,
                channels=1,
                seconds=0.5,
            )

            # Calculate RMS
            rms = float(np.sqrt(np.mean(result.audio.astype(float) ** 2)))
            peak = float(np.max(np.abs(result.audio)))

            if peak > 30000:
                level = "LOUD (possible clipping)"
            elif rms > 1000:
                level = "Good signal"
            elif rms > 100:
                level = "Quiet but usable"
            else:
                level = "Very quiet (check connection)"

            messagebox.showinfo(
                "Device Test",
                f"Device: {device['name']}\n\n"
                f"RMS: {rms:.0f}\n"
                f"Peak: {peak:.0f}\n"
                f"Level: {level}",
            )
        except Exception as e:
            messagebox.showerror("Test Failed", f"Could not record: {e}")


class CaptureProgressDialog(tk.Toplevel):
    """
    Progress dialog for capture operations.

    Shows:
    - Current stage (preflight, capturing, analyzing, gating)
    - Level meter during capture
    - Cancel button
    """

    STAGES = ["Preflight", "Capturing", "Analyzing", "Quality Check"]

    def __init__(
        self,
        parent: tk.Tk,
        title: str = "Capture in Progress",
        on_cancel: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x200")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self.on_cancel = on_cancel
        self._cancelled = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main = tk.Frame(self, padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Stage indicator
        self.stage_label = tk.Label(
            main,
            text="Preparing...",
            font=("Helvetica", 12, "bold"),
        )
        self.stage_label.pack(pady=10)

        # Progress bar
        self.progress = ttk.Progressbar(
            main,
            orient=tk.HORIZONTAL,
            length=350,
            mode="determinate",
        )
        self.progress.pack(pady=10)

        # Level meter (for capture stage)
        meter_frame = tk.Frame(main)
        meter_frame.pack(fill=tk.X, pady=10)

        tk.Label(meter_frame, text="Level:").pack(side=tk.LEFT, padx=(0, 10))
        self.meter = AudioLevelMeter(meter_frame, width=280, height=20)
        self.meter.pack(side=tk.LEFT)

        # Status text
        self.status_label = tk.Label(main, text="", fg="#666")
        self.status_label.pack(pady=5)

        # Cancel button
        self.cancel_btn = tk.Button(
            main,
            text="Cancel",
            command=self._do_cancel,
            width=10,
        )
        self.cancel_btn.pack(pady=10)

    def set_stage(self, stage_index: int, status: str = "") -> None:
        """Set the current stage (0-3)."""
        if 0 <= stage_index < len(self.STAGES):
            self.stage_label.configure(text=self.STAGES[stage_index])
            self.progress["value"] = (stage_index + 1) * 25
        self.status_label.configure(text=status)
        self.update()

    def set_level(self, level: float) -> None:
        """Update the level meter."""
        self.meter.set_level(level)
        self.update()

    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self._cancelled

    def _do_cancel(self) -> None:
        """Handle cancel button."""
        self._cancelled = True
        if self.on_cancel:
            self.on_cancel()
        self.destroy()


class ToolTip:
    """
    Simple tooltip for Tkinter widgets.

    Usage:
        button = tk.Button(root, text="Click me")
        ToolTip(button, "This is a tooltip")
    """

    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        delay: int = 500,
        wrap_length: int = 250,
    ):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wrap_length = wrap_length
        self._tooltip_window = None
        self._after_id = None

        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, event=None) -> None:
        """Schedule tooltip display."""
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        """Cancel scheduled tooltip."""
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self) -> None:
        """Display the tooltip."""
        if self._tooltip_window:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self._tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            wraplength=self.wrap_length,
            font=("Helvetica", 9),
            padx=6,
            pady=4,
        )
        label.pack()

    def _hide(self, event=None) -> None:
        """Hide the tooltip."""
        self._cancel()
        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None


def create_tooltip(widget: tk.Widget, text: str) -> "ToolTip":
    """Convenience function to create a tooltip."""
    return ToolTip(widget, text)


# Backward-compatible re-exports for extracted classes (placed after all class
# definitions to avoid circular imports — setup_wizard.py imports AudioLevelMeter
# and DeviceSelector from this module).
from tap_tone_pi.gui.session_info import SessionInfo  # noqa: F401,E402
from tap_tone_pi.gui.setup_wizard import SetupWizardDialog  # noqa: F401,E402
from tap_tone_pi.gui.session_browser import SessionBrowserDialog  # noqa: F401,E402
from tap_tone_pi.gui.pack_diff import PackDiffDialog  # noqa: F401,E402


__all__ = [
    "StatusLevel",
    "StatusMessage",
    "StatusBar",
    "AudioLevelMeter",
    "DeviceSelector",
    "SetupWizardDialog",
    "CaptureProgressDialog",
    "SessionInfo",
    "SessionBrowserDialog",
    "PackDiffDialog",
    "ToolTip",
    "create_tooltip",
]
