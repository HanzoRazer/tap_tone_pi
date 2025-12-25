from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import sounddevice as sd


@dataclass(frozen=True)
class CaptureResult:
    sample_rate: int
    audio: np.ndarray  # shape (n,)


def list_devices() -> list[dict[str, Any]]:
    devices = sd.query_devices()
    out: list[dict[str, Any]] = []
    for i, d in enumerate(devices):
        out.append(
            {
                "index": i,
                "name": d.get("name"),
                "max_input_channels": int(d.get("max_input_channels") or 0),
                "max_output_channels": int(d.get("max_output_channels") or 0),
                "default_samplerate": d.get("default_samplerate"),
            }
        )
    return out


def record_audio(
    *,
    device: int | None,
    sample_rate: int,
    channels: int,
    seconds: float,
) -> CaptureResult:
    if channels != 1:
        raise ValueError("Phase 1 expects mono capture (channels=1).")
    if seconds <= 0:
        raise ValueError("seconds must be > 0")

    sd.default.samplerate = sample_rate
    if device is not None:
        sd.default.device = (device, None)

    n_samples = int(sample_rate * seconds)

    audio = sd.rec(frames=n_samples, channels=channels, dtype="float32", blocking=True)
    audio = audio.reshape(-1)  # mono
    audio = np.nan_to_num(audio, nan=0.0)

    return CaptureResult(sample_rate=sample_rate, audio=audio)
