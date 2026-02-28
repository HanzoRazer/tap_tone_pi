"""Tests for core errors module."""

from __future__ import annotations

import time

import pytest

from tap_tone_pi.core.errors import (
    TapToneError,
    DeviceError,
    DeviceNotFoundError,
    DeviceOpenError,
    CaptureError,
    CaptureTimeoutError,
    AnalysisError,
    QualityError,
    ValidationError,
    FileFormatError,
    ConfigError,
    RetryConfig,
    with_retry,
    ErrorContext,
    format_error_for_user,
    handle_device_error,
)


class TestExceptionHierarchy:
    """Tests for custom exception hierarchy."""

    def test_taptone_error_base(self):
        """TapToneError should be base for all custom errors."""
        err = TapToneError("Test error")
        assert str(err) == "Test error"
        assert err.suggestion is None

    def test_taptone_error_with_suggestion(self):
        """TapToneError can include a suggestion."""
        err = TapToneError("Test error", suggestion="Try this fix")
        assert err.suggestion == "Try this fix"

    def test_device_error_hierarchy(self):
        """Device errors should inherit from TapToneError."""
        assert issubclass(DeviceError, TapToneError)
        assert issubclass(DeviceNotFoundError, DeviceError)
        assert issubclass(DeviceOpenError, DeviceError)

    def test_capture_error_hierarchy(self):
        """Capture errors should inherit from TapToneError."""
        assert issubclass(CaptureError, TapToneError)
        assert issubclass(CaptureTimeoutError, CaptureError)

    def test_other_errors_inherit_from_base(self):
        """All custom errors should inherit from TapToneError."""
        for err_class in [AnalysisError, QualityError, ValidationError,
                          FileFormatError, ConfigError]:
            assert issubclass(err_class, TapToneError)

    def test_can_catch_by_base_class(self):
        """Should be able to catch specific errors with base class."""
        with pytest.raises(TapToneError):
            raise DeviceNotFoundError("Device 5 not found")

        with pytest.raises(DeviceError):
            raise DeviceOpenError("Cannot open device")


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.delay_seconds == 0.5
        assert config.backoff_factor == 2.0
        assert config.exceptions == (Exception,)

    def test_custom_values(self):
        """Should accept custom values."""
        config = RetryConfig(
            max_attempts=5,
            delay_seconds=1.0,
            backoff_factor=3.0,
            exceptions=(DeviceError, CaptureError),
        )
        assert config.max_attempts == 5
        assert config.delay_seconds == 1.0
        assert config.backoff_factor == 3.0
        assert config.exceptions == (DeviceError, CaptureError)

    def test_is_frozen(self):
        """Config should be immutable."""
        config = RetryConfig()
        with pytest.raises(AttributeError):
            config.max_attempts = 10


