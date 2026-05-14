"""Tests for auto-trigger detector (Phase 10)."""

from __future__ import annotations
from unittest.mock import patch
import numpy as np
import pytest


class TestTriggerConfig:
    def test_default_config_valid(self):
        from tap_tone_pi.core.auto_trigger import TriggerConfig

        cfg = TriggerConfig()
        assert cfg.threshold_rms == 0.01

    def test_invalid_threshold_rms_raises(self):
        from tap_tone_pi.core.auto_trigger import TriggerConfig

        with pytest.raises(ValueError, match="threshold_rms"):
            TriggerConfig(threshold_rms=0.0)


class TestTriggerResult:
    def test_duration_with_audio(self):
        from tap_tone_pi.core.auto_trigger import TriggerResult, TriggerState

        audio = np.zeros(48000)
        result = TriggerResult(
            state=TriggerState.COMPLETED,
            audio=audio,
            sample_rate=48000,
            triggered=True,
        )
        assert abs(result.duration_seconds - 1.0) < 0.001

    def test_duration_without_audio(self):
        from tap_tone_pi.core.auto_trigger import TriggerResult, TriggerState

        result = TriggerResult(state=TriggerState.TIMEOUT)
        assert result.duration_seconds == 0.0


class TestAutoTriggerDetectorUnit:
    def test_compute_rms_silent(self):
        from tap_tone_pi.core.auto_trigger import AutoTriggerDetector, TriggerConfig

        with patch("tap_tone_pi.core.auto_trigger.HAS_SOUNDDEVICE", True):
            detector = AutoTriggerDetector(sample_rate=48000, config=TriggerConfig())
            audio = np.zeros(960)
            rms = detector._compute_rms(audio)
            assert rms == 0.0

    def test_is_trigger_adaptive(self):
        from tap_tone_pi.core.auto_trigger import AutoTriggerDetector, TriggerConfig

        with patch("tap_tone_pi.core.auto_trigger.HAS_SOUNDDEVICE", True):
            config = TriggerConfig(use_adaptive=True, threshold_multiplier=3.0)
            detector = AutoTriggerDetector(sample_rate=48000, config=config)
            detector._baseline_rms = 0.01
            assert not detector._is_trigger(0.02)
            assert detector._is_trigger(0.04)


class TestCaptureModuleExports:
    def test_auto_trigger_exports_from_capture(self):
        from tap_tone_pi.capture import (
            TriggerState,
        )

        assert TriggerState is not None
