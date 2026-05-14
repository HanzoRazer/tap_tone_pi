"""Centralized error handling for tap_tone_pi.

Provides:
- Custom exception hierarchy
- Retry decorator for transient failures
- Error context utilities
"""

from __future__ import annotations

import functools
import logging
import time
from dataclasses import dataclass
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


# -----------------------------------------------------------------------------
# Custom Exception Hierarchy
# -----------------------------------------------------------------------------


class TapToneError(Exception):
    """Base exception for all tap_tone_pi errors."""

    def __init__(self, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.suggestion = suggestion


class DeviceError(TapToneError):
    """Audio device related errors."""

    pass


class DeviceNotFoundError(DeviceError):
    """Specified audio device was not found."""

    pass


class DeviceOpenError(DeviceError):
    """Failed to open audio device."""

    pass


class CaptureError(TapToneError):
    """Audio capture related errors."""

    pass


class CaptureTimeoutError(CaptureError):
    """Audio capture timed out."""

    pass


class AnalysisError(TapToneError):
    """Audio analysis related errors."""

    pass


class QualityError(TapToneError):
    """Quality check related errors."""

    pass


class ValidationError(TapToneError):
    """Input validation errors."""

    pass


class FileFormatError(TapToneError):
    """File format or parsing errors."""

    pass


class ConfigError(TapToneError):
    """Configuration related errors."""

    pass


# -----------------------------------------------------------------------------
# Retry Decorator
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    delay_seconds: float = 0.5
    backoff_factor: float = 2.0
    exceptions: tuple = (Exception,)


def with_retry(
    config: RetryConfig | None = None,
    *,
    max_attempts: int | None = None,
    delay_seconds: float | None = None,
    exceptions: tuple | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry a function on transient failures.

    Args:
        config: Full retry configuration
        max_attempts: Override max attempts
        delay_seconds: Override initial delay
        exceptions: Override exception types to catch

    Returns:
        Decorated function with retry behavior

    Example:
        @with_retry(max_attempts=3, exceptions=(DeviceError,))
        def open_device(device_id):
            ...
    """
    if config is None:
        config = RetryConfig()

    actual_max = max_attempts if max_attempts is not None else config.max_attempts
    actual_delay = delay_seconds if delay_seconds is not None else config.delay_seconds
    actual_exc = exceptions if exceptions is not None else config.exceptions

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None
            delay = actual_delay

            for attempt in range(1, actual_max + 1):
                try:
                    return func(*args, **kwargs)
                except actual_exc as e:
                    last_error = e
                    if attempt < actual_max:
                        logger.warning(
                            f"{func.__name__} attempt {attempt}/{actual_max} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= config.backoff_factor
                    else:
                        logger.error(
                            f"{func.__name__} failed after {actual_max} attempts: {e}"
                        )

            # Re-raise the last error
            if last_error is not None:
                raise last_error
            raise RuntimeError("Retry loop exited without result or error")

        return wrapper

    return decorator


# -----------------------------------------------------------------------------
# Error Context
# -----------------------------------------------------------------------------


@dataclass
class ErrorContext:
    """Context information for error reporting."""

    operation: str
    device: str | None = None
    file_path: str | None = None
    details: dict | None = None

    def format_message(self, error: Exception) -> str:
        """Format error message with context."""
        parts = [f"Error during {self.operation}: {error}"]

        if self.device:
            parts.append(f"  Device: {self.device}")
        if self.file_path:
            parts.append(f"  File: {self.file_path}")
        if self.details:
            for key, value in self.details.items():
                parts.append(f"  {key}: {value}")

        return "\n".join(parts)


def format_error_for_user(error: Exception, context: ErrorContext | None = None) -> str:
    """Format an error message for display to users.

    Args:
        error: The exception
        context: Optional error context

    Returns:
        Human-readable error message
    """
    if context:
        message = context.format_message(error)
    else:
        message = str(error)

    # Add suggestion if available
    if isinstance(error, TapToneError) and error.suggestion:
        message += f"\n\nSuggestion: {error.suggestion}"

    return message


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------


def handle_device_error(error: Exception, device_id: int | None = None) -> DeviceError:
    """Convert generic exception to appropriate DeviceError.

    Args:
        error: Original exception
        device_id: Device that caused the error

    Returns:
        Appropriate DeviceError subclass
    """
    msg = str(error).lower()

    if "not found" in msg or "invalid" in msg:
        suggestion = "Run 'ttp devices' to list available devices"
        return DeviceNotFoundError(
            f"Device {device_id} not found: {error}",
            suggestion=suggestion,
        )

    if "permission" in msg or "access" in msg:
        suggestion = "Check audio device permissions in system settings"
        return DeviceOpenError(
            f"Cannot access device {device_id}: {error}",
            suggestion=suggestion,
        )

    if "busy" in msg or "in use" in msg:
        suggestion = "Close other applications using the audio device"
        return DeviceOpenError(
            f"Device {device_id} is busy: {error}",
            suggestion=suggestion,
        )

    return DeviceError(f"Device error: {error}")
