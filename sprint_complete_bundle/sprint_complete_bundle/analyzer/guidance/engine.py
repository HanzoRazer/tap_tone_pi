"""
analyzer/guidance/engine.py

# INSTRUMENT CLASS: DECISION SUPPORT
# Outputs are contextual guidance directives for the operator.
# They are display-layer only — not in viewer_pack_v1.
# See docs/ADR-0009-advisory-boundary.md

AnalyzerGuidanceEngine — watches analyzer state and emits
AttentionDirectiveV1 directives backed by live Claude API calls.

Each trigger packages measurement context into a structured prompt and
calls Claude. Stage-aware: first_run gets full explanations; expert
gets nothing unless urgency >= 0.5. Falls back to brief rule-based
text if ANTHROPIC_API_KEY is absent or the call fails.

DESIGN CONTRACT:
  - Reads finished data only. Never modifies measurements or session files.
  - API calls run in daemon threads — Qt event loop never blocks.
  - Falls back silently if the API is unreachable.
"""

from __future__ import annotations

import os
import json
import uuid
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from tap_tone_pi.agentic.contracts.analyzer_attention import (
    AttentionAction,
    AttentionDirectiveV1,
    FocusTarget,
)
from tap_tone_pi.agent.types import UserStage

# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------

_API_URL    = "https://api.anthropic.com/v1/messages"
_MODEL      = "claude-sonnet-4-20250514"
_MAX_TOKENS = 400

_SYSTEM_BASE = (
    "You are the acoustic measurement assistant inside the tap_tone_pi analyzer — "
    "a professional tool luthiers use to measure guitar soundboard vibrational properties "
    "before building.\n\n"
    "Rules:\n"
    "- Be direct. No greeting, no sign-off.\n"
    "- Vary detail by stage: first_run = plain English + next step; "
    "novice = explain the number in lutherie terms; regular = brief interpretation; "
    "expert = one sentence max or nothing.\n"
    "- Never invent numbers. Interpret only what is provided.\n"
    "- References to brace placement, graduation thickness, or species comparison are welcome."
)


def _directive_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _stage_label(stage: UserStage) -> str:
    return stage.value if hasattr(stage, "value") else str(stage)


