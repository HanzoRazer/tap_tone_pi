"""
Signal file writing utilities.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Union

import numpy as np


def signal_to_int16(signal: np.ndarray) -> np.ndarray:
    """
    Convert floating-point signal to 16-bit integer.

    Args:
        signal: Float signal in range [-1, 1]

    Returns:
        Int16 signal scaled to [-32767, 32767]
    """
    # Clip to valid range
    clipped = np.clip(signal, -1.0, 1.0)

    # Scale to int16 range (avoiding overflow at exactly 1.0)
    scaled = clipped * 32767.0

    return scaled.astype(np.int16)


def signal_to_int24(signal: np.ndarray) -> np.ndarray:
    """
    Convert floating-point signal to 24-bit integer (stored in int32).

    Args:
        signal: Float signal in range [-1, 1]

    Returns:
        Int32 signal scaled to [-8388607, 8388607] (24-bit range)
    """
    clipped = np.clip(signal, -1.0, 1.0)
    scaled = clipped * 8388607.0
    return scaled.astype(np.int32)


def signal_to_float32(signal: np.ndarray) -> np.ndarray:
    """
    Ensure signal is float32.

    Args:
        signal: Input signal

    Returns:
        Float32 signal
    """
    return signal.astype(np.float32)


def normalize_signal(
    signal: np.ndarray,
    target_peak: float = 0.95,
    target_rms: float | None = None,
) -> np.ndarray:
    """
    Normalize signal to target level.

    Args:
        signal: Input signal
        target_peak: Target peak amplitude (if target_rms is None)
        target_rms: Target RMS amplitude (overrides target_peak)

    Returns:
        Normalized signal
    """
    if target_rms is not None:
        # Normalize to target RMS
        current_rms = np.sqrt(np.mean(signal**2))
        if current_rms > 0:
            signal = signal * (target_rms / current_rms)
    else:
        # Normalize to target peak
        current_peak = np.max(np.abs(signal))
        if current_peak > 0:
            signal = signal * (target_peak / current_peak)

    return signal


def write_wav(
    signal: np.ndarray,
    filepath: Union[str, Path],
    sample_rate: int = 48000,
    channels: int = 1,
    bit_depth: int = 16,
) -> Path:
    """
    Write signal to WAV file.

    Args:
        signal: Signal array (1D for mono, 2D for stereo with shape [samples, channels])
        filepath: Output file path
        sample_rate: Sample rate in Hz
        channels: Number of channels (1 or 2)
        bit_depth: Bit depth (16 or 24)

    Returns:
        Path to written file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Ensure signal is 2D for consistency
    if signal.ndim == 1:
        if channels == 1:
            signal = signal.reshape(-1, 1)
        else:
            # Duplicate mono to stereo
            signal = np.column_stack([signal, signal])
    elif signal.ndim == 2 and signal.shape[1] != channels:
        raise ValueError(
            f"Signal has {signal.shape[1]} channels but {channels} requested"
        )

    # Convert to appropriate bit depth
    if bit_depth == 16:
        data = signal_to_int16(signal)
        sample_width = 2
    elif bit_depth == 24:
        # 24-bit requires special handling
        data = signal_to_int24(signal)
        sample_width = 3
    else:
        raise ValueError(f"Unsupported bit depth: {bit_depth}")

    # Write WAV file
    with wave.open(str(filepath), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)

        if bit_depth == 24:
            # Pack 24-bit samples (3 bytes per sample)
            packed = bytearray()
            for frame in data:
                for sample in (frame if channels > 1 else [frame]):
                    # Extract lower 3 bytes of int32
                    b = int(sample).to_bytes(4, byteorder="little", signed=True)
                    packed.extend(b[:3])
            wav_file.writeframes(bytes(packed))
        else:
            wav_file.writeframes(data.tobytes())

    return filepath


def write_raw(
    signal: np.ndarray,
    filepath: Union[str, Path],
    dtype: str = "float32",
) -> Path:
    """
    Write signal to raw binary file.

    Args:
        signal: Signal array
        filepath: Output file path
        dtype: Data type ('float32', 'float64', 'int16', 'int24')

    Returns:
        Path to written file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if dtype == "float32":
        data = signal.astype(np.float32)
    elif dtype == "float64":
        data = signal.astype(np.float64)
    elif dtype == "int16":
        data = signal_to_int16(signal)
    elif dtype == "int24":
        data = signal_to_int24(signal)
    else:
        raise ValueError(f"Unsupported dtype: {dtype}")

    data.tofile(filepath)
    return filepath


def read_wav(filepath: Union[str, Path]) -> tuple[np.ndarray, int]:
    """
    Read WAV file to numpy array.

    Args:
        filepath: Path to WAV file

    Returns:
        Tuple of (signal as float32 in [-1, 1], sample_rate)
    """
    filepath = Path(filepath)

    with wave.open(str(filepath), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        n_channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        n_frames = wav_file.getnframes()

        raw_data = wav_file.readframes(n_frames)

    # Convert to numpy array based on sample width
    if sample_width == 1:
        # 8-bit unsigned
        data = np.frombuffer(raw_data, dtype=np.uint8)
        signal = (data.astype(np.float32) - 128) / 128.0
    elif sample_width == 2:
        # 16-bit signed
        data = np.frombuffer(raw_data, dtype=np.int16)
        signal = data.astype(np.float32) / 32768.0
    elif sample_width == 3:
        # 24-bit signed (packed)
        n_samples = len(raw_data) // 3
        signal = np.zeros(n_samples, dtype=np.float32)
        for i in range(n_samples):
            b = raw_data[i * 3 : (i + 1) * 3]
            # Sign-extend from 24-bit
            val = int.from_bytes(b, byteorder="little", signed=True)
            # Handle sign extension for negative values
            if b[2] & 0x80:
                val -= 0x1000000
            signal[i] = val / 8388608.0
    elif sample_width == 4:
        # 32-bit (could be int or float)
        try:
            data = np.frombuffer(raw_data, dtype=np.float32)
            signal = data
        except ValueError:
            data = np.frombuffer(raw_data, dtype=np.int32)
            signal = data.astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    # Reshape for multi-channel
    if n_channels > 1:
        signal = signal.reshape(-1, n_channels)

    return signal, sample_rate
