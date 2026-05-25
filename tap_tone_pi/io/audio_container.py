# INSTRUMENT CLASS: MEASUREMENT
"""
Audio Container with Embedded Sample Rate.

M6 Audit Fix: Sample Rate Consistency Not Enforced.
Functions accept sample_rate as parameter but don't validate against actual audio data.

This module provides:
1. AudioContainer dataclass that bundles signal + sample_rate (immutable pairing)
2. Validation functions to check sample rate consistency
3. Validated loaders that raise on mismatch

Physics basis:
- FFT bin spacing = sample_rate / N
- Incorrect sample_rate causes proportional error in ALL frequency calculations
- 44.1 kHz audio analyzed as 48 kHz → 8.8% frequency error
- This is a systematic, undetectable error without validation

See: docs/CODEBASE_AUDIT_2026.md (M6)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from tap_tone_pi.io.wav import read_wav_mono, read_wav_2ch


class SampleRateMismatchError(ValueError):
    """Raised when sample rate doesn't match expected value."""

    def __init__(
        self,
        expected_fs: int,
        actual_fs: int,
        source: str | None = None,
    ):
        self.expected_fs = expected_fs
        self.actual_fs = actual_fs
        self.source = source
        pct_error = abs(actual_fs - expected_fs) / expected_fs * 100.0
        msg = (
            f"Sample rate mismatch: expected {expected_fs} Hz, "
            f"got {actual_fs} Hz ({pct_error:.1f}% error)"
        )
        if source:
            msg += f" from {source}"
        super().__init__(msg)


