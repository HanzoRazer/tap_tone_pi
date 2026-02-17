#!/usr/bin/env python3
"""Tests for retry decorator.

m5 Audit Fix: Untested Retry Decorator.
Add tests for all retry scenarios: success, partial failure, complete failure, timeout.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from tap_tone_pi.core.errors import (
    RetryConfig,
    with_retry,
    DeviceError,
    CaptureError,
    TapToneError,
)


class TestRetryDecoratorSuccess:
    """Test retry decorator success scenarios."""

    def test_immediate_success_no_retry(self):
        """Function succeeds on first call, no retries needed."""
        call_count = 0

        @with_retry(max_attempts=3)
        def succeed_immediately():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeed_immediately()

        assert result == "success"
        assert call_count == 1

    def test_success_returns_value(self):
        """Retry decorator preserves return value."""

        @with_retry()
        def return_complex():
            return {"data": [1, 2, 3], "status": "ok"}

        result = return_complex()

        assert result == {"data": [1, 2, 3], "status": "ok"}

    def test_success_with_args(self):
        """Retry decorator preserves function arguments."""

        @with_retry()
        def add(a, b, *, c=0):
            return a + b + c

        result = add(1, 2, c=3)

        assert result == 6

    def test_success_preserves_function_metadata(self):
        """Retry decorator preserves __name__ and __doc__."""

        @with_retry()
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestRetryDecoratorPartialFailure:
    """Test retry decorator partial failure scenarios."""

    def test_succeeds_after_one_retry(self):
        """Function fails once then succeeds."""
        call_count = 0

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DeviceError("Temporary failure")
            return "recovered"

        result = fail_then_succeed()

        assert result == "recovered"
        assert call_count == 2

    def test_succeeds_after_two_retries(self):
        """Function fails twice then succeeds on third attempt."""
        call_count = 0

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise CaptureError("Temporary failure")
            return "eventually_ok"

        result = fail_twice()

        assert result == "eventually_ok"
        assert call_count == 3

    def test_logs_retry_attempts(self):
        """Retry attempts are logged."""
        call_count = 0

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DeviceError("First attempt fails")
            return "ok"

        with patch("tap_tone_pi.core.errors.logger") as mock_logger:
            fail_once()

            # Should have logged a warning for the failed attempt
            mock_logger.warning.assert_called()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "attempt 1/3" in warning_msg
            assert "Retrying" in warning_msg


class TestRetryDecoratorCompleteFailure:
    """Test retry decorator complete failure scenarios."""

    def test_exhausts_retries_and_raises(self):
        """All retry attempts fail, original exception re-raised."""
        call_count = 0

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise DeviceError(f"Failure #{call_count}")

        with pytest.raises(DeviceError) as exc_info:
            always_fail()

        assert call_count == 3
        assert "Failure #3" in str(exc_info.value)

    def test_logs_final_failure(self):
        """Final failure is logged as error."""

        @with_retry(max_attempts=2, delay_seconds=0.01)
        def always_fail():
            raise CaptureError("Persistent failure")

        with patch("tap_tone_pi.core.errors.logger") as mock_logger:
            with pytest.raises(CaptureError):
                always_fail()

            mock_logger.error.assert_called()
            error_msg = mock_logger.error.call_args[0][0]
            assert "failed after 2 attempts" in error_msg

    def test_specific_exception_type_caught(self):
        """Only specified exception types trigger retry."""
        call_count = 0

        @with_retry(max_attempts=3, delay_seconds=0.01, exceptions=(DeviceError,))
        def fail_with_different_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a DeviceError")

        # ValueError is not in exceptions tuple, so no retry
        with pytest.raises(ValueError):
            fail_with_different_error()

        assert call_count == 1  # No retries, immediate failure

    def test_multiple_exception_types(self):
        """Multiple exception types can be specified for retry."""
        call_count = 0

        @with_retry(
            max_attempts=4,
            delay_seconds=0.01,
            exceptions=(DeviceError, CaptureError),
        )
        def fail_with_alternating_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DeviceError("Device issue")
            elif call_count == 2:
                raise CaptureError("Capture issue")
            elif call_count == 3:
                raise DeviceError("Another device issue")
            return "finally_ok"

        result = fail_with_alternating_errors()

        assert result == "finally_ok"
        assert call_count == 4


class TestRetryDecoratorBackoff:
    """Test retry decorator backoff behavior."""

    def test_exponential_backoff(self):
        """Verify exponential backoff timing."""
        call_count = 0
        call_times = []

        @with_retry(max_attempts=3, delay_seconds=0.1)
        def track_timing():
            nonlocal call_count
            call_count += 1
            call_times.append(time.time())
            if call_count < 3:
                raise DeviceError("Retry me")
            return "done"

        track_timing()

        assert len(call_times) == 3

        # Check delays: first delay ~0.1s, second delay ~0.2s (2x backoff)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # Allow some tolerance for timing
        assert 0.08 <= delay1 <= 0.2  # ~0.1s
        assert 0.15 <= delay2 <= 0.4  # ~0.2s (2x backoff)

    def test_custom_backoff_factor(self):
        """Verify custom backoff factor is used."""
        call_times = []
        call_count = 0

        # Config with 3x backoff
        config = RetryConfig(
            max_attempts=3,
            delay_seconds=0.05,
            backoff_factor=3.0,
            exceptions=(Exception,),
        )

        @with_retry(config)
        def track_timing():
            nonlocal call_count
            call_count += 1
            call_times.append(time.time())
            if call_count < 3:
                raise DeviceError("Retry me")
            return "done"

        track_timing()

        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # Second delay should be ~3x the first (with tolerance)
        assert delay2 > delay1 * 2  # At least 2x larger


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_config(self):
        """Default config has sensible defaults."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.delay_seconds == 0.5
        assert config.backoff_factor == 2.0
        assert config.exceptions == (Exception,)

    def test_custom_config(self):
        """Custom config values are preserved."""
        config = RetryConfig(
            max_attempts=5,
            delay_seconds=1.0,
            backoff_factor=1.5,
            exceptions=(ValueError, TypeError),
        )

        assert config.max_attempts == 5
        assert config.delay_seconds == 1.0
        assert config.backoff_factor == 1.5
        assert config.exceptions == (ValueError, TypeError)

    def test_config_is_frozen(self):
        """RetryConfig is immutable."""
        config = RetryConfig()

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            config.max_attempts = 10

    def test_config_overrides(self):
        """Decorator kwargs override config values."""
        config = RetryConfig(max_attempts=5)
        call_count = 0

        @with_retry(config, max_attempts=2, delay_seconds=0.01)
        def fail_always():
            nonlocal call_count
            call_count += 1
            raise DeviceError("fail")

        with pytest.raises(DeviceError):
            fail_always()

        # max_attempts=2 override should be used, not config's 5
        assert call_count == 2


