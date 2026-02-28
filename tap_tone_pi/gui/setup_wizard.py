"""Hardware setup wizard dialog for tap_tone_pi GUI."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from tap_tone_pi.gui.widgets import AudioLevelMeter, DeviceSelector

# Optional imports
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from tap_tone_pi.capture import record_audio

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
