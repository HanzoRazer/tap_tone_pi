"""Tests for CLI preflight module."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from tap_tone_pi.cli.preflight import (
    run_preflight,
    print_preflight_result,
    require_preflight,
    PreflightResult,
)


class TestPreflightResult:
    """Tests for PreflightResult dataclass."""

    def test_ok_result(self):
        """Test creating an OK result."""
        result = PreflightResult(
            ok=True,
            device_name="Test Mic",
            sample_rate=48000,
            peak_level=0.5,
            rms_level=0.1,
            clipped=False,
            message="Hardware check passed",
        )
        assert result.ok is True
        assert result.device_name == "Test Mic"
        assert result.suggestion is None

    def test_failed_result_with_suggestion(self):
        """Test creating a failed result with suggestion."""
        result = PreflightResult(
            ok=False,
            device_name="Test Mic",
            sample_rate=48000,
            peak_level=0.0,
            rms_level=0.0,
            clipped=False,
            message="No audio detected",
            suggestion="Check microphone connection",
        )
        assert result.ok is False
        assert result.suggestion == "Check microphone connection"


class TestRunPreflight:
    """Tests for run_preflight function."""

    def test_no_devices_fails(self):
        """Should fail if no audio devices found."""
        with patch("tap_tone_pi.capture.list_devices", return_value=[]):
            result = run_preflight(quiet=True)
            assert result.ok is False
            assert "No audio" in result.message

    def test_device_not_found_fails(self):
        """Should fail if specified device doesn't exist."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2, "name": "Mic 1"},
        ]
        with patch("tap_tone_pi.capture.list_devices", return_value=mock_devices):
            result = run_preflight(device=99, quiet=True)
            assert result.ok is False
            assert "not found" in result.message

    def test_recording_failure_fails(self):
        """Should fail if recording throws exception."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2, "name": "Mic 1"},
        ]
        with patch("tap_tone_pi.capture.list_devices", return_value=mock_devices):
            with patch(
                "tap_tone_pi.capture.record_audio",
                side_effect=Exception("Device error"),
            ):
                result = run_preflight(device=0, quiet=True)
                assert result.ok is False
                assert "Failed to open" in result.message

    def test_silent_audio_fails(self):
        """Should fail if audio is silent."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2, "name": "Mic 1"},
        ]
        mock_capture = MagicMock()
        mock_capture.audio = np.zeros(1000, dtype=np.float32)  # silent

        with patch("tap_tone_pi.capture.list_devices", return_value=mock_devices):
            with patch("tap_tone_pi.capture.record_audio", return_value=mock_capture):
                result = run_preflight(device=0, quiet=True)
                assert result.ok is False
                assert "silent" in result.message.lower()

    def test_clipping_audio_fails(self):
        """Should fail if audio is clipping."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2, "name": "Mic 1"},
        ]
        mock_capture = MagicMock()
        # Audio at full scale = clipping
        mock_capture.audio = np.ones(1000, dtype=np.float32)

        with patch("tap_tone_pi.capture.list_devices", return_value=mock_devices):
            with patch("tap_tone_pi.capture.record_audio", return_value=mock_capture):
                result = run_preflight(device=0, quiet=True)
                assert result.ok is False
                assert "clipping" in result.message.lower()

    def test_good_audio_passes(self):
        """Should pass with reasonable audio levels."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2, "name": "Mic 1"},
        ]
        mock_capture = MagicMock()
        # Reasonable audio: RMS ~0.1, peak ~0.5
        mock_capture.audio = np.random.randn(1000).astype(np.float32) * 0.2

        with patch("tap_tone_pi.capture.list_devices", return_value=mock_devices):
            with patch("tap_tone_pi.capture.record_audio", return_value=mock_capture):
                result = run_preflight(device=0, quiet=True)
                assert result.ok is True
                assert "passed" in result.message.lower()

    def test_high_but_not_clipping_passes_with_warning(self):
        """Should pass but warn if levels are high."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2, "name": "Mic 1"},
        ]
        mock_capture = MagicMock()
        # High but not clipping: peak ~0.95, use constant to avoid randomness
        mock_capture.audio = np.full(1000, 0.3, dtype=np.float32)
        mock_capture.audio[500] = 0.95  # one high peak

        with patch("tap_tone_pi.capture.list_devices", return_value=mock_devices):
            with patch("tap_tone_pi.capture.record_audio", return_value=mock_capture):
                result = run_preflight(device=0, quiet=True)
                assert result.ok is True
                assert result.suggestion is not None  # should have a warning

    def test_low_audio_passes_with_warning(self):
        """Should pass but warn if levels are low."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2, "name": "Mic 1"},
        ]
        mock_capture = MagicMock()
        # Low but not silent: RMS ~0.005
        mock_capture.audio = np.random.randn(1000).astype(np.float32) * 0.005

        with patch("tap_tone_pi.capture.list_devices", return_value=mock_devices):
            with patch("tap_tone_pi.capture.record_audio", return_value=mock_capture):
                result = run_preflight(device=0, quiet=True)
                assert result.ok is True
                assert "low" in result.message.lower()


class TestPrintPreflightResult:
    """Tests for print_preflight_result function."""

    def test_prints_ok_result(self, capsys):
        """Should print OK status."""
        result = PreflightResult(
            ok=True,
            device_name="Test Mic",
            sample_rate=48000,
            peak_level=0.5,
            rms_level=0.1,
            clipped=False,
            message="Hardware check passed",
        )
        print_preflight_result(result)
        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "Test Mic" in captured.out

    def test_prints_fail_result(self, capsys):
        """Should print FAIL status."""
        result = PreflightResult(
            ok=False,
            device_name="Test Mic",
            sample_rate=48000,
            peak_level=0.0,
            rms_level=0.0,
            clipped=False,
            message="No audio detected",
            suggestion="Check connection",
        )
        print_preflight_result(result)
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out
        assert "Suggestion" in captured.out

    def test_prints_clipped_flag(self, capsys):
        """Should indicate clipping."""
        result = PreflightResult(
            ok=False,
            device_name="Test Mic",
            sample_rate=48000,
            peak_level=1.0,
            rms_level=0.9,
            clipped=True,
            message="Audio is clipping",
        )
        print_preflight_result(result)
        captured = capsys.readouterr()
        assert "Clipped: YES" in captured.out


class TestRequirePreflight:
    """Tests for require_preflight function."""

    def test_skip_returns_none(self):
        """Should return None if skip=True."""
        result = require_preflight(skip=True)
        assert result is None

    def test_passes_returns_result(self):
        """Should return result if preflight passes."""
        mock_result = PreflightResult(
            ok=True,
            device_name="Test",
            sample_rate=48000,
            peak_level=0.5,
            rms_level=0.1,
            clipped=False,
            message="Passed",
        )
        with patch("tap_tone_pi.cli.preflight.run_preflight", return_value=mock_result):
            result = require_preflight()
            assert result is not None
            assert result.ok is True

    def test_fails_exits(self):
        """Should exit if preflight fails."""
        mock_result = PreflightResult(
            ok=False,
            device_name="Test",
            sample_rate=48000,
            peak_level=0.0,
            rms_level=0.0,
            clipped=False,
            message="Failed",
        )
        with patch("tap_tone_pi.cli.preflight.run_preflight", return_value=mock_result):
            with pytest.raises(SystemExit) as exc_info:
                require_preflight()
            assert exc_info.value.code == 1