class TestRetryDecoratorEdgeCases:
    """Test retry decorator edge cases."""

    def test_max_attempts_one_no_retry(self):
        """With max_attempts=1, no retries occur."""
        call_count = 0

        @with_retry(max_attempts=1, delay_seconds=0.01)
        def fail_once():
            nonlocal call_count
            call_count += 1
            raise DeviceError("Single attempt")

        with pytest.raises(DeviceError):
            fail_once()

        assert call_count == 1

    def test_zero_delay(self):
        """Zero delay works without sleeping."""
        call_count = 0
        start = time.time()

        @with_retry(max_attempts=3, delay_seconds=0)
        def fast_fail():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DeviceError("Quick failure")
            return "done"

        fast_fail()
        elapsed = time.time() - start

        assert call_count == 3
        assert elapsed < 0.1  # Should be very fast with zero delay

    def test_exception_subclass_caught(self):
        """Exception subclasses are caught when parent is specified."""
        call_count = 0

        @with_retry(
            max_attempts=3,
            delay_seconds=0.01,
            exceptions=(TapToneError,),  # Parent class
        )
        def fail_with_subclass():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DeviceError("Subclass of TapToneError")  # Child class
            return "ok"

        result = fail_with_subclass()

        assert result == "ok"
        assert call_count == 3  # Retried because DeviceError is a TapToneError

    def test_keyboard_interrupt_not_caught(self):
        """KeyboardInterrupt is not caught by retry."""

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def raise_interrupt():
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            raise_interrupt()

    def test_system_exit_not_caught(self):
        """SystemExit is not caught by retry."""

        @with_retry(max_attempts=3, delay_seconds=0.01)
        def raise_exit():
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            raise_exit()
