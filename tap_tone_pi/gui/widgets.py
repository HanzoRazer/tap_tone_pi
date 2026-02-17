"""
UI widgets for tap_tone_pi GUI.

Provides polished, reusable components:
- AudioLevelMeter: Real-time audio level visualization
- StatusBar: Operation progress feedback
- SetupWizardDialog: In-GUI hardware configuration
- DeviceSelector: Audio device dropdown with test button
- SessionBrowserDialog: Browse and manage past measurement sessions
- PackDiffDialog: Compare two measurement sessions (before/after)
"""

from __future__ import annotations

import json
import platform
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox
from typing import Callable
from dataclasses import dataclass
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
        AudioDeviceConfig,
        UserConfig,
        save_config,
        load_config,
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


class SetupWizardDialog(tk.Toplevel):
    """
    In-GUI setup wizard for hardware configuration.

    Steps:
    1. Select audio device
    2. Choose sample rate
    3. Test recording with level meter
    4. Validate and save
    """

    SAMPLE_RATES = [44100, 48000, 96000]

    def __init__(
        self,
        parent: tk.Tk,
        on_complete: Callable[[AudioDeviceConfig], None] | None = None,
    ):
        super().__init__(parent)
        self.title("Hardware Setup Wizard")
        self.geometry("500x450")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self.on_complete = on_complete
        self._recording = False
        self._test_thread: threading.Thread | None = None

        # State
        self._selected_device: dict | None = None
        self._sample_rate = tk.IntVar(value=48000)
        self._test_passed = False

        self._build_ui()

        # Load existing config if available
        self._load_existing()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        """Build the wizard UI."""
        # Main container with padding
        main = tk.Frame(self, padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(
            main,
            text="Hardware Setup Wizard",
            font=("Helvetica", 16, "bold"),
        ).pack(pady=(0, 20))

        # Step 1: Device Selection
        step1 = tk.LabelFrame(
            main, text="Step 1: Select Audio Input Device", padx=10, pady=10
        )
        step1.pack(fill=tk.X, pady=5)

        self.device_selector = DeviceSelector(
            step1, on_device_changed=self._on_device_changed
        )
        self.device_selector.pack(fill=tk.X)

        # Step 2: Sample Rate
        step2 = tk.LabelFrame(main, text="Step 2: Choose Sample Rate", padx=10, pady=10)
        step2.pack(fill=tk.X, pady=5)

        rate_frame = tk.Frame(step2)
        rate_frame.pack(fill=tk.X)

        for rate in self.SAMPLE_RATES:
            tk.Radiobutton(
                rate_frame,
                text=f"{rate} Hz",
                variable=self._sample_rate,
                value=rate,
            ).pack(side=tk.LEFT, padx=10)

        # Step 3: Test Recording
        step3 = tk.LabelFrame(main, text="Step 3: Test Recording", padx=10, pady=10)
        step3.pack(fill=tk.X, pady=5)

        # Level meter
        meter_frame = tk.Frame(step3)
        meter_frame.pack(fill=tk.X, pady=5)

        tk.Label(meter_frame, text="Level:").pack(side=tk.LEFT, padx=(0, 10))
        self.meter = AudioLevelMeter(meter_frame, width=300, height=24)
        self.meter.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Test controls
        test_frame = tk.Frame(step3)
        test_frame.pack(fill=tk.X, pady=10)

        self.test_btn = tk.Button(
            test_frame,
            text="Start Test Recording",
            command=self._toggle_test,
            width=20,
            bg="#2196F3",
            fg="white",
        )
        self.test_btn.pack(side=tk.LEFT)

        self.test_status = tk.Label(test_frame, text="", fg="#666")
        self.test_status.pack(side=tk.LEFT, padx=10)

        # Validation status
        self.validation_frame = tk.LabelFrame(main, text="Status", padx=10, pady=10)
        self.validation_frame.pack(fill=tk.X, pady=5)

        self.validation_label = tk.Label(
            self.validation_frame,
            text="Select a device and run a test recording.",
            fg="#666",
        )
        self.validation_label.pack(anchor=tk.W)

        # Buttons
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=20)

        self.save_btn = tk.Button(
            btn_frame,
            text="Save Configuration",
            command=self._save_config,
            width=18,
            bg="#4CAF50",
            fg="white",
            state=tk.DISABLED,
        )
        self.save_btn.pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            width=10,
        ).pack(side=tk.RIGHT)

    def _load_existing(self) -> None:
        """Load existing configuration if available."""
        if not HAS_CONFIG:
            return

        try:
            config = load_config()
            if config and config.audio_device:
                # Try to select the saved device
                if self.device_selector.set_selected(config.audio_device.index):
                    self._sample_rate.set(config.audio_device.sample_rate)
                    self._selected_device = self.device_selector.get_selected()
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass

    def _on_close(self) -> None:
        """Handle window close - stop recording first."""
        self._recording = False
        # Give thread a moment to stop
        if self._test_thread and self._test_thread.is_alive():
            self._test_thread.join(timeout=0.5)
        self.destroy()

    def _on_device_changed(self, device: dict | None) -> None:
        """Handle device selection change."""
        self._selected_device = device
        self._test_passed = False
        self._update_validation()

    def _toggle_test(self) -> None:
        """Toggle test recording on/off."""
        if self._recording:
            self._stop_test()
        else:
            self._start_test()

    def _start_test(self) -> None:
        """Start test recording."""
        if not self._selected_device:
            messagebox.showwarning("No Device", "Please select a device first.")
            return

        self._recording = True
        self.test_btn.configure(text="Stop Test", bg="#f44336")
        self.test_status.configure(text="Recording... tap the wood!", fg="#2196F3")

        # Start recording thread
        self._test_thread = threading.Thread(target=self._test_loop, daemon=True)
        self._test_thread.start()

    def _stop_test(self) -> None:
        """Stop test recording."""
        self._recording = False
        self.test_btn.configure(text="Start Test Recording", bg="#2196F3")
        self.test_status.configure(text="", fg="#666")
        self.meter.set_level(0)

    def _test_loop(self) -> None:
        """Recording loop for level monitoring."""
        if not HAS_CAPTURE or not HAS_NUMPY:
            return

        max_rms = 0.0
        good_samples = 0

        while self._recording:
            try:
                result = record_audio(
                    device=self._selected_device["index"],
                    sample_rate=self._sample_rate.get(),
                    channels=1,
                    seconds=0.1,  # Short chunks for responsive meter
                )

                # Calculate RMS normalized to 0-1
                audio_float = result.audio.astype(float)
                rms = np.sqrt(np.mean(audio_float**2))
                normalized = min(1.0, rms / 20000)  # Normalize assuming ~20000 is loud

                max_rms = max(max_rms, rms)
                if rms > 500:
                    good_samples += 1

                # Update meter on main thread (check if still recording)
                if self._recording:
                    try:
                        self.after(
                            0,
                            lambda level=normalized: self.meter.set_level(level)
                            if self._recording
                            else None,
                        )
                    except tk.TclError:
                        break  # Widget destroyed

            except Exception as ex:
                err_msg = str(ex)
                self.after(
                    0,
                    lambda err=err_msg: self.test_status.configure(
                        text=f"Error: {err}", fg="#f44336"
                    ),
                )
                break

        # Evaluate test results
        if max_rms > 1000 and good_samples > 2:
            self._test_passed = True
            self.after(0, lambda: self._update_validation())

    def _update_validation(self) -> None:
        """Update validation status."""
        if not self._selected_device:
            self.validation_label.configure(
                text="Please select an audio device.",
                fg="#f44336",
            )
            self.save_btn.configure(state=tk.DISABLED)
            return

        if not self._test_passed:
            self.validation_label.configure(
                text="Run a test recording and tap the wood to validate.",
                fg="#ff9800",
            )
            self.save_btn.configure(state=tk.DISABLED)
            return

        self.validation_label.configure(
            text=f"Device validated: {self._selected_device['name']}",
            fg="#4CAF50",
        )
        self.save_btn.configure(state=tk.NORMAL)

    def _save_config(self) -> None:
        """Save the configuration."""
        if not self._selected_device or not HAS_CONFIG:
            return

        try:
            device_config = AudioDeviceConfig(
                index=self._selected_device["index"],
                name=self._selected_device["name"],
                sample_rate=self._sample_rate.get(),
                channels=1,
            )

            # Load existing or create new
            try:
                config = load_config()
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                config = UserConfig()

            config.audio_device = device_config
            save_config(config)

            messagebox.showinfo(
                "Configuration Saved",
                f"Device: {device_config.name}\n"
                f"Sample Rate: {device_config.sample_rate} Hz\n\n"
                "Configuration saved successfully!",
            )

            if self.on_complete:
                self.on_complete(device_config)

            self.destroy()

        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save configuration: {e}")


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