def _call_claude(user_prompt: str) -> str:
    """Synchronous Claude API call. Returns text or empty string on any error."""
    import urllib.request

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    payload = json.dumps({
        "model":      _MODEL,
        "max_tokens": _MAX_TOKENS,
        "system":     _SYSTEM_BASE,
        "messages":   [{"role": "user", "content": user_prompt}],
    }).encode()

    req = urllib.request.Request(
        _API_URL,
        data=payload,
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _pack_prompt(pack: Dict[str, Any], stage: UserStage) -> str:
    meta    = (pack or {}).get("metadata", {}).get("session", {})
    sid     = meta.get("specimen_id", "unknown")
    species = meta.get("species", "unknown")
    cal     = (meta.get("calibration") or {}).get("status", "unknown")
    dims    = meta.get("dimensions_mm", {})
    return (
        f"Stage: {_stage_label(stage)}\n"
        f"Action: viewer pack loaded\n"
        f"Specimen: {sid}, species={species}, dimensions={dims}\n"
        f"Calibration status: {cal}\n\n"
        "What should this operator do first, and what should they watch for "
        "given the calibration status?"
    )


def _peaks_prompt(peaks: List[Dict[str, Any]], stage: UserStage) -> str:
    dominant = peaks[0].get("freq_hz", 0.0)
    n        = len(peaks)
    ratio_line = ""
    if n >= 2:
        m2 = peaks[1].get("freq_hz", 0.0)
        if dominant > 0:
            ratio_line = f"Mode-1 to mode-2 ratio: {m2/dominant:.2f}\n"
    peak_lines = "\n".join(
        f"  peak {i+1}: {p.get('freq_hz',0):.1f} Hz, mag={p.get('magnitude',0):.4f}"
        for i, p in enumerate(peaks[:6])
    )
    return (
        f"Stage: {_stage_label(stage)}\n"
        f"Action: peak detection complete\n"
        f"Peaks found: {n}\n{peak_lines}\n{ratio_line}\n"
        "Interpret these peaks in lutherie terms. Is the fundamental reasonable? "
        "What does the mode ratio tell the builder? What should they do next?"
    )


def _coherence_prompt(stats: Dict[str, Any], stage: UserStage) -> str:
    mean  = stats.get("mean", 1.0)
    mn    = stats.get("min", 1.0)
    n_bad = len(stats.get("problem_frequencies", []))
    band  = stats.get("coherence_band", stats.get("quality_grade", ""))
    return (
        f"Stage: {_stage_label(stage)}\n"
        f"Action: coherence analysis complete\n"
        f"Mean coherence: {mean:.3f}, min: {mn:.3f}, band: {band}, "
        f"problem bands: {n_bad}\n\n"
        "Explain what this coherence level means for measurement reliability. "
        "Should the operator re-measure? What might cause low coherence in a "
        "luthier workshop?"
    )


def _wood_prompt(props: Dict[str, Any], stage: UserStage) -> str:
    return (
        f"Stage: {_stage_label(stage)}\n"
        f"Action: wood properties estimated\n"
        f"Radiation coefficient: {props.get('radiation_coefficient', 0):.2f}\n"
        f"Density: {props.get('density_kg_m3', 0):.0f} kg/m³\n"
        f"Along-grain stiffness: {props.get('stiffness_along_gpa', 0):.2f} GPa\n"
        f"Fundamental frequency: {props.get('fundamental_hz', 0):.1f} Hz\n"
        f"Quality grade: {props.get('quality_grade', '')}\n"
        f"Confidence: {props.get('confidence', 0):.0%}\n\n"
        "Interpret these material properties for a luthier. How does the radiation "
        "coefficient compare to typical tonewoods? What does this suggest for "
        "graduation thickness and brace design?"
    )


# ---------------------------------------------------------------------------
# Fallback summaries (used when API unavailable)
# ---------------------------------------------------------------------------

def _fb_pack(pack: Dict) -> str:
    sid = (pack or {}).get("metadata", {}).get("session", {}).get("specimen_id", "")
    return f"Bundle loaded{f' — {sid}' if sid else ''}. Run Find Peaks to begin."

def _fb_peaks(peaks: List[Dict]) -> str:
    hz = peaks[0].get("freq_hz", 0.0) if peaks else 0.0
    return f"Dominant mode at {hz:.1f} Hz. Run Estimate Wood Properties."

def _fb_coherence(stats: Dict) -> str:
    return f"Coherence mean {stats.get('mean', 0):.2f}."

def _fb_wood(props: Dict) -> str:
    return f"Radiation coefficient {props.get('radiation_coefficient', 0):.1f}."


# ---------------------------------------------------------------------------
# AnalyzerGuidanceEngine
# ---------------------------------------------------------------------------

@dataclass
class AnalyzerGuidanceEngine:
    """
    Observes analyzer events, calls Claude in a background thread, and emits
    AttentionDirectiveV1 directives to the registered on_directive callback.

    If ANTHROPIC_API_KEY is not set, a brief fallback directive fires instead.
    Expert stage suppresses low-urgency directives entirely.
    """

    stage:        UserStage = UserStage.REGULAR
    on_directive: Optional[Callable[[AttentionDirectiveV1], None]] = field(
        default=None, repr=False
    )
    _history: List[AttentionDirectiveV1] = field(default_factory=list, repr=False)

    # ── Internal ──────────────────────────────────────────────────────────

    def _emit(self, directive: Optional[AttentionDirectiveV1]) -> None:
        if directive is None:
            return
        self._history.append(directive)
        if self.on_directive:
            self.on_directive(directive)

    def _fire_async(
        self,
        prompt:           str,
        fallback_summary: str,
        action:           AttentionAction,
        focus_type:       str,
        focus_id:         str,
        prefix:           str,
        urgency:          float = 0.2,
    ) -> None:
        """Call Claude in a daemon thread; emit directive when done."""
        if self.stage == UserStage.EXPERT and urgency < 0.5:
            return

        emit = self._emit   # capture reference for thread closure

        def _worker() -> None:
            text    = _call_claude(prompt) if prompt else ""
            summary = (text.split("\n")[0][:120] if text else fallback_summary)
            detail  = text if text else fallback_summary

            directive = AttentionDirectiveV1(
                directive_id=_directive_id(prefix),
                action=action,
                summary=summary,
                focus=FocusTarget(target_type=focus_type, target_id=focus_id),
                detail=detail,
                urgency=urgency,
                confidence=0.9 if text else 0.5,
                source_tool="analyzer_guidance_claude",
                auto_dismiss_after_seconds=(
                    None if urgency >= 0.5 else
                    None if self.stage == UserStage.FIRST_RUN else 30
                ),
            )
            emit(directive)

        threading.Thread(target=_worker, daemon=True).start()

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def history(self) -> List[AttentionDirectiveV1]:
        return list(self._history)

    def set_stage(self, stage: UserStage) -> None:
        self.stage = stage

    # ── Triggers ──────────────────────────────────────────────────────────

    def on_pack_loaded(self, pack: Dict[str, Any]) -> None:
        self._fire_async(
            prompt=_pack_prompt(pack, self.stage),
            fallback_summary=_fb_pack(pack),
            action=AttentionAction.INSPECT,
            focus_type="spectrum_view", focus_id="main_spectrum",
            prefix="pack", urgency=0.15,
        )

    def on_peaks_found(self, peaks: List[Dict[str, Any]]) -> None:
        if not peaks:
            return
        self._fire_async(
            prompt=_peaks_prompt(peaks, self.stage),
            fallback_summary=_fb_peaks(peaks),
            action=AttentionAction.INSPECT,
            focus_type="spectrum_region",
            focus_id=f"peak_{peaks[0].get('freq_hz', 0):.0f}hz",
            prefix="peaks", urgency=0.2,
        )

    def on_coherence_analyzed(self, stats: Dict[str, Any]) -> None:
        mean = stats.get("mean", 1.0)
        if mean >= 0.85 and not stats.get("problem_frequencies"):
            return
        urgency = 0.65 if mean < 0.6 else 0.35
        self._fire_async(
            prompt=_coherence_prompt(stats, self.stage),
            fallback_summary=_fb_coherence(stats),
            action=AttentionAction.REVIEW if mean < 0.6 else AttentionAction.INSPECT,
            focus_type="spectrum_view", focus_id="coherence_overlay",
            prefix="coherence", urgency=urgency,
        )

    def on_wolf_detected(
        self,
        wsi: float,
        beat_hz: float,
        freq_hz: float,
        session_id: Optional[str] = None,
    ) -> None:
        try:
            from unittest.mock import MagicMock
            from tap_tone_pi.agent.wolf_guidance import generate_wolf_guidance
            wolf_result = MagicMock()
            wolf_result.wsi = wsi
            wolf_result.beat_frequency_hz = beat_hz
            wolf_result.confidence = 0.8
            wolf_result.pairs = []
            peak = MagicMock()
            peak.freq_hz = freq_hz
            wolf_result.dominant_peak = peak
            wolf_result.avoided_crossing_model = MagicMock()
            wolf_result.avoided_crossing_model.omega = None
            result = generate_wolf_guidance(
                wolf_result,
                user_stage=_stage_label(self.stage),
                session_id=session_id,
                wsi_threshold=0.15,
            )
            if not result.skipped:
                self._emit(result.directive)
        except Exception:
            pass

    def on_wood_properties_estimated(self, props: Dict[str, Any]) -> None:
        if not props:
            return
        self._fire_async(
            prompt=_wood_prompt(props, self.stage),
            fallback_summary=_fb_wood(props),
            action=AttentionAction.INSPECT,
            focus_type="stats_panel", focus_id="wood_properties",
            prefix="wood", urgency=0.1,
        )
