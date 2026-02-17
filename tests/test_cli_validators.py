"""Tests for CLI validators module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tap_tone_pi.cli.validators import (
    validate_device_index,
    validate_output_dir,
    validate_sample_rate,
    validate_duration,
    validate_file_exists,
    confirm_overwrite,
    confirm_action,
    _format_bytes,
)


class TestValidateDeviceIndex:
    """Tests for validate_device_index."""

    def test_none_returns_none(self):
        """None device index should return None."""
        assert validate_device_index(None) is None

    def test_valid_device_returns_index(self):
        """Valid device index should be returned."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2},
            {"index": 1, "max_input_channels": 0},
            {"index": 2, "max_input_channels": 1},
        ]
        with patch(
            "tap_tone_pi.capture.list_devices", return_value=mock_devices
        ):
            assert validate_device_index(0) == 0
            assert validate_device_index(2) == 2

    def test_invalid_device_exits(self):
        """Invalid device index should exit."""
        mock_devices = [
            {"index": 0, "max_input_channels": 2},
        ]
        with patch(
            "tap_tone_pi.capture.list_devices", return_value=mock_devices
        ):
            with pytest.raises(SystemExit) as exc_info:
                validate_device_index(99)
            assert exc_info.value.code == 1

    def test_output_only_device_rejected(self):
        """Device with no input channels should be rejected."""
        mock_devices = [
            {"index": 0, "max_input_channels": 0},  # output only
            {"index": 1, "max_input_channels": 2},
        ]
        with patch(
            "tap_tone_pi.capture.list_devices", return_value=mock_devices
        ):
            with pytest.raises(SystemExit):
                validate_device_index(0)


class TestValidateOutputDir:
    """Tests for validate_output_dir."""

    def test_valid_path_returns_path(self, tmp_path):
        """Valid path should return Path object."""
        result = validate_output_dir(str(tmp_path))
        assert result == tmp_path

    def test_new_subdir_in_existing_parent(self, tmp_path):
        """New subdirectory in existing parent should be valid."""
        new_dir = tmp_path / "new_session"
        result = validate_output_dir(str(new_dir))
        assert result == new_dir

    def test_nonexistent_parent_exits(self, tmp_path):
        """Path with nonexistent parent should exit."""
        bad_path = tmp_path / "nonexistent" / "deep" / "path"
        with pytest.raises(SystemExit) as exc_info:
            validate_output_dir(str(bad_path))
        assert exc_info.value.code == 1

    def test_must_exist_with_existing_dir(self, tmp_path):
        """must_exist=True with existing dir should pass."""
        result = validate_output_dir(str(tmp_path), must_exist=True)
        assert result == tmp_path

    def test_must_exist_with_nonexistent_exits(self, tmp_path):
        """must_exist=True with nonexistent dir should exit."""
        bad_path = tmp_path / "does_not_exist"
        with pytest.raises(SystemExit):
            validate_output_dir(str(bad_path), must_exist=True)


class TestValidateSampleRate:
    """Tests for validate_sample_rate."""

    def test_standard_rates_pass(self):
        """Standard sample rates should pass."""
        for rate in [8000, 44100, 48000, 96000]:
            assert validate_sample_rate(rate) == rate

    def test_too_low_exits(self):
        """Sample rate below minimum should exit."""
        with pytest.raises(SystemExit):
            validate_sample_rate(4000)

    def test_too_high_exits(self):
        """Sample rate above maximum should exit."""
        with pytest.raises(SystemExit):
            validate_sample_rate(500000)

    def test_nonstandard_rate_warns(self, capsys):
        """Non-standard rate should warn but pass."""
        result = validate_sample_rate(22000)  # non-standard
        assert result == 22000
        captured = capsys.readouterr()
        assert "Warning" in captured.err or "Non-standard" in captured.err


class TestValidateDuration:
    """Tests for validate_duration."""

    def test_valid_duration_passes(self):
        """Valid duration should pass."""
        assert validate_duration(2.5) == 2.5
        assert validate_duration(1.0) == 1.0

    def test_zero_exits(self):
        """Zero duration should exit."""
        with pytest.raises(SystemExit):
            validate_duration(0)

    def test_negative_exits(self):
        """Negative duration should exit."""
        with pytest.raises(SystemExit):
            validate_duration(-1.0)

    def test_short_duration_warns(self, capsys):
        """Very short duration should warn."""
        result = validate_duration(0.1)
        assert result == 0.1
        captured = capsys.readouterr()
        assert "Warning" in captured.err or "short" in captured.err.lower()

    def test_long_duration_warns(self, capsys):
        """Very long duration should warn."""
        result = validate_duration(60.0)
        assert result == 60.0
        captured = capsys.readouterr()
        assert "Warning" in captured.err or "long" in captured.err.lower()


class TestValidateFileExists:
    """Tests for validate_file_exists."""

    def test_existing_file_passes(self, tmp_path):
        """Existing file should pass."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = validate_file_exists(str(test_file))
        assert result == test_file

    def test_nonexistent_exits(self, tmp_path):
        """Nonexistent file should exit."""
        bad_file = tmp_path / "missing.txt"
        with pytest.raises(SystemExit):
            validate_file_exists(str(bad_file))

    def test_directory_exits(self, tmp_path):
        """Directory (not file) should exit."""
        with pytest.raises(SystemExit):
            validate_file_exists(str(tmp_path))


class TestConfirmOverwrite:
    """Tests for confirm_overwrite."""

    def test_nonexistent_returns_true(self, tmp_path):
        """Nonexistent path should return True without prompting."""
        result = confirm_overwrite(tmp_path / "missing.zip")
        assert result is True

    def test_force_skips_prompt(self, tmp_path):
        """force=True should skip prompt."""
        test_file = tmp_path / "existing.zip"
        test_file.write_text("data")
        result = confirm_overwrite(test_file, force=True)
        assert result is True

    def test_user_confirms_yes(self, tmp_path):
        """User entering 'y' should return True."""
        test_file = tmp_path / "existing.zip"
        test_file.write_text("data")
        with patch("builtins.input", return_value="y"):
            result = confirm_overwrite(test_file)
            assert result is True

    def test_user_declines_exits(self, tmp_path):
        """User entering 'n' should exit."""
        test_file = tmp_path / "existing.zip"
        test_file.write_text("data")
        with patch("builtins.input", return_value="n"):
            with pytest.raises(SystemExit) as exc_info:
                confirm_overwrite(test_file)
            assert exc_info.value.code == 0  # graceful exit


class TestConfirmAction:
    """Tests for confirm_action."""

    def test_force_skips_prompt(self):
        """force=True should skip prompt."""
        result = confirm_action("Delete everything?", force=True)
        assert result is True

    def test_user_confirms_yes(self):
        """User entering 'yes' should return True."""
        with patch("builtins.input", return_value="yes"):
            result = confirm_action("Delete everything?")
            assert result is True

    def test_user_declines_exits(self):
        """User entering 'no' should exit."""
        with patch("builtins.input", return_value="no"):
            with pytest.raises(SystemExit) as exc_info:
                confirm_action("Delete everything?")
            assert exc_info.value.code == 0


class TestFormatBytes:
    """Tests for _format_bytes helper."""

    def test_bytes(self):
        assert _format_bytes(500) == "500 B"

    def test_kilobytes(self):
        assert _format_bytes(2048) == "2.0 KB"

    def test_megabytes(self):
        assert _format_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert _format_bytes(2 * 1024 * 1024 * 1024) == "2.0 GB"