@dataclass
class SessionInfo:
    """Information about a measurement session."""

    path: Path
    name: str
    modified: datetime
    session_type: str = "unknown"
    point_count: int = 0
    attempt_count: int = 0
    file_count: int = 0
    size_bytes: int = 0
    has_manifest: bool = False
    latest_verdict: str | None = None

    @classmethod
    def from_path(cls, path: Path) -> "SessionInfo":
        """Create SessionInfo from a session directory path."""
        name = path.name
        modified = datetime.fromtimestamp(path.stat().st_mtime)

        # Count files and calculate size
        file_count = 0
        size_bytes = 0
        has_manifest = False
        point_count = 0
        attempt_count = 0
        session_type = "unknown"
        latest_verdict = None

        try:
            for item in path.rglob("*"):
                if item.is_file():
                    file_count += 1
                    size_bytes += item.stat().st_size
                    if item.name == "manifest.json":
                        has_manifest = True

            # Detect session type
            if (path / "chladni").exists():
                session_type = "chladni"
            elif any(path.glob("*/attempt_*")):
                session_type = "quality_gated"
                # Count points and attempts
                for point_dir in path.iterdir():
                    if point_dir.is_dir() and not point_dir.name.startswith("."):
                        attempts = list(point_dir.glob("attempt_*"))
                        if attempts:
                            point_count += 1
                            attempt_count += len(attempts)
                            # Get latest verdict
                            latest_attempt = sorted(attempts)[-1]
                            qc_file = latest_attempt / "quality_check.json"
                            if qc_file.exists():
                                try:
                                    with open(qc_file) as f:
                                        qc = json.load(f)
                                        latest_verdict = qc.get("verdict", "unknown")
                                except (
                                    ImportError,
                                    OSError,
                                    ValueError,
                                    KeyError,
                                    AttributeError,
                                ):
                                    pass
            elif (path / "analysis").exists():
                session_type = "bending"
            elif (path / "moe").exists():
                session_type = "moe"
            elif any(path.glob("*.wav")):
                session_type = "tap_tone"

        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass

        return cls(
            path=path,
            name=name,
            modified=modified,
            session_type=session_type,
            point_count=point_count,
            attempt_count=attempt_count,
            file_count=file_count,
            size_bytes=size_bytes,
            has_manifest=has_manifest,
            latest_verdict=latest_verdict,
        )

    @property
    def size_display(self) -> str:
        """Human-readable size."""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        else:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"

    @property
    def type_icon(self) -> str:
        """Icon for session type."""
        icons = {
            "quality_gated": "🎯",
            "chladni": "🔊",
            "bending": "📏",
            "moe": "📊",
            "tap_tone": "🎵",
            "unknown": "📁",
        }
        return icons.get(self.session_type, "📁")


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
