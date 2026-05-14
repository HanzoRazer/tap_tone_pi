"""
Quality verdict viewer and spectrum viewer for tap_tone_pi GUI.

Extracted from app.py for maintainability. Contains:
- SpectrumViewer: Matplotlib-based FFT spectrum popup
- QualityVerdictViewer: Quality gate result display with advisory integration
- _get_verdict_banner_config: Helper for verdict banner styling
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tap_tone_pi.core.quality_gate import AnalysisResult
    from tap_tone_pi.core.quality_policy import QualityVerdict

import pathlib
import tkinter as tk
from tkinter import simpledialog

# Optional matplotlib
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Quality gate types
try:
    from tap_tone_pi.core.quality_policy import Verdict, Severity

    HAS_QUALITY_GATE = True
except ImportError:
    HAS_QUALITY_GATE = False

# Timeline viewer
try:
    from tap_tone_pi.gui.timeline_viewer import TimelineViewerDialog

    HAS_TIMELINE_VIEWER = True
except ImportError:
    HAS_TIMELINE_VIEWER = False


class SpectrumViewer(tk.Toplevel):
    """Matplotlib spectrum viewer window (Phase 6 enhancement)."""

    def __init__(
        self, parent: tk.Tk, result: "AnalysisResult", title: str = "Spectrum"
    ) -> None:
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
        ax.semilogy(freq, mag + 1e-10, "b-", linewidth=0.5, alpha=0.7)

        # Mark peaks
        for peak in result.peaks:
            ax.axvline(
                peak.freq_hz, color="r", linestyle="--", alpha=0.5, linewidth=0.8
            )
            ax.annotate(
                f"{peak.freq_hz:.1f} Hz",
                xy=(peak.freq_hz, peak.magnitude),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color="red",
            )

        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Magnitude (log scale)")
        ax.set_xlim(20, 2000)
        ax.set_title(
            f"Dominant: {result.dominant_hz:.1f} Hz | Confidence: {result.confidence:.2f}"
        )
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


def _get_verdict_banner_config(verdict_val: "Verdict") -> tuple:
    """Return (bg_color, text, icon) for verdict banner."""
    if verdict_val == Verdict.PASS:
        return ("#4CAF50", "PASS", "✓")
    elif verdict_val == Verdict.WARN:
        return ("#FF9800", "WARNING", "⚠")
    else:
        return ("#F44336", "FAIL", "✗")


class QualityVerdictViewer(tk.Toplevel):
    """
    Quality gate verdict viewer window (Phase 7 + Phase 8 enhancements).

    Phase 8 improvements:
    - Better visual hierarchy with icons
    - Color-coded rule list items
    - Improved button styling
    - Dominant frequency prominently displayed
    """

    def _build_verdict_banner(self, main: tk.Frame) -> None:
        """Build the verdict banner with icon."""
        banner_bg, banner_text, banner_icon = _get_verdict_banner_config(
            self.verdict.verdict
        )
        banner_frame = tk.Frame(main, bg=banner_bg)
        banner_frame.pack(fill=tk.X, pady=(0, 15))
        tk.Label(
            banner_frame,
            text=f" {banner_icon}  {banner_text}",
            bg=banner_bg,
            fg="white",
            font=("Helvetica", 28, "bold"),
            pady=12,
        ).pack(fill=tk.X)

    def _build_freq_frame(self, main: tk.Frame, result: "AnalysisResult") -> None:
        """Build the dominant frequency display frame."""
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

    def _build_summary_frame(self, main: tk.Frame, result: "AnalysisResult") -> None:
        """Build the measurement details summary frame."""
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
            tk.Label(
                cell, text=f"{label}:", font=("Helvetica", 9, "bold"), fg="#555"
            ).pack(side=tk.LEFT)
            fg_color = "#d32f2f" if "⚠" in value else "#333"
            tk.Label(cell, text=f" {value}", font=("Helvetica", 9), fg=fg_color).pack(
                side=tk.LEFT
            )

    def _build_triggered_rules_frame(self, main: tk.Frame) -> None:
        """Build the triggered quality rules frame."""
        if not self.verdict.triggered_rules:
            tk.Label(
                main,
                text="✓ No quality rules triggered",
                font=("Helvetica", 10),
                fg="#4CAF50",
            ).pack(pady=10)
            return

        rules_frame = tk.LabelFrame(
            main, text="Triggered Quality Rules", padx=8, pady=8
        )
        rules_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        canvas = tk.Canvas(rules_frame, height=100, highlightthickness=0)
        scrollbar = tk.Scrollbar(rules_frame, orient=tk.VERTICAL, command=canvas.yview)
        rules_container = tk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=rules_container, anchor=tk.NW)

        for tr in self.verdict.triggered_rules:
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

    def _build_trust_erosion_banner(self, main: tk.Frame) -> None:
        """Build trust erosion banner if applicable. Fail-closed."""
        if self.session_dir is None:
            return
        _TRUST_EROSION_IDS = {"TRUST_EROSION", "MOMENT_TRUST_EROSION"}
        try:
            from tap_tone_pi.gui.advisory_state import (
                has_responded as _adv_has_responded,
                is_trust_banner_dismissed,
                mark_trust_banner_dismissed,
            )
            from tap_tone_pi.agentic.spine.shadow_record import (
                load_latest_shadow_record as _load_shadow,
            )

            _te_sd = pathlib.Path(self.session_dir)
            if _adv_has_responded(_te_sd):
                return

            _te_rec = _load_shadow(_te_sd)
            _te_moment_id = None
            if isinstance(_te_rec, dict):
                _te_moment = _te_rec.get("moment") or {}
                if isinstance(_te_moment, dict):
                    _te_moment_id = _te_moment.get("id")

            if _te_moment_id in _TRUST_EROSION_IDS and not is_trust_banner_dismissed(
                _te_sd
            ):
                from tap_tone_pi.gui.info_banner import InfoBanner

                _te_banner = InfoBanner(
                    main,
                    text=(
                        "Guidance is currently reduced based on recent "
                        "interaction signals (e.g., dismissals). You can "
                        "still view the advisory block when it appears."
                    ),
                    on_dismiss=lambda: mark_trust_banner_dismissed(_te_sd),
                )
                _te_banner.pack(fill=tk.X, pady=(0, 8))
        except (ImportError, OSError, ValueError, KeyError, AttributeError, Exception):
            pass

    def _build_advisory_directive(self, main: tk.Frame) -> None:
        """Build advisory directive panel if applicable. Fail-closed."""
        if self.session_dir is None:
            return

        _adv_already_handled = False
        try:
            from tap_tone_pi.gui.advisory_state import has_responded as _adv_responded

            if _adv_responded(pathlib.Path(self.session_dir)):
                _adv_already_handled = True
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass

        if _adv_already_handled:
            return

        advisory_rec = None
        advisory_summary = None
        advisory_detail = None
        advisory_action = None

        try:
            from tap_tone_pi.agentic.spine.shadow_record import (
                load_latest_shadow_record,
            )

            rec = load_latest_shadow_record(pathlib.Path(self.session_dir))
            if isinstance(rec, dict):
                advisory_rec = rec
                adv = rec.get("advisory") or {}
                if isinstance(adv, dict):
                    advisory_summary = adv.get("summary")
                    advisory_detail = adv.get("detail") or adv.get("details")
                    advisory_action = adv.get("action")
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            advisory_rec = None

        if (
            advisory_rec is None
            or not isinstance(advisory_summary, str)
            or not advisory_summary.strip()
        ):
            return

        adv_frame = tk.LabelFrame(main, text="Advisory", padx=10, pady=8)
        adv_frame.pack(fill=tk.X, pady=(8, 5))

        header = advisory_summary.strip()
        if isinstance(advisory_action, str) and advisory_action.strip():
            header = f"[{advisory_action.strip().upper()}] {header}"

        tk.Label(
            adv_frame,
            text=header,
            font=("Helvetica", 10, "bold"),
            fg="#333",
            wraplength=470,
            justify=tk.LEFT,
        ).pack(anchor="w")

        if isinstance(advisory_detail, str) and advisory_detail.strip():
            tk.Label(
                adv_frame,
                text=advisory_detail.strip(),
                font=("Helvetica", 9),
                fg="#555",
                wraplength=470,
                justify=tk.LEFT,
                pady=4,
            ).pack(anchor="w")

        self._build_advisory_buttons(adv_frame)

    def _build_advisory_buttons(self, adv_frame: tk.Frame) -> None:
        """Build advisory Acknowledge/Dismiss buttons."""
        btns = tk.Frame(adv_frame)
        btns.pack(fill=tk.X, pady=(6, 0))

        status_var = tk.StringVar(value="")
        tk.Label(btns, textvariable=status_var, font=("Helvetica", 9), fg="#666").pack(
            side=tk.RIGHT
        )

        def _fade_and_hide(frame: tk.Widget, steps: int = 6, delay: int = 60) -> None:
            try:
                for i in range(1, steps + 1):
                    grey = 0xF9 + int((0xFF - 0xF9) * i / steps)
                    colour = f"#{grey:02x}{grey:02x}{grey:02x}"
                    frame.after(
                        delay * i,
                        lambda c=colour: (
                            frame.configure(bg=c) if frame.winfo_exists() else None
                        ),
                    )
                frame.after(
                    delay * (steps + 1),
                    lambda: (frame.pack_forget() if frame.winfo_exists() else None),
                )
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                try:
                    frame.pack_forget()
                except (ImportError, OSError, ValueError, KeyError, AttributeError):
                    pass

        def _record(outcome: str, ack_btn: tk.Button, dis_btn: tk.Button) -> None:
            try:
                from tap_tone_pi.gui.directive_outcomes import (
                    record_latest_directive_outcome,
                )

                ok = record_latest_directive_outcome(
                    session_dir=pathlib.Path(self.session_dir),
                    outcome="ack" if outcome == "ack" else "dismiss",
                    component="gui",
                )
                status_var.set("Thanks — recorded." if ok else "Thanks.")
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                status_var.set("Thanks.")

            try:
                from tap_tone_pi.gui.advisory_state import mark_responded

                mark_responded(pathlib.Path(self.session_dir))
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                pass

            try:
                ack_btn.pack_forget()
                dis_btn.pack_forget()
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                pass
            _fade_and_hide(adv_frame)

        ack_btn = tk.Button(
            btns,
            text="Acknowledge",
            bg="#4CAF50",
            fg="white",
            font=("Helvetica", 9, "bold"),
            width=14,
            relief=tk.FLAT,
            cursor="hand2",
        )
        dis_btn = tk.Button(
            btns,
            text="Dismiss",
            bg="#9E9E9E",
            fg="white",
            font=("Helvetica", 9, "bold"),
            width=10,
            relief=tk.FLAT,
            cursor="hand2",
        )
        ack_btn.configure(command=lambda: _record("ack", ack_btn, dis_btn))
        dis_btn.configure(command=lambda: _record("dismiss", ack_btn, dis_btn))
        ack_btn.pack(side=tk.LEFT, padx=(0, 6))
        dis_btn.pack(side=tk.LEFT)

        try:
            from tap_tone_pi.gui.tooltip import Tooltip

            Tooltip(ack_btn, "Record that you reviewed and accept this advisory.")
            Tooltip(dis_btn, "Dismiss this advisory without acting on it.")
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass

    def _build_timeline_button(self, main: tk.Frame) -> None:
        """Build session timeline button if applicable. Fail-closed."""
        if self.session_dir is None or not HAS_TIMELINE_VIEWER:
            return
        try:
            tk.Button(
                main,
                text="📋 Timeline",
                command=lambda: TimelineViewerDialog(
                    self, pathlib.Path(self.session_dir)
                ),
                font=("Helvetica", 9),
                cursor="hand2",
            ).pack(anchor=tk.W, pady=(6, 0))
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass

    def _build_directive_history_toggle(self, main: tk.Frame) -> None:
        """Build directive history toggle checkbox."""
        if self.session_dir is None:
            return

        toggle_row = tk.Frame(main)
        toggle_row.pack(fill=tk.X, pady=(6, 0))

        def _on_toggle_history() -> None:
            self._show_directive_history = bool(self._show_history_var.get())
            if self.session_dir is not None:
                try:
                    from tap_tone_pi.gui.advisory_state import (
                        set_show_directive_history,
                    )

                    set_show_directive_history(
                        pathlib.Path(self.session_dir), self._show_directive_history
                    )
                except (ImportError, OSError, ValueError, KeyError, AttributeError):
                    pass
            self._render_directive_history_panel()

        tk.Checkbutton(
            toggle_row,
            text="Show directive history",
            variable=self._show_history_var,
            command=_on_toggle_history,
        ).pack(side=tk.LEFT)

    def _build_action_buttons(self, main: tk.Frame) -> None:
        """Build the action buttons based on verdict."""
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(15, 5))

        if self.verdict.verdict == Verdict.PASS:
            tk.Button(
                btn_frame,
                text="✓ Accept",
                command=self._do_accept,
                bg="#4CAF50",
                fg="white",
                font=("Helvetica", 11, "bold"),
                width=15,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=5)
        elif self.verdict.verdict == Verdict.WARN:
            tk.Button(
                btn_frame,
                text="Accept with Warnings",
                command=self._do_accept,
                bg="#FF9800",
                fg="white",
                font=("Helvetica", 10, "bold"),
                width=20,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                btn_frame,
                text="↻ Retry",
                command=self._do_retry,
                bg="#607D8B",
                fg="white",
                font=("Helvetica", 10),
                width=10,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=5)
        else:  # FAIL
            tk.Button(
                btn_frame,
                text="↻ Retry",
                command=self._do_retry,
                bg="#2196F3",
                fg="white",
                font=("Helvetica", 11, "bold"),
                width=15,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                btn_frame,
                text="Override...",
                command=self._do_override,
                bg="#9E9E9E",
                fg="white",
                font=("Helvetica", 10),
                width=12,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="Close",
            command=self.destroy,
            font=("Helvetica", 10),
            width=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=5)

    def __init__(
        self,
        parent: tk.Tk,
        verdict: "QualityVerdict",
        result: "AnalysisResult",
        on_accept: callable = None,
        on_retry: callable = None,
        on_override: callable = None,
        session_dir: "pathlib.Path | None" = None,
        title: str = "Quality Gate",
        show_directive_history: bool = False,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("520x480")
        self.resizable(False, False)
        self.verdict = verdict
        self.on_accept = on_accept
        self.on_retry = on_retry
        self.on_override = on_override
        self.session_dir = session_dir

        # Session-local persistence (PR #15.1): prefer persisted value
        _persisted_dh = None
        if session_dir is not None:
            try:
                from tap_tone_pi.gui.advisory_state import get_show_directive_history

                _persisted_dh = get_show_directive_history(
                    pathlib.Path(session_dir),
                    default=None,
                )
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                _persisted_dh = None

        if isinstance(_persisted_dh, bool):
            self._show_directive_history = _persisted_dh
        else:
            self._show_directive_history = bool(show_directive_history)

        self._directive_history_frame = None
        self._show_history_var = tk.IntVar(value=int(self._show_directive_history))

        # Main frame with better padding
        main = tk.Frame(self, padx=15, pady=15)
        self._main = main
        main.pack(fill=tk.BOTH, expand=True)

        # Verdict banner with icon
        self._build_verdict_banner(main)

        # Dominant frequency display
        self._build_freq_frame(main, result)

        # Analysis summary
        self._build_summary_frame(main, result)

        # Triggered rules
        self._build_triggered_rules_frame(main)

        # Trust erosion banner
        self._build_trust_erosion_banner(main)

        # Advisory directive
        self._build_advisory_directive(main)

        # Session Timeline button
        self._build_timeline_button(main)

        # Directive History toggle
        self._build_directive_history_toggle(main)
        self._render_directive_history_panel()

        # Action buttons
        self._build_action_buttons(main)

    def _render_directive_history_panel(self) -> None:
        """Create or remove the Directive History panel based on the toggle.

        Fail-closed: any error removes the panel silently.
        """
        # Tear down existing panel if present
        if self._directive_history_frame is not None:
            try:
                self._directive_history_frame.destroy()
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                pass
            self._directive_history_frame = None

        if not self._show_directive_history:
            return
        if self.session_dir is None:
            return

        try:
            from tap_tone_pi.agentic.spine.directive_history import (
                load_directive_events,
            )
            from tap_tone_pi.gui.directive_history_view import (
                format_directive_history,
            )

            # Optional moment id from shadow record
            moment_id = None
            try:
                from tap_tone_pi.agentic.spine.shadow_record import (
                    load_latest_shadow_record as _dh_load_shadow,
                )

                _dh_rec = _dh_load_shadow(pathlib.Path(self.session_dir))
                if isinstance(_dh_rec, dict):
                    _dh_m = _dh_rec.get("moment") or {}
                    if isinstance(_dh_m, dict):
                        _dh_mid = _dh_m.get("id")
                        if isinstance(_dh_mid, str) and _dh_mid.strip():
                            moment_id = _dh_mid.strip()
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                moment_id = None

            rows = load_directive_events(
                pathlib.Path(self.session_dir),
                limit=10,
            )
            lines = format_directive_history(
                rows,
                moment_id=moment_id,
                limit=10,
            )
            if not lines:
                return

            hist = tk.LabelFrame(
                self._main,
                text="Directive History",
                padx=10,
                pady=8,
            )
            hist.pack(fill=tk.X, pady=(8, 5))
            self._directive_history_frame = hist

            txt = tk.Text(
                hist,
                height=min(8, max(2, len(lines))),
                wrap=tk.NONE,
                font=("Courier New", 9),
                bd=0,
                highlightthickness=0,
            )
            txt.pack(fill=tk.X, expand=True)
            txt.insert("1.0", "\n".join(lines))
            txt.config(state=tk.DISABLED)
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            # Fail-closed: leave panel hidden
            return

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
            parent=self,
        )
        if reason and reason.strip():
            if self.on_override:
                self.on_override(reason.strip())
            self.destroy()
