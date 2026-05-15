"""Phase 1: Single-channel tap tone analysis.

This module provides the Phase 1 workflow for capturing and analyzing
tap tone impulse responses from guitar plates, tops, and backs.

Key components:
- Demo mode: Hardware-free testing with synthetic audio
- Analysis: FFT peak detection (uses tap_tone_pi.core.analysis)
- Quality: Measurement gating (uses tap_tone_pi.core.quality_gate)

Example:
    # Demo mode (no hardware required)
    from tap_tone_pi.phase1.demo import run_demo
    result = run_demo(fundamental_hz=245.0)

    # Real capture workflow (requires microphone)
    from tap_tone_pi.capture import record_audio
    from tap_tone_pi.core.analysis import analyze_tap
    from tap_tone_pi.core.quality_gate import check_quality

    cap = record_audio(sample_rate=48000, seconds=2.5)
    analysis = analyze_tap(cap.audio, cap.sample_rate)
    verdict = check_quality(analysis, sample_rate=cap.sample_rate, audio=cap.audio)
"""

from tap_tone_pi.phase1.demo import (
    TapImpulseConfig,
    DEFAULT_HARMONICS,
    generate_tap_impulse,
    run_demo,
)

__all__ = [
    "TapImpulseConfig",
    "DEFAULT_HARMONICS",
    "generate_tap_impulse",
    "run_demo",
]