class TestWithRetry:
    """Tests for with_retry decorator."""

    def test_success_on_first_try(self):
        """Should return immediately on success."""
        call_count = 0

        @with_retry(max_attempts=3)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()
        assert result == "success"
        assert call_count == 1

    def test_retries_on_failure(self):
        """Should retry on transient failures."""
        call_count = 0

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")
            return "success"

        result = fails_twice()
        assert result == "success"
        assert call_count == 3

    def test_raises_after_max_attempts(self):
        """Should raise after exhausting retries."""
        call_count = 0

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")

        with pytest.raises(ValueError, match="Permanent error"):
            always_fails()
        assert call_count == 3

    def test_only_catches_specified_exceptions(self):
        """Should only retry on specified exception types."""
        call_count = 0

        @with_retry(max_attempts=3, exceptions=(ValueError,), delay_seconds=0.01)
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            raises_type_error()
        assert call_count == 1  # No retry

    def test_exponential_backoff(self):
        """Should apply exponential backoff between retries."""
        timestamps = []

        @with_retry(max_attempts=3, delay_seconds=0.05)
        def track_timing():
            timestamps.append(time.time())
            if len(timestamps) < 3:
                raise ValueError("Retry")
            return "done"

        track_timing()

        # First retry delay should be ~0.05s
        first_delay = timestamps[1] - timestamps[0]
        assert 0.04 < first_delay < 0.2

        # Second retry delay should be ~0.1s (backoff factor 2.0)
        second_delay = timestamps[2] - timestamps[1]
        assert second_delay > first_delay * 1.5  # Allow some tolerance

    def test_with_config_object(self):
        """Should accept RetryConfig object."""
        call_count = 0
        config = RetryConfig(max_attempts=2, delay_seconds=0.01)

        @with_retry(config)
        def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Once")
            return "ok"

        result = fails_once()
        assert result == "ok"
        assert call_count == 2

    def test_preserves_function_metadata(self):
        """Decorator should preserve function name and docstring."""
        @with_retry()
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestErrorContext:
    """Tests for ErrorContext dataclass."""

    def test_basic_context(self):
        """Should format basic error context."""
        ctx = ErrorContext(operation="recording")
        err = ValueError("Failed")
        msg = ctx.format_message(err)
        assert "recording" in msg
        assert "Failed" in msg

    def test_with_device(self):
        """Should include device info."""
        ctx = ErrorContext(operation="opening", device="USB Mic")
        err = ValueError("Failed")
        msg = ctx.format_message(err)
        assert "USB Mic" in msg

    def test_with_file_path(self):
        """Should include file path."""
        ctx = ErrorContext(operation="loading", file_path="/path/to/file.wav")
        err = ValueError("Failed")
        msg = ctx.format_message(err)
        assert "/path/to/file.wav" in msg

    def test_with_details(self):
        """Should include arbitrary details."""
        ctx = ErrorContext(
            operation="analysis",
            details={"sample_rate": 48000, "duration": 2.5}
        )
        err = ValueError("Failed")
        msg = ctx.format_message(err)
        assert "sample_rate" in msg
        assert "48000" in msg


class TestFormatErrorForUser:
    """Tests for format_error_for_user function."""

    def test_plain_error(self):
        """Should format plain error."""
        err = ValueError("Something went wrong")
        msg = format_error_for_user(err)
        assert "Something went wrong" in msg

    def test_error_with_context(self):
        """Should include context info."""
        err = ValueError("Device failed")
        ctx = ErrorContext(operation="capture", device="Mic 1")
        msg = format_error_for_user(err, ctx)
        assert "capture" in msg
        assert "Mic 1" in msg

    def test_taptone_error_with_suggestion(self):
        """Should include suggestion from TapToneError."""
        err = DeviceNotFoundError(
            "Device 5 not found",
            suggestion="Run 'ttp devices' to list available devices"
        )
        msg = format_error_for_user(err)
        assert "Device 5 not found" in msg
        assert "Suggestion" in msg
        assert "ttp devices" in msg


class TestHandleDeviceError:
    """Tests for handle_device_error function."""

    def test_not_found_error(self):
        """Should create DeviceNotFoundError for 'not found' messages."""
        err = Exception("Device not found")
        result = handle_device_error(err, device_id=5)
        assert isinstance(result, DeviceNotFoundError)
        assert "5" in str(result)
        assert result.suggestion is not None

    def test_invalid_device_error(self):
        """Should create DeviceNotFoundError for 'invalid' messages."""
        err = Exception("Invalid device index")
        result = handle_device_error(err, device_id=99)
        assert isinstance(result, DeviceNotFoundError)

    def test_permission_error(self):
        """Should create DeviceOpenError for permission issues."""
        err = Exception("Permission denied")
        result = handle_device_error(err, device_id=0)
        assert isinstance(result, DeviceOpenError)
        assert "permission" in result.suggestion.lower()

    def test_busy_device_error(self):
        """Should create DeviceOpenError for busy device."""
        err = Exception("Device is in use by another application")
        result = handle_device_error(err, device_id=0)
        assert isinstance(result, DeviceOpenError)
        assert "busy" in str(result).lower() or "in use" in str(result).lower()

    def test_generic_error(self):
        """Should create generic DeviceError for unknown issues."""
        err = Exception("Unknown problem")
        result = handle_device_error(err, device_id=0)
        assert isinstance(result, DeviceError)
        assert not isinstance(result, DeviceNotFoundError)
        assert not isinstance(result, DeviceOpenError)
