from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
from scipy.io import wavfile


@dataclass(frozen=True)
class Wav2Ch:
    sample_rate: int
    x_ref: np.ndarray  # shape (n,)
    x_rov: np.ndarray  # shape (n,)


def read_wav_2ch(path: Path) -> Wav2Ch:
    fs, data = wavfile.read(str(path))
    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError(f"Expected 2-channel wav, got shape={data.shape}")
    # normalize int16/int32 to float32 [-1,1]
    if np.issubdtype(data.dtype, np.integer):
        maxv = float(np.iinfo(data.dtype).max)
        x = (data.astype(np.float32) / maxv).astype(np.float32)
    else:
        x = data.astype(np.float32)

    return Wav2Ch(sample_rate=int(fs), x_ref=x[:, 0].copy(), x_rov=x[:, 1].copy())


def write_wav_2ch(path: Path, fs: int, x_ref: np.ndarray, x_rov: np.ndarray) -> None:
    x_ref = np.asarray(x_ref, dtype=np.float32).reshape(-1)
    x_rov = np.asarray(x_rov, dtype=np.float32).reshape(-1)
    n = min(x_ref.size, x_rov.size)
    x_ref = x_ref[:n]
    x_rov = x_rov[:n]
    x = np.stack([x_ref, x_rov], axis=1)
    x = np.clip(x, -1.0, 1.0)
    x_i16 = (x * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(path), fs, x_i16)