@dataclass(frozen=True)
class AudioContainer:
    """Immutable container bundling audio signal with its sample rate.

    Why immutable:
    - Prevents accidental sample_rate changes
    - Signal and sample_rate are inherently coupled
    - Forces explicit conversion if resampling

    Attributes:
        signal: Audio samples as float32 [-1, 1]
        sample_rate: Sample rate in Hz (immutable with signal)
        num_channels: Number of channels (1 or 2)
        source: Optional path/identifier for provenance
    """

    signal: np.ndarray
    sample_rate: int
    num_channels: int = 1
    source: str | None = None

    def __post_init__(self) -> None:
        """Validate container after creation."""
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if not isinstance(self.signal, np.ndarray):
            object.__setattr__(
                self, "signal", np.asarray(self.signal, dtype=np.float32)
            )

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        if self.signal.ndim == 1:
            return self.signal.shape[0] / self.sample_rate
        return self.signal.shape[0] / self.sample_rate

    @property
    def num_samples(self) -> int:
        """Number of samples."""
        return self.signal.shape[0]

    def validate_sample_rate(
        self, expected_fs: int, tolerance_pct: float = 0.1
    ) -> None:
        """
        Validate sample rate matches expected value.

        Args:
            expected_fs: Expected sample rate in Hz
            tolerance_pct: Acceptable deviation as percentage (default 0.1%)

        Raises:
            SampleRateMismatchError: If mismatch exceeds tolerance
        """
        validate_sample_rate(
            expected_fs, self.sample_rate, self.source, tolerance_pct=tolerance_pct
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata (not signal data) to dict."""
        return {
            "sample_rate": self.sample_rate,
            "num_channels": self.num_channels,
            "num_samples": self.num_samples,
            "duration_s": round(self.duration_s, 4),
            "source": self.source,
        }


@dataclass(frozen=True)
class AudioContainer2Ch:
    """Two-channel audio container (reference + roving mics)."""

    reference: np.ndarray
    roving: np.ndarray
    sample_rate: int
    source: str | None = None

    def __post_init__(self) -> None:
        """Validate container after creation."""
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.reference.shape[0] != self.roving.shape[0]:
            raise ValueError(
                f"Channel length mismatch: reference={self.reference.shape[0]}, "
                f"roving={self.roving.shape[0]}"
            )

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return self.reference.shape[0] / self.sample_rate

    @property
    def num_samples(self) -> int:
        """Number of samples per channel."""
        return self.reference.shape[0]

    def validate_sample_rate(
        self, expected_fs: int, tolerance_pct: float = 0.1
    ) -> None:
        """Validate sample rate matches expected value."""
        validate_sample_rate(
            expected_fs, self.sample_rate, self.source, tolerance_pct=tolerance_pct
        )


def validate_sample_rate(
    expected_fs: int,
    actual_fs: int,
    source: str | None = None,
    *,
    tolerance_pct: float = 0.1,
) -> None:
    """
    Validate sample rate matches expected value.

    Args:
        expected_fs: Expected sample rate in Hz
        actual_fs: Actual sample rate from audio file
        source: Optional source identifier for error message
        tolerance_pct: Acceptable deviation as percentage (default 0.1%)
            - 0.1% covers rounding/minor header quirks
            - Use 0 for strict equality

    Raises:
        SampleRateMismatchError: If mismatch exceeds tolerance

    Examples:
        >>> validate_sample_rate(48000, 48000)  # OK
        >>> validate_sample_rate(48000, 44100)  # Raises!
    """
    if expected_fs <= 0:
        raise ValueError(f"expected_fs must be positive, got {expected_fs}")
    if actual_fs <= 0:
        raise ValueError(f"actual_fs must be positive, got {actual_fs}")

    pct_diff = abs(actual_fs - expected_fs) / expected_fs * 100.0

    if pct_diff > tolerance_pct:
        raise SampleRateMismatchError(expected_fs, actual_fs, source)


def load_wav_validated(
    path: str | Path,
    expected_fs: int | None = None,
    *,
    tolerance_pct: float = 0.1,
) -> AudioContainer:
    """
    Load WAV file with optional sample rate validation.

    Args:
        path: Path to WAV file
        expected_fs: Expected sample rate (None to skip validation)
        tolerance_pct: Sample rate tolerance percentage

    Returns:
        AudioContainer with signal and embedded sample rate

    Raises:
        SampleRateMismatchError: If expected_fs provided and doesn't match
    """
    path = Path(path)
    signal, meta = read_wav_mono(path)

    container = AudioContainer(
        signal=signal,
        sample_rate=meta.sample_rate,
        num_channels=meta.num_channels,
        source=str(path),
    )

    if expected_fs is not None:
        container.validate_sample_rate(expected_fs, tolerance_pct=tolerance_pct)

    return container


def load_wav_2ch_validated(
    path: str | Path,
    expected_fs: int | None = None,
    *,
    tolerance_pct: float = 0.1,
) -> AudioContainer2Ch:
    """
    Load 2-channel WAV file with optional sample rate validation.

    Args:
        path: Path to WAV file
        expected_fs: Expected sample rate (None to skip validation)
        tolerance_pct: Sample rate tolerance percentage

    Returns:
        AudioContainer2Ch with reference/roving channels

    Raises:
        SampleRateMismatchError: If expected_fs provided and doesn't match
    """
    path = Path(path)
    ref, rov, meta = read_wav_2ch(path)

    container = AudioContainer2Ch(
        reference=ref,
        roving=rov,
        sample_rate=meta.sample_rate,
        source=str(path),
    )

    if expected_fs is not None:
        container.validate_sample_rate(expected_fs, tolerance_pct=tolerance_pct)

    return container


# Common sample rates with descriptive names
SAMPLE_RATES = {
    "cd_quality": 44100,
    "dvd_quality": 48000,
    "professional": 96000,
    "hi_res": 192000,
    # Common embedded/hardware rates
    "usb_audio": 44100,
    "rpi_default": 44100,
}


def is_standard_sample_rate(fs: int) -> bool:
    """Check if sample rate is a common standard."""
    standard_rates = {
        8000,
        11025,
        16000,
        22050,
        44100,
        48000,
        88200,
        96000,
        176400,
        192000,
    }
    return fs in standard_rates


def get_sample_rate_warning(fs: int) -> str | None:
    """Return warning if sample rate is unusual."""
    if fs <= 0:
        return "Invalid sample rate (must be positive)"
    if fs < 8000:
        return f"Very low sample rate ({fs} Hz) - Nyquist limit {fs // 2} Hz"
    if fs > 200000:
        return f"Very high sample rate ({fs} Hz) - may cause processing issues"
    if not is_standard_sample_rate(fs):
        return f"Non-standard sample rate ({fs} Hz) - verify hardware configuration"
    return None
